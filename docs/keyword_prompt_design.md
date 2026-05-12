# 키워드 추출 프롬프트 설계

이 문서는 자연어 제품 아이디어를 KIPRIS 검색에 사용할 수 있는 특허 검색 계획으로 변환하는 프롬프트 설계를 설명합니다.

## 목적

사용자는 특허 전문 용어나 IPC 코드를 모르는 상태에서 아이디어를 입력합니다. Query Builder는 이 입력을 다음 구조로 변환합니다.

1. 핵심 기술 키워드
2. 넓은 IPC prefix 후보
3. KIPRIS 검색 recall을 높이기 위한 확장어

이 결과는 KIPRIS 검색 API 호출 전에 사용되므로, 프롬프트의 최우선 목표는 안정적인 JSON 출력과 특허식 검색어 생성입니다.

## 현재 구현 상태

- 실제 프롬프트 파일: `app/prompts/extract_keywords.txt`
- 응답 schema: `app.schemas.search.ExtractedQuery`
- service 구현: `app/services/query_builder.py`
- deterministic mock: `app/services/mock_llm_client.py`
- 수동 검토 케이스: `data/keyword_prompt_cases.json`
- 기본 provider: Gemini
- 전환 가능 provider: OpenAI, mock

Gemini와 OpenAI provider는 같은 `ExtractedQuery` schema를 유지합니다. JSON 파싱 또는 schema 검증 실패 시 최대 2회 재시도합니다.

## 출력 계약

모델은 JSON만 반환해야 합니다.

```json
{
  "keywords": ["음식 이미지 인식", "칼로리 자동 계산", "맞춤형 식단 추천"],
  "ipc_codes": ["G06V", "G06N", "A23L"],
  "expanded_terms": {
    "음식 이미지 인식": ["식품 영상 인식", "음식 사진 식별", "식품 객체 검출"],
    "칼로리 자동 계산": ["열량 산출", "영양성분 분석", "식품 영양 추정"],
    "맞춤형 식단 추천": ["개인화 식단", "건강 상태 기반 추천", "영양 관리"]
  }
}
```

## 필드 규칙

| 필드 | 규칙 |
|---|---|
| `keywords` | 3~5개, 한국어 특허 검색에 적합한 기술 개념 |
| `ipc_codes` | 1~4개, `G06V`, `G06N`, `G06Q`, `A23L` 같은 broad prefix |
| `expanded_terms` | 모든 keyword를 key로 포함하고, 각 keyword마다 2~4개 확장어 제공 |

## 설계 원칙

- 모델에게 내부적으로 domain, function, input data, algorithm, output, IPC 후보를 생각하게 하되 reasoning은 출력하지 않습니다.
- IPC는 과도하게 세부 subclass를 만들지 않고 broad prefix 위주로 둡니다.
- "앱", "서비스", "시스템" 같은 일반어는 단독 keyword로 사용하지 않습니다.
- 일반어가 필요할 때는 "이미지 인식", "자동 계산", "위치 기반 추천"처럼 기술 기능과 결합합니다.
- 확장어는 KIPRIS 문헌에 자주 등장할 수 있는 특허식 표현을 우선합니다.
- 출력은 backend schema 검증을 통과해야 하므로 markdown, 설명문, 추가 key를 금지합니다.

## 검증 방법

offline 검증:

```bash
venv/bin/python -m pytest tests/test_query_builder.py
```

전체 품질 게이트:

```bash
venv/bin/python -m pytest
```

실제 Gemini provider 검증은 LLM live 테스트에 포함됩니다.

```bash
RUN_LIVE_LLM=1 venv/bin/python -m pytest tests/test_llm_client_live.py -m live_llm -s
```

현재 live 테스트는 요약 LLM Client 중심입니다. Query Builder의 실제 Gemini live 회귀 테스트가 필요해지면 `tests/test_query_builder_live.py`를 추가하는 것이 좋습니다.

## 수동 리뷰 체크리스트

프롬프트나 mock 케이스를 수정할 때 다음을 확인합니다.

- 키워드가 사용자의 핵심 아이디어를 보존하는가
- KIPRIS 검색어로 너무 넓거나 너무 좁지 않은가
- IPC prefix가 분야를 대략적으로 설명하는가
- `expanded_terms`가 keyword마다 빠짐없이 존재하는가
- 확장어가 검색 recall을 높이되 주제에서 크게 벗어나지 않는가
- 같은 입력에 대해 mock 출력과 실제 provider 출력의 schema가 일관적인가
