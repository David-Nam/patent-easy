# 백엔드 테스트 계획

이 문서는 PatentEasy 백엔드를 배포하기 전에 실행할 테스트 그룹과 품질 게이트를 정리합니다.

## 기본 원칙

- 기본 `pytest`는 외부 API를 호출하지 않습니다.
- KIPRIS와 LLM live 테스트는 명시 플래그를 켠 경우에만 실행합니다.
- live 테스트는 실제 호출 비용과 호출 한도를 사용하므로 배포 전, provider 변경 후, 프롬프트 변경 후에만 실행합니다.
- 실제 API 키가 들어 있는 `.env`는 커밋하지 않습니다.
- 실패한 live 테스트는 실행 명령, 실패 시각, upstream 오류 메시지를 남깁니다.

## 테스트 그룹

| 그룹 | 명령 | 외부 API | 목적 |
|---|---|---:|---|
| Offline 기본 테스트 | `venv/bin/python -m pytest` | 없음 | 단위, fixture, API, cache, OpenAPI 계약 테스트 |
| KIPRIS live 검색 | `RUN_LIVE_KIPRIS=1 venv/bin/python -m pytest tests/test_search_live.py -m live_kipris -s` | KIPRIS | 실제 KIPRIS API 기반 검색 엔드포인트 검증 |
| LLM live | `RUN_LIVE_LLM=1 venv/bin/python -m pytest tests/test_llm_client_live.py -m live_llm -s` | Gemini/OpenAI | LLM provider 키, structured output, token usage 검증 |
| 요약 live | `RUN_LIVE_KIPRIS=1 RUN_LIVE_LLM=1 venv/bin/python -m pytest tests/test_summary_live.py -m "live_kipris and live_llm" -s` | KIPRIS + LLM | KIPRIS 상세/청구항 조회와 LLM 요약 통합 검증 |

## 품질 게이트 스크립트

반복 실행은 `scripts/run_quality_gate.py`를 사용합니다.

```bash
venv/bin/python scripts/run_quality_gate.py
venv/bin/python scripts/run_quality_gate.py --live-kipris
venv/bin/python scripts/run_quality_gate.py --live-llm
venv/bin/python scripts/run_quality_gate.py --live-kipris --live-llm --live-summary
```

## 필요한 환경변수

offline 테스트는 API 키가 없어도 실행됩니다.

live 테스트에는 다음 값이 필요합니다.

```env
KIPRIS_API_KEY=...
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
RUN_LIVE_KIPRIS=1
RUN_LIVE_LLM=1
```

OpenAI 전환 검증을 할 때는 `LLM_PROVIDER=openai`, `OPENAI_API_KEY=...`를 사용합니다.

## 현재 테스트 구성

| 파일 | 역할 |
|---|---|
| `tests/test_cache.py` | SQLite cache, TTL, sync/async decorator 검증 |
| `tests/test_kipris_client.py` | KIPRIS XML fixture 파싱, cache, pagination 검증 |
| `tests/test_query_builder.py` | mock/Gemini/OpenAI Query Builder adapter 검증 |
| `tests/test_llm_client.py` | mock/Gemini/OpenAI LLM Client adapter 검증 |
| `tests/test_search_service.py` | 검색 service 조립 로직 검증 |
| `tests/test_search_api.py` | 검색 API 오류 매핑 검증 |
| `tests/test_summary_service.py` | 요약 service cache 흐름 검증 |
| `tests/test_summary_api.py` | 요약 API 오류 매핑 검증 |
| `tests/test_openapi_contract.py` | OpenAPI 경로, 응답 모델, 에러 status 계약 검증 |
| `tests/test_search_live.py` | 실제 KIPRIS 검색 live 검증 |
| `tests/test_llm_client_live.py` | 실제 Gemini LLM live 검증 |
| `tests/test_summary_live.py` | 실제 KIPRIS + Gemini 요약 live 검증 |

## Release Candidate 기준

Phase 4 배포 전 release candidate는 다음 조건을 만족해야 합니다.

- offline 기본 테스트가 통과합니다.
- OpenAPI 계약 테스트가 `/search`, `/patents/{id}`, `/patents/{id}/summary`의 응답 모델과 에러 status를 확인합니다.
- KIPRIS client, KIPRIS 설정, 검색 endpoint 변경 후에는 KIPRIS live 검색이 1회 이상 통과합니다.
- LLM prompt, LLM provider, model 설정 변경 후에는 LLM live 테스트가 1회 이상 통과합니다.
- 배포 또는 발표 리허설 전에는 요약 live 테스트가 1회 이상 통과합니다.
- live 테스트 실패 시 원인을 문서 또는 이슈에 남기고 재시도 여부를 결정합니다.

## 아직 보강할 항목

- 작업 14에서 표준 에러 응답 모델을 OpenAPI schema로 명시해야 합니다.
- 작업 15에서 request latency, provider 호출 횟수, token usage 로그를 구조화해야 합니다.
- 작업 16에서 평가용 쿼리와 benchmark script를 추가해 정량 품질 지표를 산출해야 합니다.
