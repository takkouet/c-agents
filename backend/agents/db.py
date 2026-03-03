"""
SQLite persistence layer for the agent registry.

Schema:
    agents(id, name, purpose, department, icon, base_url, api_key, model,
           system_prompt, is_orchestrator, enabled, created_at,
           llm_base_url, llm_api_key)

Field semantics:
    base_url     — Agent SERVICE URL (where /health, /models, /chat/completions live).
                   Empty for built-in agents (auto-set at runtime).
    api_key      — Bearer token for authenticating with the agent service.
    llm_base_url — LLM backend URL (Gemini/OpenAI). Used by built-in agents only.
    llm_api_key  — LLM API key. Used by built-in agents only.
                   Both llm_* fields are empty for external agents.
"""

import time
from typing import Any

import aiosqlite

from agents.config import (
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
)
from agents.services.finance import FINANCE_AGENT
from agents.services.hr import HR_AGENT
from agents.services.it import IT_AGENT

# ------------------------------------------------------------------ #
# Default seed data (used when DB is first created)
# ------------------------------------------------------------------ #


def _worker_seed(cfg) -> dict:
    """Convert an AgentConfig to a seed-data dict for the agents table."""
    return {
        "id": cfg.agent_id,
        "name": cfg.name,
        "purpose": cfg.purpose,
        "department": cfg.department,
        "icon": cfg.icon,
        "base_url": "",           # Built-in: served on the main server
        "api_key": "",
        "model": GEMINI_MODEL,
        "system_prompt": cfg.system_prompt,
        "is_orchestrator": 0,
        "enabled": 1,
        "llm_base_url": GEMINI_BASE_URL,
        "llm_api_key": GEMINI_API_KEY,
    }


_SEED_AGENTS: list[dict] = [
    # Orchestrator — hidden from the agent directory, managed by developer
    {
        "id": "orchestrator",
        "name": "Orchestrator",
        "purpose": "Analyses user requests and routes them to the most suitable specialist agent.",
        "department": "Platform",
        "icon": "🧠",
        "base_url": "",           # Built-in: auto-set at runtime
        "api_key": "",
        "model": GEMINI_MODEL,
        "system_prompt": (
            "You are the Orchestrator for C-Agents, a multi-agent enterprise AI platform. "
            "You coordinate specialist agents to answer employee queries.\n\n"
            "When synthesising specialist responses, produce a clear, structured answer. "
            "Reference the information from each agent where relevant."
        ),
        "is_orchestrator": 1,
        "enabled": 1,
        "llm_base_url": GEMINI_BASE_URL,
        "llm_api_key": GEMINI_API_KEY,
    },
    # Worker agents — configs imported from agents/services/*.py
    _worker_seed(HR_AGENT),
    _worker_seed(IT_AGENT),
    _worker_seed(FINANCE_AGENT),
]

# ------------------------------------------------------------------ #
# DB helpers
# ------------------------------------------------------------------ #

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    purpose         TEXT NOT NULL DEFAULT '',
    department      TEXT NOT NULL DEFAULT '',
    icon            TEXT NOT NULL DEFAULT '🤖',
    base_url        TEXT NOT NULL DEFAULT '',
    api_key         TEXT NOT NULL DEFAULT '',
    model           TEXT NOT NULL DEFAULT '',
    system_prompt   TEXT NOT NULL DEFAULT '',
    is_orchestrator INTEGER NOT NULL DEFAULT 0,
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      INTEGER NOT NULL,
    llm_base_url    TEXT NOT NULL DEFAULT '',
    llm_api_key     TEXT NOT NULL DEFAULT ''
)
"""

MIGRATION_SQL = [
    # v2: add llm_base_url and llm_api_key columns, migrate data from base_url/api_key
    (
        "llm_base_url",
        [
            "ALTER TABLE agents ADD COLUMN llm_base_url TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE agents ADD COLUMN llm_api_key TEXT NOT NULL DEFAULT ''",
            # Migrate: existing base_url/api_key were LLM config → move to llm_ fields
            "UPDATE agents SET llm_base_url = base_url, llm_api_key = api_key",
            # Clear base_url/api_key (now used for service URL / service auth)
            "UPDATE agents SET base_url = '', api_key = ''",
        ],
    ),
]


async def _run_migrations(conn: aiosqlite.Connection) -> None:
    """Apply pending schema migrations."""
    for check_column, statements in MIGRATION_SQL:
        cursor = await conn.execute("PRAGMA table_info(agents)")
        columns = {row[1] for row in await cursor.fetchall()}
        if check_column not in columns:
            for sql in statements:
                await conn.execute(sql)
            await conn.commit()


async def init_db(conn: aiosqlite.Connection) -> None:
    """Create schema, run migrations, and seed default agents if table is empty."""
    await conn.execute(CREATE_TABLE_SQL)
    await conn.commit()

    # Run any pending migrations for existing DBs
    await _run_migrations(conn)

    cursor = await conn.execute("SELECT COUNT(*) FROM agents")
    row = await cursor.fetchone()
    if row[0] == 0:
        now = int(time.time())
        for agent in _SEED_AGENTS:
            await conn.execute(
                """INSERT INTO agents
                   (id, name, purpose, department, icon, base_url, api_key, model,
                    system_prompt, is_orchestrator, enabled, created_at,
                    llm_base_url, llm_api_key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    agent["id"],
                    agent["name"],
                    agent["purpose"],
                    agent["department"],
                    agent["icon"],
                    agent["base_url"],
                    agent["api_key"],
                    agent["model"],
                    agent["system_prompt"],
                    agent["is_orchestrator"],
                    agent["enabled"],
                    now,
                    agent["llm_base_url"],
                    agent["llm_api_key"],
                ),
            )
        await conn.commit()


async def get_all_agents(conn: aiosqlite.Connection) -> list[dict]:
    conn.row_factory = aiosqlite.Row
    cursor = await conn.execute("SELECT * FROM agents ORDER BY created_at ASC")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_agent(conn: aiosqlite.Connection, agent_id: str) -> dict | None:
    conn.row_factory = aiosqlite.Row
    cursor = await conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def upsert_agent(conn: aiosqlite.Connection, data: dict[str, Any]) -> None:
    """Insert or replace an agent record."""
    data.setdefault("created_at", int(time.time()))
    data.setdefault("llm_base_url", "")
    data.setdefault("llm_api_key", "")
    await conn.execute(
        """INSERT INTO agents
           (id, name, purpose, department, icon, base_url, api_key, model,
            system_prompt, is_orchestrator, enabled, created_at,
            llm_base_url, llm_api_key)
           VALUES (:id, :name, :purpose, :department, :icon, :base_url, :api_key,
                   :model, :system_prompt, :is_orchestrator, :enabled, :created_at,
                   :llm_base_url, :llm_api_key)
           ON CONFLICT(id) DO UPDATE SET
               name            = excluded.name,
               purpose         = excluded.purpose,
               department      = excluded.department,
               icon            = excluded.icon,
               base_url        = excluded.base_url,
               api_key         = excluded.api_key,
               model           = excluded.model,
               system_prompt   = excluded.system_prompt,
               is_orchestrator = excluded.is_orchestrator,
               enabled         = excluded.enabled,
               llm_base_url    = excluded.llm_base_url,
               llm_api_key     = excluded.llm_api_key""",
        data,
    )
    await conn.commit()


async def delete_agent(conn: aiosqlite.Connection, agent_id: str) -> bool:
    """Delete an agent. Returns False if agent does not exist or is the orchestrator."""
    cursor = await conn.execute(
        "SELECT is_orchestrator FROM agents WHERE id = ?", (agent_id,)
    )
    row = await cursor.fetchone()
    if row is None or row[0] == 1:
        return False
    await conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    await conn.commit()
    return True
