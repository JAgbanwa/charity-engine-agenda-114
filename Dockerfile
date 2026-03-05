FROM python:3.11-slim

LABEL org.opencontainers.image.title="ce-114-search"
LABEL org.opencontainers.image.description="Search for integer solutions to x^3+y^3+z^3=114"
LABEL maintainer="agbanwajamal03@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN adduser --disabled-password --gecos "" --home /home/appuser appuser \
    && mkdir -p /app /local/output \
    && chown -R appuser:appuser /app /local/output

WORKDIR /app

# CE finite-job worker (primary)
COPY --chown=appuser:appuser worker.py /app/worker.py

# Local endless worker + support scripts (kept for local Docker testing)
COPY --chown=appuser:appuser main.py /app/main.py
COPY --chown=appuser:appuser run.sh /app/run.sh
COPY --chown=appuser:appuser healthcheck.sh /app/healthcheck.sh

RUN chmod +x /app/healthcheck.sh /app/run.sh

VOLUME ["/data", "/local/output"]

USER appuser

# Default: run the CE finite worker (override --start/--count via command line)
# For local endless mode, override CMD to /app/run.sh
CMD ["python", "/app/worker.py", "--help"]
