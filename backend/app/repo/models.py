"""Modelos SQLAlchemy do modelo de dados (spec §8). Mudou aqui → nova migração Alembic."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nomes estáveis de constraints: o SQLite recria tabelas para alterá-las (batch mode).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

BANKS = ("nubank", "itau")
ACCOUNT_KINDS = ("conta", "cartao")
TRANSACTION_KINDS = ("despesa", "ignorar")
IGNORE_REASONS = ("pagamento_fatura", "transferencia_interna", "investimento", "receita", "outro")
CATEGORY_SOURCES = ("memoria", "regra", "classificador", "gemini", "manual", "nenhuma")
STATUSES = ("real", "projetada")
MATCH_TYPES = ("contains", "regex")


def _one_of(column: str, values: tuple[str, ...], name: str | None = None) -> CheckConstraint:
    allowed = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name or column)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        UniqueConstraint("bank", "kind", "external_account_id"),
        _one_of("bank", BANKS),
        _one_of("kind", ACCOUNT_KINDS),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bank: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    # '' em vez de NULL: no SQLite, NULLs são distintos em UNIQUE e duplicariam contas.
    external_account_id: Mapped[str] = mapped_column(String, default="", server_default="")
    name: Mapped[str] = mapped_column(String)
    holder: Mapped[str | None] = mapped_column(String)


class ImportBatch(Base):
    """Só importações bem-sucedidas são gravadas."""

    __tablename__ = "import_batch"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    filename: Mapped[str] = mapped_column(String)
    file_sha256: Mapped[str] = mapped_column(String, unique=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime)
    rows_total: Mapped[int]
    rows_new: Mapped[int]
    rows_duplicate: Mapped[int]
    rows_error: Mapped[int]


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    color: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(default=True)


class Transaction(Base):
    __tablename__ = "transactions"  # plural: TRANSACTION é palavra-chave do SQL
    __table_args__ = (
        UniqueConstraint("installment_group_key", "installment_number"),
        Index("ix_transactions_competence_status_kind", "competence_month", "status", "kind"),
        _one_of("kind", TRANSACTION_KINDS),
        _one_of("ignore_reason", IGNORE_REASONS),
        _one_of("suggested_ignore_reason", IGNORE_REASONS),
        _one_of("category_source", CATEGORY_SOURCES),
        _one_of("status", STATUSES),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    # Lote que criou a transação (informativo); as origens completas ficam em transaction_source.
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batch.id", ondelete="SET NULL")
    )
    occurred_on: Mapped[date] = mapped_column(Date)
    competence_month: Mapped[str] = mapped_column(String(7))
    amount_cents: Mapped[int]  # positivo = saída
    description_raw: Mapped[str] = mapped_column(String)
    external_id: Mapped[str | None] = mapped_column(String)
    merchant_key: Mapped[str] = mapped_column(String, index=True)
    normalizer_version: Mapped[int]
    kind: Mapped[str] = mapped_column(String)
    ignore_reason: Mapped[str | None] = mapped_column(String)
    suggested_ignore_reason: Mapped[str | None] = mapped_column(String)
    bank_category: Mapped[str | None] = mapped_column(String)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id", ondelete="SET NULL"))
    category_source: Mapped[str] = mapped_column(String)
    category_confidence: Mapped[float | None]
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    installment_number: Mapped[int | None]
    installment_total: Mapped[int | None]
    installment_group_key: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    dedup_key: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class TransactionSource(Base):
    """Todos os lotes que contêm a transação, inclusive os que a viram como duplicata."""

    __tablename__ = "transaction_source"

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), primary_key=True
    )
    import_batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batch.id", ondelete="CASCADE"), primary_key=True
    )


class InstallmentGroupOverride(Base):
    __tablename__ = "installment_group_override"

    installment_group_key: Mapped[str] = mapped_column(String, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class MerchantMemory(Base):
    __tablename__ = "merchant_memory"
    __table_args__ = (_one_of("kind", TRANSACTION_KINDS),)

    merchant_key: Mapped[str] = mapped_column(String, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id", ondelete="SET NULL"))
    kind: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class KeywordRule(Base):
    __tablename__ = "keyword_rule"
    __table_args__ = (
        _one_of("match_type", MATCH_TYPES),
        _one_of("kind", TRANSACTION_KINDS),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(String)
    match_type: Mapped[str] = mapped_column(String)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id", ondelete="SET NULL"))
    kind: Mapped[str | None] = mapped_column(String)
    priority: Mapped[int]


class LlmCache(Base):
    __tablename__ = "llm_cache"

    merchant_key: Mapped[str] = mapped_column(String, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id", ondelete="SET NULL"))
    raw_response: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class RecurrenceOverride(Base):
    __tablename__ = "recurrence_override"

    merchant_key: Mapped[str] = mapped_column(String, primary_key=True)
    is_recurring: Mapped[bool]
