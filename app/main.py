from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import patents, search, summary


settings = get_settings()

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


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "patent-easy-backend"}


app.include_router(search.router, prefix="/api/v1")
app.include_router(patents.router, prefix="/api/v1")
app.include_router(summary.router, prefix="/api/v1")
