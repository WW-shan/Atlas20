from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import time
from typing import Any

import httpx


DEFAULT_PATHS = (
    "/api/overview",
    "/api/options",
    "/api/runs?page=1&pageSize=14&dateRange=all&q=&chips=",
    "/api/runs/queue",
    "/api/compare?ids=atlas,momentum,meanrev&range=YTD",
    "/api/universe/timeline",
    "/api/universe/sources",
    "/api/universe/alerts",
    "/api/reports?sort=recent",
)


@dataclass(frozen=True)
class RequestSample:
    path: str
    latency_ms: float
    status_code: int | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 400


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (percent / 100)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def build_summary(
    samples: list[RequestSample],
    *,
    target_rps: int,
    duration_seconds: float,
    p95_threshold_ms: float,
    min_success_rate: float,
    min_rps_ratio: float,
) -> dict[str, Any]:
    latencies = [sample.latency_ms for sample in samples]
    total = len(samples)
    succeeded = sum(1 for sample in samples if sample.ok)
    failed = total - succeeded
    actual_rps = total / duration_seconds if duration_seconds > 0 else 0.0
    status_counts: dict[str, int] = {}
    path_status_counts: dict[str, dict[str, int]] = {}
    error_counts: dict[str, int] = {}
    for sample in samples:
        status_key = str(sample.status_code) if sample.status_code is not None else "exception"
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        path_counts = path_status_counts.setdefault(sample.path, {})
        path_counts[status_key] = path_counts.get(status_key, 0) + 1
        if sample.error:
            error_counts[sample.error] = error_counts.get(sample.error, 0) + 1

    p95_ms = percentile(latencies, 95)
    success_rate = succeeded / total if total else 0.0
    min_rps = target_rps * min_rps_ratio
    passed = failed == 0 and p95_ms < p95_threshold_ms and actual_rps >= min_rps and success_rate >= min_success_rate
    return {
        "passed": passed,
        "target_rps": target_rps,
        "actual_rps": round(actual_rps, 2),
        "duration_seconds": round(duration_seconds, 3),
        "total_requests": total,
        "succeeded": succeeded,
        "failed": failed,
        "success_rate": round(success_rate, 4),
        "p50_ms": round(percentile(latencies, 50), 2),
        "p95_ms": round(p95_ms, 2),
        "p99_ms": round(percentile(latencies, 99), 2),
        "max_ms": round(max(latencies, default=0.0), 2),
        "status_counts": status_counts,
        "path_status_counts": path_status_counts,
        "error_counts": error_counts,
        "thresholds": {
            "p95_ms_lt": p95_threshold_ms,
            "min_success_rate": min_success_rate,
            "min_actual_rps": round(min_rps, 2),
        },
    }


async def request_once(client: httpx.AsyncClient, path: str, semaphore: asyncio.Semaphore) -> RequestSample:
    async with semaphore:
        started = time.perf_counter()
        try:
            response = await client.get(path)
            latency_ms = (time.perf_counter() - started) * 1000
            return RequestSample(path=path, latency_ms=latency_ms, status_code=response.status_code)
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            return RequestSample(
                path=path,
                latency_ms=latency_ms,
                status_code=None,
                error=f"{type(exc).__name__}: {exc}",
            )


async def run_load(
    *,
    base_url: str,
    paths: list[str],
    rps: int,
    duration_seconds: float,
    concurrency: int,
    timeout_seconds: float,
) -> tuple[list[RequestSample], float]:
    total_requests = max(1, int(round(rps * duration_seconds)))
    semaphore = asyncio.Semaphore(concurrency)
    tasks: list[asyncio.Task[RequestSample]] = []
    started = time.perf_counter()
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds) as client:
        for index in range(total_requests):
            scheduled_at = started + (index / rps)
            sleep_for = scheduled_at - time.perf_counter()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            tasks.append(asyncio.create_task(request_once(client, paths[index % len(paths)], semaphore)))
        samples = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - started
    return samples, elapsed


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Atlas20 API read-path load baseline")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--rps", type=int, default=100)
    parser.add_argument("--duration-seconds", type=float, default=60)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--timeout-seconds", type=float, default=5)
    parser.add_argument("--p95-ms", type=float, default=200)
    parser.add_argument("--min-success-rate", type=float, default=1.0)
    parser.add_argument("--min-rps-ratio", type=float, default=0.95)
    parser.add_argument("--path", action="append", dest="paths", help="API path to include; can be repeated")
    parser.add_argument("--output", default="output/load/api-load-summary.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    paths = args.paths or list(DEFAULT_PATHS)
    if args.rps <= 0:
        raise SystemExit("--rps must be greater than 0")
    if args.duration_seconds <= 0:
        raise SystemExit("--duration-seconds must be greater than 0")
    if args.concurrency <= 0:
        raise SystemExit("--concurrency must be greater than 0")

    samples, elapsed = asyncio.run(
        run_load(
            base_url=args.base_url,
            paths=paths,
            rps=args.rps,
            duration_seconds=args.duration_seconds,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout_seconds,
        )
    )
    summary = build_summary(
        samples,
        target_rps=args.rps,
        duration_seconds=elapsed,
        p95_threshold_ms=args.p95_ms,
        min_success_rate=args.min_success_rate,
        min_rps_ratio=args.min_rps_ratio,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
