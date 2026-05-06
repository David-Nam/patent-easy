from pydantic import BaseModel, Field, model_validator

from app.schemas.patent import PatentListItem


class SearchFilters(BaseModel):
    applicant: str | None = None
    ipc_codes: list[str] | None = None
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)

    @model_validator(mode="after")
    def validate_year_range(self) -> "SearchFilters":
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("year_from must be less than or equal to year_to")
        return self


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=50)


class ExtractedQuery(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    ipc_codes: list[str] = Field(default_factory=list)
    expanded_terms: dict[str, list[str]] = Field(default_factory=dict)


class Pagination(BaseModel):
    page: int
    page_size: int
    total_count: int
    total_pages: int


class SearchResponse(BaseModel):
    query: str
    extracted: ExtractedQuery
    pagination: Pagination
    results: list[PatentListItem]
