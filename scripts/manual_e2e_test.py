#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.main import app

PROMPT_CASES_PATH = ROOT_DIR / "data" / "keyword_prompt_cases.json"


def main() -> int:
    client = TestClient(app)
    cases = json.loads(PROMPT_CASES_PATH.read_text(encoding="utf-8"))

    first_search_payload = None
    for case in cases:
        response = client.post(
            "/api/v1/search",
            json={
                "query": case["query"],
                "page": 1,
                "page_size": 10,
            },
        )
        response.raise_for_status()
        search_payload = response.json()
        first_search_payload = first_search_payload or search_payload
        print(json.dumps(_keyword_review_summary(search_payload), ensure_ascii=False, indent=2))

    first_patent_id = first_search_payload["results"][0]["patent_id"]
    detail_response = client.get(f"/api/v1/patents/{first_patent_id}")
    detail_response.raise_for_status()
    print(json.dumps(detail_response.json(), ensure_ascii=False, indent=2))

    summary_response = client.post(
        f"/api/v1/patents/{first_patent_id}/summary",
        json={"user_query": first_search_payload["query"]},
    )
    summary_response.raise_for_status()
    print(json.dumps(summary_response.json(), ensure_ascii=False, indent=2))
    return 0


def _keyword_review_summary(search_payload: dict) -> dict:
    return {
        "query": search_payload["query"],
        "extracted": search_payload["extracted"],
        "result_ids": [item["patent_id"] for item in search_payload["results"]],
    }


if __name__ == "__main__":
    raise SystemExit(main())
