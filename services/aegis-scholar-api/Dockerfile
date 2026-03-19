# syntax=docker/dockerfile:1
# Multi-stage build
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry and export plugin
RUN curl -sSL https://install.python-poetry.org | python3 - 
ENV PATH="/root/.local/bin:$PATH"
RUN poetry self add poetry-plugin-export

COPY pyproject.toml poetry.lock* ./
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --only main

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Install curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/requirements.txt .

# Use BuildKit cache mount for pip downloads
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
