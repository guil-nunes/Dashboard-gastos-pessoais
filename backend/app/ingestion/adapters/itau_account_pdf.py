"""Extrato da conta Itaú em PDF (spec Anexo A.6.1).

Coluna única, data de lançamento e valor com sinal (negativo = saída).

As colunas `valor (R$)` e `saldo (R$)` são separadas pela posição do cabeçalho; o saldo é ignorado.
"""

import re

from app.domain.competence import competence_by_line_date
from app.domain.dates import parse_br_date
from app.domain.money import parse_brl_amount, to_outflow
from app.ingestion.pdf import Word, line_text, open_pdf, page_lines
from app.ingestion.types import AccountInfo, ParsedFile, RawTransaction, RejectedFile, RowError

_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_ACCOUNT = re.compile(r"agência:\s*(\d+)\s+conta:\s*([\d-]+)", re.I)
# Margem à esquerda do rótulo "valor": os valores são alinhados à direita.
VALUE_MARGIN = 30.0


class ItauAccountPdf:
    name = "itau_conta_pdf"

    def sniff_text(self, first_page: str) -> bool:
        text = first_page.casefold()
        return "extrato conta" in text and "período de visualização" in text

    def parse(self, content: bytes, filename: str) -> ParsedFile:
        transactions, errors = [], []
        account = None
        columns = None  # (início da coluna de valor, início da coluna de saldo)
        line_no = 0
        with open_pdf(content) as pdf:
            for page in pdf.pages:
                for line in page_lines(page):
                    line_no += 1
                    text = line_text(line)
                    if account is None and (match := _ACCOUNT.search(text)):
                        account = match.group(1), match.group(2)
                    if columns is None:
                        columns = _header_columns(line)
                        continue
                    if not _DATE.match(line[0].text):
                        continue
                    try:
                        raw = _parse_line(line_no, line, columns)
                    except ValueError as error:
                        errors.append(RowError(line_no, f"{error}: {text}"))
                        continue
                    if raw is not None:
                        transactions.append(raw)
        if account is None:
            raise RejectedFile("extrato Itaú sem agência e conta no cabeçalho")
        if columns is None:
            raise RejectedFile("extrato Itaú sem o cabeçalho da tabela de lançamentos")
        agency, number = account
        info = AccountInfo("itau", "conta", f"{agency}/{number}", "Itaú conta")
        return ParsedFile(info, transactions, errors)


def _header_columns(line: list[Word]) -> tuple[float, float] | None:
    labels = {word.text.casefold(): word for word in line}
    if {"data", "lançamentos", "valor", "saldo"} <= labels.keys():
        return labels["valor"].x0 - VALUE_MARGIN, labels["saldo"].x0
    return None


def _parse_line(
    line_no: int, line: list[Word], columns: tuple[float, float]
) -> RawTransaction | None:
    value_start, balance_start = columns
    date_word, rest = line[0], line[1:]
    description = " ".join(w.text for w in rest if w.x0 < value_start)
    value = "".join(w.text for w in rest if value_start <= w.x0 < balance_start)
    if not value:
        if description.upper().startswith("SALDO"):
            return None  # linha de saldo (só a coluna de saldo preenchida)
        raise ValueError("lançamento sem valor")
    occurred_on = parse_br_date(date_word.text)
    return RawTransaction(
        line_no=line_no,
        occurred_on=occurred_on,
        amount_cents=to_outflow(parse_brl_amount(value), positive_is_outflow=False),
        description_raw=description,
        competence=competence_by_line_date(occurred_on),
    )
