#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PYTHON="${PYTHON:-python3}"
PROJECT_PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
RUN_ROOT="${1:-${RUN_ROOT:-data/runs}}"
OUTPUT="${2:-${RUN_ROOT}/aggregate.json}"

PYTHONPATH="${PROJECT_PYTHONPATH}" "${PYTHON}" -m agentic_sim.cli aggregate-runs \
  "${RUN_ROOT}" \
  --output "${OUTPUT}"
