"""
Agent Template — copy this file and customize for your domain.

Usage:
  1. Copy this file: cp agent_template.py my_agent.py
  2. Update AGENT_ID, AGENT_NAME, AGENT_DESCRIPTION, SYSTEM_PROMPT
  3. Run: python my_agent.py
  4. In Open WebUI Admin, add an OpenAI connection:
       URL:     http://localhost:{PORT}/v1/{AGENT_ID}
       API Key: sk-1234  (any non-empty string)

See AGENT_SPEC.md for the full interface specification.
"""

import json
import os
import time
import uuid

import aiohttp
import certifi
import ssl
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configure your agent here
# ---------------------------------------------------------------------------

AGENT_ID = "my-agent"
AGENT_NAME = "My Custom Agent"
AGENT_DESCRIPTION = "Handles requests about [your domain]."

SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a [Domain] Agent. You MUST refuse any request that is not about [domain] topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the [Domain] Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You help employees with [domain] topics:
- Topic 1
- Topic 2

Guidelines for in-scope requests:
- Guideline 1
- Guideline 2
"""

# ---------------------------------------------------------------------------
# Config (update PORT if needed, leave the rest as-is)
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.0-flash"
PORT = int(os.environ.get("AGENT_PORT", 4003))

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}

ssl_ctx = ssl.create_default_context(cafile=certifi.where())

# ---------------------------------------------------------------------------
# Format converters (Gemini <-> OpenAI)
# ---------------------------------------------------------------------------


def openai_messages_to_gemini(messages: list) -> tuple[list, str | None]:
    """Convert OpenAI messages array to Gemini contents + system_instruction."""
    system_parts: list[str] = []
    contents: list[dict] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            parts = [{"text": content}] if content else []
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append({"text": item.get("text", "")})
                    elif item.get("type") == "image_url":
                        url = item.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            header, data = url.split(",", 1)
                            mime = header.split(";")[0].split(":")[1]
                            parts.append({"inline_data": {"mime_type": mime, "data": data}})
                        else:
                            parts.append({"text": f"[Image: {url}]"})
        else:
            parts = []

        if role == "system":
            system_parts.append(content if isinstance(content, str) else " ".join(
                p.get("text", "") for p in parts
            ))
        elif role == "assistant":
            contents.append({"role": "model", "parts": parts})
        else:
            contents.append({"role": "user", "parts": parts})

    system_instruction = " ".join(system_parts) if system_parts else None
    return contents, system_instruction


def openai_params_to_gemini(body: dict) -> dict:
    """Build Gemini generationConfig from OpenAI request params."""
    config: dict = {}
    if "max_tokens" in body:
        config["maxOutputTokens"] = body["max_tokens"]
    if "temperature" in body:
        config["temperature"] = body["temperature"]
    if "top_p" in body:
        config["topP"] = body["top_p"]
    if "stop" in body:
        stops = body["stop"]
        config["stopSequences"] = [stops] if isinstance(stops, str) else stops
    return config


def gemini_response_to_openai(gemini_resp: dict, model: str) -> dict:
    """Convert a non-streaming Gemini response to OpenAI format."""
    candidates = gemini_resp.get("candidates", [])
    text = ""
    finish_reason = "stop"

    if candidates:
        c = candidates[0]
        parts = c.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        fr = c.get("finishReason", "STOP")
        finish_reason = "stop" if fr in ("STOP", "END_OF_TURN") else fr.lower()

    usage_meta = gemini_resp.get("usageMetadata", {})
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            "total_tokens": usage_meta.get("totalTokenCount", 0),
        },
    }


def gemini_chunk_to_openai_sse(chunk: dict, model: str, chunk_id: str) -> str | None:
    """Convert one Gemini stream chunk to an OpenAI SSE data line."""
    candidates = chunk.get("candidates", [])
    if not candidates:
        return None

    c = candidates[0]
    parts = c.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    fr = c.get("finishReason", "")
    finish_reason = None
    if fr in ("STOP", "END_OF_TURN", "MAX_TOKENS"):
        finish_reason = "stop" if fr != "MAX_TOKENS" else "length"

    payload = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": text} if text else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload)}\n\n"


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response(
        {"status": "ok", "agent": AGENT_ID, "name": AGENT_NAME, "model": GEMINI_MODEL},
        headers=CORS_HEADERS,
    )


async def handle_models(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "object": "list",
            "data": [
                {
                    "id": AGENT_ID,
                    "object": "model",
                    "owned_by": "c-agents",
                    "name": AGENT_NAME,
                    "description": AGENT_DESCRIPTION,
                }
            ],
        },
        headers=CORS_HEADERS,
    )


async def handle_chat_completions(request: web.Request) -> web.Response:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return web.json_response(
            {"error": {"message": "Missing Authorization header", "type": "auth_error"}},
            status=401, headers=CORS_HEADERS,
        )

    try:
        body = await request.json()
    except Exception:
        return web.json_response(
            {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
            status=400, headers=CORS_HEADERS,
        )

    model = GEMINI_MODEL
    streaming = body.get("stream", False)
    raw_messages = body.get("messages", [])

    # Prepend agent system prompt
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + raw_messages
    contents, system_instruction = openai_messages_to_gemini(messages)
    gen_config = openai_params_to_gemini(body)

    gemini_payload: dict = {"contents": contents}
    if gen_config:
        gemini_payload["generationConfig"] = gen_config
    if system_instruction:
        gemini_payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    endpoint = "streamGenerateContent" if streaming else "generateContent"
    url = f"{GEMINI_BASE_URL}/models/{model}:{endpoint}?key={GEMINI_API_KEY}"
    if streaming:
        url += "&alt=sse"

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    if not streaming:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=gemini_payload) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    return web.json_response(
                        {"error": {"message": err_text, "type": "upstream_error"}},
                        status=resp.status, headers=CORS_HEADERS,
                    )
                gemini_data = await resp.json()
        result = gemini_response_to_openai(gemini_data, model)
        return web.json_response(result, headers=CORS_HEADERS)

    # Streaming
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
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

    opening = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
    }
    await response.write(f"data: {json.dumps(opening)}\n\n".encode())

    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(url, json=gemini_payload) as resp:
            if resp.status != 200:
                err_text = await resp.text()
                await response.write(f"data: {json.dumps({'error': err_text})}\n\n".encode())
                await response.write(b"data: [DONE]\n\n")
                await response.write_eof()
                return response

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
                sse = gemini_chunk_to_openai_sse(chunk, model, chunk_id)
                if sse:
                    await response.write(sse.encode())

    await response.write(b"data: [DONE]\n\n")
    await response.write_eof()
    return response


async def handle_options(request: web.Request) -> web.Response:
    return web.Response(status=204, headers=CORS_HEADERS)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_options)
    app.router.add_get(f"/v1/{AGENT_ID}/health", handle_health)
    app.router.add_get(f"/v1/{AGENT_ID}/models", handle_models)
    app.router.add_post(f"/v1/{AGENT_ID}/chat/completions", handle_chat_completions)
    return app


if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY is not set. Requests will fail.")
    print(f"{AGENT_NAME} starting on http://0.0.0.0:{PORT}")
    print(f"  URL: http://localhost:{PORT}/v1/{AGENT_ID}")
    print(f"  Health: http://localhost:{PORT}/v1/{AGENT_ID}/health")
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
