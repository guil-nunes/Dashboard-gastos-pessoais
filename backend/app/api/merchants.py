from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.repo import transactions as repo
from app.repo.db import get_session

router = APIRouter(tags=["merchants"])


class PendingMerchantDTO(BaseModel):
    merchant_key: str
    count: int
    total_cents: int
    sample_description: str
    category_id: int | None
    category_source: str | None
    min_confidence: float | None
    suggested_ignore_reason: str | None
    latest_on: date


@router.get("/merchants")
def get_merchants(
    pending: bool = True, session: Session = Depends(get_session)
) -> list[PendingMerchantDTO]:
    """Pendentes agrupados por `merchant_key` (R7). Só a visão de pendentes existe por ora."""
    if not pending:
        return []
    return [PendingMerchantDTO(**vars(m)) for m in repo.pending_merchants(session)]
