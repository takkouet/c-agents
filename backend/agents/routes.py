"""
Route registration for all agents.
Called once by server.py to wire up the aiohttp app.

Agents come in two flavours:
  - Built-in (llm_base_url set): served by DynamicAgent on this server.
  - External (base_url set, llm_base_url empty): proxied via ExternalAgentProxy.
"""

import asyncio
import re
import time

from aiohttp import ClientConnectionResetError, web

from agents import broadcast
from agents.config import CORS_HEADERS
from agents.db import delete_agent, get_agent, get_all_agents, init_db, upsert_agent
from agents.dynamic_agent import DynamicAgent
from agents.external_proxy import ExternalAgentProxy
from agents.orchestrator import OrchestratorAgent
from agents.services.finance import register as register_finance
from agents.services.hr import register as register_hr
from agents.services.it import register as register_it


# ------------------------------------------------------------------ #
# Agent factory — builds DynamicAgent or ExternalProxy from DB rows
# ------------------------------------------------------------------ #

def _is_external(row: dict) -> bool:
    """An agent is external if it has a base_url but no llm_base_url."""
    return bool(row.get("base_url")) and not bool(row.get("llm_base_url"))


def _agent_from_row(row: dict):
    """Create either a DynamicAgent or ExternalAgentProxy from a DB row."""
    if _is_external(row):
        return ExternalAgentProxy(
            agent_id=row["id"],
            name=row["name"],
            base_url=row["base_url"],
            api_key=row.get("api_key", ""),
            model=row.get("model", ""),
            system_prompt=row.get("system_prompt", ""),
            icon=row.get("icon", "🤖"),
            department=row.get("department", ""),
        )
    else:
        return DynamicAgent(
            agent_id=row["id"],
            name=row["name"],
            system_prompt=row["system_prompt"],
            llm_base_url=row.get("llm_base_url", ""),
            llm_api_key=row.get("llm_api_key", ""),
            model=row["model"],
            icon=row.get("icon", "🤖"),
            department=row.get("department", ""),
        )


async def _load_agents_from_db(app: web.Application) -> tuple[OrchestratorAgent, dict]:
    """Read all enabled agents from DB and return orchestrator + worker dict.

    Does NOT call ``orchestrator.update_workers`` — the caller (``reload_agents``)
    merges service-registered workers first, then updates the orchestrator.
    """
    conn = app["db"]
    rows = await get_all_agents(conn)

    orchestrator_row = next((r for r in rows if r["is_orchestrator"] == 1 and r["enabled"] == 1), None)
    worker_rows = [r for r in rows if r["is_orchestrator"] == 0 and r["enabled"] == 1]

    db_workers: dict = {r["id"]: _agent_from_row(r) for r in worker_rows}

    orchestrator: OrchestratorAgent = app.get("orchestrator")
    if orchestrator is None:
        orchestrator = OrchestratorAgent(workers=db_workers)

    if orchestrator_row:
        orchestrator.update_config(
            system_prompt=orchestrator_row["system_prompt"],
            llm_base_url=orchestrator_row.get("llm_base_url", ""),
            llm_api_key=orchestrator_row.get("llm_api_key", ""),
            model=orchestrator_row["model"],
        )

    return orchestrator, db_workers


async def reload_agents(app: web.Application) -> None:
    """Reload agents from DB, merge with service-registered workers, and update routes."""
    orchestrator, db_workers = await _load_agents_from_db(app)
    app["orchestrator"] = orchestrator

    # Merge: DB workers override service-registered ones (allows admin config updates)
    merged: dict = app.get("workers", {})
    merged.update(db_workers)
    app["workers"] = merged

    orchestrator.update_workers(merged)

    # Register routes for any agents not yet registered (admin-created via API)
    registered: set = app.get("_dynamic_routes", set())
    for agent_id in merged:
        if agent_id not in registered:
            _register_worker_routes(app, agent_id)
            registered.add(agent_id)
    app["_dynamic_routes"] = registered


def _register_worker_routes(app: web.Application, agent_id: str) -> None:
    """Register per-agent endpoints with dynamic lookup (same pattern as service register)."""

    async def _health(request: web.Request) -> web.Response:
        return await request.app["workers"][agent_id].handle_health(request)

    async def _models(request: web.Request) -> web.Response:
        return await request.app["workers"][agent_id].handle_models(request)

    async def _chat(request: web.Request) -> web.Response:
        return await request.app["workers"][agent_id].handle_chat_completions(request)

    app.router.add_get(f"/v1/{agent_id}/health", _health)
    app.router.add_get(f"/v1/{agent_id}/models", _models)
    app.router.add_post(f"/v1/{agent_id}/chat/completions", _chat)


# ------------------------------------------------------------------ #
# Utility handlers
# ------------------------------------------------------------------ #

async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "c-agents"}, headers=CORS_HEADERS)


async def handle_agents_list(request: web.Request) -> web.Response:
    """GET /v1/agents — return non-orchestrator agents for the frontend dashboard."""
    conn = request.app["db"]
    rows = await get_all_agents(conn)
    now = int(time.time())
    data = [
        {
            "id": r["id"],
            "name": r["name"],
            "purpose": r["purpose"],
            "department": r["department"],
            "icon": r["icon"],
            "model": r["model"],
            "base_url": r.get("base_url", ""),
            "is_external": _is_external(r),
            "enabled": bool(r["enabled"]),
            "created": r.get("created_at", now),
        }
        for r in rows
        if r["is_orchestrator"] == 0
    ]
    return web.json_response({"object": "list", "data": data}, headers=CORS_HEADERS)


async def handle_agents_list_all(request: web.Request) -> web.Response:
    """GET /v1/agents/all — return all agents including orchestrator (admin view)."""
    conn = request.app["db"]
    rows = await get_all_agents(conn)
    now = int(time.time())
    data = [
        {
            "id": r["id"],
            "name": r["name"],
            "purpose": r["purpose"],
            "department": r["department"],
            "icon": r["icon"],
            "base_url": r.get("base_url", ""),
            "model": r["model"],
            "system_prompt": r["system_prompt"],
            "is_orchestrator": bool(r["is_orchestrator"]),
            "is_external": _is_external(r),
            "enabled": bool(r["enabled"]),
            "created": r.get("created_at", now),
            "llm_base_url": r.get("llm_base_url", ""),
        }
        for r in rows
    ]
    return web.json_response({"object": "list", "data": data}, headers=CORS_HEADERS)


async def handle_get_agent(request: web.Request) -> web.Response:
    """GET /v1/agents/{id}"""
    agent_id = request.match_info["id"]
    conn = request.app["db"]
    row = await get_agent(conn, agent_id)
    if row is None:
        return web.json_response({"error": "Agent not found"}, status=404, headers=CORS_HEADERS)
    now = int(time.time())
    return web.json_response(
        {
            "id": row["id"],
            "name": row["name"],
            "purpose": row["purpose"],
            "department": row["department"],
            "icon": row["icon"],
            "base_url": row.get("base_url", ""),
            "api_key": row.get("api_key", ""),
            "model": row["model"],
            "system_prompt": row["system_prompt"],
            "is_orchestrator": bool(row["is_orchestrator"]),
            "is_external": _is_external(row),
            "enabled": bool(row["enabled"]),
            "created": row.get("created_at", now),
            "llm_base_url": row.get("llm_base_url", ""),
            "llm_api_key": row.get("llm_api_key", ""),
        },
        headers=CORS_HEADERS,
    )


async def handle_create_agent(request: web.Request) -> web.Response:
    """POST /v1/agents — create a new agent."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)

    agent_id = body.get("id", "").strip()
    if not agent_id:
        name = body.get("name", "agent")
        agent_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    if not agent_id:
        return web.json_response({"error": "Agent id is required"}, status=400, headers=CORS_HEADERS)

    conn = request.app["db"]
    existing = await get_agent(conn, agent_id)
    if existing is not None:
        return web.json_response(
            {"error": f"Agent '{agent_id}' already exists"}, status=409, headers=CORS_HEADERS
        )

    data = {
        "id": agent_id,
        "name": body.get("name", agent_id),
        "purpose": body.get("purpose", ""),
        "department": body.get("department", ""),
        "icon": body.get("icon", "🤖"),
        "base_url": body.get("base_url", ""),
        "api_key": body.get("api_key", ""),
        "model": body.get("model", ""),
        "system_prompt": body.get("system_prompt", ""),
        "is_orchestrator": 0,
        "enabled": int(body.get("enabled", True)),
        "llm_base_url": body.get("llm_base_url", ""),
        "llm_api_key": body.get("llm_api_key", ""),
    }
    await upsert_agent(conn, data)
    await reload_agents(request.app)

    row = await get_agent(conn, agent_id)
    return web.json_response(row, status=201, headers=CORS_HEADERS)


async def handle_update_agent(request: web.Request) -> web.Response:
    """PUT /v1/agents/{id} — update an existing agent."""
    agent_id = request.match_info["id"]
    conn = request.app["db"]

    existing = await get_agent(conn, agent_id)
    if existing is None:
        return web.json_response({"error": "Agent not found"}, status=404, headers=CORS_HEADERS)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)

    # Merge patch: keep existing values for fields not provided
    data = {
        "id": agent_id,
        "name": body.get("name", existing["name"]),
        "purpose": body.get("purpose", existing["purpose"]),
        "department": body.get("department", existing["department"]),
        "icon": body.get("icon", existing["icon"]),
        "base_url": body.get("base_url", existing.get("base_url", "")),
        "api_key": body.get("api_key", existing.get("api_key", "")),
        "model": body.get("model", existing["model"]),
        "system_prompt": body.get("system_prompt", existing["system_prompt"]),
        "is_orchestrator": existing["is_orchestrator"],
        "enabled": int(body.get("enabled", existing["enabled"])),
        "created_at": existing["created_at"],
        "llm_base_url": body.get("llm_base_url", existing.get("llm_base_url", "")),
        "llm_api_key": body.get("llm_api_key", existing.get("llm_api_key", "")),
    }
    await upsert_agent(conn, data)
    await reload_agents(request.app)

    row = await get_agent(conn, agent_id)
    return web.json_response(row, headers=CORS_HEADERS)


async def handle_delete_agent(request: web.Request) -> web.Response:
    """DELETE /v1/agents/{id} — delete an agent (orchestrator protected)."""
    agent_id = request.match_info["id"]
    conn = request.app["db"]
    deleted = await delete_agent(conn, agent_id)
    if not deleted:
        return web.json_response(
            {"error": "Agent not found or cannot delete orchestrator"},
            status=404,
            headers=CORS_HEADERS,
        )
    await reload_agents(request.app)
    return web.json_response({"deleted": True, "id": agent_id}, headers=CORS_HEADERS)


async def handle_orchestration_ws(request: web.Request) -> web.WebSocketResponse:
    """GET /v1/orchestration/ws — WebSocket stream of real-time orchestration events."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    q = broadcast.subscribe()
    try:
        await ws.send_json({"step": "connected"})
        while not ws.closed:
            try:
                event = await asyncio.wait_for(q.get(), timeout=20)
                await ws.send_json(event)
            except asyncio.TimeoutError:
                await ws.ping()
    except (asyncio.CancelledError, ConnectionResetError, ClientConnectionResetError):
        pass
    finally:
        broadcast.unsubscribe(q)

    return ws


async def handle_options(_request: web.Request) -> web.Response:
    return web.Response(status=204, headers=CORS_HEADERS)


# ------------------------------------------------------------------ #
# App startup / cleanup hooks
# ------------------------------------------------------------------ #

async def on_startup(app: web.Application) -> None:
    import aiosqlite
    from agents.config import DB_PATH
    conn = await aiosqlite.connect(DB_PATH)
    app["db"] = conn
    await init_db(conn)
    await reload_agents(app)


async def on_cleanup(app: web.Application) -> None:
    conn = app.get("db")
    if conn:
        await conn.close()


# ------------------------------------------------------------------ #
# Route registration
# ------------------------------------------------------------------ #

def register_routes(app: web.Application) -> None:
    """Wire all routes onto the aiohttp Application."""
    # Lifecycle hooks
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # CORS preflight
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_options)

    # Health
    app.router.add_get("/health", handle_health)

    # Orchestration WebSocket
    app.router.add_get("/v1/orchestration/ws", handle_orchestration_ws)

    # Agent CRUD — specific routes before the {id} catch-all
    app.router.add_get("/v1/agents", handle_agents_list)
    app.router.add_get("/v1/agents/all", handle_agents_list_all)
    app.router.add_post("/v1/agents", handle_create_agent)
    app.router.add_get("/v1/agents/{id}", handle_get_agent)
    app.router.add_put("/v1/agents/{id}", handle_update_agent)
    app.router.add_delete("/v1/agents/{id}", handle_delete_agent)

    # Built-in worker agents — each service file registers its own endpoints
    register_hr(app)
    register_it(app)
    register_finance(app)

    # Orchestrator routes (always at /v1/orchestrator/*)
    async def _orchestrator_health(request: web.Request) -> web.Response:
        return await request.app["orchestrator"].handle_health(request)

    async def _orchestrator_models(request: web.Request) -> web.Response:
        return await request.app["orchestrator"].handle_models(request)

    async def _orchestrator_chat(request: web.Request) -> web.Response:
        return await request.app["orchestrator"].handle_chat_completions(request)

    app.router.add_get("/v1/orchestrator/health", _orchestrator_health)
    app.router.add_get("/v1/orchestrator/models", _orchestrator_models)
    app.router.add_post("/v1/orchestrator/chat/completions", _orchestrator_chat)
