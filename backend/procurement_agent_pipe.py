"""
title: Procurement Agent
description: Handles purchase orders, vendor management, procurement budgets, contract tracking, and spend analytics
requirements: aiohttp,certifi
"""

import json
import re
import ssl
import time
import uuid
from datetime import date, datetime, timedelta
from typing import AsyncGenerator, Callable, Optional

import aiohttp
import certifi
from pydantic import BaseModel, Field

_ssl_ctx = ssl.create_default_context(cafile=certifi.where())

# ──────────────────────────────────────────────────────────────────────
# Mock Data
# ──────────────────────────────────────────────────────────────────────

PURCHASE_ORDERS = {
    "PO-2026-001": {
        "vendor": "Acme Office Supplies",
        "requester": "Sarah Chen",
        "department": "Marketing",
        "items": [{"desc": "Standing desks (x10)", "qty": 10, "unit_price": 450.00}],
        "total": 4500.00,
        "status": "Approved",
        "submitted_date": "2026-02-15",
        "approved_date": "2026-02-18",
        "expected_delivery": "2026-03-20",
    },
    "PO-2026-002": {
        "vendor": "TechParts International",
        "requester": "James Rivera",
        "department": "Engineering",
        "items": [
            {"desc": "Dell PowerEdge R760 servers", "qty": 5, "unit_price": 8200.00},
            {"desc": "Network switches (48-port)", "qty": 3, "unit_price": 2400.00},
        ],
        "total": 48200.00,
        "status": "Pending Approval",
        "submitted_date": "2026-03-08",
        "approved_date": None,
        "expected_delivery": None,
    },
    "PO-2026-003": {
        "vendor": "CloudScale Solutions",
        "requester": "Lisa Park",
        "department": "Engineering",
        "items": [{"desc": "AWS Reserved Instances (1yr)", "qty": 1, "unit_price": 120000.00}],
        "total": 120000.00,
        "status": "Pending Approval",
        "submitted_date": "2026-03-01",
        "approved_date": None,
        "expected_delivery": None,
    },
    "PO-2026-004": {
        "vendor": "Pinnacle Catering Co.",
        "requester": "David Kim",
        "department": "HR",
        "items": [{"desc": "Q2 Team-building event catering", "qty": 1, "unit_price": 3200.00}],
        "total": 3200.00,
        "status": "Ordered",
        "submitted_date": "2026-02-28",
        "approved_date": "2026-03-02",
        "expected_delivery": "2026-04-10",
    },
    "PO-2026-005": {
        "vendor": "SecureNet Corp",
        "requester": "Ahmed Hassan",
        "department": "IT",
        "items": [
            {"desc": "CrowdStrike Falcon licenses (100 seats)", "qty": 100, "unit_price": 180.00},
        ],
        "total": 18000.00,
        "status": "Approved",
        "submitted_date": "2026-03-05",
        "approved_date": "2026-03-10",
        "expected_delivery": "2026-03-15",
    },
    "PO-2026-006": {
        "vendor": "Acme Office Supplies",
        "requester": "Maria Santos",
        "department": "Finance",
        "items": [{"desc": "Ergonomic office chairs (x20)", "qty": 20, "unit_price": 320.00}],
        "total": 6400.00,
        "status": "Received",
        "submitted_date": "2026-01-20",
        "approved_date": "2026-01-23",
        "expected_delivery": "2026-02-10",
    },
    "PO-2026-007": {
        "vendor": "GlobalPrint Services",
        "requester": "Sarah Chen",
        "department": "Marketing",
        "items": [
            {"desc": "Trade show banners and displays", "qty": 15, "unit_price": 280.00},
            {"desc": "Branded merchandise kits", "qty": 500, "unit_price": 12.50},
        ],
        "total": 10450.00,
        "status": "Pending Approval",
        "submitted_date": "2026-03-12",
        "approved_date": None,
        "expected_delivery": None,
    },
    "PO-2026-008": {
        "vendor": "TechParts International",
        "requester": "Ahmed Hassan",
        "department": "IT",
        "items": [{"desc": "Laptop refresh — ThinkPad X1 Carbon (x30)", "qty": 30, "unit_price": 1850.00}],
        "total": 55500.00,
        "status": "Approved",
        "submitted_date": "2026-02-20",
        "approved_date": "2026-03-01",
        "expected_delivery": "2026-04-01",
    },
    "PO-2026-009": {
        "vendor": "Pinnacle Catering Co.",
        "requester": "David Kim",
        "department": "HR",
        "items": [{"desc": "Monthly snack subscription (office)", "qty": 12, "unit_price": 650.00}],
        "total": 7800.00,
        "status": "Ordered",
        "submitted_date": "2026-01-10",
        "approved_date": "2026-01-12",
        "expected_delivery": "2026-12-31",
    },
    "PO-2026-010": {
        "vendor": "LegalEase Software",
        "requester": "Maria Santos",
        "department": "Legal",
        "items": [{"desc": "Contract management platform (annual)", "qty": 1, "unit_price": 24000.00}],
        "total": 24000.00,
        "status": "Draft",
        "submitted_date": None,
        "approved_date": None,
        "expected_delivery": None,
    },
}

VENDORS = {
    "V-001": {
        "name": "Acme Office Supplies",
        "category": "Office Equipment",
        "on_time_delivery": 92,
        "quality_rating": 88,
        "price_competitiveness": 75,
        "responsiveness": 90,
        "compliance": 95,
        "total_spend_ytd": 125000.00,
    },
    "V-002": {
        "name": "TechParts International",
        "category": "IT Hardware",
        "on_time_delivery": 85,
        "quality_rating": 94,
        "price_competitiveness": 70,
        "responsiveness": 82,
        "compliance": 98,
        "total_spend_ytd": 310000.00,
    },
    "V-003": {
        "name": "CloudScale Solutions",
        "category": "Cloud Services",
        "on_time_delivery": 99,
        "quality_rating": 96,
        "price_competitiveness": 60,
        "responsiveness": 95,
        "compliance": 100,
        "total_spend_ytd": 480000.00,
    },
    "V-004": {
        "name": "Pinnacle Catering Co.",
        "category": "Food & Beverage",
        "on_time_delivery": 78,
        "quality_rating": 82,
        "price_competitiveness": 85,
        "responsiveness": 70,
        "compliance": 90,
        "total_spend_ytd": 45000.00,
    },
    "V-005": {
        "name": "SecureNet Corp",
        "category": "Cybersecurity",
        "on_time_delivery": 95,
        "quality_rating": 97,
        "price_competitiveness": 55,
        "responsiveness": 88,
        "compliance": 100,
        "total_spend_ytd": 210000.00,
    },
    "V-006": {
        "name": "GlobalPrint Services",
        "category": "Marketing Materials",
        "on_time_delivery": 70,
        "quality_rating": 75,
        "price_competitiveness": 92,
        "responsiveness": 65,
        "compliance": 85,
        "total_spend_ytd": 38000.00,
    },
    "V-007": {
        "name": "LegalEase Software",
        "category": "Legal Tech",
        "on_time_delivery": 90,
        "quality_rating": 88,
        "price_competitiveness": 72,
        "responsiveness": 91,
        "compliance": 96,
        "total_spend_ytd": 24000.00,
    },
    "V-008": {
        "name": "GreenClean Facility Services",
        "category": "Facilities",
        "on_time_delivery": 88,
        "quality_rating": 80,
        "price_competitiveness": 90,
        "responsiveness": 75,
        "compliance": 82,
        "total_spend_ytd": 96000.00,
    },
}

CONTRACTS = {
    "CTR-2025-001": {
        "vendor": "Acme Office Supplies",
        "type": "Master Service Agreement",
        "start_date": "2025-06-01",
        "end_date": "2026-05-31",
        "auto_renew": True,
        "annual_value": 250000.00,
        "notice_period_days": 60,
    },
    "CTR-2025-002": {
        "vendor": "CloudScale Solutions",
        "type": "Enterprise License Agreement",
        "start_date": "2025-01-01",
        "end_date": "2026-12-31",
        "auto_renew": False,
        "annual_value": 480000.00,
        "notice_period_days": 90,
    },
    "CTR-2025-003": {
        "vendor": "SecureNet Corp",
        "type": "Subscription Agreement",
        "start_date": "2025-09-01",
        "end_date": "2026-08-31",
        "auto_renew": True,
        "annual_value": 210000.00,
        "notice_period_days": 30,
    },
    "CTR-2025-004": {
        "vendor": "GreenClean Facility Services",
        "type": "Service Level Agreement",
        "start_date": "2025-04-01",
        "end_date": "2026-03-31",
        "auto_renew": False,
        "annual_value": 96000.00,
        "notice_period_days": 60,
    },
    "CTR-2026-001": {
        "vendor": "TechParts International",
        "type": "Preferred Vendor Agreement",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "auto_renew": True,
        "annual_value": 500000.00,
        "notice_period_days": 90,
    },
    "CTR-2026-002": {
        "vendor": "Pinnacle Catering Co.",
        "type": "Service Agreement",
        "start_date": "2026-01-15",
        "end_date": "2026-07-15",
        "auto_renew": False,
        "annual_value": 52000.00,
        "notice_period_days": 30,
    },
    "CTR-2026-003": {
        "vendor": "LegalEase Software",
        "type": "SaaS Subscription",
        "start_date": "2026-04-01",
        "end_date": "2027-03-31",
        "auto_renew": True,
        "annual_value": 24000.00,
        "notice_period_days": 30,
    },
}

DEPARTMENT_BUDGETS = {
    "Marketing": {"annual_budget": 500000, "spent_ytd": 312000, "committed": 45000},
    "Engineering": {"annual_budget": 1200000, "spent_ytd": 780000, "committed": 120000},
    "IT": {"annual_budget": 800000, "spent_ytd": 520000, "committed": 73500},
    "HR": {"annual_budget": 300000, "spent_ytd": 185000, "committed": 11000},
    "Finance": {"annual_budget": 250000, "spent_ytd": 142000, "committed": 6400},
    "Legal": {"annual_budget": 350000, "spent_ytd": 198000, "committed": 24000},
    "Sales": {"annual_budget": 600000, "spent_ytd": 375000, "committed": 30000},
    "Operations": {"annual_budget": 450000, "spent_ytd": 290000, "committed": 15000},
}

# ──────────────────────────────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are the Procurement Agent for C-Agents, an enterprise AI assistant specializing \
in procurement, vendor management, and purchasing operations.

Your expertise includes:
- Purchase order tracking and status updates
- Vendor evaluation and scorecard analysis
- Budget verification and approval routing
- Contract management and expiration monitoring
- Spend analytics and category management

When answering, use the [DATA] section provided below for precise numbers. \
Always include specific amounts, dates, and percentages. \
Format responses with clear structure: use headings, bullet points, and bold for key metrics. \
Cite PO numbers, vendor names, or contract IDs where relevant.

If the data section says "No matching data found", say so clearly and suggest what information would help.\
"""

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
        APPROVAL_THRESHOLD_MANAGER: int = Field(default=5000)
        APPROVAL_THRESHOLD_DIRECTOR: int = Field(default=25000)
        APPROVAL_THRESHOLD_VP: int = Field(default=100000)
        CONTRACT_ALERT_DAYS: int = Field(
            default=90,
            description="Days before expiry to flag contracts",
        )
        PENDING_APPROVAL_WARNING_DAYS: int = Field(
            default=5,
            description="Days after which a pending PO is flagged",
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        return [{"id": "procurement-agent", "name": "Procurement Agent"}]

    # ── helpers ──────────────────────────────────────────────────────

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
            print(f"[procurement-agent] LLM error: {e!r}", flush=True)
            return self._empty_response(self.valves.MODEL)

    async def _stream_ollama(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        url = f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions"
        payload = {"model": self.valves.MODEL, "messages": messages, "stream": True}
        session = aiohttp.ClientSession()
        try:
            resp = await session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=300))
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

    # ── business logic ──────────────────────────────────────────────

    def _today(self) -> date:
        return date.today()

    def _days_between(self, date_str: str, ref: date | None = None) -> int:
        ref = ref or self._today()
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (ref - d).days

    def _lookup_po(self, query: str) -> str:
        """Search POs by number, vendor, requester, or department."""
        q = query.lower()
        matches = []
        for po_id, po in PURCHASE_ORDERS.items():
            if (
                po_id.lower() in q
                or po["vendor"].lower() in q
                or po["requester"].lower() in q
                or po["department"].lower() in q
            ):
                matches.append((po_id, po))
        if not matches:
            return "No matching purchase orders found."

        lines = []
        for po_id, po in matches:
            days_pending = ""
            if po["status"] == "Pending Approval" and po["submitted_date"]:
                dp = self._days_between(po["submitted_date"])
                warning = " ⚠ EXCEEDS THRESHOLD" if dp > self.valves.PENDING_APPROVAL_WARNING_DAYS else ""
                days_pending = f"  Days pending: {dp}{warning}"

            items_desc = "; ".join(f"{i['desc']} (qty {i['qty']} × ${i['unit_price']:,.2f})" for i in po["items"])
            lines.append(
                f"PO: {po_id}\n"
                f"  Vendor: {po['vendor']}\n"
                f"  Requester: {po['requester']} ({po['department']})\n"
                f"  Items: {items_desc}\n"
                f"  Total: ${po['total']:,.2f}\n"
                f"  Status: {po['status']}\n"
                f"  Submitted: {po['submitted_date'] or 'N/A'}\n"
                f"  Approved: {po['approved_date'] or 'N/A'}\n"
                f"  Expected delivery: {po['expected_delivery'] or 'N/A'}"
                + (f"\n{days_pending}" if days_pending else "")
            )
        return "\n\n".join(lines)

    def _vendor_scorecard(self, query: str) -> str:
        """Calculate weighted vendor score."""
        q = query.lower()
        match = None
        for vid, v in VENDORS.items():
            if v["name"].lower() in q:
                match = (vid, v)
                break
        if not match:
            return "No matching vendor found. Available vendors: " + ", ".join(
                v["name"] for v in VENDORS.values()
            )

        vid, v = match
        score = (
            v["on_time_delivery"] * 0.30
            + v["quality_rating"] * 0.25
            + v["price_competitiveness"] * 0.20
            + v["responsiveness"] * 0.15
            + v["compliance"] * 0.10
        )
        if score >= 90:
            tier = "Preferred"
        elif score >= 75:
            tier = "Approved"
        elif score >= 60:
            tier = "Probation"
        else:
            tier = "Blacklisted"

        return (
            f"Vendor Scorecard: {v['name']} ({vid})\n"
            f"  Category: {v['category']}\n"
            f"  On-time delivery (30%): {v['on_time_delivery']}/100\n"
            f"  Quality rating (25%): {v['quality_rating']}/100\n"
            f"  Price competitiveness (20%): {v['price_competitiveness']}/100\n"
            f"  Responsiveness (15%): {v['responsiveness']}/100\n"
            f"  Compliance (10%): {v['compliance']}/100\n"
            f"  ── Composite Score: {score:.1f}/100\n"
            f"  ── Tier: {tier}\n"
            f"  YTD Spend: ${v['total_spend_ytd']:,.2f}"
        )

    def _check_budget(self, query: str) -> str:
        """Check department budget and determine approval tier."""
        q = query.lower()

        # Find department
        dept = None
        for d in DEPARTMENT_BUDGETS:
            if d.lower() in q:
                dept = d
                break
        if not dept:
            return "No department specified. Available: " + ", ".join(DEPARTMENT_BUDGETS.keys())

        # Extract dollar amount
        amount_match = re.search(r"\$?([\d,]+(?:\.\d{2})?)\s*(?:k|K)?", q)
        amount = None
        if amount_match:
            raw = amount_match.group(1).replace(",", "")
            amount = float(raw)
            if "k" in q[amount_match.end() - 2 : amount_match.end() + 1].lower():
                amount *= 1000

        b = DEPARTMENT_BUDGETS[dept]
        remaining = b["annual_budget"] - b["spent_ytd"] - b["committed"]

        # Approval tier
        tier_info = ""
        if amount is not None:
            fits = "YES — within remaining budget" if amount <= remaining else "NO — exceeds remaining budget"
            if amount < self.valves.APPROVAL_THRESHOLD_MANAGER:
                tier = "Manager"
            elif amount < self.valves.APPROVAL_THRESHOLD_DIRECTOR:
                tier = "Director"
            elif amount < self.valves.APPROVAL_THRESHOLD_VP:
                tier = "VP"
            else:
                tier = "C-Suite"
            tier_info = (
                f"\n  Requested amount: ${amount:,.2f}\n"
                f"  Budget sufficient: {fits}\n"
                f"  Approval tier required: {tier} (threshold: "
                f"<${self.valves.APPROVAL_THRESHOLD_MANAGER:,} Manager, "
                f"<${self.valves.APPROVAL_THRESHOLD_DIRECTOR:,} Director, "
                f"<${self.valves.APPROVAL_THRESHOLD_VP:,} VP, "
                f"≥${self.valves.APPROVAL_THRESHOLD_VP:,} C-Suite)"
            )

        return (
            f"Budget Check: {dept}\n"
            f"  Annual budget: ${b['annual_budget']:,.2f}\n"
            f"  Spent YTD: ${b['spent_ytd']:,.2f}\n"
            f"  Committed (open POs): ${b['committed']:,.2f}\n"
            f"  Remaining: ${remaining:,.2f}\n"
            f"  Utilization: {((b['spent_ytd'] + b['committed']) / b['annual_budget'] * 100):.1f}%"
            + tier_info
        )

    def _expiring_contracts(self) -> str:
        """List contracts expiring within the alert window."""
        today = self._today()
        window = today + timedelta(days=self.valves.CONTRACT_ALERT_DAYS)
        expiring = []
        for cid, c in CONTRACTS.items():
            end = datetime.strptime(c["end_date"], "%Y-%m-%d").date()
            if today <= end <= window:
                days_left = (end - today).days
                notice_deadline = end - timedelta(days=c["notice_period_days"])
                notice_passed = today > notice_deadline
                expiring.append((days_left, cid, c, notice_passed, notice_deadline))

        if not expiring:
            return f"No contracts expiring within the next {self.valves.CONTRACT_ALERT_DAYS} days."

        expiring.sort(key=lambda x: x[0])
        lines = [f"Contracts expiring within {self.valves.CONTRACT_ALERT_DAYS} days:\n"]
        for days_left, cid, c, notice_passed, notice_deadline in expiring:
            notice_flag = " ⚠ NOTICE DEADLINE PASSED" if notice_passed else f" (notice by {notice_deadline})"
            lines.append(
                f"{cid}: {c['vendor']}\n"
                f"  Type: {c['type']}\n"
                f"  Ends: {c['end_date']} ({days_left} days left)\n"
                f"  Auto-renew: {'Yes' if c['auto_renew'] else 'No'}\n"
                f"  Annual value: ${c['annual_value']:,.2f}\n"
                f"  Notice period: {c['notice_period_days']} days{notice_flag}"
            )
        return "\n\n".join(lines)

    def _spend_summary(self, query: str) -> str:
        """Spend summary for a department or vendor."""
        q = query.lower()

        # Check department
        for dept, b in DEPARTMENT_BUDGETS.items():
            if dept.lower() in q:
                # Find all POs for this department
                dept_pos = [(pid, po) for pid, po in PURCHASE_ORDERS.items() if po["department"] == dept]
                po_lines = "\n".join(
                    f"  {pid}: {po['vendor']} — ${po['total']:,.2f} ({po['status']})"
                    for pid, po in dept_pos
                )
                return (
                    f"Spend Summary: {dept}\n"
                    f"  Annual budget: ${b['annual_budget']:,.2f}\n"
                    f"  Spent YTD: ${b['spent_ytd']:,.2f}\n"
                    f"  Committed: ${b['committed']:,.2f}\n"
                    f"  Remaining: ${(b['annual_budget'] - b['spent_ytd'] - b['committed']):,.2f}\n"
                    f"  Purchase orders:\n{po_lines}"
                )

        # Check vendor
        for vid, v in VENDORS.items():
            if v["name"].lower() in q:
                vendor_pos = [
                    (pid, po) for pid, po in PURCHASE_ORDERS.items() if po["vendor"] == v["name"]
                ]
                po_lines = "\n".join(
                    f"  {pid}: {po['department']} — ${po['total']:,.2f} ({po['status']})"
                    for pid, po in vendor_pos
                )
                return (
                    f"Spend Summary: {v['name']}\n"
                    f"  Category: {v['category']}\n"
                    f"  YTD Spend: ${v['total_spend_ytd']:,.2f}\n"
                    f"  Purchase orders:\n{po_lines}"
                )

        return "No matching department or vendor for spend summary."

    def _analyze_and_gather(self, user_message: str) -> str:
        """Determine intent and gather relevant data context."""
        msg = user_message.lower()

        # PO lookup — look for PO number pattern or status-related keywords
        po_match = re.search(r"po[-\s]?\d{4}[-\s]?\d{3}", msg)
        if po_match:
            return self._lookup_po(user_message)

        # Vendor scorecard
        if any(w in msg for w in ["scorecard", "vendor score", "vendor rating", "evaluate vendor", "vendor evaluation"]):
            return self._vendor_scorecard(user_message)

        # Budget check
        if any(w in msg for w in ["budget", "purchase", "buy", "afford", "approval", "spend limit"]):
            # If it has a dollar amount, it's a budget check
            if re.search(r"\$[\d,]+|[\d,]+\s*(?:dollars|usd|k\b)", msg):
                return self._check_budget(user_message)
            if "budget" in msg:
                return self._check_budget(user_message)

        # Contract alerts
        if any(w in msg for w in ["contract", "expir", "renew", "agreement"]):
            return self._expiring_contracts()

        # Spend summary
        if any(w in msg for w in ["spend", "spending", "analytics", "summary", "breakdown"]):
            return self._spend_summary(user_message)

        # PO status by requester/vendor/department
        if any(w in msg for w in ["status", "order", "purchase order", "po "]):
            return self._lookup_po(user_message)

        # Generic — provide an overview
        return self._spend_summary(user_message) or "No matching data found."

    # ── main entry point ────────────────────────────────────────────

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

        # Gather business data context
        context = self._analyze_and_gather(user_message)

        # Build augmented messages
        augmented = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n[DATA]\n{context}"},
        ] + messages

        if not streaming:
            result = await self._call_ollama(augmented)
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        return self._stream_ollama(augmented)
