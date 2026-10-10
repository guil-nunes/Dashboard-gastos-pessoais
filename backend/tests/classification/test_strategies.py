import pytest

from app.classification.base import (
    ClassificationInput,
    ClassifierContext,
    KeywordRuleEntry,
    MemoryEntry,
)
from app.classification.pipeline import UNCLASSIFIED, build_strategies, classify
from app.domain.normalizer import normalize_merchant

ALIMENTACAO, TRANSPORTE, SAUDE = 1, 2, 3
PIX_RECEIVED = "Transferência recebida pelo Pix - FULANO DE TAL - •••.123.456-•• - BCO EXEMPLO"
PIX_SENT = "Transferência enviada pelo Pix - FULANO DE TAL - •••.123.456-•• - BCO EXEMPLO"


def _item(kind="cartao", cents=1000, description="Padaria Exemplo", **extra):
    return ClassificationInput(
        account_kind=kind,
        amount_cents=cents,
        description_raw=description,
        merchant_key=normalize_merchant(description),
        **extra,
    )


def _classify(item, **context):
    return classify(item, build_strategies(ClassifierContext(**context)))


def test_memory_applies_category_with_full_confidence():
    memory = {"PADARIA EXEMPLO": MemoryEntry(ALIMENTACAO, "despesa", None)}

    result = _classify(_item(), memory=memory)

    assert (result.kind, result.category_id, result.source, result.confidence) == (
        "despesa",
        ALIMENTACAO,
        "memoria",
        1.0,
    )


def test_memory_never_applies_investimento():
    memory = {"PADARIA EXEMPLO": MemoryEntry(None, "ignorar", "investimento")}

    assert _classify(_item(), memory=memory) == UNCLASSIFIED


def test_memory_can_remember_ignore_with_reason():
    memory = {"PADARIA EXEMPLO": MemoryEntry(None, "ignorar", "transferencia_interna")}

    result = _classify(_item(), memory=memory)

    assert (result.kind, result.ignore_reason) == ("ignorar", "transferencia_interna")


def test_received_pix_stays_income_even_with_expense_memory():
    memory = {"PIX FULANO DE TAL": MemoryEntry(ALIMENTACAO, "despesa", None)}

    received = _classify(_item("conta", -75986, PIX_RECEIVED), memory=memory)
    sent = _classify(_item("conta", 1100, PIX_SENT), memory=memory)

    assert (received.kind, received.ignore_reason, received.source) == (
        "ignorar",
        "receita",
        "regra",
    )
    assert sent.source == "memoria"


def test_keyword_matches_raw_description_that_the_normalizer_strips():
    rules = (KeywordRuleEntry("ifd*", "contains", ALIMENTACAO, None),)
    item = _item(description="Ifd*Sushi Exemplo")
    assert "IFD" not in item.merchant_key

    result = _classify(item, rules=rules)

    assert (result.category_id, result.source, result.confidence) == (ALIMENTACAO, "regra", 0.9)


def test_keyword_regex_and_priority_order():
    rules = (
        KeywordRuleEntry(r"^uber\b", "regex", TRANSPORTE, None),
        KeywordRuleEntry("uber", "contains", ALIMENTACAO, None),
    )

    assert _classify(_item(description="Uber - NuPay"), rules=rules).category_id == TRANSPORTE


def test_invalid_regex_does_not_break_classification():
    rules = (KeywordRuleEntry("(", "regex", ALIMENTACAO, None),)

    assert _classify(_item(), rules=rules) == UNCLASSIFIED


def test_memory_beats_keyword_rule():
    memory = {"IFOOD": MemoryEntry(SAUDE, "despesa", None)}
    rules = (KeywordRuleEntry("ifood", "contains", ALIMENTACAO, None),)

    result = _classify(_item(description="IFOOD"), memory=memory, rules=rules)

    assert (result.category_id, result.source) == (SAUDE, "memoria")


def test_bank_category_is_low_confidence_suggestion():
    result = _classify(_item(bank_category="SAÚDE"), bank_map={"SAÚDE": SAUDE})

    assert (result.kind, result.category_id, result.confidence) == ("despesa", SAUDE, 0.5)


@pytest.mark.parametrize("bank_category", ["DIVERSOS", "NOVA CATEGORIA", None])
def test_unmapped_bank_category_suggests_nothing(bank_category):
    result = _classify(_item(bank_category=bank_category), bank_map={"SAÚDE": SAUDE})

    assert result == UNCLASSIFIED


def test_keyword_beats_bank_category():
    rules = (KeywordRuleEntry("padaria", "contains", ALIMENTACAO, None),)

    result = _classify(_item(bank_category="SAÚDE"), rules=rules, bank_map={"SAÚDE": SAUDE})

    assert result.category_id == ALIMENTACAO


def test_cofrinhos_is_suggested_but_stays_expense():
    result = _classify(_item("conta", 6000, "APLICACAO COFRINHOS"))

    assert (result.kind, result.ignore_reason) == ("despesa", None)
    assert result.suggested_ignore_reason == "investimento"


def test_pix_to_holder_is_suggested_but_stays_expense():
    result = _classify(_item("conta", 50000, PIX_SENT, holder="Fulano de Tal"))

    assert (result.kind, result.suggested_ignore_reason) == ("despesa", "investimento")


def test_pix_to_someone_else_or_without_holder_is_not_suggested():
    assert (
        _classify(_item("conta", 50000, PIX_SENT, holder="Beltrano")).suggested_ignore_reason
        is None
    )
    assert _classify(_item("conta", 50000, PIX_SENT)).suggested_ignore_reason is None


def test_investment_suggestion_coexists_with_memory_category():
    memory = {"PIX FULANO DE TAL": MemoryEntry(ALIMENTACAO, "despesa", None)}

    result = _classify(_item("conta", 50000, PIX_SENT, holder="Fulano de Tal"), memory=memory)

    assert (result.kind, result.category_id, result.suggested_ignore_reason) == (
        "despesa",
        ALIMENTACAO,
        "investimento",
    )
