FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && ln -s /etc/poetry/bin/poetry /usr/local/bin/poetry
ENV PATH="/root/.local/bin:/usr/local/bin:$PATH"

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
  && poetry install --only main --no-interaction --no-ansi --no-root

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
