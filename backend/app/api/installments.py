from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analytics import installments as analytics
from app.repo.db import get_session

router = APIRouter(tags=["installments"])


class UpcomingItemDTO(BaseModel):
    group_key: str
    description: str
    number: int
    total: int
    amount_cents: int
    category_id: int | None
    account_name: str


class UpcomingMonthDTO(BaseModel):
    month: str
    total_cents: int
    items: list[UpcomingItemDTO]


class FlaggedGroupDTO(BaseModel):
    group_key: str
    description: str
    account_name: str
    next_number: int
    total: int
    expected_month: str
    covered_through: str
    remaining: int
    amount_cents: int


class UpcomingDTO(BaseModel):
    months: list[UpcomingMonthDTO]
    flagged: list[FlaggedGroupDTO]


@router.get("/installments/upcoming")
def get_upcoming(session: Session = Depends(get_session)) -> UpcomingDTO:
    result = analytics.upcoming(session)
    return UpcomingDTO(
        months=[
            UpcomingMonthDTO(
                month=m.month,
                total_cents=m.total_cents,
                items=[UpcomingItemDTO(**vars(i)) for i in m.items],
            )
            for m in result.months
        ],
        flagged=[FlaggedGroupDTO(**vars(g)) for g in result.flagged],
    )
