from pydantic import BaseModel, Field


class Claim(BaseModel):
    number: int = Field(..., ge=1)
    text: str


class PatentListItem(BaseModel):
    patent_id: str
    title: str
    applicant: str
    application_date: str | None = None
    ipc_codes: list[str] = Field(default_factory=list)
    relevance_score: int = Field(..., ge=0, le=100)
    tags: list[str] = Field(default_factory=list)
    abstract_preview: str
    kipris_url: str | None = None


class PatentDetail(PatentListItem):
    abstract: str
    inventors: list[str] = Field(default_factory=list)
    publication_date: str | None = None
    registration_date: str | None = None
    legal_status: str | None = None
    claims: list[Claim] = Field(default_factory=list)
