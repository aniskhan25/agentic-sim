#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH="${PYTHONPATH:-src}" python -m multiagent_demo.cli run --steps "${1:-4}"
