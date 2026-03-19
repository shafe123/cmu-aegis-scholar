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
    "

COPY . .

EXPOSE 8002
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
