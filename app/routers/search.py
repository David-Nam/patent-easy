from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

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
from app.utils.api_errors import error_response, raise_api_error


router = APIRouter(tags=["search"])


@lru_cache
def get_search_service() -> SearchService:
    return SearchService()


@router.post(
    "/search",
    response_model=SearchResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: error_response("Request validation error"),
        status.HTTP_502_BAD_GATEWAY: error_response("KIPRIS or LLM upstream error"),
        status.HTTP_503_SERVICE_UNAVAILABLE: error_response("Search provider configuration error"),
    },
)
async def search_patents(
    request: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    try:
        return await service.search(request)
    except (QueryBuilderConfigurationError, KIPRISConfigurationError) as exc:
        raise_api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SEARCH_CONFIGURATION_ERROR",
            message=str(exc),
            details=_configuration_error_details(exc),
        )
    except KIPRISUpstreamError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="SEARCH_UPSTREAM_ERROR",
            message=str(exc),
            details=_kipris_upstream_details(exc),
        )
    except KIPRISParseError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="SEARCH_UPSTREAM_ERROR",
            message=str(exc),
            details={"source": "kipris", "kind": "xml_parse_error"},
        )
    except QueryBuilderProviderError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="SEARCH_UPSTREAM_ERROR",
            message=str(exc),
            details={"source": "llm", "kind": "provider_error"},
        )
    except QueryBuilderParseError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="SEARCH_UPSTREAM_ERROR",
            message=str(exc),
            details={"source": "llm", "kind": "parse_error"},
        )


def _configuration_error_details(exc: Exception) -> dict[str, str]:
    source = "kipris" if isinstance(exc, KIPRISConfigurationError) else "llm"
    return {"source": source, "kind": "configuration_error"}


def _kipris_upstream_details(exc: KIPRISUpstreamError) -> dict[str, Any]:
    details: dict[str, Any] = {
        "source": "kipris",
        "kind": exc.details.get("kind", "upstream_error"),
    }
    if exc.code:
        details["upstream_code"] = exc.code
    details.update(exc.details)
    return details
