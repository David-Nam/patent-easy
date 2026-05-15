from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.routers.chat import get_chat_service
from app.schemas.chat import ChatResponse, ChatSource
from app.services.chat_service import ChatPatentNotFoundError
from app.services.kipris_client import KIPRISParseError, KIPRISUpstreamError
from app.services.llm_client import LLMConfigurationError, LLMParseError, LLMProviderError


client = TestClient(app)


def test_chat_endpoint_maps_not_found_errors():
    app.dependency_overrides[get_chat_service] = lambda: ErrorChatService(ChatPatentNotFoundError("not found"))
    try:
        response = client.post(
            "/api/v1/patents/not-found/chat",
            json={"question": "이 특허는 어떤 기능과 관련 있어?"},
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == "PATENT_NOT_FOUND"
    assert payload["details"]["patent_id"] == "not-found"


def test_chat_endpoint_maps_configuration_errors():
    app.dependency_overrides[get_chat_service] = lambda: ErrorChatService(
        LLMConfigurationError("GEMINI_API_KEY is required")
    )
    try:
        response = client.post(
            "/api/v1/patents/10-2023-0147601/chat",
            json={"question": "이 특허는 어떤 기능과 관련 있어?"},
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "CHAT_CONFIGURATION_ERROR"
    assert payload["details"]["source"] == "llm"


def test_chat_endpoint_maps_provider_errors():
    app.dependency_overrides[get_chat_service] = lambda: ErrorChatService(
        LLMProviderError("LLM provider returned HTTP 503")
    )
    try:
        response = client.post(
            "/api/v1/patents/10-2023-0147601/chat",
            json={"question": "이 특허는 어떤 기능과 관련 있어?"},
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "CHAT_UPSTREAM_ERROR"
    assert payload["details"] == {"source": "llm", "kind": "provider_error"}


def test_chat_endpoint_maps_llm_parse_errors():
    app.dependency_overrides[get_chat_service] = lambda: ErrorChatService(
        LLMParseError("LLM response is not valid JSON")
    )
    try:
        response = client.post(
            "/api/v1/patents/10-2023-0147601/chat",
            json={"question": "이 특허는 어떤 기능과 관련 있어?"},
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "CHAT_UPSTREAM_ERROR"
    assert payload["details"] == {"source": "llm", "kind": "parse_error"}


def test_chat_endpoint_maps_kipris_upstream_errors_with_details():
    app.dependency_overrides[get_chat_service] = lambda: ErrorChatService(
        KIPRISUpstreamError(
            "KIPRIS request timed out",
            code="KIPRIS_TIMEOUT",
            details={"kind": "timeout"},
        )
    )
    try:
        response = client.post(
            "/api/v1/patents/10-2023-0147601/chat",
            json={"question": "이 특허는 어떤 기능과 관련 있어?"},
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "CHAT_UPSTREAM_ERROR"
    assert payload["details"]["source"] == "kipris"
    assert payload["details"]["kind"] == "timeout"
    assert payload["details"]["upstream_code"] == "KIPRIS_TIMEOUT"


def test_chat_endpoint_maps_kipris_xml_parse_errors_with_details():
    app.dependency_overrides[get_chat_service] = lambda: ErrorChatService(
        KIPRISParseError("KIPRIS response is not valid XML")
    )
    try:
        response = client.post(
            "/api/v1/patents/10-2023-0147601/chat",
            json={"question": "이 특허는 어떤 기능과 관련 있어?"},
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "CHAT_UPSTREAM_ERROR"
    assert payload["details"] == {"source": "kipris", "kind": "xml_parse_error"}


def test_chat_endpoint_returns_service_response():
    app.dependency_overrides[get_chat_service] = lambda: StaticChatService()
    try:
        response = client.post(
            "/api/v1/patents/10-2023-0147601/chat",
            json={
                "question": "이 특허는 배터리 열관리 서비스와 관련 있어?",
                "user_query": "전기차 배터리 열관리",
                "history": [{"role": "user", "content": "핵심을 알려줘."}],
            },
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["patent_id"] == "10-2023-0147601"
    assert payload["answer"] == "청구항 1 기준으로 관련이 있습니다."
    assert payload["sources"][0]["type"] == "claim"
    assert payload["sources"][0]["claim_number"] == 1
    assert payload["is_cached"] is False


class ErrorChatService:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def chat(self, _patent_id, _request):
        raise self.exc


class StaticChatService:
    async def chat(self, patent_id, _request):
        return ChatResponse(
            patent_id=patent_id,
            answer="청구항 1 기준으로 관련이 있습니다.",
            sources=[
                ChatSource(
                    type="claim",
                    claim_number=1,
                    snippet="전기자동차 배터리의 온도와 주행 데이터를 이용하여 열관리 모드를 결정한다.",
                )
            ],
            generated_at=datetime.now(timezone.utc),
            is_cached=False,
        )
