"""Turn one run's raw data into a compact results file.

usage: summarize_run.py <work dir> <duration_s> <start_epoch> <end_epoch> <server> <route> <out.json>

<work>/summary.json  oha's JSON summary (requests per second, errors)
<work>/requests.db   oha's per-request log (SQLite): throughput per 0.5 s and latency percentiles
<work>/server.log    the server's own output (the coda's "GIL enabled" lines)
<work>/stat-start, stat-end, cores   /proc/stat around the 20 s and the server's cores: how busy those cores were,
                     counting everything that ran on them (kernel network work too, which no process is charged for)
The server's CPU and memory come from Prometheus (process-exporter) over [start, end].
"""

import json
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BUCKET_S = 0.5
PERCENTILES = [50, 90, 99, 99.9]
PROMETHEUS = "http://127.0.0.1:9090/api/v1/query_range"
# Requests still in flight when oha's 20 s end; every other error fails the run.
EXPECTED_ERRORS = {"aborted due to deadline"}
# process-exporter groups the server under test (every process started from the bench venv) as "server".
SERVER_GROUPS = "server"


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def series(expr: str, start: float, end: float) -> list[float]:
    """Values of a single-series PromQL expression, one per second, inside the measured window."""
    query = urllib.parse.urlencode({"query": expr, "start": start + 3, "end": end, "step": "1s"})
    with urllib.request.urlopen(f"{PROMETHEUS}?{query}", timeout=10) as resp:
        data = json.load(resp)["data"]["result"]
    if len(data) > 1:
        raise SystemExit(f"expected one series for {expr!r}, got {len(data)}")
    return [float(v) for _, v in data[0]["values"]] if data else []


def cpu(group: str, start: float, end: float) -> list[float]:
    return series(f'sum(rate(namedprocess_namegroup_cpu_seconds_total{{groupname=~"{group}"}}[3s]))', start, end)


def core_busy(work: Path) -> float:
    """Share of the 20 s the server's cores were busy (not idle or waiting on I/O), averaged over those cores."""
    spec = (work / "cores").read_text().strip()
    a, _, b = spec.partition("-")
    cores = {f"cpu{c}" for c in range(int(a), int(b or a) + 1)}

    def ticks(name: str) -> dict[str, list[int]]:
        rows = (line.split() for line in (work / name).read_text().splitlines())
        return {row[0]: [int(x) for x in row[1:9]] for row in rows if row[0] in cores}

    before, after = ticks("stat-start"), ticks("stat-end")
    shares = []
    for core in cores:
        delta = [y - x for x, y in zip(before[core], after[core], strict=True)]
        shares.append(1 - (delta[3] + delta[4]) / sum(delta))
    return sum(shares) / len(shares)


def mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def main() -> None:
    work, duration_s, start, end, server, route, out_path = sys.argv[1:8]
    work = Path(work)
    duration_s, start, end = float(duration_s), float(start), float(end)
    summary = json.loads((work / "summary.json").read_text())
    errors = {k: v for k, v in (summary.get("errorDistribution") or {}).items() if k not in EXPECTED_ERRORS}
    if errors:
        raise SystemExit(f"{server} {route}: errors during the run: {errors}")
    rows = sqlite3.connect(work / "requests.db").execute("SELECT start, duration, status FROM oha").fetchall()
    buckets = [0] * int(duration_s / BUCKET_S)
    durations = []
    ok = total = 0
    for begun, duration, status in rows:
        if begun >= duration_s:
            continue
        total += 1
        if not 200 <= status < 300:
            continue
        ok += 1
        durations.append(duration)
        buckets[min(int(begun / BUCKET_S), len(buckets) - 1)] += 1
    if ok == 0 or ok != total:
        raise SystemExit(f"{server} {route}: {total - ok} of {total} responses were not 2xx")
    durations.sort()
    server_cpu = cpu(SERVER_GROUPS, start, end)
    pss = series(
        f'sum(namedprocess_namegroup_memory_bytes{{groupname=~"{SERVER_GROUPS}",memtype="proportionalResident"}})',
        start,
        end,
    )
    threads = series(f'sum(namedprocess_namegroup_num_threads{{groupname=~"{SERVER_GROUPS}"}})', start, end)
    procs = series(f'sum(namedprocess_namegroup_num_procs{{groupname=~"{SERVER_GROUPS}"}})', start, end)
    rps = ok / duration_s
    log = (work / "server.log").read_text(errors="replace")
    gil = sorted(set(re.findall(r"GIL enabled: (True|False)", log)))
    result = {
        "server": server,
        "route": route,
        "window": {"start": start, "end": end},
        "summary": {
            "requestsPerSec": rps,
            "total": total,
            "successRate": ok / total,
            "oha_requestsPerSec": summary["summary"]["requestsPerSec"],
        },
        "latencyPercentiles": {f"p{p:g}": percentile(durations, p) for p in PERCENTILES},
        "throughput_series": {"bucket_s": BUCKET_S, "rps": [n / BUCKET_S for n in buckets]},
        "core_busy": core_busy(work),
        "server_cpu": mean(server_cpu),
        "cpu_us_per_request": mean(server_cpu) * 1e6 / rps if server_cpu else None,
        "postgres_cpu": mean(cpu("postgres", start, end)),
        "oha_cpu": mean(cpu("oha", start, end)),
        "server_pss_mb": max(pss) / 2**20 if pss else None,
        "server_threads": max(threads) if threads else None,
        "server_processes": max(procs) if procs else None,
        "gil_enabled": gil,
    }
    Path(out_path).write_text(json.dumps(result))
    lat = result["latencyPercentiles"]
    print(
        f"{server} {route}: {rps:,.0f} req/s, p50 {lat['p50'] * 1e3:.0f} ms, p99 {lat['p99'] * 1e3:.0f} ms, "
        f"core busy {result['core_busy']:.3f}"
    )


if __name__ == "__main__":
    main()
