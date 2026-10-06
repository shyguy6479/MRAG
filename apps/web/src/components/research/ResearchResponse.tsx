import { useState } from "react";
import {
  Check,
  Copy,
  GitBranch,
  Layers3,
  RefreshCw,
  Search,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import type { Citation, Turn } from "../../api";
import type { InspectorTab } from "../evidence/EvidenceInspector";
import { readLocal } from "../../hooks/useWorkspace";
import { Badge, Button } from "../ui";
export default function ResearchResponse({
  turn,
  onInspect,
  onRegenerate,
}: {
  turn: Turn;
  onInspect: (tab: InspectorTab, citation?: Citation) => void;
  onRegenerate: () => void;
}) {
  const answer = turn.response;
  const [preview, setPreview] = useState<{
      citation: Citation;
      left: number;
      top: number;
    } | null>(null),
    [copied, setCopied] = useState(false),
    [feedback, setFeedback] = useState<string | null>(
      () =>
        readLocal<Record<string, string>>("atlas-feedback", {})[answer.id] ||
        null,
    ),
    [copyError, setCopyError] = useState("");
  const cite = (n: number) => answer.citations.find((c) => c.number === n);
  function showPreview(element: HTMLElement, citation: Citation) {
    const bounds = element.getBoundingClientRect();
    setPreview({
      citation,
      left: Math.max(12, Math.min(bounds.left, window.innerWidth - 324)),
      top: Math.min(bounds.bottom + 8, window.innerHeight - 210),
    });
  }
  function textParts(text: string) {
    return text.split(/(\[\d+\])/g).map((part, index) => {
      const number = /^\[(\d+)\]$/.exec(part);
      const citation = number ? cite(Number(number[1])) : null;
      return citation ? (
        <button
          key={index}
          className="inline-citation"
          aria-label={`Citation ${citation.number}: ${citation.title}`}
          onMouseEnter={(e) => showPreview(e.currentTarget, citation)}
          onMouseLeave={() => setPreview(null)}
          onFocus={(e) => showPreview(e.currentTarget, citation)}
          onBlur={() => setPreview(null)}
          onClick={() => {
            setPreview(null);
            onInspect("sources", citation);
          }}
        >
          [{citation.number}]
        </button>
      ) : (
        <span key={index}>{part}</span>
      );
    });
  }
  const supported = answer.claims.filter(
    (c) => c.status === "supported",
  ).length;
  async function copy() {
    try {
      await navigator.clipboard.writeText(answer.answer);
      setCopied(true);
      setCopyError("");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyError(
        "Clipboard access was unavailable. You can select and copy the answer text.",
      );
    }
  }
  function rate(value: string) {
    const next = feedback === value ? null : value;
    const saved = readLocal<Record<string, string>>("atlas-feedback", {});
    if (next) saved[answer.id] = next;
    else delete saved[answer.id];
    localStorage.setItem("atlas-feedback", JSON.stringify(saved));
    setFeedback(next);
  }
  return (
    <section className="research-turn">
      <div className="user-query">
        <span>YOU</span>
        <h2>{turn.question}</h2>
      </div>
      <article className="research-response">
        <header className="response-header">
          <span className="researcher-mark">
            <Layers3 size={17} />
          </span>
          <strong>MRAG Researcher</strong>
          <Badge>
            {answer.generator === "extractive"
              ? "Evidence extracts"
              : answer.generator === "deterministic"
                ? "Tool result"
                : "Research answer"}
          </Badge>
          <code>{answer.latency_ms.toFixed(0)} ms</code>
        </header>
        <div className="research-prose">
          {answer.answer
            .split("\n")
            .filter(Boolean)
            .map((line, index) =>
              line.startsWith("## ") ? (
                <h3 key={index}>{textParts(line.slice(3))}</h3>
              ) : line.startsWith("- ") ? (
                <div className="finding" key={index}>
                  <span>•</span>
                  <p>{textParts(line.slice(2))}</p>
                </div>
              ) : (
                <p key={index}>{textParts(line)}</p>
              ),
            )}
        </div>
        <div className="verification-summary">
          <ShieldCheck size={15} />
          <span>
            {supported} of {answer.claims.length} claims have exact source
            support
          </span>
          <button className="text-link" onClick={() => onInspect("sources")}>
            {answer.citations.length} citations
          </button>
        </div>
        {answer.warnings.length > 0 && (
          <div className="response-limits">
            <h4>Limitations</h4>
            {answer.warnings.map((w) => (
              <p key={w}>{w}</p>
            ))}
          </div>
        )}
        <div className="response-actions">
          <Button
            variant="ghost"
            onClick={copy}
            aria-label={copied ? "Copied" : "Copy answer"}
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            <span>{copied ? "Copied" : "Copy"}</span>
          </Button>
          <Button
            variant="ghost"
            onClick={onRegenerate}
            aria-label="Regenerate answer"
          >
            <RefreshCw size={14} />
            <span>Regenerate</span>
          </Button>
          <Button
            variant="ghost"
            onClick={() => onInspect("retrieval")}
            aria-label="Inspect retrieval"
          >
            <Search size={14} />
            <span>Inspect retrieval</span>
          </Button>
          <Button
            variant="ghost"
            onClick={() => onInspect("agent")}
            aria-label="View execution"
          >
            <GitBranch size={14} />
            <span>View execution</span>
          </Button>
          <div className="feedback-actions">
            <button
              aria-label="Mark response helpful"
              aria-pressed={feedback === "helpful"}
              title="Feedback saved on this device"
              onClick={() => rate("helpful")}
            >
              <ThumbsUp size={14} />
            </button>
            <button
              aria-label="Mark response unhelpful"
              aria-pressed={feedback === "unhelpful"}
              title="Feedback saved on this device"
              onClick={() => rate("unhelpful")}
            >
              <ThumbsDown size={14} />
            </button>
          </div>
        </div>
        {copyError && <p className="subtle-note">{copyError}</p>}
        <p className="response-note">
          {answer.generator === "extractive"
            ? "Exact excerpts from your sources. Support is a heuristic, not a probability of correctness."
            : "Verify important claims against the cited sources."}
          {feedback ? " Feedback saved on this device." : ""}
        </p>
      </article>
      {preview && (
        <div
          className="citation-preview"
          role="tooltip"
          style={{ left: preview.left, top: preview.top }}
        >
          <strong>
            <span>[{preview.citation.number}]</span> {preview.citation.title}
          </strong>
          <small>
            {preview.citation.section}
            {preview.citation.page ? ` · Page ${preview.citation.page}` : ""}
          </small>
          <p>{preview.citation.text.slice(0, 180)}…</p>
          <span>Click to inspect source evidence</span>
        </div>
      )}
    </section>
  );
}
