from __future__ import annotations

from typing import Protocol

from app.config import Settings, get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.patent import PatentDetail
from app.services.cache import SQLiteCache, normalize_cache_key
from app.services.kipris_client import KIPRISClient
from app.services.llm_client import LLMClient


class ChatPatentNotFoundError(RuntimeError):
    """Raised when a patent detail cannot be found for chat."""


class ChatDetailClientProtocol(Protocol):
    async def get_patent_detail(self, patent_id: str) -> PatentDetail:
        ...


class PatentChatClientProtocol(Protocol):
    async def chat_about_patent(self, patent: PatentDetail, request: ChatRequest) -> ChatResponse:
        ...


class ChatService:
    def __init__(
        self,
        detail_client: ChatDetailClientProtocol | None = None,
        llm_client: PatentChatClientProtocol | None = None,
        cache: SQLiteCache | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.detail_client = detail_client or KIPRISClient(settings=self.settings)
        self.llm_client = llm_client or LLMClient(settings=self.settings)
        self.cache = cache if cache is not None else SQLiteCache()

    async def chat(self, patent_id: str, request: ChatRequest) -> ChatResponse:
        cache_key = self._chat_cache_key(patent_id, request)
        cached_chat = self.cache.get(cache_key)
        if cached_chat is not None:
            return ChatResponse.model_validate(cached_chat).model_copy(update={"is_cached": True})

        patent = await self.detail_client.get_patent_detail(patent_id)
        if patent is None:
            raise ChatPatentNotFoundError(f"Patent not found: {patent_id}")

        response = await self.llm_client.chat_about_patent(patent, request)
        response = response.model_copy(update={"is_cached": False})
        self.cache.set(
            cache_key,
            response.model_dump(mode="json"),
            self.settings.cache_ttl_chat,
        )
        return response

    def _chat_cache_key(self, patent_id: str, request: ChatRequest) -> str:
        return normalize_cache_key(
            "chat",
            {
                "patent_id": patent_id,
                "request": request.model_dump(mode="json"),
                "provider": self.settings.llm_provider,
                "gemini_model": self.settings.gemini_model,
                "openai_model": self.settings.openai_model,
            },
        )
