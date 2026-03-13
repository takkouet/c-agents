#!/usr/bin/env bash
# Production startup: launches Open WebUI only.

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR" || exit

# ── Secret key ────────────────────────────────────────────────────────────────
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

# ── Open WebUI ────────────────────────────────────────────────────────────────
echo "Starting Open WebUI on port $PORT..."
WEBUI_SECRET_KEY="$WEBUI_SECRET_KEY" exec "$PYTHON_CMD" -m uvicorn open_webui.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --forwarded-allow-ips '*' \
    "${ARGS[@]}"
