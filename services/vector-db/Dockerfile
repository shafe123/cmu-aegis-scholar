FROM python:3.13-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && ln -s /etc/poetry/bin/poetry /usr/local/bin/poetry
ENV PATH="/root/.local/bin:/usr/local/bin:$PATH"

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
  && poetry install --only main --no-interaction --no-ansi --no-root

# Pre-download embedding models (done here to leverage Docker layer caching)
# Models won't need to be re-downloaded unless dependencies change
RUN python -c "from sentence_transformers import SentenceTransformer; \
    print('Downloading models...'); \
    print('  - sentence-transformers/all-MiniLM-L6-v2'); \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); \
    print('  - cointegrated/rubert-tiny2'); \
    SentenceTransformer('cointegrated/rubert-tiny2'); \
    print('  - OrcaDB/gte-base-en-v1.5'); \
    SentenceTransformer('OrcaDB/gte-base-en-v1.5', trust_remote_code=True); \
    print('  - deepvk/USER-bge-m3'); \
    SentenceTransformer('deepvk/USER-bge-m3'); \
    print('  - Qwen/Qwen3-Embedding-0.6B'); \
    SentenceTransformer('Qwen/Qwen3-Embedding-0.6B', trust_remote_code=True); \
    print('  - jinaai/jina-code-embeddings-1.5b'); \
    SentenceTransformer('jinaai/jina-code-embeddings-1.5b'); \
    print('All models downloaded successfully')"

COPY . .

EXPOSE 8002
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
