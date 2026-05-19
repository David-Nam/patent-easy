from fastapi.testclient import TestClient

from app.main import app
from app.routers.patents import get_patent_detail_client
from app.schemas.patent import Claim, PatentDetail, PatentListItem
from app.services.kipris_client import KIPRISConfigurationError, KIPRISParseError, KIPRISUpstreamError


client = TestClient(app)


def test_patent_detail_endpoint_returns_kipris_detail():
    app.dependency_overrides[get_patent_detail_client] = lambda: StaticPatentDetailClient()
    try:
        response = client.get("/api/v1/patents/10-2023-0147601")
    finally:
        app.dependency_overrides.pop(get_patent_detail_client, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["patent_id"] == "10-2023-0147601"
    assert payload["title"] == "전기자동차의 배터리 열관리 시스템 및 이의 운용 방법"
    assert payload["status"] == "등록"
    assert payload["original_url"].endswith("applno=1020230147601&right=kpat")
    assert payload["claims"][0]["number"] == 1


def test_similar_patents_endpoint_searches_kipris_and_excludes_current_patent():
    static_client = StaticPatentDetailClient()
    app.dependency_overrides[get_patent_detail_client] = lambda: static_client
    try:
        response = client.get("/api/v1/patents/10-2023-0147601/similar?limit=2")
    finally:
        app.dependency_overrides.pop(get_patent_detail_client, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["patent_id"] == "10-2023-0147601"
    assert payload["strategy"] == "kipris_title_ipc_search"
    assert [item["patent_id"] for item in payload["results"]] == [
        "10-2022-0033592",
        "10-2021-0001111",
    ]
    assert "전기자동차" in static_client.received_keywords
    assert static_client.received_page_size == 7


def test_similar_patents_endpoint_maps_not_found():
    app.dependency_overrides[get_patent_detail_client] = lambda: EmptyPatentDetailClient()
    try:
        response = client.get("/api/v1/patents/not-found/similar")
    finally:
        app.dependency_overrides.pop(get_patent_detail_client, None)

    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == "PATENT_NOT_FOUND"


def test_similar_patents_endpoint_maps_kipris_errors_to_similar_scope():
    app.dependency_overrides[get_patent_detail_client] = lambda: ErrorPatentDetailClient(
        KIPRISConfigurationError("KIPRIS_API_KEY is required")
    )
    try:
        response = client.get("/api/v1/patents/10-2023-0147601/similar")
    finally:
        app.dependency_overrides.pop(get_patent_detail_client, None)

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "SIMILAR_CONFIGURATION_ERROR"


def test_patent_detail_endpoint_maps_not_found():
    app.dependency_overrides[get_patent_detail_client] = lambda: EmptyPatentDetailClient()
    try:
        response = client.get("/api/v1/patents/not-found")
    finally:
        app.dependency_overrides.pop(get_patent_detail_client, None)

    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == "PATENT_NOT_FOUND"
    assert payload["details"]["patent_id"] == "not-found"


def test_patent_detail_endpoint_maps_configuration_errors():
    app.dependency_overrides[get_patent_detail_client] = lambda: ErrorPatentDetailClient(
        KIPRISConfigurationError("KIPRIS_API_KEY is required")
    )
    try:
        response = client.get("/api/v1/patents/10-2023-0147601")
    finally:
        app.dependency_overrides.pop(get_patent_detail_client, None)

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "DETAIL_CONFIGURATION_ERROR"
    assert payload["details"] == {"source": "kipris", "kind": "configuration_error"}


def test_patent_detail_endpoint_maps_kipris_upstream_errors_with_details():
    app.dependency_overrides[get_patent_detail_client] = lambda: ErrorPatentDetailClient(
        KIPRISUpstreamError(
            "KIPRIS request timed out",
            code="KIPRIS_TIMEOUT",
            details={"kind": "timeout"},
        )
    )
    try:
        response = client.get("/api/v1/patents/10-2023-0147601")
    finally:
        app.dependency_overrides.pop(get_patent_detail_client, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "DETAIL_UPSTREAM_ERROR"
    assert payload["details"]["source"] == "kipris"
    assert payload["details"]["kind"] == "timeout"
    assert payload["details"]["upstream_code"] == "KIPRIS_TIMEOUT"


def test_patent_detail_endpoint_maps_kipris_xml_parse_errors():
    app.dependency_overrides[get_patent_detail_client] = lambda: ErrorPatentDetailClient(
        KIPRISParseError("KIPRIS response is not valid XML")
    )
    try:
        response = client.get("/api/v1/patents/10-2023-0147601")
    finally:
        app.dependency_overrides.pop(get_patent_detail_client, None)

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "DETAIL_UPSTREAM_ERROR"
    assert payload["details"] == {"source": "kipris", "kind": "xml_parse_error"}


class StaticPatentDetailClient:
    def __init__(self):
        self.received_keywords = None
        self.received_page_size = None

    async def get_patent_detail(self, _patent_id):
        return PatentDetail(
            patent_id="10-2023-0147601",
            title="전기자동차의 배터리 열관리 시스템 및 이의 운용 방법",
            applicant="서울대학교산학협력단",
            application_date="2023-10-31",
            ipc_codes=["B60H 1/32", "B60L 58/24"],
            status="등록",
            application_status="등록",
            relevance_score=100,
            tags=[],
            abstract_preview="주행 데이터에 따라 최적의 배터리 열관리 모드를 도출한다.",
            kipris_url="https://www.kipris.or.kr/khome/detail/newWindow.do?applno=1020230147601&right=kpat",
            original_url="https://www.kipris.or.kr/khome/detail/newWindow.do?applno=1020230147601&right=kpat",
            abstract="배터리 열관리 시스템에 관한 발명이다.",
            inventors=["김민수"],
            publication_date="2025-05-09",
            registration_date="2026-04-29",
            legal_status="등록결정(일반)",
            claims=[Claim(number=1, text="전기자동차에 동력을 제공하는 배터리와 제어부를 포함한다.")],
        )

    async def search_patents(self, keywords, filters=None, page=1, page_size=10):
        self.received_keywords = keywords
        self.received_page_size = page_size
        return [
            _list_item("10-2023-0147601", "전기자동차의 배터리 열관리 시스템"),
            _list_item("10-2022-0033592", "전기자동차 배터리 냉각 방법"),
            _list_item("10-2021-0001111", "차량 배터리 온도 제어 장치"),
        ]


class EmptyPatentDetailClient:
    async def get_patent_detail(self, _patent_id):
        return None


class ErrorPatentDetailClient:
    def __init__(self, exc):
        self.exc = exc

    async def get_patent_detail(self, _patent_id):
        raise self.exc


def _list_item(patent_id, title):
    return PatentListItem(
        patent_id=patent_id,
        title=title,
        applicant="테스트",
        application_date="2022-01-01",
        ipc_codes=["B60L"],
        status="공개",
        application_status="공개",
        relevance_score=90,
        similarity_score=90,
        tags=[],
        abstract_preview="전기자동차 배터리 제어 기술이다.",
        kipris_url=f"https://www.kipris.or.kr/khome/detail/newWindow.do?applno={patent_id}&right=kpat",
        original_url=f"https://www.kipris.or.kr/khome/detail/newWindow.do?applno={patent_id}&right=kpat",
    )
