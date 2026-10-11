from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analytics import recurrence as analytics
from app.repo.db import get_session
from app.repo.models import RecurrenceOverride

router = APIRouter(tags=["recurrences"])


class RecurrenceDTO(BaseModel):
    merchant_key: str
    description: str
    average_cents: int
    last_cents: int
    last_on: date
    months_count: int
    dismissed: bool


class RecurrenceUpdateDTO(BaseModel):
    is_recurring: bool


@router.get("/recurrences")
def list_recurrences(session: Session = Depends(get_session)) -> list[RecurrenceDTO]:
    items = analytics.detect_recurrences(session, analytics.default_params())
    return [
        RecurrenceDTO(**{k: v for k, v in vars(i).items() if k != "last_competence"}) for i in items
    ]


@router.patch("/recurrences/{merchant_key:path}")
def update_recurrence(
    merchant_key: str, body: RecurrenceUpdateDTO, session: Session = Depends(get_session)
) -> RecurrenceUpdateDTO:
    if not analytics.merchant_exists(session, merchant_key):
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado")
    override = session.get(RecurrenceOverride, merchant_key)
    if body.is_recurring:  # só "não é recorrente" tem efeito; voltar a recorrente remove o override
        if override is not None:
            session.delete(override)
    elif override is None:
        session.add(RecurrenceOverride(merchant_key=merchant_key, is_recurring=False))
    else:
        override.is_recurring = False
    session.commit()
    return body
