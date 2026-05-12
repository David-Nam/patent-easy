from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.routers.summary import get_summary_service
from app.schemas.summary import SummaryResponse
from app.services.llm_client import LLMConfigurationError, LLMProviderError
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
    assert response.json()["detail"]["code"] == "PATENT_NOT_FOUND"


def test_summary_endpoint_maps_configuration_errors():
    app.dependency_overrides[get_summary_service] = lambda: ErrorSummaryService(
        LLMConfigurationError("GEMINI_API_KEY is required")
    )
    try:
        response = client.post("/api/v1/patents/10-2023-0147601/summary", json={})
    finally:
        app.dependency_overrides.pop(get_summary_service, None)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SUMMARY_CONFIGURATION_ERROR"


def test_summary_endpoint_maps_provider_errors():
    app.dependency_overrides[get_summary_service] = lambda: ErrorSummaryService(
        LLMProviderError("LLM provider returned HTTP 503")
    )
    try:
        response = client.post("/api/v1/patents/10-2023-0147601/summary", json={})
    finally:
        app.dependency_overrides.pop(get_summary_service, None)

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "SUMMARY_UPSTREAM_ERROR"


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
