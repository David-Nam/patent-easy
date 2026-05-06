from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseModel):
    app_name: str = "PatentEasy Backend"
    app_version: str = "0.1.0"
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "local"))
    app_debug: bool = Field(
        default_factory=lambda: os.getenv("APP_DEBUG", "true").lower() == "true"
    )

    cors_origins: list[str] = Field(default_factory=list)

    openai_api_key: str | None = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY") or None)
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    kipris_api_key: str | None = Field(default_factory=lambda: os.getenv("KIPRIS_API_KEY") or None)
    kipris_base_url: str = Field(
        default_factory=lambda: os.getenv("KIPRIS_BASE_URL", "http://plus.kipris.or.kr")
    )
    kipris_openapi_key_param: str = Field(
        default_factory=lambda: os.getenv("KIPRIS_OPENAPI_KEY_PARAM", os.getenv("KIPRIS_KEY_PARAM", "accessKey"))
    )
    kipris_detail_key_param: str = Field(
        default_factory=lambda: os.getenv("KIPRIS_DETAIL_KEY_PARAM", "ServiceKey")
    )
    kipris_search_path: str = Field(
        default_factory=lambda: os.getenv(
            "KIPRIS_SEARCH_PATH",
            "/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo",
        )
    )
    kipris_detail_path: str = Field(
        default_factory=lambda: os.getenv(
            "KIPRIS_DETAIL_PATH",
            "/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch",
        )
    )
    kipris_claim_path: str = Field(
        default_factory=lambda: os.getenv(
            "KIPRIS_CLAIM_PATH",
            "/openapi/rest/patUtiModInfoSearchSevice/patentClaimInfo",
        )
    )

    cache_db_path: str = Field(default_factory=lambda: os.getenv("CACHE_DB_PATH", "./data/cache.sqlite"))
    cache_ttl_search: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_SEARCH", "86400")))
    cache_ttl_detail: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_DETAIL", "604800")))
    cache_ttl_summary: int = Field(default_factory=lambda: int(os.getenv("CACHE_TTL_SUMMARY", "2592000")))

    llm_monthly_budget_usd: float = Field(
        default_factory=lambda: float(os.getenv("LLM_MONTHLY_BUDGET_USD", "50"))
    )


def _parse_cors_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings(cors_origins=_parse_cors_origins())
