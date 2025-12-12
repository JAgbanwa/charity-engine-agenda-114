#!/bin/sh
# Healthcheck: ensure checkpoint file exists and was updated recently
# Uses CHECKPOINT_FILE env var or falls back to /data/checkpoint_{CONTAINER_ID}.json
if [ -n "$CHECKPOINT_FILE" ]; then
  f="$CHECKPOINT_FILE"
else
  f="/data/checkpoint_${CONTAINER_ID:-0}.json"
fi

[ -f "$f" ] || exit 1

t=$(date +%s)
# Prefer GNU stat (-c %Y), fall back to BSD stat (-f %m)
if stat -c %Y "$f" >/dev/null 2>&1; then
  mt=$(stat -c %Y "$f")
else
  mt=$(stat -f %m "$f")
fi

# Fail if last modification > 2 hours (7200 seconds)
if [ $((t - mt)) -gt 7200 ]; then
  echo "checkpoint too old"
  exit 1
fi

exit 0
