from contextlib import ExitStack
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.repo.db import create_sqlite_engine, database_url

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_file():
    """(nome, bytes) de um arquivo anonimizado em tests/fixtures/."""

    def load(relative: str) -> tuple[str, bytes]:
        path = FIXTURES / relative
        return path.name, path.read_bytes()

    return load


def _alembic_config(db_path: Path) -> Config:
    """Alembic apontando para um SQLite temporário; nunca o banco local do usuário."""
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url(db_path))
    return config


@pytest.fixture
def alembic_config(tmp_path):
    return _alembic_config(tmp_path / "test.db")


@pytest.fixture
def migrated_engine(alembic_config):
    command.upgrade(alembic_config, "head")
    engine = create_sqlite_engine(alembic_config.get_main_option("sqlalchemy.url"))
    yield engine
    engine.dispose()


@pytest.fixture
def session(migrated_engine):
    with Session(migrated_engine) as session:
        yield session


@pytest.fixture
def new_session(tmp_path):
    """Fábrica de sessões, cada uma em um banco migrado novo (para comparar bancos)."""
    with ExitStack() as stack:
        counter = 0

        def make() -> Session:
            nonlocal counter
            counter += 1
            config = _alembic_config(tmp_path / f"db{counter}.db")
            command.upgrade(config, "head")
            engine = create_sqlite_engine(config.get_main_option("sqlalchemy.url"))
            stack.callback(engine.dispose)
            return stack.enter_context(Session(engine))

        yield make
