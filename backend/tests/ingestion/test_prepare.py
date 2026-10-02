from datetime import date

import pytest

from app.domain.competence import first_installment_month_itau, itau_card_competence
from app.domain.installments import InstallmentInfo
from app.domain.months import YearMonth
from app.ingestion.prepare import _installment_groups, prepare
from app.ingestion.types import RawTransaction, RejectedFile


@pytest.fixture
def august(fixture_file):
    return prepare(*fixture_file("nubank/Nubank_2026-09-08.csv"))


@pytest.fixture
def july(fixture_file):
    return prepare(*fixture_file("nubank/Nubank_2026-08-08.csv"))


def _by_description(prepared, description):
    return [t for t in prepared.transactions if t.description_raw == description]


def test_identical_rides_get_distinct_keys(august):
    rides = _by_description(august, "Uber - NuPay")

    assert len(rides) == 2
    assert rides[0].dedup_key != rides[1].dedup_key


def test_same_file_always_gives_same_keys(fixture_file):
    content = fixture_file("nubank/Nubank_2026-09-08.csv")
    assert prepare(*content) == prepare(*content)


def test_card_rows_without_id_use_row_hash(august):
    assert all(t.dedup_key.startswith("row:") for t in august.transactions)


def test_ofx_rows_use_external_id(fixture_file):
    prepared = prepare(*fixture_file("nubank/NU_123456789_01SET2026_15SET2026.ofx"))
    assert prepared.transactions[0].dedup_key == (
        "ext:nubank:conta:12345678-9:00000000-0000-4000-8000-000000000001"
    )


def test_two_steam_purchases_are_distinct_groups(august):
    first, second = _by_description(august, "Pag*Steam - Parcela 3/3")
    assert first.installment_group_key != second.installment_group_key


def test_installment_groups_continue_across_invoices(july, august):
    def groups(prepared, description):
        return {
            t.amount_cents: t.installment_group_key for t in _by_description(prepared, description)
        }

    # 2/3 em julho → 3/3 em agosto, mesmos valores (7,94 e 13,31): mesmos grupos.
    assert groups(july, "Pag*Steam - Parcela 2/3") == groups(august, "Pag*Steam - Parcela 3/3")
    # 1/3 em julho (13,60) e 2/3 em agosto (13,58, centavos diferentes): mesmo grupo.
    (july_first,) = _by_description(july, "Pag*Steam - Parcela 1/3")
    (august_second,) = [
        t for t in _by_description(august, "Pag*Steam - Parcela 2/3") if t.amount_cents == 1358
    ]
    assert july_first.installment_group_key == august_second.installment_group_key
    assert (august_second.installment_number, august_second.installment_total) == (2, 3)


def test_iof_shares_merchant_key_with_purchase(august):
    (purchase,) = _by_description(august, "Anthropic* Claude Sub")
    (iof,) = _by_description(august, 'IOF de "Anthropic* Claude Sub"')

    assert iof.merchant_key == purchase.merchant_key
    assert iof.kind == "despesa"


def test_refund_is_negative_expense(july):
    (refund,) = [t for t in _by_description(july, "Uber - NuPay") if t.amount_cents < 0]
    assert (refund.kind, refund.amount_cents) == ("despesa", -1293)


def test_card_payment_is_ignored(august):
    (payment,) = _by_description(august, "Pagamento recebido")
    assert (payment.kind, payment.ignore_reason) == ("ignorar", "pagamento_fatura")


def test_normalizer_version_is_recorded(august):
    assert {t.normalizer_version for t in august.transactions} == {1}


def test_anticipation_is_applied_per_group():
    # Linhas no estilo do Itaú (data da compra em toda parcela): 2/4…4/4 na mesma fatura
    # recebem a competência da 2/4; a chave do grupo não muda (Q14). Golden real na 1.5.
    purchase = date(2025, 4, 26)
    raws = [
        RawTransaction(
            line_no=n,
            occurred_on=purchase,
            amount_cents=1067,
            description_raw=f"SHOPEE *LOJA 0{n}/04",
            competence=itau_card_competence(purchase, InstallmentInfo("SHOPEE *LOJA", n, 4)),
            installment=InstallmentInfo("SHOPEE *LOJA", n, 4),
            first_month=first_installment_month_itau(purchase),
        )
        for n in (2, 3, 4)
    ]

    groups, competences = _installment_groups("itau:cartao:", raws)

    assert set(competences.values()) == {YearMonth(2025, 5)}
    assert len(set(groups.values())) == 1


def test_unknown_file_is_rejected():
    with pytest.raises(RejectedFile):
        prepare("planilha.csv", b"nome,valor\n")
