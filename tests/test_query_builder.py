import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.services.query_builder import (
    QueryBuilder,
    QueryBuilderConfigurationError,
    QueryBuilderParseError,
    QueryBuilderProviderError,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPT_CASES_PATH = ROOT_DIR / "data" / "keyword_prompt_cases.json"


def test_mock_provider_returns_structured_cases():
    async def run() -> None:
        builder = QueryBuilder(settings=_settings(llm_provider="mock"))
        cases = json.loads(PROMPT_CASES_PATH.read_text(encoding="utf-8"))

        for case in cases:
            extracted = await builder.build(case["query"])
            assert extracted.keywords == case["expected_keywords"]
            assert extracted.ipc_codes == case["expected_ipc_codes"]
            assert set(extracted.keywords) == set(extracted.expanded_terms)

    asyncio.run(run())


def test_gemini_provider_posts_structured_output_request():
    async def run() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            body = json.loads(request.content.decode("utf-8"))
            assert request.url.path == "/v1beta/models/gemini-test:generateContent"
            assert request.url.params["key"] == "gemini-key"
            assert body["generationConfig"]["responseMimeType"] == "application/json"
            assert body["generationConfig"]["responseSchema"]["required"] == [
                "keywords",
                "ipc_codes",
                "expanded_terms",
            ]
            return httpx.Response(200, json=_gemini_response(_valid_extracted_payload()))

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            builder = QueryBuilder(
                settings=_settings(
                    llm_provider="gemini",
                    gemini_api_key="gemini-key",
                    gemini_model="gemini-test",
                ),
                http_client=async_client,
            )
            extracted = await builder.build("배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능")
        finally:
            await async_client.aclose()

        assert len(requests) == 1
        assert extracted.keywords == ["음식 이미지 인식", "칼로리 자동 계산", "맞춤형 식단 추천"]

    asyncio.run(run())


def test_openai_provider_posts_json_mode_request():
    async def run() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            body = json.loads(request.content.decode("utf-8"))
            assert request.url.path == "/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer openai-key"
            assert body["model"] == "openai-test"
            assert body["response_format"] == {"type": "json_object"}
            return httpx.Response(200, json=_openai_response(_valid_extracted_payload()))

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            builder = QueryBuilder(
                settings=_settings(
                    llm_provider="openai",
                    openai_api_key="openai-key",
                    openai_model="openai-test",
                ),
                http_client=async_client,
            )
            extracted = await builder.build("배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능")
        finally:
            await async_client.aclose()

        assert len(requests) == 1
        assert extracted.ipc_codes == ["G06V", "G06N", "A23L"]

    asyncio.run(run())


def test_provider_retries_invalid_json_response():
    async def run() -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(200, json=_gemini_text_response("not json"))
            return httpx.Response(200, json=_gemini_response(_valid_extracted_payload()))

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            builder = QueryBuilder(
                settings=_settings(llm_provider="gemini", gemini_api_key="gemini-key"),
                http_client=async_client,
                max_retries=2,
            )
            extracted = await builder.build("배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능")
        finally:
            await async_client.aclose()

        assert calls == 2
        assert extracted.keywords[0] == "음식 이미지 인식"

    asyncio.run(run())


def test_provider_raises_after_retry_exhaustion():
    async def run() -> None:
        async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=_gemini_text_response("not json")))
        )
        try:
            builder = QueryBuilder(
                settings=_settings(llm_provider="gemini", gemini_api_key="gemini-key"),
                http_client=async_client,
                max_retries=1,
            )
            with pytest.raises(QueryBuilderParseError):
                await builder.build("배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능")
        finally:
            await async_client.aclose()

    asyncio.run(run())


def test_missing_provider_key_raises_configuration_error():
    async def run() -> None:
        builder = QueryBuilder(settings=_settings(llm_provider="gemini", gemini_api_key=None))
        with pytest.raises(QueryBuilderConfigurationError):
            await builder.build("배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능")

    asyncio.run(run())


def test_provider_http_error_raises_provider_error():
    async def run() -> None:
        async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(503, json={"error": "unavailable"}))
        )
        try:
            builder = QueryBuilder(
                settings=_settings(llm_provider="gemini", gemini_api_key="gemini-key"),
                http_client=async_client,
            )
            with pytest.raises(QueryBuilderProviderError):
                await builder.build("배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능")
        finally:
            await async_client.aclose()

    asyncio.run(run())


def test_unsupported_provider_raises_configuration_error():
    async def run() -> None:
        builder = QueryBuilder(settings=_settings(llm_provider="unknown"))
        with pytest.raises(QueryBuilderConfigurationError):
            await builder.build("배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능")

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


def _valid_extracted_payload() -> dict:
    return {
        "keywords": ["음식 이미지 인식", "칼로리 자동 계산", "맞춤형 식단 추천"],
        "ipc_codes": ["G06V", "G06N", "A23L"],
        "expanded_terms": {
            "음식 이미지 인식": ["식품 영상 인식", "음식 사진 식별", "식품 객체 검출"],
            "칼로리 자동 계산": ["열량 산출", "영양성분 분석", "식품 영양 추정"],
            "맞춤형 식단 추천": ["개인화 식단", "건강 상태 기반 추천", "영양 관리"],
        },
    }


def _gemini_response(payload: dict) -> dict:
    return _gemini_text_response(json.dumps(payload, ensure_ascii=False))


def _gemini_text_response(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def _openai_response(payload: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}
