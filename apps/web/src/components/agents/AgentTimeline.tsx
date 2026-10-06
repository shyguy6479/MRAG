import { Check, Search, Wrench } from "lucide-react";
import type { Answer } from "../../api";
import { Badge, Metric } from "../ui";
export const actionLabel = (action: string) =>
  ({
    analyze: "Analyze query",
    rewrite: "Rewrite search query",
    decompose: "Decompose research",
    search_documents: "Search knowledge base",
    build_context: "Build evidence context",
    synthesize: "Generate response",
    verify: "Verify source support",
    finish: "Complete response",
    calculator: "Calculator",
    get_document_metadata: "Inspect metadata",
  })[action] || action.replaceAll("_", " ");
export function AgentTimeline({ answer }: { answer: Answer }) {
  return (
    <div>
      <div className="timeline-summary">
        <Badge tone="success">Completed</Badge>
        <span className="mono">
          {answer.trace.length} actions · {answer.latency_ms.toFixed(0)} ms
        </span>
      </div>
      <ol className="agent-timeline">
        {answer.trace.map((step, index) => (
          <li key={`${step.step}-${index}`}>
            <span className="step-dot">
              <Check size={12} />
            </span>
            <div className="step-content">
              <div>
                <strong>{actionLabel(step.action)}</strong>
                <code>{step.duration_ms.toFixed(1)} ms</code>
              </div>
              <p>{step.detail}</p>
              {step.evidence_ids.length > 0 && (
                <Badge>{step.evidence_ids.length} evidence chunks</Badge>
              )}
            </div>
          </li>
        ))}
      </ol>
      <p className="subtle-note">
        Recorded actions and tool outputs. Private model reasoning is not
        exposed.
      </p>
    </div>
  );
}
export function TraceWaterfall({ answer }: { answer: Answer }) {
  let cumulative = 0;
  const total = Math.max(
    answer.latency_ms,
    answer.trace.reduce((n, s) => n + s.duration_ms, 0),
    1,
  );
  return (
    <>
      <div className="trace-request">
        <span>RESEARCH RESPONSE ID</span>
        <code>{answer.id}</code>
      </div>
      <div className="trace-usage">
        <Metric label="Duration" value={`${answer.latency_ms.toFixed(0)} ms`} />
        <Metric
          label="LLM tokens"
          value={answer.input_tokens + answer.output_tokens}
        />
        <Metric
          label="Reported cost"
          value={`$${answer.estimated_cost_usd.toFixed(6)}`}
        />
      </div>
      <div
        className="waterfall"
        aria-label="Recorded stage durations in milliseconds"
      >
        <div className="waterfall-scale">
          <span>0 ms</span>
          <span>{total.toFixed(0)} ms</span>
        </div>
        {answer.trace.map((step, index) => {
          const start = cumulative;
          cumulative += step.duration_ms;
          return (
            <div className="waterfall-row" key={index}>
              <span title={actionLabel(step.action)}>
                {actionLabel(step.action)}
              </span>
              <div
                className="waterfall-track"
                title={`${step.duration_ms.toFixed(2)} ms`}
              >
                <i
                  style={{
                    marginLeft: `${(start / total) * 100}%`,
                    width: `${Math.max((step.duration_ms / total) * 100, 0.5)}%`,
                  }}
                />
              </div>
              <code>{step.duration_ms.toFixed(1)}</code>
            </div>
          );
        })}
      </div>
      <p className="subtle-note">
        Sequential recorded stages. Uninstrumented request overhead may remain
        outside these bars. Generation: {answer.generator}.
      </p>
    </>
  );
}
