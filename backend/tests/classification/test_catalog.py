"""Exclusão de categoria (spec §8): tudo que aponta para ela volta a "Sem categoria"."""

from datetime import date, datetime

from sqlalchemy import func, select

from app.classification import catalog
from app.classification.service import apply_correction
from app.ingestion.pipeline import import_file
from app.repo.models import (
    BankCategoryMap,
    Category,
    InstallmentGroupOverride,
    KeywordRule,
    MerchantMemory,
    Transaction,
)

NOW = datetime(2026, 10, 1, 12, 0, 0)
LATER = datetime(2026, 10, 2, 9, 0, 0)
CARD_AUG = "nubank/Nubank_2026-09-08.csv"


def _category(session, name):
    return session.scalar(select(Category.id).where(Category.name == name))


def _uber(session):
    return list(
        session.scalars(select(Transaction).where(Transaction.merchant_key == "UBER NUPAY"))
    )


def test_delete_clears_reviewed_and_unreviewed_transactions_and_what_points_to_it(
    session, fixture_file
):
    import_file(session, *fixture_file(CARD_AUG), now=NOW)
    transporte = _category(session, "Transporte")
    uber = _uber(session)
    apply_correction(  # um revisado (manual) e um não revisado (regra)
        session, uber[0].id, kind="despesa", ignore_reason=None, category_id=transporte, now=LATER
    )
    other_before = session.scalar(
        select(func.count()).where(
            Transaction.category_id.is_not(None), Transaction.category_id != transporte
        )
    )
    session.add_all(
        [
            Transaction(
                account_id=uber[0].account_id,
                occurred_on=date(2026, 11, 1),
                competence_month="2026-11",
                amount_cents=1000,
                description_raw="Loja - Parcela 2/3",
                merchant_key="LOJA",
                normalizer_version=1,
                kind="despesa",
                category_id=transporte,
                category_source="manual",
                status="projetada",
                dedup_key="proj:loja",
                created_at=NOW,
            ),
            InstallmentGroupOverride(
                installment_group_key="loja", category_id=transporte, updated_at=NOW
            ),
            BankCategoryMap(bank_category="TRANSPORTE", category_id=transporte),
        ]
    )
    session.flush()

    affected = catalog.delete_category(session, transporte)

    assert affected == len(uber) + 1
    assert session.get(Category, transporte) is None
    session.expire_all()
    for t in [
        *_uber(session),
        session.scalar(select(Transaction).where(Transaction.status == "projetada")),
    ]:
        assert (t.category_id, t.category_source, t.category_confidence, t.reviewed_at) == (
            None,
            "nenhuma",
            None,
            None,
        )
    assert session.scalar(select(func.count()).select_from(InstallmentGroupOverride)) == 0
    assert all(m.category_id != transporte for m in session.scalars(select(BankCategoryMap)))
    assert session.get(BankCategoryMap, "TRANSPORTE") is None
    assert all(rule.category_id != transporte for rule in session.scalars(select(KeywordRule)))
    assert (
        session.scalar(
            select(func.count()).where(
                Transaction.category_id.is_not(None), Transaction.category_id != transporte
            )
        )
        == other_before
    )


def test_delete_keeps_memory_kind_but_drops_its_category(session, fixture_file):
    import_file(session, *fixture_file(CARD_AUG), now=NOW)
    transporte = _category(session, "Transporte")
    apply_correction(
        session,
        _uber(session)[0].id,
        kind="despesa",
        ignore_reason=None,
        category_id=transporte,
        now=LATER,
    )

    catalog.delete_category(session, transporte)

    memory = session.get(MerchantMemory, "UBER NUPAY")
    assert (memory.category_id, memory.kind) == (None, "despesa")


def test_delete_unknown_category_is_not_found(session):
    assert catalog.delete_category(session, 9999) == "not_found"
