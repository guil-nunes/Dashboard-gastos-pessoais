import pytest

from app.domain.money import parse_brl_amount, parse_decimal_amount, to_outflow


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("10,06", 1006),  # Nubank cartão
        ("909,46", 90946),
        ("- 12,93", -1293),  # estorno com espaço após o sinal
        ("- 3.317,60", -331760),  # pagamento recebido
        ("-1.100,00", -110000),  # Itaú conta
        ("-0,06", -6),  # crédito pequeno da fatura Itaú
        ("1234,56", 123456),
    ],
)
def test_parse_brl_amount(text, cents):
    assert parse_brl_amount(text) == cents


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("-4350.29", -435029),
        ("759.86", 75986),
        ("-11.00", -1100),
        ("-11", -1100),
        ("0.5", 50),
    ],
)
def test_parse_decimal_amount(text, cents):
    assert parse_decimal_amount(text) == cents


@pytest.mark.parametrize("text", ["", "abc", "1.23,45", "12,3", "12.345", "R$ 10,00"])
def test_parse_brl_amount_rejects_invalid(text):
    with pytest.raises(ValueError):
        parse_brl_amount(text)


@pytest.mark.parametrize("text", ["", "abc", "1,50", "1.234"])
def test_parse_decimal_amount_rejects_invalid(text):
    with pytest.raises(ValueError):
        parse_decimal_amount(text)


def test_results_are_int():
    assert type(parse_brl_amount("10,06")) is int
    assert type(parse_decimal_amount("-4350.29")) is int


def test_to_outflow():
    assert to_outflow(1006, positive_is_outflow=True) == 1006  # Nubank cartão
    assert to_outflow(-435029, positive_is_outflow=False) == 435029  # saída na conta
    assert to_outflow(75986, positive_is_outflow=False) == -75986  # crédito na conta
