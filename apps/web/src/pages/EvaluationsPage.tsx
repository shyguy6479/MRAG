import { useState } from "react";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { useRuns } from "../hooks/useRuns";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Metric,
  PageHeader,
  SectionHeader,
  Skeleton,
} from "../components/ui";
import { BarChart } from "../components/ui/Charts";
export default function EvaluationsPage({
  onExperiments,
}: {
  onExperiments: () => void;
}) {
  const { runs, data, loading, error, refresh } = useRuns();
  const [baseRun, setBaseRun] = useState("local"),
    [compareRun, setCompareRun] = useState("neural"),
    [baseIndex, setBaseIndex] = useState(0),
    [compareIndex, setCompareIndex] = useState(3);
  const aRun = data[baseRun] || Object.values(data)[0],
    bRun = data[compareRun] || aRun,
    a = aRun?.pipelines[baseIndex] || aRun?.pipelines[0],
    b = bRun?.pipelines[compareIndex] || bRun?.pipelines[0];
  const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
  return (
    <div className="page evaluations-page">
      <PageHeader
        title="Evaluations"
        description="Compare retrieval quality, evidence support and latency from recorded runs."
        actions={<Button onClick={refresh}>Refresh results</Button>}
      />
      {error ? (
        <ErrorState message={error} retry={refresh} />
      ) : loading ? (
        <Skeleton rows={10} />
      ) : !a || !b ? (
        <EmptyState
          title="No evaluation runs available."
          description="Record an experiment to compare measured retrieval and generation metrics."
          action={<Button onClick={onExperiments}>Open experiments</Button>}
        />
      ) : (
        <>
          <div className="comparison-picker">
            {[
              {
                label: "Baseline",
                id: baseRun,
                run: aRun,
                index: baseIndex,
                setRun: setBaseRun,
                setIndex: setBaseIndex,
              },
              {
                label: "Compare against",
                id: compareRun,
                run: bRun,
                index: compareIndex,
                setRun: setCompareRun,
                setIndex: setCompareIndex,
              },
            ].map((item, index) => (
              <section key={item.label}>
                <span className="field-label">{item.label}</span>
                <div>
                  <select
                    className="field"
                    aria-label={`${item.label} run`}
                    value={data[item.id] ? item.id : runs[0]?.id}
                    onChange={(e) => {
                      item.setRun(e.target.value);
                      item.setIndex(index ? 3 : 0);
                    }}
                  >
                    {runs.map((run) => (
                      <option key={run.id} value={run.id}>
                        {run.id === "neural" ? "Neural run" : "Local run"}
                      </option>
                    ))}
                  </select>
                  <select
                    className="field"
                    aria-label={`${item.label} pipeline`}
                    value={item.index}
                    onChange={(e) => item.setIndex(Number(e.target.value))}
                  >
                    {item.run?.pipelines.map((p, i) => (
                      <option key={p.name} value={i}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
              </section>
            ))}
          </div>
          <div className="notice">
            Document-level Recall@5 and named generation proxies on 8 authored
            notes / 12 questions. Recall@10 and semantic faithfulness were not
            measured.
          </div>
          <div className="evaluation-metrics">
            {[
              {
                label: "Recall@5",
                value: pct(b.recall_at_5),
                delta: `${((b.recall_at_5 - a.recall_at_5) * 100).toFixed(1)} pp`,
              },
              {
                label: "MRR",
                value: b.mrr.toFixed(3),
                delta: (b.mrr - a.mrr).toFixed(3),
              },
              {
                label: "nDCG@5",
                value: b.ndcg_at_5.toFixed(3),
                delta: (b.ndcg_at_5 - a.ndcg_at_5).toFixed(3),
              },
              {
                label: "Exact support proxy",
                value: pct(b.exact_support_proxy),
                delta: `${((b.exact_support_proxy - a.exact_support_proxy) * 100).toFixed(1)} pp`,
              },
              {
                label: "Citation validity",
                value: pct(b.citation_validity),
                delta: `${((b.citation_validity - a.citation_validity) * 100).toFixed(1)} pp`,
              },
              {
                label: "Cold P95",
                value: `${b.cold_latency.p95_ms.toFixed(1)} ms`,
                delta: `${(b.cold_latency.p95_ms - a.cold_latency.p95_ms).toFixed(1)} ms`,
              },
            ].map((metric) => (
              <Metric
                key={metric.label}
                label={metric.label}
                value={metric.value}
                note={`${metric.delta.startsWith("-") ? "" : "+"}${metric.delta} vs baseline`}
              />
            ))}
          </div>
          <div className="chart-grid">
            <BarChart
              title="Retrieval quality"
              description="Document-level scores · higher is better"
              max={100}
              legend={[a.name, b.name]}
              data={[
                {
                  label: "Recall@5",
                  value: a.recall_at_5 * 100,
                  comparison: b.recall_at_5 * 100,
                },
                { label: "MRR", value: a.mrr * 100, comparison: b.mrr * 100 },
                {
                  label: "nDCG@5",
                  value: a.ndcg_at_5 * 100,
                  comparison: b.ndcg_at_5 * 100,
                },
              ]}
            />
            <BarChart
              title="Generation proxies"
              description="Lexical / source-match metrics · not semantic correctness"
              max={100}
              legend={[a.name, b.name]}
              data={[
                {
                  label: "Exact support",
                  value: a.exact_support_proxy * 100,
                  comparison: b.exact_support_proxy * 100,
                },
                {
                  label: "Citation validity",
                  value: a.citation_validity * 100,
                  comparison: b.citation_validity * 100,
                },
                {
                  label: "Token F1",
                  value: a.token_f1_proxy * 100,
                  comparison: b.token_f1_proxy * 100,
                },
              ]}
            />
            <BarChart
              title="Cold latency profile"
              description="First-pass in-process latency · model loading excluded"
              unit="ms"
              legend={[a.name, b.name]}
              data={[
                {
                  label: "P50",
                  value: a.cold_latency.p50_ms,
                  comparison: b.cold_latency.p50_ms,
                },
                {
                  label: "P95",
                  value: a.cold_latency.p95_ms,
                  comparison: b.cold_latency.p95_ms,
                },
                {
                  label: "P99",
                  value: a.cold_latency.p99_ms,
                  comparison: b.cold_latency.p99_ms,
                },
              ]}
            />
            <BarChart
              title="Warm latency profile"
              description="Repeated queries · caches may be populated"
              unit="ms"
              legend={[a.name, b.name]}
              data={[
                {
                  label: "P50",
                  value: a.warm_latency.p50_ms,
                  comparison: b.warm_latency.p50_ms,
                },
                {
                  label: "P95",
                  value: a.warm_latency.p95_ms,
                  comparison: b.warm_latency.p95_ms,
                },
                {
                  label: "P99",
                  value: a.warm_latency.p99_ms,
                  comparison: b.warm_latency.p99_ms,
                },
              ]}
            />
          </div>
          <div className="evaluation-bottom">
            <section>
              <SectionHeader title="Usage & measurement" />
              <dl className="technical-list">
                <div>
                  <dt>Mean LLM tokens / query</dt>
                  <dd>{b.tokens.toFixed(1)}</dd>
                </div>
                <div>
                  <dt>Mean reported LLM cost / query</dt>
                  <dd>${b.cost_usd.toFixed(6)}</dd>
                </div>
                <div>
                  <dt>Queries measured</dt>
                  <dd>{b.queries_measured}</dd>
                </div>
                <div>
                  <dt>Recorded</dt>
                  <dd>{new Date(bRun.measured_at).toLocaleString()}</dd>
                </div>
              </dl>
              <p className="subtle-note">
                Extractive runs use zero LLM tokens. This does not mean compute
                is free.
              </p>
            </section>
            <section>
              <SectionHeader
                title="Failure analysis"
                action={
                  <Button onClick={onExperiments}>
                    Inspect questions
                    <ArrowUpRight size={14} />
                  </Button>
                }
              />
              <p className="muted">
                {
                  bRun.per_question.filter(
                    (q) =>
                      q.pipeline === b.name &&
                      (q.recall_at_5 < 1 ||
                        q.exact_support_proxy < 1 ||
                        q.citation_validity < 1),
                  ).length
                }{" "}
                saved records fall below full recall, exact-source support or
                citation validity for this pipeline.
              </p>
              <p className="subtle-note">
                This small authored fixture does not establish generalization,
                calibrated correctness or production latency objectives.
              </p>
            </section>
          </div>
        </>
      )}
    </div>
  );
}
