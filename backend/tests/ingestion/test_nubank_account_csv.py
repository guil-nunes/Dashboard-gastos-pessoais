from datetime import date

import pytest

from app.domain.months import YearMonth
from app.ingestion.adapters.nubank_account_csv import NubankAccountCsv, account_id_from_filename
from app.ingestion.adapters.ofx import OfxAdapter
from app.ingestion.types import RawTransaction, RejectedFile

ADAPTER = NubankAccountCsv()
SEP = YearMonth(2026, 9)


def test_golden_statement(fixture_file):
    name, content = fixture_file("nubank/NU_123456789_01SET2026_15SET2026.csv")

    parsed = ADAPTER.parse(content, name)

    assert parsed.account.external_account_id == "12345678-9"
    assert parsed.errors == []
    assert parsed.transactions[2:4] == [
        RawTransaction(
            4,
            date(2026, 9, 2),
            331760,
            "Pagamento de fatura",
            SEP,
            "00000000-0000-4000-8000-000000000003",
        ),
        RawTransaction(
            5,
            date(2026, 9, 5),
            1007,
            "Compra no débito - POSTO EXEMPLO",
            SEP,
            "00000000-0000-4000-8000-000000000004",
        ),
    ]


def test_same_content_as_ofx_of_the_same_period(fixture_file):
    csv_name, csv_content = fixture_file("nubank/NU_123456789_01SET2026_15SET2026.csv")
    ofx_name, ofx_content = fixture_file("nubank/NU_123456789_01SET2026_15SET2026.ofx")

    from_csv = ADAPTER.parse(csv_content, csv_name)
    from_ofx = OfxAdapter().parse(ofx_content, ofx_name)

    assert from_csv.account == from_ofx.account

    def comparable(parsed):
        return [
            (t.occurred_on, t.amount_cents, t.description_raw, t.external_id)
            for t in parsed.transactions
        ]

    assert comparable(from_csv) == comparable(from_ofx)


def test_account_from_original_filename():
    assert account_id_from_filename("NU_698150529_01SET2026_24SET2026.csv") == "69815052-9"
    assert account_id_from_filename("C:/Downloads/NU_123456789_x.csv") == "12345678-9"


def test_renamed_file_is_rejected(fixture_file):
    _, content = fixture_file("nubank/NU_123456789_01SET2026_15SET2026.csv")

    with pytest.raises(RejectedFile, match="nome original"):
        ADAPTER.parse(content, "extrato_setembro.csv")


def test_sniff_accepts_utf8_and_latin1_headers():
    assert ADAPTER.sniff("Data,Valor,Identificador,Descrição\n".encode())
    assert ADAPTER.sniff("Data,Valor,Identificador,Descrição\n".encode("cp1252"))
