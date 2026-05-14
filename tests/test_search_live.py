import os

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.routers.search import get_search_service
from app.schemas.search import ExtractedQuery
from app.services.kipris_client import KIPRISClient
from app.services.search_service import SearchService


pytestmark = pytest.mark.live_kipris

client = TestClient(app)


def test_search_endpoint_calls_live_kipris_api():
    if os.getenv("RUN_LIVE_KIPRIS") != "1":
        pytest.skip("Set RUN_LIVE_KIPRIS=1 to call the real KIPRIS API")

    settings = get_settings()
    if not settings.kipris_api_key:
        pytest.skip("KIPRIS_API_KEY is required for live KIPRIS validation")

    app.dependency_overrides[get_search_service] = lambda: SearchService(
        query_builder=StaticQueryBuilder(),
        kipris_client=KIPRISClient(cache_enabled=False),
    )
    try:
        response = client.post(
            "/api/v1/search",
            json={
                "query": "자동차 관련 특허를 찾아줘",
                "page": 1,
                "page_size": 3,
            },
        )
    finally:
        app.dependency_overrides.pop(get_search_service, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["extracted"]["keywords"] == ["자동차"]
    assert payload["pagination"]["page"] == 1
    assert payload["pagination"]["page_size"] == 3
    assert payload["pagination"]["total_count"] >= len(payload["results"])
    assert len(payload["results"]) >= 1
    assert payload["results"][0]["patent_id"]
    assert payload["results"][0]["title"]


class StaticQueryBuilder:
    async def build(self, _user_query: str) -> ExtractedQuery:
        return ExtractedQuery(
            keywords=["자동차"],
            ipc_codes=["B60"],
            expanded_terms={"자동차": ["차량", "전기자동차", "모빌리티"]},
        )
