import pytest

from app.domain.installments import (
    InstallmentInfo,
    parse_itau_installment,
    parse_nubank_installment,
)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Latam Air*0000 - Parcela 4/4", InstallmentInfo("Latam Air*0000", 4, 4)),
        ("Pag*Steam - Parcela 1/3", InstallmentInfo("Pag*Steam", 1, 3)),
        ("Pandora do Brasil Come - Parcela 6/10", InstallmentInfo("Pandora do Brasil Come", 6, 10)),
    ],
)
def test_parse_nubank_installment(title, expected):
    assert parse_nubank_installment(title) == expected


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("MERCADOLIVRE*5525309/12", InstallmentInfo("MERCADOLIVRE*55253", 9, 12)),
        ("SHOPEE *OLILOJA 03/05", InstallmentInfo("SHOPEE *OLILOJA", 3, 5)),
        ("PG *ENJOEI.COM.BR 02/04", InstallmentInfo("PG *ENJOEI.COM.BR", 2, 4)),
        ("ANUIDADE DIFERENCI02/12", InstallmentInfo("ANUIDADE DIFERENCI", 2, 12)),
    ],
)
def test_parse_itau_installment(description, expected):
    assert parse_itau_installment(description) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Uber - NuPay",
        'IOF de "Anthropic* Claude Sub"',
        "Pag*Steam - Parcela 5/3",  # n > N
        "Loja - Parcela 1/1",  # N < 2 não é parcelamento
    ],
)
def test_parse_nubank_installment_none(text):
    assert parse_nubank_installment(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "PG *ENJOEI.COM.BR ATIV",
        "NETFLIX.COM",
        "SHOPEE *LOJA 05/03",  # n > N
        "SHOPEE *LOJA 00/03",  # n = 0
    ],
)
def test_parse_itau_installment_none(text):
    assert parse_itau_installment(text) is None
