#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import httpx
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "tests" / "fixtures" / "kipris_raw"
NORMALIZED_DIR = ROOT_DIR / "tests" / "fixtures" / "kipris_normalized"
REPORT_PATH = ROOT_DIR / "docs" / "kipris_api_research.md"

FIELD_CANDIDATES = {
    "patent_id": ["applicationnumber", "applicationno", "applno", "appnum", "patentid"],
    "title": ["inventiontitle", "title", "inventnam", "inventionname"],
    "applicant": ["applicantname", "applicant", "applicantnam"],
    "application_date": ["applicationdate", "applicationdt", "appdate"],
    "publication_date": ["opendate", "publicationdate", "publishedDate"],
    "registration_date": ["registrationdate", "registerdate", "regdate"],
    "legal_status": ["legalstatus", "registerstatus", "rightstatus", "finaldisposal"],
    "abstract": ["abstract", "astrtcont", "summary"],
    "claim": ["claim", "claimtext", "claimcontent", "claimcont"],
}
IPC_CANDIDATES = ["ipc", "ipcnumber", "ipccode", "ipcmain"]


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    api_key = os.getenv("KIPRIS_API_KEY")
    if not api_key:
        print("KIPRIS_API_KEY is missing. Add it to .env before running verification.", file=sys.stderr)
        return 2

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    base_url = os.getenv("KIPRIS_BASE_URL", "http://plus.kipris.or.kr").rstrip("/")
    key_param = os.getenv("KIPRIS_KEY_PARAM", "accessKey")
    query = os.getenv("KIPRIS_VERIFY_QUERY", "자동차")
    docs_count = os.getenv("KIPRIS_VERIFY_DOCS_COUNT", "5")

    endpoints = [
        {
            "name": "free_search",
            "path": os.getenv(
                "KIPRIS_SEARCH_PATH",
                "/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo",
            ),
            "params": {
                "word": query,
                "patent": "true",
                "utility": "true",
                "docsStart": "1",
                "docsCount": docs_count,
                "lastvalue": "R",
                key_param: api_key,
            },
        }
    ]

    results = []
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        search_result = call_endpoint(client, base_url, endpoints[0])
        results.append(search_result)

        application_number = (
            os.getenv("KIPRIS_SAMPLE_APPLICATION_NUMBER")
            or search_result.get("first_application_number")
        )
        if application_number:
            for name, env_name, default_path in [
                (
                    "bibliography_detail",
                    "KIPRIS_DETAIL_PATH",
                    "/openapi/rest/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch",
                ),
                (
                    "claim_detail",
                    "KIPRIS_CLAIM_PATH",
                    "/openapi/rest/patUtiModInfoSearchSevice/patentClaimInfo",
                ),
            ]:
                results.append(
                    call_endpoint(
                        client,
                        base_url,
                        {
                            "name": name,
                            "path": os.getenv(env_name, default_path),
                            "params": {
                                "applicationNumber": application_number,
                                key_param: api_key,
                            },
                        },
                    )
                )
        else:
            print("Search response did not expose an application number; skipped detail endpoints.")

    write_report(results)
    print(f"Wrote raw fixtures to {RAW_DIR}")
    print(f"Wrote normalized fixtures to {NORMALIZED_DIR}")
    print(f"Updated {REPORT_PATH}")
    return 0


def call_endpoint(client: httpx.Client, base_url: str, endpoint: dict) -> dict:
    url = f"{base_url}/{endpoint['path'].lstrip('/')}"
    print(f"Calling {endpoint['name']}: {url}")
    response = client.get(url, params=endpoint["params"])

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    body_format = detect_body_format(response)
    raw_path = RAW_DIR / f"{endpoint['name']}_{timestamp}.{body_format}"
    raw_path.write_text(response.text, encoding="utf-8")

    normalized = normalize_response(endpoint, response, raw_path)
    normalized_path = NORMALIZED_DIR / f"{endpoint['name']}_{timestamp}.json"
    normalized_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return normalized


def detect_body_format(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "").lower()
    body = response.text.lstrip()
    if "json" in content_type or body.startswith("{") or body.startswith("["):
        return "json"
    if "xml" in content_type or body.startswith("<"):
        return "xml"
    return "txt"


def normalize_response(endpoint: dict, response: httpx.Response, raw_path: Path) -> dict:
    parsed = parse_body(response)
    records = extract_records(parsed)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint["name"],
        "path": endpoint["path"],
        "request_params": sanitize_params(endpoint["params"]),
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "body_format": detect_body_format(response),
        "raw_fixture": str(raw_path.relative_to(ROOT_DIR)),
        "first_application_number": first_non_empty(record.get("patent_id") for record in records),
        "records": records[:10],
    }


def parse_body(response: httpx.Response):
    body = response.text.strip()
    if not body:
        return None
    if detect_body_format(response) == "json":
        try:
            return response.json()
        except json.JSONDecodeError:
            return body
    if detect_body_format(response) == "xml":
        try:
            return xml_to_obj(ET.fromstring(body))
        except ET.ParseError:
            return body
    return body


def xml_to_obj(element: ET.Element):
    children = list(element)
    tag = clean_tag(element.tag)
    text = (element.text or "").strip()
    if not children:
        return {tag: text}

    grouped = {}
    for child in children:
        child_obj = xml_to_obj(child)
        for child_tag, value in child_obj.items():
            if child_tag in grouped:
                if not isinstance(grouped[child_tag], list):
                    grouped[child_tag] = [grouped[child_tag]]
                grouped[child_tag].append(value)
            else:
                grouped[child_tag] = value
    return {tag: grouped}


def extract_records(parsed) -> list[dict]:
    nodes = []
    collect_candidate_nodes(parsed, nodes)
    records = []
    seen = set()
    for node in nodes:
        record = normalize_record(node)
        fingerprint = json.dumps(record, ensure_ascii=False, sort_keys=True)
        if record and fingerprint not in seen:
            records.append(record)
            seen.add(fingerprint)
    return records


def collect_candidate_nodes(value, nodes: list) -> None:
    if isinstance(value, dict):
        normalized_keys = {normalize_key(key) for key in value}
        interesting = set().union(*[set(v) for v in FIELD_CANDIDATES.values()], set(IPC_CANDIDATES))
        if normalized_keys & interesting:
            nodes.append(value)
        for child in value.values():
            collect_candidate_nodes(child, nodes)
    elif isinstance(value, list):
        for item in value:
            collect_candidate_nodes(item, nodes)


def normalize_record(node: dict) -> dict:
    record = {
        "patent_id": find_first(node, FIELD_CANDIDATES["patent_id"]),
        "title": find_first(node, FIELD_CANDIDATES["title"]),
        "applicant": find_first(node, FIELD_CANDIDATES["applicant"]),
        "application_date": find_first(node, FIELD_CANDIDATES["application_date"]),
        "publication_date": find_first(node, FIELD_CANDIDATES["publication_date"]),
        "registration_date": find_first(node, FIELD_CANDIDATES["registration_date"]),
        "legal_status": find_first(node, FIELD_CANDIDATES["legal_status"]),
        "abstract": find_first(node, FIELD_CANDIDATES["abstract"]),
        "claim": find_first(node, FIELD_CANDIDATES["claim"]),
        "ipc_codes": collect_values(node, IPC_CANDIDATES),
    }
    return {key: value for key, value in record.items() if value not in (None, "", [])}


def find_first(value, candidate_keys: list[str]) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if normalize_key(key) in candidate_keys:
                text = scalar_text(child)
                if text:
                    return text
        for child in value.values():
            found = find_first(child, candidate_keys)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_first(item, candidate_keys)
            if found:
                return found
    return None


def collect_values(value, candidate_keys: list[str]) -> list[str]:
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if normalize_key(key) in candidate_keys:
                text = scalar_text(child)
                if text:
                    found.append(text)
            found.extend(collect_values(child, candidate_keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(collect_values(item, candidate_keys))
    return sorted(set(found))


def scalar_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        if len(value) == 1:
            return scalar_text(next(iter(value.values())))
        return None
    if isinstance(value, list) and value:
        return scalar_text(value[0])
    return None


def sanitize_params(params: dict) -> dict:
    sanitized = {}
    for key, value in params.items():
        if "key" in key.lower():
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


def clean_tag(tag: str) -> str:
    return tag.split("}", 1)[-1]


def normalize_key(key: str) -> str:
    return clean_tag(str(key)).replace("_", "").replace("-", "").lower()


def first_non_empty(values) -> str | None:
    for value in values:
        if value:
            return value
    return None


def write_report(results: list[dict]) -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    lines = [
        "# KIPRIS Plus API Research",
        "",
        f"Last verification run: `{generated_at}`",
        "",
        "## Verification Policy",
        "",
        "- KIPRIS Plus API must be verified with a real `KIPRIS_API_KEY` before implementing the real `KIPRISClient`.",
        "- Raw responses are saved exactly as received under `tests/fixtures/kipris_raw/`.",
        "- Normalized JSON is generated under `tests/fixtures/kipris_normalized/` only to make field review easier.",
        "- OpenAI is not required for this verification.",
        "",
        "## Endpoints Checked",
        "",
    ]

    for result in results:
        lines.extend(
            [
                f"### {result['endpoint']}",
                "",
                f"- Path: `{result['path']}`",
                f"- HTTP status: `{result['http_status']}`",
                f"- Body format: `{result['body_format']}`",
                f"- Raw fixture: `{result['raw_fixture']}`",
                f"- Extracted records: `{len(result['records'])}`",
                f"- First application number: `{result.get('first_application_number') or 'not found'}`",
                "",
            ]
        )
        if result["records"]:
            lines.append("Sample normalized record:")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(result["records"][0], ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")

    lines.extend(
        [
            "## Next Review Checklist",
            "",
            "- Confirm exact field names for application number, title, applicant, dates, legal status, abstract, claims, and IPC.",
            "- Confirm whether the response contract is XML-only or varies by endpoint.",
            "- Confirm the actual call quota from the KIPRIS Plus account page before running broad tests.",
            "- Update `app/services/kipris_client.py` only after the raw fixtures have been reviewed.",
            "",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
