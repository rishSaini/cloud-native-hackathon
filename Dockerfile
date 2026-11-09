FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY frontend frontend
# Kept in the image so a one-off Kubernetes Job can load data into Elasticsearch.
COPY scripts/ingest.py scripts/ingest.py
COPY scripts/seed_demo.py scripts/seed_demo.py
COPY data data

ARG APP_VERSION=dev
ENV PORT=8080 APP_VERSION=$APP_VERSION PYTHONUNBUFFERED=1
WORKDIR /app/backend
# A numeric user, so runAsNonRoot can check it.
USER 1000
EXPOSE 8080
CMD ["./start.sh"]
