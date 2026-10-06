import { useRef, useState } from "react";
import { FileText, Upload, Check } from "lucide-react";
import { api, type DocumentInfo } from "../../api";
import { useWorkspace } from "../../hooks/useWorkspace";
import { Badge, Button, Dialog, ErrorState, StatusBadge } from "../ui";
type UploadItem = { name: string; id?: string; status: string; error?: string };
export default function UploadDialog({
  onClose,
  onKnowledge,
}: {
  onClose: () => void;
  onKnowledge: () => void;
}) {
  const { documents, refresh } = useWorkspace();
  const input = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<UploadItem[]>([]),
    [busy, setBusy] = useState(false),
    [drag, setDrag] = useState(false);
  const lock = useRef(false);
  async function upload(files: FileList | null) {
    if (!files?.length || lock.current) return;
    lock.current = true;
    setBusy(true);
    const batch = Array.from(files);
    const offset = items.length;
    setItems((current) => [
      ...current,
      ...batch.map((file) => ({ name: file.name, status: "waiting" })),
    ]);
    for (const [index, file] of batch.entries()) {
      const position = offset + index;
      const update = (item: Partial<UploadItem>) =>
        setItems((current) =>
          current.map((value, i) =>
            i === position ? { ...value, ...item } : value,
          ),
        );
      if (file.size > 10 * 1024 * 1024) {
        update({
          status: "failed",
          error: "This file exceeds the 10 MB upload limit.",
        });
        continue;
      }
      if (!/\.(pdf|md|html|txt)$/i.test(file.name)) {
        update({
          status: "failed",
          error: "Choose a PDF, Markdown, HTML or text file.",
        });
        continue;
      }
      update({ status: "uploading" });
      try {
        const body = new FormData();
        body.append("file", file);
        const result = await api<DocumentInfo>("/documents/upload", {
          method: "POST",
          body,
        });
        update({ id: result.id, status: result.status });
        await refresh();
      } catch (e) {
        update({ status: "failed", error: (e as Error).message });
      }
    }
    setBusy(false);
    lock.current = false;
    if (input.current) input.current.value = "";
  }
  return (
    <Dialog title="Upload documents" onClose={onClose}>
      <p className="muted">
        Add research papers, technical notes or documentation to your knowledge
        base.
      </p>
      <button
        className={`upload-zone ${drag ? "drag-active" : ""}`}
        disabled={busy}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          upload(e.dataTransfer.files);
        }}
        onClick={() => input.current?.click()}
      >
        <Upload size={27} />
        <strong>{busy ? "Uploading documents…" : "Drop documents here"}</strong>
        <span>PDF · Markdown · HTML · TXT</span>
        <span className="upload-browse">Browse files</span>
        <small>Up to 10 MB per file</small>
      </button>
      <input
        ref={input}
        type="file"
        hidden
        multiple
        accept=".pdf,.md,.html,.txt"
        onChange={(e) => upload(e.target.files)}
      />
      {items.length > 0 && (
        <div className="upload-items" aria-live="polite">
          {items.map((item, index) => {
            const document = documents.find((d) => d.id === item.id);
            const status = document?.status || item.status;
            return (
              <div key={index}>
                <div>
                  <FileText size={17} />
                  <strong>{item.name}</strong>
                  <StatusBadge status={status} />
                </div>
                {(item.error || document?.error) && (
                  <p className="upload-error">
                    {item.error || document?.error}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
      <p className="subtle-note">
        Ingestion reports queued, processing, indexed or failed. Detailed
        parsing and embedding stages are not exposed. Scanned PDFs need OCR
        before upload.
      </p>
      <div className="dialog-actions">
        <Button onClick={onClose}>Close</Button>
        {items.some((item) => item.id) && (
          <Button variant="primary" onClick={onKnowledge}>
            View knowledge base
          </Button>
        )}
      </div>
    </Dialog>
  );
}
