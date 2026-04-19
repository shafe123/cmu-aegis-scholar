# syntax=docker/dockerfile:1
# Multi-stage build
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libldap2-dev \
    libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry and export plugin
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"
RUN poetry self add poetry-plugin-export

COPY pyproject.toml poetry.lock* ./

RUN poetry lock
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --only main

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/requirements.txt ./

RUN pip install --upgrade "pip>=25.3"

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY app/ ./app/

COPY entrypoint.sh ./entrypoint.sh
COPY email_gen.py ./email_gen.py

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]