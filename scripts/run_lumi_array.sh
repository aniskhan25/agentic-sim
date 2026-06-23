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

for _env_file in "${ROOT_DIR}/.env.local" "${ROOT_DIR}/.env"; do
  if [[ -f "${_env_file}" ]]; then
    set -a; source "${_env_file}"; set +a
  fi
done

if [[ -d "${ROOT_DIR}/.venv" ]]; then
  source "${ROOT_DIR}/.venv/bin/activate"
fi

if [[ "${LOAD_CRAY_PYTHON:-1}" == "1" ]] && command -v module >/dev/null 2>&1; then
  module load cray-python
fi

PYTHON="${PYTHON:-python3}"
PROJECT_PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
TASK_ID="${SLURM_ARRAY_TASK_ID:-0}"
JOB_ID="${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-local}}"

# Build config list from SWEEP_MANIFEST (generate-sweep output), a space-separated
# CONFIG_LIST, or fall back to the default four built-in configs.
if [[ -n "${SWEEP_MANIFEST:-}" ]]; then
  mapfile -t CONFIGS < <(
    PYTHONPATH="${PROJECT_PYTHONPATH}" "${PYTHON}" -c \
      "import json,sys; [print(c) for c in json.load(open(sys.argv[1]))['configs']]" \
      "${SWEEP_MANIFEST}"
  )
else
  CONFIG_LIST="${CONFIG_LIST:-configs/storm_small.json configs/supply_chain_small.json configs/storm_scale.json configs/supply_chain_scale.json}"
  read -r -a CONFIGS <<< "${CONFIG_LIST}"
fi

if (( TASK_ID < 0 || TASK_ID >= ${#CONFIGS[@]} )); then
  echo "No config for SLURM_ARRAY_TASK_ID=${TASK_ID}; ${#CONFIGS[@]} config(s) available" >&2
  exit 2
fi

CONFIG="${CONFIG:-${CONFIGS[$TASK_ID]}}"
# Resolve relative paths against ROOT_DIR so the CLI always gets an absolute path
if [[ "${CONFIG}" != /* ]]; then
  CONFIG="${ROOT_DIR}/${CONFIG}"
fi
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
