"""
ExternalAgentProxy — proxy to an external agent service.

External agents run as separate processes/servers. The proxy forwards
/health, /models, and /chat/completions requests to the agent's base_url.

This class implements the same interface as DynamicAgent so the orchestrator
can use either transparently via _get_completion().
"""

import json
import time
import uuid

import aiohttp
from aiohttp import web

from agents.config import CORS_HEADERS, ssl_ctx


class ExternalAgentProxy:
    """
    Proxy to an external agent service that exposes standardised endpoints:
        GET  {base_url}/health
        GET  {base_url}/models
        POST {base_url}/chat/completions

    Attributes:
        agent_id     — registry key (e.g. "legal")
        name         — display name
        base_url     — external agent service URL (e.g. "http://host:5000/v1")
        api_key      — bearer token for authenticating with the external service
        model        — model name (metadata, also sent in chat requests)
        system_prompt — agent purpose description (used by orchestrator planner)
    """

    def __init__(
        self,
        *,
        agent_id: str,
        name: str,
        base_url: str,
        api_key: str = "",
        model: str = "",
        system_prompt: str = "",
        icon: str = "🤖",
        department: str = "",
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.icon = icon
        self.department = department

    # ------------------------------------------------------------------ #
    # Route handlers (same interface as DynamicAgent)
    # ------------------------------------------------------------------ #

    async def handle_health(self, request: web.Request) -> web.Response:
        """GET /v1/{agent_id}/health — forward to external agent's /health."""
        url = f"{self.base_url}/health"
        try:
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector) as session:
                headers = self._auth_headers()
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    body = await resp.json()
                    return web.json_response(body, status=resp.status, headers=CORS_HEADERS)
        except Exception:
            return web.json_response(
                {"status": "unreachable", "agent_id": self.agent_id},
                status=503,
                headers=CORS_HEADERS,
            )

    async def handle_models(self, request: web.Request) -> web.Response:
        """GET /v1/{agent_id}/models — forward to external agent's /models."""
        url = f"{self.base_url}/models"
        try:
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector) as session:
                headers = self._auth_headers()
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    body = await resp.json()
                    return web.json_response(body, status=resp.status, headers=CORS_HEADERS)
        except Exception:
            # Return a fallback model list using metadata
            now = int(time.time())
            data = [
                {
                    "id": self.model or self.agent_id,
                    "name": self.name,
                    "object": "model",
                    "created": now,
                    "owned_by": "external",
                }
            ]
            return web.json_response({"object": "list", "data": data}, headers=CORS_HEADERS)

    async def handle_chat_completions(self, request: web.Request) -> web.Response:
        """POST /v1/{agent_id}/chat/completions — forward to external agent."""
        url = f"{self.base_url}/chat/completions"
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
                status=400,
                headers=CORS_HEADERS,
            )

        streaming = body.get("stream", False)
        headers = {**self._auth_headers(), "Content-Type": "application/json"}

        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        if streaming:
            stream_response = web.StreamResponse(
                status=200,
                headers={
                    **CORS_HEADERS,
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
            await stream_response.prepare(request)
            try:
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(url, json=body, headers=headers) as resp:
                        async for chunk in resp.content.iter_chunked(1024):
                            await stream_response.write(chunk)
            except Exception:
                pass
            try:
                await stream_response.write_eof()
            except Exception:
                pass
            return stream_response
        else:
            try:
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(url, json=body, headers=headers) as resp:
                        data = await resp.json()
                return web.json_response(data, headers=CORS_HEADERS)
            except Exception as e:
                return web.json_response(
                    {"error": {"message": str(e), "type": "proxy_error"}},
                    status=502,
                    headers=CORS_HEADERS,
                )

    # ------------------------------------------------------------------ #
    # Completion helper (used by OrchestratorAgent)
    # ------------------------------------------------------------------ #

    async def _get_completion(self, messages: list, gen_config: dict | None = None) -> str:
        """Non-streaming call to external agent — returns assistant text."""
        url = f"{self.base_url}/chat/completions"
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        payload = {
            "model": self.model or self.agent_id,
            "messages": messages,
            "stream": False,
        }

        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        return ""
                    data = await resp.json()
        except Exception:
            return ""

        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _auth_headers(self) -> dict:
        """Build auth headers for the external service."""
        headers: dict = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
