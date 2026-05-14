# Frontend Mock API Guide

> 현재 배포 백엔드 연동은 `docs/frontend_backend_integration_guide.md`를 기준으로 합니다.
> 이 문서는 초기 로컬 Mock API 개발 흐름을 이해하기 위한 참고 문서입니다.

이 문서는 프론트엔드 담당자가 PatentEasy 백엔드 Mock API를 로컬에서 연결하는 방법을 설명합니다.

## 목적

초기 개발 단계에서는 프론트엔드 개발을 막지 않기 위해 Mock API 계약을 먼저
고정했습니다. 현재 배포 서버는 검색과 요약에서 실제 KIPRIS/Gemini를 호출하고,
상세 조회만 local mock 데이터를 사용합니다. 실제 프론트엔드 연동은
`docs/frontend_backend_integration_guide.md`를 우선 확인하세요.

## 직접 설정하는 방법

백엔드 repo 루트에서 실행합니다.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

과거 Mock provider만 사용할 때는 실제 API key가 필요 없었습니다. 현재 로컬 서버에서
실제 검색/요약까지 호출하려면 `.env`에 KIPRIS/Gemini key가 필요합니다.

```env
KIPRIS_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
```

KIPRIS key는 실제 검색, 상세/청구항 조회, `scripts/verify_kipris_api.py` 실행에
필요합니다. Gemini/OpenAI key는 실제 키워드 추출, 요약, 재정렬에 필요합니다.
현재 기본 계획은 Gemini 무료 tier 우선, OpenAI 전환 가능 구조입니다.

브라우저에서 확인합니다.

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

`/health`가 아래처럼 나오면 서버가 정상입니다.

```json
{"status":"ok","service":"patent-easy-backend"}
```

## 프론트엔드 환경변수

Next.js 프로젝트의 `.env.local`에 아래 값을 둡니다.

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

배포된 백엔드를 연결할 때는 다음 값을 사용합니다.

```env
NEXT_PUBLIC_API_BASE_URL=https://patent-easy-api.onrender.com
```

프론트엔드 코드에서는 이 값을 기준으로 API를 호출합니다.

```ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;
```

## 엔드포인트

| Method | Path | 용도 |
|---|---|---|
| `GET` | `/health` | 백엔드 서버 상태 확인 |
| `POST` | `/api/v1/search` | 자연어 검색 요청 후 특허 목록 반환 |
| `GET` | `/api/v1/patents/{patent_id}` | 특허 상세 조회 |
| `POST` | `/api/v1/patents/{patent_id}/summary` | 특허 AI 요약 반환 |

## 호출 예시

검색:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능","page":1,"page_size":10}'
```

상세:

```bash
curl http://127.0.0.1:8000/api/v1/patents/10-2023-0098765
```

요약:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/patents/10-2023-0098765/summary \
  -H "Content-Type: application/json" \
  -d '{"user_query":"배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능"}'
```

## AI 도구에게 시키는 방법

Codex나 Claude Code를 프론트엔드 repo에서 사용할 경우 아래처럼 요청하면 됩니다.

```text
docs/frontend_backend_integration_guide.md와 docs/frontend_ai_integration.md 문서를 읽고
PatentEasy 프론트엔드에서 배포 백엔드 API를 연결해줘.
NEXT_PUBLIC_API_BASE_URL=https://patent-easy-api.onrender.com 을 기준으로 검색, 상세, 요약 API 클라이언트를 만들고 기존 화면에서 사용하게 해줘.
```

AI 도구에 전달할 문서는 [frontend_ai_integration.md](frontend_ai_integration.md)입니다. 이 문서는 사람이 읽기보다 AI가 구현 기준으로 읽기 쉽게 작성되어 있습니다.

## 주의사항

- 현재 배포 서버의 검색과 요약은 실제 KIPRIS/Gemini 호출입니다.
- 현재 배포 서버의 상세 조회는 `data/mock_patents.json` 기준입니다.
- 백엔드 CORS는 기본적으로 `localhost:3000`, `127.0.0.1:3000`, `localhost:5173`, `127.0.0.1:5173`을 허용합니다.
- API 계약이 바뀌면 이 문서와 Swagger UI를 함께 확인하세요.
