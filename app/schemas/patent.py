from pydantic import BaseModel, Field


class Claim(BaseModel):
    number: int = Field(..., ge=1)
    text: str


class LegalEvent(BaseModel):
    status: str | None = None
    document_name: str | None = None
    receipt_date: str | None = None
    receipt_number: str | None = None


class PatentReference(BaseModel):
    patent_id: str | None = None
    title: str | None = None
    applicant: str | None = None
    application_date: str | None = None
    status: str | None = None
    relation: str | None = None
    source: str | None = None
    kipris_url: str | None = None
    original_url: str | None = None


class PatentListItem(BaseModel):
    patent_id: str
    title: str
    applicant: str
    application_date: str | None = None
    ipc_codes: list[str] = Field(default_factory=list)
    cpc_codes: list[str] = Field(default_factory=list)
    status: str | None = None
    application_status: str | None = None
    publication_date: str | None = None
    publication_number: str | None = None
    registration_date: str | None = None
    registration_number: str | None = None
    citation_count: int | None = None
    cited_by_count: int | None = None
    similarity_score: int | None = None
    relevance_score: int = Field(..., ge=0, le=100)
    tags: list[str] = Field(default_factory=list)
    abstract_preview: str
    thumbnail_url: str | None = None
    drawing_url: str | None = None
    kipris_url: str | None = None
    original_url: str | None = None


class PatentDetail(PatentListItem):
    abstract: str
    inventors: list[str] = Field(default_factory=list)
    legal_status: str | None = None
    claims: list[Claim] = Field(default_factory=list)
    legal_events: list[LegalEvent] = Field(default_factory=list)
    cited_patents: list[PatentReference] = Field(default_factory=list)
    cited_by_patents: list[PatentReference] = Field(default_factory=list)
    family_patents: list[PatentReference] = Field(default_factory=list)


class SimilarPatentsResponse(BaseModel):
    patent_id: str
    strategy: str
    results: list[PatentListItem] = Field(default_factory=list)
