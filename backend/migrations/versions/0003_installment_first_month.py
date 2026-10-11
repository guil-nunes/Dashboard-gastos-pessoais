"""Mês da parcela 1 nas transações (spec R10), base das parcelas projetadas.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _shift(year: int, month: int, months: int) -> str:
    index = year * 12 + (month - 1) + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def upgrade() -> None:
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("installment_first_month", sa.String(length=7), nullable=True)
        )

    # Reais já gravadas: mesmas regras de domain/competence.py, a partir da data da linha
    # (Nubank: mês da linha − (n−1); Itaú: mês da compra). Valores fixos, sem importar o app.
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT t.id, t.occurred_on, t.installment_number, a.bank "
            "FROM transactions t JOIN account a ON a.id = t.account_id "
            "WHERE t.installment_number IS NOT NULL AND t.status = 'real'"
        )
    ).all()
    for transaction_id, occurred_on, number, bank in rows:
        year, month = int(str(occurred_on)[:4]), int(str(occurred_on)[5:7])
        first = _shift(year, month, -(number - 1) if bank == "nubank" else 0)
        connection.execute(
            sa.text("UPDATE transactions SET installment_first_month = :first WHERE id = :id"),
            {"first": first, "id": transaction_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_column("installment_first_month")
