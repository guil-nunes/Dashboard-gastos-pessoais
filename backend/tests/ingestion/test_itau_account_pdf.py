from datetime import date

import pytest

from app.domain.months import YearMonth
from app.ingestion.adapters.itau_account_pdf import ItauAccountPdf
from app.ingestion.types import AccountInfo, RawTransaction, RejectedFile

ADAPTER = ItauAccountPdf()
SEP = YearMonth(2026, 9)


def _summary(parsed):
    return [(t.occurred_on, t.amount_cents, t.description_raw) for t in parsed.transactions]


def test_golden_statement_across_pages(fixture_file):
    name, content = fixture_file("itau/itau_extrato_A.pdf")

    parsed = ADAPTER.parse(content, name)

    assert parsed.account == AccountInfo("itau", "conta", "1234/56789-0", "Itaú conta")
    assert parsed.errors == []
    assert _summary(parsed) == [
        (date(2026, 9, 21), 1093, "ON Uber UBER 19/09"),  # lançada em 21/09, compra em 19/09
        (date(2026, 9, 18), 894, "ON Uber UBER 18/09"),
        (date(2026, 9, 18), 894, "ON Uber UBER 18/09"),
        (date(2026, 9, 16), 100, "PIX AUT HOTMART 16/09"),
        (date(2026, 9, 15), -5, "REND PAGO APLIC AUT MAIS"),
        (date(2026, 9, 10), 6000, "APLICACAO COFRINHOS"),
        (date(2026, 9, 5), 100000, "PIX TRANSF FULANO05/09"),
        (date(2026, 9, 5), -25000, "PIX TRANSF BELTRAN05/09"),
        (date(2026, 9, 2), 2697, "PAY Uber 02/09"),
    ]


def test_competence_is_the_posting_date(fixture_file):
    parsed = ADAPTER.parse(*reversed(fixture_file("itau/itau_extrato_A.pdf")))

    first = parsed.transactions[0]
    assert isinstance(first, RawTransaction)
    assert (first.occurred_on, first.competence) == (date(2026, 9, 21), SEP)
    assert first.external_id is None  # sem identificador: dedup por hash + ordinal


def test_balance_lines_are_skipped(fixture_file):
    parsed = ADAPTER.parse(*reversed(fixture_file("itau/itau_extrato_A.pdf")))
    assert not any("SALDO" in t.description_raw for t in parsed.transactions)


def test_sniff_text():
    assert ADAPTER.sniff_text("extrato conta / lançamentos\nperíodo de visualização: 01/09/2026")
    assert not ADAPTER.sniff_text("Resumo da fatura em R$ Banco Itaú S.A.")


def test_statement_without_account_is_rejected(fixture_file):
    _, content = fixture_file("itau/desconhecido.pdf")
    with pytest.raises(RejectedFile, match="agência e conta"):
        ADAPTER.parse(content, "x.pdf")
