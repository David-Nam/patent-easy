from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.summary import SummaryRequest, SummaryResponse
from app.services.kipris_client import (
    KIPRISConfigurationError,
    KIPRISParseError,
    KIPRISUpstreamError,
)
from app.services.llm_client import (
    LLMConfigurationError,
    LLMParseError,
    LLMProviderError,
)
from app.services.summary_service import SummaryPatentNotFoundError, SummaryService


router = APIRouter(tags=["summary"])


@lru_cache
def get_summary_service() -> SummaryService:
    return SummaryService()


@router.post("/patents/{patent_id}/summary", response_model=SummaryResponse)
async def summarize_patent(
    patent_id: str,
    request: SummaryRequest,
    service: Annotated[SummaryService, Depends(get_summary_service)],
) -> SummaryResponse:
    try:
        return await service.summarize(patent_id, request)
    except SummaryPatentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PATENT_NOT_FOUND", "message": "존재하지 않는 특허 ID입니다."},
        ) from exc
    except (KIPRISConfigurationError, LLMConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "SUMMARY_CONFIGURATION_ERROR",
                "message": str(exc),
            },
        ) from exc
    except (KIPRISUpstreamError, KIPRISParseError, LLMProviderError, LLMParseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "SUMMARY_UPSTREAM_ERROR",
                "message": str(exc),
            },
        ) from exc
