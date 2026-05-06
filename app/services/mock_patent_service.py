import json
from math import ceil
from pathlib import Path

from app.schemas.patent import PatentDetail
from app.schemas.search import Pagination, SearchRequest, SearchResponse
from app.services.mock_llm_client import mock_llm_client


DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mock_patents.json"


class MockPatentService:
    def __init__(self, data_path: Path = DATA_PATH) -> None:
        self.data_path = data_path
        self._patents = self._load_patents()

    def search(self, request: SearchRequest) -> SearchResponse:
        extracted = mock_llm_client.extract_keywords(request.query)
        patents = self._apply_filters(self._patents, request)
        total_count = len(patents)
        total_pages = max(1, ceil(total_count / request.page_size))
        start = (request.page - 1) * request.page_size
        end = start + request.page_size
        page_items = patents[start:end]

        return SearchResponse(
            query=request.query,
            extracted=extracted,
            pagination=Pagination(
                page=request.page,
                page_size=request.page_size,
                total_count=total_count,
                total_pages=total_pages,
            ),
            results=page_items,
        )

    def get_detail(self, patent_id: str) -> PatentDetail | None:
        for patent in self._patents:
            if patent.patent_id == patent_id:
                return patent
        return None

    def _load_patents(self) -> list[PatentDetail]:
        with self.data_path.open(encoding="utf-8") as file:
            payload = json.load(file)
        return [PatentDetail.model_validate(item) for item in payload["patents"]]

    def _apply_filters(self, patents: list[PatentDetail], request: SearchRequest) -> list[PatentDetail]:
        filters = request.filters
        filtered = patents

        if filters.applicant:
            applicant = filters.applicant.lower()
            filtered = [patent for patent in filtered if applicant in patent.applicant.lower()]

        if filters.ipc_codes:
            normalized = [code.upper() for code in filters.ipc_codes]
            filtered = [
                patent
                for patent in filtered
                if any(ipc.upper().startswith(tuple(normalized)) for ipc in patent.ipc_codes)
            ]

        if filters.year_from or filters.year_to:
            filtered = [patent for patent in filtered if self._matches_year_range(patent, filters.year_from, filters.year_to)]

        return sorted(filtered, key=lambda patent: patent.relevance_score, reverse=True)

    @staticmethod
    def _matches_year_range(patent: PatentDetail, year_from: int | None, year_to: int | None) -> bool:
        if not patent.application_date:
            return False
        year = int(patent.application_date[:4])
        if year_from and year < year_from:
            return False
        if year_to and year > year_to:
            return False
        return True


mock_patent_service = MockPatentService()
