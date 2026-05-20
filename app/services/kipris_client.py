from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import httpx

from app.config import Settings, get_settings
from app.schemas.patent import Claim, LegalEvent, PatentDetail, PatentListItem, PatentReference
from app.schemas.search import SearchFilters
from app.services.cache import SQLiteCache, normalize_cache_key
from app.utils.logger import get_logger


logger = get_logger(__name__)


class KIPRISError(RuntimeError):
    """Base exception for KIPRIS client failures."""


class KIPRISConfigurationError(KIPRISError):
    """Raised when required KIPRIS configuration is missing."""


class KIPRISUpstreamError(KIPRISError):
    """Raised when KIPRIS returns an HTTP, network, or service-level error."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class KIPRISParseError(KIPRISError):
    """Raised when a KIPRIS XML response cannot be parsed."""


@dataclass(frozen=True)
class _Endpoint:
    path: str
    key_param: str


@dataclass(frozen=True)
class PatentSearchPage:
    items: list[PatentListItem]
    total_count: int


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
        self.endpoint_call_counts: dict[str, int] = {}

    async def search_patents(
        self,
        keywords: list[str],
        filters: SearchFilters | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> list[PatentListItem]:
        search_page = await self.search_patent_page(
            keywords,
            filters=filters,
            page=page,
            page_size=page_size,
        )
        return search_page.items

    async def search_patent_page(
        self,
        keywords: list[str],
        filters: SearchFilters | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> PatentSearchPage:
        endpoint = _Endpoint(
            path=self.settings.kipris_search_path,
            key_param=self.settings.kipris_openapi_key_param,
        )
        query = " ".join(term.strip() for term in keywords if term.strip())
        if not query:
            return PatentSearchPage(items=[], total_count=0)

        cache_key = self._search_cache_key(keywords, filters, page, page_size)
        cached_page = self.cache.get(cache_key) if self.cache is not None else None
        if cached_page is not None:
            return _restore_search_page(cached_page)

        root = await self._get_xml(
            endpoint,
            {
                "word": query,
                "patent": "true",
                "utility": "true",
                "docsStart": str(((page - 1) * page_size) + 1),
                "docsCount": str(page_size),
                "lastvalue": "R",
            },
        )
        items = [
            _map_search_item(item, index, self.settings.api_public_base_url)
            for index, item in enumerate(_find_all(root, "PatentUtilityInfo"))
        ]
        items = await self._enrich_items_with_cpc(items)
        filtered_items = _apply_filters(items, filters)
        total_count = _search_total_count(root, fallback=len(items))
        if _has_filters(filters):
            total_count = len(filtered_items)
        search_page = PatentSearchPage(items=filtered_items, total_count=total_count)
        if self.cache is not None:
            self.cache.set(
                cache_key,
                {
                    "items": [item.model_dump(mode="json") for item in search_page.items],
                    "total_count": search_page.total_count,
                },
                self.settings.cache_ttl_search,
            )
        return search_page

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
        cpc_codes = await self.get_cpc_codes(compact_id)
        detail = _map_patent_detail(detail_root, claim_root, cpc_codes)
        original_pdf_url = await self.get_original_pdf_url(compact_id, status=detail.status)
        fallback_original_url = _patent_original_pdf_url(compact_id, self.settings.api_public_base_url, detail.status)
        if original_pdf_url:
            detail = detail.model_copy(update={"original_url": original_pdf_url})
        elif fallback_original_url:
            detail = detail.model_copy(update={"original_url": fallback_original_url})
        if self.cache is not None:
            self.cache.set(cache_key, detail.model_dump(mode="json"), self.settings.cache_ttl_detail)
        return detail

    async def get_cpc_codes(self, patent_id: str) -> list[str]:
        compact_id = _compact_patent_id(patent_id)
        if not compact_id:
            return []

        cache_key = self._cpc_cache_key(compact_id)
        cached_codes = self.cache.get(cache_key) if self.cache is not None else None
        if isinstance(cached_codes, list):
            return [code for code in cached_codes if isinstance(code, str)]

        endpoint = _Endpoint(
            path=self.settings.kipris_cpc_path,
            key_param=self.settings.kipris_openapi_key_param,
        )
        root = await self._get_xml(endpoint, {"applicationNumber": compact_id})
        cpc_codes = _map_cpc_codes(root)
        if self.cache is not None:
            self.cache.set(cache_key, cpc_codes, self.settings.cache_ttl_detail)
        return cpc_codes

    async def get_original_pdf_url(self, patent_id: str, status: str | None = None) -> str | None:
        compact_id = _compact_patent_id(patent_id)
        if not compact_id:
            return None

        cache_key = self._full_text_cache_key(compact_id, status)
        cached_url = self.cache.get(cache_key) if self.cache is not None else None
        if isinstance(cached_url, str) and cached_url:
            return cached_url

        for endpoint in self._full_text_pdf_endpoints(status):
            try:
                root = await self._get_xml(endpoint, {"applicationNumber": compact_id})
            except KIPRISError as exc:
                logger.warning(
                    "kipris full text lookup failed endpoint=%s error=%s",
                    endpoint.path,
                    exc.__class__.__name__,
                )
                continue

            pdf_url = _first_file_path(root)
            if pdf_url:
                if self.cache is not None:
                    self.cache.set(cache_key, pdf_url, self.settings.cache_ttl_detail)
                return pdf_url

        return None

    async def _enrich_items_with_cpc(self, items: list[PatentListItem]) -> list[PatentListItem]:
        enriched_items: list[PatentListItem] = []
        for item in items:
            if item.cpc_codes:
                enriched_items.append(item)
                continue
            cpc_codes = await self.get_cpc_codes(item.patent_id)
            enriched_items.append(item.model_copy(update={"cpc_codes": cpc_codes}))
        return enriched_items

    async def _get_xml(self, endpoint: _Endpoint, params: dict[str, str]) -> ET.Element:
        api_key = self.settings.kipris_api_key
        if not api_key:
            raise KIPRISConfigurationError("KIPRIS_API_KEY is required")

        request_params = {**params, endpoint.key_param: api_key}
        url = _join_url(self.settings.kipris_base_url, endpoint.path)
        self._record_endpoint_call(endpoint.path)
        try:
            if self.http_client is not None:
                response = await self.http_client.get(url, params=request_params)
            else:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    response = await client.get(url, params=request_params)
        except httpx.TimeoutException as exc:
            raise KIPRISUpstreamError(
                "KIPRIS request timed out",
                code="KIPRIS_TIMEOUT",
                details={"kind": "timeout"},
            ) from exc
        except httpx.HTTPError as exc:
            raise KIPRISUpstreamError(
                f"KIPRIS request failed: {exc}",
                code="KIPRIS_REQUEST_ERROR",
                details={"kind": "network_error"},
            ) from exc

        if response.status_code >= 400:
            error_code = "KIPRIS_HTTP_5XX" if response.status_code >= 500 else "KIPRIS_HTTP_4XX"
            error_kind = "http_5xx" if response.status_code >= 500 else "http_4xx"
            raise KIPRISUpstreamError(
                f"KIPRIS returned HTTP {response.status_code}",
                code=error_code,
                details={
                    "kind": error_kind,
                    "status_code": response.status_code,
                },
            )

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise KIPRISParseError("KIPRIS response is not valid XML") from exc

        _raise_for_service_error(root)
        return root

    def _record_endpoint_call(self, endpoint_path: str) -> None:
        call_count = self.endpoint_call_counts.get(endpoint_path, 0) + 1
        self.endpoint_call_counts[endpoint_path] = call_count
        logger.info("kipris request endpoint=%s call_count=%s", endpoint_path, call_count)

    def _search_cache_key(
        self,
        keywords: list[str],
        filters: SearchFilters | None,
        page: int,
        page_size: int,
    ) -> str:
        return normalize_cache_key(
            "kipris:search",
            {
                "base_url": self.settings.kipris_base_url,
                "path": self.settings.kipris_search_path,
                "cpc_path": self.settings.kipris_cpc_path,
                "keywords": keywords,
                "filters": filters.model_dump(mode="json") if filters else None,
                "page": page,
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
                "cpc_path": self.settings.kipris_cpc_path,
                "full_text_key_param": self.settings.kipris_full_text_key_param,
                "full_text_paths": [
                    self.settings.kipris_standard_pub_full_text_path,
                    self.settings.kipris_standard_ann_full_text_path,
                    self.settings.kipris_pub_full_text_path,
                    self.settings.kipris_ann_full_text_path,
                ],
                "application_number": compact_id,
            },
        )

    def _cpc_cache_key(self, compact_id: str) -> str:
        return normalize_cache_key(
            "kipris:cpc",
            {
                "base_url": self.settings.kipris_base_url,
                "path": self.settings.kipris_cpc_path,
                "key_param": self.settings.kipris_openapi_key_param,
                "application_number": compact_id,
            },
        )

    def _full_text_cache_key(self, compact_id: str, status: str | None) -> str:
        return normalize_cache_key(
            "kipris:full_text",
            {
                "base_url": self.settings.kipris_base_url,
                "key_param": self.settings.kipris_full_text_key_param,
                "status": status,
                "paths": [
                    self.settings.kipris_standard_pub_full_text_path,
                    self.settings.kipris_standard_ann_full_text_path,
                    self.settings.kipris_pub_full_text_path,
                    self.settings.kipris_ann_full_text_path,
                ],
                "application_number": compact_id,
            },
        )

    def _full_text_pdf_endpoints(self, status: str | None) -> list[_Endpoint]:
        key_param = self.settings.kipris_full_text_key_param
        pub_endpoints = [
            _Endpoint(path=self.settings.kipris_standard_pub_full_text_path, key_param=key_param),
            _Endpoint(path=self.settings.kipris_pub_full_text_path, key_param=key_param),
        ]
        ann_endpoints = [
            _Endpoint(path=self.settings.kipris_standard_ann_full_text_path, key_param=key_param),
            _Endpoint(path=self.settings.kipris_ann_full_text_path, key_param=key_param),
        ]
        if status and "등록" in status:
            return ann_endpoints + pub_endpoints
        return pub_endpoints + ann_endpoints


def _raise_for_service_error(root: ET.Element) -> None:
    result_code = _first_text(root, "resultCode")
    if result_code and result_code != "00":
        result_msg = _first_text(root, "resultMsg") or "Unknown KIPRIS service error"
        raise KIPRISUpstreamError(
            result_msg,
            code="KIPRIS_SERVICE_ERROR",
            details={
                "kind": "service_error",
                "kipris_code": result_code,
            },
        )


def _map_search_item(item: ET.Element, index: int, api_public_base_url: str | None) -> PatentListItem:
    abstract = _first_text(item, "Abstract") or ""
    application_number = _first_text(item, "ApplicationNumber") or ""
    registration_status = _first_text(item, "RegistrationStatus")
    status = _patent_status(
        final_disposal=None,
        registration_status=registration_status,
        open_date=_first_text(item, "OpeningDate") or _first_text(item, "PublicDate"),
    )
    kipris_url = _kipris_kpat_detail_url(application_number)
    original_url = _patent_original_pdf_url(application_number, api_public_base_url, status) or kipris_url
    relevance_score = max(0, 100 - (index * 3))
    return PatentListItem(
        patent_id=application_number,
        title=_first_text(item, "InventionName") or "",
        applicant=_first_text(item, "Applicant") or "",
        application_date=_normalize_date(_first_text(item, "ApplicationDate")),
        ipc_codes=_split_ipc(_first_text(item, "InternationalpatentclassificationNumber")),
        cpc_codes=_dedupe_codes(_split_codes(_first_text(item, "CpcNumber") or _first_text(item, "CPCNumber"))),
        status=status,
        application_status=status,
        publication_date=_normalize_date(_first_text(item, "OpeningDate") or _first_text(item, "PublicDate")),
        publication_number=_first_text(item, "OpeningNumber") or _first_text(item, "PublicNumber"),
        registration_date=_normalize_date(_first_text(item, "RegistrationDate")),
        registration_number=_first_text(item, "RegistrationNumber"),
        citation_count=None,
        cited_by_count=None,
        similarity_score=relevance_score,
        relevance_score=relevance_score,
        tags=[],
        abstract_preview=_preview(abstract),
        thumbnail_url=_first_text(item, "ThumbnailPath"),
        drawing_url=_first_text(item, "DrawingPath"),
        kipris_url=kipris_url,
        original_url=original_url,
    )


def _map_patent_detail(detail_root: ET.Element, claim_root: ET.Element, cpc_codes: list[str]) -> PatentDetail:
    summary = _find_first(detail_root, "biblioSummaryInfo")
    if summary is None:
        raise KIPRISParseError("Missing biblioSummaryInfo in KIPRIS detail response")

    title = _first_text(summary, "inventionTitle") or ""
    abstract = _first_text(detail_root, "astrtCont") or ""
    applicant_names = [_first_text(node, "name") for node in _find_all(detail_root, "applicantInfo")]
    inventor_names = [_first_text(node, "name") for node in _find_all(detail_root, "inventorInfo")]
    ipc_codes = [_first_text(node, "ipcNumber") for node in _find_all(detail_root, "ipcInfo")]
    merged_cpc_codes = _dedupe_codes([*_map_cpc_codes(detail_root), *cpc_codes])
    claims = [_map_claim(node, index) for index, node in enumerate(_find_all(claim_root, "claimInfo"), start=1)]
    patent_id = _first_text(summary, "applicationNumber") or ""
    final_disposal = _first_text(summary, "finalDisposal")
    register_status = _first_text(summary, "registerStatus")
    status = _patent_status(
        final_disposal=final_disposal,
        registration_status=register_status,
        open_date=_first_text(summary, "openDate") or _first_text(summary, "publicationDate"),
    )
    cited_patents = _map_prior_art_documents(detail_root)
    family_patents = _map_family_patents(detail_root)
    image_path = _find_first(detail_root, "imagePathInfo")
    original_url = _kipris_kpat_detail_url(patent_id)

    return PatentDetail(
        patent_id=patent_id,
        title=title,
        applicant="|".join(name for name in applicant_names if name) or "",
        application_date=_normalize_date(_first_text(summary, "applicationDate")),
        ipc_codes=[code for code in ipc_codes if code],
        cpc_codes=merged_cpc_codes,
        status=status,
        application_status=status,
        publication_date=_normalize_date(_first_text(summary, "openDate") or _first_text(summary, "publicationDate")),
        publication_number=_first_text(summary, "openNumber") or _first_text(summary, "publicationNumber"),
        registration_date=_normalize_date(_first_text(summary, "registerDate")),
        registration_number=_first_text(summary, "registerNumber"),
        citation_count=len(cited_patents),
        cited_by_count=None,
        similarity_score=100,
        relevance_score=100,
        tags=[],
        abstract_preview=_preview(abstract),
        thumbnail_url=_first_text(image_path, "path") if image_path is not None else None,
        drawing_url=_first_text(image_path, "largePath") if image_path is not None else None,
        kipris_url=original_url,
        original_url=original_url,
        abstract=abstract.strip(),
        inventors=[name for name in inventor_names if name],
        legal_status=final_disposal or register_status,
        claims=claims,
        legal_events=_map_legal_events(detail_root),
        cited_patents=cited_patents,
        cited_by_patents=[],
        family_patents=family_patents,
    )


def _map_claim(node: ET.Element, fallback_number: int) -> Claim:
    text = (_first_text(node, "claim") or "").strip()
    match = re.match(r"\s*(\d+)\.", text)
    number = int(match.group(1)) if match else fallback_number
    return Claim(number=number, text=text)


def _map_cpc_codes(*roots: ET.Element) -> list[str]:
    codes: list[str] = []
    for root in roots:
        for tag_name in [
            "cpcNumber",
            "CpcNumber",
            "CPCNumber",
            "CooperativepatentclassificationNumber",
        ]:
            for node in _find_all(root, tag_name):
                if node.text:
                    codes.extend(_split_codes(node.text))
    return _dedupe_codes(codes)


def _map_legal_events(root: ET.Element) -> list[LegalEvent]:
    events: list[LegalEvent] = []
    for node in _find_all(root, "legalStatusInfo"):
        events.append(
            LegalEvent(
                status=_first_text(node, "commonCodeName"),
                document_name=_first_text(node, "documentName"),
                receipt_date=_normalize_date(_first_text(node, "receiptDate")),
                receipt_number=_first_text(node, "receiptNumber"),
            )
        )
    return events


def _map_prior_art_documents(root: ET.Element) -> list[PatentReference]:
    references: list[PatentReference] = []
    for node in _find_all(root, "priorArtDocumentsInfo"):
        document_number = _first_text(node, "documentsNumber")
        if not document_number:
            continue
        references.append(
            PatentReference(
                patent_id=document_number,
                relation="cited",
                source="prior_art_documents",
                kipris_url=_kipris_search_url(document_number),
                original_url=_kipris_search_url(document_number),
            )
        )
    return references


def _map_family_patents(root: ET.Element) -> list[PatentReference]:
    family_patents: list[PatentReference] = []
    for node in _find_all(root, "familyInfo"):
        patent_id = (
            _first_text(node, "applicationNumber")
            or _first_text(node, "registerNumber")
            or _first_text(node, "publicationNumber")
            or _first_text(node, "familyApplicationNumber")
        )
        if not patent_id:
            continue
        family_patents.append(
            PatentReference(
                patent_id=patent_id,
                title=_first_text(node, "inventionTitle"),
                applicant=_first_text(node, "applicant"),
                application_date=_normalize_date(_first_text(node, "applicationDate")),
                status=_first_text(node, "registerStatus") or _first_text(node, "status"),
                relation="family",
                source="family_info",
                kipris_url=_kipris_search_url(patent_id),
                original_url=_kipris_search_url(patent_id),
            )
        )
    return family_patents


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

    if filters.cpc_codes:
        prefixes = tuple(code.upper() for code in filters.cpc_codes)
        filtered = [
            item
            for item in filtered
            if any(cpc.upper().startswith(prefixes) for cpc in item.cpc_codes)
        ]

    if filters.status:
        status = filters.status.lower()
        filtered = [
            item
            for item in filtered
            if status in (item.status or "").lower()
            or status in (item.application_status or "").lower()
        ]

    if filters.year_from or filters.year_to:
        filtered = [item for item in filtered if _matches_year_range(item, filters.year_from, filters.year_to)]

    return filtered


def _has_filters(filters: SearchFilters | None) -> bool:
    if filters is None:
        return False
    return any(
        [
            bool(filters.applicant),
            bool(filters.ipc_codes),
            bool(filters.cpc_codes),
            bool(filters.status),
            filters.year_from is not None,
            filters.year_to is not None,
        ]
    )


def _search_total_count(root: ET.Element, fallback: int) -> int:
    raw_count = _first_text(root, "TotalSearchCount")
    if raw_count is None:
        return fallback
    try:
        return int(raw_count)
    except ValueError:
        return fallback


def _restore_search_page(payload: object) -> PatentSearchPage:
    if isinstance(payload, dict):
        items = payload.get("items", [])
        total_count = payload.get("total_count", len(items) if isinstance(items, list) else 0)
        if isinstance(items, list) and isinstance(total_count, int):
            return PatentSearchPage(
                items=[PatentListItem.model_validate(item) for item in items],
                total_count=total_count,
            )
    if isinstance(payload, list):
        return PatentSearchPage(
            items=[PatentListItem.model_validate(item) for item in payload],
            total_count=len(payload),
        )
    raise KIPRISParseError("Cached KIPRIS search payload has an invalid shape")


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


def _first_file_path(root: ET.Element) -> str | None:
    for path in (_first_text(node, "path") for node in _find_all(root, "item")):
        if path:
            return path
    for path in (_first_text(node, "path") for node in _find_all(root, "filePathInfo")):
        if path:
            return path
    return _first_text(root, "path")


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _split_ipc(value: str | None) -> list[str]:
    return _split_codes(value)


def _split_codes(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[|,;]", value) if part.strip()]


def _dedupe_codes(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = re.sub(r"\s+", " ", value.strip())
        if not normalized:
            continue
        key = normalized.upper()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


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


def _patent_status(
    final_disposal: str | None,
    registration_status: str | None,
    open_date: str | None,
) -> str:
    raw_status = " ".join(value for value in [final_disposal, registration_status] if value).strip()
    if "등록" in raw_status:
        return "등록"
    if "거절" in raw_status:
        return "거절"
    if "취하" in raw_status:
        return "취하"
    if "포기" in raw_status:
        return "포기"
    if "소멸" in raw_status:
        return "소멸"
    if "무효" in raw_status:
        return "무효"
    if open_date:
        return "공개"
    return "출원"


def _kipris_search_url(patent_id: str | None) -> str:
    raw_id = (patent_id or "").strip()
    compact_id = _compact_patent_id(raw_id)
    query_text = raw_id.replace(" ", "") if re.search(r"[A-Za-z]", raw_id) else compact_id or raw_id
    if not query_text:
        return "https://www.kipris.or.kr/khome/search/searchResult.do?tab=patent"
    return f"https://www.kipris.or.kr/khome/search/searchResult.do?tab=patent&queryText={quote(query_text)}"


def _kipris_kpat_detail_url(patent_id: str | None) -> str | None:
    compact_id = _compact_patent_id(patent_id or "")
    if not compact_id:
        return None
    return f"https://www.kipris.or.kr/khome/detail/newWindow.do?applno={quote(compact_id)}&right=kpat"


def _patent_original_pdf_url(
    patent_id: str | None,
    api_public_base_url: str | None,
    status: str | None = None,
) -> str | None:
    compact_id = _compact_patent_id(patent_id or "")
    if not compact_id:
        return None
    path = f"/api/v1/patents/{quote(compact_id)}/original-pdf"
    if status:
        pdf_kind = "ann" if "등록" in status else "pub"
        path = f"{path}?kind={pdf_kind}"
    if api_public_base_url:
        return _join_url(api_public_base_url, path)
    return path


def _preview(value: str, limit: int = 120) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
