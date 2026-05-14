from __future__ import annotations

from math import ceil
from typing import Protocol

from app.schemas.search import (
    ExtractedQuery,
    Pagination,
    SearchFilters,
    SearchRequest,
    SearchResponse,
)
from app.services.kipris_client import KIPRISClient, PatentSearchPage
from app.services.query_builder import QueryBuilder


class QueryBuilderProtocol(Protocol):
    async def build(self, user_query: str) -> ExtractedQuery:
        ...


class KIPRISClientProtocol(Protocol):
    async def search_patent_page(
        self,
        keywords: list[str],
        filters: SearchFilters | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> PatentSearchPage:
        ...


class SearchService:
    def __init__(
        self,
        query_builder: QueryBuilderProtocol | None = None,
        kipris_client: KIPRISClientProtocol | None = None,
    ) -> None:
        self.query_builder = query_builder or QueryBuilder()
        self.kipris_client = kipris_client or KIPRISClient()

    async def search(self, request: SearchRequest) -> SearchResponse:
        extracted = await self.query_builder.build(request.query)
        search_page = await self.kipris_client.search_patent_page(
            keywords=_search_keywords(extracted, request.query),
            filters=request.filters,
            page=request.page,
            page_size=request.page_size,
        )

        return SearchResponse(
            query=request.query,
            extracted=extracted,
            pagination=Pagination(
                page=request.page,
                page_size=request.page_size,
                total_count=search_page.total_count,
                total_pages=max(1, ceil(search_page.total_count / request.page_size)),
            ),
            results=search_page.items,
        )


def _search_keywords(extracted: ExtractedQuery, fallback_query: str) -> list[str]:
    keywords = [keyword.strip() for keyword in extracted.keywords if keyword.strip()]
    if keywords:
        return keywords
    return [fallback_query.strip()]
