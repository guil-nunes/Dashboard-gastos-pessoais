from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.classification import catalog
from app.repo import transactions as repo
from app.repo.db import get_session
from app.repo.models import KeywordRule

router = APIRouter(tags=["rules"])

MatchType = Literal["contains", "regex"]


class RuleDTO(BaseModel):
    id: int
    pattern: str
    match_type: MatchType
    category_id: int | None
    priority: int


class RuleCreate(BaseModel):
    pattern: str
    match_type: MatchType = "contains"
    category_id: int
    priority: int = 100


class RuleUpdate(BaseModel):
    pattern: str | None = None
    match_type: MatchType | None = None
    category_id: int | None = None
    priority: int | None = None


def _dto(rule: KeywordRule) -> RuleDTO:
    return RuleDTO(
        id=rule.id,
        pattern=rule.pattern,
        match_type=rule.match_type,
        category_id=rule.category_id,
        priority=rule.priority,
    )


@router.get("/rules")
def get_rules(session: Session = Depends(get_session)) -> list[RuleDTO]:
    return [_dto(r) for r in repo.list_rules(session)]


@router.post("/rules", status_code=201)
def post_rule(body: RuleCreate, session: Session = Depends(get_session)) -> RuleDTO:
    try:
        rule = catalog.create_rule(
            session,
            pattern=body.pattern,
            match_type=body.match_type,
            category_id=body.category_id,
            priority=body.priority,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    session.commit()
    return _dto(rule)


@router.patch("/rules/{rule_id}")
def patch_rule(rule_id: int, body: RuleUpdate, session: Session = Depends(get_session)) -> RuleDTO:
    try:
        rule = catalog.update_rule(
            session,
            rule_id,
            pattern=body.pattern,
            match_type=body.match_type,
            category_id=body.category_id,
            priority=body.priority,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if rule == "not_found":
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    session.commit()
    return _dto(rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, session: Session = Depends(get_session)) -> Response:
    if not catalog.delete_rule(session, rule_id):
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    session.commit()
    return Response(status_code=204)
