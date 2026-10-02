import sqlite3
from datetime import datetime, timedelta

import pytest

from app.repo.backup import backup_database

NOW = datetime(2026, 10, 1, 22, 0, 0)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "gastos.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE category (name TEXT)")
    connection.execute("INSERT INTO category VALUES ('Moradia')")
    connection.commit()
    connection.close()
    return path


def test_backup_is_a_readable_copy(db_path, tmp_path):
    backups = tmp_path / "backups"

    target = backup_database(db_path, backups, keep=10, now=NOW)

    assert target == backups / "2026-10-01_220000.db"
    connection = sqlite3.connect(target)
    assert connection.execute("SELECT name FROM category").fetchall() == [("Moradia",)]
    connection.close()


def test_missing_database_is_not_backed_up(tmp_path):
    backups = tmp_path / "backups"

    assert backup_database(tmp_path / "missing.db", backups, keep=10, now=NOW) is None
    assert not backups.exists()


def test_keeps_only_the_newest_backups(db_path, tmp_path):
    backups = tmp_path / "backups"

    for minute in range(12):
        backup_database(db_path, backups, keep=10, now=NOW + timedelta(minutes=minute))

    names = sorted(path.name for path in backups.glob("*.db"))
    assert len(names) == 10
    assert names[0] == "2026-10-01_220200.db"
    assert names[-1] == "2026-10-01_221100.db"


def test_two_backups_in_the_same_second_do_not_overwrite(db_path, tmp_path):
    backups = tmp_path / "backups"

    first = backup_database(db_path, backups, keep=10, now=NOW)
    second = backup_database(db_path, backups, keep=10, now=NOW)

    assert first.name == "2026-10-01_220000.db"
    assert second.name == "2026-10-01_220000_1.db"
