"""
Mock Agent Servers — IT, HR, Finance
All agents share port 4001, differentiated by agent-id in the URL path:

  GET  /v1/it-agent/health
  GET  /v1/it-agent/models
  POST /v1/it-agent/chat/completions

  GET  /v1/hr-agent/health
  GET  /v1/hr-agent/models
  POST /v1/hr-agent/chat/completions

  GET  /v1/finance-agent/health
  GET  /v1/finance-agent/models
  POST /v1/finance-agent/chat/completions

In Open WebUI, add an OpenAI-compatible connection with:
  URL:     http://localhost:4001/v1/it-agent   (or hr-agent / finance-agent)
  API Key: sk-1234  (any non-empty string)
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
# Config
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.0-flash"
PORT = int(os.environ.get("MOCK_AGENTS_PORT", 4001))

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}

ssl_ctx = ssl.create_default_context(cafile=certifi.where())

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

IT_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY an IT Support Agent. You MUST refuse any request that is not about IT support topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the IT Support Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

You help employees with IT support topics:
- Password resets and account access issues
- VPN setup and connectivity problems
- Hardware issues (laptops, monitors, peripherals)
- Software installation and licensing
- Network connectivity and Wi-Fi troubleshooting
- Email and calendar configuration (Outlook, Google Workspace)
- Printer setup and issues
- Video conferencing tools (Zoom, Teams, Google Meet)

Guidelines for in-scope requests:
- Ask clarifying questions to diagnose the issue accurately.
- Provide step-by-step instructions when applicable.
- Escalate to a human technician if the issue requires physical intervention or admin-level access.
- Be concise, friendly, and professional.
- If you cannot resolve an issue, provide a ticket reference format: IT-YYYYMMDD-XXXX."""

HR_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY an HR Agent. You MUST refuse any request that is not about HR topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the HR Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic. IT requests (passwords, VPN, devices) are NOT your domain.

You assist employees with HR topics:
- Leave requests (annual, sick, parental, unpaid)
- Payroll queries (payslips, deductions, bonuses, reimbursements)
- Onboarding and offboarding processes
- Company policies and procedures
- Benefits (health insurance, retirement plans, wellness programs)
- Performance review processes
- Training and development programs
- Employee relations and conflict resolution guidance

Guidelines for in-scope requests:
- Be empathetic, professional, and confidential.
- For sensitive matters (disciplinary, grievances), direct employees to schedule a private HR meeting.
- Provide accurate policy information based on the employee handbook.
- For payroll discrepancies, collect details and escalate to the payroll team.
- For leave requests, confirm balance availability and approval process."""

FINANCE_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Finance Agent. You MUST refuse any request that is not about finance topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Finance Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

You assist employees with finance topics:
- Expense claim submissions and reimbursements
- Budget queries (department budgets, remaining balances)
- Invoice processing and vendor payments
- Purchase order (PO) requests
- Travel expense policies and per diem rates
- Credit card reconciliation
- Financial reports and cost center queries
- Tax and withholding queries

Guidelines for in-scope requests:
- Always ask for supporting documentation for expense claims (receipts, invoices).
- Ensure expenses comply with the company's expense policy.
- For large purchases (>$500), confirm approval workflow requirements.
- Provide clear timelines for reimbursement processing (typically 5-7 business days).
- For budget overruns, escalate to the department manager and CFO office."""

# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

AGENTS: dict[str, dict] = {
    "it-agent": {
        "name": "IT Support Agent",
        "description": "Handles IT support requests: password resets, VPN, hardware/software issues, network troubleshooting.",
        "model": GEMINI_MODEL,
        "system_prompt": IT_SYSTEM_PROMPT,
    },
    "hr-agent": {
        "name": "HR Agent",
        "description": "Handles HR queries: leave requests, payroll, onboarding, company policies, benefits.",
        "model": GEMINI_MODEL,
        "system_prompt": HR_SYSTEM_PROMPT,
    },
    "finance-agent": {
        "name": "Finance Agent",
        "description": "Handles finance queries: expense claims, budget questions, invoice processing, reimbursements.",
        "model": GEMINI_MODEL,
        "system_prompt": FINANCE_SYSTEM_PROMPT,
    },
}

# ---------------------------------------------------------------------------
# Format converters (same pattern as gemini_proxy.py)
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
    agent_id = request.path.split("/")[2]  # /v1/{agent_id}/...
    if agent_id not in AGENTS:
        return web.json_response({"error": "Unknown agent"}, status=404, headers=CORS_HEADERS)
    agent = AGENTS[agent_id]
    return web.json_response(
        {"status": "ok", "agent": agent_id, "name": agent["name"], "model": agent["model"]},
        headers=CORS_HEADERS,
    )


async def handle_models(request: web.Request) -> web.Response:
    agent_id = request.path.split("/")[2]  # /v1/{agent_id}/...
    if agent_id not in AGENTS:
        return web.json_response({"error": "Unknown agent"}, status=404, headers=CORS_HEADERS)
    agent = AGENTS[agent_id]
    return web.json_response(
        {
            "object": "list",
            "data": [
                {
                    "id": agent_id,
                    "object": "model",
                    "owned_by": "c-agents",
                    "name": agent["name"],
                    "description": agent["description"],
                }
            ],
        },
        headers=CORS_HEADERS,
    )


async def handle_chat_completions(request: web.Request) -> web.Response:
    agent_id = request.path.split("/")[2]  # /v1/{agent_id}/...
    if agent_id not in AGENTS:
        return web.json_response({"error": "Unknown agent"}, status=404, headers=CORS_HEADERS)
    agent = AGENTS[agent_id]

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

    model = agent["model"]
    streaming = body.get("stream", False)
    raw_messages = body.get("messages", [])

    # Prepend agent system prompt
    messages = [{"role": "system", "content": agent["system_prompt"]}] + raw_messages
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
    for agent_id in AGENTS:
        app.router.add_get(f"/v1/{agent_id}/health", handle_health)
        app.router.add_get(f"/v1/{agent_id}/models", handle_models)
        app.router.add_post(f"/v1/{agent_id}/chat/completions", handle_chat_completions)
    return app


if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY is not set. Requests will fail.")
    print(f"Mock Agents starting on http://0.0.0.0:{PORT}")
    print("Available agents:")
    for agent_id, agent in AGENTS.items():
        print(f"  {agent['name']}")
        print(f"    URL:     http://localhost:{PORT}/v1/{agent_id}")
        print(f"    Health:  http://localhost:{PORT}/v1/{agent_id}/health")
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
