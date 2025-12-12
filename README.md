# infinite-search Docker setup

This repository contains `main.py` (the active worker) and a small Docker setup to run it.
The container includes a startup wrapper (`/app/run.sh`) that prefers a writable host mount at `/data` for persistence.

## What this guide shows
- How to build the image
- How to start a container that persists checkpoints and solutions to a host folder
- How to inspect logs and verify files
- Quick troubleshooting tips

## Prerequisites
- Docker installed and working.

## 1) Build the image

```bash
docker build -t infinite-search:local .
```

## 2) Prepare a host directory for persistence

```bash
mkdir -p ./data/container_0
chmod 0777 ./data/container_0   # dev/test only; pick tighter perms in production
```

## 3) Start the container (recommended — detached)

The container's entrypoint is `/app/run.sh`. The wrapper will copy `/app/main.py` -> `/data/main.py` when `/data` is writable and then run it. This keeps the image files intact while persisting checkpoints/solutions.

```bash
docker run -d \
  --name infinite-search-0 \
  --restart unless-stopped \
  --cpus=2.0 \
  --memory=4g \
  -v "$(pwd)/data/container_0":/data \
  -e CONTAINER_ID=0 \
  -e TOTAL_CONTAINERS=10000 \
  -e CHECK_INTERVAL=1000 \
  infinite-search:local
```

## 4) Follow logs

```bash
docker logs -f infinite-search-0
```

Look for periodic progress lines, for example:

```
[2025-12-12 ...] k=..., checked≈..., rate≈.../s
```

## 5) Verify persisted files on the host

```bash
ls -lah ./data/container_0
# expected: main.py (copied), checkpoint_0.json, solutions.txt (if any found)
```

## 6) Run interactively (debug)

```bash
docker run --rm -it -v "$(pwd)/data/container_0":/data -e CONTAINER_ID=0 infinite-search:local /bin/sh
# or
docker exec -it infinite-search-0 /bin/sh
```

## 7) Stop and remove

```bash
docker stop infinite-search-0
docker rm infinite-search-0
```

## Troubleshooting
- If logs show `python: can't open file '/app/main.py'`: you mounted over `/app`. Mount to `/data` only.
- If nothing is written to `./data/container_0`: check permissions and Docker file sharing settings. For quick dev testing use `chmod 0777 ./data/container_0`.
- If healthcheck fails: the container checks the checkpoint file mod time. You can lower `CHECK_INTERVAL` during tests so the worker writes checkpoints more often.

## Environment variables
- `CONTAINER_ID` — numeric ID used for partitioning (set per-instance).
- `TOTAL_CONTAINERS` — total number of parallel containers for partitioning.
- `CHECK_INTERVAL` — how often the worker saves progress (in worker steps).
- `CHECKPOINT_FILE`, `SOLUTIONS_FILE` — to explicitly point to different file paths.

## Compose and production notes
- The included `docker-compose.yml` demonstrates mounting `./data/container_0` to `/data` and resource limits; use it for local testing.
- For Charity Engine or Kubernetes, mount a persistent volume to `/data` (PVC or object storage) and set appropriate resource limits.

## Extras I can add
- a one-line `start.sh` to build+run the container with defaults
- a Kubernetes Deployment + PVC manifest using the same `/data` approach

## Files of interest
- `main.py` — worker script
- `run.sh` — wrapper entrypoint (copies to /data and runs)
- `healthcheck.sh` — healthcheck script
