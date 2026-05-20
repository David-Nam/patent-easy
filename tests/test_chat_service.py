import asyncio
from datetime import datetime, timezone

from app.config import Settings
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource
from app.schemas.patent import Claim, PatentDetail
from app.services.cache import SQLiteCache
from app.services.chat_service import ChatService


def test_chat_service_generates_and_caches_response(tmp_path):
    async def run() -> None:
        detail_client = FakeDetailClient(_sample_patent())
        llm_client = FakeLLMClient()
        service = ChatService(
            detail_client=detail_client,
            llm_client=llm_client,
            cache=SQLiteCache(tmp_path / "cache.sqlite"),
            settings=Settings(llm_provider="gemini", gemini_model="gemini-test"),
        )
        request = ChatRequest(
            question="이 특허가 배터리 열관리 앱과 관련 있어?",
            user_query="전기차 배터리 열관리",
        )

        first = await service.chat("10-2023-0147601", request)
        second = await service.chat("10-2023-0147601", request)

        assert first.is_cached is False
        assert second.is_cached is True
        assert first.answer == second.answer
        assert detail_client.calls == 1
        assert llm_client.calls == 1
        assert llm_client.received_request.question == "이 특허가 배터리 열관리 앱과 관련 있어?"

    asyncio.run(run())


def test_chat_service_uses_history_in_cache_key(tmp_path):
    async def run() -> None:
        detail_client = FakeDetailClient(_sample_patent())
        llm_client = FakeLLMClient()
        service = ChatService(
            detail_client=detail_client,
            llm_client=llm_client,
            cache=SQLiteCache(tmp_path / "cache.sqlite"),
            settings=Settings(llm_provider="gemini", gemini_model="gemini-test"),
        )

        await service.chat(
            "10-2023-0147601",
            ChatRequest(question="관련 있어?", history=[]),
        )
        await service.chat(
            "10-2023-0147601",
            ChatRequest(
                question="관련 있어?",
                history=[{"role": "user", "content": "앞에서 핵심을 물어봤어."}],
            ),
        )

        assert detail_client.calls == 2
        assert llm_client.calls == 2

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
        self.received_request: ChatRequest | None = None

    async def chat_about_patent(self, patent: PatentDetail, request: ChatRequest) -> ChatResponse:
        self.calls += 1
        self.received_request = request
        return ChatResponse(
            patent_id=patent.patent_id,
            answer="청구항 1 기준으로 배터리 열관리 기능과 관련이 있습니다.",
            sources=[
                ChatSource(
                    type="claim",
                    claim_number=1,
                    snippet="전기자동차 배터리의 온도와 주행 데이터를 이용하여 열관리 모드를 결정한다.",
                )
            ],
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
