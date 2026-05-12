import asyncio

from app.schemas.patent import PatentListItem
from app.schemas.search import ExtractedQuery, SearchRequest
from app.services.kipris_client import PatentSearchPage
from app.services.search_service import SearchService


def test_search_service_builds_response_from_query_builder_and_kipris():
    async def run() -> None:
        extracted = ExtractedQuery(
            keywords=["음식 이미지 인식", "칼로리 자동 계산", "맞춤형 식단 추천"],
            ipc_codes=["G06V", "G06N", "A23L"],
            expanded_terms={
                "음식 이미지 인식": ["식품 영상 인식"],
                "칼로리 자동 계산": ["영양성분 분석"],
                "맞춤형 식단 추천": ["개인화 식단"],
            },
        )
        patent = PatentListItem(
            patent_id="10-2023-0098765",
            title="음식 이미지 기반 칼로리 산출 시스템",
            applicant="테스트 주식회사",
            application_date="2023-06-01",
            ipc_codes=["G06V"],
            relevance_score=100,
            tags=[],
            abstract_preview="음식 사진을 분석하여 칼로리를 산출한다.",
            kipris_url="https://www.kipris.or.kr/",
        )
        query_builder = FakeQueryBuilder(extracted)
        kipris_client = FakeKIPRISClient(PatentSearchPage(items=[patent], total_count=42))
        service = SearchService(query_builder=query_builder, kipris_client=kipris_client)

        response = await service.search(
            SearchRequest(
                query="음식 사진으로 칼로리를 계산하는 기능",
                page=2,
                page_size=10,
            )
        )

        assert query_builder.received_query == "음식 사진으로 칼로리를 계산하는 기능"
        assert kipris_client.received_keywords == extracted.keywords
        assert kipris_client.received_page == 2
        assert kipris_client.received_page_size == 10
        assert response.extracted == extracted
        assert response.pagination.total_count == 42
        assert response.pagination.total_pages == 5
        assert response.results == [patent]

    asyncio.run(run())


class FakeQueryBuilder:
    def __init__(self, extracted: ExtractedQuery) -> None:
        self.extracted = extracted
        self.received_query: str | None = None

    async def build(self, user_query: str) -> ExtractedQuery:
        self.received_query = user_query
        return self.extracted


class FakeKIPRISClient:
    def __init__(self, search_page: PatentSearchPage) -> None:
        self.search_page = search_page
        self.received_keywords: list[str] | None = None
        self.received_page: int | None = None
        self.received_page_size: int | None = None

    async def search_patent_page(self, **kwargs) -> PatentSearchPage:
        self.received_keywords = kwargs["keywords"]
        self.received_page = kwargs["page"]
        self.received_page_size = kwargs["page_size"]
        return self.search_page
