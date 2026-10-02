from datetime import date, datetime

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.repo.models import (
    Account,
    Base,
    Category,
    ImportBatch,
    Transaction,
    TransactionSource,
)

TABLES = {
    "account",
    "import_batch",
    "transactions",
    "transaction_source",
    "category",
    "merchant_memory",
    "keyword_rule",
    "installment_group_override",
    "llm_cache",
    "recurrence_override",
}
NOW = datetime(2026, 10, 1, 12, 0, 0)


def _account(**overrides) -> Account:
    return Account(**{"bank": "nubank", "kind": "cartao", "name": "Nubank cartão", **overrides})


def _batch(account: Account, sha: str) -> ImportBatch:
    return ImportBatch(
        account_id=account.id,
        filename=f"{sha}.csv",
        file_sha256=sha,
        imported_at=NOW,
        rows_total=1,
        rows_new=1,
        rows_duplicate=0,
        rows_error=0,
    )


def _transaction(account: Account, dedup_key: str, **overrides) -> Transaction:
    fields = {
        "account_id": account.id,
        "occurred_on": date(2026, 8, 24),
        "competence_month": "2026-08",
        "amount_cents": 474,
        "description_raw": "Uber - NuPay",
        "merchant_key": "UBER NUPAY",
        "normalizer_version": 1,
        "kind": "despesa",
        "category_source": "nenhuma",
        "status": "real",
        "dedup_key": dedup_key,
        "created_at": NOW,
    }
    return Transaction(**{**fields, **overrides})


@pytest.fixture
def account(session):
    account = _account()
    session.add(account)
    session.commit()
    return account


def test_upgrade_creates_all_tables(migrated_engine):
    assert TABLES <= set(inspect(migrated_engine).get_table_names())


def test_upgrade_seeds_initial_categories(session):
    names = session.scalars(select(Category.name).order_by(Category.id)).all()
    assert names == [
        "Moradia",
        "Alimentação",
        "Transporte",
        "Saúde e Bem-Estar",
        "Educação e Trabalho",
        "Lazer e Tecnologia",
        "Dívidas",
    ]
    assert all(session.scalars(select(Category.is_active)))


def test_models_match_migration(migrated_engine):
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []


def test_account_without_external_id_is_stored_as_empty_and_unique(session, account):
    assert account.external_account_id == ""

    session.add(_account())
    with pytest.raises(IntegrityError):
        session.commit()


def test_check_constraint_rejects_unknown_kind(session, account):
    session.add(_transaction(account, "row:a", kind="despesas"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_dedup_key_is_unique(session, account):
    session.add_all([_transaction(account, "row:a"), _transaction(account, "row:a")])
    with pytest.raises(IntegrityError):
        session.commit()


def test_one_transaction_per_installment_number(session, account):
    installment = {"installment_group_key": "grp:x", "installment_number": 2}
    session.add_all(
        [
            _transaction(account, "row:a", **installment),
            _transaction(account, "proj:grp:x:2", status="projetada", **installment),
        ]
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_transactions_without_installment_do_not_collide(session, account):
    session.add_all([_transaction(account, "row:a"), _transaction(account, "row:b")])
    session.commit()


def test_deleting_batch_cascades_sources_and_keeps_shared_transaction(session, account):
    first, second = _batch(account, "a"), _batch(account, "b")
    session.add_all([first, second])
    session.flush()
    shared = _transaction(account, "row:a", import_batch_id=first.id)
    session.add(shared)
    session.flush()
    session.add_all(
        [
            TransactionSource(transaction_id=shared.id, import_batch_id=first.id),
            TransactionSource(transaction_id=shared.id, import_batch_id=second.id),
        ]
    )
    session.commit()

    session.delete(first)
    session.commit()
    session.expire_all()

    sources = session.scalars(select(TransactionSource.import_batch_id)).all()
    assert sources == [second.id]
    assert session.get(Transaction, shared.id).import_batch_id is None


def test_downgrade_removes_everything(alembic_config, migrated_engine):
    command.downgrade(alembic_config, "base")

    assert set(inspect(migrated_engine).get_table_names()) == {"alembic_version"}
