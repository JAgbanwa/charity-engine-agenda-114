FROM python:3.11-slim

LABEL org.opencontainers.image.title="ce-114-search"
LABEL org.opencontainers.image.description="Elliptic curve integer solution search (y^2=x^3+A(m)x+B(m)) for Charity Engine"
LABEL maintainer="agbanwajamal03@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install build tools, GMP, and PARI/GP (for provably-complete integral-point search)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libc6-dev libgmp-dev \
        pari-gp \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" --home /home/appuser appuser \
    && mkdir -p /app /local/output \
    && chmod 1777 /local/output \
    && chown -R appuser:appuser /app

WORKDIR /app

# ── Original 128-bit search binary (kept for compatibility) ──────────────
COPY --chown=appuser:appuser elliptic_search.c /app/elliptic_search.c
RUN gcc -O3 -DSTANDALONE -o /app/elliptic_search /app/elliptic_search.c -lm \
    && chmod +x /app/elliptic_search

# ── NEW: GMP-powered binary — handles m, X, Y up to 10^30 and beyond ────
COPY --chown=appuser:appuser elliptic_gmp.c /app/elliptic_gmp.c
RUN gcc -O3 -march=native -DSTANDALONE -o /app/elliptic_gmp \
        /app/elliptic_gmp.c -lgmp -lm \
    && chmod +x /app/elliptic_gmp

# ── NEW: Standalone endless GMP runner (local testing / long-running) ────
COPY --chown=appuser:appuser endless_gmp.c /app/endless_gmp.c
RUN gcc -O3 -march=native -o /app/endless_gmp \
        /app/endless_gmp.c -lgmp -lm \
    && chmod +x /app/endless_gmp

# ── NEW: Sieve + Nagell GMP binary — modular sieve + Nagell divisor method ──
COPY --chown=appuser:appuser sieve_gmp.c /app/sieve_gmp.c
RUN gcc -O3 -march=native -DSTANDALONE -o /app/sieve_gmp \
        /app/sieve_gmp.c -lgmp -lm \
    && chmod +x /app/sieve_gmp

# ── EC19N: y²=x³+1296n²x²+15552n³x+(46656n⁴−19n) — NEW EQUATION ────────
COPY --chown=appuser:appuser ec19n_sieve.c    /app/ec19n_sieve.c
RUN gcc -O3 -march=native -o /app/ec19n_sieve \
        /app/ec19n_sieve.c -lgmp -lm \
    && chmod +x /app/ec19n_sieve

COPY --chown=appuser:appuser ec19n_worker.py  /app/ec19n_worker.py
COPY --chown=appuser:appuser ec19n_curve.gp   /app/ec19n_curve.gp

# ── CE workers ────────────────────────────────────────────────────────────
COPY --chown=appuser:appuser worker_gmp.py       /app/worker_gmp.py
COPY --chown=appuser:appuser worker_pari.py      /app/worker_pari.py
COPY --chown=appuser:appuser elliptic_curve.gp   /app/elliptic_curve.gp
COPY --chown=appuser:appuser elliptic_worker.py  /app/elliptic_worker.py

# Result aggregator
COPY --chown=appuser:appuser collect_results.py /app/collect_results.py

# Legacy x^3+y^3+z^3=114 worker (kept for compatibility)
COPY --chown=appuser:appuser worker.py /app/worker.py

# ── Generators and aggregators ───────────────────────────────────────────
COPY --chown=appuser:appuser wu_generator_big.py /app/wu_generator_big.py
COPY --chown=appuser:appuser collect_results.py  /app/collect_results.py

# ── Legacy support scripts ───────────────────────────────────────────────
COPY --chown=appuser:appuser elliptic_search_infinite.c /app/elliptic_search_infinite.c
COPY --chown=appuser:appuser main.py        /app/main.py
COPY --chown=appuser:appuser run.sh         /app/run.sh
COPY --chown=appuser:appuser healthcheck.sh /app/healthcheck.sh
COPY --chown=appuser:appuser worker.py      /app/worker.py

RUN chmod +x /app/healthcheck.sh /app/run.sh

VOLUME ["/data", "/local/output"]

# Default: PARI worker (provably-complete algorithm).  Override for CE jobs:
#   python /app/worker_pari.py --from-file in
#   python /app/worker_pari.py --m-start 0 --m-count 1000
#   python /app/worker_gmp.py  --m-start 0 --m-count 1000 --x-window 1000000
CMD ["python", "/app/worker_pari.py", "--help"]
