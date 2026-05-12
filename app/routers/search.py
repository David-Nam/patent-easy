from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.search import SearchRequest, SearchResponse
from app.services.kipris_client import (
    KIPRISConfigurationError,
    KIPRISParseError,
    KIPRISUpstreamError,
)
from app.services.query_builder import (
    QueryBuilderConfigurationError,
    QueryBuilderParseError,
    QueryBuilderProviderError,
)
from app.services.search_service import SearchService


router = APIRouter(tags=["search"])


@lru_cache
def get_search_service() -> SearchService:
    return SearchService()


@router.post("/search", response_model=SearchResponse)
async def search_patents(
    request: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    try:
        return await service.search(request)
    except (QueryBuilderConfigurationError, KIPRISConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "SEARCH_CONFIGURATION_ERROR",
                "message": str(exc),
            },
        ) from exc
    except (
        QueryBuilderProviderError,
        QueryBuilderParseError,
        KIPRISUpstreamError,
        KIPRISParseError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "SEARCH_UPSTREAM_ERROR",
                "message": str(exc),
            },
        ) from exc
