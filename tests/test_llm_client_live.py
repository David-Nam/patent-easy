import asyncio
import os

import pytest

from app.config import get_settings
from app.schemas.patent import Claim, PatentDetail
from app.services.llm_client import LLMClient


pytestmark = pytest.mark.live_llm


def test_gemini_summary_live_call_with_configured_key():
    if os.getenv("RUN_LIVE_LLM") != "1":
        pytest.skip("Set RUN_LIVE_LLM=1 to call the real LLM provider API")

    settings = get_settings()
    if settings.llm_provider != "gemini":
        pytest.skip("Set LLM_PROVIDER=gemini for Gemini live validation")
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is required for Gemini live validation")

    async def run() -> None:
        client = LLMClient()
        summary = await client.summarize_patent(_sample_patent(), "전기차 배터리 열관리")

        assert summary.patent_id == "10-2023-0147601"
        assert summary.core_summary
        assert summary.business_application
        assert 1 <= len(summary.key_tags) <= 6
        assert client.last_token_usage is not None
        assert client.last_token_usage.provider == "gemini"

    asyncio.run(run())


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
