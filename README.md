# PatentEasy Backend

AI 기반 특허 검색 서비스 PatentEasy의 FastAPI 백엔드입니다. KIPRIS Plus API는 실제 키로 검증했고, OpenAI 의존 기능은 키 발급 전까지 Mock으로 동작합니다.

Python 프로젝트 메타데이터와 테스트 설정은 `pyproject.toml`에 두고, 로컬 설치 의존성은 `requirements.txt`로 관리합니다.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

- Health check: `http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`

## Mock API

Frontend integration details are in `docs/frontend_mock_api_guide.md`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/api/v1/search` | 자연어 검색 요청에 대한 Mock 특허 목록 반환 |
| `GET` | `/api/v1/patents/{patent_id}` | Mock 특허 상세 조회 |
| `POST` | `/api/v1/patents/{patent_id}/summary` | Mock AI 요약 생성 |

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능","page":1,"page_size":10}'
```

```bash
curl http://localhost:8000/api/v1/patents/10-2023-0098765
```

```bash
curl -X POST http://localhost:8000/api/v1/patents/10-2023-0098765/summary \
  -H "Content-Type: application/json" \
  -d '{"user_query":"배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능"}'
```

## KIPRIS Verification

KIPRIS Plus API는 실제 키로 raw 응답을 확인한 뒤 실제 client 구현으로 넘어갑니다.

1. `.env`에 `KIPRIS_API_KEY`를 입력합니다.
2. 필요하면 `.env`의 `KIPRIS_*_PATH` 값을 KIPRIS Plus 콘솔 기준으로 수정합니다.
3. 아래 명령을 실행합니다.

```bash
python scripts/verify_kipris_api.py
```

실행 결과는 다음 위치에 저장됩니다.

- Raw XML/JSON: `tests/fixtures/kipris_raw/`
- Normalized JSON: `tests/fixtures/kipris_normalized/`
- 조사 문서: `docs/kipris_api_research.md`

## Tests

```bash
pytest
```
