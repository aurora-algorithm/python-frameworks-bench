#!/bin/bash
# Starts Prometheus, process-exporter and Grafana inside the rig, pinned to the monitoring cores, detached.
# Data lives in ~/prom-data; results/prometheus/ gets a copy after a session.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
cores=${MONITOR_CORE:-0-1}
mkdir -p ~/prom-data ~/grafana-data /tmp/monitoring
start() { # process name, log name, command...
  local name=$1 log=$2; shift 2
  pgrep -x "$name" >/dev/null && return 0
  setsid taskset -c "$cores" "$@" </dev/null >"/tmp/monitoring/$log.log" 2>&1 &
}
start prometheus prometheus /opt/prometheus/prometheus --config.file="$here/prometheus.yml" \
  --storage.tsdb.path="$HOME/prom-data" --storage.tsdb.retention.time=1y \
  --web.listen-address=127.0.0.1:9090 --web.enable-admin-api
start process-exporte process-exporter /opt/process-exporter/process-exporter \
  -config.path="$here/process-exporter.yml" -gather-smaps=true -web.listen-address=127.0.0.1:9256
GF_PATHS_DATA="$HOME/grafana-data" start grafana grafana /opt/grafana/bin/grafana server \
  --homepath /opt/grafana --config "$here/grafana/grafana.ini"
for _ in $(seq 60); do
  curl -sf 127.0.0.1:3000/api/health >/dev/null && curl -sf 127.0.0.1:9090/-/ready >/dev/null && exit 0
  sleep 0.5
done
echo "monitoring did not come up; see /tmp/monitoring/*.log" >&2
exit 1
