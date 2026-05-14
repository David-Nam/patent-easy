# PatentEasy 백엔드 시연 릴리스 노트

## v0.1.0 Render Demo

| 항목 | 내용 |
|---|---|
| 목적 | 생성형 AI의 이해와 활용 기말 프로젝트 발표/시연 |
| 배포 URL | `https://patent-easy-api.onrender.com` |
| 배포 플랫폼 | Render Free Web Service |
| Runtime | Python 3 + FastAPI + Uvicorn |
| LLM Provider | Gemini |
| 특허 API | KIPRIS Plus API |
| Cache | SQLite 임시 cache, `/tmp/patent-easy-cache.sqlite` |

## 포함 기능

- `GET /health`: 앱 프로세스 상태 확인
- `GET /ready`: cache, KIPRIS, LLM 설정 준비 상태 확인
- `GET /docs`: Swagger UI
- `GET /openapi.json`: OpenAPI JSON
- `POST /api/v1/search`: 자연어 아이디어 기반 KIPRIS 검색
- `GET /api/v1/patents/{patent_id}`: local mock 상세 조회
- `POST /api/v1/patents/{patent_id}/summary`: KIPRIS 상세/청구항 기반 Gemini 요약

## 배포 확인 상태

작업 18에서 확인한 항목:

- Render build 성공
- Uvicorn startup 성공
- `/health` 200 확인
- `/ready` `status=ready` 확인
- `/docs` Swagger UI 확인
- `/openapi.json` 정상 응답 확인

작업 19에서 확인할 항목:

- `scripts/smoke_test_deployed_api.py` 실행
- `/api/v1/search` 실제 검색 성공
- `/api/v1/patents/10-2023-0098765` mock 상세 조회 성공
- `/api/v1/patents/10-2023-0147601/summary` 실제 KIPRIS/Gemini 요약 성공

## Known Limitations

- Render Free Web Service는 15분 동안 요청이 없으면 sleep될 수 있습니다.
- sleep 후 첫 요청은 cold start 때문에 느릴 수 있습니다.
- Render 무료 인스턴스의 local filesystem은 ephemeral입니다.
- SQLite cache는 재시작, redeploy, sleep 이후 사라질 수 있습니다.
- `GET /api/v1/patents/{patent_id}`는 아직 KIPRIS 실제 상세 API가 아니라
  `data/mock_patents.json` 기반 mock 상세 조회입니다.
- KIPRIS/Gemini 호출 한도가 있으므로 발표 중 live 검색/요약 호출은 최소화합니다.

## 발표 전 운영 메모

- 발표 5분 전 `/health`, `/ready`, `/docs`를 열어 서버를 미리 깨웁니다.
- `/ready`가 `ready`인지 확인합니다.
- smoke test는 발표 리허설 때 한 번 실행하고, 발표 중에는 필요한 endpoint만 호출합니다.
- 실패 시 Render Dashboard의 Logs와 Environment Variables를 먼저 확인합니다.
