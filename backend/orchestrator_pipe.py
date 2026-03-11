"""
Orchestrator Pipe Function — routes user messages to specialist agents.

Paste this into Open WebUI: Admin > Workspace > Functions > Create
  Type: Pipe
  ID:   orchestrator

Replaces the standalone orchestrator_agent.py + llm_provider.py.
Orchestration events flow through __event_emitter__ (Socket.IO) instead of
a separate WebSocket connection.

Routing flow:
  1. Receives chat completion request via pipe()
  2. Calls local LLM (Ollama) to classify the user's message
  3. Forwards the full conversation to the selected downstream agent(s)
  4. Streams the agent's response (single) or synthesises (multi-agent)
"""

import json
import os
import ssl
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Callable, Optional

import aiohttp
import certifi
from pydantic import BaseModel, Field

_ssl_ctx = ssl.create_default_context(cafile=certifi.where())


class Pipe:
    class Valves(BaseModel):
        OLLAMA_BASE_URL: str = Field(
            default="http://localhost:11434",
            description="Ollama base URL for routing LLM",
        )
        ROUTING_MODEL: str = Field(
            default="llama3.1:8b",
            description="Model used for routing decisions and synthesis",
        )
        ROUTING_SYSTEM_PROMPT: str = Field(
            default=(
                "You are the Orchestrator for C-Agents, a multi-agent enterprise "
                "AI platform. You coordinate specialist agents to answer employee queries.\n\n"
                "When synthesising specialist responses, produce a clear, structured answer. "
                "Reference the information from each agent where relevant.\n\n"
                "Available agents are listed with their ID, name, and description.\n"
                'Respond with a JSON array of objects. Each object has "id" (the agent ID) '
                'and "action" specific task description (10-20 words, e.g. '
                '"Verify employee identity and check current password status").\n'
                "Examples:\n"
                "  Example for a password-change request:\n"
                '[{"agent": "hr", "action": "Verify employee identity and confirm account details"},\n'
                ' {"agent": "it", "action": "Check if password reset is permitted and initiate the process"}]\n'
                "If no agent is suitable, respond with exactly: NONE"
            ),
            description="System prompt for the routing LLM",
        )
        WEBUI_BASE_URL: str = Field(
            default="http://localhost:8080",
            description="Open WebUI base URL for internal API calls",
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        return [{"id": "orchestrator", "name": "C-Agents Orchestrator"}]

    # ------------------------------------------------------------------
    # LLM helpers (replaces llm_provider.py)
    # ------------------------------------------------------------------

    async def _call_llm(self, messages: list[dict], model: str | None = None) -> dict:
        """Non-streaming chat completion via Ollama."""
        effective_model = model or self.valves.ROUTING_MODEL
        url = f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions"
        payload = {"model": effective_model, "messages": messages, "stream": False}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        print(f"[orchestrator-pipe] call_llm failed ({resp.status}): {err[:200]}", flush=True)
                        return self._empty_response(effective_model)
                    return await resp.json()
        except Exception as e:
            print(f"[orchestrator-pipe] call_llm error: {e!r}", flush=True)
            return self._empty_response(effective_model)

    @asynccontextmanager
    async def _stream_llm(self, messages: list[dict], model: str | None = None):
        """Streaming chat completion via Ollama. Yields raw SSE text lines."""
        effective_model = model or self.valves.ROUTING_MODEL
        url = f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions"
        payload = {"model": effective_model, "messages": messages, "stream": True}

        session = aiohttp.ClientSession()
        try:
            resp = await session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=300))

            async def _lines():
                if resp.status != 200:
                    err = await resp.text()
                    print(f"[orchestrator-pipe] stream_llm failed ({resp.status}): {err[:200]}", flush=True)
                    return
                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8").strip()
                    if line:
                        yield line

            yield _lines()
        finally:
            await session.close()

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

    # ------------------------------------------------------------------
    # Agent discovery
    # ------------------------------------------------------------------

    async def _discover_agents(self) -> dict[str, dict]:
        """
        Discover agents from OpenAI connections (owned_by == 'c-agents')
        and workspace models in the Open WebUI DB.
        """
        agents: dict[str, dict] = {}

        # 1) Scan OpenAI-compatible connections
        try:
            from open_webui.config import OPENAI_API_BASE_URLS, OPENAI_API_KEYS

            base_urls: list[str] = OPENAI_API_BASE_URLS.value or []
            api_keys: list[str] = OPENAI_API_KEYS.value or []

            connector = aiohttp.TCPConnector(ssl=_ssl_ctx)
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
                    print(f"[orchestrator-pipe] Failed to query {base_url}: {e!r}", flush=True)
                    continue
            await connector.close()
        except Exception as e:
            print(f"[orchestrator-pipe] Cannot import Open WebUI config: {e!r}", flush=True)

        # 2) Workspace models from DB
        try:
            from open_webui.models.models import Models

            for m in Models.get_all_models() or []:
                if m.id == "orchestrator" or m.id in agents:
                    continue
                agents[m.id] = {
                    "name": m.name,
                    "description": (m.meta.description if m.meta else None) or "",
                    "url": None,  # None = route via Open WebUI internal proxy
                    "profile_image_url": (m.meta.profile_image_url if m.meta else None) or "",
                }
        except Exception as e:
            print(f"[orchestrator-pipe] Failed to load workspace models: {e!r}", flush=True)

        return agents

    # ------------------------------------------------------------------
    # Permission filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _get_user_accessible_agent_ids(user_id: str, agent_ids: list[str]) -> set[str] | None:
        try:
            from open_webui.models.access_grants import AccessGrants
            return AccessGrants.get_accessible_resource_ids(
                user_id=user_id,
                resource_type="model",
                resource_ids=agent_ids,
                permission="read",
            )
        except Exception as e:
            print(f"[orchestrator-pipe] DB access check failed: {e!r}", flush=True)
            return None

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

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

    async def _route_message(
        self,
        user_message: str,
        agents_subset: dict,
        conversation: list | None = None,
    ) -> list[dict]:
        """
        Ask the LLM which agent(s) should handle this message.
        Returns [{"id": "agent-id", "action": "short description"}, ...] or [].
        """
        if not agents_subset:
            return []

        agents_list = [
            {"id": k, "name": v["name"], "description": v["description"]}
            for k, v in agents_subset.items()
        ]

        # Build conversation context for follow-up messages
        context_block = ""
        if conversation and len(conversation) > 1:
            recent = conversation[-10:]
            history_lines = []
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
                    )
                if content and role in ("user", "assistant"):
                    history_lines.append(f"{role}: {content[:200]}")
            if history_lines:
                context_block = "Recent conversation:\n" + "\n".join(history_lines) + "\n\n"

        routing_messages = [
            {"role": "system", "content": self.valves.ROUTING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Available agents:\n{json.dumps(agents_list, indent=2)}\n\n"
                    f"{context_block}"
                    f"Latest user message: {user_message}\n\n"
                    "Based on the conversation context and the latest message, respond with a JSON array of objects.\n"
                    'Each object must have "id" (agent ID) and "action" (a short present-participle description '
                    "of what this agent will do for this specific request, e.g. "
                    '"Resetting user password", "Looking up leave balance", "Processing expense receipt").\n'
                    'Example: [{"id": "it-agent", "action": "Resetting user password"}]\n'
                    "If no agent is suitable, respond with exactly: NONE"
                ),
            },
        ]

        try:
            result = await self._call_llm(routing_messages)
        except Exception as e:
            print(f"[orchestrator-pipe] routing LLM call failed: {e!r}", flush=True)
            return []

        choices = result.get("choices", [])
        if not choices:
            return []
        selected = choices[0].get("message", {}).get("content", "").strip()
        print(f"[orchestrator-pipe] routing raw response: {selected!r}", flush=True)

        if selected == "NONE":
            return []

        # Strip markdown code fences
        cleaned = selected
        if "```" in cleaned:
            fence_start = cleaned.find("```")
            first_newline = cleaned.find("\n", fence_start)
            fence_end = cleaned.rfind("```")
            if first_newline != -1 and fence_end > first_newline:
                cleaned = cleaned[first_newline + 1:fence_end].strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                results = []
                for item in parsed:
                    if isinstance(item, dict) and item.get("id") in agents_subset:
                        results.append({"id": item["id"], "action": item.get("action", "Handling request")})
                    elif isinstance(item, str) and item in agents_subset:
                        results.append({"id": item, "action": "Handling request"})
                return results
        except (json.JSONDecodeError, TypeError):
            pass

        if cleaned in agents_subset:
            return [{"id": cleaned, "action": "Handling request"}]

        return []

    # ------------------------------------------------------------------
    # JWT minting for internal Open WebUI calls
    # ------------------------------------------------------------------

    @staticmethod
    def _mint_user_token(user_id: str) -> str:
        import jwt as _jwt

        secret = os.environ.get("WEBUI_SECRET_KEY", os.environ.get("WEBUI_JWT_SECRET_KEY", "t0p-s3cr3t"))
        payload = {
            "id": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "jti": str(uuid.uuid4()),
        }
        return _jwt.encode(payload, secret, algorithm="HS256")

    # ------------------------------------------------------------------
    # Main pipe entry point
    # ------------------------------------------------------------------

    async def pipe(
        self,
        body: dict,
        __user__: dict,
        __event_emitter__: Callable = None,
        __task__: str = None,
        __metadata__: dict = None,
    ) -> AsyncGenerator[str, None] | str:
        """
        Main entry point. Returns an AsyncGenerator for streaming or a str.
        """
        # Skip orchestration for background tasks (title generation, tags, etc.)
        if __task__:
            result = await self._call_llm(body.get("messages", []))
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content

        messages = body.get("messages", [])
        user_message = self._extract_last_user_message(messages)
        streaming = body.get("stream", False)

        user_id = __user__.get("id", "")
        user_role = __user__.get("role", "")

        session_id = str(uuid.uuid4())

        async def emit(step: str, **kwargs):
            if __event_emitter__:
                await __event_emitter__({
                    "type": "orchestration",
                    "data": {"step": step, "session_id": session_id, **kwargs},
                })

        # --- Emit: session start ---
        await emit("session_start", message="Request received")

        # --- Discover agents ---
        all_agents = await self._discover_agents()

        # --- Permission filtering ---
        if user_role == "admin":
            accessible_agents = all_agents
        elif user_id:
            accessible_ids = self._get_user_accessible_agent_ids(user_id, list(all_agents.keys()))
            accessible_agents = {k: v for k, v in all_agents.items() if k in (accessible_ids or set())}
        else:
            accessible_agents = {}

        # --- Route ---
        await emit(
            "routing",
            message="Selecting the best agent...",
            agents=[{"id": k, "name": v["name"]} for k, v in accessible_agents.items()],
        )
        routed_agents = await self._route_message(user_message, accessible_agents, conversation=messages)
        action_map = {r["id"]: r["action"] for r in routed_agents}
        selected_ids = list(action_map.keys())

        # --- No agent routed ---
        if not selected_ids:
            if not accessible_agents:
                await emit("session_done", message="No accessible agents")
                return (
                    "Sorry, you don't have permission to access any specialist agent. "
                    "Please contact your admin."
                )
            # Answer directly (greetings, capability questions)
            await emit("session_done", message="Handled directly")
            return await self._answer_directly(messages, accessible_agents, streaming)

        # --- Helper: get URL and auth for an agent ---
        def _agent_url_and_auth(agent_id: str) -> tuple[str, str]:
            agent = accessible_agents[agent_id]
            if agent["url"] is None:
                url = f"{self.valves.WEBUI_BASE_URL}/api/chat/completions"
                token = self._mint_user_token(user_id) if user_id else ""
                auth = f"Bearer {token}"
            else:
                url = f"{agent['url']}/chat/completions"
                auth = "Bearer sk-placeholder"
            return url, auth

        # --- Helper: call one agent non-streaming ---
        async def _call_agent(agent_id: str) -> str:
            agent = accessible_agents[agent_id]
            await emit(
                "agent_active",
                agent_id=agent_id,
                agent_label=agent["name"],
                agent_icon="🤖",
                agent_avatar_url=agent.get("profile_image_url", ""),
                agent_dept="",
                action=action_map.get(agent_id, "Handling request"),
            )
            agent_url, forward_auth = _agent_url_and_auth(agent_id)
            forward_messages = list(messages)
            if len(selected_ids) > 1:
                scope_msg = {
                    "role": "system",
                    "content": (
                        f"The user's message covers multiple topics. You are {agent['name']}. "
                        "Focus ONLY on the parts relevant to your expertise and ignore the rest — "
                        "another specialist agent is handling those. "
                        "Do NOT refuse or say the request is out of scope."
                    ),
                }
                forward_messages = [scope_msg] + forward_messages
            forward_body = {**body, "messages": forward_messages, "model": agent_id, "stream": False}
            # Remove metadata to avoid recursive pipe invocation issues
            forward_body.pop("metadata", None)
            try:
                connector = aiohttp.TCPConnector(ssl=_ssl_ctx)
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(
                        agent_url,
                        json=forward_body,
                        headers={"Authorization": forward_auth, "Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp:
                        if resp.status != 200:
                            err_text = await resp.text()
                            await emit("agent_done", agent_id=agent_id, agent_label=agent["name"])
                            return f"[{agent['name']}]: Error — {err_text[:200]}"
                        data = await resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                await emit("agent_done", agent_id=agent_id, agent_label=agent["name"])
                return text
            except Exception as e:
                await emit("agent_done", agent_id=agent_id, agent_label=agent["name"])
                return f"[{agent['name']}]: Error — {e!r}"

        # =============================================================
        # SINGLE AGENT — proxy streaming or non-streaming
        # =============================================================
        if len(selected_ids) == 1:
            selected_id = selected_ids[0]
            agent = accessible_agents[selected_id]
            await emit(
                "agent_active",
                agent_id=selected_id,
                agent_label=agent["name"],
                agent_icon="🤖",
                agent_avatar_url=agent.get("profile_image_url", ""),
                agent_dept="",
                action=action_map.get(selected_id, "Handling request"),
            )
            agent_url, forward_auth = _agent_url_and_auth(selected_id)
            forward_body = {**body, "model": selected_id, "stream": streaming}
            forward_body.pop("metadata", None)

            if not streaming:
                connector = aiohttp.TCPConnector(ssl=_ssl_ctx)
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(
                        agent_url,
                        json=forward_body,
                        headers={"Authorization": forward_auth, "Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as resp:
                        if resp.status != 200:
                            err_text = await resp.text()
                            await emit("agent_done", agent_id=selected_id, agent_label=agent["name"])
                            await emit("session_done", message="Error")
                            return f"Error from {agent['name']}: {err_text[:200]}"
                        data = await resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                await emit("agent_done", agent_id=selected_id, agent_label=agent["name"])
                await emit("session_done", message="Completed")
                return text

            # Streaming single agent — return async generator
            async def _stream_single():
                connector = aiohttp.TCPConnector(ssl=_ssl_ctx)
                try:
                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.post(
                            agent_url,
                            json=forward_body,
                            headers={"Authorization": forward_auth, "Content-Type": "application/json"},
                            timeout=aiohttp.ClientTimeout(total=300),
                        ) as resp:
                            if resp.status != 200:
                                err_text = await resp.text()
                                yield f"Error from {agent['name']}: {err_text[:200]}"
                                return
                            async for raw_line in resp.content:
                                line = raw_line.decode("utf-8").strip()
                                if not line:
                                    continue
                                if line == "data: [DONE]":
                                    break
                                # Pass through SSE lines as-is
                                if line.startswith("data: "):
                                    yield line
                finally:
                    await emit("agent_done", agent_id=selected_id, agent_label=agent["name"])
                    await emit("session_done", message="Completed")

            return _stream_single()

        # =============================================================
        # MULTIPLE AGENTS — collect responses, then synthesise
        # =============================================================
        agent_responses: list[tuple[str, str]] = []
        for agent_id in selected_ids:
            text = await _call_agent(agent_id)
            agent_responses.append((accessible_agents[agent_id]["name"], text))

        # Synthesise
        responses_text = "\n\n".join(
            f"--- Response from {name} ---\n{text}" for name, text in agent_responses
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

        if not streaming:
            result = await self._call_llm(synthesis_messages)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            await emit("session_done", message="Completed")
            return content

        # Streaming synthesis
        async def _stream_synthesis():
            try:
                async with self._stream_llm(synthesis_messages) as lines:
                    async for line in lines:
                        if line == "data: [DONE]":
                            break
                        if line.startswith("data: "):
                            try:
                                chunk = json.loads(line[6:])
                                chunk["model"] = "orchestrator"
                                yield f"data: {json.dumps(chunk)}"
                            except json.JSONDecodeError:
                                continue
            finally:
                await emit("session_done", message="Completed")

        return _stream_synthesis()

    # ------------------------------------------------------------------
    # Direct LLM answering (greetings, capability questions)
    # ------------------------------------------------------------------

    async def _answer_directly(
        self,
        messages: list,
        agents: dict,
        streaming: bool,
    ) -> AsyncGenerator[str, None] | str:
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

        llm_messages = [{"role": "system", "content": system_prompt}] + messages

        if not streaming:
            result = await self._call_llm(llm_messages)
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        async def _stream_direct():
            async with self._stream_llm(llm_messages) as lines:
                async for line in lines:
                    if line == "data: [DONE]":
                        break
                    if line.startswith("data: "):
                        try:
                            chunk = json.loads(line[6:])
                            chunk["model"] = "orchestrator"
                            yield f"data: {json.dumps(chunk)}"
                        except json.JSONDecodeError:
                            continue

        return _stream_direct()
