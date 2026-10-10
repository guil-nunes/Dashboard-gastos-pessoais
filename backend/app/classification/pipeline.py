from collections.abc import Sequence

from app.classification.bank_category import BankCategoryStrategy
from app.classification.base import Classification, ClassificationInput, ClassifierContext, Strategy
from app.classification.investment import with_investment_suggestion
from app.classification.keyword import KeywordStrategy
from app.classification.memory import MemoryStrategy
from app.classification.structural import StructuralRules

UNCLASSIFIED = Classification(kind="despesa", source="nenhuma")


def build_strategies(context: ClassifierContext) -> list[Strategy]:
    """Ordem do R6: estrutural, memória, palavra-chave, categoria do banco."""
    return [
        StructuralRules(),
        MemoryStrategy(context.memory),
        KeywordStrategy(context.rules),
        BankCategoryStrategy(context.bank_map),
    ]


def classify(item: ClassificationInput, strategies: Sequence[Strategy]) -> Classification:
    """A primeira estratégia que responder vence; sem resposta, despesa sem categoria."""
    result = UNCLASSIFIED
    for strategy in strategies:
        answer = strategy.classify(item)
        if answer is not None:
            result = answer
            break
    return with_investment_suggestion(item, result)
