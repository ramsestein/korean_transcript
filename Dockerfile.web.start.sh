#!/bin/bash
set -e

# Substitute PORT in nginx config
envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/sites-enabled/default

# Create data directory
mkdir -p /app/data

# Start backend in background (localhost only, nginx proxies to it)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Check if backend is healthy
if ! curl -sf http://127.0.0.1:8000/api/health > /dev/null; then
    echo "ERROR: Backend failed to start"
    exit 1
fi

echo "Backend started successfully (PID: $BACKEND_PID)"

# Start nginx in foreground (this keeps container running)
nginx -g 'daemon off;'
