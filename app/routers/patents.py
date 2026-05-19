from functools import lru_cache
import re
from typing import Annotated, Any, Protocol

from fastapi import APIRouter, Depends, Query, status

from app.schemas.patent import PatentDetail, PatentListItem, SimilarPatentsResponse
from app.services.kipris_client import (
    KIPRISClient,
    KIPRISConfigurationError,
    KIPRISParseError,
    KIPRISUpstreamError,
)
from app.utils.api_errors import error_response, raise_api_error


router = APIRouter(tags=["patents"])


class PatentDetailClientProtocol(Protocol):
    async def get_patent_detail(self, patent_id: str) -> PatentDetail | None:
        ...

    async def search_patents(
        self,
        keywords: list[str],
        filters: object | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> list[PatentListItem]:
        ...


@lru_cache
def get_patent_detail_client() -> KIPRISClient:
    return KIPRISClient()


@router.get(
    "/patents/{patent_id}",
    response_model=PatentDetail,
    responses={
        status.HTTP_404_NOT_FOUND: error_response("Patent not found"),
        status.HTTP_502_BAD_GATEWAY: error_response("KIPRIS upstream error"),
        status.HTTP_503_SERVICE_UNAVAILABLE: error_response("KIPRIS configuration error"),
    },
)
async def get_patent_detail(
    patent_id: str,
    client: Annotated[PatentDetailClientProtocol, Depends(get_patent_detail_client)],
) -> PatentDetail:
    return await _get_patent_detail_or_raise(patent_id, client)


@router.get(
    "/patents/{patent_id}/similar",
    response_model=SimilarPatentsResponse,
    responses={
        status.HTTP_404_NOT_FOUND: error_response("Patent not found"),
        status.HTTP_502_BAD_GATEWAY: error_response("KIPRIS upstream error"),
        status.HTTP_503_SERVICE_UNAVAILABLE: error_response("KIPRIS configuration error"),
    },
)
async def get_similar_patents(
    patent_id: str,
    client: Annotated[PatentDetailClientProtocol, Depends(get_patent_detail_client)],
    limit: int = Query(default=5, ge=1, le=10),
) -> SimilarPatentsResponse:
    patent = await _get_patent_detail_or_raise(patent_id, client, error_scope="SIMILAR")
    try:
        results = await client.search_patents(
            _similar_search_keywords(patent),
            page=1,
            page_size=min(50, limit + 5),
        )
    except KIPRISConfigurationError as exc:
        raise_api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SIMILAR_CONFIGURATION_ERROR",
            message=str(exc),
            details={"source": "kipris", "kind": "configuration_error"},
        )
    except KIPRISUpstreamError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="SIMILAR_UPSTREAM_ERROR",
            message=str(exc),
            details=_kipris_upstream_details(exc),
        )
    except KIPRISParseError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="SIMILAR_UPSTREAM_ERROR",
            message=str(exc),
            details={"source": "kipris", "kind": "xml_parse_error"},
        )

    current_id = _compact_patent_id(patent.patent_id)
    similar_results = [
        item
        for item in results
        if _compact_patent_id(item.patent_id) != current_id
    ][:limit]
    return SimilarPatentsResponse(
        patent_id=patent.patent_id,
        strategy="kipris_title_ipc_search",
        results=similar_results,
    )


async def _get_patent_detail_or_raise(
    patent_id: str,
    client: PatentDetailClientProtocol,
    error_scope: str = "DETAIL",
) -> PatentDetail:
    try:
        patent = await client.get_patent_detail(patent_id)
    except KIPRISConfigurationError as exc:
        raise_api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=f"{error_scope}_CONFIGURATION_ERROR",
            message=str(exc),
            details={"source": "kipris", "kind": "configuration_error"},
        )
    except KIPRISUpstreamError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code=f"{error_scope}_UPSTREAM_ERROR",
            message=str(exc),
            details=_kipris_upstream_details(exc),
        )
    except KIPRISParseError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code=f"{error_scope}_UPSTREAM_ERROR",
            message=str(exc),
            details={"source": "kipris", "kind": "xml_parse_error"},
        )

    if patent is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PATENT_NOT_FOUND",
            message="존재하지 않는 특허 ID입니다.",
            details={"patent_id": patent_id},
        )
    return patent


def _similar_search_keywords(patent: PatentDetail) -> list[str]:
    stopwords = {"및", "이의", "방법", "시스템", "장치", "포함", "위한", "the", "and", "for", "of"}
    title_tokens = [
        _normalize_title_token(token)
        for token in re.split(r"[\s,/()·]+", patent.title)
        if len(_normalize_title_token(token)) >= 2 and _normalize_title_token(token).lower() not in stopwords
    ]
    ipc_main_groups = [_ipc_main_group(code) for code in patent.ipc_codes]
    keywords = title_tokens[:4] + [code for code in ipc_main_groups if code]
    return keywords or [patent.title]


def _normalize_title_token(token: str) -> str:
    normalized = token.strip()
    if len(normalized) > 2 and normalized.endswith("의"):
        return normalized[:-1]
    return normalized


def _ipc_main_group(code: str) -> str | None:
    match = re.match(r"^([A-HY]\d{2}[A-Z]?)", code.strip(), flags=re.IGNORECASE)
    return match.group(1).upper() if match else None


def _compact_patent_id(patent_id: str) -> str:
    return re.sub(r"[^0-9]", "", patent_id)


def _kipris_upstream_details(exc: KIPRISUpstreamError) -> dict[str, Any]:
    details: dict[str, Any] = {
        "source": "kipris",
        "kind": exc.details.get("kind", "upstream_error"),
    }
    if exc.code:
        details["upstream_code"] = exc.code
    details.update(exc.details)
    return details
