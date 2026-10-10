"""`renormalize` (spec R5): chaves novas, migração de memória e revisadas preservadas."""

from datetime import datetime

import pytest
from sqlalchemy import select

from app.classification.service import apply_correction
from app.domain.normalizer import normalize_merchant as real_normalize
from app.ingestion import renormalize as module
from app.ingestion.pipeline import import_file
from app.repo.models import Category, LlmCache, MerchantMemory, RecurrenceOverride, Transaction

NOW = datetime(2026, 10, 1, 12, 0, 0)
OLDER = datetime(2026, 9, 1)
NEWER = datetime(2026, 9, 20)
CARD_AUG = "nubank/Nubank_2026-09-08.csv"


@pytest.fixture
def v2_normalizer(monkeypatch):
    """Normalizador v2 fictício: remove o sufixo ' EXEMPLO' da chave."""
    monkeypatch.setattr(module, "NORMALIZER_VERSION", 2)
    monkeypatch.setattr(
        module, "normalize_merchant", lambda text: real_normalize(text).replace(" EXEMPLO", "")
    )


def _category(session, name):
    return session.scalar(select(Category.id).where(Category.name == name))


def test_up_to_date_database_is_left_untouched(session, fixture_file):
    import_file(session, *fixture_file(CARD_AUG), now=NOW)

    result = module.renormalize(session)

    assert (result.transactions, result.keys_changed, result.reclassified) == (0, 0, 0)


def test_transactions_get_new_key_and_version(session, fixture_file, v2_normalizer):
    import_file(session, *fixture_file(CARD_AUG), now=NOW)

    result = module.renormalize(session)

    keys = set(session.scalars(select(Transaction.merchant_key)))
    assert {"FORNERIA", "EXEMPLO LOJA"} <= keys and "FORNERIA EXEMPLO" not in keys
    assert set(session.scalars(select(Transaction.normalizer_version))) == {2}
    assert result.transactions == 11 and result.keys_changed == 1


def test_memory_moves_to_new_key_and_newer_entry_wins_on_collapse(
    session, fixture_file, v2_normalizer
):
    import_file(session, *fixture_file(CARD_AUG), now=NOW)
    alimentacao, lazer = _category(session, "Alimentação"), _category(session, "Lazer e Tecnologia")
    session.add_all(
        [
            MerchantMemory(
                merchant_key="FORNERIA EXEMPLO",
                category_id=alimentacao,
                kind="despesa",
                updated_at=NEWER,
            ),
            MerchantMemory(
                merchant_key="FORNERIA", category_id=lazer, kind="despesa", updated_at=OLDER
            ),
            LlmCache(merchant_key="FORNERIA EXEMPLO", raw_response="{}", created_at=NEWER),
            RecurrenceOverride(merchant_key="FORNERIA EXEMPLO", is_recurring=True),
        ]
    )
    session.flush()

    module.renormalize(session)
    session.commit()

    memory = {m.merchant_key: m for m in session.scalars(select(MerchantMemory))}
    assert "FORNERIA EXEMPLO" not in memory
    assert (memory["FORNERIA"].category_id, memory["FORNERIA"].updated_at) == (alimentacao, NEWER)
    assert session.scalars(select(LlmCache.merchant_key)).all() == ["FORNERIA"]
    assert session.scalars(select(RecurrenceOverride.merchant_key)).all() == ["FORNERIA"]


def test_older_migrated_entry_does_not_replace_newer_existing(session, fixture_file, v2_normalizer):
    import_file(session, *fixture_file(CARD_AUG), now=NOW)
    alimentacao, lazer = _category(session, "Alimentação"), _category(session, "Lazer e Tecnologia")
    session.add_all(
        [
            MerchantMemory(
                merchant_key="FORNERIA EXEMPLO",
                category_id=alimentacao,
                kind="despesa",
                updated_at=OLDER,
            ),
            MerchantMemory(
                merchant_key="FORNERIA", category_id=lazer, kind="despesa", updated_at=NEWER
            ),
        ]
    )
    session.flush()

    module.renormalize(session)

    assert session.get(MerchantMemory, "FORNERIA").category_id == lazer
    assert session.get(MerchantMemory, "FORNERIA EXEMPLO") is None


def test_unreviewed_follow_migrated_memory_and_reviewed_keep_their_category(
    session, fixture_file, v2_normalizer
):
    import_file(session, *fixture_file(CARD_AUG), now=NOW)
    alimentacao, saude = _category(session, "Alimentação"), _category(session, "Saúde e Bem-Estar")
    (fomeria,) = session.scalars(
        select(Transaction).where(Transaction.merchant_key == "FORNERIA EXEMPLO")
    )
    session.add(
        MerchantMemory(
            merchant_key="FORNERIA EXEMPLO",
            category_id=alimentacao,
            kind="despesa",
            updated_at=NEWER,
        )
    )
    session.flush()

    module.renormalize(session)
    session.refresh(fomeria)
    assert (fomeria.category_id, fomeria.category_source) == (alimentacao, "memoria")

    apply_correction(
        session, fomeria.id, kind="despesa", ignore_reason=None, category_id=saude, now=NOW
    )
    assert (fomeria.category_id, fomeria.category_source) == (saude, "manual")
