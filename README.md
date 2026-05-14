# PatentEasy 백엔드

PatentEasy는 비전문가가 자연어로 제품 아이디어를 입력하면 관련 한국 특허를 검색하고, 청구항을 비즈니스 관점으로 요약해주는 FastAPI 백엔드입니다.

현재 백엔드는 KIPRIS Plus API와 Gemini API를 실제 키로 검증한 상태입니다. LLM provider는 Gemini를 기본값으로 사용하며, `LLM_PROVIDER` 설정을 통해 OpenAI 또는 mock provider로 전환할 수 있도록 구성했습니다.

## 기술 스택

| 영역 | 사용 기술 |
|---|---|
| 언어 | Python 3.11+ |
| 웹 프레임워크 | FastAPI |
| 데이터 검증 | Pydantic v2 |
| HTTP client | httpx |
| 특허 API | KIPRIS Plus API |
| LLM provider | Gemini 기본, OpenAI 전환 가능 |
| cache | SQLite |
| 테스트 | pytest |

## 설치

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 실제 API 키를 입력합니다.

```env
KIPRIS_API_KEY=...
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
```

실제 키 없이도 기본 테스트는 실행할 수 있습니다. 다만 실제 `/api/v1/search`, `/api/v1/patents/{id}/summary` 흐름을 로컬에서 직접 호출하려면 KIPRIS와 Gemini 키가 필요합니다.

## 실행

```bash
uvicorn app.main:app --reload --port 8000
```

- Health check: `http://localhost:8000/health`
- Readiness check: `http://localhost:8000/ready`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Render 시연용 배포 설정

기말 프로젝트 시연용 배포 target은 Render Free Web Service입니다. Render에서는
`.env` 파일을 업로드하지 않고, Dashboard의 Environment Variables에 값을 직접
입력합니다.

| 항목 | 값 |
|---|---|
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |

Render에 등록할 주요 환경변수는 다음과 같습니다.

| 변수 | Render 값 |
|---|---|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `KIPRIS_API_KEY` | 실제 KIPRIS Plus API 키 |
| `LLM_PROVIDER` | `gemini` |
| `GEMINI_API_KEY` | 실제 Gemini API 키 |
| `CACHE_DB_PATH` | `/tmp/patent-easy-cache.sqlite` |
| `CACHE_TTL_SEARCH` | `86400` |
| `CACHE_TTL_DETAIL` | `604800` |
| `CACHE_TTL_SUMMARY` | `2592000` |
| `CORS_ORIGINS` | 배포된 프론트엔드 origin, 없으면 로컬 개발 origin |

Render 무료 Web Service는 15분 동안 요청이 없으면 sleep될 수 있고, 재시작이나
sleep 이후 local SQLite cache 파일이 사라질 수 있습니다. 이 프로젝트에서는 제품
운영이 아니라 발표 시연용 배포이므로 SQLite cache를 임시 cache로 취급합니다.

배포 후에는 `/health`, `/ready`, `/docs`, `/openapi.json` 순서로 확인합니다.
자세한 절차는 `docs/deployment_guide.md`를 참고합니다.

배포 URL 기준 smoke test는 다음 명령으로 실행합니다. 이 명령은 KIPRIS/Gemini를
실제로 호출하므로 발표 리허설 또는 배포 확인 시점에만 실행합니다.

```bash
DEPLOYED_API_BASE_URL=https://patent-easy-api.onrender.com \
  venv/bin/python scripts/smoke_test_deployed_api.py
```

## 주요 API

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/health` | 서버 상태 확인 |
| `GET` | `/ready` | cache, KIPRIS, LLM 설정 준비 상태 확인 |
| `POST` | `/api/v1/search` | 자연어 아이디어를 키워드로 변환한 뒤 KIPRIS 검색 |
| `GET` | `/api/v1/patents/{patent_id}` | 특허 상세 정보 조회 |
| `POST` | `/api/v1/patents/{patent_id}/summary` | KIPRIS 상세/청구항 기반 LLM 요약 생성 |

상세한 요청/응답 예시와 에러 코드는 `docs/api_reference.md`를 기준으로 확인합니다.

### 검색 예시

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능","page":1,"page_size":10}'
```

### 상세 조회 예시

```bash
curl http://localhost:8000/api/v1/patents/10-2023-0098765
```

### 요약 예시

```bash
curl -X POST http://localhost:8000/api/v1/patents/10-2023-0147601/summary \
  -H "Content-Type: application/json" \
  -d '{"user_query":"전기차 배터리 열관리 기능"}'
```

## 환경변수

주요 환경변수는 `.env.example`을 기준으로 관리합니다.

| 변수 | 설명 |
|---|---|
| `KIPRIS_API_KEY` | KIPRIS Plus API 키 |
| `LLM_PROVIDER` | `gemini`, `openai`, `mock` 중 하나 |
| `GEMINI_API_KEY` | Gemini API 키 |
| `OPENAI_API_KEY` | OpenAI API 키, provider 전환 시 사용 |
| `CACHE_DB_PATH` | SQLite cache 파일 경로 |
| `CACHE_TTL_SEARCH` | 검색 cache TTL, 초 단위 |
| `CACHE_TTL_DETAIL` | 상세 cache TTL, 초 단위 |
| `CACHE_TTL_SUMMARY` | 요약 cache TTL, 초 단위 |
| `RUN_LIVE_KIPRIS` | 실제 KIPRIS live 테스트 실행 플래그 |
| `RUN_LIVE_LLM` | 실제 LLM live 테스트 실행 플래그 |

실제 API 키가 들어 있는 `.env`는 커밋하지 않습니다.

## KIPRIS API 검증

KIPRIS Plus API 응답 구조는 실제 키로 검증한 fixture를 기준으로 구현했습니다.

```bash
python scripts/verify_kipris_api.py
```

실행 결과는 다음 위치에 저장됩니다.

- Raw XML/JSON: `tests/fixtures/kipris_raw/`
- Normalized JSON: `tests/fixtures/kipris_normalized/`
- 조사 문서: `docs/kipris_api_research.md`

## 테스트

기본 테스트는 외부 API를 호출하지 않습니다.

```bash
venv/bin/python -m pytest
```

실제 API까지 포함한 품질 게이트는 다음 문서에 정리되어 있습니다.

- `docs/backend_test_plan.md`

반복 실행용 스크립트도 제공합니다.

```bash
venv/bin/python scripts/run_quality_gate.py
venv/bin/python scripts/run_quality_gate.py --live-kipris
venv/bin/python scripts/run_quality_gate.py --live-llm
venv/bin/python scripts/run_quality_gate.py --live-kipris --live-llm --live-summary
```

## 검색 품질 평가

기본 benchmark는 외부 API를 호출하지 않고 mock/local corpus로 실행됩니다.

```bash
venv/bin/python scripts/benchmark.py --mode mock --cache off
```

실제 KIPRIS 또는 Gemini/OpenAI를 호출하는 benchmark는 `--allow-live`를 명시해야 합니다.
평가 데이터와 지표 해석은 `docs/backend_evaluation_report.md`에 정리되어 있습니다.

## 참고 문서

| 문서 | 설명 |
|---|---|
| `DEVELOPMENT_PLAN.md` | 전체 개발 계획과 작업 진행 상태 |
| `docs/api_reference.md` | API 전체 기능, 요청/응답 예시, 에러 코드 |
| `docs/backend_test_plan.md` | 백엔드 테스트 및 품질 게이트 |
| `docs/backend_evaluation_report.md` | 검색 품질 평가 방법과 benchmark 실행 가이드 |
| `docs/deployment_guide.md` | Render 시연용 배포 설정과 점검 절차 |
| `docs/release_notes.md` | Render Demo 릴리스 상태와 known limitations |
| `docs/kipris_api_research.md` | KIPRIS Plus API 검증 결과 |
| `docs/keyword_prompt_design.md` | 키워드 추출 프롬프트 설계 |
| `docs/frontend_backend_integration_guide.md` | 배포 백엔드 기준 프론트엔드 연동 가이드 |
| `docs/frontend_ai_integration.md` | AI 개발 도구용 프론트엔드 연동 스펙 |
| `docs/frontend_mock_api_guide.md` | 초기 로컬 Mock API 참고 문서 |
