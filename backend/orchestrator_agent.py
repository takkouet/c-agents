"""
Orchestrator Agent — routes user messages to specialist agents (IT, HR, Finance).

Exposes OpenAI-compatible endpoints on port 4002:
  GET  /health
  GET  /v1/models
  POST /v1/chat/completions

In Open WebUI, add an OpenAI-compatible connection with:
  URL:     http://localhost:4002/v1
  API Key: sk-1234  (any non-empty string)

Routing flow:
  1. Receives chat completion request
  2. Calls Gemini routing model to classify the user's message
  3. Forwards the full conversation to the selected downstream agent
  4. Streams or returns the agent's response verbatim
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import aiohttp
import certifi
import jwt as _jwt
import ssl
from aiohttp import web
from dotenv import load_dotenv

from open_webui.utils.orchestration_broadcast import subscribe, unsubscribe, publish

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
ROUTING_MODEL = os.environ.get("ORCHESTRATOR_ROUTING_MODEL", "gemini-2.5-flash")
PORT = int(os.environ.get("ORCHESTRATOR_PORT", 4002))

ROUTING_SYSTEM_PROMPT = os.environ.get(
    "ORCHESTRATOR_SYSTEM_PROMPT",
    """You are an intelligent routing agent. Your job is to analyze the user's message and select the most appropriate specialist agent(s) to handle it.

Available agents are listed with their ID, name, and description.
If the user's message involves MULTIPLE distinct domains, respond with ALL relevant agent IDs as a JSON array, e.g. ["it-agent", "finance-agent"].
If only ONE agent is needed, respond with a single-element JSON array, e.g. ["hr-agent"].
If no agent is suitable, respond with exactly: NONE""",
)

WEBUI_BASE_URL = os.environ.get("WEBUI_BASE_URL", "http://localhost:8080")
WEBUI_SECRET_KEY = os.environ.get("WEBUI_SECRET_KEY", os.environ.get("WEBUI_JWT_SECRET_KEY", "t0p-s3cr3t"))

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}

ssl_ctx = ssl.create_default_context(cafile=certifi.where())


def _mint_user_token(user_id: str) -> str:
    """
    Mint a short-lived HS256 JWT for user_id using WEBUI_SECRET_KEY.
    Used when forwarding requests to Open WebUI's /api/chat/completions on
    behalf of the authenticated user (workspace model calls).
    """
    payload = {
        "id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "jti": str(uuid.uuid4()),
    }
    return _jwt.encode(payload, WEBUI_SECRET_KEY, algorithm="HS256")


# ---------------------------------------------------------------------------
# Format converters (same pattern as mock_agents.py / gemini_proxy.py)
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


# ---------------------------------------------------------------------------
# Routing helper
# ---------------------------------------------------------------------------


def _extract_last_user_message(messages: list) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part.get("text", "")
            elif isinstance(content, str):
                return content
    return ""


async def _discover_agents(connector: aiohttp.TCPConnector) -> dict[str, dict]:
    """
    Query each configured OpenAI connection's /models endpoint.
    Return agents where owned_by == "c-agents", keyed by model ID.
    """
    try:
        from open_webui.config import OPENAI_API_BASE_URLS, OPENAI_API_KEYS
    except Exception as e:
        print(f"[orchestrator] Cannot import Open WebUI config: {e!r}", flush=True)
        return {}

    base_urls: list[str] = OPENAI_API_BASE_URLS.value or []
    api_keys: list[str] = OPENAI_API_KEYS.value or []
    agents: dict[str, dict] = {}

    for i, base_url in enumerate(base_urls):
        key = api_keys[i] if i < len(api_keys) else ""
        try:
            async with aiohttp.ClientSession(connector=connector, connector_owner=False) as session:
                async with session.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
            for model in data.get("data", []):
                if model.get("owned_by") != "c-agents":
                    continue
                model_id = model.get("id", "")
                if not model_id:
                    continue
                # Look up profile image from Open WebUI DB
                _avatar = ""
                try:
                    from open_webui.models.models import Models as _Models
                    _rec = _Models.get_model_by_id(model_id)
                    if _rec and _rec.meta:
                        _avatar = _rec.meta.profile_image_url or ""
                except Exception:
                    pass
                agents[model_id] = {
                    "name": model.get("name", model_id),
                    "description": model.get("description", ""),
                    "url": base_url,
                    "profile_image_url": _avatar,
                }
        except Exception as e:
            print(f"[orchestrator] Failed to query {base_url}: {e!r}", flush=True)
            continue

    # Also include workspace models from Open WebUI DB (external takes priority on ID collision)
    try:
        from open_webui.models.models import Models
        for m in (Models.get_all_models() or []):
            if m.id == "orchestrator" or m.id in agents:
                continue
            agents[m.id] = {
                "name": m.name,
                "description": (m.meta.description if m.meta else None) or "",
                "url": None,  # None = route via Open WebUI internal proxy
                "profile_image_url": (m.meta.profile_image_url if m.meta else None) or "",
            }
    except Exception as e:
        print(f"[orchestrator] Failed to load workspace models: {e!r}", flush=True)

    return agents


def _get_user_accessible_agent_ids(user_id: str, agent_ids: list[str]) -> set[str] | None:
    """
    Query the access_grant table directly to find which agents the user can access.
    Returns a set of accessible agent IDs, or None if the DB is unavailable.
    """
    try:
        from open_webui.models.access_grants import AccessGrants
        return AccessGrants.get_accessible_resource_ids(
            user_id=user_id,
            resource_type="model",
            resource_ids=agent_ids,
            permission="read",
        )
    except Exception as e:
        print(f"[orchestrator] DB access check failed: {e!r}", flush=True)
        return None


async def _route_message(user_message: str, connector: aiohttp.TCPConnector, agents_subset: dict | None = None) -> list[str]:
    """
    Ask the Gemini routing model which agent(s) should handle this message.
    Returns a list of agent ID strings, or empty list if no suitable agent.
    """
    effective_agents = agents_subset or {}

    if not effective_agents:
        return []

    agents_list = [
        {"id": k, "name": v["name"], "description": v["description"]}
        for k, v in effective_agents.items()
    ]

    routing_messages = [
        {"role": "system", "content": ROUTING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Available agents:\n{json.dumps(agents_list, indent=2)}\n\n"
                f"User message: {user_message}\n\n"
                "Respond with a JSON array of agent IDs. If none suitable, respond: NONE"
            ),
        },
    ]

    contents, system_instruction = openai_messages_to_gemini(routing_messages)
    payload: dict = {"contents": contents}
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    url = f"{GEMINI_BASE_URL}/models/{ROUTING_MODEL}:generateContent?key={GEMINI_API_KEY}"

    async with aiohttp.ClientSession(connector=connector, connector_owner=False) as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

    result = gemini_response_to_openai(data, ROUTING_MODEL)
    selected = result["choices"][0]["message"]["content"].strip()

    if selected == "NONE":
        return []

    # Try parsing as JSON array first
    try:
        parsed = json.loads(selected)
        if isinstance(parsed, list):
            return [s for s in parsed if s in effective_agents]
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: single agent ID string
    if selected in effective_agents:
        return [selected]

    return []


# ---------------------------------------------------------------------------
# Fallback LLM answering (greetings, capability questions, etc.)
# ---------------------------------------------------------------------------


async def _answer_directly(
    messages: list,
    connector: aiohttp.TCPConnector,
    agents: dict,
    streaming: bool,
    request: web.Request,
) -> web.Response:
    """
    Called when no specialist agent is routable.
    Answers greetings, capability questions, and ambiguous requests via Gemini.
    """
    agent_lines = "\n".join(
        f"- {v['name']}: {v['description']}" for v in agents.values()
    ) or "No specialist agents are currently configured."

    system_prompt = (
        "You are an AI orchestrator assistant. You help employees by routing their requests "
        "to the right specialist agent.\n\n"
        f"Available agents:\n{agent_lines}\n\n"
        "Guidelines:\n"
        "- For greetings, respond warmly and briefly introduce yourself and the available agents.\n"
        "- For capability questions (e.g. 'what can you do?'), list the agents and what each handles.\n"
        "- For unclear requests, politely ask the user to clarify what they need.\n"
        "- Do NOT answer domain-specific questions yourself — those should be routed to the appropriate specialist."
    )

    gemini_messages = [{"role": "system", "content": system_prompt}] + messages
    contents, system_instruction = openai_messages_to_gemini(gemini_messages)

    if streaming:
        endpoint = "streamGenerateContent"
        url = f"{GEMINI_BASE_URL}/models/{ROUTING_MODEL}:{endpoint}?key={GEMINI_API_KEY}&alt=sse"
    else:
        endpoint = "generateContent"
        url = f"{GEMINI_BASE_URL}/models/{ROUTING_MODEL}:{endpoint}?key={GEMINI_API_KEY}"

    payload: dict = {"contents": contents}
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"

    if not streaming:
        async with aiohttp.ClientSession(connector=connector, connector_owner=False) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    data = {}
                else:
                    data = await resp.json()
        return web.json_response(gemini_response_to_openai(data, "orchestrator"), headers=CORS_HEADERS)

    # Streaming
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
        "model": "orchestrator",
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
    }
    await response.write(f"data: {json.dumps(opening)}\n\n".encode())

    async with aiohttp.ClientSession(connector=connector, connector_owner=False) as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
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
                candidates = chunk.get("candidates", [])
                if not candidates:
                    continue
                c = candidates[0]
                parts = c.get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
                fr = c.get("finishReason", "")
                finish_reason = None
                if fr in ("STOP", "END_OF_TURN", "MAX_TOKENS"):
                    finish_reason = "stop" if fr != "MAX_TOKENS" else "length"
                if text or finish_reason:
                    sse_chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "orchestrator",
                        "choices": [{"index": 0, "delta": {"content": text} if text else {}, "finish_reason": finish_reason}],
                    }
                    await response.write(f"data: {json.dumps(sse_chunk)}\n\n".encode())

    await response.write(b"data: [DONE]\n\n")
    await response.write_eof()
    return response


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "orchestrator-agent"}, headers=CORS_HEADERS)


async def handle_models(_request: web.Request) -> web.Response:
    return web.json_response(
        {
            "object": "list",
            "data": [
                {
                    "id": "orchestrator",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "c-agents",
                    "name": "Orchestrator",
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
    messages = body.get("messages", [])
    user_message = _extract_last_user_message(messages)

    # User identity forwarded by Open WebUI (requires ENABLE_FORWARD_USER_INFO_HEADERS=true)
    user_id = request.headers.get("X-OpenWebUI-User-Id", "")
    user_role = request.headers.get("X-OpenWebUI-User-Role", "")

    session_id = str(uuid.uuid4())
    await publish({"step": "session_start", "session_id": session_id, "message": "Request received"})

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    # --- Discover available agents from OpenAI connections (owned_by: c-agents) ---
    all_agents = await _discover_agents(connector)


    # --- Permission check: filter to only agents the user can access ---
    if user_role == "admin":
        accessible_agents = all_agents
    elif user_id:
        accessible_ids = _get_user_accessible_agent_ids(user_id, list(all_agents.keys()))
        accessible_agents = {k: v for k, v in all_agents.items() if k in (accessible_ids or set())}
    else:
        accessible_agents = {}

    # --- Route: ask Gemini which agent should handle this ---
    await publish({
        "step": "routing",
        "session_id": session_id,
        "message": "Selecting the best agent...",
        "agents": [{"id": k, "name": v["name"]} for k, v in accessible_agents.items()],
    })
    selected_ids = await _route_message(user_message, connector, agents_subset=accessible_agents)

    if not selected_ids:
        if not accessible_agents:
            # No agents accessible — static permission denial
            await publish({"step": "session_done", "session_id": session_id, "message": "No accessible agents"})
            fallback_text = (
                "Sorry, you don't have permission to access any specialist agent. "
                "Please contact your admin."
            )
            chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
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
                opening = {
                    "id": chunk_id, "object": "chat.completion.chunk",
                    "created": int(time.time()), "model": "orchestrator",
                    "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
                }
                await response.write(f"data: {json.dumps(opening)}\n\n".encode())
                content_chunk = {
                    "id": chunk_id, "object": "chat.completion.chunk",
                    "created": int(time.time()), "model": "orchestrator",
                    "choices": [{"index": 0, "delta": {"content": fallback_text}, "finish_reason": "stop"}],
                }
                await response.write(f"data: {json.dumps(content_chunk)}\n\n".encode())
                await response.write(b"data: [DONE]\n\n")
                await response.write_eof()
                await connector.close()
                return response
            else:
                await connector.close()
                return web.json_response(
                    gemini_response_to_openai(
                        {"candidates": [{"content": {"parts": [{"text": fallback_text}]}, "finishReason": "STOP"}]},
                        "orchestrator",
                    ),
                    headers=CORS_HEADERS,
                )
        else:
            # Agents exist but none routable — answer directly with Gemini
            await publish({"step": "session_done", "session_id": session_id, "message": "Handled directly"})
            result = await _answer_directly(messages, connector, accessible_agents, streaming, request)
            await connector.close()
            return result

    # --- Helper: get agent URL and auth for a given agent ---
    def _agent_url_and_auth(agent_id: str) -> tuple[str, str]:
        agent = accessible_agents[agent_id]
        if agent["url"] is None:
            url = f"{WEBUI_BASE_URL}/api/chat/completions"
            a = f"Bearer {_mint_user_token(user_id)}" if user_id else auth
        else:
            url = f"{agent['url']}/chat/completions"
            a = auth
        return url, a

    # --- Helper: call one agent non-streaming and return response text ---
    async def _call_agent(agent_id: str, connector: aiohttp.TCPConnector) -> str:
        agent = accessible_agents[agent_id]
        await publish({
            "step": "agent_active",
            "session_id": session_id,
            "agent_id": agent_id,
            "agent_label": agent["name"],
            "agent_icon": "🤖",
            "agent_avatar_url": agent.get("profile_image_url", ""),
            "agent_dept": "",
            "action": "Handling request",
        })
        agent_url, forward_auth = _agent_url_and_auth(agent_id)
        forward_body = {**body, "model": agent_id, "stream": False}
        try:
            async with aiohttp.ClientSession(connector=connector, connector_owner=False) as session:
                async with session.post(
                    agent_url,
                    json=forward_body,
                    headers={"Authorization": forward_auth, "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        await publish({"step": "agent_done", "session_id": session_id, "agent_id": agent_id, "agent_label": agent["name"]})
                        return f"[{agent['name']}]: Error — {err_text[:200]}"
                    data = await resp.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            await publish({"step": "agent_done", "session_id": session_id, "agent_id": agent_id, "agent_label": agent["name"]})
            return text
        except Exception as e:
            await publish({"step": "agent_done", "session_id": session_id, "agent_id": agent_id, "agent_label": agent["name"]})
            return f"[{agent['name']}]: Error — {e!r}"

    # =====================================================================
    # SINGLE AGENT — proxy directly (streaming or non-streaming)
    # =====================================================================
    if len(selected_ids) == 1:
        selected_id = selected_ids[0]
        agent = accessible_agents[selected_id]
        await publish({
            "step": "agent_active",
            "session_id": session_id,
            "agent_id": selected_id,
            "agent_label": agent["name"],
            "agent_icon": "🤖",
            "agent_avatar_url": agent.get("profile_image_url", ""),
            "agent_dept": "",
            "action": "Handling request",
        })
        agent_url, forward_auth = _agent_url_and_auth(selected_id)
        forward_body = {**body, "model": selected_id}

        if not streaming:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    agent_url,
                    json=forward_body,
                    headers={"Authorization": forward_auth, "Content-Type": "application/json"},
                ) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        return web.json_response(
                            {"error": {"message": err_text, "type": "upstream_error"}},
                            status=resp.status,
                            headers=CORS_HEADERS,
                        )
                    data = await resp.json()
            await publish({"step": "agent_done", "session_id": session_id, "agent_id": selected_id, "agent_label": agent["name"]})
            await publish({"step": "session_done", "session_id": session_id, "message": "Completed"})
            return web.json_response(data, headers=CORS_HEADERS)

        # Streaming single agent
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

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                agent_url,
                json=forward_body,
                headers={"Authorization": forward_auth, "Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    err_payload = json.dumps({"error": err_text})
                    await response.write(f"data: {err_payload}\n\n".encode())
                    await response.write(b"data: [DONE]\n\n")
                    await response.write_eof()
                    return response

                async for raw_line in resp.content:
                    await response.write(raw_line)

        await publish({"step": "agent_done", "session_id": session_id, "agent_id": selected_id, "agent_label": agent["name"]})
        await publish({"step": "session_done", "session_id": session_id, "message": "Completed"})
        await response.write_eof()
        return response

    # =====================================================================
    # MULTIPLE AGENTS — collect responses, then synthesize
    # =====================================================================
    agent_responses: list[tuple[str, str]] = []  # (agent_name, response_text)

    for agent_id in selected_ids:
        agent = accessible_agents[agent_id]
        text = await _call_agent(agent_id, connector)
        agent_responses.append((agent["name"], text))

    # Synthesize combined response via Gemini
    responses_text = "\n\n".join(
        f"--- Response from {name} ---\n{text}"
        for name, text in agent_responses
    )
    synthesis_messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful orchestrator. Multiple specialist agents have provided responses "
                "to the user's request. Combine their responses into a single, coherent, well-organized "
                "answer. Preserve all important details from each agent. Use clear headings or sections "
                "to separate different topics. Respond in the same language as the user's original message."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Original user request: {user_message}\n\n"
                f"Agent responses:\n{responses_text}\n\n"
                "Please combine these into a single coherent response for the user."
            ),
        },
    ]

    contents, system_instruction = openai_messages_to_gemini(synthesis_messages)
    gemini_payload: dict = {"contents": contents}
    if system_instruction:
        gemini_payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    if streaming:
        synth_url = f"{GEMINI_BASE_URL}/models/{ROUTING_MODEL}:streamGenerateContent?key={GEMINI_API_KEY}&alt=sse"
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
            "id": chunk_id, "object": "chat.completion.chunk",
            "created": int(time.time()), "model": "orchestrator",
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
        }
        await response.write(f"data: {json.dumps(opening)}\n\n".encode())

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(synth_url, json=gemini_payload) as resp:
                if resp.status == 200:
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
                        sse = gemini_chunk_to_openai_sse(chunk, "orchestrator", chunk_id)
                        if sse:
                            await response.write(sse.encode())

        await response.write(b"data: [DONE]\n\n")
        await publish({"step": "session_done", "session_id": session_id, "message": "Completed"})
        await response.write_eof()
        return response
    else:
        synth_url = f"{GEMINI_BASE_URL}/models/{ROUTING_MODEL}:generateContent?key={GEMINI_API_KEY}"
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(synth_url, json=gemini_payload) as resp:
                if resp.status != 200:
                    data = {}
                else:
                    data = await resp.json()
        await publish({"step": "session_done", "session_id": session_id, "message": "Completed"})
        return web.json_response(gemini_response_to_openai(data, "orchestrator"), headers=CORS_HEADERS)


async def handle_options(_request: web.Request) -> web.Response:
    return web.Response(status=204, headers=CORS_HEADERS)


async def handle_orchestration_ws(request: web.Request) -> web.WebSocketResponse:
    """GET /v1/orchestration/ws — WebSocket stream of real-time orchestration events."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    q = subscribe()
    try:
        await ws.send_json({"step": "connected"})
        while not ws.closed:
            try:
                event = await asyncio.wait_for(q.get(), timeout=20)
                await ws.send_json(event)
            except asyncio.TimeoutError:
                await ws.ping()
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        unsubscribe(q)
    return ws


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_options)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/v1/models", handle_models)
    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    app.router.add_get("/v1/orchestration/ws", handle_orchestration_ws)
    return app


if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY is not set. Routing calls will fail.")
    print(f"Orchestrator Agent starting on http://0.0.0.0:{PORT}")
    print("In Open WebUI, add an OpenAI-compatible connection with:")
    print(f"  URL:     http://localhost:{PORT}/v1")
    print(f"  API Key: sk-1234  (any non-empty value)")
    print("Agents are discovered dynamically from OpenAI connections (owned_by: c-agents).")
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
