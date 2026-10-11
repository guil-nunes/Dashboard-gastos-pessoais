"""Parcelas projetadas (spec R10): descrição, chave e plano, sem banco."""

from datetime import date

import pytest

from app.domain.installments import projected_description
from app.domain.keys import dedup_key_projected
from app.domain.months import YearMonth
from app.domain.projection import LastReal, ProjectedSpec, add_months, plan_projection


@pytest.mark.parametrize(
    ("description", "number", "expected"),
    [
        ("Latam Air*0000 - Parcela 3/4", 4, "Latam Air*0000 - Parcela 4/4"),
        ("Pag*Steam - Parcela 1/3", 2, "Pag*Steam - Parcela 2/3"),
        ("Loja - Parcela 9/12", 10, "Loja - Parcela 10/12"),
        ("MERCADOLIVRE*5525309/12", 10, "MERCADOLIVRE*5525310/12"),
        ("SHOPEE *OLILOJA 03/05", 4, "SHOPEE *OLILOJA 04/05"),
        ("ANUIDADE DIFERENCI02/12", 3, "ANUIDADE DIFERENCI03/12"),
        ("Compra sem parcela", 2, "Compra sem parcela"),
    ],
)
def test_projected_description_swaps_the_installment_number(description, number, expected):
    assert projected_description(description, number) == expected


def test_projected_dedup_key_is_distinct_from_real_keys():
    assert dedup_key_projected("grp:abc", 3) == "proj:grp:abc:3"


def _last(number=9, total=12, first="2025-05", on=date(2025, 5, 15), text="LOJA*5525309/12"):
    return LastReal(text, number, total, YearMonth.parse(first), on)


def test_plan_continues_from_the_last_real_installment():
    plan = plan_projection(_last())

    assert [s.number for s in plan] == [10, 11, 12]
    assert [str(s.competence) for s in plan] == ["2026-02", "2026-03", "2026-04"]
    assert plan[0] == ProjectedSpec(10, YearMonth(2026, 2), date(2025, 6, 15), "LOJA*5525310/12")


def test_plan_is_empty_when_the_last_installment_is_real():
    assert plan_projection(_last(number=12)) == []


def test_competence_follows_first_month_not_the_anticipated_real_one():
    """Antecipação (Q14) desloca a competência das reais; a projetada segue o mês da parcela 1."""
    plan = plan_projection(_last(number=2, total=4, first="2025-11", text="X 02/04"))

    assert [str(s.competence) for s in plan] == ["2026-01", "2026-02"]


def test_plan_crosses_year_boundary():
    plan = plan_projection(_last(number=1, total=3, first="2026-11", on=date(2026, 11, 20)))

    assert [str(s.competence) for s in plan] == ["2026-12", "2027-01"]


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2026, 12, 31), 2, date(2027, 2, 28)),
        (date(2026, 8, 15), 0, date(2026, 8, 15)),
    ],
)
def test_add_months_clamps_to_the_last_day(day, months, expected):
    assert add_months(day, months) == expected
