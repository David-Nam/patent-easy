from fastapi import APIRouter, HTTPException, status

from app.schemas.patent import PatentDetail
from app.services.mock_patent_service import mock_patent_service


router = APIRouter(tags=["patents"])


@router.get("/patents/{patent_id}", response_model=PatentDetail)
async def get_patent_detail(patent_id: str) -> PatentDetail:
    patent = mock_patent_service.get_detail(patent_id)
    if patent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PATENT_NOT_FOUND", "message": "존재하지 않는 특허 ID입니다."},
        )
    return patent
