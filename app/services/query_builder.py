from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.schemas.search import ExtractedQuery
from app.services.mock_llm_client import mock_llm_client
from app.utils.logger import get_logger


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_keywords.txt"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
OPENAI_API_BASE_URL = "https://api.openai.com/v1"
logger = get_logger(__name__)


class QueryBuilderError(RuntimeError):
    """Base error for natural-language query extraction failures."""


class QueryBuilderConfigurationError(QueryBuilderError):
    """Raised when provider configuration is missing or invalid."""


class QueryBuilderProviderError(QueryBuilderError):
    """Raised when the upstream LLM provider request fails."""


class QueryBuilderParseError(QueryBuilderError):
    """Raised when the provider returns invalid JSON or schema data."""


@dataclass(frozen=True)
class QueryBuilderTokenUsage:
    provider: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


class QueryBuilder:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
        prompt_path: Path = PROMPT_PATH,
        max_retries: int = 2,
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client
        self.prompt_template = prompt_path.read_text(encoding="utf-8")
        self.max_retries = max_retries
        self.last_token_usage: QueryBuilderTokenUsage | None = None
        self.provider_call_count = 0

    async def build(self, user_query: str) -> ExtractedQuery:
        provider = self.settings.llm_provider.lower()
        if provider == "mock":
            return mock_llm_client.extract_keywords(user_query)
        if provider == "gemini":
            return await self._build_with_provider(user_query, self._call_gemini)
        if provider == "openai":
            return await self._build_with_provider(user_query, self._call_openai)
        raise QueryBuilderConfigurationError(f"Unsupported LLM_PROVIDER: {self.settings.llm_provider}")

    async def _build_with_provider(self, user_query: str, caller) -> ExtractedQuery:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            prompt = self._render_prompt(user_query, retry_context=last_error)
            raw_text = await caller(prompt)
            try:
                return _parse_extracted_query(raw_text)
            except QueryBuilderParseError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise

        raise QueryBuilderParseError("LLM response could not be parsed")

    async def _call_gemini(self, prompt: str) -> str:
        api_key = self.settings.gemini_api_key
        if not api_key:
            raise QueryBuilderConfigurationError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")

        url = f"{GEMINI_API_BASE_URL}/models/{self.settings.gemini_model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _gemini_response_schema(),
                "temperature": 0.1,
            },
        }
        self.provider_call_count += 1
        response = await self._post_json(
            url,
            payload,
            headers={"x-goog-api-key": api_key},
        )
        self._log_token_usage("gemini", self.settings.gemini_model, response)
        return _extract_gemini_text(response)

    async def _call_openai(self, prompt: str) -> str:
        api_key = self.settings.openai_api_key
        if not api_key:
            raise QueryBuilderConfigurationError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

        url = f"{OPENAI_API_BASE_URL}/chat/completions"
        payload = {
            "model": self.settings.openai_model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        self.provider_call_count += 1
        response = await self._post_json(
            url,
            payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self._log_token_usage("openai", self.settings.openai_model, response)
        return _extract_openai_text(response)

    async def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        try:
            if self.http_client is not None:
                response = await self.http_client.post(
                    url,
                    json=payload,
                    params=params,
                    headers=request_headers,
                )
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        params=params,
                        headers=request_headers,
                    )
        except httpx.HTTPError as exc:
            raise QueryBuilderProviderError(f"LLM provider request failed: {exc}") from exc

        if response.status_code >= 400:
            raise QueryBuilderProviderError(f"LLM provider returned HTTP {response.status_code}")

        try:
            parsed = response.json()
        except json.JSONDecodeError as exc:
            raise QueryBuilderProviderError("LLM provider response is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise QueryBuilderProviderError("LLM provider response must be a JSON object")
        return parsed

    def _render_prompt(self, user_query: str, retry_context: Exception | None = None) -> str:
        prompt = f"{self.prompt_template}\n\nUser input:\n{user_query.strip()}"
        if retry_context is not None:
            prompt += (
                "\n\nPrevious response failed validation. "
                f"Return JSON only and fix this issue: {retry_context}"
            )
        return prompt

    def _log_token_usage(self, provider: str, model: str, payload: dict[str, Any]) -> None:
        usage = _extract_token_usage(provider, model, payload)
        self.last_token_usage = usage
        logger.info(
            "llm usage provider=%s model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
            usage.provider,
            usage.model,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
        )


def _parse_extracted_query(raw_text: str) -> ExtractedQuery:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise QueryBuilderParseError("LLM response is not valid JSON") from exc

    try:
        extracted = ExtractedQuery.model_validate(payload)
    except ValidationError as exc:
        raise QueryBuilderParseError("LLM response does not match ExtractedQuery schema") from exc

    _validate_extracted_query(extracted)
    return extracted


def _validate_extracted_query(extracted: ExtractedQuery) -> None:
    if not 3 <= len(extracted.keywords) <= 5:
        raise QueryBuilderParseError("keywords must contain 3 to 5 items")
    if not 1 <= len(extracted.ipc_codes) <= 4:
        raise QueryBuilderParseError("ipc_codes must contain 1 to 4 items")
    missing_terms = [keyword for keyword in extracted.keywords if keyword not in extracted.expanded_terms]
    if missing_terms:
        raise QueryBuilderParseError(f"expanded_terms missing keywords: {', '.join(missing_terms)}")


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    try:
        return payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise QueryBuilderProviderError("Gemini response did not include text content") from exc


def _extract_openai_text(payload: dict[str, Any]) -> str:
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise QueryBuilderProviderError("OpenAI response did not include message content") from exc


def _extract_token_usage(provider: str, model: str, payload: dict[str, Any]) -> QueryBuilderTokenUsage:
    if provider == "gemini":
        usage = payload.get("usageMetadata", {})
        return QueryBuilderTokenUsage(
            provider=provider,
            model=model,
            prompt_tokens=_optional_int(usage.get("promptTokenCount")),
            completion_tokens=_optional_int(usage.get("candidatesTokenCount")),
            total_tokens=_optional_int(usage.get("totalTokenCount")),
        )
    usage = payload.get("usage", {})
    return QueryBuilderTokenUsage(
        provider=provider,
        model=model,
        prompt_tokens=_optional_int(usage.get("prompt_tokens")),
        completion_tokens=_optional_int(usage.get("completion_tokens")),
        total_tokens=_optional_int(usage.get("total_tokens")),
    )


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _gemini_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "keywords": {"type": "array", "items": {"type": "string"}},
            "ipc_codes": {"type": "array", "items": {"type": "string"}},
            "expanded_terms": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "required": ["keywords", "ipc_codes", "expanded_terms"],
        "propertyOrdering": ["keywords", "ipc_codes", "expanded_terms"],
    }


query_builder = QueryBuilder()
