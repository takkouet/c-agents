"""
Gemini Proxy - OpenAI-compatible API that translates to Google Gemini.
Runs on port 4000 so Open WebUI can connect via:
  URL:     http://localhost:4000/v1
  API Key: sk-1234  (any non-empty string)
"""

import asyncio
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

from data.meeting_data import MEETING_ROOMS, ADMINS


def _build_room_list_text() -> str:
    lines = []
    for r in MEETING_ROOMS:
        equip = ", ".join(r["equipment"]) if r["equipment"] else "none"
        lines.append(
            f"  - {r['name']} (id: {r['id']}) | Office: {r['code']}"
            f" | Building: {r['building']}"
            f" | Floor: {r['floor']} | Capacity: {r['capacity']} people | Equipment: {equip}"
        )
    return "\n".join(lines)


def _build_admin_list_text() -> str:
    lines = []
    for a in ADMINS:
        lines.append(
            f"  - {a['department_code']}: {a['name']} <{a['email']}> (Floor {a['floor']})"
        )
    return "\n".join(lines)


_ROOM_LIST = _build_room_list_text()
_ADMIN_LIST = _build_admin_list_text()

# In-memory booking registry (session-scoped, resets on proxy restart)
booking_registry: dict[str, dict] = {}


def _build_active_bookings_text() -> str:
    active = [b for b in booking_registry.values() if b.get("status") in ("approved", "sent")]
    if not active:
        return "  (Không có lịch họp nào đang được đặt)"
    lines = []
    for b in active:
        lines.append(
            f"  - [{b['id']}] \"{b.get('title','?')}\""  
            f" | {b.get('date','?')} {b.get('start_time','?')} - {b.get('end_time','?')}"
            f" | Room: {b.get('room_id', b.get('room_code','?'))} | Office: {b.get('location','?')}"
        )
    return "\n".join(lines)


_BOOKING_AGENT_SYSTEM_PROMPT_STATIC = f"""
You are the CMC Global Meeting Room Booking Assistant.

══════════════════════════════════════
AVAILABLE ROOMS
══════════════════════════════════════
⚠️  VALID room_name values — use EXACTLY one of these strings, copy-paste only:
    Rose | Daisy | Blossom | Sun Flower | Orchid | Lotus | Jasmine | Tulip
    Any other name ("A2", "B3", "Phòng Họp X", "Conference Room") is a hallucination.

{_ROOM_LIST}

══════════════════════════════════════
ADMIN CONTACTS (one per office)
══════════════════════════════════════
{_ADMIN_LIST}

══════════════════════════════════════
YOUR ROLE
══════════════════════════════════════
- You ONLY help with meeting room bookings for CMC Global.
- For ANY unrelated question, respond:
  Vietnamese: "Xin lỗi, tôi chỉ hỗ trợ đặt phòng họp tại CMC Global. Bạn có muốn đặt phòng không?"
  English: "Sorry, I can only help with meeting room bookings at CMC Global. Would you like to book a room?"
- Only greet the user if their message contains ZERO booking information (e.g. "xin chào", "hi").
  If ANY meeting detail is present (date, time, purpose, person name), skip all pleasantries
  and go DIRECTLY to step 6 of the BOOKING WORKFLOW — no preamble, no questions.
- Always respond in the same language the user uses (Vietnamese or English).

══════════════════════════════════════
BOOKING WORKFLOW
══════════════════════════════════════
⚡ CRITICAL — act on this BEFORE doing anything else:
   TODAY = {{CURRENT_DATE}}.
   The moment a user message contains a title/purpose AND a date/time hint,
   compute ALL missing values using defaults and show the confirmation summary (step 6).
   Do NOT ask questions. Do NOT list what you're defaulting.
   Output the booking block (step 7) ONLY after the user explicitly confirms.

   RELATIVE DATE RESOLUTION — always compute, never ask:
     "ngày mai" / "tomorrow"        → TODAY + 1 day
     "ngày kia"                     → TODAY + 2 days
     "ngày kìa" / "2 ngày nữa"      → TODAY + 2 days
     "tuần tới" / "next week"       → TODAY + 7 days
     "thứ Hai này" / "this Monday"  → date of the coming Monday
   Always resolve to YYYY-MM-DD before writing the booking block.
   NEVER ask "Ngày kia là ngày nào?" or any equivalent — compute it yourself.

   ── CORRECT EXAMPLE ──────────────────────────────────────────────────────
   Input : "ngày kia có khách Kuok đến thăm tại Hà Nội lúc 10h sáng"
   TODAY = {{CURRENT_DATE}}  →  ngày kia = TODAY + 2 days  →  resolve to YYYY-MM-DD
   All required fields present → NO greeting, NO questions. Output ONLY step 6:

   📋 **Xác nhận thông tin đặt phòng**

   | | |
   |---|---|
   | 📋 **Tiêu đề** | Đón khách Kuok |
   | 📅 **Ngày** | [ngày kia resolved, e.g. Chủ Nhật, 01/03/2026] |
   | 🕐 **Thời gian** | 10:00 – 11:00 |
   | 🏢 **Phòng** | Orchid – Lotte Center Hanoi (Tầng 8) |
   | 📍 **Văn phòng** | Hà Nội |
   | 👥 **Số người** | 5 người |
   | ✉️ **Phê duyệt bởi** | Nguyễn Văn Trang |

   *Bạn có muốn xác nhận đặt phòng không?*
   ─────────────────────────────────────────────────────────────────────────

1. UNDERSTAND the user's intent naturally — they may describe it casually.
   Extract these fields:
   - Meeting title / purpose (who they're meeting with, what it's about)
   - Date → convert to YYYY-MM-DD (resolve relative dates using the rule above)
   - Start time → HH:MM
   - End time (default: start + 1 hour if not given)
   - Number of attendees / capacity (default: 5 if not given)
   - City/office preference (default: Hanoi → HN if not given)

2. CITY-TO-OFFICE MAPPING — users say city names, not codes:
   - "Hà Nội" / "Hanoi" / not specified → HN (Hà Nội Office)  ← DEFAULT
   - "Đà Nẵng" / "Da Nang"              → DN (Đà Nẵng Office)
   - "Hồ Chí Minh" / "Ho Chi Minh" / "HCMC" / "Sài Gòn" / "Saigon" → HCM (HCM Office)

3. ROOM SELECTION — STRICT RULES:
   ⚠️  You MUST ONLY use rooms from the AVAILABLE ROOMS list at the top of this prompt.
   ⚠️  NEVER invent, fabricate, or reference any room not in that list.
       Hallucinated names like "Phòng Họp A2", "B3", "Conference Room 1", etc. are FORBIDDEN.
   ⚠️  The room_name and room_code in the booking JSON MUST exactly match an entry in the list above.

   Pick the SMALLEST room in the chosen office whose capacity ≥ requested attendees:
   - HN  ascending: Orchid (id: orchid, 18p) → Lotus (id: lotus, 25p)
   - DN  ascending: Jasmine (id: jasmine, 12p) → Tulip (id: tulip, 16p)
   - HCM ascending: Rose (id: rose, 8p) → Daisy (id: daisy, 10p) → Blossom (id: blossom, 15p) → Sun Flower (id: sunflower, 20p)

4. APPROVER — assign the admin for the selected office:
   - HN  → Nguyễn Văn Trang <nvtrang3@cmcglobal.vn> (Floor 6)
   - DN  → Trần Thị Hương <thuong5@cmcglobal.vn> (Floor 3)
   - HCM → Lê Minh Khoa <lmkhoa2@cmcglobal.vn> (Floor 3)

5. OPTIONAL FIELDS — apply defaults silently without mentioning them:
   - End time    → start_time + 1 hour
   - Attendees   → 5 people
   - Location    → HN (Hà Nội)

   The ONLY fields you may ask about (one question max, combined):
   ✅ title/purpose — if completely absent
   ✅ start time    — if completely absent
   ✅ date          — ONLY if there is zero date hint (no day, no relative expression, nothing)
   ❌ NEVER ask about: end time, duration, number of attendees, location, city, room

   As soon as title + date + start_time are known (or computable), go to step 6.

6. CONFIRMATION SUMMARY — once all required fields are resolved, present the booking
   details in a structured table and ask the user to confirm. Do NOT output a booking
   block yet. Use this exact markdown format (adapt field values):

   📋 **Xác nhận thông tin đặt phòng**

   | | |
   |---|---|
   | 📋 **Tiêu đề** | Họp với khách Sony |
   | 📅 **Ngày** | Thứ Tư, 05/03/2026 |
   | 🕐 **Thời gian** | 14:00 – 15:00 |
   | 🏢 **Phòng** | Orchid – Lotte Center Hanoi (Tầng 8) |
   | 📍 **Văn phòng** | Hà Nội |
   | 👥 **Số người** | 5 người |
   | ✉️ **Phê duyệt bởi** | Nguyễn Văn Trang |

   *Bạn có muốn xác nhận đặt phòng không?*

   Keep the table header row (| | | and |---|---|) exactly as shown.

7. BOOKING BLOCK — output ONLY after the user explicitly confirms (says "yes", "đặt",
   "xác nhận", "ok", "được", "đồng ý", or any clear approval).
   Output a short acknowledgement line, then the booking block in this exact format:

```booking
{{
  "id": "MTG-<OFFICE_CODE>-<uuid4_no_hyphens>",
  "title": "Meeting title",
  "date": "YYYY-MM-DD",
  "start_time": "HH:MM",
  "end_time": "HH:MM",
  "capacity": 5,
  "location": "HN",
  "room_name": "Orchid",
  "room_code": "orchid",
  "room_floor": 8,
  "room_building": "Lotte Center Hanoi",
  "room_equipment": ["projector"],
  "requester": "<user name or email>",
  "invitees": [],
  "status": "draft",
  "approver": {{ "name": "Admin Name", "email": "admin@cmcglobal.vn" }}
}}
```

   ID format: "MTG-" + office code (HN/DN/HCM) + "-" + UUID v4 without hyphens (32 hex chars).
   Example: MTG-HN-a1b2c3d4e5f67890abcdef1234567890
   Keep any explanatory text OUTSIDE the booking block.

══════════════════════════════════════
ACTIVE BOOKINGS REGISTRY (session)
══════════════════════════════════════
{{ACTIVE_BOOKINGS}}

CONFLICT DETECTION: If the user requests a room/time that overlaps with an existing
booking above, warn them and suggest an alternative room or time slot.

BOOKING OPERATIONS:
- "List my bookings" / "Danh sách lịch họp" → list all entries above
- "Cancel meeting [description]" → identify the booking by context, confirm cancellation
  with the user, then respond naturally. Do NOT output a new booking block for cancellations.
- "Update meeting [description]" → start a new booking flow with the corrected details

══════════════════════════════════════
HANDLING THE CALENDAR INVITE SUMMARY
══════════════════════════════════════
When the user message starts with [CALENDAR_SENT], the booking flow is complete.
Respond warmly to congratulate the user and confirm the key meeting details.
Do NOT output a new booking block in this response.
""".strip()


def get_booking_agent_system_prompt() -> str:
    """Build the system prompt dynamically, injecting the current date and live booking registry."""
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d (%A, %d %B %Y)")
    return (
        _BOOKING_AGENT_SYSTEM_PROMPT_STATIC
        .replace("{CURRENT_DATE}", current_date)
        .replace("{ACTIVE_BOOKINGS}", _build_active_bookings_text())
    )


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
PORT = int(os.environ.get("GEMINI_PROXY_PORT", 4000))

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}

# Models exposed to Open WebUI
AVAILABLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]
DEFAULT_MODEL = "gemini-2.0-flash"

ssl_ctx = ssl.create_default_context(cafile=certifi.where())


# ---------------------------------------------------------------------------
# Format converters
# ---------------------------------------------------------------------------

def openai_messages_to_gemini(messages: list) -> tuple[list, str | None]:
    """Convert OpenAI messages array to Gemini contents + system_instruction."""
    system_parts: list[str] = []
    contents: list[dict] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Normalise content to a list of parts
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
                            # base64 inline image
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

async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "gemini-proxy"}, headers=CORS_HEADERS)


async def handle_models(request: web.Request) -> web.Response:
    now = int(time.time())
    data = [
        {
            "id": m,
            "object": "model",
            "created": now,
            "owned_by": "google",
        }
        for m in AVAILABLE_MODELS
    ]
    return web.json_response({"object": "list", "data": data}, headers=CORS_HEADERS)


async def handle_chat_completions(request: web.Request) -> web.Response:
    # --- auth (accept any non-empty Bearer token) ---
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

    model = body.get("model", DEFAULT_MODEL)
    # Strip any org prefix Open WebUI might add (e.g. "google/gemini-2.0-flash")
    if "/" in model:
        model = model.split("/", 1)[1]
    if model not in AVAILABLE_MODELS:
        model = DEFAULT_MODEL

    streaming = body.get("stream", False)
    # Always prepend the booking agent system prompt so it applies to every request.
    # openai_messages_to_gemini() concatenates all system messages in order, so
    # this is non-destructive alongside any system prompt Open WebUI may send.
    messages = [{"role": "system", "content": get_booking_agent_system_prompt()}] + body.get("messages", [])
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
        # --- non-streaming ---
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

    # --- streaming ---
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

    # Opening role delta
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
                err_payload = json.dumps({"error": err_text})
                await response.write(f"data: {err_payload}\n\n".encode())
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
# Booking registry routes
# ---------------------------------------------------------------------------

async def handle_save_booking(request: web.Request) -> web.Response:
    try:
        booking = await request.json()
        booking_registry[booking["id"]] = booking
        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400, headers=CORS_HEADERS)


async def handle_delete_booking(request: web.Request) -> web.Response:
    booking_id = request.match_info.get("booking_id", "")
    booking_registry.pop(booking_id, None)
    return web.json_response({"ok": True}, headers=CORS_HEADERS)


async def handle_list_bookings(_request: web.Request) -> web.Response:
    return web.json_response(list(booking_registry.values()), headers=CORS_HEADERS)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_options)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/v1/models", handle_models)
    app.router.add_get("/v1/models/{model_id}", handle_models)  # single model lookup
    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    # Booking registry CRUD
    app.router.add_post("/api/bookings", handle_save_booking)
    app.router.add_delete("/api/bookings/{booking_id}", handle_delete_booking)
    app.router.add_get("/api/bookings", handle_list_bookings)
    return app


if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY is not set. Requests will fail.")
    print(f"Gemini Proxy starting on http://0.0.0.0:{PORT}")
    print(f"Open WebUI connection settings:")
    print(f"  URL:     http://localhost:{PORT}/v1")
    print(f"  API Key: sk-1234  (any non-empty value)")
    print(f"  Models:  {', '.join(AVAILABLE_MODELS)}")
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
