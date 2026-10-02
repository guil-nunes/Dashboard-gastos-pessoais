"""Datas como vieram no arquivo: sempre data local, sem conversão de fuso."""

import re
from datetime import date, datetime

_OFX_DATE = re.compile(r"^(\d{8})")


def parse_iso_date(text: str) -> date:
    return datetime.strptime(text.strip(), "%Y-%m-%d").date()


def parse_br_date(text: str) -> date:
    return datetime.strptime(text.strip(), "%d/%m/%Y").date()


def parse_ofx_date(text: str) -> date:
    """`20260901000000[-3:BRT]` → 2026-09-01. Usa só a parte da data; o fuso é ignorado."""
    match = _OFX_DATE.match(text.strip())
    if match is None:
        raise ValueError(f"data OFX inválida: {text!r}")
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def infer_year(day: int, month: int, closing: date) -> date:
    """Data mais recente com esse dia/mês que não passa do fechamento da fatura (linhas `DD/MM`)."""
    # 8 anos para trás cobrem um 29/02 mesmo partindo de um ano logo após um bissexto.
    for year in range(closing.year, closing.year - 8, -1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate <= closing:
            return candidate
    raise ValueError(f"dia/mês inválido: {day:02d}/{month:02d}")
