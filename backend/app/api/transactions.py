from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.classification.service import (
    apply_correction,
    bulk_apply,
    bulk_confirm,
    confirm_transaction,
    validate_target,
)
from app.repo import transactions as repo
from app.repo.db import get_session
from app.repo.models import Account, Transaction

router = APIRouter(tags=["transactions"])

Kind = Literal["despesa", "ignorar"]


class TransactionDTO(BaseModel):
    id: int
    occurred_on: date
    competence_month: str
    amount_cents: int
    description_raw: str
    merchant_key: str
    account_id: int
    account_name: str
    kind: Kind
    ignore_reason: str | None
    suggested_ignore_reason: str | None
    category_id: int | None
    category_source: str
    category_confidence: float | None
    reviewed_at: datetime | None
    status: str
    installment_number: int | None
    installment_total: int | None


class TransactionPageDTO(BaseModel):
    items: list[TransactionDTO]
    total: int


class TransactionPatch(BaseModel):
    """`action = 'confirm'` confirma sem alterar; senão `kind` é obrigatório (correção)."""

    action: Literal["confirm", "apply"] = "apply"
    kind: Kind | None = None
    ignore_reason: str | None = None
    category_id: int | None = None


class BulkRequest(BaseModel):
    merchant_key: str
    action: Literal["confirm", "apply"]
    kind: Kind | None = None
    ignore_reason: str | None = None
    category_id: int | None = None
    transaction_ids: list[int] | None = None


class BulkResultDTO(BaseModel):
    affected: int


def _dto(transaction: Transaction, account: Account) -> TransactionDTO:
    return TransactionDTO(
        id=transaction.id,
        occurred_on=transaction.occurred_on,
        competence_month=transaction.competence_month,
        amount_cents=transaction.amount_cents,
        description_raw=transaction.description_raw,
        merchant_key=transaction.merchant_key,
        account_id=account.id,
        account_name=account.name,
        kind=transaction.kind,
        ignore_reason=transaction.ignore_reason,
        suggested_ignore_reason=transaction.suggested_ignore_reason,
        category_id=transaction.category_id,
        category_source=transaction.category_source,
        category_confidence=transaction.category_confidence,
        reviewed_at=transaction.reviewed_at,
        status=transaction.status,
        installment_number=transaction.installment_number,
        installment_total=transaction.installment_total,
    )


def _validate(session: Session, body: TransactionPatch | BulkRequest) -> str:
    if body.kind is None:
        raise HTTPException(status_code=422, detail="Informe o tipo (despesa ou ignorar)")
    try:
        validate_target(session, body.kind, body.ignore_reason, body.category_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return body.kind


@router.get("/transactions")
def get_transactions(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    account_id: int | None = None,
    category_id: int | None = None,
    source: str | None = None,
    merchant_key: str | None = None,
    kind: Kind | None = None,
    status: Literal["real", "projetada"] | None = None,
    bank: Literal["nubank", "itau"] | None = None,
    account_kind: Literal["conta", "cartao"] | None = None,
    without_category: bool = False,
    pending: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> TransactionPageDTO:
    rows, total = repo.list_transactions(
        session,
        month=month,
        account_id=account_id,
        category_id=category_id,
        source=source,
        merchant_key=merchant_key,
        kind=kind,
        status=status,
        bank=bank,
        account_kind=account_kind,
        without_category=without_category,
        pending=pending,
        limit=limit,
        offset=offset,
    )
    return TransactionPageDTO(items=[_dto(t, a) for t, a in rows], total=total)


@router.patch("/transactions/{transaction_id}")
def patch_transaction(
    transaction_id: int, body: TransactionPatch, session: Session = Depends(get_session)
) -> TransactionDTO:
    transaction = session.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    if transaction.status != "real":
        raise HTTPException(status_code=409, detail="Transação projetada não pode ser revisada")

    now = datetime.now()
    if body.action == "confirm":
        confirm_transaction(session, transaction_id, now)
    else:
        kind = _validate(session, body)
        apply_correction(
            session,
            transaction_id,
            kind=kind,
            ignore_reason=body.ignore_reason,
            category_id=body.category_id,
            now=now,
        )
    session.commit()
    session.refresh(transaction)
    account = session.get(Account, transaction.account_id)
    return _dto(transaction, account)


@router.post("/transactions/bulk-categorize")
def bulk_categorize(body: BulkRequest, session: Session = Depends(get_session)) -> BulkResultDTO:
    now = datetime.now()
    if body.action == "confirm":
        affected = bulk_confirm(session, body.merchant_key, now=now, ids=body.transaction_ids)
    else:
        kind = _validate(session, body)
        affected = bulk_apply(
            session,
            body.merchant_key,
            kind=kind,
            ignore_reason=body.ignore_reason,
            category_id=body.category_id,
            now=now,
            ids=body.transaction_ids,
        )
    session.commit()
    return BulkResultDTO(affected=affected)
