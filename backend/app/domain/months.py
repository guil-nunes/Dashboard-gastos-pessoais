from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, order=True)
class YearMonth:
    """Mês de competência; `str()` produz o formato da coluna `competence_month` ('YYYY-MM')."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"mês inválido: {self.month}")

    @classmethod
    def of(cls, day: date) -> YearMonth:
        return cls(day.year, day.month)

    @classmethod
    def parse(cls, text: str) -> YearMonth:
        year, month = text.split("-")
        return cls(int(year), int(month))

    def plus(self, months: int) -> YearMonth:
        index = self.year * 12 + (self.month - 1) + months
        return YearMonth(index // 12, index % 12 + 1)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"
