from fastapi.testclient import TestClient

from app.main import app
from app.routers.search import get_search_service
from app.routers.summary import get_summary_service
from app.services.mock_llm_client import mock_llm_client
from app.services.mock_patent_service import mock_patent_service


client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_search_mock_patents():
    app.dependency_overrides[get_search_service] = lambda: MockSearchService()
    try:
        response = client.post(
            "/api/v1/search",
            json={
                "query": "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능",
                "page": 1,
                "page_size": 10,
            },
        )
    finally:
        app.dependency_overrides.pop(get_search_service, None)

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
    app.dependency_overrides[get_summary_service] = lambda: MockSummaryService()
    try:
        response = client.post(
            "/api/v1/patents/10-2023-0098765/summary",
            json={"user_query": "음식 사진으로 칼로리를 계산하는 배달앱 기능"},
        )
    finally:
        app.dependency_overrides.pop(get_summary_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["patent_id"] == "10-2023-0098765"
    assert payload["is_cached"] is False
    assert payload["key_tags"]


def test_patent_not_found():
    response = client.get("/api/v1/patents/not-found")

    assert response.status_code == 404
    assert response.json()["code"] == "PATENT_NOT_FOUND"


def test_mock_keyword_cases_are_structured():
    queries = [
        "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능",
        "전기차 충전소 빈자리를 예측해서 운전자에게 추천하는 서비스",
        "중고차 사진과 보험 이력을 분석해서 수출 상담 답변을 자동으로 만들어주는 시스템",
        "스마트 거울이 사용자의 운동 자세를 보고 잘못된 자세를 알려주는 홈트레이닝 기능",
        "노인이 넘어지면 보호자에게 자동으로 알림을 보내는 웨어러블 기기",
        "자동차 앞유리에 길 안내와 위험 정보를 증강현실로 보여주는 기능",
        "약 복용 시간을 잊지 않도록 가족에게도 알림을 보내는 복약 관리 앱",
        "카메라로 재활용 쓰레기를 인식해서 분리배출 방법을 알려주는 서비스",
    ]

    for query in queries:
        extracted = mock_llm_client.extract_keywords(query)
        assert 3 <= len(extracted.keywords) <= 5
        assert extracted.ipc_codes
        assert set(extracted.keywords) == set(extracted.expanded_terms)


class MockSearchService:
    async def search(self, request):
        return mock_patent_service.search(request)


class MockSummaryService:
    async def summarize(self, patent_id, request):
        patent = mock_patent_service.get_detail(patent_id)
        if patent is None:
            return None
        return mock_llm_client.summarize_patent(patent, request.user_query)
