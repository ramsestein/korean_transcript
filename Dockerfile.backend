FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade build toolchain first
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy source needed for pip install
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app
COPY prompts ./prompts

# Install all dependencies
RUN pip install --no-cache-dir .

RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
