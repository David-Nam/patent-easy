import asyncio
import os

import pytest

from app.config import get_settings
from app.services.query_builder import QueryBuilder


pytestmark = pytest.mark.live_llm


def test_query_builder_calls_live_gemini_structured_output():
    if os.getenv("RUN_LIVE_LLM") != "1":
        pytest.skip("Set RUN_LIVE_LLM=1 to call the real LLM provider")

    settings = get_settings()
    if settings.llm_provider != "gemini":
        pytest.skip("Set LLM_PROVIDER=gemini for Gemini live validation")
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is required for live Query Builder validation")

    async def run() -> None:
        builder = QueryBuilder()
        extracted = await builder.build("전기차 배터리 열관리 시스템")

        assert 3 <= len(extracted.keywords) <= 5
        assert 1 <= len(extracted.ipc_codes) <= 4
        assert set(extracted.keywords) == set(extracted.expanded_terms)
        assert builder.last_token_usage is not None
        assert builder.last_token_usage.provider == "gemini"

    asyncio.run(run())
