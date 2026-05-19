from scripts.smoke_test_deployed_api import (
    StepResult,
    _expect_chat,
    _expect_detail,
    _expect_health,
    _expect_openapi,
    _expect_readiness,
    _expect_similar,
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
                "/api/v1/patents/{patent_id}/similar": {},
                "/api/v1/patents/{patent_id}/summary": {},
                "/api/v1/patents/{patent_id}/chat": {},
            },
        }
    )["path_count"] == 7

    assert _expect_detail(
        {
            "patent_id": "10-2023-0147601",
            "claims": [{"number": 1, "text": "청구항 일부"}],
            "title": "전기자동차의 배터리 열관리 시스템 및 이의 운용 방법",
            "status": "등록",
            "original_url": "https://www.kipris.or.kr/khome/detail/newWindow.do?applno=1020230147601&right=kpat",
            "legal_events": [],
            "cited_patents": [],
            "family_patents": [],
        }
    )["claim_count"] == 1

    assert _expect_similar(
        {
            "patent_id": "10-2023-0147601",
            "strategy": "kipris_title_ipc_search",
            "results": [],
        }
    )["result_count"] == 0

    assert _expect_chat(
        {
            "patent_id": "10-2023-0147601",
            "answer": "청구항 1 기준으로 관련이 있습니다.",
            "sources": [{"type": "claim", "claim_number": 1, "snippet": "청구항 일부"}],
            "is_cached": False,
        }
    )["source_count"] == 1


def test_summarize_steps_reports_failures():
    summary = summarize_steps(
        [
            StepResult("health", "GET", "/health", True, 200, 1.0, {}),
            StepResult("summary", "POST", "/summary", False, 502, 1.0, {}),
        ]
    )

    assert summary == {"ok": False, "step_count": 2, "passed": 1, "failed": 1}
