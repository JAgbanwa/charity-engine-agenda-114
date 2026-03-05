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

if ! command -v ce-cli &>/dev/null; then
  echo "ERROR: ce-cli not found. Install it first (see install-ce-cli.sh)."
  exit 1
fi

if ! command -v parallel &>/dev/null; then
  echo "WARNING: GNU parallel not found. Falling back to sequential submission."
  PARALLEL_SLOTS=1
fi

RANGE_END=$((RANGE_START + JOBS * COUNT))

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
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
  echo "[dry-run] Commands that would be executed:"
  echo ""
fi

# ── Build job list ────────────────────────────────────────────────────
submit_job() {
  local start=$1
  if [[ "$USE_INPUT_FILE" == "true" ]]; then
    # Use generic python image + worker.py as input file
    local cmd="ce-cli --app \"docker:python:3.11-slim\" \
      --commandline \"python /local/input/worker.py --start $start --count $COUNT\" \
      --inputfile worker.py \
      --auth \"$CE_AUTH_KEY\""
  else
    # Use custom Docker Hub image (worker.py baked in)
    local cmd="ce-cli --app \"docker:$IMAGE\" \
      --commandline \"python /app/worker.py --start $start --count $COUNT\" \
      --auth \"$CE_AUTH_KEY\""
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "  $cmd"
  else
    eval "$cmd"
  fi
}

export -f submit_job
export COUNT IMAGE CE_AUTH_KEY DRY_RUN USE_INPUT_FILE

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
