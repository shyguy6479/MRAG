import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Turn } from "../api";
import { useWorkspace } from "./useWorkspace";
import {
  modeConfig,
  type ResearchMode,
} from "../components/research/ResearchComposer";
export function useResearch(
  session: string | null,
  onSession: (id: string | null) => void,
) {
  const transition = useRef(onSession);
  transition.current = onSession;
  const { remember, refresh } = useWorkspace();
  const [turns, setTurns] = useState<Turn[]>([]),
    [question, setQuestion] = useState(""),
    [mode, setMode] = useState<ResearchMode>("agentic"),
    [sources, setSources] = useState<string[]>([]),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [pending, setPending] = useState(""),
    [elapsed, setElapsed] = useState(0);
  const controller = useRef<AbortController | null>(null),
    loaded = useRef<string | null>(null),
    lock = useRef(false);
  useEffect(() => {
    if (session === loaded.current) return;
    const request = new AbortController();
    controller.current?.abort();
    controller.current = null;
    lock.current = false;
    setBusy(false);
    setError("");
    setQuestion("");
    if (!session) {
      loaded.current = null;
      setTurns([]);
      setLoading(false);
      return;
    }
    setTurns([]);
    setLoading(true);
    api<Turn[]>(`/conversations/${session}`, { signal: request.signal })
      .then((value) => {
        if (request.signal.aborted) return;
        setTurns(value);
        loaded.current = session;
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!request.signal.aborted) setLoading(false);
      });
    return () => request.abort();
  }, [session]);
  useEffect(() => {
    if (!busy) return;
    const start = Date.now();
    setElapsed(0);
    const timer = setInterval(
      () => setElapsed((Date.now() - start) / 1000),
      1000,
    );
    return () => clearInterval(timer);
  }, [busy]);
  useEffect(() => () => controller.current?.abort(), []);
  async function send(value = question) {
    if (!value.trim() || lock.current || loading) return;
    lock.current = true;
    const request = new AbortController();
    controller.current = request;
    setBusy(true);
    setPending(value.trim());
    setQuestion("");
    setError("");
    try {
      const response = await api<Turn["response"]>("/chat", {
        method: "POST",
        signal: request.signal,
        body: JSON.stringify({
          question: value.trim(),
          conversation_id: session,
          ...modeConfig[mode],
          label: undefined,
          verify: true,
          filters: { document_ids: sources },
        }),
      });
      if (request.signal.aborted) return;
      setTurns((current) => [...current, { question: value.trim(), response }]);
      if (response.conversation_id) {
        loaded.current = response.conversation_id;
        transition.current(response.conversation_id);
        remember({
          id: response.conversation_id,
          title: value.trim(),
          updated_at: new Date().toISOString(),
          sources: new Set(response.citations.map((c) => c.document_id)).size,
          response,
        });
      }
      refresh().catch(() => {});
    } catch (e) {
      if (controller.current !== request) return;
      if ((e as Error).name === "AbortError")
        setError(
          "Stopped waiting. The server may still finish this research request.",
        );
      else {
        setError((e as Error).message);
        setQuestion(value);
      }
    } finally {
      if (controller.current === request) {
        lock.current = false;
        setBusy(false);
        setPending("");
      }
    }
  }
  const reset = useCallback(() => {
    controller.current?.abort();
    controller.current = null;
    lock.current = false;
    loaded.current = null;
    setBusy(false);
    setLoading(false);
    setTurns([]);
    setQuestion("");
    setSources([]);
    setPending("");
    setError("");
    onSession(null);
  }, [onSession]);
  return {
    turns,
    question,
    setQuestion,
    mode,
    setMode,
    sources,
    setSources,
    busy,
    loading,
    error,
    setError,
    pending,
    elapsed,
    send,
    reset,
    stop: () => controller.current?.abort(),
  };
}
