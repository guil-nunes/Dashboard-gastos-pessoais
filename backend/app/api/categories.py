import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.classification import catalog
from app.repo import transactions as repo
from app.repo.db import get_session
from app.repo.models import Category

router = APIRouter(tags=["categories"])

_NAME_TAKEN = "Já existe uma categoria com esse nome"
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _clean_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("nome não pode ser vazio")
    return value


def _clean_color(value: str | None) -> str | None:
    if value is not None and not _COLOR.match(value):
        raise ValueError("cor deve estar no formato #RRGGBB")
    return value


class CategoryDTO(BaseModel):
    id: int
    name: str
    color: str
    is_active: bool
    transactions_count: int = 0


class CategoryDeletedDTO(BaseModel):
    affected_transactions: int


class CategoryCreate(BaseModel):
    name: str
    color: str = "#757575"

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        return _clean_color(value)


class CategoryUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str | None) -> str | None:
        return _clean_name(value)

    @field_validator("color")
    @classmethod
    def valid_color(cls, value: str | None) -> str | None:
        return _clean_color(value)


def _dto(category: Category, count: int = 0) -> CategoryDTO:
    return CategoryDTO(
        id=category.id,
        name=category.name,
        color=category.color,
        is_active=category.is_active,
        transactions_count=count,
    )


@router.get("/categories")
def get_categories(session: Session = Depends(get_session)) -> list[CategoryDTO]:
    counts = repo.category_transaction_counts(session)
    return [_dto(c, counts.get(c.id, 0)) for c in repo.list_categories(session)]


@router.post("/categories", status_code=201)
def post_category(body: CategoryCreate, session: Session = Depends(get_session)) -> CategoryDTO:
    result = catalog.create_category(session, body.name, body.color)
    if result == "name_taken":
        raise HTTPException(status_code=409, detail=_NAME_TAKEN)
    session.commit()
    return _dto(result)


@router.patch("/categories/{category_id}")
def patch_category(
    category_id: int, body: CategoryUpdate, session: Session = Depends(get_session)
) -> CategoryDTO:
    result = catalog.update_category(
        session, category_id, name=body.name, color=body.color, is_active=body.is_active
    )
    if result == "not_found":
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    if result == "name_taken":
        raise HTTPException(status_code=409, detail=_NAME_TAKEN)
    session.commit()
    return _dto(result)


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int, session: Session = Depends(get_session)
) -> CategoryDeletedDTO:
    result = catalog.delete_category(session, category_id)
    if result == "not_found":
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    session.commit()
    return CategoryDeletedDTO(affected_transactions=result)
