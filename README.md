# x³ + y³ + z³ = 114 — Charity Engine Search

Distributed search for integer solutions to **x³ + y³ + z³ = 114** using the [Charity Engine](https://www.charityengine.com) crowdsourced compute grid.

Based on the closed-form parametrisation:

$$x = -\alpha + \sqrt{(\alpha+6n)^2 + \frac{36n^3 - 19}{\alpha}}, \quad y = 2\alpha + 6n, \quad z = -\alpha - \sqrt{(\alpha+6n)^2 + \frac{36n^3 - 19}{\alpha}}$$

For each integer **n**, we factor **D = 36n³ − 19**, enumerate its divisors as α candidates, and test whether **x(α, n)** is an integer.

**Paper**: [Closed-form formulas on the sums of three cubes for k = 114, 192](https://figshare.com/articles/preprint/Closed_form_formulas_on_the_sums_of_three_cubes_for_k_114_192_/30509981?file=60106334)

---

## Architecture

| File | Purpose |
|------|---------|
| `worker.py` | **CE finite-job worker** — searches a range `[start, start+count)`, writes results to `/local/output/` |
| `main.py` | Local endless worker (for standalone Docker testing) |
| `submit.sh` | Batch submission helper (ce-cli + GNU Parallel) |
| `install-ce-cli.sh` | CE CLI installer helper |
| `Dockerfile` | Image for both CE jobs and local testing |
| `docker-compose.yml` | Local single-container testing |
| `run.sh` | Entrypoint wrapper for local endless mode |
| `healthcheck.sh` | Healthcheck for local mode |

---

## Quick Start — Charity Engine

### 1. Register and get your auth key

- Register at: https://dashboard.charityengine.com/users/register
- Your account has pre-approved credits (no runtime charges)
- Get your auth key from the dashboard

### 2. Install the CE CLI

```bash
./install-ce-cli.sh
# or install manually from the CE dashboard
```

### 3. Option A: Use the pre-built Docker Hub image

```bash
# Build and push (one-time)
docker build -t jagbanwa/ce-114-search .
docker push jagbanwa/ce-114-search

# Submit a single test job
ce-cli --app "docker:jagbanwa/ce-114-search" \
  --commandline "python /app/worker.py --start 0 --count 1000" \
  --auth YOUR_KEY
```

### 3. Option B: Use generic Python image + worker.py as input

No Docker Hub push needed — CE downloads `worker.py` as an input file:

```bash
ce-cli --app "docker:python:3.11-slim" \
  --commandline "python /local/input/worker.py --start 0 --count 1000" \
  --inputfile worker.py \
  --auth YOUR_KEY
```

### 4. Submit thousands of jobs in parallel

```bash
export CE_AUTH_KEY="your-key-here"

# Dry run first — see what would be submitted
./submit.sh --jobs 10 --dry-run

# Submit 100 test jobs (n = 0 .. 9,999,999)
./submit.sh --jobs 100

# Go big: 10,000 jobs (n = 0 .. 999,999,999)
./submit.sh --jobs 10000

# Start deeper in the search space
./submit.sh --range-start 1000000000 --jobs 5000
```

### 5. Check results

Monitor progress on the [CE Dashboard](https://dashboard.charityengine.com). Each job writes:

- `result.json` — range searched, timing, solutions (if any)
- `SOLUTION.txt` — **only created if a solution is found**

---

## Job Sizing

Each job should run for ~1 hour on an average CPU. The default `--count 100000` is calibrated for moderate n-ranges. For very large n (> 10⁸), factoring D takes longer — consider reducing count to 50,000.

| n range | Suggested --count | Approx. time |
|---------|-------------------|--------------|
| 0 – 10⁶ | 100,000 | ~30–60 min |
| 10⁶ – 10⁸ | 100,000 | ~60 min |
| > 10⁸ | 50,000 | ~60 min |

---

## Local Testing

### Test the worker locally (no Docker)

```bash
# Quick test: search n = 0..99
OUTPUT_DIR=./test_output python worker.py --start 0 --count 100
cat ./test_output/result.json
```

### Test with Docker

```bash
docker build -t ce-114-search .
docker run --rm -v "$(pwd)/output:/local/output" ce-114-search \
  python /app/worker.py --start 0 --count 1000
cat ./output/result.json
```

### Local endless mode (original)

```bash
docker compose up -d
docker logs -f infinite-search
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPUT_DIR` | `/local/output` | Where worker.py writes results |
| `CONTAINER_ID` | `0` | Container ID (local endless mode only) |
| `TOTAL_CONTAINERS` | `1000` | Partition count (local endless mode only) |
| `CHECK_INTERVAL` | `5000` | Checkpoint interval (local endless mode only) |

---

## How It Works

For each integer n in the assigned range:

1. Compute **D = 36n³ − 19**
2. Factor D using trial division + Pollard-Rho
3. Enumerate all divisors of D as α candidates
4. For each α, check if the discriminant **(α + 6n)² + D/α** is a perfect square
5. If yes → compute x, y, z and verify x³ + y³ + z³ = 114
6. Both +n and −n are tested

---

## Author

Jamal Agbanwa — [agbanwajamal03@gmail.com](mailto:agbanwajamal03@gmail.com)
