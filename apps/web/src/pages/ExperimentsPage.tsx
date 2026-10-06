import { useState } from "react";
import { ArrowUpRight, Copy, FlaskConical, Plus } from "lucide-react";
import { useRuns } from "../hooks/useRuns";
import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  Metric,
  PageHeader,
  SectionHeader,
  Skeleton,
  Tabs,
} from "../components/ui";
import { BarChart } from "../components/ui/Charts";
type View = "overview" | "configuration" | "queries" | "failures";
export default function ExperimentsPage({
  onEvaluate,
}: {
  onEvaluate: () => void;
}) {
  const { runs, data, loading, error, refresh } = useRuns();
  const [selected, setSelected] = useState("local"),
    [tab, setTab] = useState<View>("overview"),
    [pipeline, setPipeline] = useState(""),
    [newOpen, setNewOpen] = useState(false),
    [neural, setNeural] = useState(false),
    [copied, setCopied] = useState(false);
  const run = data[selected] || Object.values(data)[0],
    summary = runs.find((r) => r.id === selected) || runs[0];
  const rows = (run?.per_question || []).filter(
    (q) =>
      (!pipeline || q.pipeline === pipeline) &&
      (tab !== "failures" ||
        q.recall_at_5 < 1 ||
        q.exact_support_proxy < 1 ||
        q.citation_validity < 1),
  );
  const command = `python scripts/benchmark.py${neural ? " --neural" : ""}`;
  return (
    <div className="page">
      <PageHeader
        title="Experiments"
        description="Reproducible retrieval experiments, measured results and saved configurations."
        actions={
          <Button variant="primary" onClick={() => setNewOpen(true)}>
            <Plus size={15} />
            New experiment
          </Button>
        }
      />
      {error ? (
        <ErrorState message={error} retry={refresh} />
      ) : loading ? (
        <Skeleton rows={9} />
      ) : !runs.length ? (
        <EmptyState
          title="No experiments recorded."
          description="Run the included benchmark runner to create your first measured experiment."
          action={
            <Button onClick={() => setNewOpen(true)}>
              Configure an experiment
            </Button>
          }
        />
      ) : (
        <>
          <SectionHeader
            title="Recorded runs"
            action={<Button onClick={refresh}>Refresh</Button>}
          />
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Experiment</th>
                  <th>Dataset</th>
                  <th>Pipelines</th>
                  <th>Questions</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {runs.map((item) => (
                  <tr
                    key={item.id}
                    className={selected === item.id ? "selected-row" : ""}
                  >
                    <td>
                      <button
                        className="row-title"
                        onClick={() => {
                          setSelected(item.id);
                          setPipeline("");
                        }}
                      >
                        {item.id === "neural"
                          ? "Neural retrieval ablations"
                          : "Local retrieval ablations"}
                      </button>
                    </td>
                    <td>Authored technical notes</td>
                    <td className="mono">{item.pipelines}</td>
                    <td className="mono">{item.questions}</td>
                    <td>
                      {new Date(item.measured_at).toLocaleDateString(
                        undefined,
                        { month: "short", day: "numeric" },
                      )}
                    </td>
                    <td>
                      <Button
                        variant="ghost"
                        aria-label={`Open ${item.id} experiment`}
                        onClick={() => {
                          setSelected(item.id);
                          setPipeline("");
                        }}
                      >
                        <ArrowUpRight size={15} />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {run && (
            <section className="experiment-detail">
              <SectionHeader
                title={
                  summary?.id === "neural"
                    ? "Neural retrieval ablations"
                    : "Local retrieval ablations"
                }
                description={run.profile}
                action={
                  <Button onClick={onEvaluate}>
                    Compare in Evaluations
                    <ArrowUpRight size={14} />
                  </Button>
                }
              />
              <Tabs
                value={tab}
                onChange={setTab}
                items={[
                  { id: "overview", label: "Overview" },
                  { id: "configuration", label: "Configuration" },
                  { id: "queries", label: "Queries" },
                  { id: "failures", label: "Failures" },
                ]}
              />
              {tab === "overview" ? (
                <>
                  <div className="notice">
                    {run.scope}. These are fixture measurements, not production
                    quality claims.
                  </div>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Pipeline</th>
                          <th>Recall@5</th>
                          <th>MRR</th>
                          <th>nDCG@5</th>
                          <th>Cold P95</th>
                          <th>Warm P95</th>
                        </tr>
                      </thead>
                      <tbody>
                        {run.pipelines.map((p) => (
                          <tr key={p.name}>
                            <td>{p.name}</td>
                            <td className="mono">{p.recall_at_5.toFixed(3)}</td>
                            <td className="mono">{p.mrr.toFixed(3)}</td>
                            <td className="mono">{p.ndcg_at_5.toFixed(3)}</td>
                            <td className="mono">
                              {p.cold_latency.p95_ms.toFixed(1)} ms
                            </td>
                            <td className="mono">
                              {p.warm_latency.p95_ms.toFixed(1)} ms
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : tab === "configuration" ? (
                <div className="configuration-grid">
                  <section>
                    <h3>Run parameters</h3>
                    <dl className="technical-list">
                      <div>
                        <dt>Chunk size</dt>
                        <dd>{run.chunk_size} words</dd>
                      </div>
                      <div>
                        <dt>Chunk overlap</dt>
                        <dd>{run.chunk_overlap} words</dd>
                      </div>
                      <div>
                        <dt>Corpus SHA-256</dt>
                        <dd>
                          <code>{run.corpus_sha256}</code>
                        </dd>
                      </div>
                      <div>
                        <dt>Dataset SHA-256</dt>
                        <dd>
                          <code>{run.dataset_sha256}</code>
                        </dd>
                      </div>
                    </dl>
                    <h3>Models</h3>
                    <pre className="code-block">
                      {JSON.stringify(run.model_configuration, null, 2)}
                    </pre>
                  </section>
                  <section>
                    <h3>Experiment configuration</h3>
                    <pre className="code-block">
                      {JSON.stringify(run.experiment_configuration, null, 2)}
                    </pre>
                  </section>
                </div>
              ) : (
                <>
                  <div className="table-toolbar">
                    <select
                      className="field compact-select"
                      aria-label="Pipeline filter"
                      value={pipeline}
                      onChange={(e) => setPipeline(e.target.value)}
                    >
                      <option value="">All pipelines</option>
                      {run.pipelines.map((p) => (
                        <option key={p.name}>{p.name}</option>
                      ))}
                    </select>
                    <span>{rows.length} saved question records</span>
                  </div>
                  {tab === "failures" && (
                    <p className="subtle-note">
                      Flagged when Recall@5, exact-source support or citation
                      validity is below 1. These are evaluation flags, not
                      automatically proven answer errors.
                    </p>
                  )}
                  {rows.length ? (
                    <div className="question-results">
                      {rows.slice(0, 50).map((q, index) => (
                        <details
                          key={`${q.pipeline}-${q.question_id}-${index}`}
                        >
                          <summary>
                            <span>
                              <Badge>{q.question_id}</Badge>
                              <strong>
                                {run.questions?.find(
                                  (item) => item.id === q.question_id,
                                )?.question || q.question_id}
                              </strong>
                              <small>{q.pipeline}</small>
                            </span>
                            <code>R@5 {q.recall_at_5.toFixed(2)}</code>
                          </summary>
                          <div>
                            <div className="query-result-metrics">
                              <span>
                                MRR <code>{q.mrr.toFixed(3)}</code>
                              </span>
                              <span>
                                Token F1{" "}
                                <code>{q.token_f1_proxy.toFixed(3)}</code>
                              </span>
                              <span>
                                Latency{" "}
                                <code>{q.latency_ms.toFixed(2)} ms</code>
                              </span>
                            </div>
                            <p>{q.answer}</p>
                            <small>
                              Ranked documents: {q.ranked_documents.join(", ")}
                            </small>
                          </div>
                        </details>
                      ))}
                    </div>
                  ) : (
                    <EmptyState
                      title="No flagged results in this selection."
                      description="The selected recorded metrics meet the displayed thresholds. This does not establish semantic answer correctness."
                    />
                  )}
                  {rows.length > 50 && (
                    <p className="subtle-note">
                      Showing 50 records. Choose a pipeline to narrow the
                      results.
                    </p>
                  )}
                </>
              )}
            </section>
          )}
        </>
      )}
      {newOpen && (
        <Dialog title="New experiment" onClose={() => setNewOpen(false)}>
          <p className="muted">
            The existing benchmark runner executes from your project terminal.
            This workspace reads its recorded results.
          </p>
          <label className="field-label" htmlFor="experiment-profile">
            Experiment profile
          </label>
          <select
            id="experiment-profile"
            className="field"
            value={neural ? "neural" : "local"}
            onChange={(e) => setNeural(e.target.value === "neural")}
          >
            <option value="local">Local · LSA and lexical reranking</option>
            <option value="neural">
              Neural · pinned MiniLM and cross-encoder
            </option>
          </select>
          <pre className="code-block">{command}</pre>
          <p className="subtle-note">
            Includes all ten configured ablations. The neural profile requires
            the optional neural dependencies and model weights. Refresh recorded
            runs after completion.
          </p>
          <div className="dialog-actions">
            <Button onClick={() => setNewOpen(false)}>Close</Button>
            <Button
              variant="primary"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(command);
                  setCopied(true);
                } catch {
                  setCopied(false);
                }
              }}
            >
              <Copy size={14} />
              {copied ? "Copied" : "Copy command"}
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
