import { useEffect, useRef, useState, type ComponentProps } from "react";
import {
  ArrowLeft,
  LoaderCircle,
  PanelRightOpen,
  ShieldCheck,
} from "lucide-react";
import type { Answer, Citation, Turn } from "../../api";
import { Badge, Button, ErrorState, Skeleton } from "../ui";
import EvidenceInspector, {
  useNarrow,
  type InspectorTab,
} from "../evidence/EvidenceInspector";
import ResearchComposer from "./ResearchComposer";
import ResearchResponse from "./ResearchResponse";
export default function ResearchSession({
  turns,
  busy,
  loading,
  pending,
  elapsed,
  error,
  onHome,
  onDocument,
  onSearch,
  composer,
  onRegenerate,
}: {
  turns: Turn[];
  busy: boolean;
  loading: boolean;
  pending: string;
  elapsed: number;
  error: string;
  onHome: () => void;
  onDocument: (id: string) => void;
  onSearch: (query: string) => void;
  composer: ComponentProps<typeof ResearchComposer>;
  onRegenerate: (question: string) => void;
}) {
  const narrow = useNarrow();
  const [open, setOpen] = useState(
      () => !matchMedia("(max-width:1199px)").matches,
    ),
    [tab, setTab] = useState<InspectorTab>("sources"),
    [source, setSource] = useState<Citation | null>(null),
    [selected, setSelected] = useState<Answer | null>(null);
  const scroll = useRef<HTMLDivElement>(null),
    answer = selected || turns.at(-1)?.response;
  useEffect(() => {
    if (narrow) setOpen(false);
  }, [narrow]);
  useEffect(() => {
    setSelected(null);
    setSource(null);
  }, [turns.at(-1)?.response.id]);
  useEffect(() => {
    const items = scroll.current?.querySelectorAll(
      busy ? ".pending-research" : ".research-turn",
    );
    items?.[items.length - 1]?.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
      block: "start",
    });
  }, [turns.length, busy, loading]);
  const inspect = (answer: Answer, next: InspectorTab, citation?: Citation) => {
    setSelected(answer);
    setTab(next);
    setSource(citation || null);
    setOpen(true);
  };
  return (
    <div className={`session-layout ${open && answer ? "inspector-open" : ""}`}>
      <div className="session-center">
        <header className="session-toolbar">
          <Button variant="ghost" onClick={onHome}>
            <ArrowLeft size={15} />
            Research
          </Button>
          <span>Research session</span>
          <Button onClick={() => setOpen(!open)} disabled={!answer}>
            <PanelRightOpen size={15} />
            Evidence
          </Button>
        </header>
        <div ref={scroll} className="session-scroll">
          {error && <ErrorState message={error} />}
          {loading ? (
            <Skeleton rows={8} />
          ) : (
            turns.map((turn) => (
              <ResearchResponse
                key={turn.response.id}
                turn={turn}
                onInspect={(next, c) => inspect(turn.response, next, c)}
                onRegenerate={() => onRegenerate(turn.question)}
              />
            ))
          )}
          {busy && (
            <section className="pending-research">
              <div className="user-query">
                <span>YOU</span>
                <h2>{pending}</h2>
              </div>
              <div className="pending-heading">
                <LoaderCircle className="spin" size={18} />
                <strong>Research request in progress</strong>
                <code>{elapsed.toFixed(0)}s</code>
              </div>
              <p>Waiting for the completed answer and execution record.</p>
              <Skeleton rows={3} />
              <small>
                This endpoint returns completed results; live stage progress is
                unavailable.
              </small>
            </section>
          )}
        </div>
        <div className="session-composer">
          <ResearchComposer {...composer} followUp />
        </div>
      </div>
      {open && answer && (
        <EvidenceInspector
          answer={answer}
          tab={tab}
          onTab={setTab}
          source={source}
          onSource={setSource}
          onClose={() => setOpen(false)}
          onDocument={onDocument}
          onSearch={onSearch}
        />
      )}
    </div>
  );
}
