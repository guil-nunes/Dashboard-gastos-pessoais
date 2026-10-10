"""Estratégia 3: categoria informada pelo banco, de baixa confiança (spec R6, Q16).

Categorias sem mapeamento (`DIVERSOS`, novas) não sugerem nada.
"""

from app.classification.base import Classification, ClassificationInput

BANK_CATEGORY_CONFIDENCE = 0.5


class BankCategoryStrategy:
    def __init__(self, bank_map: dict[str, int]) -> None:
        self._bank_map = bank_map

    def classify(self, item: ClassificationInput) -> Classification | None:
        if not item.bank_category:
            return None
        category_id = self._bank_map.get(item.bank_category.strip().upper())
        if category_id is None:
            return None
        return Classification(
            kind="despesa",
            category_id=category_id,
            source="regra",
            confidence=BANK_CATEGORY_CONFIDENCE,
        )
