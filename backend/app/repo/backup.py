"""Backup do banco antes de cada importação (spec §7.5): `VACUUM INTO`, mantendo as N últimas."""

import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import get_settings

NAME_FORMAT = "%Y-%m-%d_%H%M%S"


def backup_with_settings(now: datetime) -> Path | None:
    """Backup do banco configurado (`DATABASE_PATH`, `BACKUPS_DIR`, `BACKUPS_KEEP`)."""
    settings = get_settings()
    return backup_database(settings.database_path, settings.backups_dir, settings.backups_keep, now)


def backup_database(db_path: Path, backups_dir: Path, keep: int, now: datetime) -> Path | None:
    """Copia o banco para `backups_dir/AAAA-MM-DD_HHMMSS.db`; sem banco ainda, não faz nada."""
    if not db_path.exists():
        return None

    backups_dir.mkdir(parents=True, exist_ok=True)
    target = _free_name(backups_dir, now.strftime(NAME_FORMAT))

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("VACUUM INTO ?", (str(target),))
    finally:
        connection.close()

    _rotate(backups_dir, keep)
    return target


def _free_name(backups_dir: Path, stem: str) -> Path:
    # Dois backups no mesmo segundo: 2026-10-01_220000.db, depois 2026-10-01_220000_1.db.
    target = backups_dir / f"{stem}.db"
    suffix = 0
    while target.exists():
        suffix += 1
        target = backups_dir / f"{stem}_{suffix}.db"
    return target


def _rotate(backups_dir: Path, keep: int) -> None:
    # O nome ordena cronologicamente; o sufixo "_1" vem depois do nome sem sufixo.
    backups = sorted(backups_dir.glob("*.db"), key=lambda path: path.stem)
    for old in backups[: max(len(backups) - keep, 0)]:
        old.unlink()
