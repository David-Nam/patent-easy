# PatentEasy 프론트엔드 백엔드 연동 가이드

이 문서는 프론트엔드 개발자가 PatentEasy 백엔드 서버를 연결할 때 필요한 설정,
API 계약, 구현 주의사항을 정리합니다. 프론트엔드 담당자에게 공유할 기준 문서로
사용하고, Codex나 Claude Code 같은 AI 개발 도구에는 `docs/frontend_ai_integration.md`를
함께 전달하세요.

## 현재 기준

| 항목 | 값 |
|---|---|
| 배포 백엔드 URL | `https://patent-easy-api.onrender.com` |
| API 문서 | `https://patent-easy-api.onrender.com/docs` |
| OpenAPI JSON | `https://patent-easy-api.onrender.com/openapi.json` |
| 로컬 개발 URL | `http://127.0.0.1:8000` |
| 인증 방식 | 프론트엔드용 API key 없음 |

프론트엔드는 KIPRIS, Gemini, OpenAI key를 절대 보관하거나 요청에 포함하지 않습니다.
외부 API key는 모두 백엔드 Render 환경변수에만 존재합니다.

## 구현 상태

현재 코드 기준 서버 기능은 다음과 같습니다.

| 기능 | 현재 동작 |
|---|---|
| 검색 | 실제 Gemini Query Builder와 KIPRIS 검색 API를 호출합니다. |
| 상세 조회 | 실제 KIPRIS 서지 상세/청구항 API를 호출합니다. |
| 요약 | 실제 KIPRIS 서지/청구항 조회 후 Gemini로 요약합니다. |
| 챗봇 | 실제 KIPRIS 서지/청구항 조회 후 Gemini로 단일 특허 Q&A 답변을 생성합니다. |

시연용으로 바로 동작 확인 가능한 ID는 다음과 같습니다.

| 용도 | ID |
|---|---|
| 실제 KIPRIS 상세 조회 | `10-2023-0147601` |
| 실제 KIPRIS/Gemini 요약 | `10-2023-0147601` |
| 실제 KIPRIS/Gemini 챗봇 | `10-2023-0147601` |

## 프론트엔드 환경변수

Next.js 기준 `.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=https://patent-easy-api.onrender.com
```

Vite 기준 `.env.local`:

```env
VITE_API_BASE_URL=https://patent-easy-api.onrender.com
```

로컬 백엔드를 직접 띄워서 테스트할 때만 값을 바꿉니다.

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

프론트엔드 배포 URL이 생기면 백엔드 Render 환경변수 `CORS_ORIGINS`에 해당 origin을
추가해야 브라우저 호출이 정상 동작합니다. 예를 들어 프론트엔드가
`https://patent-easy.vercel.app`에 배포되면 백엔드의 `CORS_ORIGINS`에 그 값을
포함해야 합니다.

## 빠른 연결 확인

브라우저나 터미널에서 다음 URL이 열리면 백엔드가 살아 있는 상태입니다.

```text
https://patent-easy-api.onrender.com/health
https://patent-easy-api.onrender.com/ready
https://patent-easy-api.onrender.com/docs
```

Render Free instance는 일정 시간 요청이 없으면 sleep 상태가 될 수 있습니다. 첫 요청은
수십 초까지 느릴 수 있으므로 프론트엔드는 loading 상태를 반드시 보여줘야 합니다.

## API 요약

| Method | Path | 용도 | 프론트엔드 사용 위치 |
|---|---|---|---|
| `GET` | `/health` | 서버 생존 확인 | 개발/디버깅 |
| `GET` | `/ready` | cache, KIPRIS, LLM 준비 상태 확인 | 개발/디버깅 |
| `POST` | `/api/v1/search` | 자연어 특허 검색 | 검색 화면 |
| `GET` | `/api/v1/patents/{patent_id}` | 특허 상세 조회 | 상세 화면 |
| `POST` | `/api/v1/patents/{patent_id}/summary` | 특허 요약 생성 | 요약 화면 |
| `POST` | `/api/v1/patents/{patent_id}/chat` | 단일 특허 Q&A 챗봇 | 상세/요약 화면의 질문 패널 |

필드의 최종 기계 판독 명세는 `/openapi.json`이 기준입니다. 사람이 읽는 상세 설명은
`docs/api_reference.md`를 참고하세요.

## TypeScript 타입

프론트엔드에서는 아래 타입을 기준으로 API client를 만들면 됩니다.

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

## API Client 예시

아래 코드는 Next.js 기준입니다. Vite에서는 환경변수 이름만 `VITE_API_BASE_URL`로
바꾸면 됩니다.

```ts
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://patent-easy-api.onrender.com";

export class PatentEasyApiError extends Error {
  status: number;
  code: string;
  details?: Record<string, unknown> | null;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "PatentEasyApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  const payload = await response.json();

  if (!response.ok) {
    throw new PatentEasyApiError(response.status, payload as ApiErrorBody);
  }

  return payload as T;
}

export async function searchPatents(input: SearchRequest): Promise<SearchResponse> {
  return requestJson<SearchResponse>("/api/v1/search", {
    method: "POST",
    body: JSON.stringify({
      filters: {},
      page: 1,
      page_size: 10,
      ...input,
    }),
  });
}

export async function getPatentDetail(patentId: string): Promise<PatentDetail> {
  return requestJson<PatentDetail>(`/api/v1/patents/${encodeURIComponent(patentId)}`);
}

export async function getSimilarPatents(
  patentId: string,
  limit = 5
): Promise<SimilarPatentsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return requestJson<SimilarPatentsResponse>(
    `/api/v1/patents/${encodeURIComponent(patentId)}/similar?${params.toString()}`
  );
}

export async function summarizePatent(
  patentId: string,
  userQuery?: string
): Promise<SummaryResponse> {
  return requestJson<SummaryResponse>(
    `/api/v1/patents/${encodeURIComponent(patentId)}/summary`,
    {
      method: "POST",
      body: JSON.stringify({ user_query: userQuery ?? null }),
    }
  );
}

export async function chatAboutPatent(
  patentId: string,
  input: ChatRequest
): Promise<ChatResponse> {
  return requestJson<ChatResponse>(
    `/api/v1/patents/${encodeURIComponent(patentId)}/chat`,
    {
      method: "POST",
      body: JSON.stringify({
        user_query: null,
        history: [],
        ...input,
      }),
    }
  );
}
```

## 요청 예시

검색:

```bash
curl -s -X POST https://patent-easy-api.onrender.com/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"전기차 배터리 열관리 시스템","page":1,"page_size":3}'
```

상세:

```bash
curl -s https://patent-easy-api.onrender.com/api/v1/patents/10-2023-0147601
```

유사특허:

```bash
curl -s 'https://patent-easy-api.onrender.com/api/v1/patents/10-2023-0147601/similar?limit=5'
```

요약:

```bash
curl -s -X POST https://patent-easy-api.onrender.com/api/v1/patents/10-2023-0147601/summary \
  -H "Content-Type: application/json" \
  -d '{"user_query":"전기차 배터리 열관리 기능"}'
```

챗봇:

```bash
curl -s -X POST https://patent-easy-api.onrender.com/api/v1/patents/10-2023-0147601/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"이 특허는 전기차 배터리 열관리 기능과 관련이 있나요?","user_query":"전기차 배터리 열관리 기능","history":[]}'
```

## 화면 구현 권장사항

검색 화면:

- 사용자가 자연어 아이디어를 입력하면 `/api/v1/search`를 호출합니다.
- `results`가 비어 있으면 빈 상태를 보여줍니다.
- `extracted.keywords`, `extracted.ipc_codes`는 검색 의도를 설명하는 보조 정보로 표시할 수 있습니다.
- `status`, `registration_number`, `original_url`, `thumbnail_url`을 사용할 수 있습니다.
- `relevance_score`와 `similarity_score`는 0부터 100까지의 정수입니다.

상세 화면:

- 상세 조회는 실제 KIPRIS 서지 상세/청구항 API를 호출하므로 loading 상태가 필요합니다.
- `DETAIL_UPSTREAM_ERROR`, `DETAIL_CONFIGURATION_ERROR`, `PATENT_NOT_FOUND`를 깨진 화면이 아니라 재시도/안내 상태로 처리합니다.
- `claims`는 번호와 본문을 함께 보여줍니다.
- 원문보기는 `original_url`을 우선 사용하고, 없으면 `kipris_url`을 사용합니다.
- 특허출원 타임라인은 `legal_events`를 사용합니다.
- 특허 네트워크는 `cited_patents`, `cited_by_patents`, `family_patents`를 사용합니다.

유사특허 영역:

- 상세 화면의 기준 특허가 정해진 뒤 `/api/v1/patents/{patent_id}/similar`를 호출합니다.
- `results`가 비어 있으면 유사특허 없음 상태를 보여줍니다.
- `SIMILAR_UPSTREAM_ERROR`는 상세 화면 전체 실패가 아니라 유사특허 영역의 부분 실패로 처리합니다.

요약 화면:

- `/api/v1/patents/{patent_id}/summary`는 실제 KIPRIS/Gemini 호출이므로 검색보다 느릴 수 있습니다.
- `is_cached=true`도 정상 응답입니다.
- `disclaimer`는 사용자에게 그대로 노출하는 것을 권장합니다.

챗봇 패널:

- `/api/v1/patents/{patent_id}/chat`은 실제 KIPRIS/Gemini 호출이므로 loading 상태가 필요합니다.
- 서버는 대화 세션을 저장하지 않으므로 프론트엔드가 최근 `history`를 보관해 매 요청에 포함합니다.
- `sources`의 `snippet`은 답변 근거로 함께 보여주는 것을 권장합니다.
- `is_cached=true`도 정상 응답입니다.

## 에러 처리 기준

오류 응답은 항상 아래 형태를 목표로 합니다.

```json
{
  "code": "SEARCH_UPSTREAM_ERROR",
  "message": "외부 서비스 호출 중 오류가 발생했습니다.",
  "details": {
    "source": "kipris"
  }
}
```

대표 코드:

| HTTP Status | code | 프론트엔드 처리 |
|---:|---|---|
| `404` | `PATENT_NOT_FOUND` | 상세/요약 대상이 없다는 안내 |
| `422` | `VALIDATION_ERROR` | 입력값 수정 요청 |
| `502` | `SEARCH_UPSTREAM_ERROR` | KIPRIS 또는 LLM 일시 오류 안내 |
| `502` | `DETAIL_UPSTREAM_ERROR` | KIPRIS 상세 조회 일시 오류 안내 |
| `502` | `SIMILAR_UPSTREAM_ERROR` | 유사특허 조회 일시 오류 안내 |
| `502` | `SUMMARY_UPSTREAM_ERROR` | 요약 생성 일시 오류 안내 |
| `502` | `CHAT_UPSTREAM_ERROR` | 챗봇 답변 생성 일시 오류 안내 |
| `503` | `SEARCH_CONFIGURATION_ERROR` | 백엔드 설정 문제 안내 |
| `503` | `DETAIL_CONFIGURATION_ERROR` | 백엔드 KIPRIS 설정 문제 안내 |
| `503` | `SIMILAR_CONFIGURATION_ERROR` | 백엔드 KIPRIS 설정 문제 안내 |
| `503` | `SUMMARY_CONFIGURATION_ERROR` | 백엔드 설정 문제 안내 |
| `503` | `CHAT_CONFIGURATION_ERROR` | 백엔드 설정 문제 안내 |

네트워크 실패, timeout, Render cold start는 JSON 오류 응답이 아닐 수 있습니다.
이 경우에는 “서버 응답이 지연되고 있습니다. 잠시 후 다시 시도하세요.”처럼 처리합니다.

## AI 도구에 전달할 요청문

프론트엔드 repo에서 Codex나 Claude Code를 사용할 때는 아래처럼 요청하세요.

```text
docs/frontend_backend_integration_guide.md와 docs/frontend_ai_integration.md를 읽고
PatentEasy 백엔드 API client를 구현해줘.

NEXT_PUBLIC_API_BASE_URL=https://patent-easy-api.onrender.com 을 기준으로
검색, 상세, 요약, 챗봇 함수를 만들고 기존 화면의 loading/error/empty 상태까지 연결해줘.
유사특허 함수 getSimilarPatents도 만들고 상세 화면의 유사특허 영역에 연결해줘.
KIPRIS_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY는 프론트엔드에 추가하지 마.
상세 조회는 실제 KIPRIS 호출이므로 DETAIL_UPSTREAM_ERROR, DETAIL_CONFIGURATION_ERROR, PATENT_NOT_FOUND를 안내 상태로 처리해줘.
원문보기는 detail.original_url을 우선 사용하고 없으면 kipris_url을 사용해줘.
특허상태는 status/application_status를 사용하고, 타임라인은 legal_events를 사용해줘.
챗봇은 프론트엔드가 최근 history를 보관해 요청마다 함께 보내고, sources snippet을 답변 근거로 보여줘.
```

## 프론트엔드 완료 체크리스트

- `.env.local`에 API base URL이 설정되어 있다.
- 검색 화면이 `/api/v1/search`를 호출한다.
- 검색 loading, empty, error 상태가 보인다.
- 상세 조회 loading, `DETAIL_UPSTREAM_ERROR`, `DETAIL_CONFIGURATION_ERROR`, `PATENT_NOT_FOUND` 상태를 처리한다.
- 원문보기 버튼이 `original_url` 또는 `kipris_url`로 이동한다.
- 상세 화면에 `status`, `registration_number`, `legal_events`가 표시된다.
- 유사특허 영역이 `/similar`를 호출하고 empty/error 상태를 처리한다.
- 특허 네트워크가 `cited_patents`, `cited_by_patents`, `family_patents`를 사용한다.
- 요약 화면이 `core_summary`, `business_application`, `key_tags`, `disclaimer`를 표시한다.
- 챗봇 패널이 `answer`, `sources`, `disclaimer`를 표시하고 최근 history를 요청에 포함한다.
- 프론트엔드 코드나 환경변수에 KIPRIS/Gemini/OpenAI key가 없다.
- 배포 프론트엔드 origin이 백엔드 `CORS_ORIGINS`에 등록되어 있다.
