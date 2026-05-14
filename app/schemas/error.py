from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str = Field(..., examples=["SEARCH_UPSTREAM_ERROR"])
    message: str = Field(..., examples=["외부 서비스 호출 중 오류가 발생했습니다."])
    details: dict[str, Any] | None = Field(default=None)
