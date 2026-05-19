#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import httpx


DEFAULT_BASE_URL = "https://patent-easy-api.onrender.com"
DEFAULT_DETAIL_PATENT_ID = "10-2023-0147601"
DEFAULT_SUMMARY_PATENT_ID = "10-2023-0147601"
DEFAULT_SEARCH_QUERY = "전기차 배터리 열관리 시스템"
DEFAULT_SUMMARY_QUERY = "전기차 배터리 열관리 기능"
DEFAULT_CHAT_QUESTION = "이 특허는 전기차 배터리 열관리 기능과 관련이 있나요?"


@dataclass(frozen=True)
class SmokeConfig:
    base_url: str
    timeout: float
    skip_summary: bool
    include_chat: bool
    output: Path | None


@dataclass(frozen=True)
class StepResult:
    name: str
    method: str
    path: str
    ok: bool
    status_code: int | None
    latency_ms: float
    detail: dict[str, Any]


def main() -> int:
    args = build_parser().parse_args()
    config = SmokeConfig(
        base_url=normalize_base_url(args.base_url),
        timeout=args.timeout,
        skip_summary=args.skip_summary,
        include_chat=args.include_chat,
        output=args.output,
    )
    result = run_smoke_test(config)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if config.output:
        config.output.parent.mkdir(parents=True, exist_ok=True)
        config.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["summary"]["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run smoke tests against a deployed PatentEasy backend.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("DEPLOYED_API_BASE_URL", DEFAULT_BASE_URL),
        help="Deployed backend base URL. Defaults to DEPLOYED_API_BASE_URL or the Render demo URL.",
    )
    parser.add_argument("--timeout", type=float, default=90.0, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Skip the summary call to avoid one live KIPRIS/Gemini request during quick checks.",
    )
    parser.add_argument(
        "--include-chat",
        action="store_true",
        help="Include the chat call. This uses one additional live KIPRIS/Gemini request.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser


def normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        raise ValueError("base URL must start with http:// or https://")
    return normalized


def run_smoke_test(config: SmokeConfig) -> dict[str, Any]:
    steps: list[StepResult] = []
    with httpx.Client(base_url=config.base_url, timeout=config.timeout, follow_redirects=True) as client:
        steps.append(_request_json_step(client, "health", "GET", "/health", _expect_health))
        steps.append(_request_json_step(client, "readiness", "GET", "/ready", _expect_readiness))
        steps.append(_request_json_step(client, "openapi", "GET", "/openapi.json", _expect_openapi))
        steps.append(
            _request_json_step(
                client,
                "detail",
                "GET",
                f"/api/v1/patents/{DEFAULT_DETAIL_PATENT_ID}",
                _expect_detail,
            )
        )
        steps.append(
            _request_json_step(
                client,
                "similar",
                "GET",
                f"/api/v1/patents/{DEFAULT_DETAIL_PATENT_ID}/similar?limit=3",
                _expect_similar,
            )
        )
        steps.append(
            _request_json_step(
                client,
                "search",
                "POST",
                "/api/v1/search",
                _expect_search,
                json_body={
                    "query": DEFAULT_SEARCH_QUERY,
                    "page": 1,
                    "page_size": 3,
                },
            )
        )
        if config.skip_summary:
            steps.append(
                StepResult(
                    name="summary",
                    method="POST",
                    path=f"/api/v1/patents/{DEFAULT_SUMMARY_PATENT_ID}/summary",
                    ok=True,
                    status_code=None,
                    latency_ms=0.0,
                    detail={"skipped": True},
                )
            )
        else:
            steps.append(
                _request_json_step(
                    client,
                    "summary",
                    "POST",
                    f"/api/v1/patents/{DEFAULT_SUMMARY_PATENT_ID}/summary",
                    _expect_summary,
                    json_body={"user_query": DEFAULT_SUMMARY_QUERY},
                )
            )
        if config.include_chat:
            steps.append(
                _request_json_step(
                    client,
                    "chat",
                    "POST",
                    f"/api/v1/patents/{DEFAULT_SUMMARY_PATENT_ID}/chat",
                    _expect_chat,
                    json_body={"question": DEFAULT_CHAT_QUESTION, "user_query": DEFAULT_SUMMARY_QUERY},
                )
            )

    return {
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "base_url": config.base_url,
            "timeout": config.timeout,
            "skip_summary": config.skip_summary,
            "include_chat": config.include_chat,
        },
        "summary": summarize_steps(steps),
        "steps": [asdict(step) for step in steps],
    }


def summarize_steps(steps: list[StepResult]) -> dict[str, Any]:
    passed = sum(1 for step in steps if step.ok)
    failed = len(steps) - passed
    return {
        "ok": failed == 0,
        "step_count": len(steps),
        "passed": passed,
        "failed": failed,
    }


def _request_json_step(
    client: httpx.Client,
    name: str,
    method: str,
    path: str,
    expectation: Callable[[dict[str, Any]], dict[str, Any]],
    json_body: dict[str, Any] | None = None,
) -> StepResult:
    started_at = perf_counter()
    try:
        response = client.request(method, path, json=json_body)
        latency_ms = (perf_counter() - started_at) * 1000
        try:
            payload = response.json()
        except ValueError:
            return _failed_step(name, method, path, response.status_code, latency_ms, "response is not valid JSON")
        if not isinstance(payload, dict):
            return _failed_step(name, method, path, response.status_code, latency_ms, "response is not a JSON object")
        if response.status_code >= 400:
            return StepResult(
                name=name,
                method=method,
                path=path,
                ok=False,
                status_code=response.status_code,
                latency_ms=round(latency_ms, 2),
                detail={"error": "unexpected status code", "payload": payload},
            )
        try:
            detail = expectation(payload)
        except AssertionError as exc:
            return _failed_step(name, method, path, response.status_code, latency_ms, str(exc))
        return StepResult(
            name=name,
            method=method,
            path=path,
            ok=True,
            status_code=response.status_code,
            latency_ms=round(latency_ms, 2),
            detail=detail,
        )
    except Exception as exc:
        latency_ms = (perf_counter() - started_at) * 1000
        return _failed_step(name, method, path, None, latency_ms, f"{exc.__class__.__name__}: {exc}")


def _failed_step(
    name: str,
    method: str,
    path: str,
    status_code: int | None,
    latency_ms: float,
    message: str,
) -> StepResult:
    return StepResult(
        name=name,
        method=method,
        path=path,
        ok=False,
        status_code=status_code,
        latency_ms=round(latency_ms, 2),
        detail={"error": message},
    )


def _expect_health(payload: dict[str, Any]) -> dict[str, Any]:
    assert payload.get("status") == "ok", "health status must be ok"
    assert payload.get("service") == "patent-easy-backend", "service name mismatch"
    return {
        "status": payload["status"],
        "service": payload["service"],
        "environment": payload.get("environment"),
    }


def _expect_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    assert payload.get("status") == "ready", "readiness status must be ready"
    checks = payload.get("checks")
    assert isinstance(checks, dict), "readiness checks must be an object"
    assert checks.get("cache", {}).get("status") == "ok", "cache must be ok"
    assert checks.get("kipris", {}).get("status") == "configured", "KIPRIS must be configured"
    assert checks.get("llm", {}).get("status") in {"configured", "mock"}, "LLM must be configured or mock"
    return {
        "status": payload["status"],
        "cache_path": checks["cache"].get("path"),
        "kipris": checks["kipris"].get("status"),
        "llm_provider": checks["llm"].get("provider"),
        "llm_model": checks["llm"].get("model"),
    }


def _expect_openapi(payload: dict[str, Any]) -> dict[str, Any]:
    paths = payload.get("paths")
    assert isinstance(paths, dict), "OpenAPI paths must be an object"
    required_paths = {
        "/health",
        "/ready",
        "/api/v1/search",
        "/api/v1/patents/{patent_id}",
        "/api/v1/patents/{patent_id}/similar",
        "/api/v1/patents/{patent_id}/summary",
        "/api/v1/patents/{patent_id}/chat",
    }
    missing = sorted(required_paths - set(paths))
    assert not missing, f"OpenAPI missing paths: {', '.join(missing)}"
    return {
        "title": payload.get("info", {}).get("title"),
        "version": payload.get("info", {}).get("version"),
        "path_count": len(paths),
    }


def _expect_detail(payload: dict[str, Any]) -> dict[str, Any]:
    assert payload.get("patent_id") == DEFAULT_DETAIL_PATENT_ID, "detail patent_id mismatch"
    assert payload.get("claims"), "detail must include claims"
    assert payload.get("status"), "detail must include status"
    assert payload.get("original_url") or payload.get("kipris_url"), "detail must include original URL"
    return {
        "patent_id": payload["patent_id"],
        "title": payload.get("title"),
        "status": payload.get("status"),
        "claim_count": len(payload.get("claims", [])),
        "legal_event_count": len(payload.get("legal_events", [])),
        "cited_count": len(payload.get("cited_patents", [])),
        "family_count": len(payload.get("family_patents", [])),
    }


def _expect_similar(payload: dict[str, Any]) -> dict[str, Any]:
    assert payload.get("patent_id") == DEFAULT_DETAIL_PATENT_ID, "similar patent_id mismatch"
    assert payload.get("strategy") == "kipris_title_ipc_search", "similar strategy mismatch"
    results = payload.get("results")
    assert isinstance(results, list), "similar results must be a list"
    return {
        "patent_id": payload["patent_id"],
        "result_count": len(results),
        "strategy": payload["strategy"],
    }


def _expect_search(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results")
    assert isinstance(results, list), "search results must be a list"
    assert results, "search results must not be empty"
    extracted = payload.get("extracted")
    assert isinstance(extracted, dict), "search extracted field must be an object"
    return {
        "result_count": len(results),
        "first_patent_id": results[0].get("patent_id"),
        "keywords": extracted.get("keywords", []),
        "total_count": payload.get("pagination", {}).get("total_count"),
    }


def _expect_summary(payload: dict[str, Any]) -> dict[str, Any]:
    assert payload.get("patent_id"), "summary patent_id is required"
    assert payload.get("core_summary"), "core_summary is required"
    assert payload.get("business_application"), "business_application is required"
    return {
        "patent_id": payload["patent_id"],
        "tag_count": len(payload.get("key_tags", [])),
        "is_cached": payload.get("is_cached"),
    }


def _expect_chat(payload: dict[str, Any]) -> dict[str, Any]:
    assert payload.get("patent_id"), "chat patent_id is required"
    assert payload.get("answer"), "chat answer is required"
    sources = payload.get("sources")
    assert isinstance(sources, list), "chat sources must be a list"
    return {
        "patent_id": payload["patent_id"],
        "source_count": len(sources),
        "is_cached": payload.get("is_cached"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
