"""Conferência das projetadas com a "Próxima fatura" do Itaú (spec R10, informativa).

Cada parcela que o banco já prevê deve existir como projetada na conta, com o mesmo valor.
Divergência vira aviso; nunca bloqueia a importação.
"""

from sqlalchemy.orm import Session

from app.ingestion.types import NextInvoiceLine
from app.repo import imports as repo


def check_next_invoice(
    session: Session, account_id: int, lines: list[NextInvoiceLine]
) -> list[str]:
    projected = repo.projected_by_description(session, account_id, [x.description for x in lines])
    warnings = []
    for line in lines:
        match = projected.get(line.description)
        if match is None:
            warnings.append(
                f"Próxima fatura: «{line.description}» não corresponde a nenhuma parcela projetada"
            )
        elif match.amount_cents != line.amount_cents:
            warnings.append(
                f"Próxima fatura: «{line.description}» vale {_brl(line.amount_cents)} no banco "
                f"e {_brl(match.amount_cents)} na projetada"
            )
    return warnings


def _brl(cents: int) -> str:
    integer, rest = divmod(abs(cents), 100)
    return f"R$ {integer:,}".replace(",", ".") + f",{rest:02d}"
