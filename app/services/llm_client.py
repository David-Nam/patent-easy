from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings, get_settings
from app.schemas.patent import PatentDetail, PatentListItem
from app.schemas.summary import SummaryResponse
from app.services.mock_llm_client import mock_llm_client
from app.utils.logger import get_logger


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SUMMARY_PROMPT_PATH = PROMPTS_DIR / "summarize_patent.txt"
RERANK_PROMPT_PATH = PROMPTS_DIR / "rerank_results.txt"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
OPENAI_API_BASE_URL = "https://api.openai.com/v1"

logger = get_logger(__name__)


class LLMClientError(RuntimeError):
    """Base error for LLM client failures."""


class LLMConfigurationError(LLMClientError):
    """Raised when provider configuration is missing or invalid."""


class LLMProviderError(LLMClientError):
    """Raised when the upstream LLM provider request fails."""


class LLMParseError(LLMClientError):
    """Raised when an LLM provider returns invalid JSON or schema data."""


@dataclass(frozen=True)
class TokenUsage:
    provider: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


class _SummaryPayload(BaseModel):
    core_summary: str = Field(..., min_length=1)
    business_application: str = Field(..., min_length=1)
    key_tags: list[str] = Field(..., min_length=1, max_length=6)


class _RerankedItem(BaseModel):
    patent_id: str = Field(..., min_length=1)
    relevance_score: int = Field(..., ge=0, le=100)
    tags: list[str] = Field(default_factory=list, max_length=4)


class _RerankPayload(BaseModel):
    items: list[_RerankedItem] = Field(default_factory=list)


class LLMClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
        summary_prompt_path: Path = SUMMARY_PROMPT_PATH,
        rerank_prompt_path: Path = RERANK_PROMPT_PATH,
        max_retries: int = 2,
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client
        self.summary_prompt_template = summary_prompt_path.read_text(encoding="utf-8")
        self.rerank_prompt_template = rerank_prompt_path.read_text(encoding="utf-8")
        self.max_retries = max_retries
        self.last_token_usage: TokenUsage | None = None

    async def summarize_patent(self, patent: PatentDetail, user_query: str | None = None) -> SummaryResponse:
        provider = self.settings.llm_provider.lower()
        if provider == "mock":
            return mock_llm_client.summarize_patent(patent, user_query)

        prompt = self._render_summary_prompt(patent, user_query)
        payload = await self._generate_structured(
            prompt,
            schema=_summary_response_schema(provider),
            parser=_parse_summary_payload,
        )
        return SummaryResponse(
            patent_id=patent.patent_id,
            core_summary=payload.core_summary,
            business_application=payload.business_application,
            key_tags=payload.key_tags,
            generated_at=datetime.now(timezone.utc),
            is_cached=False,
        )

    async def rerank_results(self, query: str, results: list[PatentListItem]) -> list[PatentListItem]:
        provider = self.settings.llm_provider.lower()
        if not results:
            return []
        if provider == "mock":
            return sorted(results, key=lambda item: item.relevance_score, reverse=True)

        prompt = self._render_rerank_prompt(query, results)
        payload = await self._generate_structured(
            prompt,
            schema=_rerank_response_schema(provider),
            parser=_parse_rerank_payload,
        )
        return _apply_rerank_payload(results, payload)

    async def _generate_structured(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        parser: Callable[[str], Any],
    ) -> Any:
        provider = self.settings.llm_provider.lower()
        if provider == "gemini":
            caller = lambda rendered_prompt: self._call_gemini(rendered_prompt, schema)
        elif provider == "openai":
            caller = self._call_openai
        else:
            raise LLMConfigurationError(f"Unsupported LLM_PROVIDER: {self.settings.llm_provider}")

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            rendered_prompt = prompt
            if last_error is not None:
                rendered_prompt += (
                    "\n\nPrevious response failed validation. "
                    f"Return JSON only and fix this issue: {last_error}"
                )
            raw_text = await caller(rendered_prompt)
            try:
                return parser(raw_text)
            except LLMParseError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise

        raise LLMParseError("LLM response could not be parsed")

    async def _call_gemini(self, prompt: str, schema: dict[str, Any]) -> str:
        api_key = self.settings.gemini_api_key
        if not api_key:
            raise LLMConfigurationError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")

        url = f"{GEMINI_API_BASE_URL}/models/{self.settings.gemini_model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
                "temperature": 0.1,
            },
        }
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
            raise LLMConfigurationError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

        url = f"{OPENAI_API_BASE_URL}/chat/completions"
        payload = {
            "model": self.settings.openai_model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
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
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        try:
            if self.http_client is not None:
                response = await self.http_client.post(url, json=payload, headers=request_headers)
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload, headers=request_headers)
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"LLM provider request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LLMProviderError(f"LLM provider returned HTTP {response.status_code}")

        try:
            parsed = response.json()
        except json.JSONDecodeError as exc:
            raise LLMProviderError("LLM provider response is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMProviderError("LLM provider response must be a JSON object")
        return parsed

    def _render_summary_prompt(self, patent: PatentDetail, user_query: str | None) -> str:
        context = {
            "patent_id": patent.patent_id,
            "title": patent.title,
            "applicant": patent.applicant,
            "application_date": patent.application_date,
            "ipc_codes": patent.ipc_codes,
            "abstract": patent.abstract,
            "claims": [{"number": claim.number, "text": claim.text} for claim in patent.claims],
            "user_query": user_query,
        }
        return f"{self.summary_prompt_template}\n\nPatent context:\n{_json_dumps(context)}"

    def _render_rerank_prompt(self, query: str, results: list[PatentListItem]) -> str:
        context = {
            "user_query": query,
            "candidates": [
                {
                    "patent_id": item.patent_id,
                    "title": item.title,
                    "applicant": item.applicant,
                    "application_date": item.application_date,
                    "ipc_codes": item.ipc_codes,
                    "abstract_preview": item.abstract_preview,
                    "current_relevance_score": item.relevance_score,
                }
                for item in results
            ],
        }
        return f"{self.rerank_prompt_template}\n\nRerank context:\n{_json_dumps(context)}"

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


def _parse_summary_payload(raw_text: str) -> _SummaryPayload:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LLMParseError("LLM summary response is not valid JSON") from exc

    try:
        return _SummaryPayload.model_validate(payload)
    except ValidationError as exc:
        raise LLMParseError("LLM summary response does not match schema") from exc


def _parse_rerank_payload(raw_text: str) -> _RerankPayload:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LLMParseError("LLM rerank response is not valid JSON") from exc

    try:
        return _RerankPayload.model_validate(payload)
    except ValidationError as exc:
        raise LLMParseError("LLM rerank response does not match schema") from exc


def _apply_rerank_payload(results: list[PatentListItem], payload: _RerankPayload) -> list[PatentListItem]:
    by_id = {item.patent_id: item for item in results}
    ranked: list[PatentListItem] = []
    seen: set[str] = set()
    for item in payload.items:
        original = by_id.get(item.patent_id)
        if original is None or item.patent_id in seen:
            continue
        ranked.append(
            original.model_copy(
                update={
                    "relevance_score": item.relevance_score,
                    "tags": item.tags or original.tags,
                }
            )
        )
        seen.add(item.patent_id)

    ranked.extend(item for item in results if item.patent_id not in seen)
    return ranked


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    try:
        return payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMProviderError("Gemini response did not include text content") from exc


def _extract_openai_text(payload: dict[str, Any]) -> str:
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMProviderError("OpenAI response did not include message content") from exc


def _extract_token_usage(provider: str, model: str, payload: dict[str, Any]) -> TokenUsage:
    if provider == "gemini":
        usage = payload.get("usageMetadata", {})
        return TokenUsage(
            provider=provider,
            model=model,
            prompt_tokens=_optional_int(usage.get("promptTokenCount")),
            completion_tokens=_optional_int(usage.get("candidatesTokenCount")),
            total_tokens=_optional_int(usage.get("totalTokenCount")),
        )
    usage = payload.get("usage", {})
    return TokenUsage(
        provider=provider,
        model=model,
        prompt_tokens=_optional_int(usage.get("prompt_tokens")),
        completion_tokens=_optional_int(usage.get("completion_tokens")),
        total_tokens=_optional_int(usage.get("total_tokens")),
    )


def _summary_response_schema(provider: str) -> dict[str, Any]:
    if provider == "gemini":
        return {
            "type": "object",
            "properties": {
                "core_summary": {"type": "string"},
                "business_application": {"type": "string"},
                "key_tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["core_summary", "business_application", "key_tags"],
            "propertyOrdering": ["core_summary", "business_application", "key_tags"],
        }
    return {
        "type": "object",
        "properties": {
            "core_summary": {"type": "string"},
            "business_application": {"type": "string"},
            "key_tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["core_summary", "business_application", "key_tags"],
        "additionalProperties": False,
    }


def _rerank_response_schema(provider: str) -> dict[str, Any]:
    if provider == "gemini":
        return {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "patent_id": {"type": "string"},
                            "relevance_score": {"type": "integer"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["patent_id", "relevance_score", "tags"],
                        "propertyOrdering": ["patent_id", "relevance_score", "tags"],
                    },
                }
            },
            "required": ["items"],
            "propertyOrdering": ["items"],
        }
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "patent_id": {"type": "string"},
                        "relevance_score": {"type": "integer"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["patent_id", "relevance_score", "tags"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


llm_client = LLMClient()
