from fastapi import APIRouter

from app.schemas.search import SearchRequest, SearchResponse
from app.services.mock_patent_service import mock_patent_service


router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search_patents(request: SearchRequest) -> SearchResponse:
    return mock_patent_service.search(request)
