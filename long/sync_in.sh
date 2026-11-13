#!/bin/bash
# Copies the bench code (not venvs or results) into the rig's ~/pybench, where it runs.
set -euo pipefail
cd "$(dirname "$0")"
docker exec -u dev longs-rig mkdir -p /home/dev/pybench
COPYFILE_DISABLE=1 tar --no-mac-metadata --exclude=.venv --exclude=results --exclude=profiles -cf - . | docker exec -i -u dev longs-rig tar --warning=no-unknown-keyword -xf - -C /home/dev/pybench
