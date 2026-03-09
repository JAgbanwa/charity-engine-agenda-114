#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# submit.sh — Submit batches of x^3+y^3+z^3=114 search jobs to
#              Charity Engine using ce-cli + GNU Parallel.
#
# Prerequisites:
#   1) ce-cli installed    (see: install-ce-cli.sh)
#   2) GNU parallel         (brew install parallel  /  apt install parallel)
#   3) CE_AUTH_KEY env var   (your Charity Engine auth key)
#
# Usage:
#   export CE_AUTH_KEY="your-key-here"
#
#   # Submit 100 test jobs (n = 0 .. 9,999,999)
#   ./submit.sh --jobs 100
#
#   # Submit 10,000 jobs covering n = 0 .. 999,999,999
#   ./submit.sh --jobs 10000
#
#   # Custom range: start at n=5000000, 500 jobs
#   ./submit.sh --range-start 5000000 --jobs 500
#
#   # Dry run (print commands without executing)
#   ./submit.sh --jobs 10 --dry-run
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────
IMAGE="jagbanwa/ce-114-search"       # Docker Hub image
COUNT=100000                          # n-values per job (~1 hour on avg CPU)
RANGE_START=0                         # first n value
JOBS=100                              # number of jobs to submit
PARALLEL_SLOTS=20                     # concurrent ce-cli submissions
DRY_RUN=false
USE_INPUT_FILE=false                  # if true, uses docker:python:3.11-slim + worker.py as input
# Elliptic curve mode parameters
ELLIPTIC=false                        # if true, submit elliptic_worker.py jobs
M_COUNT=1000                          # m-steps per elliptic job
X_RANGE=1000000                       # x-range per m value (elliptic mode)
M_START_IDX=0                         # first m-step index (elliptic mode)

# ── Parse args ────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --jobs)        JOBS="$2";          shift 2 ;;
    --count)       COUNT="$2";         shift 2 ;;
    --range-start) RANGE_START="$2";   shift 2 ;;
    --parallel)    PARALLEL_SLOTS="$2";shift 2 ;;
    --image)       IMAGE="$2";         shift 2 ;;
    --dry-run)     DRY_RUN=true;       shift ;;
    --use-input-file) USE_INPUT_FILE=true; shift ;;
    --elliptic)    ELLIPTIC=true;      shift ;;
    --m-count)     M_COUNT="$2";       shift 2 ;;
    --x-range)     X_RANGE="$2";       shift 2 ;;
    --m-start)     M_START_IDX="$2";   shift 2 ;;
    -h|--help)
      head -25 "$0" | tail -20
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Validate ──────────────────────────────────────────────────────────
if [[ -z "${CE_AUTH_KEY:-}" ]]; then
  echo "ERROR: Set CE_AUTH_KEY environment variable first."
  echo "  export CE_AUTH_KEY=\"your-charity-engine-auth-key\""
  exit 1
fi

if ! command -v ce-cli &>/dev/null && [[ ! -x "./ce-cli" ]]; then
  echo "ERROR: ce-cli not found. Install it first (see install-ce-cli.sh)."
  exit 1
fi

# Prefer local ./ce-cli over PATH version
CE_CLI="ce-cli"
if [[ -x "./ce-cli" ]]; then CE_CLI="./ce-cli"; fi

if ! command -v parallel &>/dev/null; then
  echo "WARNING: GNU parallel not found. Falling back to sequential submission."
  PARALLEL_SLOTS=1
fi

RANGE_END=$((RANGE_START + JOBS * COUNT))

if [[ "$ELLIPTIC" == "true" ]]; then
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  Charity Engine — Elliptic curve search  batch submission   ║"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  Image:       $IMAGE"
  echo "║  Jobs:        $JOBS"
  echo "║  m-count/job: $M_COUNT  (actual m step = 108)"
  echo "║  x-range:     ±$X_RANGE"
  echo "║  m-start-idx: $M_START_IDX"
  echo "║  Parallel:    $PARALLEL_SLOTS"
  echo "║  Dry run:     $DRY_RUN"
  echo "╚══════════════════════════════════════════════════════════════╝"
else
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  Charity Engine — x³ + y³ + z³ = 114  batch submission     ║"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  Image:       $IMAGE"
  echo "║  Jobs:        $JOBS"
  echo "║  Count/job:   $COUNT"
  echo "║  Range:       n ∈ [$RANGE_START, $RANGE_END)"
  echo "║  Parallel:    $PARALLEL_SLOTS"
  echo "║  Dry run:     $DRY_RUN"
  echo "╚══════════════════════════════════════════════════════════════╝"
fi
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
  echo "[dry-run] Commands that would be executed:"
  echo ""
fi

# ── Build job list ────────────────────────────────────────────────────
submit_job() {
  local idx=$1
  local cmd
  if [[ "$ELLIPTIC" == "true" ]]; then
    # Elliptic curve search via elliptic_worker.py + compiled C binary
    cmd="$CE_CLI --app \"docker:$IMAGE\" \
      --commandline \"python /app/elliptic_worker.py --m-start $idx --m-count $M_COUNT --x-range $X_RANGE\" \
      --auth \"$CE_AUTH_KEY\""
  elif [[ "$USE_INPUT_FILE" == "true" ]]; then
    # Use generic python image + worker.py as input file
    cmd="$CE_CLI --app \"docker:python:3.11-slim\" \
      --commandline \"python /local/input/worker.py --start $idx --count $COUNT\" \
      --inputfile worker.py \
      --auth \"$CE_AUTH_KEY\""
  else
    # Use custom Docker Hub image (worker.py baked in)
    cmd="$CE_CLI --app \"docker:$IMAGE\" \
      --commandline \"python /app/worker.py --start $idx --count $COUNT\" \
      --auth \"$CE_AUTH_KEY\""
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "  $cmd"
  else
    eval "$cmd"
  fi
}

export -f submit_job
export COUNT M_COUNT X_RANGE IMAGE CE_AUTH_KEY DRY_RUN USE_INPUT_FILE ELLIPTIC CE_CLI

if [[ "$ELLIPTIC" == "true" ]]; then
  # Indices: M_START_IDX, M_START_IDX+1, ..., M_START_IDX+JOBS-1
  M_END_IDX=$((M_START_IDX + JOBS - 1))
  if command -v parallel &>/dev/null && [[ "$PARALLEL_SLOTS" -gt 1 ]]; then
    seq "$M_START_IDX" "$M_END_IDX" | \
      parallel -j "$PARALLEL_SLOTS" submit_job {}
  else
    for idx in $(seq "$M_START_IDX" "$M_END_IDX"); do
      submit_job "$idx"
    done
  fi
  echo ""
  echo "Done. Submitted $JOBS elliptic jobs covering m-idx [$M_START_IDX, $M_END_IDX]."
else
  if command -v parallel &>/dev/null && [[ "$PARALLEL_SLOTS" -gt 1 ]]; then
    seq "$RANGE_START" "$COUNT" "$((RANGE_END - COUNT))" | \
      parallel -j "$PARALLEL_SLOTS" submit_job {}
  else
    for start in $(seq "$RANGE_START" "$COUNT" "$((RANGE_END - COUNT))"); do
      submit_job "$start"
    done
  fi
  echo ""
  echo "Done. Submitted $JOBS jobs covering n ∈ [$RANGE_START, $RANGE_END)."
fi
