"""Categorias e regras de palavra-chave (spec §7.4): validação, gravação e reclassificação.

Convenção de retorno: `"not_found"` e `"name_taken"` viram 404 e 409 na rota; entrada inválida
levanta `ValueError` com a mensagem para o usuário (422).
"""

import re
from typing import Literal

from sqlalchemy.orm import Session

from app.classification.service import reclassify_unreviewed
from app.repo import transactions as repo
from app.repo.models import Category, KeywordRule

NotFound = Literal["not_found"]
NameTaken = Literal["name_taken"]


def create_category(session: Session, name: str, color: str) -> Category | NameTaken:
    if repo.category_name_taken(session, name):
        return "name_taken"
    category = Category(name=name, color=color, is_active=True)
    session.add(category)
    session.flush()
    return category


def update_category(
    session: Session,
    category_id: int,
    *,
    name: str | None,
    color: str | None,
    is_active: bool | None,
) -> Category | NotFound | NameTaken:
    category = repo.get_category(session, category_id)
    if category is None:
        return "not_found"
    if name is not None:
        if repo.category_name_taken(session, name, except_id=category.id):
            return "name_taken"
        category.name = name
    if color is not None:
        category.color = color
    if is_active is not None:
        category.is_active = is_active
    session.flush()
    reclassify_unreviewed(session)  # inativa/reativada muda o que as estratégias sugerem
    return category


def create_rule(
    session: Session, *, pattern: str, match_type: str, category_id: int, priority: int
) -> KeywordRule:
    _check_rule(session, pattern, match_type, category_id)
    rule = KeywordRule(
        pattern=pattern.strip(), match_type=match_type, category_id=category_id, priority=priority
    )
    session.add(rule)
    session.flush()
    reclassify_unreviewed(session)  # não revisadas passam a seguir a regra nova
    return rule


def update_rule(
    session: Session,
    rule_id: int,
    *,
    pattern: str | None,
    match_type: str | None,
    category_id: int | None,
    priority: int | None,
) -> KeywordRule | NotFound:
    rule = session.get(KeywordRule, rule_id)
    if rule is None:
        return "not_found"
    pattern = pattern if pattern is not None else rule.pattern
    match_type = match_type or rule.match_type
    category_id = category_id if category_id is not None else rule.category_id
    _check_rule(session, pattern, match_type, category_id)
    rule.pattern, rule.match_type, rule.category_id = pattern.strip(), match_type, category_id
    if priority is not None:
        rule.priority = priority
    session.flush()
    reclassify_unreviewed(session)
    return rule


def delete_rule(session: Session, rule_id: int) -> bool:
    rule = session.get(KeywordRule, rule_id)
    if rule is None:
        return False
    session.delete(rule)
    session.flush()
    reclassify_unreviewed(session)
    return True


def _check_rule(session: Session, pattern: str, match_type: str, category_id: int | None) -> None:
    if not pattern.strip():
        raise ValueError("Padrão não pode ser vazio")
    if match_type == "regex":
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError(f"Regex inválida: {error}") from error
    if category_id is not None:
        category = session.get(Category, category_id)
        if category is None:
            raise ValueError("Categoria não encontrada")
        if not category.is_active:
            raise ValueError("Categoria inativa")
