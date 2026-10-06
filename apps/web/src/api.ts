export type DocumentInfo = {
  id: string;
  title: string;
  source: string;
  format: string;
  status: string;
  chunk_count: number;
  chunking: string;
  tags: string[];
  created_at: string;
  error: string | null;
};
export type Evidence = {
  chunk_id: string;
  document_id: string;
  title: string;
  source: string;
  section: string;
  page: number | null;
  text: string;
  ordinal: number;
  created_at: string;
  tags: string[];
};
export type DocumentDetail = { document: DocumentInfo; chunks: Evidence[] };
export type Citation = {
  number: number;
  document_id: string;
  chunk_id: string;
  title: string;
  source: string;
  section: string;
  page: number | null;
  text: string;
  retrieval_score: number;
};
export type TraceStep = {
  step: number;
  action: string;
  detail: string;
  duration_ms: number;
  evidence_ids: string[];
};
export type Answer = {
  id: string;
  conversation_id: string | null;
  answer: string;
  citations: Citation[];
  confidence: number;
  confidence_kind: string;
  latency_ms: number;
  generator: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  warnings: string[];
  trace: TraceStep[];
  claims: {
    text: string;
    status: string;
    score: number;
    citation_numbers: number[];
  }[];
  retrieval: {
    strategy: string;
    chunks_considered: number;
    chunks_used: number;
    queries: string[];
    corpus_revision: number;
    cache_hit: boolean;
    dense_backend: string;
    reranker: string;
  };
};
export type Turn = { question: string; response: Answer };
export type Recent = {
  id: string;
  title: string;
  updated_at?: string;
  sources?: number;
  turns?: number;
  response?: Answer;
};
export type SystemInfo = {
  documents: number;
  ready_documents: number;
  chunks: number;
  corpus_revision: number;
  profile: string;
  dense_backend: string;
  vector_backend: string;
  reranker: string;
  generator: string;
  embedding_model: string;
  cache_hits: number;
  cache_misses: number;
  max_agent_steps: number;
  query_timeout_seconds: number;
  context_budget_bytes: number;
  jobs: Record<string, number>;
};
export type Latency = { p50_ms: number; p95_ms: number; p99_ms: number };
export type Pipeline = {
  name: string;
  configuration: Record<string, unknown>;
  recall_at_5: number;
  precision_at_5: number;
  mrr: number;
  ndcg_at_5: number;
  token_f1_proxy: number;
  exact_support_proxy: number;
  citation_validity: number;
  context_relevance: number;
  answer_relevance_proxy: number;
  tokens: number;
  cost_usd: number;
  latency: Latency;
  cold_latency: Latency;
  warm_latency: Latency;
  cache_hit_rate: number;
  queries_measured: number;
  ingestion_ms: number;
  index_build_ms: number;
  chunks: number;
};
export type QuestionResult = {
  pipeline: string;
  question_id: string;
  recall_at_5: number;
  precision_at_5: number;
  mrr: number;
  ndcg_at_5: number;
  token_f1_proxy: number;
  exact_support_proxy: number;
  citation_validity: number;
  context_relevance: number;
  answer_relevance_proxy: number;
  latency_ms: number;
  ranked_documents: string[];
  answer: string;
  tokens: number;
  cost_usd: number;
  chunks_used: number;
};
export type EvaluationRun = {
  questions?: {
    id: string;
    question: string;
    reference: string;
    relevant: string[];
  }[];
  measured_at: string;
  profile: string;
  scope: string;
  limitations: string[];
  corpus_sha256: string;
  dataset_sha256: string;
  pipelines: Pipeline[];
  per_question: QuestionResult[];
  model_configuration: Record<string, unknown>;
  experiment_configuration: unknown;
  chunk_size: number;
  chunk_overlap: number;
};
export type Evaluation = {
  available: boolean;
  message?: string;
  results?: EvaluationRun;
};
export type RunSummary = {
  id: string;
  measured_at: string;
  profile: string;
  pipelines: number;
  questions: number;
};
export type SearchHit = {
  evidence: Evidence;
  score: number;
  dense_score: number | null;
  sparse_score: number | null;
  rerank_score: number | null;
};
export type SearchResult = {
  query: string;
  strategy: string;
  hits: SearchHit[];
  considered: number;
  cache_hit: boolean;
  warnings: string[];
  latency_ms: number;
  corpus_revision: number;
  dense_backend: string;
  reranker: string;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public requestId?: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const key = sessionStorage.getItem("atlas-api-key");
  if (key) headers.set("X-API-Key", key);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...options, headers });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError(
      "MRAG could not reach the API. Check the connection and try again.",
      0,
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail =
      body.error?.message ||
      (Array.isArray(body.detail)
        ? body.detail.map((item: { msg: string }) => item.msg).join("; ")
        : body.detail);
    throw new ApiError(
      response.status === 401
        ? "Workspace key required. Update your API connection in Settings."
        : detail || "The service could not complete this request.",
      response.status,
      response.headers.get("X-Request-ID") || undefined,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.headers.get("content-type")?.includes("application/json")
    ? response.json()
    : (response.text() as Promise<T>);
}
