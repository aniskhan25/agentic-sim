#!/usr/bin/env bash
#SBATCH --job-name=agentic-sim
#SBATCH --account=project_462000131
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=00:15:00
#SBATCH --output=/scratch/project_462000131/anisrahm/agentic-sim-%j.out

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -d ".venv" ]]; then
  source ".venv/bin/activate"
fi

JOB_ID="${SLURM_JOB_ID:-local}"
CONFIG="${CONFIG:-configs/storm_scale.json}"
if [[ -z "${ARTIFACT_ROOT:-}" ]]; then
  if [[ -w "${ROOT_DIR}" ]]; then
    ARTIFACT_ROOT="${ROOT_DIR}/data"
  elif [[ -w "$(dirname "${ROOT_DIR}")" ]]; then
    ARTIFACT_ROOT="$(dirname "${ROOT_DIR}")/agentic-sim-runs"
  elif [[ -n "${SCRATCH:-}" ]]; then
    ARTIFACT_ROOT="${SCRATCH}/agentic-sim-runs"
  else
    ARTIFACT_ROOT="/tmp/${USER:-agentic-sim}/agentic-sim-runs"
  fi
fi
RUN_DIR="${RUN_DIR:-${ARTIFACT_ROOT}/lumi_run_${JOB_ID}}"
STEPS="${STEPS:-}"
AGENT_REPLICAS="${AGENT_REPLICAS:-}"
MAX_BATCH_SIZE="${MAX_BATCH_SIZE:-}"

mkdir -p "${RUN_DIR}"

args=(run --config "${CONFIG}" --storage-mode sqlite)
args+=(--sqlite-path "${RUN_DIR}/state.sqlite")
args+=(--output "${RUN_DIR}/run.json")

if [[ -n "${STEPS}" ]]; then
  args+=(--steps "${STEPS}")
fi

if [[ -n "${AGENT_REPLICAS}" ]]; then
  args+=(--agent-replicas "${AGENT_REPLICAS}")
fi

if [[ -n "${MAX_BATCH_SIZE}" ]]; then
  args+=(--max-batch-size "${MAX_BATCH_SIZE}")
fi

PYTHONPATH="${PYTHONPATH:-src}" python3 -m agentic_sim.cli "${args[@]}"
