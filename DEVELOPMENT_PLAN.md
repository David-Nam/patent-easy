# PatentEasy 백엔드 개발 계획서

> **프로젝트**: 생성형 AI의 이해와 활용 (GITA404-1) 7팀 — AI 기반 특허 검색 서비스
> **담당**: 백엔드 / AI (남준우)
> **문서 버전**: v1.31
> **최종 수정일**: 2026-05-14
> **개발 기간**: 2026-05-01 ~ 2026-06-09 (Phase 2~4)

---

## 📌 이 문서의 사용법 (Claude Code 포함)

이 문서는 **백엔드 개발의 단일 진실 원천(Single Source of Truth)** 입니다.
- 새로운 작업을 시작할 때마다 이 문서를 먼저 읽고 컨텍스트를 파악하세요.
- 의사결정이 바뀌면 반드시 이 문서를 업데이트하세요. (코드보다 문서가 먼저)
- "Phase X 작업 N번"과 같이 명시적으로 작업 단위를 참조하세요.
- Codex는 작업을 단계별로 실행하고, 각 단계가 끝날 때마다 구현 요약과 검증 방법을 보고한 뒤 검증을 진행하세요.

**현재 진행 상태**: Phase 2-A 작업 1~5 및 Phase 2-B 작업 6~11 완료, 작업 12 pending. Phase 3 작업 13~16 완료. Phase 4 작업 17~18 완료. 작업 19 smoke test 검증 중 발견된 Query Builder Gemini 요청 오류 수정 완료, Render 재배포 대기.

---

## 0. Codex 작업 운영 규칙

이 프로젝트에서 Codex는 다음 절차를 기본 작업 방식으로 따른다.

1. `DEVELOPMENT_PLAN.md`의 작업 번호 단위로 한 단계씩만 진행한다.
2. 각 단계 구현이 끝나면 즉시 다음 내용을 보고한다.
   - 무엇을 개발했는지
   - 어떤 파일을 변경했는지
   - 어떤 명령과 기준으로 검증할지
3. 사용자가 검증 진행을 컨펌하면 해당 단계의 검증을 실행한다.
4. 검증 성공/실패와 관계없이 결과를 보고하고, 다음 단계 진행 또는 추가 검증 여부를 사용자에게 확인받는다.
5. 사용자가 컨펌하기 전에는 다음 작업 번호로 넘어가지 않는다.
6. 기능 구현 작업은 해당 기능의 단위 테스트 또는 fixture 테스트를 함께 작성한다.
7. Phase 3는 테스트를 처음 작성하는 단계가 아니라, Phase 2에서 작성한 테스트를
   통합하고 배포 전 품질 게이트를 완성하는 단계다.

---

## 1. 프로젝트 컨텍스트

### 1.1 한 줄 요약

특허 비전문가(스타트업 창업자, 사업개발 담당자, 기획자)가 자연어로 아이디어를 입력하면, AI가 관련 한국 특허를 검색하고 청구항을 비즈니스 언어로 요약해주는 서비스.

### 1.2 핵심 사용자 시나리오

```
사용자 입력:
"배달 앱에서 사용자가 음식 사진을 찍으면 칼로리를 자동으로 계산해 주고,
 건강 상태에 맞는 식단을 추천해 주는 기능을 만들려고 하는데 비슷한 특허가 있을까?"

기대 결과:
1. AI가 핵심 개념(음식 이미지 인식, 칼로리 자동 계산, 맞춤형 식단 추천)을 추출
2. 동의어·유사어로 확장하여 KIPRIS에서 관련 특허 검색
3. 검색 결과를 사용자 의도 기준으로 재정렬
4. 상위 특허들의 청구항을 비즈니스 언어로 요약
```

### 1.3 풀고자 하는 문제 (중간보고서 2-1)

1. **검색 결과 과다 및 관련도 부재**: KIPRIS는 출원일순 나열, 사용자가 직접 필터링해야 함
2. **전문 용어의 장벽**: 청구항이 법률 언어로 작성되어 비즈니스 관점 해석에 시간 소요
3. **검색어 설정의 어려움**: IPC 분류 코드, 출원인명, 특허 전문 용어를 알아야 정확한 검색 가능

### 1.4 핵심 기술 가설

> **"자연어 → 좋은 검색 쿼리 변환"** 이 이 프로젝트의 핵심 기술 과제다.

기존 RAG 시나리오와 다른 점:
- 벡터DB를 새로 만들 필요 없음 (KIPRIS가 이미 검색 API 제공)
- 한국 특허 전체 임베딩은 비현실적 (수백만 건)
- 진짜 어려운 건 **개념 추출 + 동의어 확장 + 결과 재정렬** (프롬프트 엔지니어링 문제)

→ **결론: 전형적 RAG가 아닌 "LLM-augmented Search" 구조로 설계**

### 1.5 학술적 근거 (중간보고서 참고 논문)

| 논문 | 적용 부분 |
|---|---|
| Ding et al. (2025) | LLM + 검색 결합 파이프라인 구조 |
| Wang et al. (2024) EvoPat | 청구항 요약 시 Chain-of-Thought 프롬프트 |
| Jiang et al. (2024) Survey | 비전문가 자연어 인터페이스의 미탐구성 입증 |
| Thakur et al. (2021) BEIR | BM25 + Dense Retrieval Hybrid 근거 (선택적 적용) |
| Sun et al. (2023) | LLM 기반 Reranking 근거 |

---

### 1.6 개발 범위

이 문서는 **백엔드 API 서버 개발, 검증, 배포**까지만 다룬다.

**포함 범위**:
- FastAPI 백엔드 서버 구현
- KIPRIS Plus API, LLM provider, cache, error handling 구현
- API 계약 문서화와 Swagger/OpenAPI 제공
- 로컬/실제 API/배포 환경 검증
- 서버 배포와 배포 후 smoke test

**제외 범위**:
- 프론트엔드 화면 구현
- 프론트엔드 상태 관리, UI 컴포넌트, 라우팅
- 프론트엔드에서 백엔드 API를 연결하며 발견되는 디버깅 작업

프론트엔드 연동 중 발견된 백엔드 버그는 백엔드 유지보수 이슈로 처리하되,
프론트엔드 연동 자체를 백엔드 개발 계획의 Phase로 두지는 않는다.

---

## 2. 시스템 아키텍처

### 2.1 전체 흐름

```
┌─────────────┐     ┌────────────────────────────────────────┐     ┌──────────────┐
│  프론트엔드  │ ──▶ │              백엔드 (FastAPI)            │ ──▶ │  외부 서비스   │
│  (Next.js)  │     │                                          │     │              │
└─────────────┘     │  ┌────────────────────────────────┐    │     │  KIPRIS Plus  │
                    │  │  쿼리 빌더 (Query Builder)        │    │ ──▶ │  Open API     │
                    │  │  - 자연어 → 키워드 추출            │    │     └──────────────┘
                    │  │  - 동의어 확장                    │    │     ┌──────────────┐
                    │  │  - IPC 코드 추정                  │    │     │  LLM Provider │
                    │  └──────────────┬─────────────────┘    │ ──▶ │ Gemini/OpenAI  │
                    │                 ▼                       │     └──────────────┘
                    │  ┌────────────────────────────────┐    │
                    │  │  검색 클라이언트 (Search Client)  │    │
                    │  │  - KIPRIS API 호출               │    │
                    │  │  - 캐싱 레이어 (SQLite)           │    │
                    │  └──────────────┬─────────────────┘    │
                    │                 ▼                       │
                    │  ┌────────────────────────────────┐    │
                    │  │  결과 처리기 (Result Processor)   │    │
                    │  │  - LLM 기반 재정렬                │    │
                    │  │  - 청구항 요약 생성                │    │
                    │  │  - 비즈니스 활용 포인트 생성        │    │
                    │  └────────────────────────────────┘    │
                    └────────────────────────────────────────┘
```

### 2.2 주요 모듈 책임

| 모듈 | 책임 | 핵심 의존성 |
|---|---|---|
| **Query Builder** | 자연어 → 검색 쿼리 변환 | LLM Provider (Gemini 기본, OpenAI 전환 가능) |
| **Search Client** | KIPRIS API 호출 + 캐싱 | httpx, SQLite |
| **Result Processor** | 재정렬, 요약 생성 | LLM Provider (Gemini 기본, OpenAI 전환 가능) |
| **API Layer** | HTTP 엔드포인트, 검증, 에러 처리 | FastAPI, Pydantic |
| **Cache Layer** | 호출 결과 캐싱 | SQLite |

### 2.3 폴더 구조 (제안)

```
patent-easy-backend/
├── README.md
├── DEVELOPMENT_PLAN.md          # ← 이 문서
├── pyproject.toml (또는 requirements.txt)
├── .env.example                 # 환경변수 템플릿
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 앱 진입점
│   ├── config.py                # 환경변수 로드
│   ├── schemas/                 # Pydantic 모델 (API 명세의 코드 버전)
│   │   ├── __init__.py
│   │   ├── search.py
│   │   ├── patent.py
│   │   └── summary.py
│   ├── routers/                 # API 엔드포인트
│   │   ├── __init__.py
│   │   ├── search.py            # POST /api/v1/search
│   │   ├── patents.py           # GET /api/v1/patents/{id}
│   │   └── summary.py           # POST /api/v1/patents/{id}/summary
│   ├── services/                # 비즈니스 로직 (모듈 책임)
│   │   ├── __init__.py
│   │   ├── query_builder.py     # 자연어 → 키워드/IPC 추출
│   │   ├── kipris_client.py     # KIPRIS API 호출
│   │   ├── llm_client.py        # Gemini/OpenAI LLM provider 호출
│   │   └── cache.py             # 캐싱 레이어
│   ├── prompts/                 # LLM 프롬프트 (버전 관리)
│   │   ├── extract_keywords.txt
│   │   ├── expand_synonyms.txt
│   │   ├── rerank_results.txt
│   │   └── summarize_patent.txt
│   └── utils/
│       ├── __init__.py
│       └── logger.py
├── tests/
│   ├── __init__.py
│   ├── test_query_builder.py
│   ├── test_kipris_client.py
│   └── fixtures/
│       └── sample_kipris_response.json
├── scripts/                     # 일회성 스크립트
│   ├── manual_e2e_test.py       # 수동 E2E 검증용
│   └── benchmark.py             # 성능 평가용
└── data/                        # 가짜 데이터, 평가 셋
    ├── mock_patents.json
    └── eval_queries.json        # 평가용 쿼리 셋
```

---

## 3. 기술 스택 결정

| 영역 | 선택 | 이유 |
|---|---|---|
| **언어** | Python 3.11+ | LLM/AI 생태계 표준 |
| **웹 프레임워크** | FastAPI | 자동 문서화(`/docs`), Pydantic 통합, async 지원 |
| **HTTP 클라이언트** | httpx | async 지원, requests보다 현대적 |
| **데이터 검증** | Pydantic v2 | FastAPI와 완벽 통합 |
| **LLM API** | Gemini API 무료 tier 우선 | 초기 비용 0원으로 개발. `LLM_PROVIDER` 설정으로 OpenAI 교체 가능하게 추상화 |
| **임베딩** | (필요 시) text-embedding-3-small or bge-m3 | 재정렬에 사용. MVP에서는 보류 가능 |
| **캐싱** | SQLite | 설정 0, 학교 프로젝트 규모에 충분 |
| **벡터DB** | (필요 시) Chroma 로컬 | 단일 특허 청구항 처리 정도면 메모리로 충분 |
| **배포** | Render Free Web Service + uvicorn | 기말 프로젝트 시연용 공개 URL, env var, health check 관리가 가장 단순 |

### 3.1 언어 선택 검토

**현재 권장안: Python 유지**

이 프로젝트는 KIPRIS XML 파싱, LLM structured output, Pydantic schema 검증,
빠른 프롬프트/fixture 실험이 핵심이다. 이미 FastAPI, Pydantic, httpx 기반 구조와
KIPRIS fixture 검증이 완료되었으므로, MVP와 발표 배포까지는 Python 유지가 가장
현실적이다.

| 선택지 | 장점 | 단점 | 판단 |
|---|---|---|---|
| Python + FastAPI | LLM/데이터 처리 생태계, Pydantic schema, 빠른 구현 | 대규모 고성능 서버에는 Go/Java보다 운영 튜닝 필요 | **현재 유지 권장** |
| TypeScript + NestJS | 프론트엔드와 언어 통일, DTO/DI 구조 명확, 팀 협업 쉬움 | KIPRIS/LLM client와 테스트를 다시 작성해야 함 | 장기 리팩터링 후보 |
| Go | 단일 바이너리 배포, 낮은 메모리, 높은 동시성 | LLM prompt/schema 반복 개발과 XML 정규화 코드가 장황해질 수 있음 | 운영 성능이 최우선이면 후보 |
| Kotlin/Java + Spring Boot | 안정적인 엔터프라이즈 백엔드 구조 | 학교 프로젝트 MVP에는 무겁고 개발 속도 저하 | 비권장 |

**언어 변경 조건**:
- 백엔드와 프론트엔드를 TypeScript monorepo로 합쳐야 한다면 NestJS 검토
- KIPRIS 호출량이 커지고 동시성이 병목이 되면 Go 재작성 검토
- 현재 일정 안에서는 Python을 유지하고, API 계약과 테스트를 먼저 완성한다.

### 3.2 환경변수 (.env)

```bash
# LLM
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash-lite
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# KIPRIS
KIPRIS_API_KEY=...
KIPRIS_BASE_URL=http://plus.kipris.or.kr
KIPRIS_OPENAPI_KEY_PARAM=accessKey
KIPRIS_DETAIL_KEY_PARAM=ServiceKey
KIPRIS_SEARCH_PATH=/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo
KIPRIS_DETAIL_PATH=/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch
KIPRIS_CLAIM_PATH=/openapi/rest/patUtiModInfoSearchSevice/patentClaimInfo

# 캐시
CACHE_DB_PATH=./data/cache.sqlite
CACHE_TTL_SEARCH=86400        # 24시간
CACHE_TTL_DETAIL=604800       # 7일
CACHE_TTL_SUMMARY=2592000     # 30일

# 비용 한도
LLM_MONTHLY_BUDGET_USD=50
```

---

## 4. API 명세 (v0.1 — 회의에서 v1.0 확정 예정)

### 4.1 엔드포인트 한눈에 보기

| Method | Path | 용도 | 응답 속도 | LLM 호출 |
|---|---|---|---|---|
| `POST` | `/api/v1/search` | 자연어 검색 → 특허 리스트 | 5~10초 | 1회 (키워드 추출) |
| `GET` | `/api/v1/patents/{id}` | 특허 상세 조회 | 1~2초 | 0회 |
| `POST` | `/api/v1/patents/{id}/summary` | AI 요약 생성 | 3~5초 | 1~2회 |
| `POST` | `/api/v1/patents/{id}/chat` | 특허 Q&A 챗봇 (회의 후 결정) | 3~5초 | 1회 |
| `GET` | `/api/v1/patents/{id}/similar` | 유사 특허 (회의 후 결정) | 1~2초 | 0회 |
| `GET` | `/api/v1/patents/{id}/family` | 패밀리·인용 (KIPRIS 지원 시) | 1~2초 | 0회 |

### 4.2 핵심 엔드포인트 상세

#### `POST /api/v1/search`

**요청**
```json
{
  "query": "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능",
  "filters": {
    "applicant": null,
    "ipc_codes": null,
    "year_from": null,
    "year_to": null
  },
  "page": 1,
  "page_size": 10
}
```

**응답 (200 OK)**
```json
{
  "query": "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능",
  "extracted": {
    "keywords": ["음식 이미지 인식", "칼로리 자동 계산", "맞춤형 식단 추천"],
    "ipc_codes": ["G06N", "A23L", "G06V"],
    "expanded_terms": {
      "음식 이미지 인식": ["식품 영상 인식", "음식 사진 식별"],
      "칼로리 자동 계산": ["열량 산출", "영양소 분석"]
    }
  },
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_count": 20,
    "total_pages": 2
  },
  "results": [
    {
      "patent_id": "10-2023-0098765",
      "title": "사용자 식습관 기반 음식 추천 시스템",
      "applicant": "삼성전자",
      "application_date": "2023-08-15",
      "ipc_codes": ["G06N 3/08", "A23L 33/00"],
      "relevance_score": 92,
      "tags": ["추천시스템", "딥러닝", "식품", "개인화"],
      "abstract_preview": "사용자의 과거 식습관 데이터를 분석해...",
      "kipris_url": "https://www.kipris.or.kr/..."
    }
  ]
}
```

#### `GET /api/v1/patents/{patent_id}`

**응답** — 특허 메타데이터 + 청구항 전문. LLM 호출 없음. (자세한 스키마는 §6 Pydantic 모델 참고)

#### `POST /api/v1/patents/{patent_id}/summary`

**요청**
```json
{ "user_query": "배달앱에서 음식 사진..." }   // 선택. 있으면 사용자 관점 요약
```

**응답**
```json
{
  "patent_id": "10-2023-0098765",
  "core_summary": "이 기술은 사용자의 과거 식습관 데이터를 분석해...",
  "business_application": "푸드테크, 헬스케어 앱, 배달 플랫폼에서...",
  "key_tags": ["추천시스템", "딥러닝", "식품", "개인화"],
  "generated_at": "2026-04-30T10:30:00Z",
  "is_cached": false,
  "disclaimer": "이 요약은 참고용입니다. 정확한 권리범위 판단은 변리사 자문을 받으세요."
}
```

### 4.3 공통 에러 포맷

```json
{
  "error": {
    "code": "KIPRIS_RATE_LIMIT",
    "message": "일일 검색 한도를 초과했습니다.",
    "retry_after": 86400
  }
}
```

| HTTP | code | 의미 |
|---|---|---|
| 400 | `INVALID_QUERY` / `INVALID_REQUEST` | 입력 오류 |
| 404 | `PATENT_NOT_FOUND` | 존재하지 않는 ID |
| 429 | `KIPRIS_RATE_LIMIT` / `RATE_LIMIT` | 호출 한도 초과 |
| 502 | `KIPRIS_UPSTREAM_ERROR` | KIPRIS API 오류 |
| 503 | `LLM_UNAVAILABLE` | LLM API 오류 |

---

## 5. 핵심 의사결정 (회의에서 확정 필요)

| # | 안건 | 초안 | 결정 |
|---|---|---|---|
| 1 | 요약 생성 시점 | 카드 클릭 시 지연 로딩 | ⏳ |
| 2 | 유사도 점수 표시 | 0~100 정수 표시 | ⏳ |
| 3 | 챗봇 MVP 범위 | 단일 특허 컨텍스트 Q&A 포함 | ⏳ |
| 4 | 북마크 저장 | 클라이언트 localStorage | ⏳ |
| 5 | 패밀리·인용 특허 | KIPRIS 지원 시 포함 | ⏳ |
| 6 | 페이지당 건수 | 10건 | ⏳ |
| 7 | 에러 UI 처리 | 토스트 + 인라인 메시지 | ⏳ |
| 8 | 로딩 상태 표시 | 스켈레톤 UI | ⏳ |

> **회의 후 이 표를 업데이트할 것.** 결정이 코드에 반영되기 전 단계.

---

## 6. 단계별 작업 (Phase 2 ~ Phase 4)

### Phase 2-A: 검증 + Mock 서버 (5/1 ~ 5/7)

> **목표**: 핵심 가설 검증 + 백엔드 API 계약과 서버 골격 확정

#### 작업 1. 환경 셋업

**완료 조건**:
- Python 3.11+ 가상환경 생성
- `requirements.txt` 작성 (`fastapi`, `uvicorn`, `httpx`, `pydantic`, `python-dotenv`, `openai`)
- `.env.example` 작성, `.gitignore`에 `.env`, `venv/`, `__pycache__/`, `*.sqlite` 추가
- 폴더 구조 생성 (§2.3 참고)
- GitHub 레포 초기화, 첫 커밋

#### 작업 2. KIPRIS Plus API 검증 ⭐

**완료 조건**:
- KIPRIS Plus 회원가입 및 API 키 발급
- 사용자가 `.env`에 `KIPRIS_API_KEY` 입력
- `python scripts/verify_kipris_api.py` 실행
- 다음 API 응답을 직접 호출해 확인하고 `tests/fixtures/`에 저장:
  - 자유검색 (`freeSearchInfo` 우선, 필요 시 `getAdvancedSearch`)
  - 특허 상세 (`getBibliographyDetailInfoSearch`)
  - 청구항 (`patentClaimInfo`)
- raw 응답은 XML/JSON 원본 그대로 `tests/fixtures/kipris_raw/`에 저장
- 정규화 fixture는 JSON으로 `tests/fixtures/kipris_normalized/`에 저장
- 응답 필드에서 다음 값의 존재 여부 문서화:
  - 출원번호, 출원일, 공개일, 등록일, 법적상태
  - 발명의 명칭, 출원인, 발명자
  - 청구항 전문, 초록
  - IPC 코드
- 호출 한도가 어떻게 카운트되는지 확인 (계정 페이지/공식 안내 기준으로 재확인)

**산출물**: `docs/kipris_api_research.md` — 사용 가능한 엔드포인트, 응답 구조, 한계점 정리

#### 작업 3. LLM 키워드 추출 프롬프트 설계 ⭐

**완료 조건**:
- 실제 LLM API 키 발급 전에는 `app/services/mock_llm_client.py`의 deterministic mock 사용
- Gemini API 무료 tier를 우선 검증하고, OpenAI는 동일 스키마로 교체 가능하게 유지
- 다음 입력에 대해 일관된 출력을 내는 프롬프트 작성 (`app/prompts/extract_keywords.txt`):
  ```
  입력: "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능"
  출력 (JSON):
  {
    "keywords": ["음식 이미지 인식", "칼로리 자동 계산", "맞춤형 식단 추천"],
    "ipc_codes": ["G06N", "A23L", "G06V"],
    "expanded_terms": { ... }
  }
  ```
- 5~10개 다양한 입력에 대해 손으로 검증
- Chain-of-Thought 적용 (참고 논문 2 근거)
- 출력 포맷이 항상 valid JSON이 되도록 보장 (response_format 활용)

**산출물**:
- `app/prompts/extract_keywords.txt`
- `scripts/manual_e2e_test.py` — 프롬프트 결과를 KIPRIS에 넣어 실제로 좋은 특허가 나오는지 검증

#### 작업 4. Mock 서버 v1 (단순 버전)

**완료 조건**:
- `app/main.py` 한 파일에 검색/상세/요약 3개 엔드포인트 구현
- 응답은 하드코딩된 가짜 데이터
- CORS 설정 (프론트 도메인 허용)
- `uvicorn app.main:app --reload --port 8000` 으로 실행
- `http://localhost:8000/docs` 에서 Swagger UI 동작 확인
- API 호출 방법을 README와 docs에 문서화

**참고 코드**: 이전 대화에서 만든 `mock-api/v1-simple/main.py`

#### 작업 5. Mock 서버 v2 (구조화)

**완료 조건**:
- `app/schemas/` 에 Pydantic 모델 분리
- `app/routers/` 에 엔드포인트 분리
- `data/mock_patents.json` 로 가짜 데이터 분리
- 회의에서 결정된 추가 엔드포인트 포함 (챗봇/유사/패밀리 중 살아남은 것)
- README에 실행 방법, 엔드포인트 목록, 호출 예시 작성

**중요**: v2는 v1을 대체하는 게 아니라 **점진적으로 진짜 로직으로 교체될 골격**임. 가짜 응답을 반환하는 함수가 나중에 진짜 KIPRIS/LLM 호출로 바뀌는 구조.

---

### Phase 2-B: 진짜 로직 구현 (5/8 ~ 5/20)

> **목표**: Mock 응답을 진짜 KIPRIS + LLM 호출로 점진적 교체
> **테스트 원칙**: 각 작업은 구현 코드와 해당 기능의 단위/fixture 테스트를 함께 완료한다.

#### 작업 6. KIPRIS Client 구현

**상태**: 완료 (2026-05-08)

**완료 조건**:
- `app/services/kipris_client.py` 작성
- async httpx 사용
- 다음 메서드 구현:
  - `search_patents(keywords: list[str], filters: SearchFilters) -> list[PatentListItem]`
  - `get_patent_detail(patent_id: str) -> PatentDetail`
  - (회의 결과에 따라) `get_family(patent_id: str)`
- 에러 처리: 네트워크 오류, 응답 파싱 실패, rate limit
- 단위 테스트 (`tests/test_kipris_client.py`)

**검증 결과**:
- fixture 기반 단위 테스트: `tests/test_kipris_client.py` 5개 통과
- 전체 테스트: 11개 통과
- 실제 KIPRIS 최소 호출 성공:
  - 자유검색 1건 조회
  - 검색 결과 첫 특허의 서지상세 및 청구항 조회
- 로컬 `.env`의 서지상세 경로는 `/kipo-api/kipi/...`와 `ServiceKey`를 사용해야 함

#### 작업 7. Cache Layer 구현

**상태**: 완료 (2026-05-08)

**완료 조건**:
- `app/services/cache.py` 작성
- SQLite 기반 KV 스토어
- TTL 지원 (search: 24h, detail: 7d, summary: 30d)
- 캐시 키 정규화 (소문자, 공백 정리, 동의어 매핑)
- sync/async decorator helper 제공
- KIPRIS Client 검색/상세 호출에 cache 부착
- 캐시 히트율 로깅
- 단위 테스트 (`tests/test_cache.py`)
- KIPRIS cache hit 테스트 (`tests/test_kipris_client.py`)

**검증 결과**:
- cache 단위 테스트: `tests/test_cache.py` 4개 통과
- KIPRIS client 테스트: `tests/test_kipris_client.py` 7개 통과
- 전체 테스트: 17개 통과

```python
# 사용 예시
@cached(ttl=86400, key_prefix="search")
async def search_patents(keywords: list[str], ...) -> list[PatentListItem]:
    ...
```

#### 작업 8. Query Builder 구현

**상태**: 완료 (2026-05-08)

**완료 조건**:
- `app/services/query_builder.py` 작성
- 작업 3에서 만든 프롬프트를 Gemini API로 우선 호출
- `LLM_PROVIDER=gemini|openai|mock` 설정으로 provider 선택 가능
- OpenAI adapter는 같은 입출력 스키마(`ExtractedQuery`)를 유지
- 출력 검증 (JSON 파싱 실패 시 재시도, 최대 2회)
- 단위 테스트 (예시 5개)

**구현 내용**:
- mock provider는 deterministic `mock_llm_client` 사용
- Gemini provider는 REST `generateContent`와 structured output schema 사용
- OpenAI provider는 chat completions JSON mode 사용
- provider 응답은 `ExtractedQuery`로 파싱하고 키워드/IPC/확장어 구조 검증
- JSON 파싱 또는 schema 검증 실패 시 최대 2회 재시도
- 단위 테스트 (`tests/test_query_builder.py`)

**검증 결과**:
- Query Builder 단위 테스트: `tests/test_query_builder.py` 8개 통과
- 전체 테스트: 25개 통과

#### 작업 9. 검색 엔드포인트 진짜 구현

**상태**: 완료 (2026-05-12)

**완료 조건**:
- `POST /api/v1/search` 가 실제로 작동:
  ```
  자연어 → Query Builder → KIPRIS Client → 응답 조립
  ```
- 응답 시간 목표: 캐시 히트 1초, 미스 5~10초
- E2E 테스트 5개 시나리오 통과

**구현 내용**:
- `/api/v1/search` 라우터를 mock service 직접 호출에서 `SearchService` 의존성 주입 구조로 변경
- `SearchService`에서 Query Builder 결과를 KIPRIS Client 검색 요청으로 연결
- KIPRIS 검색에 `page` 기반 `docsStart` 계산과 `TotalSearchCount` 파싱 추가
- 검색 라우터에서 provider/config/upstream 오류를 HTTP 503/502로 변환
- key 없이 실행 가능한 service/API/KIPRIS fixture 테스트 추가

**검증 결과**:
- 검색 service 단위 테스트: `tests/test_search_service.py` 1개 통과
- 검색 API 오류 매핑 테스트: `tests/test_search_api.py` 2개 통과
- KIPRIS client pagination/total count fixture 테스트: `tests/test_kipris_client.py` 8개 통과
- 실제 KIPRIS API 검색 엔드포인트 live 테스트: `RUN_LIVE_KIPRIS=1 pytest tests/test_search_live.py -m live_kipris -s` 1개 통과
- 전체 테스트: 29개 통과, live 테스트 1개 기본 skip

**live 검증 정책**:
- 개발 단계에서는 KIPRIS 무료 호출 한도 내에서 실제 KIPRIS API 검증을 적극 사용
- 기본 `pytest`는 외부 API를 호출하지 않음
- 실제 KIPRIS 호출 검증은 `RUN_LIVE_KIPRIS=1`과 `-m live_kipris`를 명시해 실행

#### 작업 10. LLM Client 구현 (Gemini 기본·OpenAI 전환)

**상태**: 완료 (2026-05-12)

**완료 조건**:
- `app/services/llm_client.py` 작성
- Gemini adapter를 기본 구현으로 작성
- OpenAI adapter를 같은 인터페이스로 추가 또는 교체 가능하게 설계
- 메서드:
  - `summarize_patent(patent: PatentDetail, user_query: str | None) -> SummaryResponse`
  - `rerank_results(query: str, results: list[PatentListItem]) -> list[PatentListItem]`
- 비용 추적 (토큰 수 로깅)
- 환각 방지: 청구항 원문을 컨텍스트에 명시적으로 포함

**구현 내용**:
- `app/services/llm_client.py` 작성
- `LLM_PROVIDER=gemini|openai|mock` 기반 provider 선택
- Gemini adapter는 REST `generateContent`와 `responseJsonSchema` structured output 사용
- OpenAI adapter는 chat completions JSON mode 사용
- 요약 프롬프트와 재정렬 프롬프트 분리:
  - `app/prompts/summarize_patent.txt`
  - `app/prompts/rerank_results.txt`
- provider 응답 JSON 파싱 실패 또는 schema 검증 실패 시 최대 2회 재시도
- Gemini/OpenAI token usage를 `last_token_usage`와 logger로 기록
- 요약 프롬프트에 청구항 원문을 명시적으로 포함하여 환각을 줄이는 구조 적용

**검증 결과**:
- LLM Client 단위 테스트: `tests/test_llm_client.py` 7개 통과
- 실제 Gemini API live 테스트: `RUN_LIVE_LLM=1 pytest tests/test_llm_client_live.py -m live_llm -s` 1개 통과
- 전체 테스트: 36개 통과, live 테스트 2개 기본 skip

**live 검증 정책**:
- 기본 `pytest`는 외부 LLM API를 호출하지 않음
- 실제 Gemini 호출 검증은 `RUN_LIVE_LLM=1`과 `-m live_llm`를 명시해 실행

#### 작업 11. 요약 엔드포인트 진짜 구현

**상태**: 완료 (2026-05-12)

**완료 조건**:
- `POST /api/v1/patents/{id}/summary` 가 실제 LLM 호출
- 결과는 캐시에 저장 (30일 TTL)
- "비즈니스 활용" 섹션도 함께 생성

**구현 내용**:
- `/api/v1/patents/{id}/summary` 라우터를 mock 직접 호출에서 `SummaryService` 의존성 주입 구조로 변경
- `SummaryService`에서 summary cache hit 시 KIPRIS/LLM 호출 없이 cached 응답 반환
- cache miss 시 KIPRIS 상세/청구항 조회 후 LLM Client로 Gemini/OpenAI/mock 요약 생성
- 요약 결과를 `CACHE_TTL_SUMMARY` 기준으로 SQLite cache에 저장
- summary 라우터에서 not found/config/upstream 오류를 HTTP 404/503/502로 변환
- key 없이 실행 가능한 service/API 테스트와 실제 KIPRIS+Gemini live 테스트 추가

**검증 결과**:
- summary service cache 테스트: `tests/test_summary_service.py` 1개 통과
- summary API 오류 매핑 테스트: `tests/test_summary_api.py` 4개 통과
- 기본 전체 테스트: 41개 통과, live 테스트 3개 기본 skip
- 실제 KIPRIS+Gemini 요약 live 테스트: `RUN_LIVE_KIPRIS=1 RUN_LIVE_LLM=1 pytest tests/test_summary_live.py -m "live_kipris and live_llm" -s` 1개 통과

#### 작업 12. (회의에서 살아남으면) 챗봇 엔드포인트 구현

**상태**: pending (2026-05-12)

**완료 조건**:
- `POST /api/v1/patents/{id}/chat` 구현
- 청구항 + 초록을 컨텍스트로 LLM에 전달
- 대화 히스토리는 stateless (클라이언트가 매번 보냄)

---

### Phase 3: 백엔드 검증·안정화 (5/21 ~ 6/01)

> **목표**: 실제 API 서버로 배포하기 전에 백엔드 기능, API 계약, 장애 처리를 통합 검증한다.
> Phase 3는 테스트를 몰아서 처음 작성하는 단계가 아니라, Phase 2의 기능별 테스트를
> 하나의 release candidate 검증 체계로 묶고 운영 안정성을 보강하는 단계다.

#### 작업 13. Backend Test Suite Consolidation

**상태**: 완료 (2026-05-12)

**완료 조건**:
- Phase 2 각 작업에서 작성한 단위/fixture 테스트를 정리
- key 없이 실행 가능한 테스트와 key 필요한 테스트를 분리
- `pytest` 기본 실행은 외부 API를 호출하지 않음
- KIPRIS live test는 명시적으로만 실행
- Gemini/OpenAI live test는 명시적으로만 실행
- `tests/test_kipris_client.py`, `tests/test_mock_api.py` 외 통합 테스트 추가
- API response schema가 OpenAPI 문서와 맞는지 검증
- CI 또는 배포 전 수동 검증에서 사용할 품질 게이트 명령 확정

**검증 명령**:
```bash
pytest
pytest -m live_kipris
pytest -m live_llm
```

**구현 내용**:
- OpenAPI 계약 테스트 추가: `tests/test_openapi_contract.py`
- `/search`, `/patents/{id}/summary`의 OpenAPI error response status 문서화
- backend 품질 게이트 문서 추가: `docs/backend_test_plan.md`
- 품질 게이트 실행 스크립트 추가: `scripts/run_quality_gate.py`
- README의 테스트 섹션에서 backend test plan으로 연결

**검증 결과**:
- OpenAPI 계약 테스트: `tests/test_openapi_contract.py` 3개 통과
- 기본 offline quality gate: `venv/bin/python -m pytest` 44개 통과, live 테스트 3개 기본 skip
- 실제 KIPRIS live gate: `venv/bin/python scripts/run_quality_gate.py --live-kipris` 통과
- 실제 Gemini live gate: `venv/bin/python scripts/run_quality_gate.py --live-llm` 통과
- 실제 KIPRIS+Gemini summary live gate: `venv/bin/python scripts/run_quality_gate.py --live-summary` 통과

#### 작업 14. Backend Error Handling Hardening

**상태**: 완료 (2026-05-13)

**완료 조건**:
- KIPRIS 장애 시 표준 에러 응답 반환
- KIPRIS timeout, 4xx, 5xx, XML parse 실패 구분
- LLM 장애 시 표준 에러 응답 또는 graceful fallback 반환
- cache hit 가능 시 upstream 장애에도 캐시 결과 반환
- 모든 에러 응답은 `{code, message, details?}` 구조 유지
- Swagger `/docs`에서 에러 모델 확인 가능

**구현 내용**:
- 표준 에러 스키마 `ErrorResponse` 추가
- FastAPI/Starlette HTTP 예외와 요청 검증 예외를 `{code, message, details?}` 응답으로 변환
- 예상하지 못한 500 오류도 `INTERNAL_SERVER_ERROR` 표준 응답으로 변환
- KIPRIS timeout, 네트워크 오류, HTTP 4xx/5xx, KIPRIS 서비스 오류를 구분해 `details`에 기록
- 검색/요약/특허 상세 라우터의 에러 응답을 `ErrorResponse` 기반으로 문서화
- LLM provider/parse/configuration 장애를 표준 에러 응답으로 변환
- cache hit 시 upstream을 재호출하지 않는 기존 동작을 에러 처리 테스트 범위에 포함

**검증 예정 명령**:
```bash
pytest tests/test_error_response.py tests/test_search_api.py tests/test_summary_api.py tests/test_kipris_client.py tests/test_openapi_contract.py
pytest
```

**검증 결과**:
- 표적 에러 처리 테스트: `venv/bin/python -m pytest tests/test_error_response.py tests/test_search_api.py tests/test_summary_api.py tests/test_kipris_client.py tests/test_openapi_contract.py` 28개 통과
- 전체 offline 테스트: `venv/bin/python -m pytest` 55개 통과, live 테스트 3개 skip

#### 작업 15. Observability & Runtime Guardrails

**상태**: 완료 (2026-05-13)

**완료 조건**:
- 요청별 처리 시간 로깅
- KIPRIS endpoint별 호출 횟수 로깅
- LLM provider/model/token 사용량 로깅
- cache hit/miss 로깅
- `/health`는 앱 상태, `/ready`는 외부 의존성/캐시 준비 상태 확인
- 민감 정보(API key, 원문 전체 청구항)는 로그에 남기지 않음

**구현 내용**:
- FastAPI request middleware로 method/path/status/duration/request_id 로깅 추가
- `/health`에 version/environment 앱 상태 정보 추가
- `/ready`에서 cache 연결, KIPRIS 설정, LLM provider/model 설정 상태 확인
- KIPRIS 실제 upstream 호출 시 endpoint별 call count 로깅
- LLM Client와 Query Builder에서 provider/model/token usage 로깅
- SQLite cache `ping()`과 hit/miss/set 로그 검증 추가
- 로그에는 query string, API key, cache payload, 청구항 원문을 남기지 않는 방향으로 제한
- backend test plan의 Phase 3 보강 항목 상태 업데이트

**검증 예정 명령**:
```bash
pytest tests/test_observability.py tests/test_cache.py tests/test_kipris_client.py tests/test_llm_client.py tests/test_query_builder.py tests/test_openapi_contract.py
pytest
```

**검증 결과**:
- 표적 관측성 테스트: `venv/bin/python -m pytest tests/test_observability.py tests/test_cache.py tests/test_kipris_client.py tests/test_llm_client.py tests/test_query_builder.py tests/test_openapi_contract.py` 41개 통과
- 전체 offline 테스트: `venv/bin/python -m pytest` 64개 통과, live 테스트 3개 skip

#### 작업 16. Backend Evaluation Script

**상태**: 완료 (2026-05-13)

**완료 조건**:
- `data/eval_queries.json`에 10~20개 자연어 쿼리 작성
- 각 쿼리의 기대 키워드, IPC 후보, 관련 특허 후보를 수동 라벨링
- `scripts/benchmark.py` 작성
- cache on/off, mock/real LLM provider별 결과 비교
- Precision@10, 응답 시간, KIPRIS 호출 수, LLM 호출 수 산출

**산출물**:
- `scripts/benchmark.py`
- `docs/backend_evaluation_report.md`

**구현 내용**:
- `data/eval_queries.json`을 10개 평가 케이스로 확장
- 평가 케이스별 기대 키워드, IPC 후보, 관련 특허 후보 수동 라벨링
- mock/local corpus 평가를 위해 `data/mock_patents.json`에 도메인별 mock 특허 보강
- `scripts/benchmark.py`에서 mock/real mode, cache on/off, mock/Gemini/OpenAI provider 옵션 지원
- Precision@10, Recall@10, keyword recall, IPC recall, latency, KIPRIS/LLM call count 산출
- real KIPRIS 또는 real LLM 호출은 `--allow-live` 없이는 실행되지 않도록 보호
- `docs/backend_evaluation_report.md`에 평가 데이터셋, 실행 방법, 지표 해석 기준 문서화
- README와 backend test plan에서 benchmark 실행 가이드 연결

**검증 예정 명령**:
```bash
venv/bin/python -m pytest tests/test_benchmark.py tests/test_query_builder.py tests/test_mock_api.py
venv/bin/python scripts/benchmark.py --mode mock --cache off
venv/bin/python -m pytest
```

**검증 결과**:
- 표적 benchmark 테스트: `venv/bin/python -m pytest tests/test_benchmark.py tests/test_query_builder.py tests/test_mock_api.py` 18개 통과
- mock benchmark CLI: `venv/bin/python scripts/benchmark.py --mode mock --cache off` 실행 성공
  - `query_count=10`
  - `mean_recall_at_10=1.0`
  - `mean_keyword_recall=1.0`
  - `mean_ipc_recall=1.0`
  - `kipris_call_count=0`
  - `llm_call_count=10`
- 전체 offline 테스트: `venv/bin/python -m pytest` 67개 통과, live 테스트 3개 skip

---

### Phase 4: Render 시연용 서버 배포 (6/01 ~ 6/09)

> **목표**: 기말 프로젝트 발표/시연을 위해 Render Free Web Service에 백엔드
> 서버를 배포하고, 공개 URL에서 핵심 API가 동작하는지 검증한다.

**배포 범위 결정**:
- 제품 운영 배포가 아니라 기말 프로젝트 시연용 배포로 한정한다.
- 배포 target은 Render Free Web Service로 고정한다.
- Docker는 기본 범위에서 제외하고, Render의 Python runtime과 `requirements.txt`
  기반 배포를 우선 사용한다.
- Render 무료 Web Service는 15분 idle 후 sleep될 수 있으므로 발표 전 서버를
  미리 깨워 둔다.
- Render 무료 Web Service의 filesystem은 ephemeral이므로 SQLite cache는
  영구 저장소가 아니라 재시작 시 사라져도 되는 임시 cache로 취급한다.
- 장기 운영, persistent disk, Redis/Postgres cache, multi-instance scaling은
  이번 Phase 4 범위에서 제외한다.

#### 작업 17. Render Demo Runtime Configuration

**완료 조건**:
- Render용 start command 확정:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
- Render용 build command 확정:
  ```bash
  pip install -r requirements.txt
  ```
- `requirements.txt`에 배포 실행에 필요한 패키지가 모두 포함되어 있는지 확인
- `.env.example`과 README에 Render Environment Variables 설정 방법 반영
- Render 환경변수 기준값 정리:
  - `APP_ENV=production`
  - `APP_DEBUG=false`
  - `KIPRIS_API_KEY`
  - `LLM_PROVIDER=gemini`
  - `GEMINI_API_KEY`
  - `CACHE_DB_PATH=/tmp/patent-easy-cache.sqlite`
  - `CACHE_TTL_SEARCH`, `CACHE_TTL_DETAIL`, `CACHE_TTL_SUMMARY`
  - `CORS_ORIGINS`
- 추가로 보관 중인 KIPRIS 보조 key는 사용하지 않고, 단일 공식 key만 실제 호출에 사용
- `/ready`에서 Render 환경변수 누락 여부를 확인할 수 있도록 사용 절차 문서화

**구현 내용**:
- README에 Render 시연용 배포 설정, build/start command, 환경변수 표 추가
- `.env.example`에 Render production 값 예시와 `/tmp` cache 경로 안내 추가
- 보관용 KIPRIS 보조 key는 현재 백엔드가 자동 사용하지 않는다고 명시
- `docs/deployment_guide.md`에 Render 설정 절차, 무료 플랜 제약, `/ready` 확인 방법,
  발표 전 체크리스트 문서화

**검증 예정 명령**:
```bash
rg -n "Render 시연용|Build Command|Start Command|CACHE_DB_PATH=/tmp|KIPRIS_API_SUB" README.md .env.example docs/deployment_guide.md DEVELOPMENT_PLAN.md
git diff --check -- README.md .env.example docs/deployment_guide.md DEVELOPMENT_PLAN.md
venv/bin/python -m pytest tests/test_observability.py tests/test_openapi_contract.py
```

**검증 결과**:
- Render 설정 문구 검색 성공
- `git diff --check -- README.md .env.example docs/deployment_guide.md DEVELOPMENT_PLAN.md` 통과
- 표적 테스트 `venv/bin/python -m pytest tests/test_observability.py tests/test_openapi_contract.py` 7개 통과

#### 작업 18. Render Web Service Deploy

**완료 조건**:
- Render 계정 생성 또는 로그인
- GitHub repository를 Render Web Service에 연결
- Runtime은 Python, instance type은 Free로 설정
- build command와 start command 입력
- Render dashboard에 환경변수 등록
- public backend URL 확보
- 최초 배포 로그에서 dependency install과 Uvicorn start 성공 확인
- `/health`, `/ready`, `/docs`, `/openapi.json` 접근 확인

**수동 설정 체크리스트**:
- Render Dashboard → New → Web Service
- GitHub repository 선택
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment Variables에 `.env` 값을 직접 입력하되, `.env` 파일은 업로드하지 않음
- 발표 전 5분 이내에 `/health`, `/ready`, `/docs`를 열어 cold start를 미리 해소

**배포 결과**:
- Public Backend URL: `https://patent-easy-api.onrender.com`
- Render build 성공
- Uvicorn startup 성공
- `/health` 200 확인
- `/ready` `status=ready` 확인
  - cache: `/tmp/patent-easy-cache.sqlite`
  - KIPRIS: configured
  - LLM: `gemini`, `gemini-2.5-flash-lite`
- `/docs` Swagger UI 확인
- `/openapi.json` 정상 응답 확인

#### 작업 19. Render Smoke Test & Demo Release Notes

**완료 조건**:
- Render 배포 URL 대상으로 smoke test script 실행
- `/health` 200 확인
- `/ready` 200 또는 누락 설정이 명확히 드러나는 503 확인 후 수정
- `/docs`, `/openapi.json` 접근 확인
- `/api/v1/search` 최소 1회 성공 확인
- `/api/v1/patents/{id}` mock 상세 조회 최소 1회 성공 확인
- `/api/v1/patents/{id}/summary` 실제 KIPRIS/Gemini 호출 최소 1회 성공 확인
- 실패 시 Render dashboard에서 env var 수정 또는 이전 deploy rollback 절차 문서화
- 발표용 known limitations 정리:
  - 무료 인스턴스 cold start 가능
  - SQLite cache는 재시작 후 사라질 수 있음
  - KIPRIS/Gemini 호출 한도 때문에 발표 시 live 호출은 최소화

**산출물**:
- `scripts/smoke_test_deployed_api.py`
- `docs/deployment_guide.md`
- `docs/release_notes.md`

**구현 내용**:
- `scripts/smoke_test_deployed_api.py` 추가
  - 배포 URL 기준 `/health`, `/ready`, `/openapi.json`, mock 상세, 검색, 요약 호출
  - 기본 URL은 `https://patent-easy-api.onrender.com`
  - `DEPLOYED_API_BASE_URL`, `--base-url`, `--skip-summary`, `--output` 지원
- `tests/test_deployment_smoke.py` 추가
  - smoke script의 URL 정규화, readiness/OpenAPI 응답 검증, 결과 요약 로직 테스트
- `docs/deployment_guide.md`에 smoke test 실행 방법과 결과 저장 방법 추가
- `docs/backend_test_plan.md`에 Render 배포 smoke test 그룹 추가
- README에 Render smoke test 실행 명령과 release notes 링크 추가
- `docs/release_notes.md`에 v0.1.0 Render Demo 릴리스 노트, 포함 기능, known limitations 작성

**검증 예정 명령**:
```bash
venv/bin/python -m pytest tests/test_deployment_smoke.py
git diff --check -- scripts/smoke_test_deployed_api.py tests/test_deployment_smoke.py docs/deployment_guide.md docs/backend_test_plan.md docs/release_notes.md README.md DEVELOPMENT_PLAN.md
DEPLOYED_API_BASE_URL=https://patent-easy-api.onrender.com venv/bin/python scripts/smoke_test_deployed_api.py --skip-summary
DEPLOYED_API_BASE_URL=https://patent-easy-api.onrender.com venv/bin/python scripts/smoke_test_deployed_api.py
```

**검증 중 발견된 이슈와 수정**:
- 배포 URL smoke test에서 `POST /api/v1/search`가 `502 SEARCH_UPSTREAM_ERROR`로 실패
- 원인: `QueryBuilder`의 Gemini structured output 요청이 `responseSchema` 형식과
  query parameter key를 사용해 Gemini가 `HTTP 400`을 반환
- 수정:
  - `app/services/query_builder.py`에서 Gemini 요청을 `responseJsonSchema`와
    `x-goog-api-key` header 방식으로 변경
  - schema type을 JSON Schema 방식의 lowercase 값으로 변경
  - `tests/test_query_builder.py`에 Gemini payload 회귀 검증 보강
  - `tests/test_query_builder_live.py` 추가
  - `docs/backend_test_plan.md`에 Query Builder live 검증 그룹 추가

**현재 검증 결과**:
- `venv/bin/python -m pytest tests/test_deployment_smoke.py` 4개 통과
- `git diff --check -- ...` 통과
- `DEPLOYED_API_BASE_URL=https://patent-easy-api.onrender.com venv/bin/python scripts/smoke_test_deployed_api.py --skip-summary`
  - `/health`, `/ready`, `/openapi.json`, mock 상세 통과
  - `/api/v1/search`는 배포 서버의 이전 코드에서 `LLM provider returned HTTP 400`으로 실패
- 수정 후 로컬 표적 테스트:
  - `venv/bin/python -m pytest tests/test_query_builder.py tests/test_query_builder_live.py tests/test_search_api.py tests/test_deployment_smoke.py`
  - 18개 통과, live marker 1개 skip
- 수정 후 Gemini live Query Builder 테스트:
  - `RUN_LIVE_LLM=1 venv/bin/python -m pytest tests/test_query_builder_live.py -m live_llm -s`
  - 1개 통과

**다음 검증 필요**:
- 수정사항 commit/push 후 Render 자동 재배포
- 재배포 완료 후 `scripts/smoke_test_deployed_api.py --skip-summary` 재실행
- 통과하면 `scripts/smoke_test_deployed_api.py` 전체 실행

---

## 6.1 테스트 및 검증 전략

테스트는 Phase 3에서 한 번에 작성하지 않는다. 각 기능 작업의 완료 조건에는 해당
기능의 테스트 작성이 포함된다. Phase 3는 이미 작성된 테스트를 통합하고, live test,
에러 처리, 관측성, 배포 전 smoke test를 묶어 서버 릴리스 기준을 만드는 단계다.

| 검증 단계 | 외부 key 필요 | 목적 | 실행 시점 |
|---|---:|---|---|
| Unit tests | 없음 | schema, parser, service 단위 검증 | 각 기능 작업 안에서 작성 |
| Fixture integration tests | 없음 | KIPRIS raw fixture 기반 파싱 검증 | KIPRIS 관련 작업 안에서 작성 |
| Local API smoke tests | 없음/선택 | `/health`, `/docs`, mock endpoint 확인 | endpoint 변경 후 |
| Live KIPRIS tests | KIPRIS key | 실제 검색/상세/청구항 최소 호출 확인 | KIPRIS client 변경 후 |
| Live LLM tests | Gemini/OpenAI key | structured output, 요약, 재정렬 확인 | LLM client 변경 후 |
| Deployment smoke tests | 배포 env vars | 공개 서버 URL 정상 동작 확인 | 배포 후 |
| Benchmark | KIPRIS/LLM key 선택 | 품질·응답 시간·비용 비교 | 발표/릴리스 전 |

**검증 원칙**:
- 기능 작업은 테스트 없이 완료 처리하지 않는다.
- Phase 3는 테스트 작성 지연을 흡수하는 단계가 아니라 배포 전 통합 검증 단계다.
- 기본 `pytest`는 외부 API를 호출하지 않는다.
- 실제 KIPRIS/LLM 호출 테스트는 marker 또는 별도 script로 명시 실행한다.
- live test는 호출 횟수를 최소화하고 cache를 우선 사용한다.
- 배포 smoke test는 공개 URL 기준으로 실행한다.
- 실패한 검증은 원인, 재현 명령, 수정 방향을 문서에 남긴다.

---

## 7. 위험 요소 및 대응 (중간보고서 4-3 확장)

| 위험 | 영향도 | 대응 |
|---|---|---|
| **KIPRIS API 일 1,000건 한도 초과** | 매우 높음 | 캐싱 적극 활용, 정규화된 캐시 키 사용 |
| **LLM 환각 (요약 부정확)** | 높음 | 청구항 원문 병기, 참고용 면책 문구, 유사도 점수 명시 |
| **자연어 → 키워드 변환 품질 저하** | 높음 | 입력 가이드 예시 제공, 변환 결과 사용자에게 노출 |
| **Gemini 무료 tier 한도/정책 제약** | 중간 | 캐싱, 호출량 제한, 민감 입력은 paid tier 또는 OpenAI 전환 검토 |
| **LLM API 비용 초과** | 중간 | Gemini 무료 tier 우선, 캐싱, 월 $50 한도 알림, OpenAI는 필요 시만 전환 |
| **KIPRIS API 응답 구조가 가정과 다름** | 높음 | Phase 2-A 작업 2에서 일찍 검증 |
| **프롬프트 품질이 발표 시연에 부적합** | 중간 | 작업 3에서 5~10개 시나리오 검증, A/B 테스트 |

---

## 8. 진행 추적

> **이 섹션을 작업하면서 계속 업데이트할 것.**

### 8.1 작업 체크리스트

- [x] **Phase 2-A**
  - [x] 작업 1. 환경 셋업
  - [x] 작업 2. KIPRIS Plus API 검증
  - [x] 작업 3. LLM 키워드 추출 프롬프트 설계
  - [x] 작업 4. Mock 서버 v1
  - [x] 작업 5. Mock 서버 v2
- [ ] **Phase 2-B**
  - [x] 작업 6. KIPRIS Client
  - [x] 작업 7. Cache Layer
  - [x] 작업 8. Query Builder
  - [x] 작업 9. 검색 엔드포인트 진짜 구현
  - [x] 작업 10. LLM Client
  - [x] 작업 11. 요약 엔드포인트 진짜 구현
  - [ ] 작업 12. (조건부) 챗봇 엔드포인트 pending
- [ ] **Phase 3**
  - [x] 작업 13. Backend Test Suite Consolidation
  - [x] 작업 14. Backend Error Handling Hardening
  - [x] 작업 15. Observability & Runtime Guardrails
  - [x] 작업 16. Backend Evaluation Script
- [ ] **Phase 4**
  - [x] 작업 17. Render Demo Runtime Configuration
  - [x] 작업 18. Render Web Service Deploy
  - [ ] 작업 19. Render Smoke Test & Demo Release Notes

### 8.2 의사결정 로그

| 날짜 | 결정 | 사유 |
|---|---|---|
| 2026-05-04 | RAG 대신 LLM-augmented Search 채택 | KIPRIS가 검색 API 제공, 한국 특허 전체 임베딩 비현실적 |
| 2026-05-04 | FastAPI 채택 | Pydantic 통합, 자동 문서화 |
| 2026-05-04 | 요약은 별도 엔드포인트로 분리 (초안) | 검색 시 일괄 생성 시 응답 30초+, 비용 폭증 |
| 2026-05-06 | KIPRIS는 실제 API 키 검증을 게이트로 설정 | 실제 응답 구조 확인 전 `KIPRISClient` 구현 금지 |
| 2026-05-06 | LLM 의존 기능은 Mock 우선 구현 | 키 발급 전에도 프론트 연동과 API 스키마 확정 가능 |
| 2026-05-07 | KIPRIS 검색·서지상세·청구항 API 검증 완료 | 검색/청구항은 `/openapi/rest`+`accessKey`, 서지상세는 `/kipo-api/kipi`+`ServiceKey` 사용 |
| 2026-05-07 | Mock API 프론트엔드 공유 문서 분리 | 사람용 가이드와 AI 도구용 통합 스펙을 각각 제공 |
| 2026-05-07 | LLM 키워드 추출 프롬프트는 JSON-only 계약으로 설계 | 실제 LLM 키 없이 Mock-first 검증을 완료하고 provider 검증은 Query Builder 단계에서 수행 |
| 2026-05-07 | LLM provider는 Gemini 무료 tier를 기본값으로 채택 | 초기 비용을 줄이고, `LLM_PROVIDER` 추상화로 OpenAI 전환 가능성을 유지 |
| 2026-05-08 | KIPRIS Client는 fixture 검증과 실제 최소 호출을 모두 통과 | 검색/상세/청구항 파싱을 실제 응답 구조 기준으로 구현 |
| 2026-05-08 | 개발 계획 범위를 백엔드 서버 배포까지로 재정의 | 프론트엔드 연동 디버깅은 백엔드 개발 Phase에서 제외 |
| 2026-05-08 | MVP 언어는 Python 유지 | 현재 FastAPI/Pydantic/KIPRIS fixture 기반 구현을 유지하는 편이 일정상 가장 현실적 |
| 2026-05-08 | 기능별 테스트는 각 작업 안에서 작성 | Phase 3는 테스트를 처음 만드는 단계가 아니라 배포 전 통합 검증 단계 |
| 2026-05-08 | Cache Layer 구현 및 KIPRIS Client 연결 완료 | KIPRIS 호출 절약을 위해 검색/상세 결과를 SQLite TTL cache에 저장 |
| 2026-05-08 | Query Builder provider abstraction 구현 완료 | Gemini 기본, OpenAI 전환, Mock fallback을 동일 `ExtractedQuery` 스키마로 유지 |
| 2026-05-12 | 검색 엔드포인트 실제 검색 파이프라인 구현 | `/search`를 Query Builder와 KIPRIS Client 조합으로 전환하고 mock 의존성은 테스트 override로 격리 |
| 2026-05-12 | 검색 엔드포인트 검증 완료 | SearchService/API/KIPRIS fixture 테스트와 전체 테스트 29개 통과 |
| 2026-05-12 | 작업 9 검증에 실제 KIPRIS 호출 추가 | `RUN_LIVE_KIPRIS=1`로 실제 KIPRIS Plus API 검색 endpoint 검증을 통과 |
| 2026-05-12 | LLM Client Gemini live 검증 완료 | 새 Gemini API key로 summary structured output 호출을 성공하고 token usage를 기록 |
| 2026-05-12 | 요약 엔드포인트 실제 파이프라인 구현 | KIPRIS 상세/청구항 조회, LLM 요약, SQLite summary cache를 `SummaryService`로 연결 |
| 2026-05-12 | 요약 엔드포인트 live 검증 완료 | 실제 KIPRIS 상세/청구항 조회와 Gemini 요약 호출을 하나의 API 흐름으로 검증 |
| 2026-05-12 | 작업 12 챗봇 엔드포인트 pending | 발표/회의에서 필요성이 확정될 때까지 Phase 3 검증·안정화를 우선 진행 |
| 2026-05-12 | Phase 3는 작업 13 테스트 통합부터 진행 | 배포 전 품질 게이트와 live/offline 테스트 분리를 먼저 고정 |
| 2026-05-12 | Backend Test Suite Consolidation 완료 | OpenAPI 계약 테스트와 offline/KIPRIS/Gemini/summary live 품질 게이트 통과 |
| 2026-05-13 | Backend Error Handling Hardening 구현 | 에러 응답을 `{code, message, details?}`로 표준화하고 KIPRIS/LLM 장애 분류를 명시 |
| 2026-05-13 | Backend Error Handling Hardening 검증 완료 | 표적 에러 처리 테스트 28개와 전체 offline 테스트 55개 통과 |
| 2026-05-13 | Observability & Runtime Guardrails 구현 | request latency, readiness, cache/KIPRIS/LLM 로그를 추가하고 민감 정보 로그 노출을 제한 |
| 2026-05-13 | Observability & Runtime Guardrails 검증 완료 | 표적 관측성 테스트 41개와 전체 offline 테스트 64개 통과 |
| 2026-05-13 | Backend Evaluation Script 구현 | 평가 쿼리, benchmark script, 검색 품질 평가 문서를 추가 |
| 2026-05-13 | Backend Evaluation Script 검증 완료 | 표적 benchmark 테스트 18개, mock benchmark CLI, 전체 offline 테스트 67개 통과 |
| 2026-05-14 | Phase 4 배포 target을 Render Free Web Service로 고정 | 기말 프로젝트 시연용 배포이므로 제품 운영보다 단순성, 무료 사용, 발표 전 검증을 우선 |
| 2026-05-14 | Render Demo Runtime Configuration 완료 | README, `.env.example`, 배포 가이드에 Render 설정값과 무료 플랜 제약을 반영하고 표적 검증 통과 |
| 2026-05-14 | Render Web Service 배포 완료 | `https://patent-easy-api.onrender.com`에서 `/health`, `/ready`, `/docs`, `/openapi.json` 확인 |

### 8.3 변경 이력

| 버전 | 날짜 | 변경 내용 |
|---|---|---|
| v1.31 | 2026-05-14 | 작업 19 smoke test 중 발견된 Query Builder Gemini 요청 오류 수정 및 로컬/live 검증 결과 반영 |
| v1.30 | 2026-05-14 | 작업 19 smoke test script와 demo release notes 구현 상태 및 검증 예정 항목 반영 |
| v1.29 | 2026-05-14 | 작업 18 Render Web Service 배포 결과와 완료 상태 반영 |
| v1.28 | 2026-05-14 | 작업 17 검증 결과와 완료 상태 반영 |
| v1.27 | 2026-05-14 | 작업 17 Render Demo Runtime Configuration 구현 상태와 검증 예정 항목 반영 |
| v1.26 | 2026-05-14 | Phase 4를 Render Free Web Service 기반 기말 프로젝트 시연용 배포 계획으로 재정의 |
| v1.25 | 2026-05-13 | 작업 16 검증 결과와 완료 상태 반영 |
| v1.24 | 2026-05-13 | 작업 16 benchmark 구현 상태와 검증 예정 항목 반영 |
| v1.23 | 2026-05-13 | 작업 15 검증 결과와 완료 상태 반영 |
| v1.22 | 2026-05-13 | 작업 15 관측성·runtime guardrail 구현 상태와 검증 예정 항목 반영 |
| v1.21 | 2026-05-13 | 작업 14 검증 결과와 완료 상태 반영 |
| v1.20 | 2026-05-13 | 작업 14 에러 처리 강화 구현 상태와 검증 예정 항목 반영 |
| v1.19 | 2026-05-12 | 작업 13 검증 결과와 완료 상태 반영 |
| v1.18 | 2026-05-12 | 작업 12 pending 처리와 작업 13 테스트 통합 구현 상태 반영 |
| v1.17 | 2026-05-12 | 요약 엔드포인트 검증 결과와 작업 11 완료 상태 반영 |
| v1.16 | 2026-05-12 | 요약 엔드포인트 실제 구현 상태와 검증 예정 항목 반영 |
| v1.15 | 2026-05-12 | LLM Client 구현 및 실제 Gemini live 검증 결과 반영 |
| v1.14 | 2026-05-12 | 작업 9 실제 KIPRIS live 검증 결과와 실행 정책 반영 |
| v1.13 | 2026-05-12 | 검색 엔드포인트 검증 결과와 작업 9 완료 상태 반영 |
| v1.12 | 2026-05-12 | 검색 엔드포인트 실제 구현 상태와 검증 예정 항목 반영 |
| v1.11 | 2026-05-08 | Query Builder 완료 상태와 검증 결과 반영 |
| v1.10 | 2026-05-08 | Cache Layer 완료 상태와 검증 결과 반영 |
| v1.9 | 2026-05-08 | 기능별 테스트 작성 시점과 Phase 3 통합 검증 역할 명확화 |
| v1.8 | 2026-05-08 | Phase 3~4를 백엔드 검증·배포 계획으로 재구성하고 언어 선택 검토 추가 |
| v1.7 | 2026-05-08 | KIPRIS Client 구현 완료 상태와 실제 KIPRIS 최소 호출 검증 결과 반영 |
| v1.6 | 2026-05-07 | Gemini 무료 tier 우선 전략과 OpenAI 전환 가능한 LLM provider 계획 반영 |
| v1.5 | 2026-05-07 | Phase 2-A 완료 상태와 LLM 키워드 추출 프롬프트 검증 결과 반영 |
| v1.4 | 2026-05-07 | Mock 서버 v2 완료 상태와 프론트엔드 공유 문서 산출물 반영 |
| v1.3 | 2026-05-07 | KIPRIS Plus API 검증 완료 상태와 endpoint/key parameter 차이 반영 |
| v1.2 | 2026-05-06 | Codex 단계별 실행·검증·컨펌 운영 규칙 추가 |
| v1.1 | 2026-05-06 | KIPRIS 검증 게이트, LLM Mock 우선 개발 방침 반영 |
| v1.0 | 2026-05-04 | 초기 작성 |

---

## 9. 참고 자료

### 9.1 외부 문서
- [KIPRIS Plus Open API](https://plus.kipris.or.kr/portal/main.do)
- [Gemini API Docs](https://ai.google.dev/gemini-api/docs)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini Structured Output](https://ai.google.dev/gemini-api/docs/structured-output)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Render FastAPI 배포 문서](https://render.com/docs/deploy-fastapi)
- [Render Free Web Service 제한](https://render.com/docs/free)
- [NestJS 공식 문서](https://docs.nestjs.com/introduction)
- [Go net/http 공식 문서](https://pkg.go.dev/net/http)

### 9.2 팀 내부 문서
- 중간보고서: `docs/중간보고서.pdf`
- API Reference: `docs/api_reference.md`
- 와이어프레임: https://patent-wise-finder.lovable.app/

### 9.3 팀 구성
| 역할 | 담당자 | 학번 |
|---|---|---|
| 기획·디자인 | 민지선 | A72048 |
| 백엔드·AI | 남준우 | A72046 |
| 프론트엔드 | 김소연 | A72028 |

---

## 10. 다음 작업 (Claude Code 진입 시 여기서 시작)

**현재 상태**: Phase 2-A 작업 1~5 완료, Phase 2-B 작업 6~11 완료, 작업 12 pending, Phase 3 작업 13~16 완료, Phase 4 작업 17~18 완료, 작업 19 smoke test script 구현 및 Query Builder Gemini 오류 수정 완료, Render 재배포 대기

**즉시 할 일**:
1. 수정사항 commit/push 후 Render 재배포 진행
2. 재배포 완료 후 작업 19 smoke test 재검증
3. 검증 성공 시 작업 19 완료 상태 반영 후 commit-message 스킬 사용

**Claude Code에게 작업 요청 시 예시**:
> "DEVELOPMENT_PLAN.md를 읽고 Phase 2-A 작업 1을 진행해줘. 환경 셋업과 폴더 구조 생성부터 시작."
> "작업 4 Mock 서버 v1을 만들어줘. 이전 대화에서 논의한 단순 버전 main.py 구조 따라서."
> "작업 8 Query Builder를 구현해줘. 프롬프트는 app/prompts/extract_keywords.txt에 있는 걸 사용."
> "작업 18 Render Web Service Deploy를 진행해줘. Render 설정값과 smoke test 계획부터 보고해줘."

---

_이 문서는 살아있는 문서입니다. 의사결정이 바뀌거나 새로운 정보가 생기면 즉시 업데이트하세요._
