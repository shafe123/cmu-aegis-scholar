# syntax=docker/dockerfile:1
# Multi-stage build to reduce final image size
# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry and export plugin
RUN curl -sSL https://install.python-poetry.org | python3 - 
ENV PATH="/root/.local/bin:$PATH"
RUN poetry self add poetry-plugin-export

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Update lock file with Python 3.12, then export
RUN poetry lock
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --only main

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Copy requirements from builder
COPY --from=builder /app/requirements.txt .

# Upgrade pip first to fix CVE-2025-8869 (symlink following in tar extraction, fixed in 25.3)
RUN pip install --upgrade "pip>=25.3"

# Install all dependencies with cache mount
# FastEmbed uses ONNX Runtime (much smaller than PyTorch)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy application code
COPY app/ ./app/

# Set cache directories for models (will be persisted via volume mount)
ENV TRANSFORMERS_CACHE=/app/.cache/transformers
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence-transformers

EXPOSE 8002
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
