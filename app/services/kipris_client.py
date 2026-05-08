from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET

import httpx

from app.config import Settings, get_settings
from app.schemas.patent import Claim, PatentDetail, PatentListItem
from app.schemas.search import SearchFilters
from app.services.cache import SQLiteCache, normalize_cache_key


class KIPRISError(RuntimeError):
    """Base exception for KIPRIS client failures."""


class KIPRISConfigurationError(KIPRISError):
    """Raised when required KIPRIS configuration is missing."""


class KIPRISUpstreamError(KIPRISError):
    """Raised when KIPRIS returns an HTTP or service-level error."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class KIPRISParseError(KIPRISError):
    """Raised when a KIPRIS XML response cannot be parsed."""


@dataclass(frozen=True)
class _Endpoint:
    path: str
    key_param: str


class KIPRISClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
        cache: SQLiteCache | None = None,
        cache_enabled: bool = True,
        timeout: float = 20.0,
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client
        self.cache = cache if cache is not None else SQLiteCache() if cache_enabled else None
        self.timeout = timeout

    async def search_patents(
        self,
        keywords: list[str],
        filters: SearchFilters | None = None,
        page_size: int = 10,
    ) -> list[PatentListItem]:
        endpoint = _Endpoint(
            path=self.settings.kipris_search_path,
            key_param=self.settings.kipris_openapi_key_param,
        )
        query = " ".join(term.strip() for term in keywords if term.strip())
        if not query:
            return []

        cache_key = self._search_cache_key(keywords, filters, page_size)
        cached_items = self.cache.get(cache_key) if self.cache is not None else None
        if cached_items is not None:
            return [PatentListItem.model_validate(item) for item in cached_items]

        root = await self._get_xml(
            endpoint,
            {
                "word": query,
                "patent": "true",
                "utility": "true",
                "docsStart": "1",
                "docsCount": str(page_size),
                "lastvalue": "R",
            },
        )
        items = [_map_search_item(item, index) for index, item in enumerate(_find_all(root, "PatentUtilityInfo"))]
        filtered_items = _apply_filters(items, filters)
        if self.cache is not None:
            self.cache.set(
                cache_key,
                [item.model_dump(mode="json") for item in filtered_items],
                self.settings.cache_ttl_search,
            )
        return filtered_items

    async def get_patent_detail(self, patent_id: str) -> PatentDetail:
        compact_id = _compact_patent_id(patent_id)
        detail_endpoint = _Endpoint(
            path=self.settings.kipris_detail_path,
            key_param=self.settings.kipris_detail_key_param,
        )
        claim_endpoint = _Endpoint(
            path=self.settings.kipris_claim_path,
            key_param=self.settings.kipris_openapi_key_param,
        )

        cache_key = self._detail_cache_key(compact_id)
        cached_detail = self.cache.get(cache_key) if self.cache is not None else None
        if cached_detail is not None:
            return PatentDetail.model_validate(cached_detail)

        detail_root = await self._get_xml(detail_endpoint, {"applicationNumber": compact_id})
        claim_root = await self._get_xml(claim_endpoint, {"applicationNumber": compact_id})
        detail = _map_patent_detail(detail_root, claim_root)
        if self.cache is not None:
            self.cache.set(cache_key, detail.model_dump(mode="json"), self.settings.cache_ttl_detail)
        return detail

    async def _get_xml(self, endpoint: _Endpoint, params: dict[str, str]) -> ET.Element:
        api_key = self.settings.kipris_api_key
        if not api_key:
            raise KIPRISConfigurationError("KIPRIS_API_KEY is required")

        request_params = {**params, endpoint.key_param: api_key}
        url = _join_url(self.settings.kipris_base_url, endpoint.path)
        try:
            if self.http_client is not None:
                response = await self.http_client.get(url, params=request_params)
            else:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    response = await client.get(url, params=request_params)
        except httpx.HTTPError as exc:
            raise KIPRISUpstreamError(f"KIPRIS request failed: {exc}") from exc

        if response.status_code >= 400:
            raise KIPRISUpstreamError(f"KIPRIS returned HTTP {response.status_code}")

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise KIPRISParseError("KIPRIS response is not valid XML") from exc

        _raise_for_service_error(root)
        return root

    def _search_cache_key(
        self,
        keywords: list[str],
        filters: SearchFilters | None,
        page_size: int,
    ) -> str:
        return normalize_cache_key(
            "kipris:search",
            {
                "base_url": self.settings.kipris_base_url,
                "path": self.settings.kipris_search_path,
                "keywords": keywords,
                "filters": filters.model_dump(mode="json") if filters else None,
                "page_size": page_size,
            },
        )

    def _detail_cache_key(self, compact_id: str) -> str:
        return normalize_cache_key(
            "kipris:detail",
            {
                "base_url": self.settings.kipris_base_url,
                "detail_path": self.settings.kipris_detail_path,
                "claim_path": self.settings.kipris_claim_path,
                "application_number": compact_id,
            },
        )


def _raise_for_service_error(root: ET.Element) -> None:
    result_code = _first_text(root, "resultCode")
    if result_code and result_code != "00":
        result_msg = _first_text(root, "resultMsg") or "Unknown KIPRIS service error"
        raise KIPRISUpstreamError(result_msg, code=result_code)


def _map_search_item(item: ET.Element, index: int) -> PatentListItem:
    abstract = _first_text(item, "Abstract") or ""
    return PatentListItem(
        patent_id=_first_text(item, "ApplicationNumber") or "",
        title=_first_text(item, "InventionName") or "",
        applicant=_first_text(item, "Applicant") or "",
        application_date=_normalize_date(_first_text(item, "ApplicationDate")),
        ipc_codes=_split_ipc(_first_text(item, "InternationalpatentclassificationNumber")),
        relevance_score=max(0, 100 - (index * 3)),
        tags=[],
        abstract_preview=_preview(abstract),
        kipris_url="https://www.kipris.or.kr/",
    )


def _map_patent_detail(detail_root: ET.Element, claim_root: ET.Element) -> PatentDetail:
    summary = _find_first(detail_root, "biblioSummaryInfo")
    if summary is None:
        raise KIPRISParseError("Missing biblioSummaryInfo in KIPRIS detail response")

    title = _first_text(summary, "inventionTitle") or ""
    abstract = _first_text(detail_root, "astrtCont") or ""
    applicant_names = [_first_text(node, "name") for node in _find_all(detail_root, "applicantInfo")]
    inventor_names = [_first_text(node, "name") for node in _find_all(detail_root, "inventorInfo")]
    ipc_codes = [_first_text(node, "ipcNumber") for node in _find_all(detail_root, "ipcInfo")]
    claims = [_map_claim(node, index) for index, node in enumerate(_find_all(claim_root, "claimInfo"), start=1)]

    return PatentDetail(
        patent_id=_first_text(summary, "applicationNumber") or "",
        title=title,
        applicant="|".join(name for name in applicant_names if name) or "",
        application_date=_normalize_date(_first_text(summary, "applicationDate")),
        ipc_codes=[code for code in ipc_codes if code],
        relevance_score=100,
        tags=[],
        abstract_preview=_preview(abstract),
        kipris_url="https://www.kipris.or.kr/",
        abstract=abstract.strip(),
        inventors=[name for name in inventor_names if name],
        publication_date=_normalize_date(_first_text(summary, "openDate")),
        registration_date=_normalize_date(_first_text(summary, "registerDate")),
        legal_status=_first_text(summary, "finalDisposal") or _first_text(summary, "registerStatus"),
        claims=claims,
    )


def _map_claim(node: ET.Element, fallback_number: int) -> Claim:
    text = (_first_text(node, "claim") or "").strip()
    match = re.match(r"\s*(\d+)\.", text)
    number = int(match.group(1)) if match else fallback_number
    return Claim(number=number, text=text)


def _apply_filters(items: list[PatentListItem], filters: SearchFilters | None) -> list[PatentListItem]:
    if filters is None:
        return items

    filtered = items
    if filters.applicant:
        applicant = filters.applicant.lower()
        filtered = [item for item in filtered if applicant in item.applicant.lower()]

    if filters.ipc_codes:
        prefixes = tuple(code.upper() for code in filters.ipc_codes)
        filtered = [
            item
            for item in filtered
            if any(ipc.upper().startswith(prefixes) for ipc in item.ipc_codes)
        ]

    if filters.year_from or filters.year_to:
        filtered = [item for item in filtered if _matches_year_range(item, filters.year_from, filters.year_to)]

    return filtered


def _matches_year_range(item: PatentListItem, year_from: int | None, year_to: int | None) -> bool:
    if not item.application_date:
        return False
    year = int(item.application_date[:4])
    if year_from and year < year_from:
        return False
    if year_to and year > year_to:
        return False
    return True


def _find_all(root: ET.Element, tag_name: str) -> list[ET.Element]:
    return [element for element in root.iter() if _local_name(element.tag) == tag_name]


def _find_first(root: ET.Element, tag_name: str) -> ET.Element | None:
    for element in root.iter():
        if _local_name(element.tag) == tag_name:
            return element
    return None


def _first_text(root: ET.Element, tag_name: str) -> str | None:
    element = _find_first(root, tag_name)
    if element is None or element.text is None:
        return None
    text = element.text.strip()
    return text or None


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _split_ipc(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if re.fullmatch(r"\d{8}", cleaned):
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:]}"
    dotted = re.fullmatch(r"(\d{4})\.(\d{2})\.(\d{2})", cleaned)
    if dotted:
        return "-".join(dotted.groups())
    return cleaned


def _compact_patent_id(patent_id: str) -> str:
    return re.sub(r"[^0-9]", "", patent_id)


def _preview(value: str, limit: int = 120) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
