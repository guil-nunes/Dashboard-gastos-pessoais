"""Sugestão de investimento (spec Q15): nunca aplicada, só sugerida para confirmação.

Não é uma estratégia da cadeia: não decide tipo nem categoria, só anota a sugestão.
"""

import re
import unicodedata

from app.classification.base import Classification, ClassificationInput

_PIX_SENT = re.compile(r"^PIX\s+(?P<name>.+)$")


def _fold(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(ascii_text.upper().split())


def suggests_investment(item: ClassificationInput) -> bool:
    if item.amount_cents <= 0:
        return False
    if "APLICACAO COFRINHOS" in _fold(item.description_raw):
        return True
    if not item.holder:
        return False
    match = _PIX_SENT.match(_fold(item.merchant_key))
    return match is not None and match.group("name") == _fold(item.holder)


def with_investment_suggestion(item: ClassificationInput, result: Classification) -> Classification:
    """Só em despesas decididas por estratégia automática; correção manual não é tocada."""
    if result.kind != "despesa" or result.source == "manual":
        return result
    if not suggests_investment(item):
        return result
    return Classification(
        kind=result.kind,
        source=result.source,
        ignore_reason=result.ignore_reason,
        category_id=result.category_id,
        confidence=result.confidence,
        suggested_ignore_reason="investimento",
    )
