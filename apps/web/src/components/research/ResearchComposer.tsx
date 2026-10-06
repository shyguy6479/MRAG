import { useState } from "react";
import {
  ArrowUp,
  Check,
  ChevronDown,
  FileText,
  Plus,
  Square,
  X,
} from "lucide-react";
import { useWorkspace } from "../../hooks/useWorkspace";
import { Badge, Button, Dialog, IconButton } from "../ui";
export type ResearchMode = "quick" | "research" | "agentic" | "deep";
export const modeConfig = {
  quick: {
    label: "Quick Answer",
    strategy: "hybrid_reranked",
    rewrite: false,
    decompose: false,
    top_k: 4,
  },
  research: {
    label: "Research",
    strategy: "hybrid_reranked",
    rewrite: true,
    decompose: false,
    top_k: 6,
  },
  agentic: {
    label: "Agentic Research",
    strategy: "agentic",
    rewrite: true,
    decompose: true,
    top_k: 6,
  },
  deep: {
    label: "Deep Analysis",
    strategy: "agentic",
    rewrite: true,
    decompose: true,
    top_k: 10,
  },
};
export function SourceSelector({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const { documents } = useWorkspace();
  const [open, setOpen] = useState(false),
    [search, setSearch] = useState("");
  return (
    <>
      <Button variant="ghost" onClick={() => setOpen(true)}>
        <FileText size={15} />
        {selected.length ? `${selected.length} selected` : "All sources"}
        <ChevronDown size={12} />
      </Button>
      {open && (
        <Dialog
          initialFocus="input"
          title="Select sources"
          onClose={() => setOpen(false)}
        >
          <p className="muted">
            Search across all indexed documents, or choose specific sources.
          </p>
          <input
            className="input"
            placeholder="Find a document…"
            aria-label="Filter sources"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button
            type="button"
            className="selection-row"
            onClick={() => onChange([])}
          >
            <span className={`checkbox ${!selected.length ? "checked" : ""}`}>
              {!selected.length && <Check size={13} />}
            </span>
            <strong>All indexed sources</strong>
          </button>
          <div className="source-options">
            {documents
              .filter(
                (d) =>
                  d.status === "ready" &&
                  d.title.toLowerCase().includes(search.toLowerCase()),
              )
              .map((doc) => (
                <button
                  type="button"
                  className="selection-row"
                  key={doc.id}
                  onClick={() =>
                    onChange(
                      selected.includes(doc.id)
                        ? selected.filter((id) => id !== doc.id)
                        : [...selected, doc.id],
                    )
                  }
                >
                  <span
                    className={`checkbox ${selected.includes(doc.id) ? "checked" : ""}`}
                  >
                    {selected.includes(doc.id) && <Check size={13} />}
                  </span>
                  <span>
                    {doc.title}
                    <small>
                      {doc.format.toUpperCase()} · {doc.chunk_count} chunks
                    </small>
                  </span>
                </button>
              ))}
          </div>
          <Button variant="primary" onClick={() => setOpen(false)}>
            Apply selection
          </Button>
        </Dialog>
      )}
    </>
  );
}
export default function ResearchComposer({
  value,
  onChange,
  onSend,
  onUpload,
  busy = false,
  onStop,
  followUp = false,
  mode,
  onMode,
  sources,
  onSources,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onUpload: () => void;
  busy?: boolean;
  onStop?: () => void;
  followUp?: boolean;
  mode: ResearchMode;
  onMode: (mode: ResearchMode) => void;
  sources: string[];
  onSources: (ids: string[]) => void;
}) {
  const { documents, system } = useWorkspace();
  return (
    <div className="composer-wrap">
      <form
        className="research-composer"
        onSubmit={(e) => {
          e.preventDefault();
          onSend();
        }}
      >
        <textarea
          aria-label="Research question"
          placeholder={
            followUp
              ? "Ask a follow-up question…"
              : "Ask a research question across your knowledge base…"
          }
          rows={followUp ? 2 : 3}
          maxLength={4000}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              if (!busy) onSend();
            }
          }}
        />
        {sources.length > 0 && (
          <div className="active-sources">
            {sources.map((id) => (
              <Badge key={id}>
                {documents.find((d) => d.id === id)?.title ||
                  "Selected document"}
                <IconButton
                  label="Remove source filter"
                  onClick={() =>
                    onSources(sources.filter((value) => value !== id))
                  }
                  type="button"
                >
                  <X size={12} />
                </IconButton>
              </Badge>
            ))}
          </div>
        )}
        <footer>
          <div className="composer-options">
            <IconButton
              label="Attach documents"
              type="button"
              onClick={onUpload}
            >
              <Plus size={18} />
            </IconButton>
            <label className="mode-select">
              <select
                aria-label="Research mode"
                value={mode}
                onChange={(e) => onMode(e.target.value as ResearchMode)}
              >
                {Object.entries(modeConfig).map(([id, item]) => (
                  <option key={id} value={id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <SourceSelector selected={sources} onChange={onSources} />
          </div>
          {busy ? (
            <Button type="button" onClick={onStop}>
              <Square size={13} />
              Stop waiting
            </Button>
          ) : (
            <Button
              type="submit"
              variant="primary"
              disabled={!value.trim()}
              aria-label="Send research question"
            >
              <span>Research</span>
              <ArrowUp size={17} />
            </Button>
          )}
        </footer>
      </form>
      <div className="composer-caption">
        <span>
          {system?.generator === "extractive"
            ? "Exact-source excerpts"
            : "Source-grounded responses"}{" "}
          · Citations included
        </span>
        <span>Enter to send · Shift + Enter for a new line</span>
      </div>
    </div>
  );
}
