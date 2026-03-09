FROM python:3.11-slim

LABEL org.opencontainers.image.title="ce-114-search"
LABEL org.opencontainers.image.description="Elliptic curve integer solution search (y^2=x^3+A(m)x+B(m)) for Charity Engine"
LABEL maintainer="agbanwajamal03@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install gcc and libm for compiling the C search binary
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" --home /home/appuser appuser \
    && mkdir -p /app /local/output \
    && chmod 1777 /local/output \
    && chown -R appuser:appuser /app

WORKDIR /app

# Elliptic curve C source + compile to /app/elliptic_search (STANDALONE = no BOINC libs)
COPY --chown=appuser:appuser elliptic_search.c /app/elliptic_search.c
RUN gcc -O3 -DSTANDALONE -o /app/elliptic_search /app/elliptic_search.c -lm \
    && chmod +x /app/elliptic_search

# Primary CE worker: drives the compiled C binary for a given m/x range
COPY --chown=appuser:appuser elliptic_worker.py /app/elliptic_worker.py

# Result aggregator
COPY --chown=appuser:appuser collect_results.py /app/collect_results.py

# Legacy x^3+y^3+z^3=114 worker (kept for compatibility)
COPY --chown=appuser:appuser worker.py /app/worker.py

# Local endless runner + support scripts (kept for local Docker testing)
COPY --chown=appuser:appuser elliptic_search_infinite.c /app/elliptic_search_infinite.c
COPY --chown=appuser:appuser main.py /app/main.py
COPY --chown=appuser:appuser run.sh /app/run.sh
COPY --chown=appuser:appuser healthcheck.sh /app/healthcheck.sh

RUN chmod +x /app/healthcheck.sh /app/run.sh

VOLUME ["/data", "/local/output"]

# Run as root so CE's runtime-mounted /local/output is always writable
CMD ["python", "/app/elliptic_worker.py", "--help"]
