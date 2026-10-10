"""Correção manual e reclassificação contra SQLite temporário (spec R6, Q15)."""

from datetime import datetime

from sqlalchemy import select

from app.classification.service import apply_correction, reclassify_unreviewed
from app.ingestion.pipeline import import_file
from app.repo.models import Account, Category, MerchantMemory, Transaction

NOW = datetime(2026, 10, 1, 12, 0, 0)
LATER = datetime(2026, 10, 2, 9, 0, 0)
CARD_JUL = "nubank/Nubank_2026-08-08.csv"
CARD_AUG = "nubank/Nubank_2026-09-08.csv"
ITAU_ACCOUNT = "itau/itau_extrato_A.pdf"
ITAU_CARD = "itau/itau_fatura_2026-01.pdf"


def _import(session, fixture_file, relative):
    return import_file(session, *fixture_file(relative), now=NOW)


def _category(session, name):
    return session.scalar(select(Category.id).where(Category.name == name))


def _by_key(session, merchant_key):
    return list(
        session.scalars(
            select(Transaction)
            .where(Transaction.merchant_key == merchant_key)
            .order_by(Transaction.id)
        )
    )


def _correct(session, transaction, category_id, kind="despesa", ignore_reason=None):
    return apply_correction(
        session,
        transaction.id,
        kind=kind,
        ignore_reason=ignore_reason,
        category_id=category_id,
        now=LATER,
    )


def test_imported_transactions_get_seeded_rule_and_stay_unreviewed(session, fixture_file):
    _import(session, fixture_file, CARD_AUG)

    uber = _by_key(session, "UBER NUPAY")
    assert {t.category_id for t in uber} == {_category(session, "Transporte")}
    assert {(t.category_source, t.category_confidence) for t in uber} == {("regra", 0.9)}
    assert all(t.reviewed_at is None for t in uber)


def test_bank_category_fills_low_confidence_category_and_keyword_wins(session, fixture_file):
    _import(session, fixture_file, ITAU_CARD)

    netflix = _by_key(session, "NETFLIX COM")[0]
    diversos = _by_key(session, "LOJA EXEMPLO")[0]
    assert (netflix.category_id, netflix.category_confidence) == (
        _category(session, "Lazer e Tecnologia"),
        0.9,  # a palavra-chave vence a categoria do banco
    )
    assert (diversos.category_id, diversos.category_source) == (None, "nenhuma")


def test_correction_updates_memory_and_recategorizes_only_unreviewed(session, fixture_file):
    _import(session, fixture_file, CARD_AUG)
    lazer, saude = _category(session, "Lazer e Tecnologia"), _category(session, "Saúde e Bem-Estar")
    first, second, third = _by_key(session, "STEAM")

    _correct(session, first, lazer)
    session.refresh(second), session.refresh(third)
    assert (first.category_source, first.reviewed_at) == ("manual", LATER)
    assert [(t.category_id, t.category_source) for t in (second, third)] == [(lazer, "memoria")] * 2

    _correct(session, second, saude)
    session.refresh(first), session.refresh(third)
    assert first.category_id == lazer  # revisada: intacta
    assert third.category_id == saude  # não revisada: segue a memória nova
    assert session.get(MerchantMemory, "STEAM").category_id == saude


def test_reviewed_transactions_survive_reclassification_and_new_imports(session, fixture_file):
    _import(session, fixture_file, CARD_AUG)
    lazer = _category(session, "Lazer e Tecnologia")
    (reviewed, *_) = _by_key(session, "STEAM")
    _correct(session, reviewed, lazer)
    session.execute(MerchantMemory.__table__.update().values(category_id=None))

    reclassify_unreviewed(session)
    _import(session, fixture_file, CARD_JUL)
    session.refresh(reviewed)

    assert (reviewed.category_id, reviewed.category_source) == (lazer, "manual")


def test_memory_is_used_by_later_imports(session, fixture_file):
    _import(session, fixture_file, CARD_AUG)
    lazer = _category(session, "Lazer e Tecnologia")
    _correct(session, _by_key(session, "STEAM")[0], lazer)

    _import(session, fixture_file, CARD_JUL)

    steam = _by_key(session, "STEAM")
    assert len(steam) == 6
    assert {t.category_id for t in steam} == {lazer}


def test_structural_rule_is_not_overridden_by_memory_recategorization(session, fixture_file):
    _import(session, fixture_file, CARD_AUG)
    payment, *_ = _by_key(session, "PAGAMENTO RECEBIDO")
    session.add(MerchantMemory(merchant_key="PAGAMENTO RECEBIDO", kind="despesa", updated_at=NOW))
    session.flush()

    reclassify_unreviewed(session, merchant_key="PAGAMENTO RECEBIDO")
    session.refresh(payment)

    assert (payment.kind, payment.ignore_reason) == ("ignorar", "pagamento_fatura")


def test_manual_correction_can_override_structural_rule_on_that_transaction_only(
    session, fixture_file
):
    _import(session, fixture_file, CARD_AUG)
    (payment,) = _by_key(session, "PAGAMENTO RECEBIDO")

    _correct(session, payment, None, kind="despesa")

    assert (payment.kind, payment.category_source) == ("despesa", "manual")


def test_investment_suggestion_needs_holder_and_is_never_applied(session, fixture_file):
    _import(session, fixture_file, ITAU_ACCOUNT)
    account = session.scalars(select(Account)).one()
    (pix,) = _by_key(session, "PIX FULANO")
    (cofrinhos,) = _by_key(session, "APLICACAO COFRINHOS")
    assert (pix.suggested_ignore_reason, cofrinhos.suggested_ignore_reason) == (
        None,
        "investimento",
    )

    account.holder = "Fulano"
    reclassify_unreviewed(session, account_id=account.id)
    session.refresh(pix)

    assert (pix.kind, pix.ignore_reason, pix.suggested_ignore_reason) == (
        "despesa",
        None,
        "investimento",
    )


def test_confirming_investment_applies_it_without_polluting_memory(session, fixture_file):
    _import(session, fixture_file, ITAU_ACCOUNT)
    (cofrinhos,) = _by_key(session, "APLICACAO COFRINHOS")

    _correct(session, cofrinhos, None, kind="ignorar", ignore_reason="investimento")

    assert (cofrinhos.kind, cofrinhos.ignore_reason) == ("ignorar", "investimento")
    assert cofrinhos.suggested_ignore_reason is None
    assert cofrinhos.reviewed_at == LATER
    assert session.get(MerchantMemory, "APLICACAO COFRINHOS") is None


def test_correction_of_unknown_transaction_returns_none(session):
    assert (
        apply_correction(
            session, 999, kind="despesa", ignore_reason=None, category_id=None, now=LATER
        )
        is None
    )
