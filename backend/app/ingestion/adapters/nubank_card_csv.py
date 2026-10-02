"""Fatura do cartão Nubank em CSV (spec Anexo A.1): `date,title,amount`."""

import csv
import io

from app.domain.competence import competence_by_line_date, first_installment_month_nubank
from app.domain.dates import parse_iso_date
from app.domain.installments import parse_nubank_installment
from app.domain.money import parse_brl_amount
from app.ingestion.text import decode, first_line
from app.ingestion.types import AccountInfo, ParsedFile, RawTransaction, RowError

HEADER = "date,title,amount"
# O CSV não identifica o cartão: uma conta "Nubank cartão" fixa.
ACCOUNT = AccountInfo(
    bank="nubank", kind="cartao", external_account_id="", default_name="Nubank cartão"
)


class NubankCardCsv:
    name = "nubank_cartao_csv"

    def sniff(self, head: bytes) -> bool:
        return first_line(head) == HEADER

    def parse(self, content: bytes, filename: str) -> ParsedFile:
        rows = csv.reader(io.StringIO(decode(content)))
        next(rows)  # cabeçalho
        transactions, errors = [], []
        for line_no, row in enumerate(rows, start=2):
            if not any(cell.strip() for cell in row):
                continue
            try:
                transactions.append(_parse_row(line_no, row))
            except ValueError as error:
                errors.append(RowError(line_no, str(error)))
        return ParsedFile(ACCOUNT, transactions, errors)


def _parse_row(line_no: int, row: list[str]) -> RawTransaction:
    if len(row) != 3:
        raise ValueError(f"esperadas 3 colunas, encontradas {len(row)}")
    day_text, title, amount_text = row
    occurred_on = parse_iso_date(day_text)
    installment = parse_nubank_installment(title)
    return RawTransaction(
        line_no=line_no,
        occurred_on=occurred_on,
        amount_cents=parse_brl_amount(amount_text),  # positivo = compra, como no sistema
        description_raw=title,
        competence=competence_by_line_date(occurred_on),
        installment=installment,
        first_month=(
            first_installment_month_nubank(occurred_on, installment.number) if installment else None
        ),
    )
