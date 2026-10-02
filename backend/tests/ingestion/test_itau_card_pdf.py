from datetime import date

import pytest

from app.domain.installments import InstallmentInfo
from app.domain.months import YearMonth
from app.ingestion.adapters.itau_card_pdf import ItauCardPdf
from app.ingestion.prepare import prepare
from app.ingestion.types import AccountInfo, RejectedFile

ADAPTER = ItauCardPdf()
INVOICE = "itau/itau_fatura_2026-01.pdf"
DEC, JAN = YearMonth(2025, 12), YearMonth(2026, 1)


def test_golden_invoice(fixture_file):
    name, content = fixture_file(INVOICE)

    parsed = ADAPTER.parse(content, name)

    assert parsed.account == AccountInfo("itau", "cartao", "", "Itaú cartão")
    assert parsed.errors == []
    assert [
        (t.occurred_on, t.amount_cents, t.description_raw, t.competence, t.bank_category)
        for t in parsed.transactions
    ] == [
        # Página 2, coluna esquerda.
        (date(2025, 5, 15), 1071, "MERCADOLIVRE*5525309/12", JAN, "VESTUÁRIO"),
        (date(2025, 12, 15), 12000, "LOJA EXEMPLO", DEC, "DIVERSOS"),
        (date(2025, 12, 14), 12346, "PG *ENJOEI.COM.BR 01/04", DEC, "DIVERSOS"),
        (date(2025, 12, 14), 12346, "PG *ENJOEI.COM.BR 02/04", JAN, "DIVERSOS"),
        # Página 2, coluna direita.
        (date(2025, 12, 14), 12346, "PG *ENJOEI.COM.BR 03/04", YearMonth(2026, 2), "DIVERSOS"),
        (date(2025, 12, 14), 12346, "PG *ENJOEI.COM.BR 04/04", YearMonth(2026, 3), "DIVERSOS"),
        (date(2025, 12, 14), -49384, "PG *ENJOEI.COM.BR ATIV", DEC, "DIVERSOS"),
        (date(2025, 11, 12), -6, "RafolinoPresen", YearMonth(2025, 11), "VESTUÁRIO"),
        # Página 3, coluna esquerda (o "L" do total, na mesma altura, não cola na linha).
        (date(2025, 11, 26), 1067, "SHOPEE *SPECIALSTY03/05", JAN, "VESTUÁRIO"),
        (date(2025, 11, 26), 1067, "SHOPEE *SPECIALSTY04/05", YearMonth(2026, 2), "VESTUÁRIO"),
        (date(2025, 11, 26), 1067, "SHOPEE *SPECIALSTY05/05", YearMonth(2026, 3), "VESTUÁRIO"),
        (date(2026, 1, 2), 5990, "NETFLIX.COM", JAN, "TURISMO E ENTRETENIM"),
        (date(2025, 11, 26), 1067, "SHOPEE *SPECIALSTY02/05", DEC, "VESTUÁRIO"),
        # Página 3, coluna direita: produtos e serviços (sem linha de categoria).
        (date(2025, 12, 7), 1325, "ANUIDADE DIFERENCI02/12", JAN, None),
    ]


def test_installments_carry_purchase_month(fixture_file):
    parsed = ADAPTER.parse(*reversed(fixture_file(INVOICE)))

    mercado = parsed.transactions[0]
    assert mercado.installment == InstallmentInfo("MERCADOLIVRE*55253", 9, 12)
    assert mercado.first_month == YearMonth(2025, 5)


def test_next_invoices_section_is_ignored(fixture_file):
    parsed = ADAPTER.parse(*reversed(fixture_file(INVOICE)))
    assert not any("5525310" in t.description_raw for t in parsed.transactions)


def test_total_mismatch_rejects_the_invoice(fixture_file):
    name, content = fixture_file("itau/itau_fatura_total_errado.pdf")

    with pytest.raises(RejectedFile, match=r"soma lida R\$ 246,48 difere do total .* 246,49"):
        ADAPTER.parse(content, name)


def test_anticipation_and_refund_land_in_the_same_month(fixture_file):
    prepared = prepare(*fixture_file(INVOICE))

    enjoei = [t for t in prepared.transactions if "ENJOEI" in t.description_raw]
    assert {t.competence_month for t in enjoei} == {"2025-12"}
    assert sum(t.amount_cents for t in enjoei) == 0
    assert len({t.installment_group_key for t in enjoei if t.installment_number}) == 1

    special = [t for t in prepared.transactions if "SPECIALSTY" in t.description_raw]
    assert {t.competence_month for t in special} == {"2025-12"}  # competência da 2/5
    assert len({t.installment_group_key for t in special}) == 1


def test_sniff_text():
    assert ADAPTER.sniff_text("Resumo da fatura em R$\nBanco Itaú S.A. 341-7")
    assert not ADAPTER.sniff_text("extrato conta / lançamentos")
