from fastapi.testclient import TestClient

from app.main import app
from app.routers.search import get_search_service
from app.services.kipris_client import KIPRISParseError, KIPRISUpstreamError
from app.services.query_builder import (
    QueryBuilderConfigurationError,
    QueryBuilderParseError,
    QueryBuilderProviderError,
)


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
    payload = response.json()
    assert payload["code"] == "SEARCH_CONFIGURATION_ERROR"
    assert payload["details"]["source"] == "llm"


def test_search_endpoint_maps_provider_errors():
    app.dependency_overrides[get_search_service] = lambda: ErrorSearchService(
        QueryBuilderProviderError("LLM provider returned HTTP 503")
    )
    try:
        response = client.post("/api/v1/search", json={"query": "전기차 배터리 열관리"})
    finally:
        app.dependency_overrides.pop(get_search_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "SEARCH_UPSTREAM_ERROR"
    assert payload["details"] == {"source": "llm", "kind": "provider_error"}


def test_search_endpoint_maps_llm_parse_errors():
    app.dependency_overrides[get_search_service] = lambda: ErrorSearchService(
        QueryBuilderParseError("LLM response is not valid JSON")
    )
    try:
        response = client.post("/api/v1/search", json={"query": "전기차 배터리 열관리"})
    finally:
        app.dependency_overrides.pop(get_search_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "SEARCH_UPSTREAM_ERROR"
    assert payload["details"] == {"source": "llm", "kind": "parse_error"}


def test_search_endpoint_maps_kipris_upstream_errors_with_details():
    app.dependency_overrides[get_search_service] = lambda: ErrorSearchService(
        KIPRISUpstreamError(
            "KIPRIS returned HTTP 503",
            code="KIPRIS_HTTP_5XX",
            details={"kind": "http_5xx", "status_code": 503},
        )
    )
    try:
        response = client.post("/api/v1/search", json={"query": "전기차 배터리 열관리"})
    finally:
        app.dependency_overrides.pop(get_search_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "SEARCH_UPSTREAM_ERROR"
    assert payload["details"]["source"] == "kipris"
    assert payload["details"]["kind"] == "http_5xx"
    assert payload["details"]["upstream_code"] == "KIPRIS_HTTP_5XX"
    assert payload["details"]["status_code"] == 503


def test_search_endpoint_maps_kipris_xml_parse_errors_with_details():
    app.dependency_overrides[get_search_service] = lambda: ErrorSearchService(
        KIPRISParseError("KIPRIS response is not valid XML")
    )
    try:
        response = client.post("/api/v1/search", json={"query": "전기차 배터리 열관리"})
    finally:
        app.dependency_overrides.pop(get_search_service, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "SEARCH_UPSTREAM_ERROR"
    assert payload["details"] == {"source": "kipris", "kind": "xml_parse_error"}


class ErrorSearchService:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def search(self, _request):
        raise self.exc
