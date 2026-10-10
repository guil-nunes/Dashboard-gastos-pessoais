"""Classificação (spec R6, Q16): motivo na memória, mapa da categoria do banco e seeds.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Valores fixos: a migração não depende dos modelos Python, que mudam depois.
# Chaves no formato que o adapter do Itaú grava (categoria truncada, sem ponto final).
BANK_CATEGORY_MAP = [
    ("SAÚDE", "Saúde e Bem-Estar"),
    ("ALIMENTAÇÃO", "Alimentação"),
    ("MORADIA", "Moradia"),
    ("TURISMO E ENTRETENIM", "Lazer e Tecnologia"),
    ("HOBBY", "Lazer e Tecnologia"),
]

# (padrão `contains`, categoria); o padrão casa em minúsculas na descrição e no merchant_key.
KEYWORD_RULES = [
    ("ifd*", "Alimentação"),
    ("ifood", "Alimentação"),
    ("rappi", "Alimentação"),
    ("uber", "Transporte"),
    ("netflix", "Lazer e Tecnologia"),
    ("spotify", "Lazer e Tecnologia"),
]


def upgrade() -> None:
    with op.batch_alter_table("merchant_memory", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ignore_reason", sa.String(), nullable=True))
        batch_op.create_check_constraint(
            "ck_merchant_memory_ignore_reason",
            "ignore_reason IN ('pagamento_fatura', 'transferencia_interna', 'receita', 'outro')",
        )

    bank_map = op.create_table(
        "bank_category_map",
        sa.Column("bank_category", sa.String(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name=op.f("fk_bank_category_map_category_id_category"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("bank_category", name=op.f("pk_bank_category_map")),
    )

    connection = op.get_bind()
    category_ids = dict(connection.execute(sa.text("SELECT name, id FROM category")).all())
    op.bulk_insert(
        bank_map,
        [
            {"bank_category": bank_category, "category_id": category_ids[name]}
            for bank_category, name in BANK_CATEGORY_MAP
        ],
    )
    rules = sa.table(
        "keyword_rule",
        sa.column("pattern", sa.String),
        sa.column("match_type", sa.String),
        sa.column("category_id", sa.Integer),
        sa.column("priority", sa.Integer),
    )
    op.bulk_insert(
        rules,
        [
            {
                "pattern": pattern,
                "match_type": "contains",
                "category_id": category_ids[name],
                "priority": priority,
            }
            for priority, (pattern, name) in enumerate(KEYWORD_RULES, start=1)
        ],
    )


def downgrade() -> None:
    seeded = ", ".join(f"'{pattern}'" for pattern, _ in KEYWORD_RULES)
    op.execute(f"DELETE FROM keyword_rule WHERE pattern IN ({seeded})")
    op.drop_table("bank_category_map")
    with op.batch_alter_table("merchant_memory", schema=None) as batch_op:
        batch_op.drop_constraint("ck_merchant_memory_ignore_reason", type_="check")
        batch_op.drop_column("ignore_reason")
