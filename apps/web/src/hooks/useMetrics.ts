import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import {
  parseMetrics,
  summarizeMetrics,
  requestRate,
} from "../services/metrics";
export function useMetrics() {
  const [metrics, setMetrics] = useState<ReturnType<
      typeof summarizeMetrics
    > | null>(null),
    [ready, setReady] = useState("checking"),
    [rate, setRate] = useState<number | null>(null),
    [error, setError] = useState(""),
    [updated, setUpdated] = useState<Date | null>(null);
  const previous = useRef<{ count: number; time: number } | null>(null),
    controller = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    try {
      const [raw, health] = await Promise.all([
        api<string>("/metrics", { signal: request.signal }),
        api<{ status: string }>("/ready", { signal: request.signal }).catch(
          () => ({ status: "unavailable" }),
        ),
      ]);
      if (request.signal.aborted) return;
      const next = summarizeMetrics(parseMetrics(raw)),
        now = Date.now(),
        before = previous.current;
      setRate(requestRate(before, { count: next.requests, time: now }));
      previous.current = { count: next.requests, time: now };
      setMetrics(next);
      setReady(health.status);
      setError("");
      setUpdated(new Date(now));
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    }
  }, []);
  useEffect(() => {
    refresh();
    const timer = setInterval(() => {
      if (!document.hidden) refresh();
    }, 15000);
    return () => {
      clearInterval(timer);
      controller.current?.abort();
    };
  }, [refresh]);
  return { metrics, ready, rate, error, updated, refresh };
}
