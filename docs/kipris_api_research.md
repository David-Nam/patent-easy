# KIPRIS Plus API Research

Last verification run: `pending`

## Verification Policy

- KIPRIS Plus API must be verified with a real `KIPRIS_API_KEY` before implementing the real `KIPRISClient`.
- Raw responses are saved exactly as received under `tests/fixtures/kipris_raw/`.
- Normalized JSON is generated under `tests/fixtures/kipris_normalized/` only to make field review easier.
- OpenAI is not required for this verification.

## How To Run

```bash
cp .env.example .env
# Edit .env and set KIPRIS_API_KEY.
python scripts/verify_kipris_api.py
```

The script calls:

- `freeSearchInfo` using `KIPRIS_SEARCH_PATH`
- `getBibliographyDetailInfoSearch` using `KIPRIS_DETAIL_PATH` when an application number is found
- `patentClaimInfo` using `KIPRIS_CLAIM_PATH` when an application number is found

## Next Review Checklist

- Confirm exact field names for application number, title, applicant, dates, legal status, abstract, claims, and IPC.
- Confirm whether the response contract is XML-only or varies by endpoint.
- Confirm the actual call quota from the KIPRIS Plus account page before running broad tests.
- Update `app/services/kipris_client.py` only after the raw fixtures have been reviewed.
