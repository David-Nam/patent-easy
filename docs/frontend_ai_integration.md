# PatentEasy Frontend AI Integration Spec

## Role

You are configuring a frontend app to consume the PatentEasy backend Mock API.

## Backend Base URL

Use an environment variable:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Do not hard-code the base URL outside the env fallback layer.

## API Keys

No API key is required for frontend Mock API integration.

The frontend must not read or send `KIPRIS_API_KEY`, `GEMINI_API_KEY`, or
`OPENAI_API_KEY`. Those keys are backend-only and are not needed while the
backend serves Mock search, detail, and summary responses.

## Required Endpoints

### Health

```http
GET /health
```

Expected response:

```json
{
  "status": "ok",
  "service": "patent-easy-backend"
}
```

### Search

```http
POST /api/v1/search
Content-Type: application/json
```

Request:

```json
{
  "query": "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능",
  "filters": {
    "applicant": null,
    "ipc_codes": null,
    "year_from": null,
    "year_to": null
  },
  "page": 1,
  "page_size": 10
}
```

Response shape:

```ts
type SearchResponse = {
  query: string;
  extracted: {
    keywords: string[];
    ipc_codes: string[];
    expanded_terms: Record<string, string[]>;
  };
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
  };
  results: PatentListItem[];
};
```

### Patent Detail

```http
GET /api/v1/patents/{patent_id}
```

Response shape:

```ts
type PatentDetail = PatentListItem & {
  abstract: string;
  inventors: string[];
  publication_date: string | null;
  registration_date: string | null;
  legal_status: string | null;
  claims: Claim[];
};
```

### Summary

```http
POST /api/v1/patents/{patent_id}/summary
Content-Type: application/json
```

Request:

```json
{
  "user_query": "배달앱에서 음식 사진을 찍으면 칼로리를 계산해주는 기능"
}
```

Response shape:

```ts
type SummaryResponse = {
  patent_id: string;
  core_summary: string;
  business_application: string;
  key_tags: string[];
  generated_at: string;
  is_cached: boolean;
  disclaimer: string;
};
```

## Shared Types

```ts
type PatentListItem = {
  patent_id: string;
  title: string;
  applicant: string;
  application_date: string | null;
  ipc_codes: string[];
  relevance_score: number;
  tags: string[];
  abstract_preview: string;
  kipris_url: string | null;
};

type Claim = {
  number: number;
  text: string;
};

type SearchFilters = {
  applicant?: string | null;
  ipc_codes?: string[] | null;
  year_from?: number | null;
  year_to?: number | null;
};

type SearchRequest = {
  query: string;
  filters?: SearchFilters;
  page?: number;
  page_size?: number;
};
```

## Implementation Requirements

- Create a small API client module for the backend.
- Read the base URL from `NEXT_PUBLIC_API_BASE_URL`.
- Default `filters` to an empty object when the UI does not provide filters.
- Default `page` to `1`.
- Default `page_size` to `10`.
- Surface non-2xx responses as user-visible errors.
- Do not call KIPRIS or LLM providers directly from the frontend.
- Do not duplicate Mock data in the frontend.

## Suggested API Client Interface

```ts
export async function searchPatents(input: SearchRequest): Promise<SearchResponse>;
export async function getPatentDetail(patentId: string): Promise<PatentDetail>;
export async function summarizePatent(
  patentId: string,
  userQuery?: string
): Promise<SummaryResponse>;
```

## Acceptance Criteria

- The frontend can search with a natural Korean sentence.
- Search results render title, applicant, date, IPC codes, score, tags, and abstract preview.
- Clicking a result can fetch detail by `patent_id`.
- The detail page or panel renders claims.
- The summary action calls the summary endpoint and renders `core_summary`, `business_application`, `key_tags`, and `disclaimer`.
- The API base URL can be changed without code changes.
