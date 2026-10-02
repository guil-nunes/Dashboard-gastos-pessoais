"""Estruturas que atravessam os estágios puros do pipeline de importação."""

from dataclasses import dataclass, field
from datetime import date

from app.domain.installments import InstallmentInfo
from app.domain.months import YearMonth


class RejectedFile(Exception):
    """Arquivo não reconhecido ou inválido como um todo; nada dele é gravado."""


@dataclass(frozen=True)
class AccountInfo:
    bank: str  # 'nubank' | 'itau'
    kind: str  # 'conta' | 'cartao'
    external_account_id: str
    default_name: str


@dataclass(frozen=True)
class RawTransaction:
    """Uma linha do arquivo, já com sinal normalizado (positivo = saída) e competência do banco."""

    line_no: int
    occurred_on: date
    amount_cents: int
    description_raw: str
    competence: YearMonth
    external_id: str | None = None
    bank_category: str | None = None
    installment: InstallmentInfo | None = None
    first_month: YearMonth | None = None  # mês da parcela 1, pela data da linha (R10)


@dataclass(frozen=True)
class RowError:
    line_no: int
    reason: str


@dataclass(frozen=True)
class ParsedFile:
    account: AccountInfo
    transactions: list[RawTransaction]
    errors: list[RowError] = field(default_factory=list)
