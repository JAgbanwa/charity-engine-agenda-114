FROM python:3.11-slim

LABEL org.opencontainers.image.title="infinite-search"
LABEL org.opencontainers.image.description="Infinite search container for x^3+y^3+z^3=114"
LABEL maintainer="agbanwajamal03@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH

RUN adduser --disabled-password --gecos "" --home /home/appuser appuser \
    && mkdir -p /app \
    && chown -R appuser:appuser /app

WORKDIR /app

# Copy the active entrypoint script, wrapper and healthcheck
COPY --chown=appuser:appuser main.py /app/main.py
COPY --chown=appuser:appuser run.sh /app/run.sh
COPY --chown=appuser:appuser healthcheck.sh /app/healthcheck.sh

RUN chmod +x /app/healthcheck.sh /app/run.sh

# Persistent data mount (for checkpoints/solutions)
VOLUME ["/data"]

USER appuser

# Use exec form so signals are forwarded. The wrapper will prefer /data for persistence.
HEALTHCHECK --interval=10m --timeout=10s --start-period=3m --retries=3 CMD ["/app/healthcheck.sh"]
CMD ["/app/run.sh"]
