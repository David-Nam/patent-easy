from fastapi.testclient import TestClient

from app.main import app
from app.routers.search import get_search_service
from app.services.query_builder import QueryBuilderConfigurationError, QueryBuilderProviderError


client = TestClient(app)


def test_search_endpoint_maps_configuration_errors():
    app.dependency_overrides[get_search_service] = lambda: ErrorSearchService(
        QueryBuilderConfigurationError("GEMINI_API_KEY is required")
    )
    try:
        response = client.post("/api/v1/search", json={"query": "전기차 배터리 열관리"})
    finally:
        app.dependency_overrides.pop(get_search_service, None)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SEARCH_CONFIGURATION_ERROR"


def test_search_endpoint_maps_provider_errors():
    app.dependency_overrides[get_search_service] = lambda: ErrorSearchService(
        QueryBuilderProviderError("LLM provider returned HTTP 503")
    )
    try:
        response = client.post("/api/v1/search", json={"query": "전기차 배터리 열관리"})
    finally:
        app.dependency_overrides.pop(get_search_service, None)

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "SEARCH_UPSTREAM_ERROR"


class ErrorSearchService:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def search(self, _request):
        raise self.exc
