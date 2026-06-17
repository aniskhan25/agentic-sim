#!/usr/bin/env bash
#SBATCH --job-name=agentic-sim-array
#SBATCH --account=project_462000131
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --array=0-3
#SBATCH --output=/scratch/project_462000131/anisrahm/agentic-sim-runs/logs/%x-%A_%a.out

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -d ".venv" ]]; then
  source ".venv/bin/activate"
fi

PYTHON="${PYTHON:-python3}"
PROJECT_PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
TASK_ID="${SLURM_ARRAY_TASK_ID:-0}"
JOB_ID="${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-local}}"
CONFIG_LIST="${CONFIG_LIST:-configs/storm_small.json configs/supply_chain_small.json configs/storm_scale.json configs/supply_chain_scale.json}"
read -r -a CONFIGS <<< "${CONFIG_LIST}"

if (( TASK_ID < 0 || TASK_ID >= ${#CONFIGS[@]} )); then
  echo "No config for SLURM_ARRAY_TASK_ID=${TASK_ID}; CONFIG_LIST has ${#CONFIGS[@]} entries" >&2
  exit 2
fi

CONFIG="${CONFIG:-${CONFIGS[$TASK_ID]}}"
CONFIG_NAME="$(basename "${CONFIG}" .json)"

if [[ -z "${ARTIFACT_ROOT:-}" ]]; then
  if [[ -n "${SCRATCH:-}" ]]; then
    ARTIFACT_ROOT="${SCRATCH}/agentic-sim-runs"
  else
    ARTIFACT_ROOT="/scratch/project_462000131/anisrahm/agentic-sim-runs"
  fi
fi

RUN_ROOT="${RUN_ROOT:-${ARTIFACT_ROOT}/array_${JOB_ID}}"
RUN_DIR="${RUN_DIR:-${RUN_ROOT}/${TASK_ID}_${CONFIG_NAME}}"
STEPS="${STEPS:-}"
AGENT_REPLICAS="${AGENT_REPLICAS:-}"
MAX_BATCH_SIZE="${MAX_BATCH_SIZE:-}"
BACKEND="${BACKEND:-}"
AITTA_WARMUP="${AITTA_WARMUP:-0}"
AITTA_WARMUP_TIMEOUT="${AITTA_WARMUP_TIMEOUT:-900}"
AITTA_WARMUP_INTERVAL="${AITTA_WARMUP_INTERVAL:-30}"

mkdir -p "${RUN_DIR}" "${RUN_ROOT}"

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

if [[ -n "${BACKEND}" ]]; then
  args+=(--backend "${BACKEND}")
fi

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
PYTHONPATH="${PROJECT_PYTHONPATH}" "${PYTHON}" -m agentic_sim.cli aggregate-runs \
  "${RUN_ROOT}" \
  --output "${RUN_ROOT}/aggregate.json"
