import asyncio
import json

import pytest

from scripts.benchmark import BenchmarkConfig, DEFAULT_EVAL_FILE, load_eval_cases, run_benchmark


def test_eval_dataset_has_required_manual_labels():
    cases = load_eval_cases(DEFAULT_EVAL_FILE)

    assert 10 <= len(cases) <= 20
    assert all(case.expected_keywords for case in cases)
    assert all(case.expected_ipc_codes for case in cases)
    assert all(case.expected_patent_ids for case in cases)


def test_mock_benchmark_reports_quality_and_runtime_metrics():
    async def run() -> None:
        cases = load_eval_cases(DEFAULT_EVAL_FILE)
        result = await run_benchmark(
            cases,
            BenchmarkConfig(
                mode="mock",
                llm_provider="mock",
                cache_enabled=False,
                top_k=10,
            ),
        )

        assert result["run"]["mode"] == "mock"
        assert result["summary"]["query_count"] == len(cases)
        assert result["summary"]["llm_call_count"] == len(cases)
        assert result["summary"]["kipris_call_count"] == 0
        assert result["summary"]["mean_precision_at_10"] > 0
        assert result["summary"]["mean_recall_at_10"] > 0
        assert "latency_ms" in result["cases"][0]
        json.dumps(result, ensure_ascii=False)

    asyncio.run(run())


def test_eval_dataset_size_validation(tmp_path):
    path = tmp_path / "eval_queries.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "too-small",
                    "query": "테스트 쿼리",
                    "expected_keywords": ["테스트"],
                    "expected_ipc_codes": ["G06F"],
                    "expected_patent_ids": ["p1"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="10 to 20"):
        load_eval_cases(path)
