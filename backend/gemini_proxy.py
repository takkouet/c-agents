"""
Gemini Proxy - OpenAI-compatible API that translates to Google Gemini.
Runs on port 4000 so Open WebUI can connect via:
  URL:     http://localhost:4000/v1
  API Key: sk-1234  (any non-empty string)
"""

import asyncio
import base64
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from datetime import datetime, timedelta

import aiohttp
import certifi
import ssl
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

from data.meeting_data import ADMINS, CATERING_OPTIONS, DEPARTMENTS, MEETING_ROOMS

# ---------------------------------------------------------------------------
# SQLite database setup
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent / "data" / "meeting_booking.db"

# JSON columns that need serialisation round-trip
_JSON_COLS = {"room_equipment", "invitees", "approver", "catering", "email_details"}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for col in _JSON_COLS:
        if d.get(col):
            try:
                d[col] = json.loads(d[col])
            except (json.JSONDecodeError, TypeError):
                pass
    # normalise email_sent to bool
    if "email_sent" in d:
        d["email_sent"] = bool(d["email_sent"])
    return d


def init_db() -> None:
    """Create tables and seed reference data. Safe to call multiple times (idempotent)."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS meeting_rooms (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                code        TEXT NOT NULL,
                building    TEXT,
                floor       INTEGER,
                capacity    INTEGER,
                equipment   TEXT,
                available   INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS admins (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                email           TEXT NOT NULL,
                role            TEXT,
                department_code TEXT,
                floor           INTEGER
            );

            CREATE TABLE IF NOT EXISTS departments (
                id       TEXT PRIMARY KEY,
                name     TEXT NOT NULL,
                code     TEXT,
                floor    INTEGER,
                admin_id TEXT
            );

            CREATE TABLE IF NOT EXISTS catering_options (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                price      INTEGER,
                per_person INTEGER DEFAULT 1,
                icon       TEXT
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id              TEXT PRIMARY KEY,
                title           TEXT,
                client          TEXT,
                date            TEXT,
                start_time      TEXT,
                end_time        TEXT,
                capacity        INTEGER,
                location        TEXT,
                room_name       TEXT,
                room_code       TEXT,
                room_floor      INTEGER,
                room_building   TEXT,
                room_equipment  TEXT,
                requester       TEXT,
                invitees        TEXT,
                status          TEXT DEFAULT 'draft',
                approver        TEXT,
                admin_note      TEXT,
                catering        TEXT,
                email_sent      INTEGER DEFAULT 0,
                email_details   TEXT,
                created_at      INTEGER,
                updated_at      INTEGER
            );
        """)

        # Seed reference tables (INSERT OR IGNORE = idempotent)
        for r in MEETING_ROOMS:
            conn.execute(
                "INSERT OR IGNORE INTO meeting_rooms (id,name,code,building,floor,capacity,equipment,available) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (r["id"], r["name"], r["code"], r.get("building"), r.get("floor"),
                 r.get("capacity"), json.dumps(r.get("equipment", [])), int(r.get("available", True)))
            )
        for a in ADMINS:
            conn.execute(
                "INSERT OR IGNORE INTO admins (id,name,email,role,department_code,floor) VALUES (?,?,?,?,?,?)",
                (a["id"], a["name"], a["email"], a.get("role"), a.get("department_code"), a.get("floor"))
            )
        for d in DEPARTMENTS:
            conn.execute(
                "INSERT OR IGNORE INTO departments (id,name,code,floor,admin_id) VALUES (?,?,?,?,?)",
                (d["id"], d["name"], d.get("code"), d.get("floor"), d.get("admin_id"))
            )
        for c in CATERING_OPTIONS:
            conn.execute(
                "INSERT OR IGNORE INTO catering_options (id,name,price,per_person,icon) VALUES (?,?,?,?,?)",
                (c["id"], c["name"], c.get("price"), int(c.get("per_person", True)), c.get("icon"))
            )
        conn.commit()
        # Migration: add columns that may not exist in older DBs
        for migration in [
            "ALTER TABLE bookings ADD COLUMN client TEXT",
        ]:
            try:
                conn.execute(migration)
                conn.commit()
            except Exception:
                pass  # Column already exists — safe to ignore
    print(f"[DB] Initialised: {DB_PATH}")


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

def _extract_user_email(auth_header: str) -> str:
    """Decode the user email from a JWT Bearer token (payload only, no signature verification)."""
    try:
        token = auth_header.removeprefix("Bearer ").strip()
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("email", "")
    except Exception:
        return ""


def _build_active_bookings_text(user_email: str = "") -> str:
    """Return non-cancelled/rejected bookings for the given user (or all if no email).
    Used by the agent to:
    - detect room conflicts (approved/sent),
    - find the user's own bookings when they ask to cancel.
    """
    try:
        with get_db() as conn:
            if user_email:
                rows = conn.execute(
                    "SELECT * FROM bookings WHERE status NOT IN ('cancelled','rejected') "
                    "AND lower(requester) = lower(?) ORDER BY date, start_time",
                    (user_email,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM bookings WHERE status NOT IN ('cancelled','rejected') "
                    "ORDER BY date, start_time"
                ).fetchall()
    except Exception:
        rows = []
    if not rows:
        return "  (Không có lịch họp nào đang hoạt động)"
    lines = []
    for row in rows:
        b = dict(row)
        client = b.get('client') or ''
        lines.append(
            f"  - [{b['id']}] \"{b.get('title','?')}\""
            + (f" | Client: {client}" if client else "")
            + f" | {b.get('date','?')} {b.get('start_time','?')} – {b.get('end_time','?')}"
            f" | Room: {b.get('room_code','?')} | Office: {b.get('location','?')}"
            f" | Status: {b.get('status','?')}"
        )
    return "\n".join(lines)


_BOOKING_AGENT_SYSTEM_PROMPT_STATIC = f"""
You are the CMC Global Meeting Room Booking Assistant.

══════════════════════════════════════
AVAILABLE ROOMS
══════════════════════════════════════
⚠️  VALID room_name values — use EXACTLY one of these strings, copy-paste only:
    {_ROOM_LIST}
    Any other name ("A2", "B3", "Phòng Họp X", "Conference Room") is a hallucination.

{_ROOM_LIST}

══════════════════════════════════════
ADMIN CONTACTS (one per office)
══════════════════════════════════════
{_ADMIN_LIST}

══════════════════════════════════════
YOUR ROLE
══════════════════════════════════════
- Your primary role is meeting room booking for CMC Global, but you ALSO handle:
    • Natural conversation during or after the booking flow — e.g. "cảm ơn", "ok", "được rồi",
      "thôi nhé", greetings, goodbyes, short clarifications.
    • Follow-up questions after a cancellation — e.g. "đặt phòng mới", "kiểm tra phòng trống".
    • Any message that is clearly part of or related to the booking / cancellation workflow.
- Only refuse with the standard apology for topics clearly outside booking entirely
  (e.g. IT support, HR questions, general company info). Use your judgement.
  Refusal message (Vietnamese): "Xin lỗi, tôi chỉ hỗ trợ đặt phòng họp tại CMC Global. Bạn có muốn đặt phòng không?"
  Refusal message (English): "Sorry, I can only help with meeting room bookings at CMC Global. Would you like to book a room?"
- AMENDMENT DETECTION: If this conversation already contains a ```booking``` block
  AND the user's latest message mentions any meeting detail (attendee count, date, time,
  room, location) without starting a completely new unrelated request, treat it as an
  update to the previously discussed booking. Re-run steps 1–6, carrying over all fields
  from the previous booking except the ones the user explicitly changed.
  NEVER refuse with "I only help with bookings" when there is prior booking context.
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

   RELATIVE DATE RESOLUTION — use the pre-computed values from TODAY context, never ask:
     "ngày mai" / "tomorrow"                        → tomorrow
     "ngày kia" / "ngày kìa" / "2 ngày nữa"        → day_after_tomorrow
     "tuần tới" / "next week"                       → next_week
     "thứ 2 tuần sau" / "thứ hai tuần sau"          → next_monday
     "thứ 3 tuần sau" / "thứ ba tuần sau"           → next_tuesday
     "thứ 4 tuần sau" / "thứ tư tuần sau"           → next_wednesday
     "thứ 5 tuần sau" / "thứ năm tuần sau"          → next_thursday
     "thứ 6 tuần sau" / "thứ sáu tuần sau"          → next_friday
     "thứ 7 tuần sau" / "thứ bảy tuần sau"          → next_saturday
     "chủ nhật tuần sau"                            → next_sunday
   All these exact date values are provided in TODAY = {{CURRENT_DATE}}.
   Copy the value directly — do NOT add or subtract days from them.
   Always resolve to YYYY-MM-DD before writing the booking block.
   NEVER ask "Ngày kia là ngày nào?" or any equivalent — read the value from TODAY.

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
   - Client name (`client` field) — ALWAYS extract the name of the person, company, or team being
     met with (e.g. "Sony", "Kuok Group", "HR team"). This field is used for cancellation lookup,
     so it must always be populated. If not explicitly stated, infer it from the meeting title.
   - Date → convert to DD/MM/YYYY (resolve relative dates using the rule above) - eg: 07/12/2026
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
  "client": "<client/company/visitor name — e.g. Sony, Kuok Group, or empty string if internal>",
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
- "List my bookings" / "Danh sách lịch họp" → list all entries from the registry above.
- "Update meeting [description]" → start a new booking flow with the corrected details.

CANCELLATION WORKFLOW — follow these 3 steps exactly:

Step C1 — SEARCH: When user wants to cancel a meeting, search ACTIVE BOOKINGS REGISTRY above
  by matching BOTH criteria (resolve relative dates same as booking workflow — TODAY = {{CURRENT_DATE}}):
    a) Client name — fuzzy/partial case-insensitive match of the name the user mentions (e.g. "Sony")
       against the `Client` field in the registry.
    b) Date and/or time hint — match against the date/start_time shown in the registry.
  - If only one criterion given (e.g. client name only), match on that alone.
  - If no match found: reply "Không tìm thấy lịch họp phù hợp. Bạn có thể mô tả rõ hơn không?"
  - If multiple matches: list them and ask which one.

Step C2 — CONFIRM: Show a summary table before cancelling (do NOT cancel yet):

  ❌ **Xác nhận huỷ lịch họp**

  | | |
  |---|---|
  | 📋 **Tiêu đề** | <title from registry> |
  | 🏢 **Khách/Đối tác** | <client from registry> |
  | 📅 **Ngày** | <formatted date> |
  | 🕐 **Thời gian** | <start_time> – <end_time> |
  | 🏢 **Phòng** | <room_name> |
  | 📍 **Văn phòng** | <location> |
  | 🔖 **Trạng thái** | <status label in Vietnamese — use the mapping below> |

  Status label mapping:
    draft     → Chờ xác nhận
    pending   → Chờ duyệt
    approved  → Đã duyệt
    sent      → Đã gửi
    cancelled → Đã hủy
    rejected  → Từ chối

  *Bạn có chắc muốn huỷ lịch họp này không?*

Step C3 — EXECUTE: ONLY after user explicitly confirms (says "có", "huỷ", "yes", "đồng ý",
  "xác nhận", or any clear approval), output the cancellation block below, then confirm naturally.

```cancel_booking
{{"id": "<exact booking id copied from registry — e.g. MTG-HN-abc123...>"}}
```

  ⚠️  RULES:
  - The id MUST be copied verbatim from the ACTIVE BOOKINGS REGISTRY (the [id] field).
  - NEVER invent or guess an id.
  - NEVER output a ```booking block for cancellations — only ```cancel_booking.
  - Keep all explanatory text OUTSIDE the cancel_booking block.

POST-CANCELLATION: After confirming the cancellation naturally, always follow up by
  asking what else you can help with, then suggest ONLY the following (actions this agent
  can actually perform):
    • "Đặt lịch họp mới" — start the booking workflow for a new meeting
    • "Kiểm tra phòng họp còn trống" — check room availability for a specific date/time
  Do NOT suggest: sending emails manually, contacting admins, rescheduling, or any action
  outside the booking workflow.
  If the user responds with a decline or farewell ("không", "cảm ơn", "bye", "thôi",
  "xong rồi", "ok thôi", "không cần", or similar), reply with a warm goodbye, e.g.:
    "Vâng, chúc bạn một ngày làm việc hiệu quả! Nếu cần đặt phòng họp lần sau,
     mình luôn sẵn sàng hỗ trợ bạn nhé. 😊"
  Otherwise, proceed with the relevant workflow based on the user's response.

CONFLICT DETECTION: warn only when the requested room/time overlaps with a booking whose
  status is 'approved' or 'sent' (a 'pending' or 'draft' booking does NOT block a room).

══════════════════════════════════════
HANDLING THE CALENDAR INVITE SUMMARY
══════════════════════════════════════
When the user message starts with [CALENDAR_SENT], the booking flow is complete.
Respond warmly to congratulate the user and confirm the key meeting details.
Do NOT output a new booking block in this response.
""".strip()


def get_booking_agent_system_prompt(user_email: str = "") -> str:
    """Build the system prompt dynamically, injecting the current date and live booking registry."""
    dt = _get_current_datetime()
    current_date = (
        f"{dt['date']} ({dt['day_of_week']}) | time={dt['time']}"
        f" | tomorrow={dt['tomorrow']}"
        f" | day_after_tomorrow={dt['day_after_tomorrow']}"
        f" | next_week={dt['next_week']}"
        f" | next_monday={dt['next_monday']}"
        f" | next_tuesday={dt['next_tuesday']}"
        f" | next_wednesday={dt['next_wednesday']}"
        f" | next_thursday={dt['next_thursday']}"
        f" | next_friday={dt['next_friday']}"
        f" | next_saturday={dt['next_saturday']}"
        f" | next_sunday={dt['next_sunday']}"
    )
    return (
        _BOOKING_AGENT_SYSTEM_PROMPT_STATIC
        .replace("{CURRENT_DATE}", current_date)
        .replace("{ACTIVE_BOOKINGS}", _build_active_bookings_text(user_email))
    )


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
PORT = int(os.environ.get("GEMINI_PROXY_PORT", 4000))

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PATCH, PUT, DELETE",
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
# Date preprocessing — resolve relative expressions before they reach the LLM
# ---------------------------------------------------------------------------

def _get_current_datetime():
    now = datetime.now()
    day_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

    def _nwd(wd: int) -> str:
        """Next occurrence of weekday wd (0=Mon…6=Sun), never today."""
        days = wd - now.weekday()
        if days <= 0:
            days += 7
        return (now + timedelta(days=days)).strftime("%Y-%m-%d")

    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": day_names[now.weekday()],
        "timestamp": int(now.timestamp()),
        "tomorrow": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
        "day_after_tomorrow": (now + timedelta(days=2)).strftime("%Y-%m-%d"),
        "next_week": (now + timedelta(days=7)).strftime("%Y-%m-%d"),
        "next_monday":    _nwd(0),
        "next_tuesday":   _nwd(1),
        "next_wednesday": _nwd(2),
        "next_thursday":  _nwd(3),
        "next_friday":    _nwd(4),
        "next_saturday":  _nwd(5),
        "next_sunday":    _nwd(6),
    }

def _next_weekday(today, weekday: int):
    """Return the date of the next `weekday` (0=Mon … 6=Sun), never today."""
    # from datetime import timedelta
    days = weekday - today.weekday()
    if days <= 0:
        days += 7
    return today + timedelta(days=days)


def _resolve_dates(text: str) -> str:
    """
    Replace Vietnamese / English relative-date phrases with absolute DD/MM/YYYY
    strings so the LLM never sees ambiguous expressions like 'ngày kia' or
    'thứ 2 tuần sau' and has no reason to ask the user for clarification.
    """
    if not isinstance(text, str):
        return text
    # from datetime import datetime, timedelta
    today = datetime.now()
    fmt = lambda d: d.strftime('%d/%m/%Y')  # noqa: E731

    pairs = [
        # longest phrases first to avoid partial matches
        (r'the day after tomorrow',                                    fmt(today + timedelta(days=2))),
        (r'ngày kìa',                                                  fmt(today + timedelta(days=2))),
        (r'ngày kia',                                                  fmt(today + timedelta(days=2))),
        (r'2 ngày nữa',                                                fmt(today + timedelta(days=2))),
        (r'ngày mai',                                                  fmt(today + timedelta(days=1))),
        (r'tuần tới',                                                  fmt(today + timedelta(days=7))),
        (r'tuần sau',                                                  fmt(today + timedelta(days=7))),
        (r'next week',                                                 fmt(today + timedelta(days=7))),
        (r'tomorrow',                                                  fmt(today + timedelta(days=1))),
        # "thứ X tuần sau" and "thứ X này" → next occurrence of that weekday
        (r'thứ hai tuần sau|thứ 2 tuần sau|thứ hai này|thứ 2 này',    fmt(_next_weekday(today, 0))),
        (r'thứ ba tuần sau|thứ 3 tuần sau|thứ ba này|thứ 3 này',      fmt(_next_weekday(today, 1))),
        (r'thứ tư tuần sau|thứ 4 tuần sau|thứ tư này|thứ 4 này',      fmt(_next_weekday(today, 2))),
        (r'thứ năm tuần sau|thứ 5 tuần sau|thứ năm này|thứ 5 này',    fmt(_next_weekday(today, 3))),
        (r'thứ sáu tuần sau|thứ 6 tuần sau|thứ sáu này|thứ 6 này',    fmt(_next_weekday(today, 4))),
        (r'thứ bảy tuần sau|thứ 7 tuần sau|thứ bảy này|thứ 7 này',    fmt(_next_weekday(today, 5))),
        (r'chủ nhật tuần sau|chủ nhật này',                           fmt(_next_weekday(today, 6))),
        # English weekdays
        (r'next monday',    fmt(_next_weekday(today, 0))),
        (r'next tuesday',   fmt(_next_weekday(today, 1))),
        (r'next wednesday', fmt(_next_weekday(today, 2))),
        (r'next thursday',  fmt(_next_weekday(today, 3))),
        (r'next friday',    fmt(_next_weekday(today, 4))),
        (r'next saturday',  fmt(_next_weekday(today, 5))),
        (r'next sunday',    fmt(_next_weekday(today, 6))),
    ]
    for pattern, replacement in pairs:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


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
    raw_messages = body.get("messages", [])
    user_email = _extract_user_email(auth)
    messages = [{"role": "system", "content": get_booking_agent_system_prompt(user_email)}] + raw_messages
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
# Booking routes
# ---------------------------------------------------------------------------

def _booking_to_row(b: dict) -> tuple:
    """Serialise a booking dict to the INSERT/REPLACE positional tuple."""
    now = int(time.time())
    return (
        b.get("id"), b.get("title"), b.get("client"), b.get("date"),
        b.get("start_time"), b.get("end_time"),
        b.get("capacity"), b.get("location"), b.get("room_name"), b.get("room_code"),
        b.get("room_floor"), b.get("room_building"),
        json.dumps(b.get("room_equipment") or []),
        b.get("requester"),
        json.dumps(b.get("invitees") or []),
        b.get("status", "draft"),
        json.dumps(b.get("approver")) if b.get("approver") else None,
        b.get("admin_note"),
        json.dumps(b.get("catering")) if b.get("catering") else None,
        int(bool(b.get("email_sent", False))),
        json.dumps(b.get("email_details")) if b.get("email_details") else None,
        b.get("created_at") or now,
        now,  # always update updated_at
    )


async def handle_save_booking(request: web.Request) -> web.Response:
    """Upsert a booking — used for both initial creation and all state updates."""
    try:
        booking = await request.json()
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO bookings "
                "(id,title,client,date,start_time,end_time,capacity,location,"
                " room_name,room_code,room_floor,room_building,room_equipment,"
                " requester,invitees,status,approver,admin_note,catering,"
                " email_sent,email_details,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                _booking_to_row(booking)
            )
            conn.commit()
        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400, headers=CORS_HEADERS)


async def handle_get_booking(request: web.Request) -> web.Response:
    booking_id = request.match_info.get("booking_id", "")
    try:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
        if row is None:
            return web.json_response({"error": "not found"}, status=404, headers=CORS_HEADERS)
        return web.json_response(_row_to_dict(row), headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


async def handle_delete_booking(request: web.Request) -> web.Response:
    booking_id = request.match_info.get("booking_id", "")
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
            conn.commit()
        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


async def handle_list_bookings(_request: web.Request) -> web.Response:
    try:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM bookings ORDER BY created_at DESC").fetchall()
        return web.json_response([_row_to_dict(r) for r in rows], headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


# ---------------------------------------------------------------------------
# Reference-data routes
# ---------------------------------------------------------------------------

async def handle_list_rooms(_request: web.Request) -> web.Response:
    try:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM meeting_rooms").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("equipment"):
                try:
                    d["equipment"] = json.loads(d["equipment"])
                except (json.JSONDecodeError, TypeError):
                    pass
            d["available"] = bool(d.get("available", 1))
            result.append(d)
        return web.json_response(result, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


async def handle_list_admins(_request: web.Request) -> web.Response:
    try:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM admins").fetchall()
        return web.json_response([dict(r) for r in rows], headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


async def handle_list_departments(_request: web.Request) -> web.Response:
    try:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM departments").fetchall()
        return web.json_response([dict(r) for r in rows], headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


async def handle_list_catering(_request: web.Request) -> web.Response:
    try:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM catering_options").fetchall()
        result = [dict(r) | {"per_person": bool(r["per_person"])} for r in rows]
        return web.json_response(result, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


# ---------------------------------------------------------------------------
# Admin CRUD — bookings (PATCH for partial update)
# ---------------------------------------------------------------------------

async def handle_patch_booking(request: web.Request) -> web.Response:
    """Partially update a booking — admin can change status and admin_note."""
    booking_id = request.match_info.get("booking_id", "")
    try:
        data = await request.json()
        with get_db() as conn:
            row = conn.execute("SELECT id FROM bookings WHERE id=?", (booking_id,)).fetchone()
            if row is None:
                return web.json_response({"error": "not found"}, status=404, headers=CORS_HEADERS)
            updates: dict = {}
            if "status" in data:
                updates["status"] = data["status"]
            if "admin_note" in data:
                updates["admin_note"] = data["admin_note"]
            if updates:
                updates["updated_at"] = int(time.time())
                set_clause = ", ".join(f"{k}=?" for k in updates)
                conn.execute(
                    f"UPDATE bookings SET {set_clause} WHERE id=?",
                    (*updates.values(), booking_id)
                )
                conn.commit()
        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


# ---------------------------------------------------------------------------
# Admin CRUD — meeting rooms
# ---------------------------------------------------------------------------

async def handle_add_room(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        rid = data.get("id") or str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO meeting_rooms (id,name,code,building,floor,capacity,equipment,available) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (rid, data.get("name", ""), data.get("code", ""), data.get("building"),
                 data.get("floor"), data.get("capacity"),
                 json.dumps(data.get("equipment") or []), int(bool(data.get("available", True))))
            )
            conn.commit()
        return web.json_response({"ok": True, "id": rid}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400, headers=CORS_HEADERS)


async def handle_update_room(request: web.Request) -> web.Response:
    room_id = request.match_info.get("room_id", "")
    try:
        data = await request.json()
        with get_db() as conn:
            conn.execute(
                "UPDATE meeting_rooms SET name=?,code=?,building=?,floor=?,capacity=?,equipment=?,available=? WHERE id=?",
                (data.get("name", ""), data.get("code", ""), data.get("building"),
                 data.get("floor"), data.get("capacity"),
                 json.dumps(data.get("equipment") or []), int(bool(data.get("available", True))), room_id)
            )
            conn.commit()
        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


async def handle_delete_room(request: web.Request) -> web.Response:
    room_id = request.match_info.get("room_id", "")
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM meeting_rooms WHERE id=?", (room_id,))
            conn.commit()
        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


# ---------------------------------------------------------------------------
# Admin CRUD — admins
# ---------------------------------------------------------------------------

async def handle_add_admin(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        aid = data.get("id") or str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO admins (id,name,email,role,department_code,floor) VALUES (?,?,?,?,?,?)",
                (aid, data.get("name", ""), data.get("email", ""), data.get("role"),
                 data.get("department_code"), data.get("floor"))
            )
            conn.commit()
        return web.json_response({"ok": True, "id": aid}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400, headers=CORS_HEADERS)


async def handle_update_admin(request: web.Request) -> web.Response:
    admin_id = request.match_info.get("admin_id", "")
    try:
        data = await request.json()
        with get_db() as conn:
            conn.execute(
                "UPDATE admins SET name=?,email=?,role=?,department_code=?,floor=? WHERE id=?",
                (data.get("name", ""), data.get("email", ""), data.get("role"),
                 data.get("department_code"), data.get("floor"), admin_id)
            )
            conn.commit()
        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


async def handle_delete_admin(request: web.Request) -> web.Response:
    admin_id = request.match_info.get("admin_id", "")
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM admins WHERE id=?", (admin_id,))
            conn.commit()
        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


# ---------------------------------------------------------------------------
# Admin CRUD — catering options
# ---------------------------------------------------------------------------

async def handle_add_catering(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        cid = data.get("id") or str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO catering_options (id,name,price,per_person,icon) VALUES (?,?,?,?,?)",
                (cid, data.get("name", ""), data.get("price"), int(bool(data.get("per_person", True))),
                 data.get("icon"))
            )
            conn.commit()
        return web.json_response({"ok": True, "id": cid}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400, headers=CORS_HEADERS)


async def handle_update_catering(request: web.Request) -> web.Response:
    catering_id = request.match_info.get("catering_id", "")
    try:
        data = await request.json()
        with get_db() as conn:
            conn.execute(
                "UPDATE catering_options SET name=?,price=?,per_person=?,icon=? WHERE id=?",
                (data.get("name", ""), data.get("price"), int(bool(data.get("per_person", True))),
                 data.get("icon"), catering_id)
            )
            conn.commit()
        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


async def handle_delete_catering(request: web.Request) -> web.Response:
    catering_id = request.match_info.get("catering_id", "")
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM catering_options WHERE id=?", (catering_id,))
            conn.commit()
        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

async def _on_startup(_app: web.Application) -> None:
    init_db()


def create_app() -> web.Application:
    app = web.Application()
    app.on_startup.append(_on_startup)
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_options)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/v1/models", handle_models)
    app.router.add_get("/v1/models/{model_id}", handle_models)
    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    # Bookings CRUD
    app.router.add_get("/api/bookings", handle_list_bookings)
    app.router.add_get("/api/bookings/{booking_id}", handle_get_booking)
    app.router.add_post("/api/bookings", handle_save_booking)
    app.router.add_route("PATCH", "/api/bookings/{booking_id}", handle_patch_booking)
    app.router.add_delete("/api/bookings/{booking_id}", handle_delete_booking)
    # Meeting rooms CRUD
    app.router.add_get("/api/meeting-rooms", handle_list_rooms)
    app.router.add_post("/api/meeting-rooms", handle_add_room)
    app.router.add_put("/api/meeting-rooms/{room_id}", handle_update_room)
    app.router.add_delete("/api/meeting-rooms/{room_id}", handle_delete_room)
    # Admins CRUD
    app.router.add_get("/api/admins", handle_list_admins)
    app.router.add_post("/api/admins", handle_add_admin)
    app.router.add_put("/api/admins/{admin_id}", handle_update_admin)
    app.router.add_delete("/api/admins/{admin_id}", handle_delete_admin)
    # Departments (read-only)
    app.router.add_get("/api/departments", handle_list_departments)
    # Catering options CRUD
    app.router.add_get("/api/catering-options", handle_list_catering)
    app.router.add_post("/api/catering-options", handle_add_catering)
    app.router.add_put("/api/catering-options/{catering_id}", handle_update_catering)
    app.router.add_delete("/api/catering-options/{catering_id}", handle_delete_catering)
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
