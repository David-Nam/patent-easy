# KIPRIS Plus API Research

Last verification run: `2026-05-06T23:38:58.341158+00:00`

## Verification Policy

- KIPRIS Plus API must be verified with a real `KIPRIS_API_KEY` before implementing the real `KIPRISClient`.
- Raw responses are saved exactly as received under `tests/fixtures/kipris_raw/`.
- Normalized JSON is generated under `tests/fixtures/kipris_normalized/` only to make field review easier.
- LLM provider keys are not required for this verification.

## Endpoints Checked

Endpoint note: OpenAPI endpoints use `accessKey`, while the
bibliography detail endpoint uses `/kipo-api/kipi/...` with `ServiceKey`.

### free_search

- Path: `/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo`
- HTTP status: `200`
- Body format: `xml`
- Raw fixture: `tests/fixtures/kipris_raw/free_search_20260506T233857Z.xml`
- Extracted records: `5`
- First application number: `1020230147601`

Sample normalized record:

```json
{
  "patent_id": "1020230147601",
  "title": "전기자동차의 배터리 열관리 시스템 및 이의 운용 방법",
  "applicant": "서울대학교산학협력단",
  "application_date": "20231031",
  "registration_date": "20260429",
  "abstract": "본 발명에 따른 전기자동차의 배터리 열관리 시스템 및 이의 운용 방법은, 초기 온도와 주행 데이터에 따라 최적의 배터리 열관리 모드를 도출하도록 구성됨으로써, 배터리의 성능과 수명을 보다 효율적으로 관리할 수 있는 이점이 있다. 또한, 본 발명에서는 전기자동차 에너지 모델을 이용하여 전기자동차의 소모 전력량을 산출하고, 배터리 에너지 모델을 이용하여 배터리의 전압 변화와 배터리의 소모 에너지를 산출함으로써, 히트펌프의 열 거동에 따른 소모 전력량과 배터리의 열과 전기화학 거동에 따른 소모 전력량을 모두 고려하여 최적의 배터리 열관리 모드를 도출할 수 있으므로, 차실 난방과 배터리 열관리를 보다 효과적으로 수행할 수 있다. 또한, 전기자동차의 가상 주행시 배터리의 전압이 컷 오프 전압에 도달하는지 여부를 미리 예측하여, 배터리의 전압이 컷 오프 전압에 도달한다고 판단되면, 주행 가능 거리가 최대인 배터리 열관리 모드로 작동시킴으로써, 겨울철 전기자동차의 주행 가능 거리가 감소하는 현상을 방지할 수 있다."
}
```

### bibliography_detail

- Path: `/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch`
- HTTP status: `200`
- Body format: `xml`
- Raw fixture: `tests/fixtures/kipris_raw/bibliography_detail_20260506T233858Z.xml`
- Extracted records: `10`
- First application number: `10-2023-0147601`

Sample normalized record:

```json
{
  "patent_id": "10-2023-0147601",
  "title": "전기자동차의 배터리 열관리 시스템 및 이의 운용 방법",
  "application_date": "2023.10.31",
  "publication_date": "2025.05.09",
  "registration_date": "2026.04.29",
  "legal_status": "등록결정(일반)"
}
```

### claim_detail

- Path: `/openapi/rest/patUtiModInfoSearchSevice/patentClaimInfo`
- HTTP status: `200`
- Body format: `xml`
- Raw fixture: `tests/fixtures/kipris_raw/claim_detail_20260506T233858Z.xml`
- Extracted records: `10`
- First application number: `not found`

Sample normalized record:

```json
{
  "claim": "1. 전기자동차에 동력을 제공하는 배터리와;압축기, 응축기, 팽창밸브 및 증발기를 포함하는 히트펌프와;상기 응축기에서 가열된 냉각수와 차실로 유입되는 공기를 열교환시켜, 차실을 난방시키기 위한 실내 열교환기와;상기 응축기와 상기 실내 열교환기를 연결하여, 미리 설정된 복수의 배터리 열관리 모드들 중에서 상기 히트펌프의 열원을 상기 배터리에 사용하지 않는 배터리 자가발열 모드시, 상기 응축기에서 가열된 냉각수를 상기 실내 열교환기로 안내하기 위한 응축기 토출유로와;상기 응축기와 상기 배터리를 연결하여, 상기 복수의 배터리 열관리 모드들 중에서 상기 히트펌프의 열원을 상기 배터리의 가열에 이용하는 배터리 능동가열 모드시, 상기 응축기에서 가열된 냉각수 중 적어도 일부를 상기 배터리로 공급하여 상기 배터리를 가열한 후 상기 응축기로 순환시키기 위한 배터리 가열 유로와; 상기 증발기와 상기 배터리를 연결하여, 상기 복수의 배터리 열관리 모드 중에서 상기 배터리의 열원을 상기 히트펌프의 열원으로 이용하는 배터리 열회수 모드시, 상기 증발기에서 냉각된 냉각수 중 적어도 일부를 상기 배터리로 공급하여 상기 배터리의 열원을 흡수한 후 상기 증발기로 순환시키기 위한 배터리 열회수 유로와;상기 배터리 가열 유로를 개폐하는 배터리 가열 밸브와;상기 배터리 열회수 유로를 개폐하는 배터리 열회수 밸브와;상기 전기자동차의 주행이 시작되면, 외기 온도, 배터리 온도, 전장부품 온도, 차실 온도 및 배터리 충전량을 포함한 초기 데이터를 수집하는 초기 데이터 수집부와;출발지로부터 목적지까지 가상 주행시 주행 속도와 주행 시간을 포함한 주행 데이터를 예측하여 산출하는 주행 데이터 산출부와;상기 전기자동차가 상기 목적지까지 상기 가상 주행시 상기 초기 데이터와 상기 주행 데이터에 따른 상기 배터리의 전압 변화, 상기 배터리 열관리 모드별 주행 가능 거리, 상기 배터리 열관리 모드별 상기 배터리의 소모 에너지를 포함한 배터리 데이터를 예측하여 산출하는 배터리 데이터 산출부와;상기 배터리의 전압 변화로부터 상기 배터리의 전압이 미리 설정된 컷 오프 전압에 도달하는지 여부를 판단하고, 상기 배터리의 전압이 상기 컷 오프 전압에 도달한다고 판단되면, 상기 배터리 열관리 모드들 중에서 상기 주행 가능 거리가 최대인 배터리 열관리 모드를 최적 배터리 열관리 모드로 도출하고, 도출된 최적 배터리 열관리 모드에 따라 상기 배터리 가열 밸브와 상기 배터리 열회수 밸브를 선택적으로 개폐시키는 제어부를 포함하고,상기 배터리 데이터 산출부는,상기 초기 데이터와 상기 주행 데이터에 따라 상기 전기자동차에서 소모되는 전력 소모량을 산출하도록 미리 구축된 수학적 모델인 전기자동차 에너지 모델과,상기 초기 데이터, 상기 주행 데이터 및 상기 전력 소모량에 따라 상기 배터리의 전압 변화와 상기 배터리의 소모 에너지를 산출하도록 미리 구축된 수학적 모델인 배터리 에너지 모델을 사용하고,상기 전력 소모량은, 상기 전기자동차 에너지 모델에 상기 초기 데이터와 상기 주행 데이터를 입력하면 산출되고,상기 배터리의 전압 변화는, 상기 배터리 에너지 모델에 상기 초기 데이터, 상기 주행 데이터 및 상기 전력 소모량을 입력하여면산출되고,상기 배터리 열관리 모드별 주행 가능 거리는, 상기 배터리의 전압 변화에 따라 산출되고,상기 배터리의 소모 에너지는, 상기 배터리 에너지 모델에 상기 초기 데이터, 상기 주행 데이터 및 상기 전력 소모량을 입력하면 산출되는,전기자동차의 배터리 열관리 시스템."
}
```

## Next Review Checklist

- Confirm exact field names for application number, title, applicant, dates, legal status, abstract, claims, and IPC.
- Confirm whether the response contract is XML-only or varies by endpoint.
- Confirm the actual call quota from the KIPRIS Plus account page before running broad tests.
- Update `app/services/kipris_client.py` only after the raw fixtures have been reviewed.
