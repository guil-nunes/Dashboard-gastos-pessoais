import pytest

from app.domain.normalizer import NORMALIZER_VERSION, normalize_merchant

# Casos reais das amostras (spec R5 e Anexo A), com nomes de pessoas anonimizados.
CASES = [
    # Nubank cartão
    ("Ifd*Sushi Mais Japones", "SUSHI MAIS JAPONES"),
    ("Latam Air*0000 - Parcela 4/4", "LATAM AIR"),
    ("Dm*Helphbomaxcom", "HELPHBOMAXCOM"),
    ("Mp *Espain", "ESPAIN"),
    ("Pag*Steam - Parcela 2/3", "STEAM"),
    ("App *Piuka - Parcela 3/3", "PIUKA"),
    ("Anthropic* Claude Sub", "ANTHROPIC CLAUDE SUB"),
    ('IOF de "Anthropic* Claude Sub"', "ANTHROPIC CLAUDE SUB"),
    ("Uber - NuPay", "UBER NUPAY"),
    # Nubank conta
    ("Compra no débito - POSTO RUI BARBOSA", "POSTO RUI BARBOSA"),
    (
        "Transferência enviada pelo Pix - FULANO DE TAL - •••.665.513-•• - NU PAGAMENTOS - IP "
        "(0260) Agência: 1 Conta: 99361870-2",
        "PIX FULANO DE TAL",
    ),
    (
        "Transferência recebida pelo Pix - FULANO DE TAL - •••.665.513-•• - BCO DO BRASIL S.A. "
        "(0001) Agência: 3655 Conta: 88054-0",
        "PIX FULANO DE TAL",
    ),
    (
        "Transferência Recebida - 12.345.678 FULANO DE TAL - 12.345.678/0001-00 - NU PAGAMENTOS",
        "PIX FULANO DE TAL",
    ),
    # Itaú conta
    ("ON Uber UBER 19/09", "UBER"),
    ("PAY Uber 07/08", "UBER"),
    ("PIX AUT HOTMART 24/09", "HOTMART"),
    ("PIX TRANSF FULANO25/09", "PIX FULANO"),
    ("PIX TRANSF Débora 29/09", "PIX DEBORA"),
    ("APLICACAO COFRINHOS", "APLICACAO COFRINHOS"),
    # Itaú cartão
    ("PG *ENJOEI.COM.BR 02/04", "ENJOEI COM BR"),
    ("MERCADOLIVRE*5525309/12", "MERCADOLIVRE"),
    ("SHOPEE *OLILOJA 03/05", "SHOPEE OLILOJA"),
    ("ZP *OLX FULANO 01/07", "OLX FULANO"),
    ("NETFLIX.COM", "NETFLIX COM"),
]


@pytest.mark.parametrize(("raw", "expected"), CASES)
def test_normalize_merchant(raw, expected):
    assert normalize_merchant(raw) == expected


def test_iof_shares_merchant_key_with_purchase():
    assert normalize_merchant('IOF de "Anthropic* Claude Sub"') == normalize_merchant(
        "Anthropic* Claude Sub"
    )


def test_is_deterministic():
    raw = "Ifd*Sushi Mais Japones"
    assert normalize_merchant(raw) == normalize_merchant(raw)


def test_only_digits_falls_back_to_digits():
    assert normalize_merchant("12345") == "12345"


def test_version_is_positive_int():
    assert isinstance(NORMALIZER_VERSION, int) and NORMALIZER_VERSION >= 1
