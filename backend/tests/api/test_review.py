"""Contrato HTTP da revisão: /transactions, /merchants, /categories e /rules (spec §7.4, R7)."""

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repo.models import Category, MerchantMemory, Transaction

NOW = datetime(2026, 10, 1, 12, 0, 0)
CARD_JUL = "nubank/Nubank_2026-08-08.csv"
CARD_AUG = "nubank/Nubank_2026-09-08.csv"
ITAU_ACCOUNT = "itau/itau_extrato_A.pdf"
ITAU_CARD = "itau/itau_fatura_2026-01.pdf"


def _category_id(client, name):
    return next(c["id"] for c in client.get("/api/categories").json() if c["name"] == name)


def _transactions(client, **params):
    response = client.get("/api/transactions", params={"limit": 500, **params})
    assert response.status_code == 200
    return response.json()["items"]


def _merchant(client, key):
    return next(
        (m for m in client.get("/api/merchants?pending=true").json() if m["merchant_key"] == key),
        None,
    )


def test_list_filters_by_month_account_and_source(client, load):
    load(CARD_JUL, CARD_AUG)

    months = sorted({t["competence_month"] for t in _transactions(client)})
    assert len(months) >= 2
    first = _transactions(client, month=months[0])
    assert first and {t["competence_month"] for t in first} == {months[0]}
    account_id = first[0]["account_id"]
    assert {t["account_id"] for t in _transactions(client, account_id=account_id)} == {account_id}
    assert {t["category_source"] for t in _transactions(client, source="regra")} == {"regra"}


def test_list_filters_by_merchant_key(client, load):
    load(CARD_AUG)

    steam = _transactions(client, merchant_key="STEAM", pending=True)

    assert len(steam) == 3 and {t["merchant_key"] for t in steam} == {"STEAM"}


def test_list_paginates(client, load):
    load(CARD_AUG)

    page = client.get("/api/transactions", params={"limit": 4, "offset": 8}).json()

    assert page["total"] == 11 and len(page["items"]) == 3


def test_pending_queue_definition(client, load):
    load(CARD_AUG, ITAU_ACCOUNT, ITAU_CARD)

    pending = {t["merchant_key"] for t in _transactions(client, pending=True)}

    assert "FORNERIA EXEMPLO" in pending  # sem categoria
    assert "APLICACAO COFRINHOS" in pending  # sugestão de investimento
    assert "UBER NUPAY" not in pending  # regra 0.9 com categoria
    assert "PAGAMENTO RECEBIDO" not in pending  # ignorar estrutural


def test_bank_category_suggestion_is_in_low_confidence_queue(client, load):
    load(ITAU_CARD)
    # sem a regra de palavra-chave, só a categoria do banco (0.5) sugere
    rule = next(r for r in client.get("/api/rules").json() if r["pattern"] == "netflix")
    client.delete(f"/api/rules/{rule['id']}")

    netflix = next(t for t in _transactions(client) if t["merchant_key"] == "NETFLIX COM")

    assert (netflix["category_source"], netflix["category_confidence"]) == ("regra", 0.5)
    assert netflix["id"] in {t["id"] for t in _transactions(client, pending=True)}


def test_merchants_groups_pending(client, load):
    load(CARD_AUG)

    steam = _merchant(client, "STEAM")

    assert steam["count"] == 3 and steam["total_cents"] == 1358 + 1331 + 794
    assert steam["category_id"] is None
    assert _merchant(client, "UBER NUPAY") is None


def test_patch_correction_learns_and_recategorizes_unreviewed(client, load):
    load(CARD_AUG)
    lazer = _category_id(client, "Lazer e Tecnologia")
    first, second, third = [t for t in _transactions(client) if t["merchant_key"] == "STEAM"]

    response = client.patch(
        f"/api/transactions/{first['id']}", json={"kind": "despesa", "category_id": lazer}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["category_source"], body["category_id"]) == ("manual", lazer)
    assert body["reviewed_at"] is not None
    others = {t["id"]: t for t in _transactions(client) if t["merchant_key"] == "STEAM"}
    assert {others[second["id"]]["category_source"], others[third["id"]]["category_source"]} == {
        "memoria"
    }
    assert _merchant(client, "STEAM") is None  # memória 1.0 com categoria sai da fila


def test_patch_confirm_only_marks_reviewed(client, load):
    load(ITAU_CARD)
    rule = next(r for r in client.get("/api/rules").json() if r["pattern"] == "netflix")
    client.delete(f"/api/rules/{rule['id']}")
    netflix = next(t for t in _transactions(client) if t["merchant_key"] == "NETFLIX COM")

    response = client.patch(f"/api/transactions/{netflix['id']}", json={"action": "confirm"})

    body = response.json()
    assert body["reviewed_at"] is not None
    assert (body["category_source"], body["category_confidence"]) == ("regra", 0.5)
    assert netflix["id"] not in {t["id"] for t in _transactions(client, pending=True)}


def test_confirming_investment_ignores_it_without_memory(client, load, migrated_engine):
    load(ITAU_ACCOUNT)
    cofrinhos = next(t for t in _transactions(client) if t["merchant_key"] == "APLICACAO COFRINHOS")
    assert cofrinhos["suggested_ignore_reason"] == "investimento"

    response = client.patch(
        f"/api/transactions/{cofrinhos['id']}",
        json={"kind": "ignorar", "ignore_reason": "investimento"},
    )

    body = response.json()
    assert (body["kind"], body["ignore_reason"], body["suggested_ignore_reason"]) == (
        "ignorar",
        "investimento",
        None,
    )
    with Session(migrated_engine) as session:
        assert session.get(MerchantMemory, "APLICACAO COFRINHOS") is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"kind": "ignorar"},
        {"kind": "despesa", "ignore_reason": "outro"},
        {"kind": "despesa", "category_id": 9999},
    ],
)
def test_patch_rejects_invalid_combinations(client, load, payload):
    load(CARD_AUG)
    target = _transactions(client)[0]

    assert client.patch(f"/api/transactions/{target['id']}", json=payload).status_code == 422


def test_patch_unknown_is_404_and_projected_is_409(client, load, migrated_engine):
    load(CARD_AUG)
    assert client.patch("/api/transactions/9999", json={"action": "confirm"}).status_code == 404
    with Session(migrated_engine) as session:
        transaction = session.scalars(select(Transaction)).first()
        transaction.status = "projetada"
        session.commit()
        projected_id = transaction.id

    response = client.patch(f"/api/transactions/{projected_id}", json={"action": "confirm"})

    assert response.status_code == 409


def test_inactive_category_cannot_be_applied(client, load):
    load(CARD_AUG)
    lazer = _category_id(client, "Lazer e Tecnologia")
    client.patch(f"/api/categories/{lazer}", json={"is_active": False})
    target = _transactions(client)[0]

    response = client.patch(
        f"/api/transactions/{target['id']}", json={"kind": "despesa", "category_id": lazer}
    )

    assert response.status_code == 422


def test_bulk_apply_affects_only_pending_of_that_merchant(client, load):
    load(CARD_AUG, CARD_JUL)
    saude = _category_id(client, "Saúde e Bem-Estar")
    lazer = _category_id(client, "Lazer e Tecnologia")
    steam = [t for t in _transactions(client) if t["merchant_key"] == "STEAM"]
    reviewed = steam[0]
    client.patch(
        f"/api/transactions/{reviewed['id']}", json={"kind": "despesa", "category_id": lazer}
    )

    # nova correção em outra categoria, depois um lote só nas ainda pendentes (nenhuma)
    response = client.post(
        "/api/transactions/bulk-categorize",
        json={"merchant_key": "STEAM", "action": "apply", "kind": "despesa", "category_id": saude},
    )

    assert response.status_code == 200 and response.json() == {"affected": 0}
    after = {t["id"]: t for t in _transactions(client) if t["merchant_key"] == "STEAM"}
    assert after[reviewed["id"]]["category_id"] == lazer


def test_bulk_apply_and_bulk_confirm(client, load):
    load(CARD_AUG, CARD_JUL)
    saude = _category_id(client, "Saúde e Bem-Estar")

    applied = client.post(
        "/api/transactions/bulk-categorize",
        json={"merchant_key": "STEAM", "action": "apply", "kind": "despesa", "category_id": saude},
    )
    confirmed = client.post(
        "/api/transactions/bulk-categorize",
        json={"merchant_key": "LATAM AIR", "action": "confirm"},
    )

    assert applied.json() == {"affected": 6}
    assert confirmed.json() == {"affected": 2}
    steam = [t for t in _transactions(client) if t["merchant_key"] == "STEAM"]
    assert {(t["category_id"], t["category_source"]) for t in steam} == {(saude, "manual")}
    assert all(t["reviewed_at"] for t in steam)
    assert _merchant(client, "STEAM") is None and _merchant(client, "LATAM AIR") is None


def test_bulk_with_ids_limits_scope(client, load):
    load(CARD_AUG)
    saude = _category_id(client, "Saúde e Bem-Estar")
    steam = [t for t in _transactions(client) if t["merchant_key"] == "STEAM"]

    response = client.post(
        "/api/transactions/bulk-categorize",
        json={
            "merchant_key": "STEAM",
            "action": "apply",
            "kind": "despesa",
            "category_id": saude,
            "transaction_ids": [steam[0]["id"]],
        },
    )

    assert response.json() == {"affected": 1}


def test_reimport_does_not_undo_reviews(client, load, migrated_engine, fixture_file):
    load(CARD_AUG)
    saude = _category_id(client, "Saúde e Bem-Estar")
    client.post(
        "/api/transactions/bulk-categorize",
        json={"merchant_key": "STEAM", "action": "apply", "kind": "despesa", "category_id": saude},
    )
    client.post(
        "/api/transactions/bulk-categorize", json={"merchant_key": "LATAM AIR", "action": "confirm"}
    )
    before = {t["id"]: t for t in _transactions(client) if t["reviewed_at"]}

    load(CARD_JUL, CARD_AUG)  # lote sobreposto + reimportação do mesmo arquivo

    after = {t["id"]: t for t in _transactions(client)}
    assert before and all(after[i] == t for i, t in before.items())


def test_categories_create_rename_deactivate(client):
    created = client.post("/api/categories", json={"name": " Pets ", "color": "#123456"})
    assert created.status_code == 201 and created.json()["name"] == "Pets"
    category_id = created.json()["id"]

    assert client.post("/api/categories", json={"name": "Pets"}).status_code == 409
    assert (
        client.patch(f"/api/categories/{category_id}", json={"name": "Moradia"}).status_code == 409
    )
    assert client.post("/api/categories", json={"name": "  "}).status_code == 422
    patched = client.patch(
        f"/api/categories/{category_id}", json={"name": "Animais", "is_active": False}
    )
    assert patched.json()["name"] == "Animais" and patched.json()["is_active"] is False
    assert client.patch("/api/categories/9999", json={"name": "X"}).status_code == 404


def test_rules_crud_and_validation(client):
    alimentacao = _category_id(client, "Alimentação")

    created = client.post(
        "/api/rules", json={"pattern": "padaria", "category_id": alimentacao, "priority": 5}
    )
    assert created.status_code == 201
    rule_id = created.json()["id"]
    assert any(r["id"] == rule_id for r in client.get("/api/rules").json())
    assert (
        client.post(
            "/api/rules", json={"pattern": "(", "match_type": "regex", "category_id": alimentacao}
        ).status_code
        == 422
    )
    assert client.post("/api/rules", json={"pattern": "x", "category_id": 9999}).status_code == 422
    assert client.patch(f"/api/rules/{rule_id}", json={"priority": 1}).json()["priority"] == 1
    assert client.delete(f"/api/rules/{rule_id}").status_code == 204
    assert client.delete(f"/api/rules/{rule_id}").status_code == 404


def test_rule_change_reclassifies_unreviewed_only(client, load, migrated_engine):
    load(CARD_AUG)
    transporte = _category_id(client, "Transporte")
    saude = _category_id(client, "Saúde e Bem-Estar")
    uber = [t for t in _transactions(client) if t["merchant_key"] == "UBER NUPAY"]
    client.patch(
        f"/api/transactions/{uber[0]['id']}", json={"kind": "despesa", "category_id": saude}
    )

    client.post("/api/rules", json={"pattern": "uber", "category_id": transporte, "priority": 0})

    after = {t["id"]: t for t in _transactions(client)}
    assert after[uber[0]["id"]]["category_id"] == saude  # revisada intacta
    with Session(migrated_engine) as session:
        assert session.get(MerchantMemory, "UBER NUPAY").category_id == saude
        assert (
            session.scalar(select(Category.id).where(Category.name == "Transporte")) == transporte
        )
