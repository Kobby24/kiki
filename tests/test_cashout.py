import pytest


async def register_and_login(client, email):
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "strong-password"}
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "strong-password"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_complete_simulated_cashout(client):
    headers = await register_and_login(client, "demo@example.com")
    intent = await client.post(
        "/api/v1/intent/interpret",
        json={"input_type": "text", "text": "Me pɛ sɛ meyi sidi 100", "language": "tw"},
    )
    assert intent.status_code == 200
    assert intent.json()["amount"] == "100"
    cashout = await client.post(
        "/api/v1/cashout",
        headers=headers,
        json={"amount": 100, "language": "tw", "input_method": "structured"},
    )
    assert cashout.status_code == 201
    cashout_id = cashout.json()["id"]
    confirmed = await client.post(
        f"/api/v1/cashout/{cashout_id}/confirm",
        headers=headers,
        json={"confirmed": True},
    )
    assert confirmed.json()["status"] == "awaiting_authorization"
    instructions = await client.post(
        f"/api/v1/cashout/{cashout_id}/authorization/start", headers=headers
    )
    assert "PIN" in " ".join(instructions.json()["instructions"])
    completed = await client.post(
        f"/api/v1/cashout/{cashout_id}/authorization/status",
        headers=headers,
        json={"status": "authorized"},
    )
    assert completed.json()["status"] == "simulated"
    message = await client.post(
        f"/api/v1/cashout/{cashout_id}/communication", headers=headers
    )
    assert message.json()["message_type"] == "agent_message"
    receipt = await client.get(f"/api/v1/cashout/{cashout_id}/receipt", headers=headers)
    assert receipt.status_code == 200
    assert receipt.json()["simulation"] is True


@pytest.mark.asyncio
async def test_ownership_and_confirmation(client):
    owner = await register_and_login(client, "owner@example.com")
    other = await register_and_login(client, "other@example.com")
    cashout = await client.post("/api/v1/cashout", headers=owner, json={"amount": 50})
    cashout_id = cashout.json()["id"]
    forbidden = await client.get(f"/api/v1/cashout/{cashout_id}", headers=other)
    assert forbidden.status_code == 404
    bypass = await client.post(
        f"/api/v1/cashout/{cashout_id}/authorization/status",
        headers=owner,
        json={"status": "authorized"},
    )
    assert bypass.status_code == 409


@pytest.mark.asyncio
async def test_pin_payload_is_rejected(client):
    headers = await register_and_login(client, "pin@example.com")
    response = await client.post(
        "/api/v1/cashout", headers=headers, json={"amount": 100, "pin": "1234"}
    )
    assert response.status_code == 422
