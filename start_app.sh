#!/usr/bin/env bash
set -e

# Change to the repository root directory
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "==================================================="
echo "Starting Agentic Multilingual Tutor Application..."
echo "==================================================="

# Detect python3 or python
if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PY_CMD="$REPO_ROOT/.venv/bin/python"
    echo "Using virtual environment at .venv"
elif [ -f "$REPO_ROOT/venv/bin/python" ]; then
    PY_CMD="$REPO_ROOT/venv/bin/python"
    echo "Using virtual environment at venv"
elif command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PY_CMD="python"
else
    echo "[ERROR] Python was not found in PATH."
    exit 1
fi

# Check for npm
if ! command -v npm >/dev/null 2>&1; then
    echo "[ERROR] npm is not installed or not in PATH."
    exit 1
fi

# Kill any lingering processes on port 8000 or 5173
echo "Clearing ports 8000 and 5173..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

# Export PYTHONPATH so backend is resolvable
export PYTHONPATH="$REPO_ROOT/backend"

# Start backend in background
echo "[1/3] Starting FastAPI backend on http://127.0.0.1:8000..."
$PY_CMD -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Wait 2 seconds for backend to initialize
sleep 2

# Start frontend in background
echo "[2/3] Starting Vite frontend on http://localhost:5173..."
(cd "$REPO_ROOT/frontend" && npm run dev -- --host 0.0.0.0 --port 5173) &
FRONTEND_PID=$!

# Wait 3 seconds for Vite dev server
sleep 3

# Open default browser
echo "[3/3] Opening browser at http://localhost:5173..."
if command -v open >/dev/null 2>&1; then
    open "http://localhost:5173"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:5173"
fi

echo ""
echo "==================================================="
echo "Application running successfully!"
echo "Frontend: http://localhost:5173"
echo "Backend:  http://127.0.0.1:8000"
echo "Press CTRL+C to terminate both servers."
echo "==================================================="

# Trap SIGINT / SIGTERM to clean up background processes on exit
trap "echo 'Shutting down servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
