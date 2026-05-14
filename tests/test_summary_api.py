from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.routers.summary import get_summary_service
from app.schemas.summary import SummaryResponse
from app.services.kipris_client import KIPRISParseError, KIPRISUpstreamError
from app.services.llm_client import LLMConfigurationError, LLMParseError, LLMProviderError
from app.services.summary_service import SummaryPatentNotFoundError


client = TestClient(app)


def test_summary_endpoint_maps_not_found_errors():
    app.dependency_overrides[get_summary_service] = lambda: ErrorSummaryService(
        SummaryPatentNotFoundError("not found")
    )
    try:
        response = client.post("/api/v1/patents/not-found/summary", json={})
    finally:
        app.dependency_overrides.pop(get_summary_service, None)

    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == "PATENT_NOT_FOUND"
    assert payload["details"]["patent_id"] == "not-found"


def test_summary_endpoint_maps_configuration_errors():
    app.dependency_overrides[get_summary_service] = lambda: ErrorSummaryService(
        LLMConfigurationError("GEMINI_API_KEY is required")
    )
    try:
        response = client.post("/api/v1/patents/10-2023-0147601/summary", json={})
    finally:
        app.dependency_overrides.pop(get_summary_service, None)

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "SUMMARY_CONFIGURATION_ERROR"
    assert payload["details"]["source"] == "llm"


def test_summary_endpoint_maps_provider_errors():
    app.dependency_overrides[get_summary_service] = lambda: ErrorSummaryService(
        LLMProviderError("LLM provider returned HTTP 503")
    )
    try:
        response = client.post("/api/v1/patents/10-2023-0147601/summary", json={})
    finally:
        app.dependency_overrides.pop(get_summary_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "SUMMARY_UPSTREAM_ERROR"
    assert payload["details"] == {"source": "llm", "kind": "provider_error"}


def test_summary_endpoint_maps_llm_parse_errors():
    app.dependency_overrides[get_summary_service] = lambda: ErrorSummaryService(
        LLMParseError("LLM response is not valid JSON")
    )
    try:
        response = client.post("/api/v1/patents/10-2023-0147601/summary", json={})
    finally:
        app.dependency_overrides.pop(get_summary_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "SUMMARY_UPSTREAM_ERROR"
    assert payload["details"] == {"source": "llm", "kind": "parse_error"}


def test_summary_endpoint_maps_kipris_upstream_errors_with_details():
    app.dependency_overrides[get_summary_service] = lambda: ErrorSummaryService(
        KIPRISUpstreamError(
            "KIPRIS request timed out",
            code="KIPRIS_TIMEOUT",
            details={"kind": "timeout"},
        )
    )
    try:
        response = client.post("/api/v1/patents/10-2023-0147601/summary", json={})
    finally:
        app.dependency_overrides.pop(get_summary_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "SUMMARY_UPSTREAM_ERROR"
    assert payload["details"]["source"] == "kipris"
    assert payload["details"]["kind"] == "timeout"
    assert payload["details"]["upstream_code"] == "KIPRIS_TIMEOUT"


def test_summary_endpoint_maps_kipris_xml_parse_errors_with_details():
    app.dependency_overrides[get_summary_service] = lambda: ErrorSummaryService(
        KIPRISParseError("KIPRIS response is not valid XML")
    )
    try:
        response = client.post("/api/v1/patents/10-2023-0147601/summary", json={})
    finally:
        app.dependency_overrides.pop(get_summary_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "SUMMARY_UPSTREAM_ERROR"
    assert payload["details"] == {"source": "kipris", "kind": "xml_parse_error"}


def test_summary_endpoint_returns_service_response():
    app.dependency_overrides[get_summary_service] = lambda: StaticSummaryService()
    try:
        response = client.post(
            "/api/v1/patents/10-2023-0147601/summary",
            json={"user_query": "전기차 배터리 열관리"},
        )
    finally:
        app.dependency_overrides.pop(get_summary_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["patent_id"] == "10-2023-0147601"
    assert payload["core_summary"] == "배터리 열관리 특허 요약"
    assert payload["is_cached"] is False


class ErrorSummaryService:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def summarize(self, _patent_id, _request):
        raise self.exc


class StaticSummaryService:
    async def summarize(self, patent_id, _request):
        return SummaryResponse(
            patent_id=patent_id,
            core_summary="배터리 열관리 특허 요약",
            business_application="전기차 기능 기획에 활용할 수 있습니다.",
            key_tags=["배터리", "열관리", "전기차"],
            generated_at=datetime.now(timezone.utc),
            is_cached=False,
        )
