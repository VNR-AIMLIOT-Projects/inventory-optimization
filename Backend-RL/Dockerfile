FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for torch and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Layer 1: Heavy stable deps (torch, numpy) — cached independently
# Changing requirements.txt will NOT invalidate this layer
COPY requirements-base.txt .
RUN pip install --no-cache-dir -r requirements-base.txt

# Layer 2: Lightweight app deps — fast to reinstall
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create storage directories
RUN mkdir -p /app/storage/uploads /app/storage/models /app/storage/logs

# Run Alembic migrations then start the server
CMD ["sh", "-c", "cd /app && alembic upgrade head && cd /app/src && uvicorn app:app --host 0.0.0.0 --port 8000"]
