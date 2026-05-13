# PatentEasy 백엔드 평가 계획

## 목적

작업 16의 목적은 백엔드 검색 파이프라인을 정량적으로 점검하는 것입니다.
이 평가는 배포 전 품질 게이트와 별개로, 자연어 쿼리에서 추출된 키워드와
검색 결과가 사람이 정한 기준에 얼마나 가까운지 확인하기 위해 사용합니다.

## 평가 데이터셋

평가 케이스는 `data/eval_queries.json`에 저장합니다.

각 케이스는 다음 필드를 가집니다.

| 필드 | 설명 |
|---|---|
| `id` | 케이스 식별자 |
| `query` | 사용자가 입력할 자연어 아이디어 |
| `expected_keywords` | 기대 핵심 키워드 |
| `expected_ipc_codes` | 기대 IPC prefix 후보 |
| `expected_patent_ids` | 관련 특허로 인정할 후보 ID |

현재 데이터셋은 음식 이미지/식단 추천, 전기차 충전소, 중고차 상담,
홈트레이닝, 낙상 감지, 차량 AR 표시, 복약 관리, 재활용 분류 등
10개 케이스로 구성되어 있습니다.

## 실행 방법

기본 실행은 외부 API를 호출하지 않는 mock benchmark입니다.

```bash
venv/bin/python scripts/benchmark.py --mode mock --cache off
```

결과를 파일로 저장하려면 `--output`을 사용합니다.

```bash
venv/bin/python scripts/benchmark.py \
  --mode mock \
  --cache off \
  --output data/benchmark_mock_latest.json
```

실제 KIPRIS 또는 Gemini/OpenAI를 호출하는 평가는 명시적으로
`--allow-live`를 붙여야 합니다.

```bash
venv/bin/python scripts/benchmark.py \
  --mode real \
  --llm-provider gemini \
  --cache on \
  --allow-live \
  --output data/benchmark_real_gemini_latest.json
```

KIPRIS는 실제로 호출하되 Query Builder는 deterministic mock으로 유지하려면
다음처럼 실행합니다.

```bash
venv/bin/python scripts/benchmark.py \
  --mode real \
  --llm-provider mock \
  --cache on \
  --allow-live
```

## 측정 항목

| 항목 | 의미 |
|---|---|
| `precision_at_10` | 상위 10개 결과 중 기대 관련 특허가 포함된 비율 |
| `recall_at_10` | 기대 관련 특허 중 상위 10개에 포함된 비율 |
| `keyword_recall` | 기대 키워드 중 Query Builder 결과에 포함된 비율 |
| `ipc_recall` | 기대 IPC 후보 중 추출 결과에 포함된 비율 |
| `latency_ms` | 케이스별 검색 처리 시간 |
| `kipris_call_count` | KIPRIS upstream 호출 횟수 |
| `llm_call_count` | Query Builder LLM 호출 횟수 |

`precision_at_10`의 분모는 항상 10입니다. mock corpus가 10건보다 작아도
동일 기준을 유지해 실제 검색 결과와 비교 가능한 형태로 둡니다.

## 결과 해석 기준

초기 기준은 다음과 같이 둡니다.

| 항목 | 목표 |
|---|---|
| mock `mean_keyword_recall` | 0.8 이상 |
| mock `mean_ipc_recall` | 0.8 이상 |
| mock `mean_recall_at_10` | 0.7 이상 |
| mock 평균 응답 시간 | 로컬에서 500ms 이하 |
| live KIPRIS 호출 수 | 케이스당 1회 내외 |

real benchmark는 KIPRIS 검색 품질과 외부 API 상태에 영향을 받습니다.
따라서 live 결과는 단일 성공/실패 판정보다는 추세 확인용으로 사용합니다.

## 주의사항

- 기본 benchmark는 mock/local corpus만 사용하므로 API key가 필요 없습니다.
- `--allow-live` 없이는 real KIPRIS 또는 real LLM 호출이 실행되지 않습니다.
- benchmark 결과 파일에는 API key를 저장하지 않습니다.
- 실제 KIPRIS 결과가 기대 특허 ID와 다를 수 있으므로, live 결과를 본 뒤
  `data/eval_queries.json`의 기대값을 수동으로 보정할 수 있습니다.
