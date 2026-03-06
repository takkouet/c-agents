#!/usr/bin/env bash
# Single-container startup: launches gemini-proxy then open-webui.

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR" || exit

# ── Gemini proxy ──────────────────────────────────────────────────────────────
echo "Starting Gemini proxy on port ${GEMINI_PROXY_PORT:-4000}..."
python gemini_proxy.py &
PROXY_PID=$!

# Wait for proxy to be ready before starting the main app
echo "Waiting for Gemini proxy to be ready..."
for i in $(seq 1 30); do
    if python -c "import urllib.request; urllib.request.urlopen('http://localhost:${GEMINI_PROXY_PORT:-4000}/v1/models')" 2>/dev/null; then
        echo "Gemini proxy is ready."
        break
    fi
    sleep 1
done

# ── Mock Agents (IT / HR / Finance) ───────────────────────────────────────────
echo "Starting Mock Agents on port ${MOCK_AGENTS_PORT:-4001}..."
python mock_agents.py &
MOCK_AGENTS_PID=$!

# ── Orchestrator Agent ─────────────────────────────────────────────────────────
echo "Starting Orchestrator Agent on port ${ORCHESTRATOR_PORT:-4002}..."
python orchestrator_agent.py &
ORCHESTRATOR_PID=$!

# ── Open WebUI (copied from original start.sh) ────────────────────────────────
if [ -n "${WEBUI_SECRET_KEY_FILE}" ]; then
    KEY_FILE="${WEBUI_SECRET_KEY_FILE}"
else
    KEY_FILE=".webui_secret_key"
fi

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"
if test "$WEBUI_SECRET_KEY $WEBUI_JWT_SECRET_KEY" = " "; then
    echo "Loading WEBUI_SECRET_KEY from file, not provided as an environment variable."
    if ! [ -e "$KEY_FILE" ]; then
        echo "Generating WEBUI_SECRET_KEY"
        echo $(head -c 12 /dev/random | base64) > "$KEY_FILE"
    fi
    echo "Loading WEBUI_SECRET_KEY from $KEY_FILE"
    WEBUI_SECRET_KEY=$(cat "$KEY_FILE")
fi

if [[ "${USE_OLLAMA_DOCKER,,}" == "true" ]]; then
    echo "USE_OLLAMA is set to true, starting ollama serve."
    ollama serve &
fi

if [[ "${USE_CUDA_DOCKER,,}" == "true" ]]; then
    export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/local/lib/python3.11/site-packages/torch/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib"
fi

PYTHON_CMD=$(command -v python3 || command -v python)
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"

if [ "$#" -gt 0 ]; then
    ARGS=("$@")
else
    ARGS=(--workers "$UVICORN_WORKERS")
fi

# Trap to clean up all agent processes if webui exits
trap "kill $PROXY_PID $MOCK_AGENTS_PID $ORCHESTRATOR_PID 2>/dev/null" EXIT

echo "Starting Open WebUI on port $PORT..."
WEBUI_SECRET_KEY="$WEBUI_SECRET_KEY" exec "$PYTHON_CMD" -m uvicorn open_webui.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --forwarded-allow-ips '*' \
    "${ARGS[@]}"
