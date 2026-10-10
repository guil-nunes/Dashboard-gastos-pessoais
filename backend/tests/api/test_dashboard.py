"""Dashboard de fechamento (spec R8): totais, categorias, histórico, filtros e drill-down."""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import create_app
from app.repo.models import Account, Category, Transaction

CARD_JUL = "nubank/Nubank_2026-08-08.csv"  # competência 2026-07
CARD_AUG = "nubank/Nubank_2026-09-08.csv"  # competência 2026-08
OFX_A = "nubank/NU_123456789_01SET2026_15SET2026.ofx"
OFX_B = "nubank/NU_123456789_10SET2026_24SET2026.ofx"
ITAU_ACCOUNT = "itau/itau_extrato_A.pdf"
ITAU_CARD = "itau/itau_fatura_2026-01.pdf"

JUL_TOTAL, AUG_TOTAL = 111721, 210283  # soma manual das faturas, sem o pagamento recebido
NUBANK_ACCOUNT_SEP = 1100 + 1007 + 8990 + 4500 + 3250
ITAU_ACCOUNT_SEP = 111678
STEAM_AUG = 1358 + 1331 + 794


def _summary(client, month, **filters):
    response = client.get("/api/dashboard/summary", params={"month": month, **filters})
    assert response.status_code == 200
    return response.json()


def _history(client, **filters):
    response = client.get("/api/dashboard/history", params=filters)
    assert response.status_code == 200
    return response.json()


def _category_id(client, name):
    return next(c["id"] for c in client.get("/api/categories").json() if c["name"] == name)


def test_empty_database_gives_empty_dashboard(client):
    summary = _summary(client, "2026-08")

    assert (summary["total_cents"], summary["delta_pct"], summary["categories"]) == (0, None, [])
    assert _history(client) == {"months": [], "categories": []}


def test_card_month_matches_manual_sum_and_ignores_invoice_payment(client, load):
    load(CARD_JUL, CARD_AUG, OFX_A, OFX_B)  # a fatura paga na conta (R4) não conta duas vezes

    assert _summary(client, "2026-07", account_kind="cartao")["total_cents"] == JUL_TOTAL
    assert _summary(client, "2026-08", account_kind="cartao")["total_cents"] == AUG_TOTAL


def test_refund_reduces_the_category_total(client, load):
    load(CARD_JUL)  # Uber 12,93 e o estorno de -12,93
    summary = _summary(client, "2026-07")

    transporte = next(c for c in summary["categories"] if c["name"] == "Transporte")

    assert (transporte["total_cents"], transporte["count"]) == (0, 2)


def test_projected_transactions_do_not_count(client, load, migrated_engine):
    load(CARD_AUG)
    with Session(migrated_engine) as session:
        account = session.scalars(select(Account)).one()
        session.add(
            Transaction(
                account_id=account.id,
                occurred_on=date(2026, 8, 20),
                competence_month="2026-08",
                amount_cents=99999,
                description_raw="Projetada",
                merchant_key="PROJETADA",
                normalizer_version=1,
                kind="despesa",
                category_source="nenhuma",
                status="projetada",
                dedup_key="proj:test",
                created_at=datetime(2026, 10, 1),
            )
        )
        session.commit()

    assert _summary(client, "2026-08")["total_cents"] == AUG_TOTAL


def test_categories_sum_to_total_with_percentages(client, load):
    load(CARD_AUG)
    summary = _summary(client, "2026-08")
    categories = summary["categories"]

    assert sum(c["total_cents"] for c in categories) == summary["total_cents"]
    assert categories == sorted(categories, key=lambda c: (-c["total_cents"], c["name"]))
    assert round(sum(c["pct"] for c in categories)) in (99, 100, 101)
    assert any(c["category_id"] is None and c["name"] == "Sem categoria" for c in categories)


def test_variation_against_previous_month(client, load):
    load(CARD_JUL, CARD_AUG)

    august = _summary(client, "2026-08")
    july = _summary(client, "2026-07")

    assert (august["previous_month"], august["previous_total_cents"]) == ("2026-07", JUL_TOTAL)
    assert august["delta_cents"] == AUG_TOTAL - JUL_TOTAL
    assert august["delta_pct"] == 88.2
    assert (july["previous_total_cents"], july["delta_cents"], july["delta_pct"]) == (
        0,
        JUL_TOTAL,
        None,
    )


def test_bank_and_account_kind_filters_in_a_mixed_month(client, load):
    load(OFX_A, OFX_B, ITAU_ACCOUNT)

    both = _summary(client, "2026-09")["total_cents"]
    nubank = _summary(client, "2026-09", bank="nubank", account_kind="conta")["total_cents"]
    itau = _summary(client, "2026-09", bank="itau")["total_cents"]

    assert (nubank, itau) == (NUBANK_ACCOUNT_SEP, ITAU_ACCOUNT_SEP)
    assert both == nubank + itau
    assert _summary(client, "2026-09", account_kind="cartao")["total_cents"] == 0


def test_history_fills_gaps_and_totals_match_categories(client, load):
    load(CARD_JUL, OFX_A, OFX_B)

    history = _history(client)

    assert [m["month"] for m in history["months"]] == ["2026-07", "2026-08", "2026-09"]
    assert history["months"][1]["total_cents"] == 0 and history["months"][1]["by_category"] == []
    for month in history["months"]:
        assert month["total_cents"] == sum(v["total_cents"] for v in month["by_category"])
    used = {v["category_id"] for m in history["months"] for v in m["by_category"]} - {None}
    assert {c["id"] for c in history["categories"]} == used


def test_history_of_itau_card_spans_the_invoice_months(client, load):
    load(ITAU_CARD)

    months = {m["month"]: m["total_cents"] for m in _history(client, bank="itau")["months"]}

    assert months == {"2025-11": -6, "2025-12": 16268, "2026-01": 8386}


@pytest.mark.parametrize("filters", [{}, {"bank": "itau"}, {"account_kind": "cartao"}])
def test_drill_down_sums_match_every_category_total(client, load, filters):
    load(CARD_JUL, CARD_AUG, ITAU_CARD, ITAU_ACCOUNT)
    month = "2025-12" if filters.get("bank") == "itau" else "2026-08"
    summary = _summary(client, month, **filters)
    assert summary["categories"]

    for category in summary["categories"]:
        params = {"month": month, "kind": "despesa", "status": "real", "limit": 500, **filters}
        if category["category_id"] is None:
            params["without_category"] = True
        else:
            params["category_id"] = category["category_id"]
        page = client.get("/api/transactions", params=params).json()

        assert sum(t["amount_cents"] for t in page["items"]) == category["total_cents"]
        assert page["total"] == category["count"]


def test_review_correction_is_reflected_in_the_dashboard(client, load):
    load(CARD_AUG)
    lazer = _category_id(client, "Lazer e Tecnologia")
    before = _summary(client, "2026-08")
    assert not any(c["category_id"] == lazer for c in before["categories"])

    client.post(
        "/api/transactions/bulk-categorize",
        json={"merchant_key": "STEAM", "action": "apply", "kind": "despesa", "category_id": lazer},
    )
    after = _summary(client, "2026-08")

    steam = next(c for c in after["categories"] if c["category_id"] == lazer)
    assert steam["total_cents"] == STEAM_AUG
    assert after["total_cents"] == before["total_cents"]


def test_ignored_in_review_leaves_the_dashboard_total(client, load):
    load(CARD_AUG)
    client.post(
        "/api/transactions/bulk-categorize",
        json={
            "merchant_key": "STEAM",
            "action": "apply",
            "kind": "ignorar",
            "ignore_reason": "outro",
        },
    )

    assert _summary(client, "2026-08")["total_cents"] == AUG_TOTAL - STEAM_AUG


@pytest.mark.parametrize(
    "params", [{"month": "2026-13"}, {"month": "agosto"}, {"month": "2026-08", "bank": "xp"}]
)
def test_invalid_parameters_are_rejected(client, params):
    assert client.get("/api/dashboard/summary", params=params).status_code == 422


def test_summary_requires_month(client):
    assert client.get("/api/dashboard/summary").status_code == 422


def test_category_names_come_from_the_category_table(client, load, migrated_engine):
    load(CARD_JUL)
    with Session(migrated_engine) as session:
        transporte = session.scalar(select(Category).where(Category.name == "Transporte"))
        transporte.name = "Mobilidade"
        session.commit()

    names = {c["name"] for c in _summary(client, "2026-07")["categories"]}

    assert "Mobilidade" in names


def test_frontend_is_served_with_spa_fallback(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("segredo", encoding="utf-8")
    web = TestClient(create_app(frontend_dist=dist))

    assert web.get("/dashboard").text == "<html>app</html>"
    assert web.get("/assets/app.js").text == "console.log(1)"
    assert "segredo" not in web.get("/..%2fsecret.txt").text
    missing = web.get("/api/nao-existe")
    assert (missing.status_code, missing.json()) == (404, {"detail": "Not Found"})
    assert web.get("/api/health").json() == {"status": "ok"}


def test_without_a_built_frontend_the_api_still_works(tmp_path):
    web = TestClient(create_app(frontend_dist=tmp_path / "nada"))

    assert web.get("/api/health").status_code == 200
    assert web.get("/dashboard").status_code == 404
