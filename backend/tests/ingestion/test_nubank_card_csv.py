from datetime import date

from app.domain.installments import InstallmentInfo
from app.domain.months import YearMonth
from app.ingestion.adapters.nubank_card_csv import NubankCardCsv
from app.ingestion.types import AccountInfo, RawTransaction, RowError

ADAPTER = NubankCardCsv()
AUG = YearMonth(2026, 8)


def _line(line_no, day, cents, title, installment=None, first_month=None):
    return RawTransaction(
        line_no=line_no,
        occurred_on=day,
        amount_cents=cents,
        description_raw=title,
        competence=YearMonth.of(day),
        installment=installment,
        first_month=first_month,
    )


def test_golden_invoice(fixture_file):
    name, content = fixture_file("nubank/Nubank_2026-09-08.csv")

    parsed = ADAPTER.parse(content, name)

    assert parsed.account == AccountInfo("nubank", "cartao", "", "Nubank cartão")
    assert parsed.errors == []
    assert parsed.transactions == [
        _line(2, date(2026, 8, 31), 1006, "Forneria Exemplo"),
        _line(3, date(2026, 8, 24), 474, "Uber - NuPay"),
        _line(4, date(2026, 8, 24), 474, "Uber - NuPay"),
        _line(5, date(2026, 8, 18), 11000, "Anthropic* Claude Sub"),
        _line(6, date(2026, 8, 18), 400, 'IOF de "Anthropic* Claude Sub"'),
        _line(7, date(2026, 8, 4), -331760, "Pagamento recebido"),
        _line(
            8,
            date(2026, 8, 1),
            90946,
            "Latam Air*0000 - Parcela 4/4",
            InstallmentInfo("Latam Air*0000", 4, 4),
            YearMonth(2026, 5),
        ),
        _line(
            9,
            date(2026, 8, 1),
            1358,
            "Pag*Steam - Parcela 2/3",
            InstallmentInfo("Pag*Steam", 2, 3),
            YearMonth(2026, 7),
        ),
        _line(
            10,
            date(2026, 8, 1),
            1331,
            "Pag*Steam - Parcela 3/3",
            InstallmentInfo("Pag*Steam", 3, 3),
            YearMonth(2026, 6),
        ),
        _line(
            11,
            date(2026, 8, 1),
            794,
            "Pag*Steam - Parcela 3/3",
            InstallmentInfo("Pag*Steam", 3, 3),
            YearMonth(2026, 6),
        ),
        _line(12, date(2026, 8, 1), 102500, "Mp *Exemplo Loja"),
    ]
    assert all(t.competence == AUG for t in parsed.transactions)


def test_refund_is_negative(fixture_file):
    name, content = fixture_file("nubank/Nubank_2026-08-08.csv")

    refunds = [t for t in ADAPTER.parse(content, name).transactions if t.amount_cents < 0]

    assert [(t.description_raw, t.amount_cents) for t in refunds] == [
        ("Uber - NuPay", -1293),
        ("Pagamento recebido", -215040),
    ]


def test_invalid_row_becomes_error_without_dropping_file():
    content = b'date,title,amount\n2026-08-31,Forneria,"10,06"\n2026-08-30,Quebrada,"dez reais"\n'

    parsed = ADAPTER.parse(content, "Nubank_2026-09-08.csv")

    assert [t.description_raw for t in parsed.transactions] == ["Forneria"]
    assert parsed.errors == [
        RowError(3, "valor em formato brasileiro inválido: 'dez reais'"),
    ]


def test_sniff():
    assert ADAPTER.sniff(b'date,title,amount\n2026-08-31,Forneria,"10,06"')
    assert ADAPTER.sniff(b"\xef\xbb\xbfdate,title,amount\r\n")
    assert not ADAPTER.sniff(b"Data,Valor,Identificador,Descri\xc3\xa7\xc3\xa3o\n")
