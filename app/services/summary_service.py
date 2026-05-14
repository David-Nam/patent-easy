from __future__ import annotations

from typing import Protocol

from app.config import Settings, get_settings
from app.schemas.patent import PatentDetail
from app.schemas.summary import SummaryRequest, SummaryResponse
from app.services.cache import SQLiteCache, normalize_cache_key
from app.services.kipris_client import KIPRISClient
from app.services.llm_client import LLMClient


class SummaryPatentNotFoundError(RuntimeError):
    """Raised when a patent detail cannot be found for summarization."""


class PatentDetailClientProtocol(Protocol):
    async def get_patent_detail(self, patent_id: str) -> PatentDetail:
        ...


class PatentSummaryClientProtocol(Protocol):
    async def summarize_patent(self, patent: PatentDetail, user_query: str | None = None) -> SummaryResponse:
        ...


class SummaryService:
    def __init__(
        self,
        detail_client: PatentDetailClientProtocol | None = None,
        llm_client: PatentSummaryClientProtocol | None = None,
        cache: SQLiteCache | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.detail_client = detail_client or KIPRISClient(settings=self.settings)
        self.llm_client = llm_client or LLMClient(settings=self.settings)
        self.cache = cache if cache is not None else SQLiteCache()

    async def summarize(self, patent_id: str, request: SummaryRequest) -> SummaryResponse:
        cache_key = self._summary_cache_key(patent_id, request)
        cached_summary = self.cache.get(cache_key)
        if cached_summary is not None:
            return SummaryResponse.model_validate(cached_summary).model_copy(update={"is_cached": True})

        patent = await self.detail_client.get_patent_detail(patent_id)
        if patent is None:
            raise SummaryPatentNotFoundError(f"Patent not found: {patent_id}")

        summary = await self.llm_client.summarize_patent(patent, request.user_query)
        summary = summary.model_copy(update={"is_cached": False})
        self.cache.set(
            cache_key,
            summary.model_dump(mode="json"),
            self.settings.cache_ttl_summary,
        )
        return summary

    def _summary_cache_key(self, patent_id: str, request: SummaryRequest) -> str:
        return normalize_cache_key(
            "summary",
            {
                "patent_id": patent_id,
                "user_query": request.user_query,
                "provider": self.settings.llm_provider,
                "gemini_model": self.settings.gemini_model,
                "openai_model": self.settings.openai_model,
            },
        )
