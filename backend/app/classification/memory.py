"""Estratégia 1: memória do usuário por `merchant_key` (spec R6).

Nunca devolve `investimento` (Q15): a memória não guarda esse motivo.
"""

from app.classification.base import Classification, ClassificationInput, MemoryEntry


class MemoryStrategy:
    def __init__(self, memory: dict[str, MemoryEntry]) -> None:
        self._memory = memory

    def classify(self, item: ClassificationInput) -> Classification | None:
        entry = self._memory.get(item.merchant_key)
        if entry is None or (entry.kind is None and entry.category_id is None):
            return None
        if entry.kind == "ignorar":
            if entry.ignore_reason is None or entry.ignore_reason == "investimento":
                return None
            return Classification(
                kind="ignorar",
                ignore_reason=entry.ignore_reason,
                category_id=entry.category_id,
                source="memoria",
                confidence=1.0,
            )
        if entry.category_id is None:
            return None  # sem categoria lembrada: deixa regras e categoria do banco sugerirem
        return Classification(
            kind="despesa", category_id=entry.category_id, source="memoria", confidence=1.0
        )
