"""Modelo de dados inicial (spec §8) e seed das 7 categorias.

Revision ID: 0001
Revises:
Create Date: 2026-10-01 22:08:28.908963
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Valores fixos: a migração não depende dos modelos Python, que mudam depois.
INITIAL_CATEGORIES = [
    ("Moradia", "#8d6e63"),
    ("Alimentação", "#ef6c00"),
    ("Transporte", "#1e88e5"),
    ("Saúde e Bem-Estar", "#43a047"),
    ("Educação e Trabalho", "#5e35b1"),
    ("Lazer e Tecnologia", "#d81b60"),
    ("Dívidas", "#546e7a"),
]


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bank", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("external_account_id", sa.String(), server_default="", nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("holder", sa.String(), nullable=True),
        sa.CheckConstraint("bank IN ('nubank', 'itau')", name=op.f("ck_account_bank")),
        sa.CheckConstraint("kind IN ('conta', 'cartao')", name=op.f("ck_account_kind")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
        sa.UniqueConstraint(
            "bank",
            "kind",
            "external_account_id",
            name=op.f("uq_account_bank_kind_external_account_id"),
        ),
    )
    category = op.create_table(
        "category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category")),
        sa.UniqueConstraint("name", name=op.f("uq_category_name")),
    )
    op.bulk_insert(
        category,
        [{"name": name, "color": color, "is_active": True} for name, color in INITIAL_CATEGORIES],
    )
    op.create_table(
        "recurrence_override",
        sa.Column("merchant_key", sa.String(), nullable=False),
        sa.Column("is_recurring", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("merchant_key", name=op.f("pk_recurrence_override")),
    )
    op.create_table(
        "import_batch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_sha256", sa.String(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("rows_new", sa.Integer(), nullable=False),
        sa.Column("rows_duplicate", sa.Integer(), nullable=False),
        sa.Column("rows_error", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_import_batch_account_id_account")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batch")),
        sa.UniqueConstraint("file_sha256", name=op.f("uq_import_batch_file_sha256")),
    )
    op.create_table(
        "installment_group_override",
        sa.Column("installment_group_key", sa.String(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_installment_group_override_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "installment_group_key", name=op.f("pk_installment_group_override")
        ),
    )
    op.create_table(
        "keyword_rule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern", sa.String(), nullable=False),
        sa.Column("match_type", sa.String(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.CheckConstraint("kind IN ('despesa', 'ignorar')", name=op.f("ck_keyword_rule_kind")),
        sa.CheckConstraint(
            "match_type IN ('contains', 'regex')", name=op.f("ck_keyword_rule_match_type")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_keyword_rule_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keyword_rule")),
    )
    op.create_table(
        "llm_cache",
        sa.Column("merchant_key", sa.String(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("raw_response", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_llm_cache_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("merchant_key", name=op.f("pk_llm_cache")),
    )
    op.create_table(
        "merchant_memory",
        sa.Column("merchant_key", sa.String(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('despesa', 'ignorar')", name=op.f("ck_merchant_memory_kind")),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_merchant_memory_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("merchant_key", name=op.f("pk_merchant_memory")),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("competence_month", sa.String(length=7), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("description_raw", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("merchant_key", sa.String(), nullable=False),
        sa.Column("normalizer_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("ignore_reason", sa.String(), nullable=True),
        sa.Column("suggested_ignore_reason", sa.String(), nullable=True),
        sa.Column("bank_category", sa.String(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("category_source", sa.String(), nullable=False),
        sa.Column("category_confidence", sa.Double(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("installment_number", sa.Integer(), nullable=True),
        sa.Column("installment_total", sa.Integer(), nullable=True),
        sa.Column("installment_group_key", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("dedup_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "category_source IN ('memoria', 'regra', 'classificador', 'gemini', 'manual', 'nenhuma')",
            name=op.f("ck_transactions_category_source"),
        ),
        sa.CheckConstraint(
            "ignore_reason IN ('pagamento_fatura', 'transferencia_interna', 'investimento', 'receita', 'outro')",
            name=op.f("ck_transactions_ignore_reason"),
        ),
        sa.CheckConstraint("kind IN ('despesa', 'ignorar')", name=op.f("ck_transactions_kind")),
        sa.CheckConstraint("status IN ('real', 'projetada')", name=op.f("ck_transactions_status")),
        sa.CheckConstraint(
            "suggested_ignore_reason IN ('pagamento_fatura', 'transferencia_interna', 'investimento', 'receita', 'outro')",
            name=op.f("ck_transactions_suggested_ignore_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_transactions_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_transactions_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batch.id"],
            name=op.f("fk_transactions_import_batch_id_import_batch"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint("dedup_key", name=op.f("uq_transactions_dedup_key")),
        sa.UniqueConstraint(
            "installment_group_key",
            "installment_number",
            name=op.f("uq_transactions_installment_group_key_installment_number"),
        ),
    )
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_transactions_competence_status_kind",
            ["competence_month", "status", "kind"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_transactions_merchant_key"), ["merchant_key"], unique=False
        )

    op.create_table(
        "transaction_source",
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batch.id"],
            name=op.f("fk_transaction_source_import_batch_id_import_batch"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_transaction_source_transaction_id_transactions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "transaction_id", "import_batch_id", name=op.f("pk_transaction_source")
        ),
    )


def downgrade() -> None:
    op.drop_table("transaction_source")
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_transactions_merchant_key"))
        batch_op.drop_index("ix_transactions_competence_status_kind")

    op.drop_table("transactions")
    op.drop_table("merchant_memory")
    op.drop_table("llm_cache")
    op.drop_table("keyword_rule")
    op.drop_table("installment_group_override")
    op.drop_table("import_batch")
    op.drop_table("recurrence_override")
    op.drop_table("category")
    op.drop_table("account")
