"""Small HTTP concurrency experiment; requires an already seeded running API."""

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import httpx
import numpy as np


async def run(url: str, count: int) -> dict[str, object]:
    headers = {"X-API-Key": os.environ.get("ATLAS_API_KEY", "")}
    questions = json.loads(Path("benchmarks/questions.json").read_text())
    rows = []
    async with httpx.AsyncClient(base_url=url, headers=headers, timeout=60) as client:
        health = await client.get("/ready")
        health.raise_for_status()
        for concurrency in [1, 4, 8]:
            semaphore = asyncio.Semaphore(concurrency)
            latencies: list[float] = []
            statuses: dict[str, int] = {}
            cache_hits = 0

            async def query(
                index: int,
                gate: asyncio.Semaphore = semaphore,
                timings: list[float] = latencies,
                codes: dict[str, int] = statuses,
            ) -> None:
                nonlocal cache_hits
                async with gate:
                    started = perf_counter()
                    response = await client.post(
                        "/query",
                        json={
                            "question": questions[index % len(questions)]["question"],
                            "strategy": "agentic",
                        },
                    )
                    timings.append((perf_counter() - started) * 1000)
                    code = str(response.status_code)
                    codes[code] = codes.get(code, 0) + 1
                    if response.status_code == 200:
                        cache_hits += response.json()["retrieval"]["cache_hit"]

            started = perf_counter()
            await asyncio.gather(*(query(i) for i in range(count)))
            elapsed = perf_counter() - started
            rows.append(
                {
                    "concurrency": concurrency,
                    "requests": count,
                    "statuses": statuses,
                    "duration_seconds": elapsed,
                    "throughput_requests_per_second": count / elapsed,
                    "cache_hit_rate": cache_hits / count,
                    **{f"p{p}_ms": float(np.percentile(latencies, p)) for p in [50, 95, 99]},
                }
            )
    return {
        "measured_at": datetime.now(UTC).isoformat(),
        "target": url,
        "scope": "HTTP loopback, small authored corpus, mixed/warm caches, no LLM calls",
        "limitations": "12 requests per level by default; not a capacity or tail-SLO estimate.",
        "runs": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=12)
    args = parser.parse_args()
    if args.requests < 1:
        parser.error("requests must be positive")
    result = asyncio.run(run(args.url, args.requests))
    path = Path("benchmarks/results/load.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if any(set(row["statuses"]) != {"200"} for row in result["runs"]):
        raise SystemExit("Load run contained HTTP failures; inspect the saved status counts.")


if __name__ == "__main__":
    main()
