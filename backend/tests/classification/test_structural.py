import pytest

from app.classification.base import Classification, ClassificationInput
from app.classification.pipeline import UNCLASSIFIED, classify
from app.classification.structural import StructuralRules
from app.domain.normalizer import normalize_merchant

PIX_RECEIVED = "Transferência recebida pelo Pix - FULANO DE TAL - •••.123.456-•• - BCO EXEMPLO"
PIX_SENT = "Transferência enviada pelo Pix - FULANO DE TAL - •••.123.456-•• - BCO EXEMPLO"


def _item(kind: str, cents: int, description: str) -> ClassificationInput:
    return ClassificationInput(
        account_kind=kind,
        amount_cents=cents,
        description_raw=description,
        merchant_key=normalize_merchant(description),
    )


def _ignored(reason: str) -> Classification:
    return Classification(kind="ignorar", ignore_reason=reason, source="regra", confidence=1.0)


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        (_item("conta", -75986, PIX_RECEIVED), _ignored("receita")),
        (_item("conta", -2500, "Crédito em conta"), _ignored("receita")),
        (_item("conta", 331760, "Pagamento de fatura"), _ignored("pagamento_fatura")),
        (_item("cartao", -331760, "Pagamento recebido"), _ignored("pagamento_fatura")),
    ],
)
def test_structural_rules(item, expected):
    assert classify(item) == expected


@pytest.mark.parametrize(
    "item",
    [
        _item("conta", 1100, PIX_SENT),  # Pix para terceiros: despesa sem categoria (R4)
        _item("conta", 1007, "Compra no débito - POSTO EXEMPLO"),
        _item("cartao", -1293, "Uber - NuPay"),  # estorno: despesa negativa (Q9)
        _item("cartao", 400, 'IOF de "Anthropic* Claude Sub"'),
    ],
)
def test_other_transactions_fall_through_as_unclassified_expense(item):
    assert StructuralRules().classify(item) is None
    assert classify(item) == UNCLASSIFIED == Classification(kind="despesa", source="nenhuma")


class _RememberedExpense:
    """Faz o papel da memória (estratégia 1): lembra 'despesa/Alimentação' para PIX FULANO."""

    def classify(self, item):
        if item.merchant_key == "PIX FULANO DE TAL":
            return Classification(kind="despesa", category_id=2, source="memoria", confidence=1.0)
        return None


def test_received_pix_stays_income_even_with_expense_memory():
    strategies = [StructuralRules(), _RememberedExpense()]
    received, sent = _item("conta", -75986, PIX_RECEIVED), _item("conta", 1100, PIX_SENT)
    assert received.merchant_key == sent.merchant_key

    assert classify(received, strategies) == _ignored("receita")
    assert classify(sent, strategies).source == "memoria"
