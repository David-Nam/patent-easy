from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_search_mock_patents():
    response = client.post(
        "/api/v1/search",
        json={
            "query": "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능",
            "page": 1,
            "page_size": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["extracted"]["keywords"][0] == "음식 이미지 인식"
    assert payload["pagination"]["total_count"] >= 1
    assert payload["results"][0]["patent_id"] == "10-2023-0098765"


def test_get_patent_detail():
    response = client.get("/api/v1/patents/10-2023-0098765")

    assert response.status_code == 200
    payload = response.json()
    assert payload["patent_id"] == "10-2023-0098765"
    assert payload["claims"][0]["number"] == 1


def test_summarize_patent():
    response = client.post(
        "/api/v1/patents/10-2023-0098765/summary",
        json={"user_query": "음식 사진으로 칼로리를 계산하는 배달앱 기능"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["patent_id"] == "10-2023-0098765"
    assert payload["is_cached"] is False
    assert payload["key_tags"]


def test_patent_not_found():
    response = client.get("/api/v1/patents/not-found")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PATENT_NOT_FOUND"
