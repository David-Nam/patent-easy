import os

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.routers.chat import get_chat_service
from app.services.cache import SQLiteCache
from app.services.chat_service import ChatService
from app.services.kipris_client import KIPRISClient
from app.services.llm_client import LLMClient


pytestmark = [pytest.mark.live_kipris, pytest.mark.live_llm]

client = TestClient(app)


def test_chat_endpoint_calls_live_kipris_and_gemini(tmp_path):
    if os.getenv("RUN_LIVE_KIPRIS") != "1" or os.getenv("RUN_LIVE_LLM") != "1":
        pytest.skip("Set RUN_LIVE_KIPRIS=1 and RUN_LIVE_LLM=1 for live chat validation")

    settings = get_settings()
    if not settings.kipris_api_key:
        pytest.skip("KIPRIS_API_KEY is required for live chat validation")
    if settings.llm_provider != "gemini":
        pytest.skip("Set LLM_PROVIDER=gemini for Gemini live validation")
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is required for live chat validation")

    app.dependency_overrides[get_chat_service] = lambda: ChatService(
        detail_client=KIPRISClient(cache_enabled=False),
        llm_client=LLMClient(),
        cache=SQLiteCache(tmp_path / "chat-cache.sqlite"),
    )
    try:
        response = client.post(
            "/api/v1/patents/10-2023-0147601/chat",
            json={"question": "이 특허는 전기차 배터리 열관리 기능과 관련이 있나요?"},
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["patent_id"]
    assert payload["answer"]
    assert payload["sources"]
