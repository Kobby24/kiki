import pytest
from fastapi import FastAPI

from app.main import app
from ai.asr_service import get_asr_service


def test_single_fastapi_application_exposes_both_apis():
    assert isinstance(app, FastAPI)
    paths = {route.path for route in app.routes}
    assert "/api/v1/health" in paths
    assert "/api/v1/intent/interpret" in paths
    assert "/ai/transcribe" in paths
    assert "/ai/extract-intent" in paths
    assert "/ai/process-pipeline" in paths
    assert "/ai/synthesize" in paths


def test_asr_service_is_a_lazy_singleton():
    first = get_asr_service()
    second = get_asr_service()
    assert first is second


@pytest.mark.asyncio
async def test_openapi_lists_sikapa_and_ai_endpoints(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/cashout" in paths
    assert "/ai/extract-intent" in paths
    assert "/ai/transcribe" in paths
    assert "/ai/synthesize" in paths
    assert paths["/ai/extract-intent"]["post"]["tags"] == ["AI"]
    assert paths["/api/v1/health"]["get"]["tags"] == ["Health"]


@pytest.mark.asyncio
async def test_extract_intent_is_local(client):
    response = await client.post(
        "/ai/extract-intent",
        json={"text": "withdraw 100 cedis"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "WITHDRAW"
    assert body["amount"] == 100.0
    assert body["currency"] == "GHS"
    assert body["raw_text"] == "withdraw 100 cedis"


@pytest.mark.asyncio
async def test_transcribe_rejects_unsupported_media(client):
    response = await client.post(
        "/ai/transcribe",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_transcribe_rejects_empty_audio(client):
    response = await client.post(
        "/ai/transcribe",
        files={"file": ("audio.wav", b"", "audio/wav")},
    )
    assert response.status_code == 422
