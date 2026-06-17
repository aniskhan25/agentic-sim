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

PYTHON="${PYTHON:-python3}"
PROJECT_PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
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
AITTA_WARMUP="${AITTA_WARMUP:-0}"
AITTA_WARMUP_TIMEOUT="${AITTA_WARMUP_TIMEOUT:-900}"
AITTA_WARMUP_INTERVAL="${AITTA_WARMUP_INTERVAL:-30}"

mkdir -p "${RUN_DIR}"

if [[ "${AITTA_WARMUP}" == "1" ]]; then
  PYTHONPATH="${PROJECT_PYTHONPATH}" "${PYTHON}" -m agentic_sim.cli check-aitta \
    --wait \
    --wait-timeout "${AITTA_WARMUP_TIMEOUT}" \
    --wait-interval "${AITTA_WARMUP_INTERVAL}"
fi

args=(run --config "${CONFIG}" --storage-mode sqlite)
args+=(--sqlite-path "${RUN_DIR}/state.sqlite")
args+=(--output "${RUN_DIR}/run.json")
args+=(--output-dir "${RUN_DIR}/artifacts")

if [[ -n "${STEPS}" ]]; then
  args+=(--steps "${STEPS}")
fi

if [[ -n "${AGENT_REPLICAS}" ]]; then
  args+=(--agent-replicas "${AGENT_REPLICAS}")
fi

if [[ -n "${MAX_BATCH_SIZE}" ]]; then
  args+=(--max-batch-size "${MAX_BATCH_SIZE}")
fi

PYTHONPATH="${PROJECT_PYTHONPATH}" "${PYTHON}" -m agentic_sim.cli "${args[@]}"
