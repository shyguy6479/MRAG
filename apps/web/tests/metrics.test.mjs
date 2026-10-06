import { test } from "node:test";
import assert from "node:assert/strict";
import {
  parseMetrics,
  histogramQuantile,
  summarizeMetrics,
  requestRate,
} from "../src/services/metrics.ts";

test("parses labeled Prometheus samples and ignores comments and invalid samples", () => {
  const values = parseMetrics(
    '# TYPE requests counter\nrequests{route="/chat",status="200"} 3\nplain 4\nbroken NaN\n',
  );
  assert.deepEqual(values, [
    { name: "requests", labels: { route: "/chat", status: "200" }, value: 3 },
    { name: "plain", labels: {}, value: 4 },
  ]);
});
test("aggregates cumulative histogram buckets, with explicit route scope", () => {
  const samples = parseMetrics(
    'latency_bucket{route="/chat",le="0.1"} 5\nlatency_bucket{route="/chat",le="1"} 10\nlatency_bucket{route="/chat",le="+Inf"} 10\nlatency_bucket{route="/query",le="0.1"} 5\nlatency_bucket{route="/query",le="1"} 10\nlatency_bucket{route="/query",le="+Inf"} 10',
  );
  assert.equal(histogramQuantile(samples, "latency", 0.5), 0.1);
  assert.ok(
    Math.abs(histogramQuantile(samples, "latency", 0.95) - 0.91) < 1e-9,
  );
  assert.equal(
    histogramQuantile(
      samples,
      "latency",
      0.5,
      (s) => s.labels.route === "/query",
    ),
    0.1,
  );
});
test("does not invent quantiles for empty or unbounded observations", () => {
  assert.equal(histogramQuantile([], "latency", 0.95), null);
  assert.equal(
    histogramQuantile(
      parseMetrics('latency_bucket{le="1"} 0\nlatency_bucket{le="+Inf"} 10'),
      "latency",
      0.95,
    ),
    null,
  );
});
test("scopes request/error totals to research endpoints and calculates weighted stage means", () => {
  const metrics = summarizeMetrics(
    parseMetrics(
      'rag_requests_total{route="/health",status="200"} 100\nrag_requests_total{route="/chat",status="200"} 8\nrag_requests_total{route="/search",status="500"} 2\nrag_stage_latency_seconds_count{stage="retrieval"} 4\nrag_stage_latency_seconds_sum{stage="retrieval"} 2\ncache_requests_total{result="hit"} 3\ncache_requests_total{result="miss"} 1',
    ),
  );
  assert.equal(metrics.requests, 10);
  assert.equal(metrics.errors, 2);
  assert.equal(metrics.errorRate, 0.2);
  assert.equal(metrics.stages[0].meanMs, 500);
  assert.equal(metrics.cacheHits, 3);
  assert.equal(metrics.cacheMisses, 1);
  assert.equal(summarizeMetrics([]).errorRate, null);
});
test("rates need two valid observations and reset when counters decrease", () => {
  assert.equal(requestRate(null, { count: 10, time: 1000 }), null);
  assert.equal(
    requestRate({ count: 10, time: 1000 }, { count: 15, time: 16000 }),
    20,
  );
  assert.equal(
    requestRate({ count: 10, time: 1000 }, { count: 1, time: 16000 }),
    null,
  );
  assert.equal(
    requestRate({ count: 10, time: 1000 }, { count: 12, time: 1000 }),
    null,
  );
});
