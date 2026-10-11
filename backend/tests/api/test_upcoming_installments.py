"""GET /installments/upcoming e o efeito das projetadas nas demais rotas (spec R10, §7.4)."""

CARD_JUL = "nubank/Nubank_2026-08-08.csv"
CARD_AUG = "nubank/Nubank_2026-09-08.csv"
ITAU_CARD = "itau/itau_fatura_2026-01.pdf"


def _upcoming(client):
    response = client.get("/api/installments/upcoming")
    assert response.status_code == 200
    return response.json()


def _upload(client, name, content):
    return client.post("/api/imports", files=[("files", (name, content, "text/csv"))])


def test_empty_database_has_nothing_upcoming(client):
    assert _upcoming(client) == {"months": [], "flagged": []}


def test_upcoming_lists_committed_installments_by_month(client, load):
    load(CARD_JUL)

    months = {m["month"]: m for m in _upcoming(client)["months"]}

    assert list(months) == ["2026-08", "2026-09"]
    assert months["2026-08"]["total_cents"] == 90946 + 1360 + 1331 + 794
    assert months["2026-09"]["total_cents"] == 1360
    latam = next(i for i in months["2026-08"]["items"] if i["description"].startswith("Latam"))
    assert (latam["number"], latam["total"], latam["amount_cents"]) == (4, 4, 90946)
    assert latam["account_name"] == "Nubank cartão"


def test_real_installment_leaves_the_upcoming_list(client, load):
    load(CARD_JUL, CARD_AUG)

    upcoming = _upcoming(client)

    assert [(m["month"], m["total_cents"]) for m in upcoming["months"]] == [("2026-09", 1358)]
    assert upcoming["flagged"] == []


def test_group_without_the_real_installment_is_flagged(client, load):
    """A conta cobre set/2026, mas as parcelas de ago/2026 não vieram (cancelada ou antecipada)."""
    load(CARD_JUL)
    response = _upload(
        client, "Nubank_2026-10-08.csv", b'date,title,amount\n2026-09-05,Padaria,"10,00"\n'
    )
    assert response.json()[0]["status"] == "importado"

    upcoming = _upcoming(client)

    assert upcoming["months"] == []
    assert len(upcoming["flagged"]) == 4  # Latam, Steam 13,60 e as duas Steam 3/3 (mesmo texto)
    flagged = {g["description"]: g for g in upcoming["flagged"]}
    latam = flagged["Latam Air*0000 - Parcela 4/4"]
    assert (latam["expected_month"], latam["covered_through"], latam["next_number"]) == (
        "2026-08",
        "2026-09",
        4,
    )
    assert flagged["Pag*Steam - Parcela 2/3"]["remaining"] == 2


def test_uncovered_months_are_not_flagged_for_other_accounts(client, load):
    load(CARD_JUL, "nubank/NU_123456789_10SET2026_24SET2026.ofx")  # a conta Nubank cobre set/2026

    upcoming = _upcoming(client)

    assert upcoming["flagged"] == []  # cobertura é por conta: o cartão só chega a jul/2026
    assert len(upcoming["months"]) == 2


def test_import_response_carries_next_invoice_warnings(client, fixture_file):
    files = [("files", (*fixture_file(ITAU_CARD), "application/pdf"))]

    (result,) = client.post("/api/imports", files=files).json()

    assert result["status"] == "importado"
    assert result["warnings"] == []


def test_transactions_list_hides_projected_by_default(client, load):
    load(CARD_JUL)

    default = client.get("/api/transactions", params={"limit": 500}).json()
    projected = client.get("/api/transactions", params={"status": "projetada", "limit": 500}).json()

    assert {t["status"] for t in default["items"]} == {"real"}
    assert default["total"] == 10
    assert {t["status"] for t in projected["items"]} == {"projetada"}
    assert projected["total"] == 5


def test_projected_do_not_count_in_the_dashboard(client, load):
    load(CARD_JUL)

    summary = client.get("/api/dashboard/summary", params={"month": "2026-08"}).json()

    assert summary["total_cents"] == 0
    assert client.get("/api/dashboard/history").json()["months"][-1]["month"] == "2026-07"


def test_projected_transaction_cannot_be_reviewed(client, load):
    load(CARD_JUL)
    projected = client.get("/api/transactions", params={"status": "projetada"}).json()["items"][0]

    response = client.patch(f"/api/transactions/{projected['id']}", json={"action": "confirm"})

    assert response.status_code == 409


def test_undo_through_the_api_rebuilds_projected(client, load, fixture_file):
    load(CARD_JUL)
    (aug,) = client.post(
        "/api/imports", files=[("files", (*fixture_file(CARD_AUG), "text/csv"))]
    ).json()
    assert [m["month"] for m in _upcoming(client)["months"]] == ["2026-09"]

    assert client.delete(f"/api/imports/{aug['batch_id']}").status_code == 204

    months = {m["month"] for m in _upcoming(client)["months"]}
    assert months == {"2026-08", "2026-09"}
