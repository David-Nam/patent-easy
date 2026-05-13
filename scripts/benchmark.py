#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field, TypeAdapter


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.config import Settings, get_settings
from app.schemas.patent import PatentDetail, PatentListItem
from app.schemas.search import SearchFilters, SearchRequest
from app.services.kipris_client import KIPRISClient, PatentSearchPage
from app.services.mock_patent_service import DATA_PATH
from app.services.query_builder import QueryBuilder
from app.services.search_service import SearchService


DEFAULT_EVAL_FILE = ROOT_DIR / "data" / "eval_queries.json"


class EvalCase(BaseModel):
    id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=2)
    expected_keywords: list[str] = Field(..., min_length=1)
    expected_ipc_codes: list[str] = Field(..., min_length=1)
    expected_patent_ids: list[str] = Field(..., min_length=1)


@dataclass(frozen=True)
class BenchmarkConfig:
    mode: str
    llm_provider: str
    cache_enabled: bool
    top_k: int


class LocalPatentSearchClient:
    """Offline search client for benchmark runs against data/mock_patents.json."""

    def __init__(self, data_path: Path = DATA_PATH) -> None:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        self.patents = [PatentDetail.model_validate(item) for item in payload["patents"]]

    async def search_patent_page(
        self,
        keywords: list[str],
        filters: SearchFilters | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> PatentSearchPage:
        scored_items = [
            _to_list_item(patent, _local_relevance_score(patent, keywords))
            for patent in self.patents
        ]
        filtered_items = _apply_filters(scored_items, filters)
        ranked_items = sorted(filtered_items, key=lambda item: item.relevance_score, reverse=True)
        start = (page - 1) * page_size
        end = start + page_size
        return PatentSearchPage(items=ranked_items[start:end], total_count=len(ranked_items))


async def run_benchmark(cases: list[EvalCase], config: BenchmarkConfig) -> dict[str, Any]:
    settings = _settings_for(config)
    query_builder = QueryBuilder(settings=settings)
    search_client = _search_client_for(config, settings)
    service = SearchService(query_builder=query_builder, kipris_client=search_client)

    case_results = []
    for case in cases:
        before_llm_calls = _llm_call_count(query_builder)
        before_kipris_calls = _kipris_call_count(search_client)
        started_at = perf_counter()
        response = await service.search(
            SearchRequest(query=case.query, page=1, page_size=config.top_k)
        )
        latency_ms = (perf_counter() - started_at) * 1000
        llm_calls = _llm_call_delta(config, query_builder, before_llm_calls)
        kipris_calls = _kipris_call_count(search_client) - before_kipris_calls

        result_ids = [item.patent_id for item in response.results]
        hits = [patent_id for patent_id in result_ids[: config.top_k] if patent_id in case.expected_patent_ids]
        keyword_hits = _overlap(case.expected_keywords, response.extracted.keywords)
        ipc_hits = _ipc_overlap(case.expected_ipc_codes, response.extracted.ipc_codes)
        case_results.append(
            {
                "id": case.id,
                "query": case.query,
                "latency_ms": round(latency_ms, 2),
                "precision_at_10": _precision_at_k(len(hits), config.top_k),
                "recall_at_10": _recall(len(hits), len(case.expected_patent_ids)),
                "matched_patent_ids": hits,
                "result_patent_ids": result_ids[: config.top_k],
                "expected_patent_ids": case.expected_patent_ids,
                "keyword_recall": _recall(len(keyword_hits), len(case.expected_keywords)),
                "matched_keywords": keyword_hits,
                "ipc_recall": _recall(len(ipc_hits), len(case.expected_ipc_codes)),
                "matched_ipc_codes": ipc_hits,
                "kipris_call_count": kipris_calls,
                "llm_call_count": llm_calls,
            }
        )

    return {
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": config.mode,
            "llm_provider": config.llm_provider,
            "cache_enabled": config.cache_enabled,
            "top_k": config.top_k,
        },
        "summary": _summary(case_results),
        "cases": case_results,
    }


def load_eval_cases(path: Path = DEFAULT_EVAL_FILE) -> list[EvalCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = TypeAdapter(list[EvalCase]).validate_python(payload)
    if not 10 <= len(cases) <= 20:
        raise ValueError("eval dataset must contain 10 to 20 cases")
    return cases


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark PatentEasy backend search quality.")
    parser.add_argument("--mode", choices=["mock", "real"], default="mock")
    parser.add_argument("--llm-provider", choices=["mock", "gemini", "openai"], default=None)
    parser.add_argument("--cache", choices=["on", "off"], default="off")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_FILE)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Allow calls to real KIPRIS or LLM provider APIs.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    llm_provider = args.llm_provider or ("mock" if args.mode == "mock" else get_settings().llm_provider)
    config = BenchmarkConfig(
        mode=args.mode,
        llm_provider=llm_provider,
        cache_enabled=args.cache == "on",
        top_k=args.top_k,
    )
    if config.top_k < 1:
        parser.error("--top-k must be greater than or equal to 1")
    if _requires_live_access(config) and not args.allow_live:
        parser.error("real KIPRIS/LLM benchmark runs require --allow-live")

    cases = load_eval_cases(args.eval_file)
    result = asyncio.run(run_benchmark(cases, config))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


def _settings_for(config: BenchmarkConfig) -> Settings:
    base_settings = get_settings()
    return base_settings.model_copy(update={"llm_provider": config.llm_provider})


def _search_client_for(config: BenchmarkConfig, settings: Settings):
    if config.mode == "mock":
        return LocalPatentSearchClient()
    return KIPRISClient(settings=settings, cache_enabled=config.cache_enabled)


def _requires_live_access(config: BenchmarkConfig) -> bool:
    return config.mode == "real" or config.llm_provider in {"gemini", "openai"}


def _llm_call_delta(config: BenchmarkConfig, query_builder: QueryBuilder, before_calls: int) -> int:
    delta = _llm_call_count(query_builder) - before_calls
    if config.llm_provider == "mock":
        return 1
    return delta


def _llm_call_count(query_builder: QueryBuilder) -> int:
    return query_builder.provider_call_count


def _kipris_call_count(search_client: Any) -> int:
    return sum(getattr(search_client, "endpoint_call_counts", {}).values())


def _summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "query_count": len(case_results),
        "mean_precision_at_10": _mean(item["precision_at_10"] for item in case_results),
        "mean_recall_at_10": _mean(item["recall_at_10"] for item in case_results),
        "mean_keyword_recall": _mean(item["keyword_recall"] for item in case_results),
        "mean_ipc_recall": _mean(item["ipc_recall"] for item in case_results),
        "mean_latency_ms": _mean(item["latency_ms"] for item in case_results),
        "kipris_call_count": sum(item["kipris_call_count"] for item in case_results),
        "llm_call_count": sum(item["llm_call_count"] for item in case_results),
    }


def _local_relevance_score(patent: PatentDetail, keywords: list[str]) -> int:
    haystack = _normalize_text(
        " ".join(
            [
                patent.title,
                patent.applicant,
                patent.abstract,
                patent.abstract_preview,
                " ".join(patent.tags),
                " ".join(patent.ipc_codes),
            ]
        )
    )
    score = 0
    for keyword in keywords:
        keyword_text = _normalize_text(keyword)
        if keyword_text and keyword_text in haystack:
            score += 18
        for part in keyword_text.split():
            if len(part) >= 2 and part in haystack:
                score += 7
    return min(100, max(0, score + min(20, patent.relevance_score // 5)))


def _to_list_item(patent: PatentDetail, relevance_score: int) -> PatentListItem:
    return PatentListItem.model_validate(
        patent.model_dump(mode="json") | {"relevance_score": relevance_score}
    )


def _apply_filters(items: list[PatentListItem], filters: SearchFilters | None) -> list[PatentListItem]:
    if filters is None:
        return items
    filtered = items
    if filters.applicant:
        applicant = filters.applicant.lower()
        filtered = [item for item in filtered if applicant in item.applicant.lower()]
    if filters.ipc_codes:
        codes = tuple(code.upper() for code in filters.ipc_codes)
        filtered = [
            item for item in filtered if any(ipc.upper().startswith(codes) for ipc in item.ipc_codes)
        ]
    if filters.year_from or filters.year_to:
        filtered = [item for item in filtered if _matches_year(item, filters.year_from, filters.year_to)]
    return filtered


def _matches_year(item: PatentListItem, year_from: int | None, year_to: int | None) -> bool:
    if not item.application_date:
        return False
    year = int(item.application_date[:4])
    if year_from and year < year_from:
        return False
    if year_to and year > year_to:
        return False
    return True


def _overlap(expected: list[str], actual: list[str]) -> list[str]:
    actual_set = {_normalize_text(item) for item in actual}
    return [item for item in expected if _normalize_text(item) in actual_set]


def _ipc_overlap(expected: list[str], actual: list[str]) -> list[str]:
    actual_codes = [item.upper().replace(" ", "") for item in actual]
    hits = []
    for code in expected:
        compact = code.upper().replace(" ", "")
        if any(actual_code.startswith(compact) for actual_code in actual_codes):
            hits.append(code)
    return hits


def _precision_at_k(hit_count: int, k: int) -> float:
    return round(hit_count / k, 4)


def _recall(hit_count: int, total_count: int) -> float:
    return round(hit_count / total_count, 4) if total_count else 0.0


def _mean(values) -> float:
    items = list(values)
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


if __name__ == "__main__":
    raise SystemExit(main())
