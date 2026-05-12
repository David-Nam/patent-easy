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

주의할 점은 자유검색/청구항 endpoint는 `accessKey`를 사용하고, 서지 상세 endpoint는 `/kipo-api/kipi/...` 경로와 `ServiceKey`를 사용한다는 점입니다.

## 환경변수 매핑

```env
KIPRIS_BASE_URL=http://plus.kipris.or.kr
KIPRIS_OPENAPI_KEY_PARAM=accessKey
KIPRIS_DETAIL_KEY_PARAM=ServiceKey
KIPRIS_SEARCH_PATH=/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo
KIPRIS_DETAIL_PATH=/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch
KIPRIS_CLAIM_PATH=/openapi/rest/patUtiModInfoSearchSevice/patentClaimInfo
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
| `TotalSearchCount` | `SearchResponse.pagination.total_count` |

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
| `biblioSummaryInfo.registerDate` | `PatentDetail.registration_date` |
| `biblioSummaryInfo.finalDisposal` / `registerStatus` | `PatentDetail.legal_status` |
| `applicantInfo.name` | `PatentDetail.applicant` |
| `inventorInfo.name` | `PatentDetail.inventors` |
| `ipcInfo.ipcNumber` | `PatentDetail.ipc_codes` |
| `astrtCont` | `PatentDetail.abstract` |

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
