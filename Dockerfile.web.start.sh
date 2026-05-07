#!/bin/bash
set -e

echo "=== Starting Korean Meeting Interpreter ==="

# Substitute PORT in nginx config
envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/sites-enabled/default

# Create data and logs directories
mkdir -p /app/data /app/logs

echo "Starting backend on port 8000..."

# Start backend in background (localhost only, nginx proxies to it)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info &
BACKEND_PID=$!

# Wait for backend to start with retries
echo "Waiting for backend to be ready..."
for i in {1..15}; do
if curl -sf http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
echo "Backend is healthy!"
break
fi
if [ $i -eq 15 ]; then
echo "ERROR: Backend failed to start after 15 attempts"
echo "Checking backend logs..."
wait $BACKEND_PID || true
exit 1
fi
echo "Attempt $i/15: Backend not ready yet, waiting..."
sleep 1
done

echo "Backend started successfully (PID: $BACKEND_PID)"
echo "Starting nginx on port ${PORT:-8080}..."

# Start nginx in foreground (this keeps container running)
nginx -g 'daemon off;'
