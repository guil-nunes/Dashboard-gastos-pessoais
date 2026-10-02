"""Engine e sessão SQLAlchemy síncronas do banco SQLite local."""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def database_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def create_sqlite_engine(url: str) -> Engine:
    engine = create_engine(url)
    event.listen(engine, "connect", _enable_foreign_keys)
    return engine


def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    # O SQLite ignora FKs (e o ON DELETE CASCADE de transaction_source) sem este pragma.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@lru_cache
def get_engine() -> Engine:
    path = get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_sqlite_engine(database_url(path))


def get_session() -> Iterator[Session]:
    """Dependência FastAPI: uma sessão por requisição."""
    with sessionmaker(bind=get_engine())() as session:
        yield session
