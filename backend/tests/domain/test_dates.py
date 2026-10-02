from datetime import date

import pytest

from app.domain.dates import infer_year, parse_br_date, parse_iso_date, parse_ofx_date


def test_parse_iso_date():
    assert parse_iso_date("2026-08-31") == date(2026, 8, 31)


def test_parse_br_date():
    assert parse_br_date("02/09/2026") == date(2026, 9, 2)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("20260901000000[-3:BRT]", date(2026, 9, 1)),
        # 22h do dia 31 em BRT seria dia 1º em UTC: o dia local do arquivo é mantido.
        ("20260831220000[-3:BRT]", date(2026, 8, 31)),
        ("20260924", date(2026, 9, 24)),
    ],
)
def test_parse_ofx_date_keeps_local_day(text, expected):
    assert parse_ofx_date(text) == expected


@pytest.mark.parametrize("text", ["", "2026-09-01", "31/08/2026"])
def test_parse_ofx_date_rejects_invalid(text):
    with pytest.raises(ValueError):
        parse_ofx_date(text)


@pytest.mark.parametrize(
    ("day", "month", "closing", "expected"),
    [
        # Fatura Itaú com fechamento em 06/06/2025.
        (15, 9, date(2025, 6, 6), date(2024, 9, 15)),  # parcela 09/12 comprada no ano anterior
        (14, 5, date(2025, 6, 6), date(2025, 5, 14)),
        (6, 6, date(2025, 6, 6), date(2025, 6, 6)),  # no próprio dia do fechamento
        (29, 2, date(2025, 6, 6), date(2024, 2, 29)),  # último 29/02 antes do fechamento
    ],
)
def test_infer_year(day, month, closing, expected):
    assert infer_year(day, month, closing) == expected


def test_infer_year_rejects_impossible_date():
    with pytest.raises(ValueError):
        infer_year(31, 2, date(2025, 6, 6))
