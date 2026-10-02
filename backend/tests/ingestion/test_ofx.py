from datetime import date

import pytest

from app.domain.months import YearMonth
from app.ingestion.adapters.ofx import OfxAdapter
from app.ingestion.types import AccountInfo, RawTransaction, RejectedFile

ADAPTER = OfxAdapter()
SEP = YearMonth(2026, 9)
NUBANK_ACCOUNT = AccountInfo("nubank", "conta", "12345678-9", "Nubank conta")


def _fitid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def test_golden_statement(fixture_file):
    name, content = fixture_file("nubank/NU_123456789_10SET2026_24SET2026.ofx")

    parsed = ADAPTER.parse(content, name)

    assert parsed.account == NUBANK_ACCOUNT
    assert parsed.errors == []
    assert parsed.transactions == [
        RawTransaction(1, date(2026, 9, 10), -2500, "Crédito em conta", SEP, _fitid(5)),
        RawTransaction(
            2, date(2026, 9, 12), 8990, "Compra no débito - MERCADO EXEMPLO", SEP, _fitid(6)
        ),
        RawTransaction(
            3,
            date(2026, 9, 20),
            4500,
            "Transferência enviada pelo Pix - BELTRANO DA SILVA - •••.654.321-•• - "
            "BCO EXEMPLO S.A. (0001) Agência: 1 Conta: 65432-1",
            SEP,
            _fitid(7),
        ),
        # 23h do dia 24 em BRT: continua dia 24 (sem conversão para UTC).
        RawTransaction(
            4, date(2026, 9, 24), 3250, "Compra no débito - FARMACIA EXEMPLO", SEP, _fitid(8)
        ),
    ]


def test_inflow_is_negative_and_outflow_positive(fixture_file):
    name, content = fixture_file("nubank/NU_123456789_01SET2026_15SET2026.ofx")

    amounts = {t.description_raw: t.amount_cents for t in ADAPTER.parse(content, name).transactions}

    assert amounts["Pagamento de fatura"] == 331760
    assert amounts["Crédito em conta"] == -2500


def _ofx(bank_id: str = "0260", acct_type: str = "CHECKING") -> bytes:
    return (
        "OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTRS><BANKACCTFROM>\n"
        f"<BANKID>{bank_id}\n<ACCTID>1-0\n<ACCTTYPE>{acct_type}\n</BANKACCTFROM>\n"
        "<BANKTRANLIST>\n<STMTTRN>\n<TRNTYPE>DEBIT\n<DTPOSTED>20260901\n<TRNAMT>-1.5\n"
        "<FITID>abc\n<MEMO>Sem fechamento &amp; com entidade\n</BANKTRANLIST></STMTRS></OFX>"
    ).encode()


def test_sgml_without_closing_tags():
    parsed = ADAPTER.parse(_ofx(), "extrato.ofx")

    assert parsed.transactions == [
        RawTransaction(1, date(2026, 9, 1), 150, "Sem fechamento & com entidade", SEP, "abc")
    ]


def test_itau_bank_id_is_recognized():
    assert ADAPTER.parse(_ofx(bank_id="0341"), "itau.ofx").account.bank == "itau"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (_ofx(bank_id="0999"), "banco não suportado"),
        (_ofx(acct_type="CREDITLINE"), "tipo de conta"),
        (b"OFXHEADER:100\n<OFX><CREDITCARDMSGSRSV1><CCACCTFROM>", "cartão"),
    ],
)
def test_unsupported_ofx_is_rejected(content, message):
    with pytest.raises(RejectedFile, match=message):
        ADAPTER.parse(content, "x.ofx")


def test_sniff():
    assert ADAPTER.sniff(b"OFXHEADER:100\nDATA:OFXSGML")
    assert not ADAPTER.sniff(b"date,title,amount\n")
