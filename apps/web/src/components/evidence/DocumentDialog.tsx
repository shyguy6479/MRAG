import { useEffect, useState } from "react";
import { api, type DocumentDetail } from "../../api";
import {
  Badge,
  Button,
  Dialog,
  ErrorState,
  Skeleton,
  StatusBadge,
  Tabs,
} from "../ui";
export default function DocumentDialog({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<DocumentDetail | null>(null),
    [error, setError] = useState(""),
    [tab, setTab] = useState<"chunks" | "metadata">("chunks"),
    [search, setSearch] = useState(""),
    [limit, setLimit] = useState(12),
    [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError("");
    api<DocumentDetail>(`/documents/${id}`, { signal: controller.signal })
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [id, attempt]);
  const chunks =
    data?.chunks.filter((c) =>
      `${c.section} ${c.text}`.toLowerCase().includes(search.toLowerCase()),
    ) || [];
  return (
    <Dialog
      title={data?.document.title || "Document details"}
      onClose={onClose}
      wide
    >
      {error ? (
        <ErrorState message={error} retry={() => setAttempt(attempt + 1)} />
      ) : !data ? (
        <Skeleton rows={6} />
      ) : (
        <>
          <div className="document-detail-meta">
            <StatusBadge status={data.document.status} />
            <Badge>{data.document.format.toUpperCase()}</Badge>
            <span>
              {data.chunks.length} chunks ·{" "}
              {new Set(data.chunks.map((c) => c.section)).size} sections
            </span>
          </div>
          <Tabs
            value={tab}
            onChange={setTab}
            items={[
              { id: "chunks", label: "Chunks", count: data.chunks.length },
              { id: "metadata", label: "Metadata" },
            ]}
          />
          {tab === "metadata" ? (
            <dl className="technical-list document-metadata">
              {Object.entries({
                "Document ID": data.document.id,
                Source: data.document.source,
                Format: data.document.format.toUpperCase(),
                "Chunking strategy": data.document.chunking,
                "Index status": data.document.status,
                "Embedding stage": "Not separately reported",
                Created: new Date(data.document.created_at).toLocaleString(),
                "Indexed page numbers":
                  [
                    ...new Set(data.chunks.map((c) => c.page).filter(Boolean)),
                  ].join(", ") || "Unavailable",
                Tags: data.document.tags.join(", ") || "None",
              }).map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <>
              <input
                className="input chunk-search"
                placeholder="Search passages or sections…"
                aria-label="Search document chunks"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setLimit(12);
                }}
              />
              {data.document.error && (
                <ErrorState message={data.document.error} />
              )}
              <div className="chunk-list">
                {chunks.slice(0, limit).map((chunk, index) => (
                  <article key={chunk.chunk_id}>
                    <header>
                      <Badge>Chunk {chunk.ordinal + 1}</Badge>
                      <span>
                        {chunk.section}
                        {chunk.page ? ` · Page ${chunk.page}` : ""}
                      </span>
                    </header>
                    <p>{chunk.text}</p>
                    <code>{chunk.chunk_id}</code>
                  </article>
                ))}
                {!chunks.length && (
                  <p className="quiet-empty">
                    No indexed passages match this filter.
                  </p>
                )}
              </div>
              {chunks.length > limit && (
                <Button onClick={() => setLimit(limit + 12)}>
                  Show 12 more chunks
                </Button>
              )}
            </>
          )}
        </>
      )}
    </Dialog>
  );
}
