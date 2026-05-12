import asyncio
from datetime import datetime, timezone

from app.config import Settings
from app.schemas.patent import Claim, PatentDetail
from app.schemas.summary import SummaryRequest, SummaryResponse
from app.services.cache import SQLiteCache
from app.services.summary_service import SummaryService


def test_summary_service_generates_and_caches_summary(tmp_path):
    async def run() -> None:
        detail_client = FakeDetailClient(_sample_patent())
        llm_client = FakeLLMClient()
        service = SummaryService(
            detail_client=detail_client,
            llm_client=llm_client,
            cache=SQLiteCache(tmp_path / "cache.sqlite"),
            settings=Settings(llm_provider="gemini", gemini_model="gemini-test"),
        )
        request = SummaryRequest(user_query="전기차 배터리 열관리")

        first = await service.summarize("10-2023-0147601", request)
        second = await service.summarize("10-2023-0147601", request)

        assert first.is_cached is False
        assert second.is_cached is True
        assert first.core_summary == second.core_summary
        assert detail_client.calls == 1
        assert llm_client.calls == 1
        assert llm_client.received_user_query == "전기차 배터리 열관리"

    asyncio.run(run())


class FakeDetailClient:
    def __init__(self, patent: PatentDetail) -> None:
        self.patent = patent
        self.calls = 0

    async def get_patent_detail(self, _patent_id: str) -> PatentDetail:
        self.calls += 1
        return self.patent


class FakeLLMClient:
    def __init__(self) -> None:
        self.calls = 0
        self.received_user_query: str | None = None

    async def summarize_patent(self, patent: PatentDetail, user_query: str | None = None) -> SummaryResponse:
        self.calls += 1
        self.received_user_query = user_query
        return SummaryResponse(
            patent_id=patent.patent_id,
            core_summary="배터리 열관리 모드를 요약합니다.",
            business_application="전기차 배터리 보호 기능 기획에 활용할 수 있습니다.",
            key_tags=["배터리", "열관리", "전기차"],
            generated_at=datetime.now(timezone.utc),
            is_cached=False,
        )


def _sample_patent() -> PatentDetail:
    return PatentDetail(
        patent_id="10-2023-0147601",
        title="전기자동차의 배터리 열관리 시스템 및 이의 운용 방법",
        applicant="서울대학교산학협력단",
        application_date="2023-10-31",
        ipc_codes=["B60L 58/24"],
        relevance_score=100,
        tags=[],
        abstract_preview="배터리 열관리 모드를 도출한다.",
        kipris_url="https://www.kipris.or.kr/",
        abstract="주행 데이터에 따라 최적의 배터리 열관리 모드를 도출한다.",
        inventors=["김민수"],
        claims=[
            Claim(
                number=1,
                text="전기자동차 배터리의 온도와 주행 데이터를 이용하여 열관리 모드를 결정한다.",
            )
        ],
    )
