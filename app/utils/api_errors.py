from __future__ import annotations

from typing import Any, NoReturn

from fastapi import HTTPException

from app.schemas.error import ErrorResponse


def error_payload(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ErrorResponse(code=code, message=message, details=details).model_dump(exclude_none=True)


def raise_api_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    raise HTTPException(status_code=status_code, detail=error_payload(code, message, details))


def error_response(description: str) -> dict[str, Any]:
    return {"model": ErrorResponse, "description": description}
