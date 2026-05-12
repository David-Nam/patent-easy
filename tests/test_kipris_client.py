import asyncio
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.schemas.search import SearchFilters
from app.services.cache import SQLiteCache
from app.services.kipris_client import (
    KIPRISClient,
    KIPRISConfigurationError,
    KIPRISParseError,
    KIPRISUpstreamError,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_FIXTURES = ROOT_DIR / "tests" / "fixtures" / "kipris_raw"


def test_search_patents_maps_fixture_records_and_filters():
    async def run() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            assert request.url.path == "/search"
            return _xml_response(_read_fixture("free_search_20260506T233857Z.xml"))

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = KIPRISClient(
                settings=_settings(kipris_search_path="/search"),
                http_client=async_client,
                cache_enabled=False,
            )
            results = await client.search_patents(
                ["전기자동차", "배터리"],
                filters=SearchFilters(ipc_codes=["B60L"], year_from=2020),
                page=2,
                page_size=5,
            )
        finally:
            await async_client.aclose()

        assert len(results) == 2
        assert results[0].patent_id == "1020230147601"
        assert results[0].title == "전기자동차의 배터리 열관리 시스템 및 이의 운용 방법"
        assert results[0].applicant == "서울대학교산학협력단"
        assert results[0].application_date == "2023-10-31"
        assert "B60L 58/24" in results[0].ipc_codes
        assert len(results[0].abstract_preview) <= 120

        params = requests[0].url.params
        assert params["word"] == "전기자동차 배터리"
        assert params["docsStart"] == "6"
        assert params["docsCount"] == "5"
        assert params["accessKey"] == "test-key"

    asyncio.run(run())


def test_search_patent_page_returns_total_count_from_fixture():
    async def run() -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return _xml_response(_read_fixture("free_search_20260506T233857Z.xml"))

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = KIPRISClient(
                settings=_settings(kipris_search_path="/search"),
                http_client=async_client,
                cache_enabled=False,
            )
            search_page = await client.search_patent_page(["자동차"], page=1, page_size=5)
        finally:
            await async_client.aclose()

        assert search_page.total_count == 180195
        assert len(search_page.items) == 5

    asyncio.run(run())


def test_get_patent_detail_maps_bibliography_and_claim_fixtures():
    async def run() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/detail":
                return _xml_response(_read_fixture("bibliography_detail_20260506T233858Z.xml"))
            if request.url.path == "/claim":
                return _xml_response(_read_fixture("claim_detail_20260506T233858Z.xml"))
            return httpx.Response(404, text="not found")

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = KIPRISClient(
                settings=_settings(kipris_detail_path="/detail", kipris_claim_path="/claim"),
                http_client=async_client,
                cache_enabled=False,
            )
            detail = await client.get_patent_detail("10-2023-0147601")
        finally:
            await async_client.aclose()

        assert detail.patent_id == "10-2023-0147601"
        assert detail.title == "전기자동차의 배터리 열관리 시스템 및 이의 운용 방법"
        assert detail.applicant == "서울대학교산학협력단"
        assert detail.application_date == "2023-10-31"
        assert detail.publication_date == "2025-05-09"
        assert detail.registration_date == "2026-04-29"
        assert detail.legal_status == "등록결정(일반)"
        assert "B60H 1/32" in detail.ipc_codes
        assert "김민수" in detail.inventors
        assert len(detail.claims) == 14
        assert detail.claims[0].number == 1
        assert "전기자동차에 동력을 제공하는 배터리" in detail.claims[0].text

        detail_params = requests[0].url.params
        claim_params = requests[1].url.params
        assert detail_params["applicationNumber"] == "1020230147601"
        assert detail_params["ServiceKey"] == "test-key"
        assert claim_params["applicationNumber"] == "1020230147601"
        assert claim_params["accessKey"] == "test-key"

    asyncio.run(run())


def test_missing_api_key_raises_configuration_error():
    async def run() -> None:
        client = KIPRISClient(settings=_settings(kipris_api_key=None), cache_enabled=False)
        with pytest.raises(KIPRISConfigurationError):
            await client.search_patents(["자동차"])

    asyncio.run(run())


def test_service_error_raises_upstream_error():
    async def run() -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return _xml_response(
                "<response><header><resultCode>99</resultCode>"
                "<resultMsg>bad key</resultMsg></header></response>"
            )

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = KIPRISClient(settings=_settings(), http_client=async_client, cache_enabled=False)
            with pytest.raises(KIPRISUpstreamError) as exc_info:
                await client.search_patents(["자동차"])
        finally:
            await async_client.aclose()

        assert exc_info.value.code == "99"
        assert str(exc_info.value) == "bad key"

    asyncio.run(run())


def test_invalid_xml_raises_parse_error():
    async def run() -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not xml")

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = KIPRISClient(settings=_settings(), http_client=async_client, cache_enabled=False)
            with pytest.raises(KIPRISParseError):
                await client.search_patents(["자동차"])
        finally:
            await async_client.aclose()

    asyncio.run(run())


def test_search_patents_uses_cache_for_repeated_requests(tmp_path):
    async def run() -> None:
        request_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            return _xml_response(_read_fixture("free_search_20260506T233857Z.xml"))

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = KIPRISClient(
                settings=_settings(kipris_search_path="/search"),
                http_client=async_client,
                cache=SQLiteCache(tmp_path / "cache.sqlite"),
            )
            first = await client.search_patents(["전기 자동차"], page_size=5)
            second = await client.search_patents(["전기차"], page_size=5)
        finally:
            await async_client.aclose()

        assert request_count == 1
        assert first[0].patent_id == second[0].patent_id
        assert isinstance(second[0].application_date, str)

    asyncio.run(run())


def test_get_patent_detail_uses_cache_for_repeated_requests(tmp_path):
    async def run() -> None:
        request_paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            request_paths.append(request.url.path)
            if request.url.path == "/detail":
                return _xml_response(_read_fixture("bibliography_detail_20260506T233858Z.xml"))
            if request.url.path == "/claim":
                return _xml_response(_read_fixture("claim_detail_20260506T233858Z.xml"))
            return httpx.Response(404, text="not found")

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            client = KIPRISClient(
                settings=_settings(kipris_detail_path="/detail", kipris_claim_path="/claim"),
                http_client=async_client,
                cache=SQLiteCache(tmp_path / "cache.sqlite"),
            )
            first = await client.get_patent_detail("10-2023-0147601")
            second = await client.get_patent_detail("1020230147601")
        finally:
            await async_client.aclose()

        assert request_paths == ["/detail", "/claim"]
        assert first.patent_id == second.patent_id
        assert len(second.claims) == 14

    asyncio.run(run())


def _settings(**overrides) -> Settings:
    values = {
        "kipris_api_key": "test-key",
        "kipris_base_url": "http://kipris.test",
        "kipris_openapi_key_param": "accessKey",
        "kipris_detail_key_param": "ServiceKey",
        "kipris_search_path": "/search",
        "kipris_detail_path": "/detail",
        "kipris_claim_path": "/claim",
    }
    values.update(overrides)
    return Settings(**values)


def _read_fixture(name: str) -> str:
    return (RAW_FIXTURES / name).read_text(encoding="utf-8")


def _xml_response(text: str) -> httpx.Response:
    return httpx.Response(200, text=text, headers={"content-type": "text/xml;charset=utf-8"})
