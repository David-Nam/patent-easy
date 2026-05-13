from fastapi import APIRouter, status

from app.schemas.patent import PatentDetail
from app.services.mock_patent_service import mock_patent_service
from app.utils.api_errors import error_response, raise_api_error


router = APIRouter(tags=["patents"])


@router.get(
    "/patents/{patent_id}",
    response_model=PatentDetail,
    responses={status.HTTP_404_NOT_FOUND: error_response("Patent not found")},
)
async def get_patent_detail(patent_id: str) -> PatentDetail:
    patent = mock_patent_service.get_detail(patent_id)
    if patent is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PATENT_NOT_FOUND",
            message="존재하지 않는 특허 ID입니다.",
            details={"patent_id": patent_id},
        )
    return patent
