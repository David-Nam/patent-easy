from fastapi import APIRouter, HTTPException, status

from app.schemas.summary import SummaryRequest, SummaryResponse
from app.services.mock_llm_client import mock_llm_client
from app.services.mock_patent_service import mock_patent_service


router = APIRouter(tags=["summary"])


@router.post("/patents/{patent_id}/summary", response_model=SummaryResponse)
async def summarize_patent(patent_id: str, request: SummaryRequest) -> SummaryResponse:
    patent = mock_patent_service.get_detail(patent_id)
    if patent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PATENT_NOT_FOUND", "message": "존재하지 않는 특허 ID입니다."},
        )
    return mock_llm_client.summarize_patent(patent, request.user_query)
