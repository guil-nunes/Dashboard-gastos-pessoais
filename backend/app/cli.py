"""Comandos: `python -m app.cli serve` (uso real) e `python -m app.cli renormalize`."""

import argparse
from datetime import datetime

from sqlalchemy.orm import Session

from app.ingestion.renormalize import renormalize
from app.repo.backup import backup_with_settings
from app.repo.db import get_engine


def serve(host: str, port: int) -> int:
    """Migra o banco para a versão atual e sobe a API servindo o `frontend/dist` (spec §7.5)."""
    import uvicorn
    from alembic import command
    from alembic.config import Config

    from app.config import BACKEND_DIR, get_settings

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(config, "head")

    dist = get_settings().frontend_dist
    if not (dist / "index.html").is_file():
        print(f"Aviso: {dist} não existe; rode `npm run build` em frontend/ para ver a interface.")
    uvicorn.run("app.main:app", host=host, port=port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    serve_parser = commands.add_parser("serve", help="migra o banco e sobe a API com a interface")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    commands.add_parser(
        "renormalize", help="recalcula merchant_key após mudança do normalizador (R5)"
    )
    args = parser.parse_args(argv)

    if args.command == "serve":
        return serve(args.host, args.port)

    backup_with_settings(datetime.now())
    with Session(get_engine()) as session:
        try:
            result = renormalize(session)
            session.commit()
        except Exception:
            session.rollback()
            raise
    print(
        f"{result.transactions} transações recalculadas, {result.keys_changed} chaves alteradas, "
        f"{result.reclassified} reclassificadas"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
