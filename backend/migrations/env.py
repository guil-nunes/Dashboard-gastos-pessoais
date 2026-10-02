from logging.config import fileConfig

from alembic import context

from app.config import get_settings
from app.repo.db import create_sqlite_engine, database_url
from app.repo.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    path = get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return database_url(path)


def run_migrations() -> None:
    engine = create_sqlite_engine(_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            render_as_batch=True,  # o SQLite só altera tabelas recriando-as
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Modo offline não suportado: rode as migrações contra o banco.")
run_migrations()
