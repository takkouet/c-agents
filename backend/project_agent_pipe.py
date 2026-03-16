"""
title: Project Manager Agent
description: Handles project status tracking, resource allocation, milestone risk assessment, sprint management, and cross-project dependencies
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

PROJECTS = {
    "PRJ-001": {
        "name": "Cloud Migration Phase 2",
        "owner": "James Rivera",
        "department": "Engineering",
        "status": "In Progress",
        "start_date": "2026-01-15",
        "target_end": "2026-06-30",
        "budget": 450000,
        "actual_spend": 198000,
        "planned_value": 225000,
        "earned_value": 210000,
        "completion_pct": 46,
        "team": ["James Rivera", "Lisa Park", "Ahmed Hassan", "Maria Santos"],
        "milestones": [
            {"name": "Database Migration", "due": "2026-03-28", "status": "at_risk", "pct": 75, "deps": ["PRJ-003"]},
            {"name": "API Gateway Setup", "due": "2026-04-15", "status": "on_track", "pct": 30, "deps": []},
            {"name": "Load Testing", "due": "2026-05-20", "status": "on_track", "pct": 0, "deps": []},
            {"name": "Production Cutover", "due": "2026-06-25", "status": "on_track", "pct": 0, "deps": []},
        ],
        "dependencies": ["PRJ-003"],
        "slipped_milestones_count": 1,
    },
    "PRJ-002": {
        "name": "Mobile App Redesign",
        "owner": "Sarah Chen",
        "department": "Product",
        "status": "In Progress",
        "start_date": "2026-02-01",
        "target_end": "2026-05-15",
        "budget": 280000,
        "actual_spend": 145000,
        "planned_value": 168000,
        "earned_value": 140000,
        "completion_pct": 50,
        "team": ["Sarah Chen", "David Kim", "Priya Patel", "Tom Zhang"],
        "milestones": [
            {"name": "UX Research & Wireframes", "due": "2026-02-28", "status": "completed", "pct": 100, "deps": []},
            {"name": "Design System Update", "due": "2026-03-20", "status": "at_risk", "pct": 60, "deps": []},
            {"name": "Frontend Implementation", "due": "2026-04-20", "status": "on_track", "pct": 20, "deps": []},
            {"name": "Beta Launch", "due": "2026-05-10", "status": "on_track", "pct": 0, "deps": ["PRJ-002-M3"]},
        ],
        "dependencies": [],
        "slipped_milestones_count": 0,
    },
    "PRJ-003": {
        "name": "Data Platform Upgrade",
        "owner": "Lisa Park",
        "department": "Engineering",
        "status": "In Progress",
        "start_date": "2025-11-01",
        "target_end": "2026-04-30",
        "budget": 380000,
        "actual_spend": 310000,
        "planned_value": 342000,
        "earned_value": 295000,
        "completion_pct": 78,
        "team": ["Lisa Park", "Ahmed Hassan", "Wei Chen", "Raj Patel"],
        "milestones": [
            {"name": "Schema Redesign", "due": "2026-01-15", "status": "completed", "pct": 100, "deps": []},
            {"name": "ETL Pipeline Rewrite", "due": "2026-03-01", "status": "completed", "pct": 100, "deps": []},
            {"name": "Data Validation & QA", "due": "2026-03-25", "status": "at_risk", "pct": 65, "deps": []},
            {"name": "Production Deployment", "due": "2026-04-25", "status": "on_track", "pct": 10, "deps": []},
        ],
        "dependencies": [],
        "slipped_milestones_count": 2,
    },
    "PRJ-004": {
        "name": "Security Compliance Audit",
        "owner": "Ahmed Hassan",
        "department": "IT",
        "status": "In Progress",
        "start_date": "2026-01-01",
        "target_end": "2026-03-31",
        "budget": 150000,
        "actual_spend": 128000,
        "planned_value": 142500,
        "earned_value": 120000,
        "completion_pct": 80,
        "team": ["Ahmed Hassan", "Maria Santos"],
        "milestones": [
            {"name": "Vulnerability Assessment", "due": "2026-02-15", "status": "completed", "pct": 100, "deps": []},
            {"name": "Remediation Plan", "due": "2026-03-01", "status": "completed", "pct": 100, "deps": []},
            {"name": "Compliance Report", "due": "2026-03-25", "status": "at_risk", "pct": 70, "deps": []},
        ],
        "dependencies": [],
        "slipped_milestones_count": 1,
    },
    "PRJ-005": {
        "name": "CRM Integration",
        "owner": "David Kim",
        "department": "Sales",
        "status": "Planning",
        "start_date": "2026-04-01",
        "target_end": "2026-08-31",
        "budget": 200000,
        "actual_spend": 0,
        "planned_value": 0,
        "earned_value": 0,
        "completion_pct": 0,
        "team": ["David Kim", "Priya Patel"],
        "milestones": [
            {"name": "Requirements Gathering", "due": "2026-04-15", "status": "on_track", "pct": 0, "deps": []},
            {"name": "API Design", "due": "2026-05-15", "status": "on_track", "pct": 0, "deps": []},
            {"name": "Implementation", "due": "2026-07-31", "status": "on_track", "pct": 0, "deps": []},
            {"name": "Go-Live", "due": "2026-08-25", "status": "on_track", "pct": 0, "deps": []},
        ],
        "dependencies": ["PRJ-002"],
        "slipped_milestones_count": 0,
    },
    "PRJ-006": {
        "name": "Office Relocation",
        "owner": "Maria Santos",
        "department": "Operations",
        "status": "In Progress",
        "start_date": "2026-02-15",
        "target_end": "2026-05-30",
        "budget": 320000,
        "actual_spend": 85000,
        "planned_value": 112000,
        "earned_value": 96000,
        "completion_pct": 30,
        "team": ["Maria Santos", "Tom Zhang"],
        "milestones": [
            {"name": "Space Planning", "due": "2026-03-10", "status": "completed", "pct": 100, "deps": []},
            {"name": "Vendor Selection", "due": "2026-03-25", "status": "on_track", "pct": 50, "deps": []},
            {"name": "Physical Move", "due": "2026-05-15", "status": "on_track", "pct": 0, "deps": []},
        ],
        "dependencies": [],
        "slipped_milestones_count": 0,
    },
}

TEAM_MEMBERS = {
    "James Rivera": {
        "role": "Senior Engineer",
        "department": "Engineering",
        "allocations": [
            {"project": "PRJ-001", "hours_per_week": 30},
            {"project": "PRJ-003", "hours_per_week": 15},
        ],
        "capacity_hours": 40,
    },
    "Lisa Park": {
        "role": "Data Architect",
        "department": "Engineering",
        "allocations": [
            {"project": "PRJ-003", "hours_per_week": 35},
            {"project": "PRJ-001", "hours_per_week": 10},
        ],
        "capacity_hours": 40,
    },
    "Ahmed Hassan": {
        "role": "Security Lead",
        "department": "IT",
        "allocations": [
            {"project": "PRJ-004", "hours_per_week": 25},
            {"project": "PRJ-001", "hours_per_week": 10},
            {"project": "PRJ-003", "hours_per_week": 10},
        ],
        "capacity_hours": 40,
    },
    "Sarah Chen": {
        "role": "Product Manager",
        "department": "Product",
        "allocations": [
            {"project": "PRJ-002", "hours_per_week": 35},
        ],
        "capacity_hours": 40,
    },
    "David Kim": {
        "role": "Business Analyst",
        "department": "Sales",
        "allocations": [
            {"project": "PRJ-002", "hours_per_week": 20},
            {"project": "PRJ-005", "hours_per_week": 15},
        ],
        "capacity_hours": 40,
    },
    "Maria Santos": {
        "role": "Operations Manager",
        "department": "Operations",
        "allocations": [
            {"project": "PRJ-006", "hours_per_week": 25},
            {"project": "PRJ-004", "hours_per_week": 10},
        ],
        "capacity_hours": 40,
    },
    "Priya Patel": {
        "role": "UX Designer",
        "department": "Product",
        "allocations": [
            {"project": "PRJ-002", "hours_per_week": 30},
            {"project": "PRJ-005", "hours_per_week": 10},
        ],
        "capacity_hours": 40,
    },
    "Tom Zhang": {
        "role": "Frontend Engineer",
        "department": "Engineering",
        "allocations": [
            {"project": "PRJ-002", "hours_per_week": 25},
            {"project": "PRJ-006", "hours_per_week": 15},
        ],
        "capacity_hours": 40,
    },
    "Wei Chen": {
        "role": "Data Engineer",
        "department": "Engineering",
        "allocations": [
            {"project": "PRJ-003", "hours_per_week": 40},
        ],
        "capacity_hours": 40,
    },
    "Raj Patel": {
        "role": "Backend Engineer",
        "department": "Engineering",
        "allocations": [
            {"project": "PRJ-003", "hours_per_week": 30},
        ],
        "capacity_hours": 40,
    },
}

SPRINTS = {
    "PRJ-001-S5": {
        "project": "PRJ-001",
        "name": "Sprint 5",
        "start": "2026-03-11",
        "end": "2026-03-25",
        "planned_points": 34,
        "completed_points": 18,
        "avg_velocity": 30,
        "stories": [
            {"id": "US-142", "title": "Migrate user auth DB", "points": 8, "status": "Done"},
            {"id": "US-143", "title": "Setup read replicas", "points": 5, "status": "In Progress"},
            {"id": "US-144", "title": "DB connection pooling", "points": 5, "status": "Done"},
            {"id": "US-145", "title": "Schema validation scripts", "points": 3, "status": "In Progress"},
            {"id": "US-146", "title": "Data migration dry-run", "points": 8, "status": "To Do"},
            {"id": "US-147", "title": "Rollback procedure docs", "points": 5, "status": "Done"},
        ],
    },
    "PRJ-002-S3": {
        "project": "PRJ-002",
        "name": "Sprint 3",
        "start": "2026-03-04",
        "end": "2026-03-18",
        "planned_points": 26,
        "completed_points": 20,
        "avg_velocity": 24,
        "stories": [
            {"id": "US-201", "title": "Design token system", "points": 5, "status": "Done"},
            {"id": "US-202", "title": "Color palette update", "points": 3, "status": "Done"},
            {"id": "US-203", "title": "Typography scale", "points": 5, "status": "Done"},
            {"id": "US-204", "title": "Component library - buttons", "points": 5, "status": "Done"},
            {"id": "US-205", "title": "Component library - forms", "points": 5, "status": "In Progress"},
            {"id": "US-206", "title": "Component library - cards", "points": 3, "status": "Done"},
        ],
    },
    "PRJ-003-S8": {
        "project": "PRJ-003",
        "name": "Sprint 8",
        "start": "2026-03-11",
        "end": "2026-03-25",
        "planned_points": 30,
        "completed_points": 12,
        "avg_velocity": 28,
        "stories": [
            {"id": "US-301", "title": "Data quality rules engine", "points": 8, "status": "In Progress"},
            {"id": "US-302", "title": "Anomaly detection pipeline", "points": 8, "status": "To Do"},
            {"id": "US-303", "title": "Validation dashboard", "points": 5, "status": "Done"},
            {"id": "US-304", "title": "Fix ETL null handling", "points": 4, "status": "Done"},
            {"id": "US-305", "title": "Performance benchmarks", "points": 5, "status": "To Do"},
        ],
    },
}

# ──────────────────────────────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are the Project Manager Agent for C-Agents, an enterprise AI assistant specializing \
in project tracking, resource management, and delivery planning.

Your expertise includes:
- Project status reporting with Earned Value metrics (SPI, CPI)
- Resource allocation and utilization analysis
- Milestone tracking and risk assessment
- Sprint/iteration management and velocity analysis
- Cross-project dependency identification

When reporting project health, use these metrics:
- SPI (Schedule Performance Index) = Earned Value / Planned Value
  - SPI > 1.0 = ahead of schedule, SPI < 1.0 = behind schedule
- CPI (Cost Performance Index) = Earned Value / Actual Cost
  - CPI > 1.0 = under budget, CPI < 1.0 = over budget
- RAG status: Green (both > 0.95), Amber (either 0.85–0.95), Red (either < 0.85)

For resource utilization, flag any team member over 100% allocation.
For milestone risk, provide specific action recommendations.

Use the [DATA] section for precise numbers. Format with headings, bullet points, and bold metrics. \
Lead with the headline status before diving into details.\
"""


# ──────────────────────────────────────────────────────────────────────
# Pipe
# ──────────────────────────────────────────────────────────────────────


class Pipe:
    class Valves(BaseModel):
        OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", description="Ollama base URL")
        MODEL: str = Field(default="phi4-mini", description="Ollama model")
        RISK_THRESHOLD_HIGH: int = Field(default=60)
        RISK_THRESHOLD_MEDIUM: int = Field(default=30)
        OVERALLOCATION_HOURS: int = Field(default=40, description="Weekly capacity threshold")

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        return [{"id": "project-agent", "name": "Project Manager Agent"}]

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
            "choices": [{"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    async def _call_ollama(self, messages: list[dict]) -> dict:
        url = f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions"
        payload = {"model": self.valves.MODEL, "messages": messages, "stream": False}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status != 200:
                        return self._empty_response(self.valves.MODEL)
                    return await resp.json()
        except Exception as e:
            print(f"[project-agent] LLM error: {e!r}", flush=True)
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

    def _project_health(self, project_id: str) -> str:
        """Calculate project health with Earned Value metrics."""
        p = PROJECTS.get(project_id)
        if not p:
            return f"Project {project_id} not found."

        # EV metrics
        spi = p["earned_value"] / p["planned_value"] if p["planned_value"] else 0
        cpi = p["earned_value"] / p["actual_spend"] if p["actual_spend"] else 0

        if spi >= 0.95 and cpi >= 0.95:
            rag = "GREEN"
        elif spi < 0.85 or cpi < 0.85:
            rag = "RED"
        else:
            rag = "AMBER"

        # Days remaining
        today = self._today()
        target = datetime.strptime(p["target_end"], "%Y-%m-%d").date()
        days_left = (target - today).days

        # Budget
        budget_remaining = p["budget"] - p["actual_spend"]
        burn_rate = p["actual_spend"] / max((today - datetime.strptime(p["start_date"], "%Y-%m-%d").date()).days, 1)
        projected_spend = p["actual_spend"] + (burn_rate * max(days_left, 0))

        # Milestones
        ms_lines = []
        for ms in p["milestones"]:
            due = datetime.strptime(ms["due"], "%Y-%m-%d").date()
            ms_days = (due - today).days
            ms_lines.append(
                f"  - {ms['name']}: {ms['pct']}% done, due {ms['due']} "
                f"({ms_days} days), status: {ms['status'].upper()}"
            )

        return (
            f"Project: {p['name']} ({project_id})\n"
            f"  Owner: {p['owner']} | Dept: {p['department']}\n"
            f"  Status: {p['status']} | Completion: {p['completion_pct']}%\n"
            f"  RAG Status: {rag}\n"
            f"  Schedule Performance (SPI): {spi:.2f} {'(ahead)' if spi > 1 else '(behind)' if spi < 1 else '(on track)'}\n"
            f"  Cost Performance (CPI): {cpi:.2f} {'(under budget)' if cpi > 1 else '(over budget)' if cpi < 1 else '(on budget)'}\n"
            f"  Budget: ${p['budget']:,.0f} | Spent: ${p['actual_spend']:,.0f} | Remaining: ${budget_remaining:,.0f}\n"
            f"  Projected total spend: ${projected_spend:,.0f}\n"
            f"  Target end: {p['target_end']} ({days_left} days left)\n"
            f"  Team: {', '.join(p['team'])}\n"
            f"  Dependencies: {', '.join(p['dependencies']) or 'None'}\n"
            f"  Milestones:\n" + "\n".join(ms_lines)
        )

    def _resource_utilization(self, query: str) -> str:
        """Check resource utilization for a person or department."""
        q = query.lower()
        results = []

        for name, member in TEAM_MEMBERS.items():
            if name.lower() in q or member["department"].lower() in q:
                total_hours = sum(a["hours_per_week"] for a in member["allocations"])
                util_pct = (total_hours / member["capacity_hours"]) * 100
                over = total_hours > self.valves.OVERALLOCATION_HOURS
                alloc_lines = "\n".join(
                    f"    {a['project']} ({PROJECTS.get(a['project'], {}).get('name', '?')}): {a['hours_per_week']}h/wk"
                    for a in member["allocations"]
                )
                results.append(
                    f"{name} ({member['role']}, {member['department']})\n"
                    f"  Capacity: {member['capacity_hours']}h/wk\n"
                    f"  Allocated: {total_hours}h/wk ({util_pct:.0f}%)"
                    + (f" ⚠ OVER-ALLOCATED" if over else "")
                    + f"\n  Breakdown:\n{alloc_lines}"
                )

        if not results:
            return "No matching team member or department. Available: " + ", ".join(TEAM_MEMBERS.keys())
        return "\n\n".join(results)

    def _milestone_risk(self, query: str) -> str:
        """Assess milestone risk across projects."""
        today = self._today()
        at_risk = []

        for pid, p in PROJECTS.items():
            for ms in p["milestones"]:
                due = datetime.strptime(ms["due"], "%Y-%m-%d").date()
                days_left = (due - today).days
                if days_left < 0 or ms["status"] == "completed" or ms["pct"] == 100:
                    continue
                if days_left > 45:
                    continue  # Only near-term milestones

                # Dependency factor (0-100): how complete are dependencies?
                dep_score = 100
                for dep_ref in ms.get("deps", []):
                    dep_proj = PROJECTS.get(dep_ref)
                    if dep_proj:
                        dep_score = min(dep_score, dep_proj["completion_pct"])

                dep_factor = 100 - dep_score  # Higher = more risk

                # Resource factor: are team members over-allocated?
                team_over = 0
                for member_name in p["team"]:
                    member = TEAM_MEMBERS.get(member_name, {})
                    total = sum(a["hours_per_week"] for a in member.get("allocations", []))
                    if total > self.valves.OVERALLOCATION_HOURS:
                        team_over += 1
                resource_factor = min(100, (team_over / max(len(p["team"]), 1)) * 100)

                # Historical slip factor
                slip_factor = min(100, p["slipped_milestones_count"] * 35)

                risk_score = dep_factor * 0.4 + resource_factor * 0.3 + slip_factor * 0.3

                if risk_score >= self.valves.RISK_THRESHOLD_MEDIUM:
                    if risk_score >= self.valves.RISK_THRESHOLD_HIGH:
                        level = "HIGH"
                    else:
                        level = "MEDIUM"
                    at_risk.append((risk_score, level, pid, p["name"], ms, days_left, dep_factor, resource_factor, slip_factor))

        if not at_risk:
            return "No milestones currently at medium or high risk."

        at_risk.sort(key=lambda x: -x[0])
        lines = []
        for score, level, pid, pname, ms, days_left, dep_f, res_f, slip_f in at_risk:
            lines.append(
                f"[{level}] {pname} ({pid}) — {ms['name']}\n"
                f"  Risk score: {score:.0f}/100\n"
                f"  Due: {ms['due']} ({days_left} days left) | {ms['pct']}% complete\n"
                f"  Breakdown: dependency risk {dep_f:.0f}, resource risk {res_f:.0f}, slip history {slip_f:.0f}"
            )
        return "At-risk milestones:\n\n" + "\n\n".join(lines)

    def _sprint_summary(self, query: str) -> str:
        """Sprint/iteration summary."""
        q = query.lower()
        matches = []
        for sid, sp in SPRINTS.items():
            proj = PROJECTS.get(sp["project"], {})
            if sid.lower() in q or proj.get("name", "").lower() in q or sp["project"].lower() in q:
                matches.append((sid, sp))

        if not matches:
            return "No matching sprint found. Available: " + ", ".join(SPRINTS.keys())

        lines = []
        for sid, sp in matches:
            today = self._today()
            start = datetime.strptime(sp["start"], "%Y-%m-%d").date()
            end = datetime.strptime(sp["end"], "%Y-%m-%d").date()
            total_days = max((end - start).days, 1)
            elapsed_days = max((today - start).days, 0)
            remaining_days = max((end - today).days, 0)
            pct_time = min(100, (elapsed_days / total_days) * 100)

            remaining_points = sp["planned_points"] - sp["completed_points"]
            on_track = remaining_points <= (sp["avg_velocity"] * remaining_days / total_days) if remaining_days > 0 else remaining_points == 0

            stories_done = [s for s in sp["stories"] if s["status"] == "Done"]
            stories_ip = [s for s in sp["stories"] if s["status"] == "In Progress"]
            stories_todo = [s for s in sp["stories"] if s["status"] == "To Do"]

            story_lines = "\n".join(
                f"    [{s['status']}] {s['id']}: {s['title']} ({s['points']} pts)"
                for s in sp["stories"]
            )

            lines.append(
                f"Sprint: {sp['name']} ({sid})\n"
                f"  Project: {PROJECTS.get(sp['project'], {}).get('name', sp['project'])}\n"
                f"  Period: {sp['start']} → {sp['end']} ({remaining_days} days remaining, {pct_time:.0f}% elapsed)\n"
                f"  Points: {sp['completed_points']}/{sp['planned_points']} ({remaining_points} remaining)\n"
                f"  Avg velocity: {sp['avg_velocity']} pts/sprint\n"
                f"  Projection: {'ON TRACK' if on_track else '⚠ AT RISK — may not complete all planned work'}\n"
                f"  Stories: {len(stories_done)} done, {len(stories_ip)} in progress, {len(stories_todo)} to do\n"
                f"  Details:\n{story_lines}"
            )
        return "\n\n".join(lines)

    def _all_projects_overview(self) -> str:
        """Quick overview of all projects."""
        lines = []
        for pid, p in PROJECTS.items():
            spi = p["earned_value"] / p["planned_value"] if p["planned_value"] else 0
            cpi = p["earned_value"] / p["actual_spend"] if p["actual_spend"] else 0
            if spi >= 0.95 and cpi >= 0.95:
                rag = "GREEN"
            elif spi < 0.85 or cpi < 0.85:
                rag = "RED"
            else:
                rag = "AMBER"
            lines.append(
                f"{pid}: {p['name']} [{rag}] — {p['completion_pct']}% complete, "
                f"SPI={spi:.2f}, CPI={cpi:.2f}, owner: {p['owner']}"
            )
        return "All Projects Overview:\n" + "\n".join(lines)

    def _dependency_info(self, query: str) -> str:
        """Cross-project dependency analysis."""
        lines = []
        for pid, p in PROJECTS.items():
            if p["dependencies"]:
                for dep in p["dependencies"]:
                    dep_proj = PROJECTS.get(dep)
                    dep_name = dep_proj["name"] if dep_proj else dep
                    dep_pct = dep_proj["completion_pct"] if dep_proj else "?"
                    lines.append(f"{pid} ({p['name']}) depends on {dep} ({dep_name}) — {dep_pct}% complete")
        if not lines:
            return "No cross-project dependencies found."
        return "Cross-Project Dependencies:\n" + "\n".join(lines)

    def _analyze_and_gather(self, user_message: str) -> str:
        """Determine intent and gather data."""
        msg = user_message.lower()

        # Specific project lookup
        prj_match = re.search(r"prj[-\s]?\d{3}", msg)
        if prj_match:
            pid = prj_match.group().upper().replace(" ", "-")
            return self._project_health(pid)

        # Project name search
        for pid, p in PROJECTS.items():
            if p["name"].lower() in msg:
                return self._project_health(pid)

        # Resource / utilization
        if any(w in msg for w in ["resource", "utilization", "allocated", "workload", "over-allocated", "overallocated", "capacity"]):
            return self._resource_utilization(user_message)

        # Person lookup
        for name in TEAM_MEMBERS:
            if name.lower() in msg:
                return self._resource_utilization(user_message) + "\n\n" + self._project_health_for_person(name)

        # Milestone risk
        if any(w in msg for w in ["milestone", "risk", "at risk", "at_risk", "deadline"]):
            return self._milestone_risk(user_message)

        # Sprint
        if any(w in msg for w in ["sprint", "iteration", "velocity", "burn"]):
            return self._sprint_summary(user_message)

        # Dependencies
        if any(w in msg for w in ["dependenc", "blocking", "blocked"]):
            return self._dependency_info(user_message)

        # All projects overview
        if any(w in msg for w in ["all project", "overview", "portfolio", "dashboard", "status"]):
            return self._all_projects_overview()

        return self._all_projects_overview()

    def _project_health_for_person(self, name: str) -> str:
        """Get project health for all projects a person is on."""
        member = TEAM_MEMBERS.get(name)
        if not member:
            return ""
        pids = [a["project"] for a in member["allocations"]]
        return "\n\n".join(self._project_health(pid) for pid in pids)

    # ── main entry point ────────────────────────────────────────────

    async def pipe(
        self,
        body: dict,
        __user__: dict,
        __event_emitter__: Callable = None,
        __task__: str = None,
        __metadata__: dict = None,
    ) -> AsyncGenerator[str, None] | str:
        if __task__:
            result = await self._call_ollama(body.get("messages", []))
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        messages = body.get("messages", [])
        user_message = self._extract_last_user_message(messages)
        streaming = body.get("stream", False)

        context = self._analyze_and_gather(user_message)
        augmented = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n[DATA]\n{context}"},
        ] + messages

        if not streaming:
            result = await self._call_ollama(augmented)
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        return self._stream_ollama(augmented)
