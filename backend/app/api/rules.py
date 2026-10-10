import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.classification.service import reclassify_unreviewed
from app.repo import transactions as repo
from app.repo.db import get_session
from app.repo.models import Category, KeywordRule

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


def _check(session: Session, pattern: str, match_type: str, category_id: int | None) -> None:
    if not pattern.strip():
        raise HTTPException(status_code=422, detail="Padrão não pode ser vazio")
    if match_type == "regex":
        try:
            re.compile(pattern)
        except re.error as error:
            raise HTTPException(status_code=422, detail=f"Regex inválida: {error}") from error
    if category_id is not None:
        category = session.get(Category, category_id)
        if category is None:
            raise HTTPException(status_code=422, detail="Categoria não encontrada")
        if not category.is_active:
            raise HTTPException(status_code=422, detail="Categoria inativa")


@router.get("/rules")
def get_rules(session: Session = Depends(get_session)) -> list[RuleDTO]:
    return [_dto(r) for r in repo.list_rules(session)]


@router.post("/rules", status_code=201)
def post_rule(body: RuleCreate, session: Session = Depends(get_session)) -> RuleDTO:
    _check(session, body.pattern, body.match_type, body.category_id)
    rule = KeywordRule(
        pattern=body.pattern.strip(),
        match_type=body.match_type,
        category_id=body.category_id,
        priority=body.priority,
    )
    session.add(rule)
    session.flush()
    reclassify_unreviewed(session)  # não revisadas passam a seguir a regra nova
    session.commit()
    return _dto(rule)


@router.patch("/rules/{rule_id}")
def patch_rule(rule_id: int, body: RuleUpdate, session: Session = Depends(get_session)) -> RuleDTO:
    rule = session.get(KeywordRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    pattern = body.pattern if body.pattern is not None else rule.pattern
    match_type = body.match_type or rule.match_type
    category_id = body.category_id if body.category_id is not None else rule.category_id
    _check(session, pattern, match_type, category_id)
    rule.pattern, rule.match_type, rule.category_id = pattern.strip(), match_type, category_id
    if body.priority is not None:
        rule.priority = body.priority
    session.flush()
    reclassify_unreviewed(session)
    session.commit()
    return _dto(rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, session: Session = Depends(get_session)) -> Response:
    rule = session.get(KeywordRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    session.delete(rule)
    session.flush()
    reclassify_unreviewed(session)
    session.commit()
    return Response(status_code=204)
