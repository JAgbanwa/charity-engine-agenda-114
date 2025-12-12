# infinite-search Docker setup

This repository contains `main.py` (the active script) and a production-ready Docker configuration to run it safely in an orchestrated environment (Charity Engine, Kubernetes, Docker Swarm, etc.).


Quick build (local):

```bash
# From repository root
docker build -t infinite-search:local .
```

Run (example, mapping a host directory for persistence). The container prefers a writable `/data` mount for checkpoints and solutions; it will copy `main.py` into `/data` on startup if `/data` is writable. This avoids masking the image's `/app` directory.

Example run (recommended):

```bash
docker run -d \
  --name infinite-search-0 \
  --restart unless-stopped \
  --cpus=2.0 \
  --memory=8g \
  --memory-swap=8g \
  --ulimit nofile=65536:65536 \
  --pids-limit=2048 \
  -v $(pwd)/data/container_0:/data \
  -e CONTAINER_ID=0 \
  -e TOTAL_CONTAINERS=10000 \
  -e CHECK_INTERVAL=1000 \
  infinite-search:local
```

If `/data` is writable the container will set `CHECKPOINT_FILE` and `SOLUTIONS_FILE` to files under `/data` automatically. To explicitly override these paths, pass env vars:

```bash
docker run --rm -v $(pwd)/data/container_0:/data \
  -e CONTAINER_ID=0 \
  -e CHECKPOINT_FILE=/data/checkpoint_0.json \
  -e SOLUTIONS_FILE=/data/solutions.txt \
  infinite-search:local
```
```

Notes:
- Keep `/app` persistent (host path or network storage). Back up `solutions.txt` and checkpoint files.
- Adjust CPU/memory for production. If Charity Engine runs many containers, reduce per-container resources.
- For Kubernetes, replace compose resource specs with `resources.requests`/`limits` and a PVC for `/app`.
