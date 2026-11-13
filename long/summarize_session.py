"""Summarize the measured session: the middle of 5 runs per configuration.

usage: python3 summarize_session.py [results_dir] > summary.json

Per configuration: requests/s (middle run, plus every run sorted), latency of the middle run, how busy the server's
cores were, µs of one core per request (1 s × cores ÷ requests/s), PSS memory, process and thread counts, oha's and
Postgres's CPU, and the Mac background CPU of every run. The time per request only holds when the cores were full:
it's left out (null) for a configuration that didn't fill them, and the script stops if such a configuration
isn't one of the expected ones (the Postgres test's single sync worker, which is there to show the idle core).
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

MIN_BUSY = 0.97
RUNS = 5
# Sync workers leave the core idle while they wait for Postgres: that's what the Postgres test shows, not a rig limit.
MAY_IDLE = {f"{app}{variant}/users-db" for app in ("flask", "django") for variant in ("", "-w1", "-w2")}
# oha must stay well under its three cores, or it would be the limit instead of the server.
MAX_OHA_CPU = 2.4


def load(results: Path) -> dict[tuple[str, str], list[dict]]:
    runs: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for path in sorted(results.glob("*_run[0-9].json")):
        server, route, _ = path.stem.rsplit("_", 2)
        runs[(server, route)].append(json.loads(path.read_text()))
    return runs


def summarize(key: str, runs: list[dict]) -> dict:
    if len(runs) != RUNS:
        raise SystemExit(f"{key}: {len(runs)} runs, expected {RUNS}")
    ordered = sorted(runs, key=lambda r: r["summary"]["requestsPerSec"])
    mid = ordered[len(ordered) // 2]
    busy = min(r["core_busy"] for r in runs)
    full = busy >= MIN_BUSY
    if not full and key not in MAY_IDLE:
        raise SystemExit(f"{key}: cores only {busy:.3f} busy in one run")
    if max(r["oha_cpu"] for r in runs) > MAX_OHA_CPU:
        raise SystemExit(f"{key}: oha used {max(r['oha_cpu'] for r in runs):.2f} cores")
    rps = mid["summary"]["requestsPerSec"]
    return {
        "rps": rps,
        "rps_runs": [r["summary"]["requestsPerSec"] for r in ordered],
        "cores": 1,
        "core_busy": mid["core_busy"],
        "core_busy_min": busy,
        "us_per_request": 1e6 / rps if full else None,
        "p50_ms": mid["latencyPercentiles"]["p50"] * 1000,
        "p99_ms": mid["latencyPercentiles"]["p99"] * 1000,
        "pss_mb": mid["server_pss_mb"],
        "processes": mid["server_processes"],
        "threads": mid["server_threads"],
        "postgres_cpu": mid["postgres_cpu"],
        "oha_cpu": mid["oha_cpu"],
        "gil_enabled": sorted({g for r in runs for g in r["gil_enabled"]}),
        "mac_background_cpu_pct": [r.get("mac_background_cpu_pct") for r in runs],
        "spread_pct": (ordered[-1]["summary"]["requestsPerSec"] - ordered[0]["summary"]["requestsPerSec"]) / rps * 100,
    }


def main() -> None:
    results = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
    configs = {
        f"{server}/{route}": summarize(f"{server}/{route}", runs)
        for (server, route), runs in sorted(load(results).items())
    }
    json.dump({"configs": configs}, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
