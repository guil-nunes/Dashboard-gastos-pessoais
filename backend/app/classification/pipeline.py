from collections.abc import Sequence

from app.classification.base import Classification, ClassificationInput, Strategy
from app.classification.structural import StructuralRules

# Ordem do R6; as estratégias 1–3 entram na Fase 2.
DEFAULT_STRATEGIES: list[Strategy] = [StructuralRules()]

UNCLASSIFIED = Classification(kind="despesa", source="nenhuma")


def classify(
    item: ClassificationInput, strategies: Sequence[Strategy] = DEFAULT_STRATEGIES
) -> Classification:
    """A primeira estratégia que responder vence; sem resposta, despesa sem categoria."""
    for strategy in strategies:
        result = strategy.classify(item)
        if result is not None:
            return result
    return UNCLASSIFIED
