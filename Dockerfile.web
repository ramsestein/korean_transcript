# Combined Dockerfile for PaaS platforms (Sliplane, Railway, etc.)
# Serves both frontend (nginx) and backend (FastAPI) in one container

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend with nginx
FROM python:3.12-slim

# Install nginx, ffmpeg, and envsubst
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    ffmpeg \
    curl \
    gettext-base \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY prompts ./prompts
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

COPY Dockerfile.web.nginx.conf /etc/nginx/templates/default.conf.template

COPY Dockerfile.web.start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/api/health || exit 1

EXPOSE 8080
ENV PORT=8080
ENV DATA_DIR=/app/data

CMD ["/app/start.sh"]
