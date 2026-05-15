from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_openapi_documents_core_backend_routes():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    spec = response.json()
    paths = spec["paths"]

    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/v1/search" in paths
    assert "/api/v1/patents/{patent_id}" in paths
    assert "/api/v1/patents/{patent_id}/summary" in paths
    assert "/api/v1/patents/{patent_id}/chat" in paths


def test_openapi_response_models_match_public_api_contract():
    spec = client.get("/openapi.json").json()

    assert _response_schema_ref(spec, "/api/v1/search", "post", "200") == "#/components/schemas/SearchResponse"
    assert _response_schema_ref(spec, "/api/v1/patents/{patent_id}", "get", "200") == "#/components/schemas/PatentDetail"
    assert (
        _response_schema_ref(spec, "/api/v1/patents/{patent_id}/summary", "post", "200")
        == "#/components/schemas/SummaryResponse"
    )
    assert (
        _response_schema_ref(spec, "/api/v1/patents/{patent_id}/chat", "post", "200")
        == "#/components/schemas/ChatResponse"
    )


def test_openapi_contains_error_response_statuses_for_real_endpoints():
    spec = client.get("/openapi.json").json()

    assert "502" in spec["paths"]["/api/v1/search"]["post"]["responses"]
    assert "503" in spec["paths"]["/api/v1/search"]["post"]["responses"]
    assert _response_schema_ref(spec, "/api/v1/search", "post", "422") == "#/components/schemas/ErrorResponse"
    assert _response_schema_ref(spec, "/api/v1/search", "post", "502") == "#/components/schemas/ErrorResponse"
    assert _response_schema_ref(spec, "/api/v1/search", "post", "503") == "#/components/schemas/ErrorResponse"
    assert _response_schema_ref(spec, "/api/v1/patents/{patent_id}", "get", "404") == "#/components/schemas/ErrorResponse"
    assert "404" in spec["paths"]["/api/v1/patents/{patent_id}/summary"]["post"]["responses"]
    assert "502" in spec["paths"]["/api/v1/patents/{patent_id}/summary"]["post"]["responses"]
    assert "503" in spec["paths"]["/api/v1/patents/{patent_id}/summary"]["post"]["responses"]
    assert (
        _response_schema_ref(spec, "/api/v1/patents/{patent_id}/summary", "post", "404")
        == "#/components/schemas/ErrorResponse"
    )
    assert (
        _response_schema_ref(spec, "/api/v1/patents/{patent_id}/summary", "post", "422")
        == "#/components/schemas/ErrorResponse"
    )
    assert (
        _response_schema_ref(spec, "/api/v1/patents/{patent_id}/summary", "post", "502")
        == "#/components/schemas/ErrorResponse"
    )
    assert (
        _response_schema_ref(spec, "/api/v1/patents/{patent_id}/summary", "post", "503")
        == "#/components/schemas/ErrorResponse"
    )
    assert "404" in spec["paths"]["/api/v1/patents/{patent_id}/chat"]["post"]["responses"]
    assert "502" in spec["paths"]["/api/v1/patents/{patent_id}/chat"]["post"]["responses"]
    assert "503" in spec["paths"]["/api/v1/patents/{patent_id}/chat"]["post"]["responses"]
    assert (
        _response_schema_ref(spec, "/api/v1/patents/{patent_id}/chat", "post", "404")
        == "#/components/schemas/ErrorResponse"
    )
    assert (
        _response_schema_ref(spec, "/api/v1/patents/{patent_id}/chat", "post", "422")
        == "#/components/schemas/ErrorResponse"
    )
    assert (
        _response_schema_ref(spec, "/api/v1/patents/{patent_id}/chat", "post", "502")
        == "#/components/schemas/ErrorResponse"
    )
    assert (
        _response_schema_ref(spec, "/api/v1/patents/{patent_id}/chat", "post", "503")
        == "#/components/schemas/ErrorResponse"
    )


def _response_schema_ref(spec: dict, path: str, method: str, status_code: str) -> str:
    return spec["paths"][path][method]["responses"][status_code]["content"]["application/json"]["schema"]["$ref"]
