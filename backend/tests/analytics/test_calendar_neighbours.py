import pytest

from app.analytics.dashboard import next_month, previous_month


@pytest.mark.parametrize(
    ("month", "previous", "following"),
    [
        ("2026-08", "2026-07", "2026-09"),
        ("2026-01", "2025-12", "2026-02"),
        ("2025-12", "2025-11", "2026-01"),
    ],
)
def test_calendar_neighbours(month, previous, following):
    assert previous_month(month) == previous
    assert next_month(month) == following
