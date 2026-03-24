"""
title: Office Tour Agent
description: Handles office tour scheduling — extracts visit details from multilingual input (Vietnamese, English, Japanese), classifies tour types by group size, suggests local Hanoi activities with Google Maps links, generates tour plan summaries with PMS checklists, and produces tour metrics charts
requirements: aiohttp,certifi,matplotlib
"""

import base64
import io
import json
import re
import ssl
import time
import uuid
from datetime import date, datetime
from typing import AsyncGenerator, Callable
from urllib.parse import quote_plus

import aiohttp
import certifi
from pydantic import BaseModel, Field

_ssl_ctx = ssl.create_default_context(cafile=certifi.where())

# ──────────────────────────────────────────────────────────────────────
# Tour type definitions
# ──────────────────────────────────────────────────────────────────────

TOUR_TYPES = {
    "quick": {
        "name": "Quick Tour",
        "duration_mins": 55,
        "focus_areas": [
            "Computer Vision",
            "Service Offering",
            "Chatbot",
        ],
    },
    "standard": {
        "name": "Standard Tour",
        "duration_mins": 75,
        "focus_areas": [
            "Computer Vision",
            "Service Offering",
            "Chatbot",
            "All-in-one Demo",
            "AI Agent",
            "Security GDC",
        ],
    },
    "full": {
        "name": "Full Tour",
        "duration_mins": 115,
        "focus_areas": [
            "Computer Vision",
            "Service Offering",
            "Chatbot",
            "All-in-one Demo",
            "AI Agent",
            "Vietnam Cultural Activities",
            "Security GDC",
        ],
    },
}

# ──────────────────────────────────────────────────────────────────────
# Mock historical tour data (for chart generation)
# ──────────────────────────────────────────────────────────────────────

MOCK_TOUR_HISTORY = [
    {"quarter": "Q1 2025", "quick": 12, "standard": 8, "full": 5, "total_visitors": 320},
    {"quarter": "Q2 2025", "quick": 15, "standard": 10, "full": 7, "total_visitors": 410},
    {"quarter": "Q3 2025", "quick": 18, "standard": 12, "full": 4, "total_visitors": 390},
    {"quarter": "Q4 2025", "quick": 20, "standard": 14, "full": 9, "total_visitors": 520},
    {"quarter": "Q1 2026", "quick": 8, "standard": 6, "full": 3, "total_visitors": 210},
]

MOCK_TOP_CLIENTS = [
    {"client": "Sony", "tours": 6, "total_visitors": 42},
    {"client": "Samsung", "tours": 5, "total_visitors": 55},
    {"client": "Toyota", "tours": 4, "total_visitors": 28},
    {"client": "Panasonic", "tours": 3, "total_visitors": 18},
    {"client": "LG", "tours": 3, "total_visitors": 22},
    {"client": "Bosch", "tours": 2, "total_visitors": 15},
    {"client": "Siemens", "tours": 2, "total_visitors": 12},
    {"client": "Intel", "tours": 1, "total_visitors": 8},
]

# ──────────────────────────────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are the Office Tour Agent for C-Agents, an enterprise AI assistant specializing \
in office tour scheduling and visitor management.

IMPORTANT: The user talking to you is an INTERNAL EMPLOYEE (e.g., admin, receptionist, \
project manager) who is planning a tour for visiting clients. The user is NOT the client. \
Do NOT write letters, emails, or address the client directly. Speak directly to the \
internal employee in a conversational, helpful tone.

Your expertise includes:
- Extracting visit details from multilingual input (Vietnamese, English, Japanese, etc.)
- Classifying tour types based on group size
- Suggesting specific named locations in Hanoi for after-tour activities
- Generating tour plan summaries with PMS checklists
- Providing tour metrics and analytics

Tour Classification Rules:
- Group > 15 members → Quick Tour (55 mins): Computer Vision, Service Offering, Chatbot
- Group 5–15 members → Standard Tour (75 mins): + All-in-one Demo, AI Agent, Security GDC
- Group ≤ 5 members → Full Tour (115 mins): + Vietnam Cultural Activities, Security GDC

Guidelines:
- Always respond in the SAME LANGUAGE as the user's message
- The [DATA] section below is INTERNAL CONTEXT for you only. NEVER output the [DATA] block, \
its raw text, labels like "[DATA]", "[ACTIVITY SUGGESTIONS]", "ACTION:", "VISIT DETAILS:", \
or any internal instructions in your response. Rewrite all information in your own words \
using clean, user-friendly formatting.
- Format responses with clear structure: headings, bullet points, bold for key details
- For post-tour activities, suggest SPECIFIC named places (e.g., "Hoan Kiem Lake", \
"Bun Cha Huong Lien restaurant") — not generic categories. Always include a Google Maps \
link for each place: https://www.google.com/maps/search/?api=1&query=<URL-encoded place name + Hanoi>
- When presenting a tour plan, include duration, focus areas, and actionable next steps
- Ask the user to confirm or modify the tour suggestion before generating the final summary

CRITICAL FLOW RULES:
1. On the FIRST response (tour suggestion), ONLY present: tour type, duration, focus areas, \
and post-tour activity suggestions. Ask the user to confirm or modify. \
Do NOT include PMS checklist, action items, or next steps about reservations/preparation at this stage.
2. ONLY after the user explicitly confirms the plan, THEN output the final summary WITH the \
PMS checklist below.

PMS Checklist (ONLY include after user confirms):
- [ ] Create visitor registration ticket in PMS
- [ ] Reserve meeting rooms for tour duration
- [ ] Assign tour guide
- [ ] Prepare demo stations (relevant focus areas)
- [ ] Order catering/refreshments
- [ ] Arrange transportation (if needed)
- [ ] Send confirmation email to client contact\
"""

# Prompt for LLM-based extraction of visit info
EXTRACTION_PROMPT = """\
You are a data extraction assistant. Extract visit information from the user message below.
The message may be in any language (Vietnamese, English, Japanese, Korean, etc.).

Today's date is {today}. Use {year} as the default year if not specified.

Return ONLY a JSON object with these fields:
- "client_name": string (the company or delegation name)
- "start_date": string in YYYY-MM-DD format
- "end_date": string in YYYY-MM-DD format
- "member_count": integer (number of visitors/guests)

If a field cannot be determined, use null.
Do not include any text outside the JSON object. No markdown fences.

User message: {message}\
"""

# Keywords for intent detection
CHART_KEYWORDS = [
    "chart", "graph", "metrics", "statistics", "stats", "report",
    "q1", "q2", "q3", "q4", "quarterly", "quarter",
    "how many tours", "number of tours", "tours executed", "tour data",
    "tours per", "tour count", "tour history",
    "biểu đồ", "thống kê", "báo cáo", "bao nhiêu tour", "số lượng tour",
    "グラフ", "統計", "チャート", "ツアー数",
]

SUMMARY_KEYWORDS = [
    "summary", "summarize", "checklist", "pms", "confirm", "approve",
    "finalize", "final plan",
    "tóm tắt", "xác nhận", "hoàn tất",
    "まとめ", "確認", "チェックリスト",
]

TOUR_REQUEST_KEYWORDS = [
    "visit", "tour", "delegation", "guest", "visitor", "coming",
    "khách", "thăm", "đến", "đoàn", "tham quan",
    "訪問", "見学", "ツアー", "来客",
]


# ──────────────────────────────────────────────────────────────────────
# Pipe
# ──────────────────────────────────────────────────────────────────────


class Pipe:
    class Valves(BaseModel):
        OLLAMA_BASE_URL: str = Field(
            default="http://localhost:11434",
            description="Ollama base URL",
        )
        MODEL: str = Field(
            default="phi4-mini",
            description="Ollama model for response generation",
        )
        ENABLE_WEB_SEARCH: bool = Field(
            default=True,
            description="Enable web search for local activity suggestions",
        )
        WEB_SEARCH_RESULT_COUNT: int = Field(
            default=5,
            description="Number of web search results to fetch",
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        return [{"id": "office-tour-agent", "name": "Office Tour Agent"}]

    # ── standard helpers ─────────────────────────────────────────────

    @staticmethod
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

    @staticmethod
    def _empty_response(model: str) -> dict:
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    async def _call_ollama(self, messages: list[dict]) -> dict:
        url = f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions"
        payload = {"model": self.valves.MODEL, "messages": messages, "stream": False}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status != 200:
                        return self._empty_response(self.valves.MODEL)
                    return await resp.json()
        except Exception as e:
            print(f"[office-tour-agent] LLM error: {e!r}", flush=True)
            return self._empty_response(self.valves.MODEL)

    async def _stream_ollama(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        url = f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions"
        payload = {"model": self.valves.MODEL, "messages": messages, "stream": True}
        session = aiohttp.ClientSession()
        try:
            resp = await session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=300)
            )
            if resp.status != 200:
                yield f"Error contacting LLM (status {resp.status})"
                return
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                if line == "data: [DONE]":
                    break
                if line.startswith("data: "):
                    yield line
        finally:
            await session.close()

    # ── tour business logic ──────────────────────────────────────────

    @staticmethod
    def _classify_tour(member_count: int) -> tuple[str, dict]:
        """Classify tour type based on group size. Returns (key, tour_type_dict)."""
        if member_count > 15:
            return "quick", TOUR_TYPES["quick"]
        elif member_count >= 5:
            return "standard", TOUR_TYPES["standard"]
        else:
            return "full", TOUR_TYPES["full"]

    async def _extract_visit_info(self, user_message: str) -> dict | None:
        """Use LLM to extract structured visit info from multilingual input."""
        today = date.today()
        prompt = EXTRACTION_PROMPT.format(
            today=today.isoformat(),
            year=today.year,
            message=user_message,
        )
        messages = [{"role": "user", "content": prompt}]
        result = await self._call_ollama(messages)
        raw = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not raw:
            return None

        # Strip markdown code fences if present
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            # Validate required fields
            if data.get("client_name") and data.get("member_count") is not None:
                return data
            return None
        except (json.JSONDecodeError, TypeError):
            print(f"[office-tour-agent] Failed to parse extraction: {raw}", flush=True)
            return None

    def _build_tour_suggestion(self, visit_info: dict) -> str:
        """Format extracted visit info + classified tour into a [DATA] block."""
        member_count = visit_info.get("member_count", 1)
        _, tour = self._classify_tour(member_count)

        focus = ", ".join(tour["focus_areas"])
        return (
            f"client_name={visit_info.get('client_name', 'Unknown')}\n"
            f"start_date={visit_info.get('start_date', 'TBD')}\n"
            f"end_date={visit_info.get('end_date', 'TBD')}\n"
            f"member_count={member_count}\n"
            f"tour_type={tour['name']}\n"
            f"tour_duration={tour['duration_mins']} minutes\n"
            f"focus_areas={focus}\n"
            f"instruction=Present the tour recommendation and post-tour activity suggestions "
            f"with Google Maps links. Ask the user to confirm or modify. "
            f"Do NOT include the PMS checklist, action items, or preparation steps yet — "
            f"those come only after the user confirms."
        )

    # ── web search ───────────────────────────────────────────────────

    async def _web_search_activities(self, city: str = "Hanoi") -> str:
        """Search for specific tourist attractions and restaurants in the city."""
        query = f"top rated specific restaurants landmarks attractions to visit in {city} Hoan Kiem Old Quarter"
        try:
            from open_webui.retrieval.web.duckduckgo import search_duckduckgo

            results = search_duckduckgo(query, count=self.valves.WEB_SEARCH_RESULT_COUNT)
        except ImportError:
            print("[office-tour-agent] DuckDuckGo search not available", flush=True)
            return ""
        except Exception as e:
            print(f"[office-tour-agent] Web search error: {e!r}", flush=True)
            return ""

        if not results:
            return ""

        lines = []
        for i, result in enumerate(results[: self.valves.WEB_SEARCH_RESULT_COUNT], 1):
            title = result.title or ""
            link = result.link or ""
            snippet = result.snippet or ""
            # Generate a Google Maps link from the title
            maps_query = quote_plus(f"{title} {city}")
            maps_link = f"https://www.google.com/maps/search/?api=1&query={maps_query}"
            lines.append(
                f"[{i}] {title}\n"
                f"    URL: {link}\n"
                f"    Google Maps: {maps_link}\n"
                f"    {snippet}"
            )

        return "\n\n".join(lines)

    # ── chart generation ─────────────────────────────────────────────

    async def _generate_chart(self, user_message: str, __event_emitter__: Callable) -> bool:
        """Generate a matplotlib chart and emit it as a file event.

        Returns True if chart was generated successfully, False if matplotlib
        is not available (caller should fall back to text-only response).
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("[office-tour-agent] matplotlib not available, falling back to text", flush=True)
            return False

        msg = user_message.lower()

        # Determine which chart to generate
        if any(kw in msg for kw in ["client", "khách hàng", "top", "クライアント"]):
            # Top clients bar chart
            fig, ax = plt.subplots(figsize=(10, 6))
            clients = [c["client"] for c in MOCK_TOP_CLIENTS]
            tours = [c["tours"] for c in MOCK_TOP_CLIENTS]
            visitors = [c["total_visitors"] for c in MOCK_TOP_CLIENTS]

            x = range(len(clients))
            width = 0.35
            bars1 = ax.bar([i - width / 2 for i in x], tours, width, label="Tours", color="#4ECDC4")
            bars2 = ax.bar([i + width / 2 for i in x], visitors, width, label="Total Visitors", color="#FF6B6B")

            ax.set_xlabel("Client")
            ax.set_ylabel("Count")
            ax.set_title("Top Clients — Tours & Visitors")
            ax.set_xticks(list(x))
            ax.set_xticklabels(clients, rotation=45, ha="right")
            ax.legend()

            for bar in bars1:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                        str(int(bar.get_height())), ha="center", va="bottom", fontsize=9)
            for bar in bars2:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                        str(int(bar.get_height())), ha="center", va="bottom", fontsize=9)

        elif any(kw in msg for kw in ["visitor", "total", "khách", "訪問者"]):
            # Total visitors line chart
            fig, ax = plt.subplots(figsize=(10, 6))
            quarters = [h["quarter"] for h in MOCK_TOUR_HISTORY]
            visitors = [h["total_visitors"] for h in MOCK_TOUR_HISTORY]

            ax.plot(quarters, visitors, marker="o", linewidth=2, color="#45B7D1", markersize=8)
            ax.fill_between(range(len(quarters)), visitors, alpha=0.15, color="#45B7D1")
            ax.set_xlabel("Quarter")
            ax.set_ylabel("Total Visitors")
            ax.set_title("Total Visitors per Quarter")
            ax.set_xticks(range(len(quarters)))
            ax.set_xticklabels(quarters)

            for i, v in enumerate(visitors):
                ax.annotate(str(v), (i, v), textcoords="offset points", xytext=(0, 10), ha="center")

        else:
            # Default: tours per type grouped bar chart
            fig, ax = plt.subplots(figsize=(10, 6))
            quarters = [h["quarter"] for h in MOCK_TOUR_HISTORY]
            quick = [h["quick"] for h in MOCK_TOUR_HISTORY]
            standard = [h["standard"] for h in MOCK_TOUR_HISTORY]
            full = [h["full"] for h in MOCK_TOUR_HISTORY]

            x = range(len(quarters))
            width = 0.25
            bars1 = ax.bar([i - width for i in x], quick, width, label="Quick Tour", color="#FF6B6B")
            bars2 = ax.bar(list(x), standard, width, label="Standard Tour", color="#4ECDC4")
            bars3 = ax.bar([i + width for i in x], full, width, label="Full Tour", color="#45B7D1")

            ax.set_xlabel("Quarter")
            ax.set_ylabel("Number of Tours")
            ax.set_title("Office Tours by Type per Quarter")
            ax.set_xticks(list(x))
            ax.set_xticklabels(quarters)
            ax.legend()

            for bars in [bars1, bars2, bars3]:
                for bar in bars:
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                            str(int(bar.get_height())), ha="center", va="bottom", fontsize=8)

        plt.tight_layout()

        # Save to buffer and base64 encode
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")
        data_url = f"data:image/png;base64,{b64}"

        # Emit file event
        if __event_emitter__:
            await __event_emitter__({
                "type": "chat:message:files",
                "data": {"files": [{"type": "image", "url": data_url}]},
            })

        return True

    # ── intent detection ─────────────────────────────────────────────

    @staticmethod
    def _detect_intent(user_message: str) -> str:
        """Detect user intent from the latest message."""
        msg = user_message.lower()

        if any(kw in msg for kw in CHART_KEYWORDS):
            return "chart"

        if any(kw in msg for kw in SUMMARY_KEYWORDS):
            return "summary"

        if any(kw in msg for kw in TOUR_REQUEST_KEYWORDS):
            return "tour_request"

        return "general"

    # ── main entry point ─────────────────────────────────────────────

    async def pipe(
        self,
        body: dict,
        __user__: dict,
        __event_emitter__: Callable = None,
        __task__: str = None,
        __metadata__: dict = None,
    ) -> AsyncGenerator[str, None] | str:
        # Background tasks (title generation, etc.)
        if __task__:
            result = await self._call_ollama(body.get("messages", []))
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        messages = body.get("messages", [])
        user_message = self._extract_last_user_message(messages)
        streaming = body.get("stream", False)

        intent = self._detect_intent(user_message)
        data_context = ""

        # ── Chart / metrics request ──
        if intent == "chart":
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": "Generating tour metrics chart...", "done": False}}
                )
            chart_ok = await self._generate_chart(user_message, __event_emitter__)

            # Build raw mock data context so the LLM can answer textually
            history_text = "\n".join(
                f"  {h['quarter']}: Quick={h['quick']}, Standard={h['standard']}, "
                f"Full={h['full']}, Total Visitors={h['total_visitors']}"
                for h in MOCK_TOUR_HISTORY
            )
            clients_text = "\n".join(
                f"  {c['client']}: {c['tours']} tours, {c['total_visitors']} visitors"
                for c in MOCK_TOP_CLIENTS
            )
            chart_note = (
                "A chart image has also been displayed above."
                if chart_ok
                else ""
            )
            data_context = (
                f"TOUR HISTORY DATA:\n{history_text}\n\n"
                f"TOP CLIENTS DATA:\n{clients_text}\n\n"
                f"Use ONLY this data to answer the user's question. Present it as real data.\n"
                f"ALWAYS format the data as a markdown table. "
                f"Example: | Quarter | Quick | Standard | Full | Total Visitors |\n"
                f"{chart_note}"
            )

            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": "Chart generated" if chart_ok else "Data ready", "done": True}}
                )

        # ── New tour request ──
        elif intent == "tour_request":
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": "Extracting visit details...", "done": False}}
                )

            visit_info = await self._extract_visit_info(user_message)

            if visit_info:
                tour_suggestion = self._build_tour_suggestion(visit_info)

                # Web search for local activities
                activity_context = ""
                if self.valves.ENABLE_WEB_SEARCH:
                    if __event_emitter__:
                        await __event_emitter__(
                            {"type": "status", "data": {"description": "Searching for local activities in Hanoi...", "done": False}}
                        )
                    activity_context = await self._web_search_activities("Hanoi")

                data_context = tour_suggestion
                if activity_context:
                    data_context += f"\n\n[ACTIVITY SUGGESTIONS]\n{activity_context}"

                if __event_emitter__:
                    await __event_emitter__(
                        {"type": "status", "data": {"description": "Tour plan ready", "done": True}}
                    )
            else:
                data_context = (
                    "Could not extract visit details from the user message. "
                    "Ask the user to provide: client name, visit dates, and number of visitors."
                )
                if __event_emitter__:
                    await __event_emitter__(
                        {"type": "status", "data": {"description": "Need more details", "done": True}}
                    )

        # ── Summary / confirmation ──
        elif intent == "summary":
            data_context = (
                "The user has confirmed the tour plan. Generate a final summary based on "
                "the tour plan discussed in the conversation above. Include:\n"
                "1. Visit details (client, dates, group size)\n"
                "2. Tour type, duration, and focus areas\n"
                "3. Post-tour activities (with Google Maps links)\n"
                "4. PMS checklist — include EXACTLY as follows:\n"
                "- [ ] Create visitor registration ticket in PMS\n"
                "- [ ] Reserve meeting rooms for tour duration\n"
                "- [ ] Assign tour guide\n"
                "- [ ] Prepare demo stations (relevant focus areas)\n"
                "- [ ] Order catering/refreshments\n"
                "- [ ] Arrange transportation (if needed)\n"
                "- [ ] Send confirmation email to client contact\n"
                "Respond in the same language as the user."
            )

        # ── General / fallback ──
        # (no special data context, LLM uses system prompt + conversation history)

        # Build augmented messages
        system = SYSTEM_PROMPT
        if data_context:
            system += f"\n\n[DATA]\n{data_context}"

        augmented = [{"role": "system", "content": system}] + messages

        if not streaming:
            result = await self._call_ollama(augmented)
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        return self._stream_ollama(augmented)
