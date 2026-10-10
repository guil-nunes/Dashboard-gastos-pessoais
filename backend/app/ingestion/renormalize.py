"""`renormalize` (spec R5): recalcula `merchant_key` quando o normalizador muda de versão.

Migra as chaves de `merchant_memory`, `llm_cache` e `recurrence_override`; quando chaves antigas
colapsam na mesma, prevalece a memória atualizada mais recentemente. Depois reclassifica as
transações não revisadas, que são dado derivado.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classification.service import reclassify_unreviewed
from app.domain.normalizer import NORMALIZER_VERSION, normalize_merchant
from app.repo.models import LlmCache, MerchantMemory, RecurrenceOverride, Transaction


@dataclass(frozen=True)
class RenormalizeResult:
    transactions: int  # recalculadas (versão antiga)
    keys_changed: int  # chaves antigas que viraram outra
    reclassified: int  # não revisadas cuja classificação mudou


def renormalize(session: Session) -> RenormalizeResult:
    """Uma transação SQL: quem chama faz commit (ou rollback em erro)."""
    outdated = session.scalars(
        select(Transaction).where(Transaction.normalizer_version < NORMALIZER_VERSION)
    ).all()

    old_to_new: dict[str, set[str]] = defaultdict(set)
    for transaction in outdated:
        old_key = transaction.merchant_key
        transaction.merchant_key = normalize_merchant(transaction.description_raw)
        transaction.normalizer_version = NORMALIZER_VERSION
        old_to_new[old_key].add(transaction.merchant_key)
    session.flush()

    changed = {old: news for old, news in old_to_new.items() if news != {old}}
    _migrate_keys(session, MerchantMemory, changed, lambda row: row.updated_at)
    _migrate_keys(session, LlmCache, changed, lambda row: row.created_at)
    _migrate_keys(session, RecurrenceOverride, changed, lambda row: None)
    session.flush()

    reclassified = reclassify_unreviewed(session) if outdated else 0
    return RenormalizeResult(len(outdated), len(changed), reclassified)


def _migrate_keys(
    session: Session,
    model: type,
    changed: dict[str, set[str]],
    stamp: Callable[[Any], Any],
) -> None:
    """Move linhas de chave antiga para as novas; no conflito, vence o carimbo mais recente."""
    rows = {row.merchant_key: row for row in session.scalars(select(model))}
    columns = [column.name for column in model.__table__.columns]

    candidates: dict[str, Any] = {}  # chave nova → linha vencedora entre as migradas
    removed: list[Any] = []
    for old, news in changed.items():
        row = rows.get(old)
        if row is None:
            continue
        if old not in news:
            removed.append(row)
        for new in news - {old}:
            best = candidates.get(new)
            if best is None or _newer(stamp(row), stamp(best)):
                candidates[new] = row

    additions = []
    for new, source in candidates.items():
        occupant = rows.get(new)
        if occupant is not None and occupant not in removed:
            if not _newer(stamp(source), stamp(occupant)):
                continue
            removed.append(occupant)
        data = {name: getattr(source, name) for name in columns}
        data["merchant_key"] = new
        additions.append(model(**data))

    for row in removed:
        session.delete(row)
    session.flush()
    session.add_all(additions)


def _newer(candidate: Any, current: Any) -> bool:
    return candidate is not None and (current is None or candidate > current)
