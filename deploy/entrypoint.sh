#!/bin/bash
set -e

# Start agents API (port 8050) in background
echo "[entrypoint] Starting agents API on :8050..."
python -m uvicorn src.serve:app --host 0.0.0.0 --port 8050 &
AGENTS_PID=$!

# Start console backend (port 8060) in background
echo "[entrypoint] Starting console backend on :8060..."
cd /app/console/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8060 &
CONSOLE_PID=$!
cd /app

# Wait for agents API to be ready before starting nginx
echo "[entrypoint] Waiting for agents API..."
for i in $(seq 1 30); do
    if python -c "import urllib.request; urllib.request.urlopen('http://localhost:8050/health')" 2>/dev/null; then
        echo "[entrypoint] Agents API ready."
        break
    fi
    sleep 2
done

# Start nginx in foreground (PID 1 behavior)
echo "[entrypoint] Starting nginx on :80..."
nginx -g 'daemon off;' &
NGINX_PID=$!

# Wait for any process to exit
wait -n $AGENTS_PID $CONSOLE_PID $NGINX_PID

# If any process exits, kill all and exit
echo "[entrypoint] A process exited, shutting down..."
kill $AGENTS_PID $CONSOLE_PID $NGINX_PID 2>/dev/null || true
exit 1
