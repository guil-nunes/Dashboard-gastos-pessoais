from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.classification.service import reclassify_unreviewed
from app.repo import transactions as repo
from app.repo.db import get_session
from app.repo.models import Category

router = APIRouter(tags=["categories"])


def _clean_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("nome não pode ser vazio")
    return value


class CategoryDTO(BaseModel):
    id: int
    name: str
    color: str
    is_active: bool


class CategoryCreate(BaseModel):
    name: str
    color: str = "#757575"

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        return _clean_name(value)


class CategoryUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str | None) -> str | None:
        return _clean_name(value)


def _dto(category: Category) -> CategoryDTO:
    return CategoryDTO(
        id=category.id, name=category.name, color=category.color, is_active=category.is_active
    )


@router.get("/categories")
def get_categories(session: Session = Depends(get_session)) -> list[CategoryDTO]:
    return [_dto(c) for c in repo.list_categories(session)]


@router.post("/categories", status_code=201)
def post_category(body: CategoryCreate, session: Session = Depends(get_session)) -> CategoryDTO:
    if repo.category_name_taken(session, body.name):
        raise HTTPException(status_code=409, detail="Já existe uma categoria com esse nome")
    category = Category(name=body.name, color=body.color, is_active=True)
    session.add(category)
    session.commit()
    return _dto(category)


@router.patch("/categories/{category_id}")
def patch_category(
    category_id: int, body: CategoryUpdate, session: Session = Depends(get_session)
) -> CategoryDTO:
    category = repo.get_category(session, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    if body.name is not None:
        if repo.category_name_taken(session, body.name, except_id=category.id):
            raise HTTPException(status_code=409, detail="Já existe uma categoria com esse nome")
        category.name = body.name
    if body.color is not None:
        category.color = body.color
    if body.is_active is not None:
        category.is_active = body.is_active
    session.flush()
    reclassify_unreviewed(session)  # inativa/reativada muda o que as estratégias sugerem
    session.commit()
    return _dto(category)
