# infinite-search Docker setup

This repository contains `main.py` (the active script) and a production-ready Docker configuration to run it safely in an orchestrated environment (Charity Engine, Kubernetes, Docker Swarm, etc.).


Quick build (local):

```bash
# From repository root
docker build -t infinite-search:local .
```

Run (example, mapping a host directory for persistence). The image defaults to running `main.py` from the repository root. You can override the command at runtime to run a different script if needed.

```bash
docker run -d \
  --name infinite-search-0 \
  --restart unless-stopped \
  --cpus=2.0 \
  --memory=8g \
  --memory-swap=8g \
  --ulimit nofile=65536:65536 \
  --pids-limit=2048 \
  --read-only \
  --tmpfs /tmp:rw,size=256m \
  -v $(pwd)/data/container_0:/app \
  -e CONTAINER_ID=0 \
  -e TOTAL_CONTAINERS=10000 \
  -e JUMP_SIZE=1000000 \
  infinite-search:local


```bash
docker run --rm -v $(pwd)/data/container_0:/app infinite-search:local python main.py
```
```

Notes:
- Keep `/app` persistent (host path or network storage). Back up `solutions.txt` and checkpoint files.
- Adjust CPU/memory for production. If Charity Engine runs many containers, reduce per-container resources.
- For Kubernetes, replace compose resource specs with `resources.requests`/`limits` and a PVC for `/app`.
