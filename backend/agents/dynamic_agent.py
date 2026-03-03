"""
DynamicAgent — a built-in agent loaded from the DB that can proxy to either:
  - A Gemini endpoint (detected when llm_base_url contains "generativelanguage.googleapis.com")
  - Any OpenAI-compatible endpoint (everything else)

Used for built-in agents (hr, it, finance) and admin-created agents that run
on the same server. External agents use ExternalAgentProxy instead.

Field semantics:
  - base_url     → Agent service URL (auto-set at runtime for built-in agents).
  - llm_base_url → LLM backend URL (Gemini/OpenAI) used for actual LLM calls.
  - llm_api_key  → API key / bearer token for the LLM backend.
"""

import json
import time
import uuid

import aiohttp
from aiohttp import web

from agents.config import CORS_HEADERS, ssl_ctx
from agents.gemini_utils import (
    gemini_chunk_to_openai_sse,
    openai_messages_to_gemini,
    openai_params_to_gemini,
)

_GEMINI_MARKER = "generativelanguage.googleapis.com"


def _is_gemini(url: str) -> bool:
    return _GEMINI_MARKER in url


class DynamicAgent:
    """
    Built-in agent loaded from the agents DB.

    Attributes set on construction:
        agent_id      — registry key (e.g. "hr", "custom-legal")
        name          — display name
        system_prompt — domain-specific instruction
        llm_base_url  — LLM endpoint (e.g. Gemini URL or "http://localhost:11434/v1")
        llm_api_key   — API key / bearer token for the LLM
        model         — model name (e.g. "gemini-2.5-flash", "gpt-4o")
    """

    def __init__(
        self,
        *,
        agent_id: str,
        name: str,
        system_prompt: str,
        llm_base_url: str,
        llm_api_key: str,
        model: str,
        icon: str = "🤖",
        department: str = "",
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.system_prompt = system_prompt
        self.llm_base_url = llm_base_url.rstrip("/")
        self.llm_api_key = llm_api_key
        self.model = model
        self.icon = icon
        self.department = department

    # ------------------------------------------------------------------ #
    # Public route handlers
    # ------------------------------------------------------------------ #

    async def handle_health(self, request: web.Request) -> web.Response:
        """GET /v1/{agent_id}/health"""
        return web.json_response(
            {"status": "ok", "agent_id": self.agent_id, "model": self.model},
            headers=CORS_HEADERS,
        )

    async def handle_models(self, request: web.Request) -> web.Response:
        """GET /v1/{agent_id}/models"""
        now = int(time.time())
        data = [
            {
                "id": self.agent_id,
                "name": self.name,
                "object": "model",
                "created": now,
                "owned_by": "c-agents",
            }
        ]
        return web.json_response({"object": "list", "data": data}, headers=CORS_HEADERS)

    async def handle_chat_completions(self, request: web.Request) -> web.Response:
        """POST /v1/{agent_id}/chat/completions"""
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return web.json_response(
                {"error": {"message": "Missing Authorization header", "type": "auth_error"}},
                status=401,
                headers=CORS_HEADERS,
            )

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
                status=400,
                headers=CORS_HEADERS,
            )

        streaming = body.get("stream", False)
        raw_messages = body.get("messages", [])
        messages = [{"role": "system", "content": self.system_prompt}] + raw_messages
        gen_config = openai_params_to_gemini(body)

        if _is_gemini(self.llm_base_url):
            return await self._handle_gemini(request, messages, gen_config, streaming)
        else:
            return await self._handle_openai(request, body, messages, streaming)

    # ------------------------------------------------------------------ #
    # Internal helpers used directly by OrchestratorAgent
    # ------------------------------------------------------------------ #

    async def _get_completion(self, messages: list, gen_config: dict | None = None) -> str:
        """Non-streaming call — returns the assistant text string."""
        if _is_gemini(self.llm_base_url):
            return await self._gemini_completion(messages, gen_config or {})
        else:
            return await self._openai_completion(messages)

    # ------------------------------------------------------------------ #
    # Gemini path
    # ------------------------------------------------------------------ #

    async def _handle_gemini(
        self,
        request: web.Request,
        messages: list,
        gen_config: dict,
        streaming: bool,
    ) -> web.Response:
        if streaming:
            response = web.StreamResponse(
                status=200,
                headers={
                    **CORS_HEADERS,
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
            await response.prepare(request)
            chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
            await self._gemini_stream(messages, gen_config, response, chunk_id)
            await response.write(b"data: [DONE]\n\n")
            await response.write_eof()
            return response
        else:
            text = await self._gemini_completion(messages, gen_config)
            result = {
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": self.model,
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
                ],
            }
            return web.json_response(result, headers=CORS_HEADERS)

    async def _gemini_stream(
        self,
        messages: list,
        gen_config: dict,
        stream_response: web.StreamResponse,
        chunk_id: str,
    ) -> None:
        contents, system_instruction = openai_messages_to_gemini(messages)
        payload: dict = {"contents": contents}
        if gen_config:
            payload["generationConfig"] = gen_config
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{self.llm_base_url}/models/{self.model}:streamGenerateContent?key={self.llm_api_key}&alt=sse"

        opening = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
        }
        await stream_response.write(f"data: {json.dumps(opening)}\n\n".encode())

        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    await stream_response.write(f"data: {json.dumps({'error': err_text})}\n\n".encode())
                    return
                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    json_str = line[len("data:"):].strip()
                    if not json_str:
                        continue
                    try:
                        chunk = json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
                    sse = gemini_chunk_to_openai_sse(chunk, self.model, chunk_id)
                    if sse:
                        await stream_response.write(sse.encode())

    async def _gemini_completion(self, messages: list, gen_config: dict) -> str:
        contents, system_instruction = openai_messages_to_gemini(messages)
        payload: dict = {"contents": contents}
        if gen_config:
            payload["generationConfig"] = gen_config
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{self.llm_base_url}/models/{self.model}:generateContent?key={self.llm_api_key}"
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)

    # ------------------------------------------------------------------ #
    # OpenAI-compatible path
    # ------------------------------------------------------------------ #

    async def _handle_openai(
        self,
        request: web.Request,
        original_body: dict,
        messages: list,
        streaming: bool,
    ) -> web.Response:
        """Forward the request to an OpenAI-compatible endpoint."""
        url = f"{self.llm_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {**original_body, "messages": messages, "model": self.model}

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
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    async for chunk in resp.content.iter_chunked(1024):
                        await stream_response.write(chunk)
            await stream_response.write_eof()
            return stream_response
        else:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    data = await resp.json()
            return web.json_response(data, headers=CORS_HEADERS)

    async def _openai_completion(self, messages: list) -> str:
        """Non-streaming OpenAI-compatible call — returns assistant text."""
        url = f"{self.llm_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "messages": messages, "stream": False}

        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json()

        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")
