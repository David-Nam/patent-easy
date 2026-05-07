# Keyword Extraction Prompt Design

## Purpose

The keyword extraction prompt converts a non-expert Korean product idea into
a KIPRIS-friendly search plan. The backend uses this output before calling
KIPRIS, so the prompt prioritizes stable JSON, Korean patent-style terms, and
broad recall.

## Current Status

- Real LLM provider integration is not required yet.
- Gemini API free tier is the default target for the first real provider.
- OpenAI must remain switchable through the same output contract.
- `app/services/mock_llm_client.py` provides deterministic mock outputs for
  frontend and backend flow testing.
- The production prompt lives in `app/prompts/extract_keywords.txt`.
- Manual review cases live in `data/keyword_prompt_cases.json`.

## Output Contract

The model must return JSON only:

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

## Design Notes

- The prompt asks the model to reason internally, but never output reasoning.
- IPC codes are broad prefixes to avoid overconfident classification.
- Keywords avoid generic product words unless paired with technical function.
- Expanded terms improve KIPRIS recall by adding patent-style synonyms.
- The response shape matches `app.schemas.search.ExtractedQuery`.

## Manual Review

Run the mock E2E script to inspect the deterministic output for all review
cases:

```bash
python scripts/manual_e2e_test.py
```

When a Gemini key is available, replace the mock call with Gemini structured
output in the later Query Builder task. Keep the same schema so OpenAI can be
used as a provider replacement later.
