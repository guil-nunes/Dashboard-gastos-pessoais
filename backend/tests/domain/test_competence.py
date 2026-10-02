from datetime import date

from app.domain.competence import (
    apply_anticipation,
    competence_by_line_date,
    first_installment_month_itau,
    first_installment_month_nubank,
    itau_card_competence,
)
from app.domain.installments import InstallmentInfo, InstallmentLine
from app.domain.keys import installment_ordinals
from app.domain.months import YearMonth


def test_competence_by_line_date():
    assert competence_by_line_date(date(2026, 8, 31)) == YearMonth(2026, 8)


def test_nubank_first_month_is_stable_across_invoices():
    # Pag*Steam 1/3 na fatura de julho (data da compra) e 2/3 na de agosto (abertura do ciclo).
    july = first_installment_month_nubank(date(2026, 7, 2), 1)
    august = first_installment_month_nubank(date(2026, 8, 1), 2)
    assert july == august == YearMonth(2026, 7)


def test_nubank_first_month_of_late_installment():
    # Latam Air 4/4 em 2026-08-01 → 1ª parcela em maio.
    assert first_installment_month_nubank(date(2026, 8, 1), 4) == YearMonth(2026, 5)


def test_itau_installment_competence_from_purchase_date():
    # MERCADOLIVRE 09/12 comprado em 15/09/2024 → maio/2025.
    info = InstallmentInfo("MERCADOLIVRE*55253", 9, 12)
    assert itau_card_competence(date(2024, 9, 15), info) == YearMonth(2025, 5)
    assert first_installment_month_itau(date(2024, 9, 15)) == YearMonth(2024, 9)


def test_itau_single_payment_competence():
    assert itau_card_competence(date(2025, 5, 27), None) == YearMonth(2025, 5)


def _itau_line(root, number, total, purchase, cents):
    info = InstallmentInfo(root, number, total)
    return InstallmentLine(
        root=root,
        total=total,
        number=number,
        first_month=first_installment_month_itau(purchase),
        amount_cents=cents,
        competence=itau_card_competence(purchase, info),
    )


def test_anticipation_moves_all_installments_to_earliest():
    # ENJOEI: 1/4…4/4 cobradas na mesma fatura, compra em 14/05/2025 (cancelamento).
    lines = [_itau_line("PG *ENJOEI.COM.BR", n, 4, date(2025, 5, 14), 12346) for n in (2, 3, 4, 1)]

    adjusted = apply_anticipation(lines, installment_ordinals(lines))

    assert adjusted == [YearMonth(2025, 5)] * 4


def test_anticipation_without_first_installment():
    # SPECIALSTY: 2/5…5/5 antecipadas, compra em 26/04/2025 → todas na competência da 2/5 (maio).
    lines = [_itau_line("SHOPEE *SPECIALSTY", n, 5, date(2025, 4, 26), 1067) for n in (3, 4, 5, 2)]

    adjusted = apply_anticipation(lines, installment_ordinals(lines))

    assert adjusted == [YearMonth(2025, 5)] * 4


def test_single_installment_per_group_is_not_changed():
    lines = [
        _itau_line("MERCADOLIVRE*55253", 9, 12, date(2024, 9, 15), 1071),
        _itau_line("SHOPEE *RODRIMODAS", 7, 8, date(2024, 11, 12), 559),
    ]

    adjusted = apply_anticipation(lines, installment_ordinals(lines))

    assert adjusted == [YearMonth(2025, 5), YearMonth(2025, 5)]
