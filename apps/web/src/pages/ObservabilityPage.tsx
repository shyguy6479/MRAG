import { useState } from "react";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import type { Recent } from "../api";
import { useMetrics } from "../hooks/useMetrics";
import { useWorkspace } from "../hooks/useWorkspace";
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
} from "../components/ui";
import { BarChart } from "../components/ui/Charts";
import { TraceWaterfall } from "../components/agents/AgentTimeline";
export default function ObservabilityPage() {
  const { metrics, ready, rate, error, updated, refresh } = useMetrics(),
    { recent, refreshRecent, system } = useWorkspace();
  const [trace, setTrace] = useState<Recent | null>(null);
  const records = recent.filter((r) => r.response),
    cacheTotal = (metrics?.cacheHits || 0) + (metrics?.cacheMisses || 0);
  return (
    <div className="page observability-page">
      <PageHeader
        title="Observability"
        description="Process health, measured stage latency and recorded research requests."
        actions={
          <>
            <Badge tone={ready === "ready" ? "success" : "warning"}>
              <i className="status-dot" />
              {ready === "ready"
                ? "System ready"
                : ready === "checking"
                  ? "Checking readiness"
                  : "Readiness unavailable"}
            </Badge>
            <Button
              onClick={() => {
                refresh();
                refreshRecent();
              }}
            >
              <RefreshCw size={14} />
              Refresh
            </Button>
          </>
        }
      />
      {error && <ErrorState message={error} retry={refresh} />}
      {!metrics ? (
        <Skeleton rows={8} />
      ) : (
        <>
          <div className="operations-metrics">
            <Metric
              label="Research requests"
              value={metrics.requests}
              note="Process lifetime"
            />
            <Metric
              label="Requests / min"
              value={rate === null ? "Unavailable" : rate.toFixed(1)}
              note={
                rate === null
                  ? "Waiting for second sample"
                  : "Since previous observation"
              }
            />
            <Metric
              label="P95 request latency"
              value={
                metrics.p95 === null
                  ? "Unavailable"
                  : `${(metrics.p95 * 1000).toFixed(1)} ms`
              }
              note="Histogram estimate · process lifetime"
            />
            <Metric
              label="HTTP error rate"
              value={
                metrics.errorRate === null
                  ? "Unavailable"
                  : `${(metrics.errorRate * 100).toFixed(1)}%`
              }
              note="Research routes · 4xx / 5xx"
            />
            <Metric
              label="Cache hit rate"
              value={
                cacheTotal
                  ? `${((metrics.cacheHits / cacheTotal) * 100).toFixed(1)}%`
                  : "Unavailable"
              }
              note={`${metrics.cacheHits} hits · ${metrics.cacheMisses} misses`}
            />
          </div>
          <div className="operations-grid">
            {metrics.stages.length ? (
              <BarChart
                title="Stage latency"
                description="Mean duration per recorded stage · process lifetime"
                unit="ms"
                data={metrics.stages.map((stage) => ({
                  label: stage.name.replaceAll("_", " "),
                  value: stage.meanMs,
                }))}
              />
            ) : (
              <div className="chart-container">
                <EmptyState
                  title="No stages recorded yet."
                  description="Run a research or search request to populate stage latency."
                />
              </div>
            )}
            <section className="operations-panel">
              <SectionHeader title="Retrieval & tools" />
              <dl className="technical-list">
                <div>
                  <dt>Candidates considered</dt>
                  <dd className="mono">{metrics.candidates}</dd>
                </div>
                <div>
                  <dt>Verification failures</dt>
                  <dd className="mono">{metrics.verificationFailures}</dd>
                </div>
                <div>
                  <dt>Cache requests</dt>
                  <dd className="mono">{cacheTotal}</dd>
                </div>
              </dl>
              <h3>Tool calls</h3>
              {metrics.tools.length ? (
                <div className="tool-counts">
                  {metrics.tools.map((tool) => (
                    <div key={tool.name}>
                      <span>{tool.name.replaceAll("_", " ")}</span>
                      <code>{tool.count}</code>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="subtle-note">
                  No tool calls recorded in this process.
                </p>
              )}
            </section>
          </div>
          <section className="trace-table-section">
            <SectionHeader
              title="Recent research traces"
              description="Latest completed request per saved session. This is a scoped sample, not a distributed trace history."
              action={<Badge>{records.length} saved requests</Badge>}
            />
            {records.length ? (
              <div className="table-scroll">
                <table className="data-table trace-table">
                  <thead>
                    <tr>
                      <th>Research request</th>
                      <th>Duration</th>
                      <th>Generator</th>
                      <th>LLM tokens</th>
                      <th>Reported cost</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {records.slice(0, 20).map((row) => (
                      <tr key={row.id}>
                        <td>
                          <button
                            className="row-title"
                            onClick={() => setTrace(row)}
                          >
                            {row.title}
                          </button>
                        </td>
                        <td className="mono">
                          {row.response!.latency_ms.toFixed(0)} ms
                        </td>
                        <td>{row.response!.generator}</td>
                        <td className="mono">
                          {row.response!.input_tokens +
                            row.response!.output_tokens}
                        </td>
                        <td className="mono">
                          ${row.response!.estimated_cost_usd.toFixed(6)}
                        </td>
                        <td>
                          <Button
                            variant="ghost"
                            aria-label={`Inspect trace for ${row.title}`}
                            onClick={() => setTrace(row)}
                          >
                            <ArrowUpRight size={14} />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="No persisted research traces."
                description="Complete a research session to inspect its recorded execution here."
              />
            )}
          </section>
          <div className="operations-footer">
            <span>
              Last sampled {updated?.toLocaleTimeString() || "Unavailable"} ·
              auto-refresh every 15 seconds
            </span>
            <a href="http://127.0.0.1:3001" target="_blank" rel="noreferrer">
              Grafana (requires Docker stack)
              <ArrowUpRight size={13} />
            </a>
          </div>
          <p className="subtle-note">
            Request metrics cover /chat, /query and /search. Histogram
            percentiles are approximate; stage means are not per-request
            breakdowns. Provider cost excludes infrastructure costs.
          </p>
        </>
      )}
      {trace?.response && (
        <Dialog title="Request trace" wide onClose={() => setTrace(null)}>
          <p className="trace-question">{trace.title}</p>
          <TraceWaterfall answer={trace.response} />
        </Dialog>
      )}
    </div>
  );
}
