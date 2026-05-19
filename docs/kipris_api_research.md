# KIPRIS Plus API 조사 결과

마지막 검증 실행 시각: `2026-05-06T23:38:58.341158+00:00`

이 문서는 PatentEasy 백엔드에서 사용하는 KIPRIS Plus API endpoint, key parameter, 응답 필드, fixture 위치를 정리합니다.

## 검증 정책

- 실제 검색 로직 구현 전 `KIPRIS_API_KEY`로 최소 호출을 검증합니다.
- raw 응답은 원본 XML/JSON 그대로 `tests/fixtures/kipris_raw/`에 저장합니다.
- 사람이 필드를 검토하기 쉬운 normalized JSON은 `tests/fixtures/kipris_normalized/`에 저장합니다.
- LLM provider key는 KIPRIS 검증에 필요하지 않습니다.
- broad test나 반복 live test는 KIPRIS 호출 한도를 소모하므로 필요한 경우에만 실행합니다.

## 핵심 결론

| 구분 | endpoint | key parameter | 응답 형식 | 구현 상태 |
|---|---|---|---|---|
| 자유검색 | `/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo` | `accessKey` | XML | 구현 완료 |
| 서지 상세 | `/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch` | `ServiceKey` | XML | 구현 완료 |
| 청구항 상세 | `/openapi/rest/patUtiModInfoSearchSevice/patentClaimInfo` | `accessKey` | XML | 구현 완료 |
| 공개전문 PDF | `/kipo-api/kipi/patUtiModInfoSearchSevice/getPubFullTextInfoSearch` | `ServiceKey` | XML | 구현 완료 |
| 공고전문 PDF | `/kipo-api/kipi/patUtiModInfoSearchSevice/getAnnFullTextInfoSearch` | `ServiceKey` | XML | 구현 완료 |
| 표준화 공개전문 PDF | `/kipo-api/kipi/patUtiModInfoSearchSevice/getStandardPubFullTextInfoSearch` | `ServiceKey` | XML | 구현 완료 |
| 표준화 공고전문 PDF | `/kipo-api/kipi/patUtiModInfoSearchSevice/getStandardAnnFullTextInfoSearch` | `ServiceKey` | XML | 구현 완료 |

주의할 점은 자유검색/청구항 endpoint는 `accessKey`를 사용하고, 서지 상세/원문 PDF endpoint는 `/kipo-api/kipi/...` 경로와 `ServiceKey`를 사용한다는 점입니다.

## 환경변수 매핑

```env
KIPRIS_BASE_URL=http://plus.kipris.or.kr
KIPRIS_OPENAPI_KEY_PARAM=accessKey
KIPRIS_DETAIL_KEY_PARAM=ServiceKey
KIPRIS_SEARCH_PATH=/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo
KIPRIS_DETAIL_PATH=/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch
KIPRIS_CLAIM_PATH=/openapi/rest/patUtiModInfoSearchSevice/patentClaimInfo
KIPRIS_FULL_TEXT_KEY_PARAM=ServiceKey
KIPRIS_PUB_FULL_TEXT_PATH=/kipo-api/kipi/patUtiModInfoSearchSevice/getPubFullTextInfoSearch
KIPRIS_ANN_FULL_TEXT_PATH=/kipo-api/kipi/patUtiModInfoSearchSevice/getAnnFullTextInfoSearch
KIPRIS_STANDARD_PUB_FULL_TEXT_PATH=/kipo-api/kipi/patUtiModInfoSearchSevice/getStandardPubFullTextInfoSearch
KIPRIS_STANDARD_ANN_FULL_TEXT_PATH=/kipo-api/kipi/patUtiModInfoSearchSevice/getStandardAnnFullTextInfoSearch
```

## 자유검색

| 항목 | 값 |
|---|---|
| path | `/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo` |
| key parameter | `accessKey` |
| 검증 HTTP status | `200` |
| 응답 형식 | XML |
| raw fixture | `tests/fixtures/kipris_raw/free_search_20260506T233857Z.xml` |
| normalized fixture | `tests/fixtures/kipris_normalized/free_search_20260506T233857Z.json` |
| 추출 record 수 | 5 |
| 첫 application number | `1020230147601` |

주요 request parameter:

| parameter | 설명 |
|---|---|
| `word` | 검색어 |
| `patent` | 특허 포함 여부 |
| `utility` | 실용신안 포함 여부 |
| `docsStart` | 검색 시작 번호 |
| `docsCount` | 조회 개수 |
| `lastvalue` | 정렬/검색 옵션, 현재 `R` 사용 |

백엔드 매핑:

| KIPRIS XML field | backend field |
|---|---|
| `ApplicationNumber` | `PatentListItem.patent_id` |
| `InventionName` | `PatentListItem.title` |
| `Applicant` | `PatentListItem.applicant` |
| `ApplicationDate` | `PatentListItem.application_date` |
| `InternationalpatentclassificationNumber` | `PatentListItem.ipc_codes` |
| `Abstract` | `PatentListItem.abstract_preview` |
| `OpeningDate` / `PublicDate` | `PatentListItem.publication_date` |
| `OpeningNumber` / `PublicNumber` | `PatentListItem.publication_number` |
| `RegistrationDate` | `PatentListItem.registration_date` |
| `RegistrationNumber` | `PatentListItem.registration_number` |
| `RegistrationStatus` | `PatentListItem.status`, `PatentListItem.application_status` |
| `ThumbnailPath` | `PatentListItem.thumbnail_url` |
| `DrawingPath` | `PatentListItem.drawing_url` |
| `TotalSearchCount` | `SearchResponse.pagination.total_count` |

`PatentListItem.kipris_url`은 KIPRIS XML에 직접 포함된 값이 아니라 출원번호 기반으로
생성한 KIPRIS 상세 새창 URL입니다. `original_url`은 검색 목록에서 원문 PDF redirect
endpoint(`/api/v1/patents/{applicationNumber}/original-pdf?kind=ann|pub`)를 가리킵니다. 프론트엔드는
이 상대 URL을 백엔드 base URL 기준으로 열어야 합니다.

KIPRIS 화면의 `openWindow('detail', ...)` 로직은 `/khome/detail/newWindow.do`에
`applno`, `right`를 전달합니다.

## 서지 상세

| 항목 | 값 |
|---|---|
| path | `/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch` |
| key parameter | `ServiceKey` |
| 검증 HTTP status | `200` |
| 응답 형식 | XML |
| raw fixture | `tests/fixtures/kipris_raw/bibliography_detail_20260506T233858Z.xml` |
| normalized fixture | `tests/fixtures/kipris_normalized/bibliography_detail_20260506T233858Z.json` |
| 첫 application number | `10-2023-0147601` |

백엔드 매핑:

| KIPRIS XML field | backend field |
|---|---|
| `biblioSummaryInfo.applicationNumber` | `PatentDetail.patent_id` |
| `biblioSummaryInfo.inventionTitle` | `PatentDetail.title` |
| `biblioSummaryInfo.applicationDate` | `PatentDetail.application_date` |
| `biblioSummaryInfo.openDate` | `PatentDetail.publication_date` |
| `biblioSummaryInfo.openNumber` | `PatentDetail.publication_number` |
| `biblioSummaryInfo.registerDate` | `PatentDetail.registration_date` |
| `biblioSummaryInfo.registerNumber` | `PatentDetail.registration_number` |
| `biblioSummaryInfo.finalDisposal` / `registerStatus` | `PatentDetail.legal_status` |
| `biblioSummaryInfo.finalDisposal` / `registerStatus` | `PatentDetail.status`, `PatentDetail.application_status` |
| `applicantInfo.name` | `PatentDetail.applicant` |
| `inventorInfo.name` | `PatentDetail.inventors` |
| `ipcInfo.ipcNumber` | `PatentDetail.ipc_codes` |
| `astrtCont` | `PatentDetail.abstract` |
| `legalStatusInfo` | `PatentDetail.legal_events[]` |
| `priorArtDocumentsInfo.documentsNumber` | `PatentDetail.cited_patents[]`, `PatentDetail.citation_count` |
| `familyInfo` | `PatentDetail.family_patents[]` |
| `imagePathInfo.path` | `PatentDetail.thumbnail_url` |
| `imagePathInfo.largePath` | `PatentDetail.drawing_url` |

현재 확인한 서지 상세 응답에는 피인용 목록이 없어서 `cited_by_patents`는 빈 배열,
`cited_by_count`는 `null`로 둡니다. 피인용 네트워크가 필수이면 별도 KIPRIS
endpoint 또는 KIPRIS 웹 화면의 안정적인 API 확인이 필요합니다.

상세 응답의 `original_url`은 아래 원문 PDF API가 반환한 `path`가 있으면 해당
`fileToss.jsp` URL을 사용하고, 없으면 원문 PDF redirect endpoint로 fallback합니다.

## 원문 PDF 경로

KIPRIS Plus 상품 설명의 `도면/전문` 분류에서 확인한 원문 PDF 관련 API입니다.
모두 입력값은 `applicationNumber`이고, 출력값은 `docName`, `path`입니다.

| 항목 | path | 우선순위 |
|---|---|---|
| 표준화 공고전문 PDF | `/kipo-api/kipi/patUtiModInfoSearchSevice/getStandardAnnFullTextInfoSearch` | 등록 상태 특허 1순위 |
| 공고전문 PDF | `/kipo-api/kipi/patUtiModInfoSearchSevice/getAnnFullTextInfoSearch` | 등록 상태 특허 2순위 |
| 표준화 공개전문 PDF | `/kipo-api/kipi/patUtiModInfoSearchSevice/getStandardPubFullTextInfoSearch` | 공개 상태 특허 1순위 |
| 공개전문 PDF | `/kipo-api/kipi/patUtiModInfoSearchSevice/getPubFullTextInfoSearch` | 공개 상태 특허 2순위 |

샘플 요청 형식:

```text
http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getAnnFullTextInfoSearch?applicationNumber=1020050050026&ServiceKey=서비스키
```

샘플 응답의 핵심 구조:

```xml
<item>
  <docName>1020050050026.pdf</docName>
  <path>http://plus.kipris.or.kr/kiprisplusws/fileToss.jsp?arg=...</path>
</item>
```

## 청구항 상세

| 항목 | 값 |
|---|---|
| path | `/openapi/rest/patUtiModInfoSearchSevice/patentClaimInfo` |
| key parameter | `accessKey` |
| 검증 HTTP status | `200` |
| 응답 형식 | XML |
| raw fixture | `tests/fixtures/kipris_raw/claim_detail_20260506T233858Z.xml` |
| normalized fixture | `tests/fixtures/kipris_normalized/claim_detail_20260506T233858Z.json` |

백엔드 매핑:

| KIPRIS XML field | backend field |
|---|---|
| `claimInfo.claim` | `PatentDetail.claims[].text` |

청구항 번호는 청구항 text 앞의 `1.`, `2.` 패턴에서 추출하고, 패턴이 없으면 응답 순서를 fallback으로 사용합니다.

## 구현 파일

| 파일 | 역할 |
|---|---|
| `scripts/verify_kipris_api.py` | 실제 KIPRIS 최소 호출, raw/normalized fixture 생성 |
| `app/services/kipris_client.py` | KIPRIS 검색/상세/청구항 client |
| `tests/test_kipris_client.py` | fixture 기반 파싱, cache, pagination 테스트 |
| `tests/test_search_live.py` | 실제 KIPRIS 검색 endpoint live 테스트 |
| `tests/test_summary_live.py` | 실제 KIPRIS 상세/청구항 + Gemini 요약 live 테스트 |

## 재검증 명령

fixture 재생성:

```bash
venv/bin/python scripts/verify_kipris_api.py
```

offline fixture 테스트:

```bash
venv/bin/python -m pytest tests/test_kipris_client.py
```

실제 KIPRIS 검색 live 테스트:

```bash
RUN_LIVE_KIPRIS=1 venv/bin/python -m pytest tests/test_search_live.py -m live_kipris -s
```

실제 KIPRIS + Gemini 요약 live 테스트:

```bash
RUN_LIVE_KIPRIS=1 RUN_LIVE_LLM=1 \
venv/bin/python -m pytest tests/test_summary_live.py -m "live_kipris and live_llm" -s
```

## 남은 확인 사항

- KIPRIS Plus 계정 화면에서 실제 일 호출 한도와 서비스별 제한을 주기적으로 확인합니다.
- KIPRIS 응답 XML field가 변경될 경우 `scripts/verify_kipris_api.py`로 fixture를 다시 생성합니다.
- 검색 결과의 relevance score는 현재 KIPRIS 응답 순서 기반 임시 점수입니다. LLM reranking 또는 별도 평가 지표를 적용하면 이 문서에 반영합니다.
