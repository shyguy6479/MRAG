import { useState } from "react";
import { FileText, Search, Trash2, Upload } from "lucide-react";
import { api, type DocumentInfo } from "../api";
import { useWorkspace } from "../hooks/useWorkspace";
import {
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  IconButton,
  Metric,
  PageHeader,
  Skeleton,
  StatusBadge,
} from "../components/ui";
export default function KnowledgePage({
  onUpload,
  onDocument,
}: {
  onUpload: () => void;
  onDocument: (id: string) => void;
}) {
  const { documents, system, loading, refresh } = useWorkspace();
  const [query, setQuery] = useState(""),
    [format, setFormat] = useState(""),
    [pending, setPending] = useState<DocumentInfo | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const filtered = documents.filter(
    (doc) =>
      `${doc.title} ${doc.source}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (!format || doc.format === format),
  );
  async function remove() {
    if (!pending) return;
    setBusy(true);
    try {
      await api(`/documents/${pending.id}`, { method: "DELETE" });
      await refresh();
      setPending(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page">
      <PageHeader
        title="Knowledge Base"
        description="Manage the source material behind your research."
        actions={
          <Button variant="primary" onClick={onUpload}>
            <Upload size={15} />
            Upload documents
          </Button>
        }
      />
      <div className="metrics-row metrics-strip">
        <Metric label="Documents" value={system?.documents} />
        <Metric label="Indexed chunks" value={system?.chunks} />
        <Metric
          label="Processing"
          value={
            documents.filter((d) => ["queued", "processing"].includes(d.status))
              .length
          }
        />
        <Metric
          label="Index size"
          value="Unavailable"
          note="Disk size is not exposed"
        />
      </div>
      {error && (
        <ErrorState
          message={error}
          retry={() => {
            setError("");
            refresh().catch((e) => setError(e.message));
          }}
        />
      )}
      <div className="table-toolbar">
        <label className="input-with-icon">
          <Search size={16} />
          <input
            aria-label="Search documents"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search documents…"
          />
        </label>
        <select
          className="field compact-select"
          aria-label="Document type"
          value={format}
          onChange={(e) => setFormat(e.target.value)}
        >
          <option value="">All file types</option>
          {["pdf", "md", "html", "txt"].map((type) => (
            <option key={type} value={type}>
              {type.toUpperCase()}
            </option>
          ))}
        </select>
        <span>{filtered.length} documents</span>
      </div>
      {loading ? (
        <Skeleton rows={7} />
      ) : documents.length === 0 ? (
        <EmptyState
          title="Your knowledge base is empty."
          description="Upload documents to begin researching across your own sources."
          action={
            <Button variant="primary" onClick={onUpload}>
              Upload documents
            </Button>
          }
        />
      ) : (
        <div className="table-scroll">
          <table className="data-table document-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Chunks</th>
                <th>Status</th>
                <th>Added</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <button
                      className="document-row-title"
                      onClick={() => onDocument(doc.id)}
                    >
                      <span className="document-icon">
                        <FileText size={19} />
                      </span>
                      <span>
                        {doc.title}
                        <small>{doc.source}</small>
                      </span>
                    </button>
                  </td>
                  <td>
                    <span className="file-type">
                      {doc.format.toUpperCase()}
                    </span>
                  </td>
                  <td className="mono">{doc.chunk_count}</td>
                  <td>
                    <StatusBadge status={doc.status} />
                  </td>
                  <td>
                    {new Date(doc.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </td>
                  <td>
                    <IconButton
                      label={`Delete ${doc.title}`}
                      onClick={() => setPending(doc)}
                    >
                      <Trash2 size={15} />
                    </IconButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length && (
            <div className="quiet-empty">No documents match your filters.</div>
          )}
        </div>
      )}
      <p className="subtle-note">
        Collections are unavailable in the current API. Document filters and
        provenance are supported for every indexed source.
      </p>
      {pending && (
        <Dialog title="Delete document" onClose={() => setPending(null)}>
          <p className="muted">
            Delete “{pending.title}” and remove its indexed chunks? Existing
            conversation responses remain in history.
          </p>
          {error && <ErrorState message={error} />}
          <div className="dialog-actions">
            <Button onClick={() => setPending(null)}>Cancel</Button>
            <Button variant="danger" disabled={busy} onClick={remove}>
              {busy ? "Deleting…" : "Delete document"}
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
