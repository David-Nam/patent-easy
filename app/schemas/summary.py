from datetime import datetime

from pydantic import BaseModel, Field


class SummaryRequest(BaseModel):
    user_query: str | None = Field(default=None, max_length=500)


class SummaryResponse(BaseModel):
    patent_id: str
    core_summary: str
    business_application: str
    key_tags: list[str] = Field(default_factory=list)
    generated_at: datetime
    is_cached: bool = False
    disclaimer: str = "이 요약은 참고용입니다. 정확한 권리범위 판단은 변리사 자문을 받으세요."
