from datetime import date

import pytest

from app.domain.months import YearMonth


def test_of_and_str():
    assert str(YearMonth.of(date(2026, 8, 31))) == "2026-08"


def test_parse_round_trip():
    assert YearMonth.parse("2025-05") == YearMonth(2025, 5)


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (YearMonth(2024, 9), 8, YearMonth(2025, 5)),
        (YearMonth(2026, 8), -3, YearMonth(2026, 5)),
        (YearMonth(2026, 1), -1, YearMonth(2025, 12)),
        (YearMonth(2026, 12), 1, YearMonth(2027, 1)),
    ],
)
def test_plus(start, months, expected):
    assert start.plus(months) == expected


def test_invalid_month():
    with pytest.raises(ValueError):
        YearMonth(2026, 13)
