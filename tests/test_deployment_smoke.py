from scripts.smoke_test_deployed_api import (
    StepResult,
    _expect_health,
    _expect_openapi,
    _expect_readiness,
    normalize_base_url,
    summarize_steps,
)


def test_normalize_base_url_strips_trailing_slash():
    assert normalize_base_url("https://patent-easy-api.onrender.com/") == "https://patent-easy-api.onrender.com"


def test_normalize_base_url_requires_scheme():
    try:
        normalize_base_url("patent-easy-api.onrender.com")
    except ValueError as exc:
        assert "http:// or https://" in str(exc)
    else:
        raise AssertionError("normalize_base_url should reject URLs without scheme")


def test_smoke_expectations_accept_deployed_shapes():
    assert _expect_health(
        {
            "status": "ok",
            "service": "patent-easy-backend",
            "version": "0.1.0",
            "environment": "production",
        }
    )["environment"] == "production"

    assert _expect_readiness(
        {
            "status": "ready",
            "service": "patent-easy-backend",
            "checks": {
                "cache": {"status": "ok", "path": "/tmp/patent-easy-cache.sqlite"},
                "kipris": {"status": "configured", "base_url": "http://plus.kipris.or.kr"},
                "llm": {
                    "status": "configured",
                    "provider": "gemini",
                    "model": "gemini-2.5-flash-lite",
                },
            },
        }
    )["llm_provider"] == "gemini"

    assert _expect_openapi(
        {
            "info": {"title": "PatentEasy Backend", "version": "0.1.0"},
            "paths": {
                "/health": {},
                "/ready": {},
                "/api/v1/search": {},
                "/api/v1/patents/{patent_id}": {},
                "/api/v1/patents/{patent_id}/summary": {},
            },
        }
    )["path_count"] == 5


def test_summarize_steps_reports_failures():
    summary = summarize_steps(
        [
            StepResult("health", "GET", "/health", True, 200, 1.0, {}),
            StepResult("summary", "POST", "/summary", False, 502, 1.0, {}),
        ]
    )

    assert summary == {"ok": False, "step_count": 2, "passed": 1, "failed": 1}
