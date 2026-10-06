import {
  ArrowLeft,
  ArrowUpRight,
  FileText,
  PanelRightClose,
  Search,
} from "lucide-react";
import { useState, useEffect } from "react";
import type { Answer, Citation } from "../../api";
import { Badge, Button, Dialog, IconButton, Score, Tabs } from "../ui";
import { AgentTimeline, TraceWaterfall } from "../agents/AgentTimeline";
export type InspectorTab = "sources" | "retrieval" | "agent" | "trace";
export function useNarrow() {
  const [narrow, setNarrow] = useState(
    () => matchMedia("(max-width:1199px)").matches,
  );
  useEffect(() => {
    const media = matchMedia("(max-width:1199px)"),
      listen = () => setNarrow(media.matches);
    media.addEventListener("change", listen);
    return () => media.removeEventListener("change", listen);
  }, []);
  return narrow;
}
export default function EvidenceInspector({
  answer,
  tab,
  onTab,
  source,
  onSource,
  onClose,
  onDocument,
  onSearch,
}: {
  answer: Answer;
  tab: InspectorTab;
  onTab: (tab: InspectorTab) => void;
  source: Citation | null;
  onSource: (source: Citation | null) => void;
  onClose: () => void;
  onDocument: (id: string) => void;
  onSearch: (query: string) => void;
}) {
  const narrow = useNarrow();
  const body = (
    <>
      <Tabs
        value={tab}
        onChange={onTab}
        items={[
          { id: "sources", label: "Sources", count: answer.citations.length },
          { id: "retrieval", label: "Retrieval" },
          { id: "agent", label: "Agent" },
          { id: "trace", label: "Trace" },
        ]}
        label="Evidence inspector"
      />
      <div className="inspector-body">
        {tab === "sources" ? (
          source ? (
            <>
              <button className="text-link" onClick={() => onSource(null)}>
                <ArrowLeft size={14} />
                All sources
              </button>
              <div className="source-detail-heading">
                <Badge tone="accent">Source {source.number}</Badge>
                <h3>{source.title}</h3>
                <p>
                  {source.section}
                  {source.page ? ` · Page ${source.page}` : ""}
                </p>
              </div>
              <blockquote>{source.text}</blockquote>
              <Score
                label="Retrieval ranking score"
                value={source.retrieval_score}
              />
              <dl className="technical-list">
                <div>
                  <dt>Source</dt>
                  <dd>{source.source}</dd>
                </div>
                <div>
                  <dt>Chunk ID</dt>
                  <dd>
                    <code>{source.chunk_id}</code>
                  </dd>
                </div>
              </dl>
              <Button onClick={() => onDocument(source.document_id)}>
                <FileText size={15} />
                Open document & chunks
              </Button>
            </>
          ) : (
            <>
              <div className="inspector-intro">
                <h3>Supporting evidence</h3>
                <p>Stored passages referenced by this answer.</p>
              </div>
              {answer.citations.length ? (
                answer.citations.map((c) => (
                  <article className="evidence-card" key={c.number}>
                    <button
                      className="evidence-card-title"
                      onClick={() => onSource(c)}
                    >
                      <span className="citation-number">{c.number}</span>
                      <strong>{c.title}</strong>
                      <ArrowUpRight size={14} />
                    </button>
                    <p className="metadata">
                      {c.section}
                      {c.page ? ` · Page ${c.page}` : ""}
                    </p>
                    <p className="evidence-excerpt">
                      {c.text.slice(0, 230)}
                      {c.text.length > 230 ? "…" : ""}
                    </p>
                    <Score label="Ranking score" value={c.retrieval_score} />
                    <div className="evidence-actions">
                      <button
                        className="text-link"
                        onClick={() => onDocument(c.document_id)}
                      >
                        Open document
                      </button>
                      <button className="text-link" onClick={() => onSource(c)}>
                        View chunk
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <p className="quiet-empty">
                  No knowledge-base evidence was cited in this response.
                </p>
              )}
            </>
          )
        ) : tab === "retrieval" ? (
          <>
            <div className="inspector-intro">
              <h3>Retrieval inspection</h3>
              <p>The strategy and searches used for this response.</p>
            </div>
            <div className="retrieval-methods">
              {(answer.retrieval.strategy === "dense"
                ? ["Dense"]
                : answer.retrieval.strategy === "sparse"
                  ? ["BM25"]
                  : answer.retrieval.strategy === "hybrid"
                    ? ["Dense", "BM25", "RRF"]
                    : ["Dense", "BM25", "RRF", "Reranker"]
              ).map((item) => (
                <Badge key={item} tone="accent">
                  {item}
                </Badge>
              ))}
            </div>
            <dl className="technical-list">
              <div>
                <dt>Strategy</dt>
                <dd>{answer.retrieval.strategy}</dd>
              </div>
              <div>
                <dt>Dense backend</dt>
                <dd>{answer.retrieval.dense_backend}</dd>
              </div>
              <div>
                <dt>Reranker</dt>
                <dd>{answer.retrieval.reranker}</dd>
              </div>
              <div>
                <dt>Candidates considered</dt>
                <dd className="mono">{answer.retrieval.chunks_considered}</dd>
              </div>
              <div>
                <dt>Context chunks</dt>
                <dd className="mono">{answer.retrieval.chunks_used}</dd>
              </div>
              <div>
                <dt>Corpus revision</dt>
                <dd className="mono">{answer.retrieval.corpus_revision}</dd>
              </div>
              <div>
                <dt>Retrieval cache</dt>
                <dd>{answer.retrieval.cache_hit ? "Hit" : "Miss"}</dd>
              </div>
            </dl>
            <h4 className="small-heading">Search queries</h4>
            <ol className="query-list">
              {answer.retrieval.queries.map((query, index) => (
                <li key={index}>{query}</li>
              ))}
            </ol>
            <Button onClick={() => onSearch(answer.retrieval.queries[0] || "")}>
              <Search size={14} />
              Explore current index
            </Button>
            <p className="subtle-note">
              Per-channel candidate scores are unavailable in saved answers.
              Search Explorer runs a new scored retrieval against the current
              index.
            </p>
          </>
        ) : tab === "agent" ? (
          <>
            <div className="inspector-intro">
              <h3>Agent execution</h3>
              <p>Bounded actions and tool activity.</p>
            </div>
            <AgentTimeline answer={answer} />
          </>
        ) : (
          <>
            <div className="inspector-intro">
              <h3>Request trace</h3>
              <p>Measured stage durations and reported usage.</p>
            </div>
            <TraceWaterfall answer={answer} />
          </>
        )}
      </div>
    </>
  );
  return narrow ? (
    <Dialog title="Evidence inspector" onClose={onClose} sheet>
      {body}
    </Dialog>
  ) : (
    <aside className="evidence-inspector">
      <header>
        <h2>Evidence inspector</h2>
        <IconButton label="Collapse evidence inspector" onClick={onClose}>
          <PanelRightClose size={17} />
        </IconButton>
      </header>
      {body}
    </aside>
  );
}
