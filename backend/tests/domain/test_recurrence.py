"""Detector de recorrência (R9): intervalos, tolerância sobre a mediana, sequência recente e IOF."""

from datetime import date, timedelta

from app.domain.recurrence import Occurrence, RecurrenceParams, detect, merge_iof

PARAMS = RecurrenceParams()
START = date(2026, 1, 10)


def _series(cents: list[int], gaps: list[int]) -> list[Occurrence]:
    day, out = START, [Occurrence(START, cents[0])]
    for value, gap in zip(cents[1:], gaps, strict=True):
        day += timedelta(days=gap)
        out.append(Occurrence(day, value))
    return out


def test_three_monthly_occurrences_are_recurring():
    assert detect(_series([5000, 5000, 5000], [30, 31]), PARAMS) is not None


def test_two_occurrences_are_not_enough():
    assert detect(_series([5000, 5000], [30]), PARAMS) is None


def test_gap_limits_are_inclusive():
    assert detect(_series([5000] * 3, [25, 35]), PARAMS) is not None
    assert detect(_series([5000] * 3, [24, 30]), PARAMS) is None
    assert detect(_series([5000] * 3, [30, 36]), PARAMS) is None


def test_value_tolerance_is_ten_percent_of_the_median():
    assert detect(_series([5000, 5500, 4500], [30, 30]), PARAMS) is not None  # exatamente ±10%
    assert detect(_series([5000, 5501, 5000], [30, 30]), PARAMS) is None


def test_old_break_does_not_invalidate_the_current_series():
    old = _series([1000, 1000, 1000, 5000, 5000, 5000], [30, 30, 90, 30, 30])

    series = detect(old, PARAMS)

    assert [o.cents for o in series] == [5000, 5000, 5000]


def test_outlier_at_the_start_is_dropped_when_the_rest_still_qualifies():
    series = detect(_series([9000, 5000, 5000, 5000], [30, 30, 30]), PARAMS)

    assert [o.cents for o in series] == [5000, 5000, 5000]


def test_params_are_configurable():
    loose = RecurrenceParams(min_occurrences=2, min_days=1, max_days=10, tolerance_pct=50)

    assert detect(_series([5000, 6000], [7]), loose) is not None


def test_iof_is_added_to_the_nearest_earlier_purchase():
    purchases = [Occurrence(date(2026, 7, 15), 10000), Occurrence(date(2026, 8, 18), 10000)]
    iofs = [Occurrence(date(2026, 7, 15), 400), Occurrence(date(2026, 8, 19), 400)]

    assert [o.cents for o in merge_iof(purchases, iofs)] == [10400, 10400]


def test_iof_without_a_nearby_purchase_is_ignored():
    purchases = [Occurrence(date(2026, 7, 15), 10000)]

    assert merge_iof(purchases, [Occurrence(date(2026, 9, 1), 400)])[0].cents == 10000
