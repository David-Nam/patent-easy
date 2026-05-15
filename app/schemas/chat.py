from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    user_query: str | None = Field(default=None, max_length=500)
    history: list[ChatMessage] = Field(default_factory=list, max_length=6)


class ChatSource(BaseModel):
    type: Literal["abstract", "claim"]
    snippet: str = Field(..., min_length=1)
    claim_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_claim_number(self) -> "ChatSource":
        if self.type == "claim" and self.claim_number is None:
            raise ValueError("claim source requires claim_number")
        if self.type == "abstract" and self.claim_number is not None:
            raise ValueError("abstract source cannot include claim_number")
        return self


class ChatResponse(BaseModel):
    patent_id: str
    answer: str
    sources: list[ChatSource] = Field(default_factory=list, max_length=3)
    generated_at: datetime
    is_cached: bool = False
    disclaimer: str = "이 답변은 참고용입니다. 정확한 권리범위 판단은 변리사 자문을 받으세요."
