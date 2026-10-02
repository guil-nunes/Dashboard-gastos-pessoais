"""Fatura do cartão Itaú em PDF (spec Anexo A.6.2).

- Duas colunas por página: cada coluna é lida inteira (esquerda, depois direita), sem intercalar.
- Lê "compras e saques" e "produtos e serviços"; ignora próximas faturas, resumo e simulações.
- Datas `DD/MM` sem ano: ano inferido pela data de emissão (fechamento) da fatura.
- A linha abaixo de cada lançamento traz a categoria do banco e a cidade (`VESTUÁRIO .Osasco`).
- Conferência: a soma lida tem de bater com "Total dos lançamentos atuais", senão rejeita.
"""

import re
from dataclasses import dataclass
from datetime import date

from app.domain.competence import first_installment_month_itau, itau_card_competence
from app.domain.dates import infer_year, parse_br_date
from app.domain.installments import parse_itau_installment
from app.domain.money import parse_brl_amount
from app.ingestion.pdf import line_text, open_pdf, page_lines
from app.ingestion.types import AccountInfo, ParsedFile, RawTransaction, RejectedFile, RowError

ACCOUNT = AccountInfo("itau", "cartao", "", "Itaú cartão")
# Divisa entre as colunas, antes do cabeçalho da direita: os ícones do resumo ("L", "=") ficam
# entre o fim dos valores da esquerda e o início da direita e pertencem à direita.
SPLIT_MARGIN = 12.0
# Divisa quando a página não tem cabeçalho de seção (calibrada nas amostras).
DEFAULT_SPLIT = 350.0

_AMOUNT = r"(-\s?)?(\d{1,3}(?:\.\d{3})*,\d{2})"
_TRANSACTION = re.compile(rf"^(\d{{2}})/(\d{{2}})\s+(.+?)\s+{_AMOUNT}$")
_DAY_MONTH = re.compile(r"^\d{2}/\d{2}\s")
_CATEGORY = re.compile(r"^([A-ZÀ-Ý][A-ZÀ-Ý &/-]*?)\s*\.")
_TOTAL = re.compile(rf"Total dos lançamentos atuais\s+{_AMOUNT}$", re.I)
_CLOSING = (
    re.compile(r"Emissão:\s*(\d{2}/\d{2}/\d{4})"),
    re.compile(r"Postagem:\s*(\d{2}/\d{2}/\d{4})"),
)
_ACTIVE_SECTIONS = ("lançamentos: compras e saques", "lançamentos: produtos e serviços")
_INACTIVE_SECTIONS = ("compras parceladas - próximas faturas",)


@dataclass
class _Entry:
    line_no: int
    day: int
    month: int
    description: str
    cents: int
    category: str | None = None


class ItauCardPdf:
    name = "itau_cartao_pdf"

    def sniff_text(self, first_page: str) -> bool:
        text = first_page.casefold()
        return "itaú" in text and "resumo da fatura" in text

    def parse(self, content: bytes, filename: str) -> ParsedFile:
        with open_pdf(content) as pdf:
            closing = _closing_date(pdf.pages[0].extract_text() or "")
            lines = []
            split = DEFAULT_SPLIT
            for page in pdf.pages:
                split = _column_split(page, split)
                lines += page_lines(page, 0, split) + page_lines(page, split, page.width)

        entries, errors, total = _read_sections([line_text(line) for line in lines])
        if total is None:
            raise RejectedFile("fatura Itaú sem 'Total dos lançamentos atuais'")
        read = sum(entry.cents for entry in entries)
        if read != total:
            raise RejectedFile(
                f"soma lida R$ {_brl(read)} difere do total da fatura R$ {_brl(total)}; "
                "o arquivo não foi importado"
            )
        transactions = [_to_raw(entry, closing) for entry in entries]
        return ParsedFile(ACCOUNT, transactions, errors)


def _closing_date(first_page: str) -> date:
    for pattern in _CLOSING:
        if match := pattern.search(first_page):
            return parse_br_date(match.group(1))
    raise RejectedFile("fatura Itaú sem data de emissão")


def _column_split(page, previous: float) -> float:
    headers = [w for w in page.extract_words() if w["text"] == "Lançamentos:"]
    starts = sorted({round(w["x0"]) for w in headers})
    return starts[-1] - SPLIT_MARGIN if len(starts) >= 2 else previous


def _read_sections(texts: list[str]) -> tuple[list[_Entry], list[RowError], int | None]:
    entries: list[_Entry] = []
    errors: list[RowError] = []
    total = None
    active = False
    last: _Entry | None = None
    for line_no, text in enumerate(texts, start=1):
        lowered = text.casefold()
        if any(section in lowered for section in _ACTIVE_SECTIONS):
            active, last = True, None
            continue
        if any(section in lowered for section in _INACTIVE_SECTIONS):
            active, last = False, None
            continue
        if match := _TOTAL.search(text):
            total = parse_brl_amount((match.group(1) or "") + match.group(2))
            active, last = False, None
            continue
        if not active:
            continue
        if match := _TRANSACTION.match(text):
            day, month, description, sign, value = match.groups()
            last = _Entry(
                line_no, int(day), int(month), description, parse_brl_amount((sign or "") + value)
            )
            entries.append(last)
        elif _DAY_MONTH.match(text):
            errors.append(RowError(line_no, f"lançamento ilegível: {text}"))
            last = None
        elif last is not None and last.category is None and (match := _CATEGORY.match(text)):
            last.category = match.group(1).strip()
    return entries, errors, total


def _to_raw(entry: _Entry, closing: date) -> RawTransaction:
    purchase = infer_year(entry.day, entry.month, closing)
    installment = parse_itau_installment(entry.description)
    return RawTransaction(
        line_no=entry.line_no,
        occurred_on=purchase,
        amount_cents=entry.cents,  # positivo = compra; negativo = estorno/crédito
        description_raw=entry.description,
        competence=itau_card_competence(purchase, installment),
        bank_category=entry.category,
        installment=installment,
        first_month=first_installment_month_itau(purchase) if installment else None,
    )


def _brl(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    integer, rest = divmod(abs(cents), 100)
    return f"{sign}{integer:,}".replace(",", ".") + f",{rest:02d}"
