# PatentEasy Render 배포 가이드

이 문서는 기말 프로젝트 발표/시연을 위해 PatentEasy 백엔드를 Render Free Web
Service에 배포하는 방법을 정리합니다. 제품 운영용 배포가 아니라 시연용 공개 URL
확보와 smoke test를 목표로 합니다.

## 배포 목표

- 공개 백엔드 URL 확보
- `/health`, `/ready`, `/docs`, `/openapi.json` 접근 확인
- 검색, mock 상세, 요약 API를 발표 전에 최소 1회씩 확인
- KIPRIS/Gemini key는 Render Environment Variables에만 저장
- Render 무료 플랜 제약을 알고 발표 전에 서버를 미리 깨워 둠

## Render 무료 플랜 제약

Render Free Web Service는 발표용으로는 충분하지만 운영용으로는 제한이 있습니다.

- 15분 동안 inbound request가 없으면 service가 sleep될 수 있습니다.
- sleep 상태에서 첫 요청은 cold start 때문에 약 1분 정도 느릴 수 있습니다.
- local filesystem은 ephemeral입니다.
- SQLite cache 파일은 redeploy, restart, sleep 이후 사라질 수 있습니다.
- 발표 전에는 `/health`, `/ready`, `/docs`를 미리 열어 service를 깨워 둡니다.

이 프로젝트에서는 SQLite cache를 영구 데이터 저장소가 아니라 임시 cache로만
사용합니다.

## 사전 준비

Render 배포 전에 다음이 준비되어 있어야 합니다.

- GitHub repository에 최신 백엔드 코드가 push되어 있음
- Render 계정 생성 또는 로그인 가능
- KIPRIS Plus API key
- Gemini API key
- 프론트엔드 배포 URL 또는 로컬 개발 origin

`.env` 파일은 Render에 업로드하지 않습니다. 필요한 값만 Render Dashboard의
Environment Variables에 직접 입력합니다.

## Render Web Service 설정값

Render Dashboard에서 `New` → `Web Service`를 선택한 뒤 GitHub repository를
연결합니다.

| 항목 | 값 |
|---|---|
| Runtime | Python |
| Instance Type | Free |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

Render는 `$PORT` 값을 자동으로 제공합니다. FastAPI 앱은 반드시
`0.0.0.0` host와 `$PORT`를 사용해야 외부 요청을 받을 수 있습니다.

## Environment Variables

Render Dashboard의 Environment Variables에 다음 값을 등록합니다.

| 변수 | 값 | 설명 |
|---|---|---|
| `APP_ENV` | `production` | 배포 환경 표시 |
| `APP_DEBUG` | `false` | 배포 환경 debug off |
| `CORS_ORIGINS` | frontend origin 목록 | 쉼표로 구분 |
| `KIPRIS_API_KEY` | 실제 key | KIPRIS 검색/상세/청구항 호출 |
| `LLM_PROVIDER` | `gemini` | 기본 LLM provider |
| `GEMINI_API_KEY` | 실제 key | Gemini keyword/summary/chat 호출 |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` | Gemini model |
| `OPENAI_API_KEY` | 비워둠 | OpenAI 전환 시에만 사용 |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI 전환 시 model |
| `CACHE_DB_PATH` | `/tmp/patent-easy-cache.sqlite` | Render 시연용 임시 SQLite cache |
| `CACHE_TTL_SEARCH` | `86400` | 검색 cache TTL |
| `CACHE_TTL_DETAIL` | `604800` | 상세 cache TTL |
| `CACHE_TTL_SUMMARY` | `2592000` | 요약 cache TTL |
| `CACHE_TTL_CHAT` | `86400` | 챗봇 cache TTL |
| `LLM_MONTHLY_BUDGET_USD` | `50` | LLM 비용 guardrail 기준 |

`KIPRIS_API_SUB1_KEY`, `KIPRIS_API_SUB2_KEY`, `KIPRIS_API_SUB3_KEY`는 현재 백엔드가
자동으로 사용하지 않습니다. 보관용으로만 두고 Render 배포 환경에는 등록하지
않습니다.

## 배포 후 기본 확인

Render가 제공한 URL을 `BACKEND_URL`이라고 할 때 다음 순서로 확인합니다.

```bash
curl -s "$BACKEND_URL/health"
curl -s "$BACKEND_URL/ready"
curl -s "$BACKEND_URL/openapi.json"
```

브라우저에서는 다음 URL을 엽니다.

```text
$BACKEND_URL/docs
```

`/ready`가 `503`을 반환하면 정상적인 실패일 수 있습니다. 응답의 `checks`에서
어떤 환경변수가 빠졌는지 확인한 뒤 Render Dashboard에서 수정합니다.

## 배포 Smoke Test

배포 URL의 핵심 API를 한 번에 확인할 때는 다음 스크립트를 사용합니다.

```bash
DEPLOYED_API_BASE_URL=https://patent-easy-api.onrender.com \
  venv/bin/python scripts/smoke_test_deployed_api.py
```

이 명령은 다음 endpoint를 순서대로 호출합니다.

- `GET /health`
- `GET /ready`
- `GET /openapi.json`
- `GET /api/v1/patents/10-2023-0098765`
- `POST /api/v1/search`
- `POST /api/v1/patents/10-2023-0147601/summary`

`/api/v1/search`와 `/summary`는 배포 서버에서 KIPRIS/Gemini를 실제로 호출합니다.
요약 호출을 잠시 아끼고 싶으면 빠른 점검용으로만 `--skip-summary`를 사용합니다.
최종 발표 전 smoke test에서는 `--skip-summary` 없이 실행합니다.

챗봇까지 확인하려면 `--include-chat`을 추가합니다. 이 옵션은 KIPRIS/Gemini 호출을
1회 더 사용하므로 발표 직전 전체 점검 때만 실행하는 것을 권장합니다.

```bash
DEPLOYED_API_BASE_URL=https://patent-easy-api.onrender.com \
  venv/bin/python scripts/smoke_test_deployed_api.py --skip-summary
```

```bash
DEPLOYED_API_BASE_URL=https://patent-easy-api.onrender.com \
  venv/bin/python scripts/smoke_test_deployed_api.py --include-chat
```

결과를 파일로 남기려면 `--output`을 사용합니다.

```bash
DEPLOYED_API_BASE_URL=https://patent-easy-api.onrender.com \
  venv/bin/python scripts/smoke_test_deployed_api.py \
  --output artifacts/deployment_smoke_latest.json
```

## 현재 시연용 배포 정보

| 항목 | 값 |
|---|---|
| Public Backend URL | `https://patent-easy-api.onrender.com` |
| Runtime | Python 3 |
| Instance Type | Free |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |

확인 완료 항목:

- Render build 성공
- Uvicorn startup 성공
- `/health` 200 확인
- `/ready` `status=ready` 확인
- `/docs` Swagger UI 확인
- `/openapi.json` 정상 응답 확인

## 발표 전 체크리스트

- 발표 5분 전 `/health`, `/ready`, `/docs`를 열어 cold start를 해소
- `/ready`가 `ready`인지 확인
- KIPRIS/Gemini 호출 한도를 아끼기 위해 live 검색/요약은 필요한 만큼만 실행
- 실패 시 Render Dashboard의 Logs에서 최근 오류 확인
- 환경변수 수정 후 Manual Deploy 또는 redeploy 실행

## 관련 문서

| 문서 | 설명 |
|---|---|
| `README.md` | 설치, 실행, Render 설정 요약 |
| `docs/api_reference.md` | API 요청/응답 상세 |
| `docs/backend_test_plan.md` | 로컬/Live/배포 검증 전략 |
| `docs/release_notes.md` | 발표용 릴리스 상태와 known limitations |
| `DEVELOPMENT_PLAN.md` | Phase 4 작업 계획 |
