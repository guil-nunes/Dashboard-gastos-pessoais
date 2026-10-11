"""Recorrências (R9) e piso do mês seguinte (R12), com lançamentos inseridos direto no banco."""

from datetime import date, datetime
from urllib.parse import quote

import pytest
from sqlalchemy.orm import Session

from app.repo.models import Account, Transaction

NETFLIX = ("NETFLIX", 5590)
GYM = ("ACADEMIA", 12000)


@pytest.fixture
def db(migrated_engine):
    with Session(migrated_engine) as session:
        session.add(Account(bank="nubank", kind="cartao", name="Cartão"))
        session.commit()
        yield session


def _add(db, key, cents, on, *, raw=None, month=None, **extra):
    account_id = db.query(Account).one().id
    seq = db.query(Transaction).count()
    db.add(
        Transaction(
            account_id=account_id,
            occurred_on=on,
            competence_month=month or f"{on.year}-{on.month:02d}",
            amount_cents=cents,
            description_raw=raw or key.title(),
            merchant_key=key,
            normalizer_version=1,
            kind=extra.pop("kind", "despesa"),
            category_source="nenhuma",
            status=extra.pop("status", "real"),
            dedup_key=f"test:{seq}",
            created_at=datetime(2026, 10, 1),
            **extra,
        )
    )
    db.commit()


def _monthly(db, key, cents, months, day=10, **kw):
    for month in months:
        _add(db, key, cents, date(2026, month, day), **kw)


def _recurrences(client):
    response = client.get("/api/recurrences")
    assert response.status_code == 200
    return response.json()


def _floor(client, month):
    response = client.get("/api/dashboard/floor", params={"month": month})
    assert response.status_code == 200
    return response.json()


def test_empty_database_has_no_recurrences_and_zero_floor(client):
    assert _recurrences(client) == []
    floor = _floor(client, "2026-08")
    assert (floor["target_month"], floor["total_cents"]) == ("2026-09", 0)
    assert floor["installments"] == floor["recurrences"] == []


def test_monthly_series_is_listed_with_average_last_and_months(client, db):
    for month, cents in ((6, 5500), (7, 5600), (8, 5700)):
        _add(db, "NETFLIX", cents, date(2026, month, 10))

    [item] = _recurrences(client)

    assert item["merchant_key"] == "NETFLIX"
    assert (item["average_cents"], item["last_cents"], item["months_count"]) == (5600, 5700, 3)
    assert (item["last_on"], item["dismissed"]) == ("2026-08-10", False)


def test_two_occurrences_are_not_recurring(client, db):
    _monthly(db, "NETFLIX", 5590, [7, 8])

    assert _recurrences(client) == []


def test_installments_projected_ignored_and_refunds_are_excluded(client, db):
    _monthly(db, "PARCELADO", 3000, [6, 7, 8])
    for n, month in enumerate((6, 7, 8), start=1):
        _add(
            db,
            "LOJA",
            3000,
            date(2026, month, 10),
            installment_group_key="loja",
            installment_number=n,
            installment_total=10,
        )
    _monthly(db, "PROJETADA", 3000, [6, 7, 8], status="projetada")
    _monthly(db, "PIX AMIGO", 3000, [6, 7, 8], kind="ignorar", ignore_reason="receita")

    keys = [i["merchant_key"] for i in _recurrences(client)]

    assert keys == ["PARCELADO"]  # só a série sem número de parcela e do tipo despesa


def test_iof_is_added_to_the_purchase(client, db):
    for month in (6, 7, 8):
        _add(db, "CLAUDE", 10000, date(2026, month, 15), raw="Claude Sub")
        _add(db, "CLAUDE", 400, date(2026, month, 15), raw='IOF de "Claude Sub"')

    [item] = _recurrences(client)

    assert (item["last_cents"], item["average_cents"]) == (10400, 10400)


def test_patch_marks_not_recurring_and_can_be_undone(client, db):
    _monthly(db, "NETFLIX", 5590, [6, 7, 8])
    path = f"/api/recurrences/{quote('NETFLIX', safe='')}"

    assert client.patch(path, json={"is_recurring": False}).status_code == 200
    assert _recurrences(client)[0]["dismissed"] is True
    assert _floor(client, "2026-08")["recurrences"] == []

    assert client.patch(path, json={"is_recurring": True}).status_code == 200
    assert _recurrences(client)[0]["dismissed"] is False


def test_patch_unknown_merchant_is_404(client):
    response = client.patch("/api/recurrences/NADA", json={"is_recurring": False})

    assert response.status_code == 404


def test_floor_sums_recurring_last_value_and_projected_installments(client, db):
    _monthly(db, "NETFLIX", 5590, [6, 7, 8])
    _add(
        db,
        "LOJA",
        2500,
        date(2026, 9, 5),
        status="projetada",
        month="2026-09",
        installment_group_key="loja",
        installment_number=4,
        installment_total=6,
        raw="Loja",
    )
    _add(
        db,
        "LOJA",
        2500,
        date(2026, 10, 5),
        status="projetada",
        month="2026-10",
        installment_group_key="loja",
        installment_number=5,
        installment_total=6,
        raw="Loja",
    )

    floor = _floor(client, "2026-08")

    assert floor["target_month"] == "2026-09"
    assert (floor["installments_cents"], floor["recurrences_cents"]) == (2500, 5590)
    assert floor["total_cents"] == 8090
    assert [i["description"] for i in floor["installments"]] == ["Loja"]
    assert [r["merchant_key"] for r in floor["recurrences"]] == ["NETFLIX"]


def test_floor_of_a_past_month_only_knows_what_existed_then(client, db):
    _monthly(db, "NETFLIX", 5590, [4, 5, 6, 7, 8])
    _monthly(db, "ACADEMIA", 12000, [7, 8, 9])  # só vira recorrente em 2026-09

    assert _floor(client, "2026-06")["recurrences_cents"] == 5590
    assert {r["merchant_key"] for r in _floor(client, "2026-09")["recurrences"]} == {
        "NETFLIX",
        "ACADEMIA",
    }


def test_inactive_series_is_left_out_of_the_floor(client, db):
    _monthly(db, "NETFLIX", 5590, [3, 4, 5])  # parou em maio

    assert _recurrences(client)[0]["merchant_key"] == "NETFLIX"
    assert _floor(client, "2026-08")["recurrences"] == []
    assert _floor(client, "2026-06")["recurrences_cents"] == 5590


def test_floor_counts_real_installments_of_a_past_target_month(client, db):
    _add(
        db,
        "LOJA",
        2500,
        date(2026, 7, 5),
        installment_group_key="loja",
        installment_number=2,
        installment_total=6,
        raw="Loja",
    )

    floor = _floor(client, "2026-06")

    assert (floor["target_month"], floor["installments_cents"]) == ("2026-07", 2500)


def test_claude_subscription_with_iof_is_detected_from_three_card_files(client, load):
    load(
        "nubank/Nubank_2026-07-08.csv",
        "nubank/Nubank_2026-08-08.csv",
        "nubank/Nubank_2026-09-08.csv",
    )

    [item] = _recurrences(client)

    assert (item["merchant_key"], item["last_cents"], item["months_count"]) == (
        "ANTHROPIC CLAUDE SUB",
        11400,
        3,
    )
