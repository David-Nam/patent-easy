# PatentEasy 백엔드 개발 계획서

> **프로젝트**: 생성형 AI의 이해와 활용 (GITA404-1) 7팀 — AI 기반 특허 검색 서비스
> **담당**: 백엔드 / AI (남준우)
> **문서 버전**: v1.6
> **최종 수정일**: 2026-05-07
> **개발 기간**: 2026-05-01 ~ 2026-06-09 (Phase 2~4)

---

## 📌 이 문서의 사용법 (Claude Code 포함)

이 문서는 **백엔드 개발의 단일 진실 원천(Single Source of Truth)** 입니다.
- 새로운 작업을 시작할 때마다 이 문서를 먼저 읽고 컨텍스트를 파악하세요.
- 의사결정이 바뀌면 반드시 이 문서를 업데이트하세요. (코드보다 문서가 먼저)
- "Phase X 작업 N번"과 같이 명시적으로 작업 단위를 참조하세요.
- Codex는 작업을 단계별로 실행하고, 각 단계가 끝날 때마다 구현 요약과 검증 방법을 보고한 뒤 검증을 진행하세요.

**현재 진행 상태**: Phase 2-A 작업 1~5 완료. LLM provider는 Gemini 무료 tier 우선, OpenAI 전환 가능 구조로 진행. 다음 작업은 Phase 2-B 작업 6 KIPRIS Client 구현.

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
| **배포** | (선택) Railway / Render | Mock 서버 공유용. 미배포도 가능 |

### 3.1 환경변수 (.env)

```bash
# LLM
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash-lite
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# KIPRIS
KIPRIS_API_KEY=...
KIPRIS_BASE_URL=http://plus.kipris.or.kr/openapi/rest

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

> **목표**: 핵심 가설 검증 + 프론트엔드가 개발 시작 가능하게 만들기

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
- 김소연 님께 호출 방법 공유

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

#### 작업 6. KIPRIS Client 구현

**완료 조건**:
- `app/services/kipris_client.py` 작성
- async httpx 사용
- 다음 메서드 구현:
  - `search_patents(keywords: list[str], filters: SearchFilters) -> list[PatentListItem]`
  - `get_patent_detail(patent_id: str) -> PatentDetail`
  - (회의 결과에 따라) `get_family(patent_id: str)`
- 에러 처리: 네트워크 오류, 응답 파싱 실패, rate limit
- 단위 테스트 (`tests/test_kipris_client.py`)

#### 작업 7. Cache Layer 구현

**완료 조건**:
- `app/services/cache.py` 작성
- SQLite 기반 KV 스토어
- TTL 지원 (search: 24h, detail: 7d, summary: 30d)
- 캐시 키 정규화 (소문자, 공백 정리, 동의어 매핑)
- 데코레이터 또는 helper로 KIPRIS/LLM 클라이언트에 부착
- 캐시 히트율 로깅

```python
# 사용 예시
@cached(ttl=86400, key_prefix="search")
async def search_patents(keywords: list[str], ...) -> list[PatentListItem]:
    ...
```

#### 작업 8. Query Builder 구현

**완료 조건**:
- `app/services/query_builder.py` 작성
- 작업 3에서 만든 프롬프트를 Gemini API로 우선 호출
- `LLM_PROVIDER=gemini|openai|mock` 설정으로 provider 선택 가능
- OpenAI adapter는 같은 입출력 스키마(`ExtractedQuery`)를 유지
- 출력 검증 (JSON 파싱 실패 시 재시도, 최대 2회)
- 단위 테스트 (예시 5개)

#### 작업 9. 검색 엔드포인트 진짜 구현

**완료 조건**:
- `POST /api/v1/search` 가 실제로 작동:
  ```
  자연어 → Query Builder → KIPRIS Client → 응답 조립
  ```
- 응답 시간 목표: 캐시 히트 1초, 미스 5~10초
- E2E 테스트 5개 시나리오 통과

#### 작업 10. LLM Client 구현 (Gemini 기본·OpenAI 전환)

**완료 조건**:
- `app/services/llm_client.py` 작성
- Gemini adapter를 기본 구현으로 작성
- OpenAI adapter를 같은 인터페이스로 추가 또는 교체 가능하게 설계
- 메서드:
  - `summarize_patent(claims: list[Claim], user_query: str | None) -> SummaryResponse`
  - `rerank_results(query: str, results: list[PatentListItem]) -> list[PatentListItem]`
- 비용 추적 (토큰 수 로깅)
- 환각 방지: 청구항 원문을 컨텍스트에 명시적으로 포함

#### 작업 11. 요약 엔드포인트 진짜 구현

**완료 조건**:
- `POST /api/v1/patents/{id}/summary` 가 실제 LLM 호출
- 결과는 캐시에 저장 (30일 TTL)
- "비즈니스 활용" 섹션도 함께 생성

#### 작업 12. (회의에서 살아남으면) 챗봇 엔드포인트 구현

**완료 조건**:
- `POST /api/v1/patents/{id}/chat` 구현
- 청구항 + 초록을 컨텍스트로 LLM에 전달
- 대화 히스토리는 stateless (클라이언트가 매번 보냄)

---

### Phase 3: 프론트엔드 연동 + 안정화 (5/10 ~ 6/01)

> **백엔드 입장에서 이 시기는 "프론트가 호출하면서 발견하는 이슈를 빠르게 대응" + "성능 튜닝"**

#### 작업 13. 통합 테스트

- 김소연 님이 실제 프론트에서 호출하면서 발생하는 이슈 추적
- API 명세 변경 시 즉시 문서 업데이트

#### 작업 14. 에러 처리 강화

- KIPRIS 장애 시 graceful degradation (캐시된 결과라도 반환)
- LLM 장애 시 요약 없이 검색 결과만 반환 (선택 사항)
- 사용자 친화적 에러 메시지

#### 작업 15. 로깅·모니터링

- 요청별 처리 시간 로깅
- LLM 토큰 사용량 누적 추적
- KIPRIS 호출 카운터 (일 한도 임박 시 경고)

---

### Phase 4: 평가 + 발표 준비 (6/01 ~ 6/09)

#### 작업 16. 정량 평가 실험

**평가 셋 구축** (`data/eval_queries.json`):
- 10~20개 자연어 쿼리
- 각 쿼리에 대해 "관련 특허"를 수동으로 라벨링 (Gold standard)

**측정 지표**:
- Precision@10, Recall@10
- BM25 단독 vs LLM 키워드 추출 + KIPRIS 비교 (BEIR 논문 근거)
- LLM 재정렬 적용 전후 비교 (Sun et al. 2023 근거)

**산출물**: `scripts/benchmark.py` + 결과 표/그래프

#### 작업 17. 발표 자료에 들어갈 백엔드 섹션

- 아키텍처 다이어그램
- 핵심 의사결정 근거 (RAG vs LLM-augmented Search)
- 정량 평가 결과
- 시연 시나리오 1~2개

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
  - [ ] 작업 6. KIPRIS Client
  - [ ] 작업 7. Cache Layer
  - [ ] 작업 8. Query Builder
  - [ ] 작업 9. 검색 엔드포인트 진짜 구현
  - [ ] 작업 10. LLM Client
  - [ ] 작업 11. 요약 엔드포인트 진짜 구현
  - [ ] 작업 12. (조건부) 챗봇 엔드포인트
- [ ] **Phase 3**
  - [ ] 작업 13. 통합 테스트
  - [ ] 작업 14. 에러 처리 강화
  - [ ] 작업 15. 로깅·모니터링
- [ ] **Phase 4**
  - [ ] 작업 16. 정량 평가 실험
  - [ ] 작업 17. 발표 자료 백엔드 섹션

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

### 8.3 변경 이력

| 버전 | 날짜 | 변경 내용 |
|---|---|---|
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

### 9.2 팀 내부 문서
- 중간보고서: `docs/중간보고서.pdf`
- API 명세: `docs/api_spec_v0.1.md` (이 문서로 통합 가능)
- 와이어프레임: https://patent-wise-finder.lovable.app/

### 9.3 팀 구성
| 역할 | 담당자 | 학번 |
|---|---|---|
| 기획·디자인 | 민지선 | A72048 |
| 백엔드·AI | 남준우 | A72046 |
| 프론트엔드 | 김소연 | A72028 |

---

## 10. 다음 작업 (Claude Code 진입 시 여기서 시작)

**현재 상태**: Phase 1 완료, Phase 2-A 진입

**즉시 할 일**:
1. 폴더 구조 생성 (§2.3)
2. `requirements.txt`, `.env.example`, `.gitignore` 작성 (§작업 1)
3. KIPRIS Plus API 키 발급 후 작업 2 진행

**Claude Code에게 작업 요청 시 예시**:
> "DEVELOPMENT_PLAN.md를 읽고 Phase 2-A 작업 1을 진행해줘. 환경 셋업과 폴더 구조 생성부터 시작."
> "작업 4 Mock 서버 v1을 만들어줘. 이전 대화에서 논의한 단순 버전 main.py 구조 따라서."
> "작업 8 Query Builder를 구현해줘. 프롬프트는 app/prompts/extract_keywords.txt에 있는 걸 사용."

---

_이 문서는 살아있는 문서입니다. 의사결정이 바뀌거나 새로운 정보가 생기면 즉시 업데이트하세요._
