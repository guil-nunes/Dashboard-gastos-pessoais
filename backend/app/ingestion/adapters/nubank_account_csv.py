"""Extrato da conta Nubank em CSV (spec Anexo A.3, P1): `Data,Valor,Identificador,Descrição`.

O CSV não traz a conta; ela vem do nome do arquivo (`NU_698150529_...` → `69815052-9`, o mesmo
`ACCTID` do OFX), para OFX e CSV do mesmo período caírem na mesma conta sem duplicar.
"""

import csv
import io
import re
from pathlib import PurePath

from app.domain.competence import competence_by_line_date
from app.domain.dates import parse_br_date
from app.domain.money import parse_decimal_amount, to_outflow
from app.ingestion.text import decode, first_line
from app.ingestion.types import AccountInfo, ParsedFile, RawTransaction, RejectedFile, RowError

HEADER = "Data,Valor,Identificador,Descrição"
_FILENAME = re.compile(r"^NU_(\d{2,})_", re.I)


class NubankAccountCsv:
    name = "nubank_conta_csv"

    def sniff(self, head: bytes) -> bool:
        return first_line(head) == HEADER

    def parse(self, content: bytes, filename: str) -> ParsedFile:
        account = AccountInfo(
            bank="nubank",
            kind="conta",
            external_account_id=account_id_from_filename(filename),
            default_name="Nubank conta",
        )
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
        return ParsedFile(account, transactions, errors)


def account_id_from_filename(filename: str) -> str:
    match = _FILENAME.match(PurePath(filename).name)
    if match is None:
        raise RejectedFile(
            "CSV da conta Nubank sem o número da conta no nome (esperado NU_<conta>_...). "
            "Use o nome original do arquivo ou importe o OFX."
        )
    digits = match.group(1)
    return f"{digits[:-1]}-{digits[-1]}"


def _parse_row(line_no: int, row: list[str]) -> RawTransaction:
    if len(row) != 4:
        raise ValueError(f"esperadas 4 colunas, encontradas {len(row)}")
    day_text, amount_text, identifier, description = row
    if not identifier.strip():
        raise ValueError("linha sem Identificador")
    occurred_on = parse_br_date(day_text)
    return RawTransaction(
        line_no=line_no,
        occurred_on=occurred_on,
        amount_cents=to_outflow(parse_decimal_amount(amount_text), positive_is_outflow=False),
        description_raw=description,
        competence=competence_by_line_date(occurred_on),
        external_id=identifier.strip(),
    )
