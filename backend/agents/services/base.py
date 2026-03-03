"""
Agent service helpers — config + endpoint registration.

Each agent service file (hr.py, it.py, finance.py) defines an AgentConfig
and exposes a ``register(app)`` function that:

  1. Creates a DynamicAgent from the config
  2. Registers the three standard endpoints on the aiohttp app:
       GET  /v1/{agent_id}/health
       GET  /v1/{agent_id}/models
       POST /v1/{agent_id}/chat/completions
  3. Stores the agent in ``app["workers"]`` so the orchestrator can call it

All agents run on the main server (single port).
"""

from __future__ import annotations

from dataclasses import dataclass

from aiohttp import web

from agents.config import GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL
from agents.dynamic_agent import DynamicAgent


@dataclass(frozen=True)
class AgentConfig:
    """Immutable configuration for a worker agent."""

    agent_id: str
    name: str
    purpose: str
    system_prompt: str
    department: str = ""
    icon: str = "🤖"


def create_agent(config: AgentConfig) -> DynamicAgent:
    """Instantiate a DynamicAgent from an AgentConfig."""
    return DynamicAgent(
        agent_id=config.agent_id,
        name=config.name,
        system_prompt=config.system_prompt,
        llm_base_url=GEMINI_BASE_URL,
        llm_api_key=GEMINI_API_KEY,
        model=GEMINI_MODEL,
        icon=config.icon,
        department=config.department,
    )


def register_agent(app: web.Application, config: AgentConfig) -> DynamicAgent:
    """Create agent, register standard endpoints, and store in app state.

    Route handlers use dynamic lookup via ``app["workers"]`` so that
    admin updates (via DB reload) take effect without re-registering routes.

    Returns the DynamicAgent instance.
    """
    agent = create_agent(config)
    aid = config.agent_id

    async def _health(request: web.Request) -> web.Response:
        return await request.app["workers"][aid].handle_health(request)

    async def _models(request: web.Request) -> web.Response:
        return await request.app["workers"][aid].handle_models(request)

    async def _chat(request: web.Request) -> web.Response:
        return await request.app["workers"][aid].handle_chat_completions(request)

    app.router.add_get(f"/v1/{aid}/health", _health)
    app.router.add_get(f"/v1/{aid}/models", _models)
    app.router.add_post(f"/v1/{aid}/chat/completions", _chat)

    app.setdefault("workers", {})[aid] = agent
    app.setdefault("_dynamic_routes", set()).add(aid)

    return agent
