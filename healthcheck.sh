#!/bin/sh
# Healthcheck: ensure checkpoint file exists and was updated recently
if [ -z "$CONTAINER_ID" ]; then
  echo "CONTAINER_ID not set"
  exit 1
fi

f="/app/checkpoint_${CONTAINER_ID}.txt"
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
