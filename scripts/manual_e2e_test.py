#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.main import app


def main() -> int:
    client = TestClient(app)
    response = client.post(
        "/api/v1/search",
        json={
            "query": "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능",
            "page": 1,
            "page_size": 10,
        },
    )
    response.raise_for_status()
    search_payload = response.json()
    print(json.dumps(search_payload, ensure_ascii=False, indent=2))

    first_patent_id = search_payload["results"][0]["patent_id"]
    detail_response = client.get(f"/api/v1/patents/{first_patent_id}")
    detail_response.raise_for_status()
    print(json.dumps(detail_response.json(), ensure_ascii=False, indent=2))

    summary_response = client.post(
        f"/api/v1/patents/{first_patent_id}/summary",
        json={"user_query": search_payload["query"]},
    )
    summary_response.raise_for_status()
    print(json.dumps(summary_response.json(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
