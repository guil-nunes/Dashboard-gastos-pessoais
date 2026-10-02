"""Importação de ponta a ponta contra SQLite temporário (R1, R2, R4)."""

from datetime import datetime
from itertools import permutations

import pytest
from sqlalchemy import func, select

from app.ingestion.pipeline import import_file, import_files
from app.repo.models import Account, ImportBatch, Transaction, TransactionSource

NOW = datetime(2026, 10, 1, 12, 0, 0)
CARD_JUL = "nubank/Nubank_2026-08-08.csv"
CARD_AUG = "nubank/Nubank_2026-09-08.csv"
OFX_A = "nubank/NU_123456789_01SET2026_15SET2026.ofx"
OFX_B = "nubank/NU_123456789_10SET2026_24SET2026.ofx"
CSV_A = "nubank/NU_123456789_01SET2026_15SET2026.csv"

# Colunas que dependem da ordem de importação, não do conteúdo.
ORDER_DEPENDENT = {"id", "import_batch_id", "created_at", "account_id"}


def _import(session, fixture_file, *relatives):
    return [import_file(session, *fixture_file(r), now=NOW) for r in relatives]


def _count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def _transactions(session):
    """Retrato das transações sem o que depende da ordem; a conta entra pela identidade."""
    columns = [c for c in Transaction.__table__.columns if c.name not in ORDER_DEPENDENT]
    rows = session.execute(
        select(Account.bank, Account.kind, Account.external_account_id, *columns).join(
            Account, Account.id == Transaction.account_id
        )
    )
    return sorted(tuple(row) for row in rows)


def _sources(session):
    rows = session.execute(
        select(Transaction.dedup_key, ImportBatch.file_sha256)
        .join(TransactionSource, TransactionSource.transaction_id == Transaction.id)
        .join(ImportBatch, ImportBatch.id == TransactionSource.import_batch_id)
    )
    return sorted(tuple(row) for row in rows)


def test_import_creates_account_batch_and_transactions(session, fixture_file):
    (result,) = _import(session, fixture_file, CARD_AUG)

    assert (result.status, result.rows_new, result.rows_duplicate, result.rows_error) == (
        "importado",
        11,
        0,
        0,
    )
    batch = session.get(ImportBatch, result.batch_id)
    assert (batch.filename, batch.rows_total, batch.rows_new) == ("Nubank_2026-09-08.csv", 11, 11)
    account = session.scalars(select(Account)).one()
    assert (account.bank, account.kind, account.external_account_id, account.holder) == (
        "nubank",
        "cartao",
        "",
        None,
    )
    assert _count(session, Transaction) == _count(session, TransactionSource) == 11
    assert set(session.scalars(select(Transaction.status))) == {"real"}


def test_reimporting_same_file_changes_nothing(session, fixture_file):
    _import(session, fixture_file, CARD_AUG)
    before = (_transactions(session), _sources(session), _count(session, ImportBatch))

    (again,) = _import(session, fixture_file, CARD_AUG)

    assert again.status == "ja_importado"
    assert (_transactions(session), _sources(session), _count(session, ImportBatch)) == before


def test_identical_rides_on_the_same_day_are_kept(session, fixture_file):
    _import(session, fixture_file, CARD_AUG)

    rides = session.scalar(
        select(func.count()).where(
            Transaction.description_raw == "Uber - NuPay", Transaction.amount_cents == 474
        )
    )
    assert rides == 2


def test_overlapping_statements_only_add_new_rows(session, fixture_file):
    first, second = _import(session, fixture_file, OFX_A, OFX_B)

    assert (first.rows_new, first.rows_duplicate) == (6, 0)
    assert (second.rows_new, second.rows_duplicate) == (2, 2)
    assert _count(session, Transaction) == 8
    # As duas linhas sobrepostas têm origem nos dois lotes.
    shared = [key for key, _ in _sources(session) if key.endswith(("0005", "0006"))]
    assert len(shared) == 4


def test_ofx_and_csv_of_same_period_do_not_duplicate(session, fixture_file):
    _, from_csv = _import(session, fixture_file, OFX_A, CSV_A)

    assert (from_csv.status, from_csv.rows_new, from_csv.rows_duplicate) == ("importado", 0, 6)
    assert _count(session, Account) == 1


def test_import_order_does_not_change_the_database(new_session, fixture_file):
    files = [CARD_JUL, CARD_AUG, OFX_A, OFX_B]
    baseline = None
    for order in permutations(files):
        session = new_session()
        results = _import(session, fixture_file, *order)
        assert {r.status for r in results} == {"importado"}
        snapshot = (_transactions(session), _sources(session))
        if baseline is None:
            baseline = snapshot
        assert snapshot == baseline, order


def test_statement_union_equals_separate_statements(new_session, fixture_file):
    separate = new_session()
    _import(separate, fixture_file, OFX_A, OFX_B)

    # Um único extrato de 01 a 24/09: as transações de A mais as que só existem em B.
    name_a, content_a = fixture_file(OFX_A)
    _, content_b = fixture_file(OFX_B)
    text_b = content_b.decode()
    only_in_b = text_b[text_b.index("<STMTTRN>", text_b.index("-000000000007") - 300) :]
    only_in_b = only_in_b[: only_in_b.index("</BANKTRANLIST>")]
    text_a = content_a.decode()
    union = text_a.replace("</BANKTRANLIST>", only_in_b + "</BANKTRANLIST>").encode()
    together = new_session()
    (result,) = [import_file(together, "NU_123456789_01SET2026_24SET2026.ofx", union, NOW)]

    assert result.rows_new == 8
    assert _transactions(together) == _transactions(separate)


def test_invoice_payment_is_not_an_expense(session, fixture_file):
    """R4: o pagamento da fatura (conta) e o pagamento recebido (cartão) não somam despesa."""
    _import(session, fixture_file, CARD_JUL, CARD_AUG, OFX_A, OFX_B)

    def expenses(month):
        return session.scalar(
            select(func.sum(Transaction.amount_cents)).where(
                Transaction.competence_month == month,
                Transaction.kind == "despesa",
                Transaction.status == "real",
            )
        )

    # Cartão em agosto: só as compras e o IOF, sem o "Pagamento recebido" (-3.317,60).
    assert expenses("2026-08") == 210283
    # Conta em setembro: Pix enviado e compras no débito, sem o "Pagamento de fatura" (3.317,60).
    assert expenses("2026-09") == 1100 + 1007 + 8990 + 4500 + 3250
    payments = session.scalars(
        select(Transaction.ignore_reason).where(
            Transaction.description_raw.in_(["Pagamento de fatura", "Pagamento recebido"])
        )
    ).all()
    assert payments == ["pagamento_fatura"] * 3  # 2 no cartão (jul e ago) + 1 na conta


def test_failed_file_writes_nothing(session):
    first = b'date,title,amount\n2026-08-01,Loja - Parcela 2/3,"10,00"\n'
    # Outra fatura com a mesma parcela 2/3 do mesmo grupo e outro valor: viola
    # UNIQUE(installment_group_key, installment_number) depois de gravar a primeira linha.
    second = (
        b'date,title,amount\n2026-08-02,Outra compra,"5,00"\n'
        b'2026-08-01,Loja - Parcela 2/3,"10,01"\n'
    )
    import_file(session, "Nubank_2026-09-08.csv", first, NOW)

    result = import_file(session, "Nubank_2026-09-08 (1).csv", second, NOW)

    assert result.status == "erro"
    assert "UNIQUE" in result.message
    assert _count(session, ImportBatch) == 1
    assert _count(session, Transaction) == 1
    assert session.scalar(select(Transaction.description_raw)) == "Loja - Parcela 2/3"


def test_rejected_file_writes_nothing(session):
    result = import_file(session, "planilha.csv", b"nome,valor\nmercado,10\n", NOW)

    assert result.status == "rejeitado"
    assert result.message == "formato de arquivo não reconhecido"
    assert _count(session, ImportBatch) == _count(session, Account) == 0


def test_row_errors_are_counted(session):
    content = b'date,title,amount\n2026-08-31,Forneria,"10,06"\n2026-08-30,Quebrada,"x"\n'

    result = import_file(session, "Nubank_2026-09-08.csv", content, NOW)

    assert (result.status, result.rows_new, result.rows_error) == ("importado", 1, 1)
    assert result.errors[0].line_no == 3
    assert session.get(ImportBatch, result.batch_id).rows_total == 2


ITAU_A = "itau/itau_extrato_A.pdf"
ITAU_B = "itau/itau_extrato_B.pdf"
ITAU_CARD = "itau/itau_fatura_2026-01.pdf"


def test_overlapping_itau_statements_only_add_new_rows(session, fixture_file):
    first, second = _import(session, fixture_file, ITAU_A, ITAU_B)

    assert (first.rows_new, first.rows_duplicate) == (9, 0)
    assert (second.rows_new, second.rows_duplicate) == (2, 5)
    # As duas corridas idênticas de 18/09 continuam duas.
    rides = session.scalar(
        select(func.count()).where(
            Transaction.description_raw == "ON Uber UBER 18/09", Transaction.amount_cents == 894
        )
    )
    assert rides == 2


def test_itau_credit_is_income(session, fixture_file):
    _import(session, fixture_file, ITAU_A)

    kinds = session.execute(
        select(Transaction.kind, Transaction.ignore_reason).where(
            Transaction.description_raw == "REND PAGO APLIC AUT MAIS"
        )
    ).all()
    assert kinds == [("ignorar", "receita")]


def test_itau_import_order_does_not_change_the_database(new_session, fixture_file):
    baseline = None
    for order in permutations([ITAU_A, ITAU_B, ITAU_CARD]):
        session = new_session()
        results = _import(session, fixture_file, *order)
        assert {r.status for r in results} == {"importado"}
        snapshot = (_transactions(session), _sources(session))
        if baseline is None:
            baseline = snapshot
        assert snapshot == baseline, order


def test_invoice_with_wrong_total_writes_nothing(session, fixture_file):
    (result,) = _import(session, fixture_file, "itau/itau_fatura_total_errado.pdf")

    assert result.status == "rejeitado"
    assert "difere do total" in result.message
    assert _count(session, ImportBatch) == _count(session, Transaction) == 0


def test_bank_category_is_stored(session, fixture_file):
    _import(session, fixture_file, ITAU_CARD)

    category = session.scalar(
        select(Transaction.bank_category).where(Transaction.description_raw == "NETFLIX.COM")
    )
    assert category == "TURISMO E ENTRETENIM"


@pytest.mark.parametrize("count", [1, 3])
def test_import_files_backs_up_once(session, fixture_file, count):
    calls = []
    files = [fixture_file(r) for r in [CARD_JUL, CARD_AUG, OFX_A][:count]]

    results = import_files(session, files, NOW, backup=lambda: calls.append(1))

    assert calls == [1]
    assert [r.status for r in results] == ["importado"] * count
