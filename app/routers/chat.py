from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatPatentNotFoundError, ChatService
from app.services.kipris_client import (
    KIPRISConfigurationError,
    KIPRISParseError,
    KIPRISUpstreamError,
)
from app.services.llm_client import (
    LLMConfigurationError,
    LLMParseError,
    LLMProviderError,
)
from app.utils.api_errors import error_response, raise_api_error


router = APIRouter(tags=["chat"])


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService()


@router.post(
    "/patents/{patent_id}/chat",
    response_model=ChatResponse,
    responses={
        status.HTTP_404_NOT_FOUND: error_response("Patent not found"),
        status.HTTP_422_UNPROCESSABLE_CONTENT: error_response("Request validation error"),
        status.HTTP_502_BAD_GATEWAY: error_response("KIPRIS or LLM upstream error"),
        status.HTTP_503_SERVICE_UNAVAILABLE: error_response("Chat provider configuration error"),
    },
)
async def chat_about_patent(
    patent_id: str,
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    try:
        return await service.chat(patent_id, request)
    except ChatPatentNotFoundError:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PATENT_NOT_FOUND",
            message="존재하지 않는 특허 ID입니다.",
            details={"patent_id": patent_id},
        )
    except (KIPRISConfigurationError, LLMConfigurationError) as exc:
        raise_api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="CHAT_CONFIGURATION_ERROR",
            message=str(exc),
            details=_configuration_error_details(exc),
        )
    except KIPRISUpstreamError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="CHAT_UPSTREAM_ERROR",
            message=str(exc),
            details=_kipris_upstream_details(exc),
        )
    except KIPRISParseError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="CHAT_UPSTREAM_ERROR",
            message=str(exc),
            details={"source": "kipris", "kind": "xml_parse_error"},
        )
    except LLMProviderError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="CHAT_UPSTREAM_ERROR",
            message=str(exc),
            details={"source": "llm", "kind": "provider_error"},
        )
    except LLMParseError as exc:
        raise_api_error(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="CHAT_UPSTREAM_ERROR",
            message=str(exc),
            details={"source": "llm", "kind": "parse_error"},
        )


def _configuration_error_details(exc: Exception) -> dict[str, str]:
    source = "kipris" if isinstance(exc, KIPRISConfigurationError) else "llm"
    return {"source": source, "kind": "configuration_error"}


def _kipris_upstream_details(exc: KIPRISUpstreamError) -> dict[str, Any]:
    details: dict[str, Any] = {
        "source": "kipris",
        "kind": exc.details.get("kind", "upstream_error"),
    }
    if exc.code:
        details["upstream_code"] = exc.code
    details.update(exc.details)
    return details
