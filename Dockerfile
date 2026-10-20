FROM python:3.12-slim

WORKDIR /app

# Listen on all interfaces inside the container; set DAILYANCHOR_ALLOWED_HOSTS at deploy
# time to the public hostname so the MCP endpoint accepts requests addressed to it.
# FORWARDED_ALLOW_IPS lets uvicorn trust the platform proxy's X-Forwarded-Proto, so the
# dashboard shows the https URL.
ENV PYTHONUNBUFFERED=1 \
    DAILYANCHOR_HOST=0.0.0.0 \
    PORT=8000 \
    DAILYANCHOR_DB=/app/data/dailyanchor.db \
    FORWARDED_ALLOW_IPS=*

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY scripts ./scripts

EXPOSE 8000

# Seeding is idempotent, so a restart with an existing database keeps its data.
CMD ["sh", "-c", "python scripts/seed_data.py --history && exec dailyanchor"]
