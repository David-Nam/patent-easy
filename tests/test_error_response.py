from fastapi.testclient import TestClient

from app.main import app
from app.routers.search import get_search_service


client = TestClient(app)
non_raising_client = TestClient(app, raise_server_exceptions=False)


def test_validation_errors_use_standard_error_response():
    response = client.post("/api/v1/search", json={"page": 0})

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["message"] == "요청 형식이 올바르지 않습니다."
    assert "errors" in payload["details"]
    assert "detail" not in payload


def test_framework_404_uses_standard_error_response():
    response = client.get("/missing-route")

    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == "HTTP_ERROR"
    assert payload["message"] == "Not Found"
    assert payload["details"]["status_code"] == 404
    assert "detail" not in payload


def test_unhandled_errors_use_standard_error_response():
    app.dependency_overrides[get_search_service] = lambda: RuntimeErrorSearchService()
    try:
        response = non_raising_client.post("/api/v1/search", json={"query": "전기차 배터리 열관리"})
    finally:
        app.dependency_overrides.pop(get_search_service, None)

    assert response.status_code == 500
    payload = response.json()
    assert payload["code"] == "INTERNAL_SERVER_ERROR"
    assert payload["message"] == "서버 내부 오류가 발생했습니다."
    assert "detail" not in payload


class RuntimeErrorSearchService:
    async def search(self, _request):
        raise RuntimeError("unexpected failure")
