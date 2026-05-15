from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.routers import chat, patents, search, summary
from app.services.cache import SQLiteCache
from app.utils.api_errors import error_payload
from app.utils.logger import get_logger


settings = get_settings()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="PatentEasy mock-first backend API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    started_at = perf_counter()
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["x-request-id"] = request_id
        return response
    finally:
        duration_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "request method=%s path=%s status_code=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            request_id,
        )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and {"code", "message"}.issubset(exc.detail):
        content = exc.detail
    else:
        content = error_payload(
            code="HTTP_ERROR",
            message=str(exc.detail),
            details={"status_code": exc.status_code},
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(content),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    content = error_payload(
        code="VALIDATION_ERROR",
        message="요청 형식이 올바르지 않습니다.",
        details={"errors": exc.errors()},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=jsonable_encoder(content),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    content = error_payload(
        code="INTERNAL_SERVER_ERROR",
        message="서버 내부 오류가 발생했습니다.",
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder(content),
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "patent-easy-backend",
        "version": settings.app_version,
        "environment": settings.app_env,
    }


@app.get("/ready", tags=["health"])
async def readiness_check() -> JSONResponse:
    payload, status_code = _readiness_payload()
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


def _readiness_payload() -> tuple[dict[str, object], int]:
    checks = {
        "cache": _cache_readiness(),
        "kipris": _kipris_readiness(),
        "llm": _llm_readiness(),
    }
    ready = all(check["status"] in {"ok", "configured", "mock"} for check in checks.values())
    payload = {
        "status": "ready" if ready else "not_ready",
        "service": "patent-easy-backend",
        "checks": checks,
    }
    status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return payload, status_code


def _cache_readiness() -> dict[str, object]:
    try:
        SQLiteCache(settings.cache_db_path).ping()
    except Exception as exc:
        return {"status": "error", "path": settings.cache_db_path, "message": exc.__class__.__name__}
    return {"status": "ok", "path": settings.cache_db_path}


def _kipris_readiness() -> dict[str, object]:
    return {
        "status": "configured" if settings.kipris_api_key else "not_configured",
        "base_url": settings.kipris_base_url,
    }


def _llm_readiness() -> dict[str, object]:
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return {"status": "mock", "provider": "mock", "model": "mock"}
    if provider == "gemini":
        return {
            "status": "configured" if settings.gemini_api_key else "not_configured",
            "provider": "gemini",
            "model": settings.gemini_model,
        }
    if provider == "openai":
        return {
            "status": "configured" if settings.openai_api_key else "not_configured",
            "provider": "openai",
            "model": settings.openai_model,
        }
    return {"status": "invalid", "provider": settings.llm_provider}


app.include_router(search.router, prefix="/api/v1")
app.include_router(patents.router, prefix="/api/v1")
app.include_router(summary.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
