import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, type DocumentInfo, type Recent, type SystemInfo } from "../api";
export function readLocal<T>(key: string, fallback: T): T {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    return fallback;
  }
}
function useData() {
  const [system, setSystem] = useState<SystemInfo | null>(null),
    [documents, setDocuments] = useState<DocumentInfo[]>([]),
    [recent, setRecent] = useState<Recent[]>(() =>
      readLocal("atlas-recent", []),
    ),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const [info, docs] = await Promise.all([
        api<SystemInfo>("/system"),
        api<DocumentInfo[]>("/documents"),
      ]);
      setSystem(info);
      setDocuments(docs);
      setError("");
    } catch (e) {
      setError((e as Error).message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);
  const refreshRecent = useCallback(async () => {
    try {
      const entries = await api<Recent[]>("/conversations");
      setRecent(entries);
      localStorage.setItem(
        "atlas-recent",
        JSON.stringify(entries.map(({ response, ...entry }) => entry)),
      );
    } catch {
      /* Existing browser history remains available on older API versions. */
    }
  }, []);
  useEffect(() => {
    refresh().catch(() => {});
    refreshRecent();
  }, [refresh, refreshRecent]);
  useEffect(() => {
    if (!documents.some((doc) => ["queued", "processing"].includes(doc.status)))
      return;
    const timer = setInterval(() => refresh().catch(() => {}), 1500);
    return () => clearInterval(timer);
  }, [documents, refresh]);
  const remember = (entry: Recent) =>
    setRecent((current) => {
      const next = [
        entry,
        ...current.filter((item) => item.id !== entry.id),
      ].slice(0, 50);
      localStorage.setItem(
        "atlas-recent",
        JSON.stringify(next.map(({ response, ...item }) => item)),
      );
      return next;
    });
  return {
    system,
    documents,
    recent,
    loading,
    error,
    refresh,
    refreshRecent,
    remember,
  };
}
const WorkspaceContext = createContext<ReturnType<typeof useData> | null>(null);
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const value = useData();
  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}
export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error("WorkspaceProvider is required");
  return context;
}
