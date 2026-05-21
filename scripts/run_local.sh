#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH="${PYTHONPATH:-src}" python3 -m agentic_sim.cli run --steps "${1:-4}"
