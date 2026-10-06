export type Sample = {
  name: string;
  labels: Record<string, string>;
  value: number;
};
export function parseMetrics(text: string): Sample[] {
  return text.split("\n").flatMap((line) => {
    if (!line || line.startsWith("#")) return [];
    const match = /^([a-zA-Z_:][\w:]*)(?:\{(.*?)\})?\s+([^\s]+)/.exec(line);
    if (!match) return [];
    const value = Number(match[3] === "+Inf" ? "Infinity" : match[3]);
    if (Number.isNaN(value)) return [];
    const labels: Record<string, string> = {};
    for (const entry of (match[2] || "").matchAll(/(\w+)="((?:\\.|[^"\\])*)"/g))
      labels[entry[1]] = entry[2]
        .replace(/\\"/g, '"')
        .replace(/\\n/g, "\n")
        .replace(/\\\\/g, "\\");
    return [{ name: match[1], labels, value }];
  });
}
const queryRoute = (sample: Sample) =>
  ["/query", "/chat", "/search"].includes(sample.labels.route);
export function histogramQuantile(
  samples: Sample[],
  name: string,
  quantile: number,
  filter: (sample: Sample) => boolean = () => true,
): number | null {
  const buckets = new Map<number, number>();
  for (const sample of samples.filter(
    (s) => s.name === `${name}_bucket` && filter(s),
  )) {
    const bound =
      sample.labels.le === "+Inf" ? Infinity : Number(sample.labels.le);
    buckets.set(bound, (buckets.get(bound) || 0) + sample.value);
  }
  const sorted = [...buckets].sort((a, b) => a[0] - b[0]);
  const count = buckets.get(Infinity) || 0;
  if (!count) return null;
  const target = count * quantile;
  let beforeCount = 0,
    beforeBound = 0;
  for (const [bound, value] of sorted) {
    if (value >= target) {
      if (!Number.isFinite(bound)) return null;
      return value === beforeCount
        ? bound
        : beforeBound +
            ((bound - beforeBound) * (target - beforeCount)) /
              (value - beforeCount);
    }
    beforeCount = value;
    beforeBound = bound;
  }
  return null;
}
export function summarizeMetrics(samples: Sample[]) {
  const sum = (
    name: string,
    filter: (sample: Sample) => boolean = () => true,
  ) =>
    samples
      .filter((s) => s.name === name && filter(s))
      .reduce((total, s) => total + s.value, 0);
  const requests = sum("rag_requests_total", queryRoute),
    errors = sum(
      "rag_requests_total",
      (s) => queryRoute(s) && Number(s.labels.status) >= 400,
    );
  const stages = samples
    .filter((s) => s.name === "rag_stage_latency_seconds_count" && s.value > 0)
    .map((s) => ({
      name: s.labels.stage,
      count: s.value,
      meanMs:
        (sum(
          "rag_stage_latency_seconds_sum",
          (x) => x.labels.stage === s.labels.stage,
        ) /
          s.value) *
        1000,
    }));
  return {
    requests,
    errors,
    errorRate: requests ? errors / requests : null,
    p95: histogramQuantile(
      samples,
      "rag_request_latency_seconds",
      0.95,
      queryRoute,
    ),
    stages,
    candidates: sum("retrieval_candidates_total"),
    verificationFailures: sum("verification_failures_total"),
    tools: samples
      .filter((s) => s.name === "tool_calls_total")
      .map((s) => ({ name: s.labels.tool, count: s.value })),
    cacheHits: sum("cache_requests_total", (s) => s.labels.result === "hit"),
    cacheMisses: sum("cache_requests_total", (s) => s.labels.result === "miss"),
  };
}

export function requestRate(
  before: { count: number; time: number } | null,
  next: { count: number; time: number },
): number | null {
  return before && next.count >= before.count && next.time > before.time
    ? ((next.count - before.count) / (next.time - before.time)) * 60000
    : null;
}
