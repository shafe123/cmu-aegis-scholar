# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - 
ENV PATH="/root/.local/bin:$PATH"
RUN poetry self add poetry-plugin-export

COPY pyproject.toml poetry.lock* ./

RUN poetry lock
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --only main

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/requirements.txt .

RUN pip install --upgrade "pip>=25.3"

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy logic
COPY app/ ./app/

# Note: The main script is app/loader.py
CMD ["python", "-m", "app.loader"]