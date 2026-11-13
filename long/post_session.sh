#!/bin/bash
# After run_all.sh, from the Mac: the session summary (with its gates), the py-spy profiles, and the results copied
# out of the rig into this folder. Each step stops on failure.
# usage: post_session.sh [summary|profiles|copy ...]   (default: all, in that order)
set -euo pipefail
cd "$(dirname "$0")"
PROFILES=("fastapi users" "fastapi-typed users" "flask users" "django users" "litestar users" "django users-post")
rig() { docker exec -u dev longs-rig bash -lc "cd ~/pybench && $1"; }

summary() {
  ./sync_in.sh
  rig "python3 summarize_session.py results > summary.json"
  docker cp longs-rig:/home/dev/pybench/summary.json summary.json
  echo "summary: $(python3 -c 'import json; print(len(json.load(open("summary.json"))["configs"]))') configurations"
}

profiles() {
  for p in "${PROFILES[@]}"; do
    rig "./profile_one.sh $p"
  done
  rig "python3 analyze_profile.py profiles/*.speedscope.json"
}

copy() {
  mkdir -p results profiles
  docker cp longs-rig:/home/dev/pybench/results/. results/
  docker cp longs-rig:/home/dev/pybench/profiles/. profiles/
}

[ $# -gt 0 ] || set -- summary profiles copy
for step in "$@"; do
  echo "== $step"
  "$step"
done
