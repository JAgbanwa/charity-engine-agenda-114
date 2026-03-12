#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# submit.sh — Submit batches of elliptic curve search jobs to
#              Charity Engine using ce-cli + GNU Parallel.
#
# Supports four modes:
#   default    — legacy x^3+y^3+z^3=114 worker (worker.py)
#   --elliptic — 128-bit elliptic_worker.py (m up to ~10^9)
#   --gmp      — arbitrary-precision worker_gmp.py (m up to 10^30)
#   --pari     — PROVABLY COMPLETE: PARI/GP ellintegralpoints() (recommended)
#
# Prerequisites:
#   1) ce-cli installed    (see: install-ce-cli.sh)
#   2) GNU parallel         (brew install parallel  /  apt install parallel)
#   3) CE_AUTH_KEY env var   (your Charity Engine auth key)
#
# Usage:
#   export CE_AUTH_KEY="your-key-here"
#
#   # GMP mode — submit 200 jobs from Tier 0 (m=0..21,599,892)
#   ./submit.sh --gmp --jobs 200 --m-count 1000 --x-window 1000000
#
#   # GMP mode — Tier 3: m starting at 10^12
#   ./submit.sh --gmp --jobs 500 --m-start-val 1000000000000 \
#               --m-count 100 --x-window 1000000000000
#
#   # Legacy elliptic worker (128-bit, faster for small m)
#   ./submit.sh --elliptic --jobs 100 --m-count 1000 --x-range 1000000
#
#   # PARI mode — provably-complete algorithm (recommended for real search)
#   ./submit.sh --pari --jobs 200 --m-count 50 --m-start-val 108
#
#   # PARI mode at large m (Tier 5)
#   ./submit.sh --pari --jobs 500 --m-count 20 --m-start-val 1000000000000000000
#
#   # Dry run (print commands without executing)
#   ./submit.sh --pari --jobs 10 --dry-run
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
GMP=false                             # if true, submit worker_gmp.py (10^30 capable)
PARI=false                            # if true, submit worker_pari.py (PARI/GP, provably complete)
EC19N=false                           # if true, submit ec19n_worker.py (new equation)
EC19N_FOREVER=false                   # if true, continuously submit EC19N batches forever
M_COUNT=50                            # m-steps per elliptic/GMP/PARI job
N_COUNT=500                           # n-values per ec19n job
N_START_VAL=1                         # first |n| value for ec19n mode
N_NEGATIVES=false                     # if true, pass --negatives to ec19n_worker
STATE_FILE=".ec19n_state"             # checkpoint for --ec19n-forever mode
SLEEP_SECONDS=3                       # pause between forever-batches
X_RANGE=1000000                       # x-range per m value (elliptic mode)
X_WINDOW=1000000                      # x half-window (GMP mode)
M_START_IDX=0                         # first m-step index (elliptic mode)
M_START_VAL=0                         # first m value for GMP mode (arbitrary integer)

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
    --gmp)         GMP=true;           shift ;;
    --pari)        PARI=true;          shift ;;
    --ec19n)       EC19N=true;         shift ;;
    --ec19n-forever) EC19N=true; EC19N_FOREVER=true; shift ;;
    --n-count)     N_COUNT="$2";       shift 2 ;;
    --n-start-val) N_START_VAL="$2";   shift 2 ;;
    --n-negatives) N_NEGATIVES=true;   shift ;;
    --state-file)  STATE_FILE="$2";    shift 2 ;;
    --sleep)       SLEEP_SECONDS="$2"; shift 2 ;;
    --m-count)     M_COUNT="$2";       shift 2 ;;
    --x-range)     X_RANGE="$2";       shift 2 ;;
    --x-window)    X_WINDOW="$2";      shift 2 ;;
    --m-start)     M_START_IDX="$2";   shift 2 ;;
    --m-start-val) M_START_VAL="$2";   shift 2 ;;
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

if [[ "$EC19N" == "true" ]]; then
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  Charity Engine — EC19N  y²=x³+1296n²x²+15552n³x+46656n⁴−19n ║"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  Image:       $IMAGE"
  echo "║  Worker:      ec19n_worker.py  (PARI/GP ellintegralpoints)"
  echo "║  Algorithm:   Tzanakis-de Weger (complete, no missed sols)  ║"
  echo "║  Jobs:        $JOBS"
  echo "║  n-count/job: $N_COUNT"
  echo "║  n-start-val: $N_START_VAL"
  echo "║  negatives:   $N_NEGATIVES"
  echo "║  forever:     $EC19N_FOREVER"
  echo "║  state-file:  $STATE_FILE"
  echo "║  Parallel:    $PARALLEL_SLOTS"
  echo "║  Dry run:     $DRY_RUN"
  echo "╚══════════════════════════════════════════════════════════════╝"
elif [[ "$PARI" == "true" ]]; then
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  Charity Engine — PARI/GP  PROVABLY COMPLETE  integer pts  ║"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  Image:       $IMAGE"
  echo "║  Worker:      worker_pari.py  (PARI/GP ellintegralpoints)"
  echo "║  Algorithm:   Tzanakis-de Weger (complete, no missed sols)  ║"
  echo "║  Jobs:        $JOBS"
  echo "║  m-count/job: $M_COUNT  (step = 108)"
  echo "║  m-start-val: $M_START_VAL"
  echo "║  Parallel:    $PARALLEL_SLOTS"
  echo "║  Dry run:     $DRY_RUN"
  echo "╚══════════════════════════════════════════════════════════════╝"
elif [[ "$GMP" == "true" ]]; then
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  Charity Engine — GMP Elliptic search  (m up to 10^30)     ║"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  Image:       $IMAGE"
  echo "║  Worker:      worker_gmp.py  (binary: elliptic_gmp + GMP)"
  echo "║  Jobs:        $JOBS"
  echo "║  m-count/job: $M_COUNT  (step = 108)"
  echo "║  x-window:    ±$X_WINDOW (+ auto pivot windows)"
  echo "║  m-start-val: $M_START_VAL"
  echo "║  Parallel:    $PARALLEL_SLOTS"
  echo "║  Dry run:     $DRY_RUN"
  echo "╚══════════════════════════════════════════════════════════════╝"
elif [[ "$ELLIPTIC" == "true" ]]; then
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  Charity Engine — Elliptic curve search  (128-bit)         ║"
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
  if [[ "$EC19N" == "true" ]]; then
    # EC19N worker — provably complete PARI/GP search for new equation
    local neg_flag=""
    [[ "$N_NEGATIVES" == "true" ]] && neg_flag=" --negatives"
    cmd="$CE_CLI --app \"docker:$IMAGE\" \\
      --commandline \"python /app/ec19n_worker.py --n-start $idx --n-count $N_COUNT$neg_flag\" \\
      --auth \"$CE_AUTH_KEY\""
  elif [[ "$PARI" == "true" ]]; then
    # PARI worker — provably complete using PARI/GP ellintegralpoints()
    # Writes work unit as 'in' file on the container
    cmd="$CE_CLI --app \"docker:$IMAGE\" \\
      --commandline \"python /app/worker_pari.py --m-start $idx --m-count $M_COUNT\" \\
      --auth \"$CE_AUTH_KEY\""
  elif [[ "$GMP" == "true" ]]; then
    # GMP worker — supports m up to 10^30 via arbitrary-precision C+GMP binary
    # idx here is the actual m start value (bignum-safe as shell variable)
    cmd="$CE_CLI --app \"docker:$IMAGE\" \
      --commandline \"python /app/worker_gmp.py --m-start $idx --m-count $M_COUNT --x-window $X_WINDOW\" \
      --auth \"$CE_AUTH_KEY\""
  elif [[ "$ELLIPTIC" == "true" ]]; then
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
export COUNT M_COUNT X_RANGE X_WINDOW IMAGE CE_AUTH_KEY DRY_RUN USE_INPUT_FILE ELLIPTIC GMP PARI EC19N N_COUNT N_NEGATIVES CE_CLI

if [[ "$EC19N" == "true" ]]; then
  if [[ "$EC19N_FOREVER" == "true" ]]; then
    # Continuous EC19N mode: repeatedly submit JOBS jobs, then advance N_START_VAL.
    # State file format: single integer (next N_START_VAL)
    if [[ -f "$STATE_FILE" ]]; then
      N_START_VAL="$(tr -d '[:space:]' < "$STATE_FILE")"
      echo "[ec19n-forever] Resuming from state file: next n-start=$N_START_VAL"
    else
      echo "$N_START_VAL" > "$STATE_FILE"
      echo "[ec19n-forever] Initializing state file at n-start=$N_START_VAL"
    fi

    while true; do
      BATCH_START="$N_START_VAL"
      BATCH_MAX=$((BATCH_START + JOBS * N_COUNT - 1))
      echo ""
      echo "[ec19n-forever] Submitting batch: |n| in [$BATCH_START, $BATCH_MAX]"

      if command -v parallel &>/dev/null && [[ "$PARALLEL_SLOTS" -gt 1 ]]; then
        python3 -c "
start = $BATCH_START
step  = $N_COUNT
for i in range($JOBS):
    print(start + i * step)
" | parallel -j "$PARALLEL_SLOTS" submit_job {}
      else
        python3 -c "
start = $BATCH_START
step  = $N_COUNT
for i in range($JOBS):
    print(start + i * step)
" | while read n_val; do
          submit_job "$n_val"
        done
      fi

      N_START_VAL=$((BATCH_MAX + 1))
      echo "$N_START_VAL" > "$STATE_FILE"
      echo "[ec19n-forever] Batch done. Next n-start=$N_START_VAL (saved to $STATE_FILE)"

      if [[ "$DRY_RUN" == "true" ]]; then
        echo "[ec19n-forever] Dry-run complete; stopping after one batch."
        break
      fi

      sleep "$SLEEP_SECONDS"
    done

    echo ""
    echo "Done. EC19N forever loop exited."
    exit 0
  fi

  # EC19N mode: n values stride by N_COUNT per job
  if command -v parallel &>/dev/null && [[ "$PARALLEL_SLOTS" -gt 1 ]]; then
    python3 -c "
start = $N_START_VAL
step  = $N_COUNT
for i in range($JOBS):
    print(start + i * step)
" | parallel -j "$PARALLEL_SLOTS" submit_job {}
  else
    python3 -c "
start = $N_START_VAL
step  = $N_COUNT
for i in range($JOBS):
    print(start + i * step)
" | while read n_val; do
      submit_job "$n_val"
    done
  fi
  echo ""
  MAX_N=$((N_START_VAL + JOBS * N_COUNT - 1))
  echo "Done. Submitted $JOBS EC19N jobs (|n| ∈ [$N_START_VAL, $MAX_N]).  negatives=$N_NEGATIVES"
elif [[ "$PARI" == "true" ]]; then
  # PARI mode: m values increment by M_COUNT * 108 per job
  JOB_SPAN=$((M_COUNT * 108))
  if command -v parallel &>/dev/null && [[ "$PARALLEL_SLOTS" -gt 1 ]]; then
    python3 -c "
start = $M_START_VAL
step  = $JOB_SPAN
for i in range($JOBS):
    print(start + i * step)
" | parallel -j "$PARALLEL_SLOTS" submit_job {}
  else
    python3 -c "
start = $M_START_VAL
step  = $JOB_SPAN
for i in range($JOBS):
    print(start + i * step)
" | while read m_val; do
      submit_job "$m_val"
    done
  fi
  echo ""
  echo "Done. Submitted $JOBS PARI jobs (m_start=$M_START_VAL, span=$JOB_SPAN per job)."
elif [[ "$GMP" == "true" ]]; then
  # GMP mode: m values increment by M_COUNT * 108 per job
  JOB_SPAN=$((M_COUNT * 108))
  if command -v parallel &>/dev/null && [[ "$PARALLEL_SLOTS" -gt 1 ]]; then
    # Use printf to generate bignum-safe m-start values
    python3 -c "
start = $M_START_VAL
step  = $JOB_SPAN
for i in range($JOBS):
    print(start + i * step)
" | parallel -j "$PARALLEL_SLOTS" submit_job {}
  else
    python3 -c "
start = $M_START_VAL
step  = $JOB_SPAN
for i in range($JOBS):
    print(start + i * step)
" | while read m_val; do
      submit_job "$m_val"
    done
  fi
  echo ""
  echo "Done. Submitted $JOBS GMP jobs (m_start=$M_START_VAL, span=$JOB_SPAN per job)."
elif [[ "$ELLIPTIC" == "true" ]]; then
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
