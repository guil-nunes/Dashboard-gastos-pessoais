"""Parcelas projetadas (spec R10): reconstrução, substituição pela real e independência de ordem."""

from datetime import datetime
from itertools import permutations

from sqlalchemy import func, select

from app.analytics.dashboard import month_summary
from app.classification.service import apply_correction, reclassify_unreviewed
from app.ingestion.next_invoice import check_next_invoice
from app.ingestion.pipeline import import_file
from app.ingestion.types import NextInvoiceLine
from app.ingestion.undo import undo_import
from app.repo.imports import rebuild_projected
from app.repo.models import (
    Account,
    Category,
    InstallmentGroupOverride,
    KeywordRule,
    MerchantMemory,
    Transaction,
)
from app.repo.transactions import list_transactions

NOW = datetime(2026, 10, 1, 12, 0, 0)
CARD_JUL = "nubank/Nubank_2026-08-08.csv"
CARD_AUG = "nubank/Nubank_2026-09-08.csv"
ITAU_A = "itau/itau_extrato_A.pdf"
ITAU_CARD = "itau/itau_fatura_2026-01.pdf"
ORDER_DEPENDENT = {"id", "import_batch_id", "created_at", "account_id"}


def _import(session, fixture_file, *relatives):
    return [import_file(session, *fixture_file(r), now=NOW) for r in relatives]


def _snapshot(session):
    columns = [c for c in Transaction.__table__.columns if c.name not in ORDER_DEPENDENT]
    return sorted(tuple(row) for row in session.execute(select(*columns)))


def _projected(session):
    rows = session.scalars(select(Transaction).where(Transaction.status == "projetada"))
    return sorted(
        (t.description_raw, t.installment_number, t.competence_month, t.amount_cents) for t in rows
    )


def _category(session, name):
    return session.scalar(select(Category.id).where(Category.name == name))


def test_card_invoice_projects_the_remaining_installments(session, fixture_file):
    _import(session, fixture_file, CARD_JUL)

    assert _projected(session) == [
        ("Latam Air*0000 - Parcela 4/4", 4, "2026-08", 90946),
        ("Pag*Steam - Parcela 2/3", 2, "2026-08", 1360),
        ("Pag*Steam - Parcela 3/3", 3, "2026-08", 794),
        ("Pag*Steam - Parcela 3/3", 3, "2026-08", 1331),
        ("Pag*Steam - Parcela 3/3", 3, "2026-09", 1360),
    ]
    row = session.scalars(select(Transaction).where(Transaction.status == "projetada")).first()
    assert (row.import_batch_id, row.reviewed_at, row.dedup_key.startswith("proj:grp:")) == (
        None,
        None,
        True,
    )


def test_real_installment_replaces_the_projected_one(session, fixture_file):
    results = _import(session, fixture_file, CARD_JUL, CARD_AUG)

    assert [r.status for r in results] == ["importado", "importado"]  # sem erro de UNIQUE
    # Steam 1/3 (13,60) e 2/3 (13,58) são o mesmo grupo: sobra só a 3/3, com o valor da última real.
    assert _projected(session) == [("Pag*Steam - Parcela 3/3", 3, "2026-09", 1358)]
    duplicated = (
        select(Transaction.installment_group_key, Transaction.installment_number)
        .where(Transaction.installment_group_key.is_not(None))
        .group_by(Transaction.installment_group_key, Transaction.installment_number)
        .having(func.count() > 1)
    )
    assert session.execute(duplicated).all() == []


def test_import_order_does_not_change_projected_rows(new_session, fixture_file):
    baseline = None
    for order in permutations([CARD_JUL, CARD_AUG, ITAU_CARD]):
        session = new_session()
        _import(session, fixture_file, *order)
        snapshot = _snapshot(session)
        if baseline is None:
            baseline = snapshot
        assert snapshot == baseline, order
    assert any("projetada" in row for row in baseline)


def test_undo_rebuilds_projected_like_importing_only_the_other(new_session, fixture_file):
    session = new_session()
    jul, aug = _import(session, fixture_file, CARD_JUL, CARD_AUG)

    assert undo_import(session, aug.batch_id, NOW)

    expected = new_session()
    _import(expected, fixture_file, CARD_JUL)
    assert _snapshot(session) == _snapshot(expected)
    assert len(_projected(session)) == 5


def test_undoing_the_first_invoice_keeps_the_later_projection(new_session, fixture_file):
    session = new_session()
    jul, aug = _import(session, fixture_file, CARD_JUL, CARD_AUG)

    undo_import(session, jul.batch_id, NOW)

    expected = new_session()
    _import(expected, fixture_file, CARD_AUG)
    assert _snapshot(session) == _snapshot(expected)


def test_itau_invoice_projects_installments_from_the_purchase_month(session, fixture_file):
    _import(session, fixture_file, ITAU_CARD)

    projected = _projected(session)
    mercado = [p for p in projected if p[0].startswith("MERCADOLIVRE")]
    anuidade = [p for p in projected if p[0].startswith("ANUIDADE")]

    assert mercado == [
        ("MERCADOLIVRE*5525310/12", 10, "2026-02", 1071),
        ("MERCADOLIVRE*5525311/12", 11, "2026-03", 1071),
        ("MERCADOLIVRE*5525312/12", 12, "2026-04", 1071),
    ]
    assert [p[1] for p in anuidade] == list(range(3, 13))
    assert [p[2] for p in anuidade][:3] == ["2026-02", "2026-03", "2026-04"]


def test_anticipation_does_not_create_duplicate_groups_or_projections(session, fixture_file):
    _import(session, fixture_file, ITAU_CARD)

    for root in ("PG *ENJOEI.COM.BR 0", "SHOPEE *SPECIALSTY0"):
        rows = session.scalars(
            select(Transaction).where(Transaction.description_raw.like(f"{root}%"))
        ).all()
        reals = [t for t in rows if t.status == "real"]
        assert len({t.installment_group_key for t in reals}) == 1
        assert {t.competence_month for t in reals} == {"2025-12"}  # antecipadas na menor parcela
        assert [t for t in rows if t.status == "projetada"] == []  # grupo completo


def test_group_survives_cents_remainder_between_invoices(session, fixture_file):
    _import(session, fixture_file, CARD_JUL, CARD_AUG)

    steam = session.scalars(
        select(Transaction).where(Transaction.description_raw.like("Pag*Steam - Parcela %/3"))
    ).all()
    groups = {}
    for t in steam:
        groups.setdefault(t.installment_group_key, set()).add(t.installment_number)
    assert {1, 2, 3} in groups.values()  # 13,60 → 13,58 → projetada 3/3, mesmo grupo


def test_projected_inherits_the_category_of_the_last_real(session, fixture_file):
    transporte = _category(session, "Transporte")
    session.add(
        KeywordRule(pattern="latam", match_type="contains", category_id=transporte, priority=1)
    )
    session.flush()

    _import(session, fixture_file, CARD_JUL)

    latam = session.scalars(
        select(Transaction).where(
            Transaction.status == "projetada", Transaction.description_raw.like("Latam%")
        )
    ).one()
    assert (latam.category_id, latam.category_source, latam.category_confidence) == (
        transporte,
        "regra",
        0.9,
    )
    assert (latam.kind, latam.reviewed_at) == ("despesa", None)


def test_correcting_one_installment_sets_the_group_override(session, fixture_file):
    _import(session, fixture_file, ITAU_CARD)
    saude = _category(session, "Saúde e Bem-Estar")
    real = session.scalars(
        select(Transaction).where(
            Transaction.status == "real", Transaction.description_raw.like("ANUIDADE%")
        )
    ).one()

    apply_correction(
        session, real.id, kind="despesa", ignore_reason=None, category_id=saude, now=NOW
    )

    override = session.get(InstallmentGroupOverride, real.installment_group_key)
    assert override.category_id == saude
    projected = session.scalars(
        select(Transaction).where(
            Transaction.status == "projetada", Transaction.description_raw.like("ANUIDADE%")
        )
    ).all()
    assert len(projected) == 10
    assert {(t.category_id, t.category_source) for t in projected} == {(saude, "manual")}

    rebuild_projected(session, [real.account_id], NOW)  # o override sobrevive à reconstrução
    again = session.scalars(
        select(Transaction.category_id).where(
            Transaction.status == "projetada", Transaction.description_raw.like("ANUIDADE%")
        )
    ).all()
    assert set(again) == {saude}


def test_projected_are_excluded_from_totals_pending_and_reclassification(session, fixture_file):
    _import(session, fixture_file, CARD_JUL)
    assert _projected(session)

    # Total do dashboard: a competência 2026-08 só tem projetadas.
    assert month_summary(session, "2026-08").total_cents == 0
    # Fila de revisão: nenhuma projetada.
    rows, _ = list_transactions(session, pending=True, limit=500)
    assert rows and all(t.status == "real" for t, _ in rows)
    # Reclassificação automática não toca nelas.
    session.add(
        MerchantMemory(
            merchant_key="STEAM",
            category_id=_category(session, "Lazer e Tecnologia"),
            kind="despesa",
            updated_at=NOW,
        )
    )
    session.flush()
    reclassify_unreviewed(session)
    steam = session.scalars(
        select(Transaction).where(
            Transaction.status == "projetada", Transaction.merchant_key == "STEAM"
        )
    ).all()
    assert steam and {t.category_id for t in steam} == {None}


def test_next_invoice_check_reports_only_divergences(session, fixture_file):
    _import(session, fixture_file, ITAU_CARD)
    account = session.scalars(select(Account).where(Account.kind == "cartao")).one()
    lines = [
        NextInvoiceLine("MERCADOLIVRE*5525310/12", 1071),  # confere
        NextInvoiceLine("MERCADOLIVRE*5525311/12", 999),  # valor diferente
        NextInvoiceLine("OUTRA COMPRA*0000001/03", 500),  # sem projetada
    ]

    warnings = check_next_invoice(session, account.id, lines)

    assert len(warnings) == 2
    assert "5525311/12" in warnings[0] and "R$ 9,99" in warnings[0] and "R$ 10,71" in warnings[0]
    assert "OUTRA COMPRA" in warnings[1]


def test_real_invoice_has_no_next_invoice_warnings(session, fixture_file):
    (result,) = _import(session, fixture_file, ITAU_CARD)

    assert result.warnings == []


def test_installment_first_month_is_stored_for_real_rows(session, fixture_file):
    _import(session, fixture_file, CARD_JUL, ITAU_A)

    rows = session.scalars(
        select(Transaction).where(
            Transaction.status == "real", Transaction.installment_number.is_not(None)
        )
    ).all()
    assert rows and all(t.installment_first_month for t in rows)
    latam = next(t for t in rows if t.description_raw.startswith("Latam"))
    assert latam.installment_first_month == "2026-05"  # 3/4 em jul → parcela 1 em mai
