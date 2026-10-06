import { useCallback, useEffect, useState } from "react";
import { api, type EvaluationRun, type RunSummary } from "../api";
export function useRuns() {
  const [runs, setRuns] = useState<RunSummary[]>([]),
    [data, setData] = useState<Record<string, EvaluationRun>>({}),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const refresh = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const summaries = await api<RunSummary[]>("/evaluation-runs", { signal });
      const full = await Promise.all(
        summaries.map(
          async (run) =>
            [
              run.id,
              await api<EvaluationRun>(`/evaluation-runs/${run.id}`, {
                signal,
              }),
            ] as const,
        ),
      );
      setRuns(summaries);
      setData(Object.fromEntries(full));
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);
  return { runs, data, loading, error, refresh: () => refresh() };
}
