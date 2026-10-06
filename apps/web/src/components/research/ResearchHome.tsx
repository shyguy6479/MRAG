import {
  ArrowRight,
  GitCompare,
  Search,
  ShieldCheck,
  Split,
  TextSearch,
} from "lucide-react";
import { useWorkspace } from "../../hooks/useWorkspace";
import {
  Badge,
  Button,
  Metric,
  PageHeader,
  SectionHeader,
  Skeleton,
} from "../ui";
import ResearchComposer from "./ResearchComposer";
import type { ComponentProps } from "react";
export const quickActions = [
  {
    label: "Compare sources",
    question:
      "Compare quantization and speculative decoding for reducing inference cost.",
    icon: GitCompare,
  },
  {
    label: "Find contradictions",
    question:
      "Do the indexed sources disagree about inference latency and memory trade-offs?",
    icon: Split,
  },
  {
    label: "Summarize research",
    question:
      "Summarize the inference optimization techniques discussed in the indexed sources.",
    icon: TextSearch,
  },
  {
    label: "Trace a claim",
    question:
      "What evidence supports the claim that paged attention improves memory efficiency?",
    icon: ShieldCheck,
  },
  {
    label: "Explore a topic",
    question:
      "What are the quality and latency trade-offs of hybrid retrieval and reranking?",
    icon: Search,
  },
];
export default function ResearchHome({
  composer,
  onOpen,
  onKnowledge,
  onPrompt,
}: {
  composer: ComponentProps<typeof ResearchComposer>;
  onOpen: (id: string) => void;
  onKnowledge: () => void;
  onPrompt: (value: string) => void;
}) {
  const { recent, system, documents, loading } = useWorkspace();
  return (
    <div className="research-home">
      <PageHeader
        title="Research across your knowledge"
        description="Ask complex questions. Follow the research. Trace every answer to evidence."
      />
      <ResearchComposer {...composer} />
      <div className="quick-actions" aria-label="Research quick actions">
        {quickActions.map((action) => (
          <Button
            variant="ghost"
            key={action.label}
            onClick={() => onPrompt(action.question)}
          >
            <action.icon size={15} />
            {action.label}
          </Button>
        ))}
      </div>
      <section className="home-sessions">
        <SectionHeader
          title="Recent research"
          description="Pick up where you left off."
          action={<Badge>{recent.length} sessions</Badge>}
        />
        {loading && !recent.length ? (
          <Skeleton />
        ) : recent.length ? (
          <div className="table-scroll">
            <table className="data-table session-table">
              <thead>
                <tr>
                  <th>Research</th>
                  <th>Sources</th>
                  <th>Status</th>
                  <th>Updated</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {recent.slice(0, 4).map((item) => (
                  <tr key={item.id}>
                    <td>
                      <button
                        className="row-title"
                        onClick={() => onOpen(item.id)}
                      >
                        {item.title}
                      </button>
                    </td>
                    <td className="mono">{item.sources ?? "—"}</td>
                    <td>
                      <Badge tone={item.response ? "success" : "neutral"}>
                        {item.response ? "Completed" : "Saved"}
                      </Badge>
                    </td>
                    <td className="metadata">
                      {item.updated_at
                        ? new Date(item.updated_at).toLocaleDateString(
                            undefined,
                            { month: "short", day: "numeric" },
                          )
                        : "Unavailable"}
                    </td>
                    <td>
                      <Button
                        variant="ghost"
                        aria-label={`Open ${item.title}`}
                        onClick={() => onOpen(item.id)}
                      >
                        <ArrowRight size={15} />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="quiet-empty">
            Your research will appear here after your first question.
          </div>
        )}
      </section>
      <section className="knowledge-overview">
        <SectionHeader
          title="Your knowledge base"
          action={
            <button className="text-link" onClick={onKnowledge}>
              Manage documents
              <ArrowRight size={14} />
            </button>
          }
        />
        <div className="metrics-row">
          <Metric label="Documents indexed" value={system?.ready_documents} />
          <Metric label="Searchable chunks" value={system?.chunks} />
          <Metric
            label="Ingestion queue"
            value={
              system
                ? documents.filter((d) =>
                    ["queued", "processing"].includes(d.status),
                  ).length
                : null
            }
          />
          <Metric
            label="Retrieval engine"
            value={
              system?.dense_backend === "neural"
                ? "Neural + BM25"
                : system
                  ? "LSA + BM25"
                  : null
            }
            note="Hybrid retrieval · RRF fusion"
          />
        </div>
      </section>
    </div>
  );
}
