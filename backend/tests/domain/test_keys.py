from datetime import date

from app.domain.competence import first_installment_month_nubank
from app.domain.installments import InstallmentLine
from app.domain.keys import (
    account_ref,
    dedup_key_external,
    dedup_key_row,
    identical_row_ordinals,
    installment_group_key,
    installment_ordinals,
)
from app.domain.months import YearMonth

NUBANK_CARD = account_ref("nubank", "cartao")


def test_account_ref():
    assert NUBANK_CARD == "nubank:cartao:"
    assert account_ref("nubank", "conta", "69815052-9") == "nubank:conta:69815052-9"


def test_dedup_key_external():
    assert dedup_key_external("nubank:conta:1", "6a98-uuid") == "ext:nubank:conta:1:6a98-uuid"


def _row_keys(rows):
    ordinals = identical_row_ordinals(rows)
    return [
        dedup_key_row(NUBANK_CARD, day, cents, title, ordinal)
        for (day, cents, title), ordinal in zip(rows, ordinals, strict=True)
    ]


def test_identical_rides_same_day_get_distinct_keys():
    rides = [
        (date(2026, 8, 24), 474, "Uber - NuPay"),
        (date(2026, 8, 24), 472, "Uber - NuPay"),
        (date(2026, 8, 24), 474, "Uber - NuPay"),
    ]

    assert identical_row_ordinals(rides) == [1, 1, 2]
    keys = _row_keys(rides)
    assert len(set(keys)) == 3


def test_row_keys_do_not_depend_on_file_order():
    rows = [
        (date(2026, 8, 24), 474, "Uber - NuPay"),
        (date(2026, 8, 24), 474, "Uber - NuPay"),
        (date(2026, 8, 31), 1006, "Forneria"),
    ]
    shuffled = [rows[2], rows[0], rows[1]]

    assert set(_row_keys(rows)) == set(_row_keys(shuffled))


def test_reimporting_same_rows_gives_same_keys():
    rows = [(date(2026, 8, 24), 474, "Uber - NuPay")] * 2
    assert _row_keys(rows) == _row_keys(list(rows))


def test_row_key_changes_with_account():
    other = dedup_key_row("itau:conta:1", date(2026, 8, 24), 474, "Uber - NuPay", 1)
    assert other != dedup_key_row(NUBANK_CARD, date(2026, 8, 24), 474, "Uber - NuPay", 1)


def _nubank_line(root, number, total, line_date, cents):
    return InstallmentLine(
        root=root,
        total=total,
        number=number,
        first_month=first_installment_month_nubank(line_date, number),
        amount_cents=cents,
        competence=YearMonth.of(line_date),
    )


def _group_keys(lines):
    ordinals = installment_ordinals(lines)
    return [
        installment_group_key(NUBANK_CARD, line.root, line.total, line.first_month, ordinal)
        for line, ordinal in zip(lines, ordinals, strict=True)
    ]


def test_same_merchant_distinct_purchases_get_distinct_groups():
    # Duas linhas "Pag*Steam - Parcela 3/3" no mesmo dia, 13,31 e 7,94: compras diferentes.
    lines = [
        _nubank_line("Pag*Steam", 3, 3, date(2026, 7, 1), 1331),
        _nubank_line("Pag*Steam", 3, 3, date(2026, 7, 1), 794),
    ]

    assert installment_ordinals(lines) == [2, 1]  # ordenadas por valor
    first, second = _group_keys(lines)
    assert first != second


def test_group_key_is_stable_across_invoices_and_cents():
    # 1/3 em julho com o resto dos centavos, 2/3 em agosto: o mesmo grupo.
    july = _group_keys([_nubank_line("Pag*Steam", 1, 3, date(2026, 7, 2), 1360)])
    august = _group_keys([_nubank_line("Pag*Steam", 2, 3, date(2026, 8, 1), 1358)])
    assert july == august


def test_group_key_differs_for_same_purchase_in_other_month():
    may = installment_group_key(NUBANK_CARD, "Latam Air*0000", 4, YearMonth(2026, 5), 1)
    june = installment_group_key(NUBANK_CARD, "Latam Air*0000", 4, YearMonth(2026, 6), 1)
    assert may != june


def test_group_key_ignores_anticipation():
    # A antecipação muda só a competência; a identidade usa root, N e mês da 1ª parcela.
    line = _nubank_line("Loja", 3, 5, date(2026, 8, 1), 1000)
    anticipated = InstallmentLine(
        root=line.root,
        total=line.total,
        number=line.number,
        first_month=line.first_month,
        amount_cents=line.amount_cents,
        competence=YearMonth(2026, 7),
    )
    assert _group_keys([line]) == _group_keys([anticipated])
