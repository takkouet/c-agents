"""
OrchestratorAgent — plans which worker agents to consult, executes each step,
then synthesises a final answer.

Workers can be either DynamicAgent (built-in) or ExternalAgentProxy (external).
Both implement _get_completion(messages) so the orchestrator can call them uniformly.

WebSocket events broadcast to the sidebar (via broadcast.publish):
  {"step":"session_start", "session_id":"<uuid>", "message":"..."}
  {"step":"agent_active",  "session_id":"<uuid>", "agent_id":"hr",
   "agent_label":"HR Agent", "agent_icon":"👥", "agent_dept":"Human Resources",
   "action":"Verify employee identity"}
  {"step":"agent_done",    "session_id":"<uuid>", "agent_id":"hr", "agent_label":"HR Agent"}
  {"step":"session_done",  "session_id":"<uuid>", "message":"Completed"}
"""

import json
import re
import time
import uuid

import aiohttp
from aiohttp import web

from agents import broadcast
from agents.config import CORS_HEADERS, ssl_ctx
from agents.dynamic_agent import DynamicAgent, _is_gemini
from agents.gemini_utils import openai_messages_to_gemini

# ------------------------------------------------------------------ #
# Prompts
# ------------------------------------------------------------------ #

ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator for C-Agents, a multi-agent enterprise \
AI platform. You coordinate specialist agents to answer employee queries.

When synthesising specialist responses, produce a clear, structured answer. \
Reference the information from each agent where relevant."""


def build_planner_prompt(workers: dict) -> str:
    """Build the planner system prompt dynamically from the current worker registry."""
    if not workers:
        agent_lines = "  (no specialist agents registered)"
    else:
        agent_lines = "\n".join(
            f"- {agent_id}: {getattr(worker, 'name', agent_id)} — {worker.system_prompt.splitlines()[0]}"
            for agent_id, worker in workers.items()
        )

    return f"""You are a query planner for a multi-agent AI system.
Given the user's message, determine which specialist agents to consult and what specific task to assign each.

Available agents:
{agent_lines}

Return a JSON array. Each item must have:
- "agent": one of {list(workers.keys()) if workers else []}
- "action": specific task description (10-20 words, e.g. "Verify employee identity and check current password status")

Rules:
- If the request is irrelevant to all worker agents, do not route to any
- Use ONLY the agents that are genuinely needed (1 to 3 agents max)
- If the query clearly belongs to one domain, return a single-item array
- Return ONLY valid JSON — no explanation, no markdown fences

Example for a password-change request:
[{{"agent": "hr", "action": "Verify employee identity and confirm account details"}},
 {{"agent": "it", "action": "Check if password reset is permitted and initiate the process"}}]"""


class OrchestratorAgent(DynamicAgent):
    agent_id = "orchestrator"

    def __init__(self, workers: dict, system_prompt: str = ORCHESTRATOR_SYSTEM_PROMPT):
        super().__init__(
            agent_id="orchestrator",
            name="Orchestrator",
            system_prompt=system_prompt,
            llm_base_url="",   # set dynamically from DB via update_config()
            llm_api_key="",
            model="",
        )
        self.workers = workers

    def update_workers(self, new_workers: dict) -> None:
        """Hot-reload the worker registry (called after DB changes)."""
        self.workers = new_workers

    def update_config(self, *, system_prompt: str, llm_base_url: str, llm_api_key: str, model: str) -> None:
        """Update orchestrator's own LLM config (loaded from DB at startup and on edit)."""
        self.system_prompt = system_prompt
        self.llm_base_url = llm_base_url.rstrip("/")
        self.llm_api_key = llm_api_key
        self.model = model

    # ------------------------------------------------------------------ #
    # Main handler: Plan → Execute → Synthesise
    # ------------------------------------------------------------------ #

    async def handle_chat_completions(self, request: web.Request) -> web.Response:
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

        raw_messages = body.get("messages", [])

        # ── Phase 1: Broadcast session_start then plan ─────────────────
        session_id = str(uuid.uuid4())

        await broadcast.publish({
            "step": "session_start",
            "session_id": session_id,
            "message": "Request received by orchestrator",
        })

        plan = await self._plan(raw_messages)

        # ── Phase 2: Execute each planned step (non-streaming) ─────────
        collected: list[dict] = []

        for step in plan:
            worker_key = step["agent"]
            action = step.get("action", "Handle request")
            worker = self.workers.get(worker_key)
            if worker is None:
                continue

            agent_label = worker.name
            agent_icon = getattr(worker, "icon", "🤖")
            agent_dept = getattr(worker, "department", "")

            await broadcast.publish({
                "step": "agent_active",
                "session_id": session_id,
                "agent_id": worker_key,
                "agent_label": agent_label,
                "agent_icon": agent_icon,
                "agent_dept": agent_dept,
                "action": action,
            })

            # Both DynamicAgent and ExternalAgentProxy implement _get_completion()
            worker_messages = [
                {"role": "system", "content": f"{worker.system_prompt}\n\nFocused task: {action}"}
            ] + raw_messages

            response_text = await worker._get_completion(worker_messages)
            collected.append({
                "agent_name": agent_label,
                "action": action,
                "response": response_text,
            })

            await broadcast.publish({
                "step": "agent_done",
                "session_id": session_id,
                "agent_id": worker_key,
                "agent_label": agent_label,
            })

        await broadcast.publish({
            "step": "session_done",
            "session_id": session_id,
            "message": "Completed",
        })

        # ── Phase 3: Synthesise and stream back to Open WebUI ──────────
        chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
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

        if not collected:
            messages = [{"role": "system", "content": self.system_prompt}] + raw_messages
        else:
            agent_summaries = "\n\n".join(
                f"[{r['agent_name']} — {r['action']}]:\n{r['response']}"
                for r in collected
            )
            synthesis_system = (
                f"{self.system_prompt}\n\n"
                f"The following specialist agents have provided their input:\n\n"
                f"{agent_summaries}\n\n"
                f"Using this information, provide a clear, comprehensive answer to the user's request."
            )
            messages = [{"role": "system", "content": synthesis_system}] + raw_messages

        await self._stream_to_response(messages, {}, stream_response, chunk_id)

        try:
            await stream_response.write(b"data: [DONE]\n\n")
            await stream_response.write_eof()
        except Exception:
            pass
        return stream_response

    # ------------------------------------------------------------------ #
    # Planner helper
    # ------------------------------------------------------------------ #

    async def _plan(self, messages: list) -> list[dict]:
        """Ask the LLM to return a JSON plan of which agents to call."""
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        if isinstance(last_user, list):
            last_user = " ".join(
                p.get("text", "") for p in last_user if isinstance(p, dict)
            )

        planner_prompt = build_planner_prompt(self.workers)
        plan_messages = [
            {"role": "system", "content": planner_prompt},
            {"role": "user", "content": last_user},
        ]

        _fallback: list[dict] = []
        if self.workers:
            first_key = next(iter(self.workers))
            _fallback = [{"agent": first_key, "action": "Handle the user's request"}]

        if _is_gemini(self.llm_base_url):
            raw = await self._gemini_plan(plan_messages)
        else:
            raw = await self._openai_plan(plan_messages)

        if not raw:
            return _fallback

        # Extract JSON array (LLM may wrap it in markdown fences)
        json_match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)

        try:
            plan = json.loads(raw)
            valid = [
                step for step in plan
                if isinstance(step, dict)
                and "agent" in step
                and step["agent"] in self.workers
            ]
            return valid if valid else _fallback
        except Exception:
            return _fallback

    async def _gemini_plan(self, plan_messages: list) -> str:
        """Call Gemini for planning."""
        contents, system_instruction = openai_messages_to_gemini(plan_messages)
        payload: dict = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 300, "temperature": 0.0},
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{self.llm_base_url}/models/{self.model}:generateContent?key={self.llm_api_key}"
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        return ""
                    data = await resp.json()
        except Exception:
            return ""

        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()

    async def _openai_plan(self, plan_messages: list) -> str:
        """Call an OpenAI-compatible endpoint for planning."""
        url = f"{self.llm_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": plan_messages,
            "stream": False,
            "max_tokens": 300,
            "temperature": 0.0,
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
        return choices[0].get("message", {}).get("content", "").strip()

    # ------------------------------------------------------------------ #
    # Streaming helper (delegates to DynamicAgent based on backend type)
    # ------------------------------------------------------------------ #

    async def _stream_to_response(self, messages, gen_config, stream_response, chunk_id):
        """Stream the synthesis response back to the client."""
        if _is_gemini(self.llm_base_url):
            await self._gemini_stream(messages, gen_config, stream_response, chunk_id)
        else:
            # For OpenAI-compatible backends, proxy the stream
            url = f"{self.llm_base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.llm_api_key}",
                "Content-Type": "application/json",
            }
            payload = {"model": self.model, "messages": messages, "stream": True}
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            try:
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(url, json=payload, headers=headers) as resp:
                        async for chunk in resp.content.iter_chunked(1024):
                            await stream_response.write(chunk)
            except Exception:
                pass
