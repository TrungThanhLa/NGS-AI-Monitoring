FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN python -m playwright install --with-deps chromium

COPY backend backend

ENV PYTHONPATH=/app

CMD ["/app/backend/entrypoint.sh"]
