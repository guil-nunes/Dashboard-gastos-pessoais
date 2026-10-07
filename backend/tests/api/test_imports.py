"""Contrato HTTP de /imports e /accounts contra SQLite temporário (spec §7.4)."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.imports import get_backup
from app.ingestion.pipeline import import_file
from app.main import create_app
from app.repo.db import get_session
from app.repo.models import Transaction

CARD_AUG = "nubank/Nubank_2026-09-08.csv"
OFX_A = "nubank/NU_123456789_01SET2026_15SET2026.ofx"
OFX_B = "nubank/NU_123456789_10SET2026_24SET2026.ofx"


@pytest.fixture
def backups():
    return []


@pytest.fixture
def client(migrated_engine, backups):
    app = create_app()

    def session_override():
        with Session(migrated_engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_backup] = lambda: backups.append
    return TestClient(app)


def _upload(client, fixture_file, *relatives):
    files = [("files", (*fixture_file(r), "application/octet-stream")) for r in relatives]
    return client.post("/api/imports", files=files)


def _snapshot(session):
    """Transações sem o que depende da ordem de importação."""
    skip = {"id", "import_batch_id", "created_at", "account_id"}
    columns = [c for c in Transaction.__table__.columns if c.name not in skip]
    return sorted(tuple(r) for r in session.execute(select(*columns)))


def test_post_returns_result_per_file_even_with_rejected(client, fixture_file, backups):
    files = [
        ("files", (*fixture_file(CARD_AUG), "text/csv")),
        ("files", ("planilha.csv", b"nome,valor\nmercado,10\n", "text/csv")),
    ]

    response = client.post("/api/imports", files=files)

    assert response.status_code == 200
    ok, rejected = response.json()
    assert (ok["status"], ok["rows_new"], ok["needs_holder"]) == ("importado", 11, True)
    assert ok["account_id"] is not None
    assert (rejected["status"], rejected["batch_id"]) == ("rejeitado", None)
    assert len(backups) == 1


def test_reimport_is_reported_as_already_imported(client, fixture_file):
    _upload(client, fixture_file, CARD_AUG)

    (again,) = _upload(client, fixture_file, CARD_AUG).json()

    assert again["status"] == "ja_importado"
    assert len(client.get("/api/imports").json()) == 1


def test_patch_holder_clears_needs_holder(client, fixture_file):
    (first,) = _upload(client, fixture_file, CARD_AUG).json()

    response = client.patch(f"/api/accounts/{first['account_id']}", json={"holder": " Maria "})

    assert response.status_code == 200
    assert response.json()["holder"] == "Maria"
    (again,) = _upload(client, fixture_file, CARD_AUG).json()
    assert again["needs_holder"] is False
    assert client.get("/api/imports").json()[0]["holder"] == "Maria"


def test_patch_holder_validates_and_404s(client):
    assert client.patch("/api/accounts/999", json={"holder": "Ana"}).status_code == 404
    assert client.patch("/api/accounts/1", json={"holder": "  "}).status_code == 422


def test_delete_unknown_batch_is_404(client):
    assert client.delete("/api/imports/999").status_code == 404


@pytest.mark.parametrize("undone, kept", [(0, OFX_B), (1, OFX_A)])
def test_undo_with_overlapping_batches_equals_importing_only_the_other(
    client, fixture_file, migrated_engine, new_session, undone, kept
):
    results = [_upload(client, fixture_file, f).json()[0] for f in (OFX_A, OFX_B)]

    response = client.delete(f"/api/imports/{results[undone]['batch_id']}")

    assert response.status_code == 204
    expected = new_session()
    import_file(expected, *fixture_file(kept), now=datetime(2026, 10, 1))
    with Session(migrated_engine) as session:
        assert _snapshot(session) == _snapshot(expected)
    assert [b["id"] for b in client.get("/api/imports").json()] == [results[1 - undone]["batch_id"]]


def test_undo_then_reimport_works_and_keeps_account(client, fixture_file, migrated_engine):
    (first,) = _upload(client, fixture_file, CARD_AUG).json()
    client.patch(f"/api/accounts/{first['account_id']}", json={"holder": "Ana"})

    assert client.delete(f"/api/imports/{first['batch_id']}").status_code == 204
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(Transaction)) == 0

    (again,) = _upload(client, fixture_file, CARD_AUG).json()
    assert (again["status"], again["rows_new"], again["needs_holder"]) == ("importado", 11, False)
