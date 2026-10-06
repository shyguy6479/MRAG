import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Search, SlidersHorizontal } from "lucide-react";
import { api, type SearchResult } from "../api";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  PageHeader,
  Score,
  Skeleton,
} from "../components/ui";
import { SourceSelector } from "../components/research/ResearchComposer";
export default function SearchPage({
  initialQuery = "",
  onDocument,
}: {
  initialQuery?: string;
  onDocument: (id: string) => void;
}) {
  const [query, setQuery] = useState(initialQuery),
    [strategy, setStrategy] = useState("hybrid_reranked"),
    [topK, setTopK] = useState(5),
    [sources, setSources] = useState<string[]>([]),
    [section, setSection] = useState(""),
    [data, setData] = useState<SearchResult | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => setQuery(initialQuery), [initialQuery]);
  async function run() {
    if (!query.trim() || busy) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    try {
      setData(
        await api<SearchResult>("/search", {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({
            question: query,
            strategy,
            top_k: topK,
            filters: { document_ids: sources, section: section || null },
          }),
        }),
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page search-page">
      <PageHeader
        title="Search Explorer"
        description="Inspect retrieval before generation. Compare dense, sparse, fusion and reranker scores."
        actions={<Badge>Retrieval only · no LLM generation</Badge>}
      />
      <form
        className="search-workbench"
        onSubmit={(e) => {
          e.preventDefault();
          run();
        }}
      >
        <div className="search-query">
          <Search size={19} />
          <input
            aria-label="Search query"
            placeholder="How does speculative decoding reduce latency?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button
            type="submit"
            variant="primary"
            disabled={busy || !query.trim()}
          >
            {busy ? "Searching…" : "Search"}
          </Button>
        </div>
        <div className="search-controls">
          <label>
            Retrieval mode
            <select
              className="field"
              aria-label="Retrieval mode"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            >
              <option value="dense">Dense</option>
              <option value="sparse">BM25</option>
              <option value="hybrid">Hybrid · RRF</option>
              <option value="hybrid_reranked">Hybrid + Rerank</option>
            </select>
          </label>
          <label>
            Top K
            <select
              className="field"
              aria-label="Top K"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            >
              {[5, 10, 15, 20].map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
          </label>
          <div>
            <span>Documents</span>
            <SourceSelector selected={sources} onChange={setSources} />
          </div>
          <label className="section-filter">
            Section
            <input
              className="input"
              aria-label="Section filter"
              placeholder="Any section"
              value={section}
              onChange={(e) => setSection(e.target.value)}
            />
          </label>
        </div>
      </form>
      {error && <ErrorState message={error} retry={run} />}
      {busy ? (
        <div className="search-loading">
          <Skeleton rows={9} />
        </div>
      ) : data ? (
        <>
          <div className="result-summary">
            <strong>{data.hits.length} passages</strong>
            <span>
              {data.considered} candidates · {data.latency_ms.toFixed(1)} ms
            </span>
            <Badge>{data.cache_hit ? "Cache hit" : "Cache miss"}</Badge>
            <span className="result-profile">
              {data.dense_backend} · {data.reranker}
            </span>
          </div>
          {data.warnings.map((w) => (
            <p className="notice warning-notice" key={w}>
              {w}
            </p>
          ))}
          {data.hits.length ? (
            <div className="retrieval-results">
              {data.hits.map((hit, index) => (
                <article
                  className="retrieval-result"
                  key={hit.evidence.chunk_id}
                >
                  <span className="result-rank">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <header>
                      <button
                        onClick={() => onDocument(hit.evidence.document_id)}
                      >
                        {hit.evidence.title}
                        <ArrowUpRight size={15} />
                      </button>
                      <span>
                        {hit.evidence.section}
                        {hit.evidence.page
                          ? ` · Page ${hit.evidence.page}`
                          : ""}
                      </span>
                    </header>
                    <p>{hit.evidence.text}</p>
                    <div className="score-breakdown">
                      <Score label="Dense" value={hit.dense_score} />
                      <Score label="BM25" value={hit.sparse_score} />
                      <Score
                        label="RRF"
                        value={
                          data.strategy.startsWith("hybrid") ? hit.score : null
                        }
                      />
                      <Score label="Reranker" value={hit.rerank_score} />
                    </div>
                    <details className="result-details">
                      <summary>Chunk metadata</summary>
                      <dl>
                        <dt>Chunk ID</dt>
                        <dd>
                          <code>{hit.evidence.chunk_id}</code>
                        </dd>
                        <dt>Source</dt>
                        <dd>{hit.evidence.source}</dd>
                      </dl>
                    </details>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No passages found."
              description="Try another question or broaden your document and section filters."
            />
          )}
          <p className="subtle-note">
            Scores come directly from the retrieval engine. Different channels
            have different scales; none are probabilities. Corpus revision{" "}
            {data.corpus_revision}.
          </p>
        </>
      ) : (
        <EmptyState
          title="Look inside the retrieval engine."
          description="Run a query to inspect ranked chunks, compare score channels and verify where your evidence comes from."
          action={
            <Button
              onClick={() =>
                setQuery("How does speculative decoding reduce latency?")
              }
            >
              Use an example query
            </Button>
          }
        />
      )}
    </div>
  );
}
