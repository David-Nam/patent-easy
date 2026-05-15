import asyncio
import json

import httpx
import pytest

from app.config import Settings
from app.schemas.chat import ChatRequest
from app.schemas.patent import Claim, PatentDetail, PatentListItem
from app.services.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMParseError,
    LLMProviderError,
)


def test_mock_provider_summarizes_patent():
    async def run() -> None:
        client = LLMClient(settings=_settings(llm_provider="mock"))
        summary = await client.summarize_patent(_sample_patent(), "배터리 열관리 서비스")

        assert summary.patent_id == "10-2023-0147601"
        assert summary.core_summary
        assert summary.business_application
        assert summary.is_cached is False

    asyncio.run(run())


def test_mock_provider_answers_chat_with_sources():
    async def run() -> None:
        client = LLMClient(settings=_settings(llm_provider="mock"))
        response = await client.chat_about_patent(
            _sample_patent(),
            ChatRequest(question="이 특허가 배터리 열관리 기능과 관련 있어?"),
        )

        assert response.patent_id == "10-2023-0147601"
        assert response.answer
        assert response.sources
        assert response.sources[0].type == "claim"
        assert response.is_cached is False

    asyncio.run(run())


def test_gemini_provider_posts_structured_summary_request():
    async def run() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            body = json.loads(request.content.decode("utf-8"))
            assert request.url.path == "/v1beta/models/gemini-test:generateContent"
            assert request.headers["x-goog-api-key"] == "gemini-key"
            assert body["generationConfig"]["responseMimeType"] == "application/json"
            assert body["generationConfig"]["responseJsonSchema"]["required"] == [
                "core_summary",
                "business_application",
                "key_tags",
            ]
            return httpx.Response(200, json=_gemini_response(_summary_payload()))

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = LLMClient(
                settings=_settings(
                    llm_provider="gemini",
                    gemini_api_key="gemini-key",
                    gemini_model="gemini-test",
                ),
                http_client=async_client,
            )
            summary = await client.summarize_patent(_sample_patent(), "배터리 열관리 서비스")
        finally:
            await async_client.aclose()

        assert len(requests) == 1
        assert summary.core_summary == "배터리 열관리 모드를 도출하는 특허입니다."
        assert client.last_token_usage is not None
        assert client.last_token_usage.model == "gemini-test"
        assert client.last_token_usage.total_tokens == 42

    asyncio.run(run())


def test_gemini_provider_posts_structured_chat_request_and_maps_sources():
    async def run() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            body = json.loads(request.content.decode("utf-8"))
            assert request.url.path == "/v1beta/models/gemini-test:generateContent"
            assert body["generationConfig"]["responseJsonSchema"]["required"] == [
                "answer",
                "source_ids",
            ]
            prompt = body["contents"][0]["parts"][0]["text"]
            assert '"source_id": "claim:1"' in prompt
            return httpx.Response(200, json=_gemini_response(_chat_payload()))

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = LLMClient(
                settings=_settings(
                    llm_provider="gemini",
                    gemini_api_key="gemini-key",
                    gemini_model="gemini-test",
                ),
                http_client=async_client,
            )
            response = await client.chat_about_patent(
                _sample_patent(),
                ChatRequest(
                    question="이 특허가 배터리 열관리 기능과 관련 있어?",
                    history=[{"role": "user", "content": "핵심을 알려줘."}],
                ),
            )
        finally:
            await async_client.aclose()

        assert len(requests) == 1
        assert response.answer == "청구항 1 기준으로 배터리 열관리 기능과 관련이 있습니다."
        assert response.sources[0].type == "claim"
        assert response.sources[0].claim_number == 1
        assert "전기자동차 배터리" in response.sources[0].snippet

    asyncio.run(run())


def test_llm_usage_logs_provider_model_and_tokens_without_api_key(caplog):
    async def run() -> None:
        async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=_gemini_response(_summary_payload())))
        )
        try:
            client = LLMClient(
                settings=_settings(
                    llm_provider="gemini",
                    gemini_api_key="gemini-key",
                    gemini_model="gemini-test",
                ),
                http_client=async_client,
            )
            with caplog.at_level("INFO", logger="app.services.llm_client"):
                await client.summarize_patent(_sample_patent(), "배터리 열관리 서비스")
        finally:
            await async_client.aclose()

        assert "llm usage provider=gemini model=gemini-test" in caplog.text
        assert "prompt_tokens=20 completion_tokens=22 total_tokens=42" in caplog.text
        assert "gemini-key" not in caplog.text

    asyncio.run(run())


def test_openai_provider_posts_json_mode_rerank_request():
    async def run() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            body = json.loads(request.content.decode("utf-8"))
            assert request.url.path == "/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer openai-key"
            assert body["model"] == "openai-test"
            assert body["response_format"] == {"type": "json_object"}
            return httpx.Response(200, json=_openai_response(_rerank_payload()))

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = LLMClient(
                settings=_settings(
                    llm_provider="openai",
                    openai_api_key="openai-key",
                    openai_model="openai-test",
                ),
                http_client=async_client,
            )
            reranked = await client.rerank_results("전기차 배터리 열관리", _sample_results())
        finally:
            await async_client.aclose()

        assert len(requests) == 1
        assert [item.patent_id for item in reranked] == ["p2", "p1"]
        assert reranked[0].relevance_score == 97
        assert reranked[0].tags == ["배터리", "열관리"]

    asyncio.run(run())


def test_provider_retries_invalid_json_response():
    async def run() -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(200, json=_gemini_text_response("not json"))
            return httpx.Response(200, json=_gemini_response(_summary_payload()))

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = LLMClient(
                settings=_settings(llm_provider="gemini", gemini_api_key="gemini-key"),
                http_client=async_client,
                max_retries=2,
            )
            summary = await client.summarize_patent(_sample_patent())
        finally:
            await async_client.aclose()

        assert calls == 2
        assert summary.key_tags == ["배터리", "열관리", "전기차"]

    asyncio.run(run())


def test_provider_raises_after_retry_exhaustion():
    async def run() -> None:
        async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=_gemini_text_response("not json")))
        )
        try:
            client = LLMClient(
                settings=_settings(llm_provider="gemini", gemini_api_key="gemini-key"),
                http_client=async_client,
                max_retries=1,
            )
            with pytest.raises(LLMParseError):
                await client.summarize_patent(_sample_patent())
        finally:
            await async_client.aclose()

    asyncio.run(run())


def test_missing_provider_key_raises_configuration_error():
    async def run() -> None:
        client = LLMClient(settings=_settings(llm_provider="gemini", gemini_api_key=None))
        with pytest.raises(LLMConfigurationError):
            await client.summarize_patent(_sample_patent())

    asyncio.run(run())


def test_provider_http_error_raises_provider_error():
    async def run() -> None:
        async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(503, json={"error": "unavailable"}))
        )
        try:
            client = LLMClient(
                settings=_settings(llm_provider="gemini", gemini_api_key="gemini-key"),
                http_client=async_client,
            )
            with pytest.raises(LLMProviderError):
                await client.summarize_patent(_sample_patent())
        finally:
            await async_client.aclose()

    asyncio.run(run())


def _settings(**overrides) -> Settings:
    values = {
        "llm_provider": "mock",
        "gemini_api_key": "gemini-key",
        "gemini_model": "gemini-test",
        "openai_api_key": "openai-key",
        "openai_model": "openai-test",
    }
    values.update(overrides)
    return Settings(**values)


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
        claims=[Claim(number=1, text="전기자동차 배터리의 온도와 주행 데이터를 이용하여 열관리 모드를 결정한다.")],
    )


def _sample_results() -> list[PatentListItem]:
    return [
        PatentListItem(
            patent_id="p1",
            title="자동차 표시 장치",
            applicant="테스트",
            application_date="2024-01-01",
            ipc_codes=["G02B"],
            relevance_score=60,
            tags=[],
            abstract_preview="차량 전방 정보를 표시한다.",
        ),
        PatentListItem(
            patent_id="p2",
            title="전기자동차 배터리 열관리 시스템",
            applicant="테스트",
            application_date="2024-01-01",
            ipc_codes=["B60L"],
            relevance_score=80,
            tags=[],
            abstract_preview="배터리 온도에 따라 열관리 모드를 제어한다.",
        ),
    ]


def _summary_payload() -> dict:
    return {
        "core_summary": "배터리 열관리 모드를 도출하는 특허입니다.",
        "business_application": "전기차 서비스의 배터리 보호 기능을 기획할 때 참고할 수 있습니다.",
        "key_tags": ["배터리", "열관리", "전기차"],
    }


def _rerank_payload() -> dict:
    return {
        "items": [
            {"patent_id": "p2", "relevance_score": 97, "tags": ["배터리", "열관리"]},
            {"patent_id": "p1", "relevance_score": 35, "tags": ["표시"]},
        ]
    }


def _chat_payload() -> dict:
    return {
        "answer": "청구항 1 기준으로 배터리 열관리 기능과 관련이 있습니다.",
        "source_ids": ["claim:1", "missing-source"],
    }


def _gemini_response(payload: dict) -> dict:
    response = _gemini_text_response(json.dumps(payload, ensure_ascii=False))
    response["usageMetadata"] = {
        "promptTokenCount": 20,
        "candidatesTokenCount": 22,
        "totalTokenCount": 42,
    }
    return response


def _gemini_text_response(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def _openai_response(payload: dict) -> dict:
    return {
        "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 22, "total_tokens": 42},
    }
