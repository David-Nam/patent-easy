# PatentEasy Frontend AI Integration Spec

이 문서는 Codex, Claude Code 같은 AI 개발 도구가 PatentEasy 프론트엔드에
백엔드 API를 연결할 때 읽는 구현 스펙입니다. 사람용 설명은
`docs/frontend_backend_integration_guide.md`를 기준으로 합니다.

## Goal

Implement a frontend API client for the deployed PatentEasy FastAPI backend and
wire it into search, patent detail, summary, and patent chat UI flows.

## Backend

Use an environment variable for the base URL.

```env
NEXT_PUBLIC_API_BASE_URL=https://patent-easy-api.onrender.com
```

For Vite projects, use:

```env
VITE_API_BASE_URL=https://patent-easy-api.onrender.com
```

Do not hard-code the base URL outside one API client/config layer.

## Security

No frontend API key is required.

The frontend must not read, store, log, or send these server-only variables:

- `KIPRIS_API_KEY`
- `KIPRIS_API_SUB1_KEY`
- `KIPRIS_API_SUB2_KEY`
- `GEMINI_API_KEY`
- `OPENAI_API_KEY`

The browser talks only to the PatentEasy backend. It must never call KIPRIS,
Gemini, or OpenAI directly.

## Current Backend Behavior

This table describes the current backend code contract.

| Endpoint | Current behavior |
|---|---|
| `POST /api/v1/search` | Live Gemini query building plus live KIPRIS search. |
| `GET /api/v1/patents/{patent_id}` | Live KIPRIS bibliography/claim lookup. |
| `POST /api/v1/patents/{patent_id}/summary` | Live KIPRIS bibliography/claim lookup plus Gemini summary. |
| `POST /api/v1/patents/{patent_id}/chat` | Live KIPRIS bibliography/claim lookup plus Gemini single-patent Q&A. |

Known demo IDs:

- Detail: `10-2023-0147601`
- Summary: `10-2023-0147601`
- Chat: `10-2023-0147601`

## Required Endpoints

### Health

```http
GET /health
```

Use only for debugging or optional service status UI.

### Readiness

```http
GET /ready
```

Use only for debugging. Do not block normal user flows on this endpoint unless
the product explicitly has a backend status view.

### Search

```http
POST /api/v1/search
Content-Type: application/json
```

Request:

```json
{
  "query": "전기차 배터리 열관리 시스템",
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

Rules:

- `query` is required, 2 to 500 characters.
- `page` defaults to `1`.
- `page_size` defaults to `10`, max `50`.
- `filters` may be omitted or sent as `{}`.

### Patent Detail

```http
GET /api/v1/patents/{patent_id}
```

Rules:

- This endpoint calls live KIPRIS bibliography and claim APIs.
- It can be slower than search on cache miss.
- Handle `DETAIL_UPSTREAM_ERROR`, `DETAIL_CONFIGURATION_ERROR`, and
  `PATENT_NOT_FOUND` without crashing.
- Use `original_url` first for 원문보기 and fall back to `kipris_url`.

### Similar Patents

```http
GET /api/v1/patents/{patent_id}/similar?limit=5
```

Rules:

- This endpoint calls live KIPRIS detail and search APIs.
- `limit` is optional, 1 to 10.
- Handle `SIMILAR_UPSTREAM_ERROR` as a partial section failure.

### Summary

```http
POST /api/v1/patents/{patent_id}/summary
Content-Type: application/json
```

Request:

```json
{
  "user_query": "전기차 배터리 열관리 기능"
}
```

Rules:

- `user_query` is optional and may be `null`.
- This endpoint can be slower than search because it may call KIPRIS and Gemini.
- `is_cached=true` is a successful response.

### Chat

```http
POST /api/v1/patents/{patent_id}/chat
Content-Type: application/json
```

Request:

```json
{
  "question": "이 특허는 전기차 배터리 열관리 기능과 관련이 있나요?",
  "user_query": "전기차 배터리 열관리 기능",
  "history": [
    { "role": "user", "content": "이 특허 핵심이 뭐야?" },
    { "role": "assistant", "content": "청구항 1은..." }
  ]
}
```

Rules:

- `question` is required, 2 to 500 characters.
- `user_query` is optional and may be `null`.
- `history` is optional, max 6 messages.
- `role` must be `user` or `assistant`.
- Backend does not store chat sessions. The frontend owns recent history.
- This endpoint can be slower than search because it may call KIPRIS and Gemini.
- `sources` are evidence snippets and should be displayed with the answer.

## TypeScript Contract

```ts
export type ApiErrorBody = {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
};

export type SearchFilters = {
  applicant?: string | null;
  ipc_codes?: string[] | null;
  cpc_codes?: string[] | null;
  status?: string | null;
  year_from?: number | null;
  year_to?: number | null;
};

export type SearchRequest = {
  query: string;
  filters?: SearchFilters;
  page?: number;
  page_size?: number;
};

export type ExtractedQuery = {
  keywords: string[];
  ipc_codes: string[];
  expanded_terms: Record<string, string[]>;
};

export type Pagination = {
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
};

export type PatentListItem = {
  patent_id: string;
  title: string;
  applicant: string;
  application_date: string | null;
  ipc_codes: string[];
  cpc_codes: string[];
  status: string | null;
  application_status: string | null;
  publication_date: string | null;
  publication_number: string | null;
  registration_date: string | null;
  registration_number: string | null;
  citation_count: number | null;
  cited_by_count: number | null;
  similarity_score: number | null;
  relevance_score: number;
  tags: string[];
  abstract_preview: string;
  thumbnail_url: string | null;
  drawing_url: string | null;
  kipris_url: string | null;
  original_url: string | null;
};

export type Claim = {
  number: number;
  text: string;
};

export type PatentDetail = PatentListItem & {
  abstract: string;
  inventors: string[];
  legal_status: string | null;
  claims: Claim[];
  legal_events: LegalEvent[];
  cited_patents: PatentReference[];
  cited_by_patents: PatentReference[];
  family_patents: PatentReference[];
};

export type LegalEvent = {
  status: string | null;
  document_name: string | null;
  receipt_date: string | null;
  receipt_number: string | null;
};

export type PatentReference = {
  patent_id: string | null;
  title: string | null;
  applicant: string | null;
  application_date: string | null;
  status: string | null;
  relation: string | null;
  source: string | null;
  kipris_url: string | null;
  original_url: string | null;
};

export type SimilarPatentsResponse = {
  patent_id: string;
  strategy: string;
  results: PatentListItem[];
};

export type SearchResponse = {
  query: string;
  extracted: ExtractedQuery;
  pagination: Pagination;
  results: PatentListItem[];
};

export type SummaryRequest = {
  user_query?: string | null;
};

export type SummaryResponse = {
  patent_id: string;
  core_summary: string;
  business_application: string;
  key_tags: string[];
  generated_at: string;
  is_cached: boolean;
  disclaimer: string;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatRequest = {
  question: string;
  user_query?: string | null;
  history?: ChatMessage[];
};

export type ChatSource = {
  type: "abstract" | "claim";
  snippet: string;
  claim_number?: number | null;
};

export type ChatResponse = {
  patent_id: string;
  answer: string;
  sources: ChatSource[];
  generated_at: string;
  is_cached: boolean;
  disclaimer: string;
};
```

## API Client Requirements

Create one API client module with these exported functions:

```ts
export async function searchPatents(input: SearchRequest): Promise<SearchResponse>;
export async function getPatentDetail(patentId: string): Promise<PatentDetail>;
export async function getSimilarPatents(
  patentId: string,
  limit?: number
): Promise<SimilarPatentsResponse>;
export async function summarizePatent(
  patentId: string,
  userQuery?: string
): Promise<SummaryResponse>;
export async function chatAboutPatent(
  patentId: string,
  input: ChatRequest
): Promise<ChatResponse>;
```

Implementation rules:

- Use `fetch` or the project’s existing HTTP client.
- Prefix all paths with the env-based base URL.
- Always send `Content-Type: application/json` for JSON requests.
- Encode `patent_id` path values with `encodeURIComponent`.
- Parse non-2xx JSON errors as `ApiErrorBody`.
- Preserve backend `code`, `message`, and `details` for UI decisions.
- Handle network errors separately from backend JSON errors.

## UI Requirements

Search UI:

- Shows loading while `/api/v1/search` is pending.
- Shows empty state when `results.length === 0`.
- Renders `title`, `applicant`, `application_date`, `ipc_codes`,
  `status`, `registration_number`, `relevance_score`, `tags`,
  `abstract_preview`, and `original_url`.
- Renders `cpc_codes`; the backend enriches them through KIPRIS
  `patentCpcInfo`.
- Resolves relative `original_url` values against the backend API base URL
  before opening 원문보기.
- Optionally renders `extracted.keywords` and `extracted.ipc_codes`.

Detail UI:

- Calls `getPatentDetail(patentId)` only when a detail view is opened.
- Shows loading because live KIPRIS calls can take several seconds.
- Renders claims, `legal_events`, `cited_patents`, `family_patents`, and
  status fields if detail exists.
- Uses `original_url` or `kipris_url` for 원문보기.
- Handles `DETAIL_UPSTREAM_ERROR`, `DETAIL_CONFIGURATION_ERROR`, and
  `PATENT_NOT_FOUND` with a non-fatal unavailable/retry state.

Similar Patent UI:

- Calls `getSimilarPatents(patentId)` after the detail view has a target patent.
- Shows empty state when `results.length === 0`.
- Treats `SIMILAR_UPSTREAM_ERROR` as a partial-feature failure, not a full detail page failure.

Summary UI:

- Calls `summarizePatent(patentId, userQuery)` on explicit user action.
- Shows loading because live KIPRIS/Gemini calls can take several seconds.
- Renders `core_summary`, `business_application`, `key_tags`, and `disclaimer`.
- Treats `is_cached=true` as normal success.

Chat UI:

- Calls `chatAboutPatent(patentId, input)` on explicit user message submit.
- Keeps recent chat history client-side and sends it in `history` on each call.
- Shows loading because live KIPRIS/Gemini calls can take several seconds.
- Renders `answer`, `sources`, and `disclaimer`.
- Treats `is_cached=true` as normal success.

## Error Handling

Use `code` as the primary branch key.

| code | Expected UI |
|---|---|
| `PATENT_NOT_FOUND` | Detail, summary, or chat target not found. Show a friendly unavailable state. |
| `VALIDATION_ERROR` | Ask user to fix the input. |
| `SEARCH_UPSTREAM_ERROR` | Search provider is temporarily unavailable. |
| `DETAIL_UPSTREAM_ERROR` | KIPRIS detail lookup is temporarily unavailable. |
| `SIMILAR_UPSTREAM_ERROR` | Similar patent lookup is temporarily unavailable. |
| `SUMMARY_UPSTREAM_ERROR` | Summary provider is temporarily unavailable. |
| `CHAT_UPSTREAM_ERROR` | Chat provider is temporarily unavailable. |
| `SEARCH_CONFIGURATION_ERROR` | Backend configuration problem. Show service unavailable. |
| `DETAIL_CONFIGURATION_ERROR` | Backend KIPRIS configuration problem. Show service unavailable. |
| `SIMILAR_CONFIGURATION_ERROR` | Backend KIPRIS configuration problem. Show service unavailable. |
| `SUMMARY_CONFIGURATION_ERROR` | Backend configuration problem. Show service unavailable. |
| `CHAT_CONFIGURATION_ERROR` | Backend configuration problem. Show service unavailable. |

Network timeout, failed fetch, and Render cold start may not return JSON. Show a
generic retryable server connection message in those cases.

## Acceptance Criteria

- API base URL can be changed without source code edits.
- Frontend contains no KIPRIS/Gemini/OpenAI key.
- Search works against `https://patent-easy-api.onrender.com`.
- Detail view handles success, loading, `DETAIL_UPSTREAM_ERROR`,
  `DETAIL_CONFIGURATION_ERROR`, and `PATENT_NOT_FOUND`.
- Detail view uses `original_url` or `kipris_url` for 원문보기.
- Similar patent section calls `getSimilarPatents` and handles empty/error states.
- Patent status, legal timeline, cited patents, and family patents use backend fields.
- Summary action works for `10-2023-0147601`.
- Chat action works for `10-2023-0147601` and displays evidence snippets.
- Loading, empty, backend error, and network error states are visible.
- No mock patent dataset is duplicated in the frontend.
