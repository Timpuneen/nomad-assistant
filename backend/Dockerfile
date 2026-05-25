FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install dependencies first (layer caching)
COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt || \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# ChromaDB will persist here (mounted as volume)
RUN mkdir -p /app/chroma_db

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
