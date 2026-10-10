"""Fixtures compartilhadas dos testes de rota: cliente HTTP e carga de fixtures por importação."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.imports import get_backup
from app.ingestion.pipeline import import_file
from app.main import create_app
from app.repo.db import get_session

LOAD_NOW = datetime(2026, 10, 1, 12, 0, 0)


@pytest.fixture
def backups():
    return []


@pytest.fixture
def client(migrated_engine, backups, tmp_path):
    # `frontend_dist` inexistente: as rotas de API não dependem de `frontend/dist` buildado.
    app = create_app(frontend_dist=tmp_path / "sem-dist")

    def session_override():
        with Session(migrated_engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_backup] = lambda: backups.append
    return TestClient(app)


@pytest.fixture
def load(migrated_engine, fixture_file):
    def _load(*relatives):
        with Session(migrated_engine) as session:
            for relative in relatives:
                import_file(session, *fixture_file(relative), now=LOAD_NOW)

    return _load
