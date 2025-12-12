FROM python:3.11-slim

LABEL org.opencontainers.image.title="infinite-search"
LABEL org.opencontainers.image.description="Infinite search container for x^3+y^3+z^3=114"
LABEL maintainer="you@example.com"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH

RUN adduser --disabled-password --gecos "" --home /home/appuser appuser \
    && mkdir -p /app \
    && chown -R appuser:appuser /app

WORKDIR /app

# Copy the script and healthcheck
COPY --chown=appuser:appuser infinite_search.py /app/infinite_search.py
# Also copy the user's improved code (filename contains a space)
COPY --chown=appuser:appuser "improved code" "/app/improved code"
COPY --chown=appuser:appuser healthcheck.sh /app/healthcheck.sh

RUN chmod +x /app/healthcheck.sh

VOLUME ["/app"]

USER appuser

# Use exec form so signals are forwarded
HEALTHCHECK --interval=10m --timeout=10s --start-period=3m --retries=3 CMD ["/app/healthcheck.sh"]
## Default: run the improved code file. If you prefer the original script, override the CMD.
CMD ["python", "improved code"]
