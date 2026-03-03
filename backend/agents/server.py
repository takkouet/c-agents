"""
Multi-agent server entry point.

Run with:
    python -m backend.agents.server
or:
    python backend/agents/server.py

Open WebUI connection settings:
    URL:     http://localhost:4001/v1/orchestrator
    API Key: sk-1234  (any non-empty value)
"""

import os
import sys

# Ensure the backend/ directory is on sys.path so `agents.*` imports resolve
# regardless of how this script is invoked (python agents/server.py, etc.)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiohttp import web

from agents.config import GEMINI_API_KEY, PORT
from agents.routes import register_routes


def create_app() -> web.Application:
    app = web.Application()
    register_routes(app)
    return app


if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY is not set. Gemini-backed agents will fail.")

    base = f"http://localhost:{PORT}"
    print(f"C-Agents multi-agent server starting on http://0.0.0.0:{PORT}")
    print()
    print("Open WebUI connection — add this as an OpenAI-compatible connection:")
    print(f"  URL:     {base}/v1/orchestrator")
    print("  API Key: sk-1234  (any non-empty value)")
    print()
    print("Per-agent endpoints (each agent follows the same standard):")
    for aid in ("orchestrator", "hr", "it", "finance"):
        print(f"  [{aid}]")
        print(f"    GET  {base}/v1/{aid}/health")
        print(f"    GET  {base}/v1/{aid}/models")
        print(f"    POST {base}/v1/{aid}/chat/completions")
    print()
    print("Agent management API:")
    print(f"  GET    {base}/v1/agents        (directory, excl. orchestrator)")
    print(f"  GET    {base}/v1/agents/all    (all agents incl. orchestrator)")
    print(f"  POST   {base}/v1/agents        (create agent)")
    print(f"  PUT    {base}/v1/agents/{{id}}   (update agent)")
    print(f"  DELETE {base}/v1/agents/{{id}}   (delete agent)")
    print(f"  GET    {base}/health")

    web.run_app(create_app(), host="0.0.0.0", port=PORT)
