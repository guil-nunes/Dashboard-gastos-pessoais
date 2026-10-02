"""Valores monetários em centavos (`int`), nunca `float`."""

import re

# Formato brasileiro: "10,06", "1.234,56", "- 12,93", "-1.100,00".
_BRL_AMOUNT = re.compile(r"^([+-])?\s*(\d{1,3}(?:\.\d{3})+|\d+),(\d{2})$")
# Ponto decimal (OFX `TRNAMT`, CSV da conta Nubank): "-4350.29", "759.86", "-11".
_DECIMAL_AMOUNT = re.compile(r"^([+-])?(\d+)(?:\.(\d{1,2}))?$")


def parse_brl_amount(text: str) -> int:
    match = _BRL_AMOUNT.match(text.strip())
    if match is None:
        raise ValueError(f"valor em formato brasileiro inválido: {text!r}")
    sign, integer, cents = match.groups()
    value = int(integer.replace(".", "")) * 100 + int(cents)
    return -value if sign == "-" else value


def parse_decimal_amount(text: str) -> int:
    match = _DECIMAL_AMOUNT.match(text.strip())
    if match is None:
        raise ValueError(f"valor decimal inválido: {text!r}")
    sign, integer, cents = match.groups()
    value = int(integer) * 100 + int((cents or "0").ljust(2, "0"))
    return -value if sign == "-" else value


def to_outflow(cents: int, positive_is_outflow: bool) -> int:
    """Normaliza o sinal para a convenção do sistema: positivo = saída de dinheiro."""
    return cents if positive_is_outflow else -cents
