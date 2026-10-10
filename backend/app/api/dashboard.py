from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analytics import dashboard as analytics
from app.repo.db import get_session

router = APIRouter(tags=["dashboard"])

Bank = Literal["nubank", "itau"]
AccountKind = Literal["conta", "cartao"]


class CategoryTotalDTO(BaseModel):
    category_id: int | None
    name: str
    color: str | None
    total_cents: int
    count: int
    pct: float | None


class SummaryDTO(BaseModel):
    month: str
    total_cents: int
    previous_month: str
    previous_total_cents: int
    delta_cents: int
    delta_pct: float | None
    categories: list[CategoryTotalDTO]


class HistoryCategoryDTO(BaseModel):
    id: int
    name: str
    color: str


class HistoryValueDTO(BaseModel):
    category_id: int | None
    total_cents: int


class HistoryMonthDTO(BaseModel):
    month: str
    total_cents: int
    by_category: list[HistoryValueDTO]


class HistoryDTO(BaseModel):
    months: list[HistoryMonthDTO]
    categories: list[HistoryCategoryDTO]


@router.get("/dashboard/summary")
def get_summary(
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    bank: Bank | None = None,
    account_kind: AccountKind | None = None,
    session: Session = Depends(get_session),
) -> SummaryDTO:
    summary = analytics.month_summary(session, month, bank, account_kind)
    return SummaryDTO(
        month=summary.month,
        total_cents=summary.total_cents,
        previous_month=summary.previous_month,
        previous_total_cents=summary.previous_total_cents,
        delta_cents=summary.delta_cents,
        delta_pct=summary.delta_pct,
        categories=[CategoryTotalDTO(**vars(c)) for c in summary.categories],
    )


@router.get("/dashboard/history")
def get_history(
    bank: Bank | None = None,
    account_kind: AccountKind | None = None,
    session: Session = Depends(get_session),
) -> HistoryDTO:
    result = analytics.history(session, bank, account_kind)
    return HistoryDTO(
        months=[
            HistoryMonthDTO(
                month=m.month,
                total_cents=m.total_cents,
                by_category=[
                    HistoryValueDTO(category_id=cid, total_cents=cents)
                    for cid, cents in sorted(
                        m.by_category.items(), key=lambda item: (item[0] is None, item[0] or 0)
                    )
                ],
            )
            for m in result.months
        ],
        categories=[
            HistoryCategoryDTO(id=c.id, name=c.name, color=c.color) for c in result.categories
        ],
    )
