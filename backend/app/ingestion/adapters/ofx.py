"""Extrato de conta corrente em OFX 1.x/SGML (spec Anexo A.2). Genérico: o banco vem do BANKID."""

import html
import re

from app.domain.competence import competence_by_line_date
from app.domain.dates import parse_ofx_date
from app.domain.money import parse_decimal_amount, to_outflow
from app.ingestion.text import decode
from app.ingestion.types import AccountInfo, ParsedFile, RawTransaction, RejectedFile, RowError

# Código de compensação → banco do sistema.
BANKS = {"260": ("nubank", "Nubank conta"), "341": ("itau", "Itaú conta")}
CHECKING_TYPES = {"CHECKING", "SAVINGS", "MONEYMRKT"}

_TRANSACTION = re.compile(r"<STMTTRN>(.*?)(?=</STMTTRN>|<STMTTRN>|</BANKTRANLIST>)", re.S | re.I)


def _tag(block: str, name: str) -> str | None:
    # SGML: o valor vai até a próxima tag ou fim de linha; o fechamento é opcional.
    match = re.search(rf"<{name}>([^<\r\n]*)", block, re.I)
    return html.unescape(match.group(1).strip()) if match else None


def _has(text: str, name: str) -> bool:
    return re.search(rf"<{name}>", text, re.I) is not None


class OfxAdapter:
    name = "ofx_conta"

    def sniff(self, head: bytes) -> bool:
        text = decode(head).lstrip().upper()
        return text.startswith("OFXHEADER:") or (text.startswith("<?XML") and "<OFX>" in text)

    def parse(self, content: bytes, filename: str) -> ParsedFile:
        text = decode(content)
        account = _account(text)
        transactions, errors = [], []
        for index, match in enumerate(_TRANSACTION.finditer(text), start=1):
            try:
                transactions.append(_parse_transaction(index, match.group(1)))
            except ValueError as error:
                errors.append(RowError(index, str(error)))
        return ParsedFile(account, transactions, errors)


def _account(text: str) -> AccountInfo:
    if not _has(text, "BANKACCTFROM"):
        raise RejectedFile("OFX sem conta corrente (BANKACCTFROM); OFX de cartão não é suportado")
    bank_id = (_tag(text, "BANKID") or _tag(text, "FID") or "").lstrip("0")
    if bank_id not in BANKS:
        raise RejectedFile(f"OFX de banco não suportado (código {bank_id or 'ausente'})")
    account_type = (_tag(text, "ACCTTYPE") or "").upper()
    if account_type not in CHECKING_TYPES:
        raise RejectedFile(f"tipo de conta OFX não suportado: {account_type or 'ausente'}")
    account_id = _tag(text, "ACCTID")
    if not account_id:
        raise RejectedFile("OFX sem identificação da conta (ACCTID)")
    bank, name = BANKS[bank_id]
    return AccountInfo(bank=bank, kind="conta", external_account_id=account_id, default_name=name)


def _parse_transaction(index: int, block: str) -> RawTransaction:
    posted, amount, fitid = _tag(block, "DTPOSTED"), _tag(block, "TRNAMT"), _tag(block, "FITID")
    description = _tag(block, "MEMO") or _tag(block, "NAME")
    if not (posted and amount and fitid and description):
        raise ValueError("transação sem DTPOSTED, TRNAMT, FITID ou MEMO")
    occurred_on = parse_ofx_date(posted)
    return RawTransaction(
        line_no=index,
        occurred_on=occurred_on,
        amount_cents=to_outflow(parse_decimal_amount(amount), positive_is_outflow=False),
        description_raw=description,
        competence=competence_by_line_date(occurred_on),
        external_id=fitid,
    )
