"""Interface comum das estratégias de classificação (spec R6)."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ClassificationInput:
    account_kind: str  # 'conta' | 'cartao'
    amount_cents: int  # positivo = saída
    description_raw: str
    merchant_key: str
    bank_category: str | None = None
    holder: str | None = None  # titular da conta; só para sugerir investimento (Q15)


@dataclass(frozen=True)
class Classification:
    """Tipo (R4) e categoria vêm juntos de uma mesma estratégia."""

    kind: str  # 'despesa' | 'ignorar'
    source: str  # 'memoria' | 'regra' | 'classificador' | 'gemini' | 'manual' | 'nenhuma'
    ignore_reason: str | None = None
    category_id: int | None = None
    confidence: float | None = None
    suggested_ignore_reason: str | None = None  # sugestão que exige confirmação (Q15)


class Strategy(Protocol):
    def classify(self, item: ClassificationInput) -> Classification | None:
        """Devolve a classificação, ou `None` para passar a vez à próxima estratégia."""
        ...


@dataclass(frozen=True)
class MemoryEntry:
    category_id: int | None
    kind: str | None
    ignore_reason: str | None


@dataclass(frozen=True)
class KeywordRuleEntry:
    pattern: str
    match_type: str  # 'contains' | 'regex'
    category_id: int | None
    kind: str | None


@dataclass(frozen=True)
class ClassifierContext:
    """Dados do banco que as estratégias 1–3 consultam, carregados antes do estágio puro."""

    memory: dict[str, MemoryEntry] = field(default_factory=dict)
    rules: tuple[KeywordRuleEntry, ...] = ()  # já ordenadas por prioridade
    bank_map: dict[str, int] = field(default_factory=dict)  # categoria do banco → category_id
