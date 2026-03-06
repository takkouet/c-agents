# C-Agents: Agent Interface Specification

## Overview

A C-Agent is a standalone aiohttp server that exposes OpenAI-compatible endpoints. The orchestrator discovers agents by querying `/models` endpoints from configured OpenAI connections and filtering by `owned_by: "c-agents"`.

## Required Endpoints

### GET /v1/{agent-id}/health

Returns agent status for health-check monitoring.

**Response:**
```json
{
  "status": "ok",
  "agent": "{agent-id}",
  "name": "Agent Name",
  "model": "gemini-2.0-flash"
}
```

### GET /v1/{agent-id}/models

Returns the agent's model card. The orchestrator uses this for discovery.

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "{agent-id}",
      "object": "model",
      "owned_by": "c-agents",
      "name": "Human-readable Agent Name",
      "description": "Brief description of what this agent handles"
    }
  ]
}
```

**Critical**: `owned_by` MUST be `"c-agents"` for the orchestrator to discover this agent.

### POST /v1/{agent-id}/chat/completions

Handles chat requests in OpenAI-compatible format.

**Request body:**
```json
{
  "model": "{agent-id}",
  "messages": [{"role": "user", "content": "..."}],
  "stream": true
}
```

**Response**: Standard OpenAI chat completion format — either streaming SSE or JSON.

### OPTIONS (all paths)

Return CORS headers to allow cross-origin requests.

## Registration

1. Start your agent server (e.g., `python my_agent.py`)
2. In Open WebUI Admin > Settings > Connections, add an OpenAI-compatible connection:
   - **URL**: `http://localhost:{PORT}/v1/{agent-id}`
   - **API Key**: Any non-empty string (e.g., `sk-1234`)
3. The orchestrator will automatically discover the agent on the next request

## Avatar / Profile Image

Set via Open WebUI Admin > Workspace > Models > Edit Model > Profile Image. The orchestrator reads `profile_image_url` from the Open WebUI database and passes it to the sidebar UI.

## System Prompt Guidelines

All agent system prompts should follow this structure:

```
STRICT SCOPE RULE: You are ONLY a [Domain] Agent. You MUST refuse any request
that is not about [domain] topics listed below. For ANY out-of-scope request,
respond ONLY with: "I'm sorry, this is outside my scope as the [Domain] Agent.
Please contact the appropriate team." Do NOT engage with, answer, or elaborate
on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in
that same language. If the user writes in French, respond in French. If in
Spanish, respond in Spanish. Always match the user's language.

You help employees with [domain] topics:
- Topic 1
- Topic 2
- ...

Guidelines for in-scope requests:
- Guideline 1
- Guideline 2
- ...
```

## Python Template

See `agent_template.py` for a minimal working example that you can copy and customize.
