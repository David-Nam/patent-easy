# PatentEasy 백엔드 API Reference

이 문서는 PatentEasy 백엔드 서버를 직접 호출하거나 프론트엔드에서 연동할 때
필요한 API 계약을 정리합니다. Swagger UI가 자동 생성 문서라면, 이 문서는
사람이 전체 기능과 현재 구현 상태를 빠르게 이해하기 위한 상세 설명서입니다.

## 빠른 요약

| Method | Path | 용도 | 외부 의존성 |
|---|---|---|---|
| `GET` | `/health` | 앱 프로세스 상태 확인 | 없음 |
| `GET` | `/ready` | cache, KIPRIS, LLM 설정 준비 상태 확인 | cache 설정 |
| `POST` | `/api/v1/search` | 자연어 아이디어로 관련 특허 검색 | KIPRIS, Gemini |
| `GET` | `/api/v1/patents/{patent_id}` | 특허 상세 조회 | KIPRIS |
| `GET` | `/api/v1/patents/{patent_id}/original-pdf` | KIPRIS Plus 원문 PDF로 redirect | KIPRIS |
| `GET` | `/api/v1/patents/{patent_id}/similar` | 기준 특허와 유사한 특허 조회 | KIPRIS |
| `POST` | `/api/v1/patents/{patent_id}/summary` | 특허 청구항 기반 AI 요약 | KIPRIS, Gemini |
| `POST` | `/api/v1/patents/{patent_id}/chat` | 단일 특허 기반 Q&A 챗봇 | KIPRIS, Gemini |

## 문서와 실제 명세 확인 위치

서버 실행 후 다음 URL에서 자동 생성 문서를 볼 수 있습니다.

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

이 문서는 구현 의도, 현재 제한사항, 사용 예시를 설명합니다. 필드의 최종
기계 판독 명세는 `/openapi.json`이 기준입니다.

## Base URL

로컬 개발 기본값:

```text
http://127.0.0.1:8000
```

프론트엔드에서는 환경변수로 base URL을 분리하는 방식을 권장합니다.

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

배포 후에는 이 값을 실제 백엔드 공개 URL로 바꾸면 됩니다.

## 인증과 API Key 정책

현재 PatentEasy 백엔드의 public API 자체에는 별도 사용자 인증이나 frontend용
API key가 없습니다.

다만 백엔드 내부에서 외부 서비스를 호출하기 위해 다음 서버 환경변수가 필요합니다.

| 변수 | 사용 위치 | frontend 전달 여부 |
|---|---|---:|
| `KIPRIS_API_KEY` | KIPRIS 검색, 서지 상세, 청구항, 원문 PDF 경로 조회 | 전달 금지 |
| `GEMINI_API_KEY` | `LLM_PROVIDER=gemini`일 때 키워드 추출/요약 | 전달 금지 |
| `OPENAI_API_KEY` | `LLM_PROVIDER=openai`일 때 키워드 추출/요약 | 전달 금지 |

프론트엔드는 위 key를 읽거나 요청에 포함하면 안 됩니다. 모든 외부 API key는
백엔드 서버의 `.env` 또는 배포 환경변수에만 존재해야 합니다.

## 현재 구현 상태와 주의사항

현재 구현은 다음과 같이 동작합니다.

| 기능 | 현재 구현 |
|---|---|
| 검색 `/api/v1/search` | Query Builder가 자연어를 키워드로 바꾸고 KIPRIS 검색 API를 호출합니다. |
| 상세 `/api/v1/patents/{patent_id}` | KIPRIS 서지 상세/청구항 API를 호출하고, 원문 PDF 경로가 있으면 `original_url`에 반영합니다. |
| 원문 PDF `/api/v1/patents/{patent_id}/original-pdf` | KIPRIS Plus 원문 PDF 경로 API를 호출해 실제 PDF 파일 경로로 redirect합니다. |
| 유사특허 `/api/v1/patents/{patent_id}/similar` | KIPRIS 상세에서 제목/IPC를 추출한 뒤 KIPRIS 검색 API로 후보를 반환합니다. |
| 요약 `/api/v1/patents/{patent_id}/summary` | KIPRIS 서지 상세/청구항 API를 호출한 뒤 LLM으로 요약합니다. |
| 챗봇 `/api/v1/patents/{patent_id}/chat` | KIPRIS 서지 상세/청구항 API를 호출한 뒤 단일 특허 context Q&A를 수행합니다. |

## 공통 응답 정책

모든 성공 응답은 JSON입니다.

```http
Content-Type: application/json
```

모든 응답에는 요청 추적용 `x-request-id` header가 붙습니다. 클라이언트가
요청 header에 `x-request-id`를 넣으면 그 값을 그대로 사용하고, 없으면 서버가
새 값을 생성합니다. 운영 중 오류 문의나 로그 추적에는 이 값을 함께 남기는
방식을 권장합니다.

오류 응답은 다음 표준 구조를 사용합니다.

```json
{
  "code": "SEARCH_UPSTREAM_ERROR",
  "message": "KIPRIS returned HTTP 503",
  "details": {
    "source": "kipris",
    "kind": "http_5xx",
    "status_code": 503
  }
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `code` | string | 프론트엔드가 분기 처리할 수 있는 에러 코드 |
| `message` | string | 사람이 읽을 수 있는 오류 메시지 |
| `details` | object 또는 null | source, kind, status_code 등 디버깅 정보 |

대표적인 공통 오류:

| HTTP Status | code | 의미 |
|---:|---|---|
| `404` | `HTTP_ERROR` | 존재하지 않는 route |
| `422` | `VALIDATION_ERROR` | 요청 body 또는 query 형식 오류 |
| `500` | `INTERNAL_SERVER_ERROR` | 예상하지 못한 서버 내부 오류 |

## 상태 확인 API

### `GET /health`

앱 프로세스가 떠 있는지 확인합니다. 외부 서비스 준비 상태는 확인하지 않습니다.

#### Request

```bash
curl -s http://127.0.0.1:8000/health
```

#### Response `200`

```json
{
  "status": "ok",
  "service": "patent-easy-backend",
  "version": "0.1.0",
  "environment": "local"
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `status` | string | 앱 프로세스 상태. 정상은 `ok` |
| `service` | string | 서비스 식별자 |
| `version` | string | 앱 버전 |
| `environment` | string | `APP_ENV` 값 |

### `GET /ready`

배포 환경에서 트래픽을 받아도 되는지 확인합니다. cache 연결, KIPRIS key 설정,
LLM provider 설정 상태를 확인합니다.

#### Request

```bash
curl -s http://127.0.0.1:8000/ready
```

#### Response `200`

```json
{
  "status": "ready",
  "service": "patent-easy-backend",
  "checks": {
    "cache": {
      "status": "ok",
      "path": "./data/cache.sqlite"
    },
    "kipris": {
      "status": "configured",
      "base_url": "http://plus.kipris.or.kr"
    },
    "llm": {
      "status": "configured",
      "provider": "gemini",
      "model": "gemini-2.5-flash-lite"
    }
  }
}
```

#### Response `503`

KIPRIS key가 없거나, LLM provider key가 없거나, cache DB를 열 수 없으면
`not_ready`가 반환됩니다.

```json
{
  "status": "not_ready",
  "service": "patent-easy-backend",
  "checks": {
    "cache": {
      "status": "ok",
      "path": "./data/cache.sqlite"
    },
    "kipris": {
      "status": "not_configured",
      "base_url": "http://plus.kipris.or.kr"
    },
    "llm": {
      "status": "not_configured",
      "provider": "gemini",
      "model": "gemini-2.5-flash-lite"
    }
  }
}
```

## 검색 API

### `POST /api/v1/search`

사용자가 입력한 자연어 아이디어를 특허 검색용 키워드와 IPC 후보로 바꾼 뒤,
KIPRIS 검색 결과를 반환합니다.

현재 흐름:

```text
사용자 자연어
→ QueryBuilder: 키워드/IPC/확장어 추출
→ KIPRISClient: 추출 키워드로 KIPRIS 자유검색 API 호출
→ SearchResponse 반환
```

현재 검색 요청에서 실제 KIPRIS `word` parameter로 들어가는 값은
`extracted.keywords`를 합친 문자열입니다. `extracted.ipc_codes`와
`extracted.expanded_terms`는 응답에 포함되지만, 자동 검색 필터로 적용되지는
않습니다. IPC 필터링이 필요하면 요청의 `filters.ipc_codes`에 명시해야 합니다.

또한 `filters`는 현재 KIPRIS가 반환한 현재 page 결과에 대해 백엔드에서
후처리로 적용됩니다. 따라서 필터를 사용한 경우 `total_count`는 KIPRIS 전체
검색 결과 수가 아니라 현재 page에서 필터를 통과한 결과 수를 의미합니다. 이
동작은 배포 전 검색 정밀도 개선 단계에서 다시 조정할 수 있습니다.

#### Request Body

```json
{
  "query": "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능",
  "filters": {
    "applicant": "삼성전자",
    "ipc_codes": ["G06V", "A23L"],
    "cpc_codes": ["G06V"],
    "status": "등록",
    "year_from": 2020,
    "year_to": 2026
  },
  "page": 1,
  "page_size": 10
}
```

| 필드 | 타입 | 필수 | 제약 | 설명 |
|---|---|---:|---|---|
| `query` | string | 예 | 2~500자 | 사용자의 자연어 아이디어 |
| `filters` | object | 아니오 | 기본 `{}` | 검색 필터 |
| `filters.applicant` | string 또는 null | 아니오 | 제한 없음 | 출원인명 부분 검색 |
| `filters.ipc_codes` | string[] 또는 null | 아니오 | prefix 매칭 | IPC prefix 후보 |
| `filters.cpc_codes` | string[] 또는 null | 아니오 | prefix 매칭 | CPC prefix 후보 |
| `filters.status` | string 또는 null | 아니오 | 부분 매칭 | 등록, 공개, 거절, 취하 등 상태 필터 |
| `filters.year_from` | integer 또는 null | 아니오 | 1900~2100 | 출원연도 시작 |
| `filters.year_to` | integer 또는 null | 아니오 | 1900~2100 | 출원연도 끝 |
| `page` | integer | 아니오 | 1 이상, 기본 1 | 페이지 번호 |
| `page_size` | integer | 아니오 | 1~50, 기본 10 | 페이지당 결과 수 |

`year_from`이 `year_to`보다 크면 `422 VALIDATION_ERROR`가 반환됩니다.

#### 최소 Request

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능",
    "page": 1,
    "page_size": 10
  }'
```

#### Response `200`

```json
{
  "query": "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능",
  "extracted": {
    "keywords": ["음식 이미지 인식", "칼로리 자동 계산", "맞춤형 식단 추천"],
    "ipc_codes": ["G06V", "G06N", "A23L"],
    "expanded_terms": {
      "음식 이미지 인식": ["식품 영상 인식", "음식 사진 식별", "식품 객체 검출"],
      "칼로리 자동 계산": ["열량 산출", "영양성분 분석", "식품 영양 추정"],
      "맞춤형 식단 추천": ["개인화 식단", "건강 상태 기반 추천", "영양 관리"]
    }
  },
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_count": 180195,
    "total_pages": 18020
  },
  "results": [
    {
      "patent_id": "10-2023-0147601",
      "title": "전기자동차의 배터리 열관리 시스템 및 이의 운용 방법",
      "applicant": "서울대학교산학협력단",
      "application_date": "2023-10-31",
      "ipc_codes": ["B60H 1/32", "B60L 58/24"],
      "cpc_codes": [],
      "status": "등록",
      "application_status": "등록",
      "publication_date": "2025-05-09",
      "publication_number": "10-2025-0064010",
      "registration_date": "2026-04-29",
      "registration_number": "1029609060000",
      "citation_count": null,
      "cited_by_count": null,
      "similarity_score": 100,
      "relevance_score": 100,
      "tags": [],
      "abstract_preview": "주행 데이터에 따라 최적의 배터리 열관리 모드를 도출한다.",
      "thumbnail_url": "http://plus.kipris.or.kr/openapi/fileToss.jsp?...",
      "drawing_url": "http://plus.kipris.or.kr/openapi/fileToss.jsp?...",
      "kipris_url": "https://www.kipris.or.kr/khome/detail/newWindow.do?applno=1020230147601&right=kpat",
      "original_url": "/api/v1/patents/1020230147601/original-pdf?kind=ann"
    }
  ]
}
```

#### Response Fields

| 필드 | 타입 | 설명 |
|---|---|---|
| `query` | string | 원본 사용자 입력 |
| `extracted` | object | Query Builder가 추출한 검색 개념 |
| `extracted.keywords` | string[] | 핵심 검색 키워드 |
| `extracted.ipc_codes` | string[] | 추정 IPC prefix 후보 |
| `extracted.expanded_terms` | object | 키워드별 확장어/동의어 후보 |
| `pagination` | object | 페이지 정보 |
| `pagination.page` | integer | 현재 페이지 |
| `pagination.page_size` | integer | 페이지당 결과 수 |
| `pagination.total_count` | integer | 전체 검색 결과 수 |
| `pagination.total_pages` | integer | 전체 페이지 수 |
| `results` | PatentListItem[] | 특허 목록 |

#### PatentListItem

| 필드 | 타입 | 설명 |
|---|---|---|
| `patent_id` | string | 특허/출원 식별자 |
| `title` | string | 발명의 명칭 |
| `applicant` | string | 출원인 |
| `application_date` | string 또는 null | 출원일, `YYYY-MM-DD` |
| `ipc_codes` | string[] | IPC 코드 |
| `cpc_codes` | string[] | CPC 코드. 현재 KIPRIS 응답에 없으면 빈 배열 |
| `status` | string 또는 null | 프론트 배지용 정규화 상태. 예: `등록`, `공개`, `거절`, `취하` |
| `application_status` | string 또는 null | `status`와 동일한 표시용 상태. 프론트 명명 차이 대응 |
| `publication_date` | string 또는 null | 공개일 또는 공고일 |
| `publication_number` | string 또는 null | 공개번호 또는 공고번호 |
| `registration_date` | string 또는 null | 등록일 |
| `registration_number` | string 또는 null | 등록번호 |
| `citation_count` | integer 또는 null | KIPRIS 상세의 선행기술문헌 수. 검색 목록에서는 알 수 없으면 null |
| `cited_by_count` | integer 또는 null | 피인용 수. 현재 사용 중인 KIPRIS endpoint에서 제공하지 않으면 null |
| `similarity_score` | integer 또는 null | 유사도/관련도 표시용 점수 |
| `relevance_score` | integer | 백엔드 내부 관련도 점수, 0~100 |
| `tags` | string[] | 태그. 실제 KIPRIS 검색에서는 비어 있을 수 있음 |
| `abstract_preview` | string | 초록 요약 미리보기 |
| `thumbnail_url` | string 또는 null | KIPRIS 대표도면 thumbnail URL |
| `drawing_url` | string 또는 null | KIPRIS 대표도면 원본 크기 URL |
| `kipris_url` | string 또는 null | KIPRIS 이동 URL. 국내 특허는 KIPRIS 상세 새창 URL |
| `original_url` | string 또는 null | 원문보기 버튼용 URL. 검색 목록에서는 백엔드 redirect endpoint, 상세에서는 가능하면 KIPRIS Plus PDF 파일 경로 |

#### Search Error Responses

| HTTP Status | code | details 예시 | 의미 |
|---:|---|---|---|
| `422` | `VALIDATION_ERROR` | `{"errors": [...]}` | 요청 형식 오류 |
| `502` | `SEARCH_UPSTREAM_ERROR` | `{"source":"kipris","kind":"timeout"}` | KIPRIS timeout |
| `502` | `SEARCH_UPSTREAM_ERROR` | `{"source":"kipris","kind":"http_4xx"}` | KIPRIS 4xx |
| `502` | `SEARCH_UPSTREAM_ERROR` | `{"source":"kipris","kind":"http_5xx"}` | KIPRIS 5xx |
| `502` | `SEARCH_UPSTREAM_ERROR` | `{"source":"kipris","kind":"xml_parse_error"}` | KIPRIS XML 파싱 실패 |
| `502` | `SEARCH_UPSTREAM_ERROR` | `{"source":"llm","kind":"provider_error"}` | LLM provider 호출 실패 |
| `502` | `SEARCH_UPSTREAM_ERROR` | `{"source":"llm","kind":"parse_error"}` | LLM JSON/schema 파싱 실패 |
| `503` | `SEARCH_CONFIGURATION_ERROR` | `{"source":"kipris","kind":"configuration_error"}` | KIPRIS key 누락 |
| `503` | `SEARCH_CONFIGURATION_ERROR` | `{"source":"llm","kind":"configuration_error"}` | LLM provider 설정 오류 |

## 특허 상세 API

### `GET /api/v1/patents/{patent_id}`

특허 상세 정보를 반환합니다.

현재 이 엔드포인트는 KIPRIS 서지 상세 API, 청구항 API, 원문 PDF 경로 API를 호출합니다.
처음 호출은 외부 API 응답 시간만큼 느릴 수 있고, 이후에는 상세 cache TTL 동안
SQLite cache를 사용할 수 있습니다.

#### Request

```bash
curl -s http://127.0.0.1:8000/api/v1/patents/10-2023-0147601
```

#### Path Parameters

| 이름 | 타입 | 설명 |
|---|---|---|
| `patent_id` | string | 특허 ID 또는 출원번호 형식 ID |

#### Response `200`

```json
{
  "patent_id": "10-2023-0147601",
  "title": "전기자동차의 배터리 열관리 시스템 및 이의 운용 방법",
  "applicant": "서울대학교산학협력단",
  "application_date": "2023-10-31",
  "ipc_codes": ["B60H 1/32", "B60L 58/24"],
  "cpc_codes": [],
  "status": "등록",
  "application_status": "등록",
  "publication_date": "2025-05-09",
  "publication_number": "10-2025-0064010",
  "registration_date": "2026-04-29",
  "registration_number": "10-2960906-0000",
  "citation_count": 5,
  "cited_by_count": null,
  "similarity_score": 100,
  "relevance_score": 100,
  "tags": [],
  "abstract_preview": "전기자동차의 배터리 열관리 시스템에 관한 발명입니다.",
  "thumbnail_url": "http://plus.kipris.or.kr/openapi/fileToss.jsp?...",
  "drawing_url": "http://plus.kipris.or.kr/openapi/fileToss.jsp?...",
  "kipris_url": "https://www.kipris.or.kr/khome/detail/newWindow.do?applno=1020230147601&right=kpat",
  "original_url": "http://plus.kipris.or.kr/kiprisplusws/fileToss.jsp?arg=...",
  "abstract": "본 발명은 전기자동차의 배터리 열관리 시스템 및 이의 운용 방법에 관한 것이다.",
  "inventors": ["김민수", "황인찬", "이상욱", "정연우"],
  "legal_status": "등록결정(일반)",
  "claims": [
    {
      "number": 1,
      "text": "전기자동차에 동력을 제공하는 배터리와 제어부를 포함하는 전기자동차의 배터리 열관리 시스템."
    }
  ],
  "legal_events": [
    {
      "status": "수리 (Accepted)",
      "document_name": "[특허출원]특허출원서",
      "receipt_date": "2023-10-31",
      "receipt_number": "1-1-2023-1197539-71"
    }
  ],
  "cited_patents": [
    {
      "patent_id": "KR1020200101558 A",
      "relation": "cited",
      "source": "prior_art_documents",
      "kipris_url": "https://www.kipris.or.kr/khome/search/searchResult.do?tab=patent&queryText=KR1020200101558A",
      "original_url": "https://www.kipris.or.kr/khome/search/searchResult.do?tab=patent&queryText=KR1020200101558A"
    }
  ],
  "cited_by_patents": [],
  "family_patents": []
}
```

#### PatentDetail

`PatentDetail`은 `PatentListItem` 필드에 다음 필드를 추가합니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `abstract` | string | 초록 원문 또는 정규화된 초록 |
| `inventors` | string[] | 발명자 |
| `legal_status` | string 또는 null | 법적 상태 |
| `claims` | Claim[] | 청구항 목록 |
| `legal_events` | LegalEvent[] | 출원/보정/거절이유통지/등록결정 등 진행 이벤트 |
| `cited_patents` | PatentReference[] | KIPRIS 선행기술문헌 기반 인용 후보 |
| `cited_by_patents` | PatentReference[] | 피인용 특허. 현재 사용 endpoint에서 제공하지 않으면 빈 배열 |
| `family_patents` | PatentReference[] | 국내 패밀리 특허. 없으면 빈 배열 |

#### Claim

| 필드 | 타입 | 설명 |
|---|---|---|
| `number` | integer | 청구항 번호 |
| `text` | string | 청구항 원문 |

#### LegalEvent

| 필드 | 타입 | 설명 |
|---|---|---|
| `status` | string 또는 null | KIPRIS 공통 코드명 |
| `document_name` | string 또는 null | 서류명 |
| `receipt_date` | string 또는 null | 접수일 |
| `receipt_number` | string 또는 null | 접수번호 |

#### PatentReference

| 필드 | 타입 | 설명 |
|---|---|---|
| `patent_id` | string 또는 null | 참조 특허/문헌 번호 |
| `title` | string 또는 null | 발명의 명칭. KIPRIS 응답에 없으면 null |
| `applicant` | string 또는 null | 출원인. KIPRIS 응답에 없으면 null |
| `application_date` | string 또는 null | 출원일 |
| `status` | string 또는 null | 상태 |
| `relation` | string 또는 null | `cited`, `cited_by`, `family` 등 관계 |
| `source` | string 또는 null | 매핑 출처 |
| `kipris_url` | string 또는 null | KIPRIS 이동 URL |
| `original_url` | string 또는 null | 원문보기 버튼용 URL |

#### Error Responses

| HTTP Status | code | 의미 |
|---:|---|---|
| `404` | `PATENT_NOT_FOUND` | 해당 특허 상세를 찾을 수 없음 |
| `502` | `DETAIL_UPSTREAM_ERROR` | KIPRIS timeout, HTTP 오류, XML 파싱 실패 등 |
| `503` | `DETAIL_CONFIGURATION_ERROR` | KIPRIS key 누락 또는 설정 오류 |

예시:

```json
{
  "code": "PATENT_NOT_FOUND",
  "message": "존재하지 않는 특허 ID입니다.",
  "details": {
    "patent_id": "not-found"
  }
}
```

## 원문 PDF API

### `GET /api/v1/patents/{patent_id}/original-pdf`

KIPRIS Plus의 공개전문PDF/공고전문PDF API에서 원문 PDF 파일 경로를 조회한 뒤,
KIPRIS Plus `fileToss.jsp` URL로 `307 Temporary Redirect`합니다. 프론트엔드는
검색 결과의 상대 `original_url`을 사용할 때 반드시 `NEXT_PUBLIC_API_BASE_URL` 기준으로
절대 URL을 만든 뒤 새 창을 열어야 합니다.

등록 상태 특허는 공고전문PDF를 먼저 조회하고, 미등록/공개 상태 특허는 공개전문PDF를
먼저 조회합니다. PDF 경로를 찾지 못하면 KIPRIS 상세 화면으로 fallback redirect합니다.
`kind=ann`은 공고전문PDF 우선, `kind=pub`은 공개전문PDF 우선, `kind=auto`는 공개전문PDF
우선 조회를 의미합니다.

#### Request

```bash
curl -I http://127.0.0.1:8000/api/v1/patents/10-2023-0147601/original-pdf
```

#### Response `307`

```http
HTTP/1.1 307 Temporary Redirect
Location: http://plus.kipris.or.kr/kiprisplusws/fileToss.jsp?arg=...
```

## 유사특허 API

### `GET /api/v1/patents/{patent_id}/similar`

기준 특허를 KIPRIS 상세 API로 조회한 뒤, 제목 키워드와 IPC main group을 이용해
KIPRIS 검색 API에서 유사 후보를 반환합니다. 완전한 의미 기반 추천 엔진이 아니라
KIPRIS 실데이터 기반 1차 후보 목록입니다.

#### Request

```bash
curl -s 'http://127.0.0.1:8000/api/v1/patents/10-2023-0147601/similar?limit=5'
```

| 이름 | 타입 | 설명 |
|---|---|---|
| `patent_id` | string | 기준 특허 ID 또는 출원번호 |
| `limit` | integer | 1~10, 기본 5 |

#### Response `200`

```json
{
  "patent_id": "10-2023-0147601",
  "strategy": "kipris_title_ipc_search",
  "results": [
    {
      "patent_id": "10-2022-0033592",
      "title": "전기자동차 배터리 냉각 방법",
      "applicant": "테스트",
      "application_date": "2022-01-01",
      "ipc_codes": ["B60L"],
      "cpc_codes": [],
      "status": "공개",
      "application_status": "공개",
      "relevance_score": 90,
      "similarity_score": 90,
      "tags": [],
      "abstract_preview": "전기자동차 배터리 제어 기술이다.",
      "kipris_url": "https://www.kipris.or.kr/khome/detail/newWindow.do?applno=1020220033592&right=kpat",
      "original_url": "/api/v1/patents/1020220033592/original-pdf?kind=pub"
    }
  ]
}
```

#### Similar Error Responses

| HTTP Status | code | 의미 |
|---:|---|---|
| `404` | `PATENT_NOT_FOUND` | 기준 특허 상세를 찾을 수 없음 |
| `502` | `SIMILAR_UPSTREAM_ERROR` | KIPRIS timeout, HTTP 오류, XML 파싱 실패 등 |
| `503` | `SIMILAR_CONFIGURATION_ERROR` | KIPRIS key 누락 또는 설정 오류 |

## 요약 API

### `POST /api/v1/patents/{patent_id}/summary`

KIPRIS에서 특허 서지 상세와 청구항을 조회한 뒤, LLM provider를 사용해
비즈니스 관점 요약을 생성합니다.

현재 흐름:

```text
patent_id
→ KIPRIS 서지 상세 API
→ KIPRIS 청구항 API
→ LLM 요약
→ SummaryResponse 반환
```

#### Request

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/patents/10-2023-0147601/summary \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "전기차 배터리 열관리 기능"
  }'
```

#### Path Parameters

| 이름 | 타입 | 설명 |
|---|---|---|
| `patent_id` | string | KIPRIS에서 조회할 특허 ID 또는 출원번호 |

#### Request Body

```json
{
  "user_query": "전기차 배터리 열관리 기능"
}
```

| 필드 | 타입 | 필수 | 제약 | 설명 |
|---|---|---:|---|---|
| `user_query` | string 또는 null | 아니오 | 최대 500자 | 사용자의 원래 검색 의도. 요약 관점 보정에 사용 |

빈 body도 허용됩니다.

```json
{}
```

#### Response `200`

```json
{
  "patent_id": "10-2023-0147601",
  "core_summary": "이 특허는 전기차의 주행 데이터와 배터리 상태를 바탕으로 최적의 배터리 열관리 모드를 선택하는 기술입니다.",
  "business_application": "전기차 배터리 보호, 겨울철 주행거리 개선, 열관리 소프트웨어 기획에 참고할 수 있습니다.",
  "key_tags": ["전기차", "배터리", "열관리"],
  "generated_at": "2026-05-13T09:00:00Z",
  "is_cached": false,
  "disclaimer": "이 요약은 참고용입니다. 정확한 권리범위 판단은 변리사 자문을 받으세요."
}
```

#### Response Fields

| 필드 | 타입 | 설명 |
|---|---|---|
| `patent_id` | string | 요약 대상 특허 ID |
| `core_summary` | string | 핵심 기술 요약 |
| `business_application` | string | 비즈니스 관점 활용/검토 포인트 |
| `key_tags` | string[] | 주요 태그 |
| `generated_at` | datetime string | 요약 생성 시각 |
| `is_cached` | boolean | cache에서 가져온 요약인지 여부 |
| `disclaimer` | string | 법률 자문 아님 고지문 |

#### Summary Error Responses

| HTTP Status | code | details 예시 | 의미 |
|---:|---|---|---|
| `404` | `PATENT_NOT_FOUND` | `{"patent_id":"..."}` | 특허 상세 조회 결과 없음 |
| `422` | `VALIDATION_ERROR` | `{"errors": [...]}` | 요청 형식 오류 |
| `502` | `SUMMARY_UPSTREAM_ERROR` | `{"source":"kipris","kind":"timeout"}` | KIPRIS timeout |
| `502` | `SUMMARY_UPSTREAM_ERROR` | `{"source":"kipris","kind":"xml_parse_error"}` | KIPRIS XML 파싱 실패 |
| `502` | `SUMMARY_UPSTREAM_ERROR` | `{"source":"llm","kind":"provider_error"}` | LLM provider 호출 실패 |
| `502` | `SUMMARY_UPSTREAM_ERROR` | `{"source":"llm","kind":"parse_error"}` | LLM JSON/schema 파싱 실패 |
| `503` | `SUMMARY_CONFIGURATION_ERROR` | `{"source":"kipris","kind":"configuration_error"}` | KIPRIS key 누락 |
| `503` | `SUMMARY_CONFIGURATION_ERROR` | `{"source":"llm","kind":"configuration_error"}` | LLM provider key 또는 설정 오류 |

## 챗봇 API

### `POST /api/v1/patents/{patent_id}/chat`

단일 특허를 기준으로 사용자의 질문에 답합니다. 전통적인 벡터DB 기반 RAG가 아니라,
KIPRIS에서 조회한 초록과 청구항을 LLM context로 제공하는 LLM 기반 Q&A 구조입니다.

현재 흐름:

```text
patent_id
→ KIPRIS 서지 상세 API
→ KIPRIS 청구항 API
→ LLM Q&A
→ 서버가 근거 snippet 매핑
→ ChatResponse 반환
```

#### Request

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/patents/10-2023-0147601/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "이 특허는 전기차 배터리 열관리 기능과 관련이 있나요?",
    "user_query": "전기차 배터리 열관리 기능",
    "history": []
  }'
```

| 필드 | 타입 | 필수 | 제약 | 설명 |
|---|---|---:|---|---|
| `question` | string | 예 | 2~500자 | 특허에 대해 묻는 질문 |
| `user_query` | string 또는 null | 아니오 | 최대 500자 | 사용자의 원래 검색 의도 |
| `history` | message[] | 아니오 | 최대 6개 | 클라이언트가 보관한 최근 대화 |

`history` item:

```json
{ "role": "user", "content": "이 특허 핵심이 뭐야?" }
```

`role`은 `user` 또는 `assistant`만 허용하고, `content`는 1~1000자입니다.

#### Response `200`

```json
{
  "patent_id": "10-2023-0147601",
  "answer": "청구항 1 기준으로 배터리 열관리 기능과 관련이 있습니다.",
  "sources": [
    {
      "type": "claim",
      "claim_number": 1,
      "snippet": "전기자동차 배터리의 온도와 주행 데이터를 이용하여..."
    }
  ],
  "generated_at": "2026-05-15T09:00:00Z",
  "is_cached": false,
  "disclaimer": "이 답변은 참고용입니다. 정확한 권리범위 판단은 변리사 자문을 받으세요."
}
```

#### Chat Error Responses

| HTTP Status | code | details 예시 | 의미 |
|---:|---|---|---|
| `404` | `PATENT_NOT_FOUND` | `{"patent_id":"..."}` | 특허 상세 조회 결과 없음 |
| `422` | `VALIDATION_ERROR` | `{"errors": [...]}` | 요청 형식 오류 |
| `502` | `CHAT_UPSTREAM_ERROR` | `{"source":"kipris","kind":"timeout"}` | KIPRIS timeout |
| `502` | `CHAT_UPSTREAM_ERROR` | `{"source":"llm","kind":"provider_error"}` | LLM provider 호출 실패 |
| `502` | `CHAT_UPSTREAM_ERROR` | `{"source":"llm","kind":"parse_error"}` | LLM JSON/schema 파싱 실패 |
| `503` | `CHAT_CONFIGURATION_ERROR` | `{"source":"llm","kind":"configuration_error"}` | LLM provider key 또는 설정 오류 |

## 캐시 동작

백엔드는 SQLite cache를 사용합니다.

| 대상 | 기본 TTL | 환경변수 |
|---|---:|---|
| KIPRIS 검색 결과 | 86400초 | `CACHE_TTL_SEARCH` |
| KIPRIS 상세 결과 | 604800초 | `CACHE_TTL_DETAIL` |
| LLM 요약 결과 | 2592000초 | `CACHE_TTL_SUMMARY` |
| LLM 챗봇 답변 | 86400초 | `CACHE_TTL_CHAT` |

캐시 DB 경로:

```env
CACHE_DB_PATH=./data/cache.sqlite
```

배포 환경에서 filesystem이 ephemeral이면 cache가 재시작 때 사라질 수 있습니다.
Phase 4에서 배포 플랫폼에 맞춰 persistent disk 사용 여부를 확정해야 합니다.

## 환경변수 요약

| 변수 | 기본값 | 설명 |
|---|---|---|
| `APP_ENV` | `local` | 실행 환경 |
| `APP_DEBUG` | `true` | debug 설정 |
| `CORS_ORIGINS` | localhost frontend 목록 | 허용할 frontend origin |
| `KIPRIS_API_KEY` | 없음 | KIPRIS Plus API key |
| `KIPRIS_BASE_URL` | `http://plus.kipris.or.kr` | KIPRIS base URL |
| `KIPRIS_OPENAPI_KEY_PARAM` | `accessKey` | 자유검색/청구항 key parameter |
| `KIPRIS_DETAIL_KEY_PARAM` | `ServiceKey` | 서지 상세 key parameter |
| `KIPRIS_SEARCH_PATH` | KIPRIS 자유검색 path | 검색 endpoint |
| `KIPRIS_DETAIL_PATH` | KIPRIS 서지 상세 path | 상세 endpoint |
| `KIPRIS_CLAIM_PATH` | KIPRIS 청구항 path | 청구항 endpoint |
| `LLM_PROVIDER` | `gemini` | `gemini`, `openai`, `mock`. 단, `APP_ENV=production` 또는 `prod`에서는 `mock` 금지 |
| `GEMINI_API_KEY` | 없음 | Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` | Gemini model |
| `OPENAI_API_KEY` | 없음 | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `CACHE_DB_PATH` | `./data/cache.sqlite` | SQLite cache 경로 |
| `CACHE_TTL_SEARCH` | `86400` | 검색 cache TTL |
| `CACHE_TTL_DETAIL` | `604800` | 상세 cache TTL |
| `CACHE_TTL_SUMMARY` | `2592000` | 요약 cache TTL |

## 로컬 수동 테스트 순서

개발자가 배포 전에 직접 서버를 호출해볼 때는 다음 순서를 권장합니다.

```bash
venv/bin/python -m pytest
uvicorn app.main:app --reload --port 8000
```

다른 터미널에서:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/ready
curl -s http://127.0.0.1:8000/openapi.json
```

검색:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"전기차 충전소 빈자리를 예측해서 운전자에게 추천하는 서비스","page":1,"page_size":10}'
```

상세:

```bash
curl -s http://127.0.0.1:8000/api/v1/patents/10-2023-0147601
```

유사특허:

```bash
curl -s 'http://127.0.0.1:8000/api/v1/patents/10-2023-0147601/similar?limit=5'
```

요약:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/patents/10-2023-0147601/summary \
  -H "Content-Type: application/json" \
  -d '{"user_query":"전기차 배터리 열관리 기능"}'
```

## 프론트엔드 연동 시 권장 처리

프론트엔드에서는 다음 원칙을 권장합니다.

- API base URL은 환경변수로 관리합니다.
- KIPRIS/Gemini/OpenAI key는 frontend에 두지 않습니다.
- `code` 기준으로 에러를 분기합니다.
- `details.source`가 `kipris`이면 외부 특허 API 문제로 안내합니다.
- `details.source`가 `llm`이면 AI 요약/키워드 생성 문제로 안내합니다.
- `is_cached=true`인 요약도 정상 응답으로 취급합니다.
- `disclaimer`는 요약 화면에 그대로 노출하는 것을 권장합니다.

간단한 에러 처리 예시:

```ts
type ApiError = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const payload = await response.json();

  if (!response.ok) {
    const error = payload as ApiError;
    throw new Error(`${error.code}: ${error.message}`);
  }

  return payload as T;
}
```

## 관련 문서

| 문서 | 설명 |
|---|---|
| `README.md` | 설치, 실행, 주요 명령 |
| `docs/backend_test_plan.md` | 테스트 그룹과 품질 게이트 |
| `docs/backend_evaluation_report.md` | 검색 품질 benchmark |
| `docs/kipris_api_research.md` | KIPRIS API 응답 구조 조사 |
| `docs/frontend_backend_integration_guide.md` | 배포 백엔드 기준 frontend 연동 가이드 |
| `docs/frontend_ai_integration.md` | AI 개발 도구용 frontend 연동 스펙 |
| `docs/frontend_mock_api_guide.md` | 초기 local mock API 참고 문서 |
