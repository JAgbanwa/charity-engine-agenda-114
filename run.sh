#!/bin/sh
set -e

# Startup wrapper: try to use mounted /data for persistence. If /data is not writable,
# fall back to running the in-image /app/main.py so startup doesn't fail when mounts
# are read-only for the container user.

# Ensure /data exists
mkdir -p /data 2>/dev/null || true

APP_IN_IMAGE="/app/main.py"
APP_IN_DATA="/data/main.py"

echo "[entrypoint] CONTAINER_ID=${CONTAINER_ID:-unset}"

# Check we have an in-image main.py
if [ ! -f "$APP_IN_IMAGE" ]; then
  echo "[entrypoint] ERROR: $APP_IN_IMAGE not found in image"
  exit 1
fi

# Test if /data is writable
if touch /data/.write_test 2>/dev/null; then
  rm -f /data/.write_test
  echo "[entrypoint] /data is writable — using persistent data dir"
  # Copy main.py into data dir if it's missing
  if [ ! -f "$APP_IN_DATA" ]; then
    cp "$APP_IN_IMAGE" "$APP_IN_DATA" || true
    echo "[entrypoint] copied main.py -> /data/main.py"
  fi
  # Set defaults for checkpoint/solutions
  export CHECKPOINT_FILE="${CHECKPOINT_FILE:-/data/checkpoint_${CONTAINER_ID:-0}.json}"
  export SOLUTIONS_FILE="${SOLUTIONS_FILE:-/data/solutions.txt}"
  echo "[entrypoint] CHECKPOINT_FILE=$CHECKPOINT_FILE"
  echo "[entrypoint] SOLUTIONS_FILE=$SOLUTIONS_FILE"
  exec python "$APP_IN_DATA"
else
  echo "[entrypoint] /data not writable by this user; falling back to in-image /app"
  export CHECKPOINT_FILE="${CHECKPOINT_FILE:-/app/checkpoint_${CONTAINER_ID:-0}.json}"
  export SOLUTIONS_FILE="${SOLUTIONS_FILE:-/app/solutions.txt}"
  echo "[entrypoint] CHECKPOINT_FILE=$CHECKPOINT_FILE"
  echo "[entrypoint] SOLUTIONS_FILE=$SOLUTIONS_FILE"
  exec python "$APP_IN_IMAGE"
fi
