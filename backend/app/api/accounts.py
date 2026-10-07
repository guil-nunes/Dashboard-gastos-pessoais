from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.repo import imports as repo
from app.repo.db import get_session

router = APIRouter(tags=["accounts"])


class HolderUpdate(BaseModel):
    holder: str

    @field_validator("holder")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("titular não pode ser vazio")
        return value


class AccountDTO(BaseModel):
    id: int
    name: str
    holder: str | None


@router.patch("/accounts/{account_id}")
def patch_account(
    account_id: int, body: HolderUpdate, session: Session = Depends(get_session)
) -> AccountDTO:
    account = repo.set_holder(session, account_id, body.holder)
    if account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    session.commit()
    return AccountDTO(id=account.id, name=account.name, holder=account.holder)
