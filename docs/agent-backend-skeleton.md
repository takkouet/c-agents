# Agent Backend Skeleton for Open WebUI

A reusable project skeleton for building backend agents that serve on Open WebUI. Uses FastAPI + Ollama (local LLM), zero-cost monitoring, and minimal dependencies.

---

## Architecture Overview

```
Open WebUI  ──POST /v1/chat/completions──▶  Agent Backend  ──▶  Ollama (local LLM)
            ◀──── SSE streaming ──────────  (FastAPI:4000)      (localhost:11434)
```

The agent backend is a **thin proxy** that:
1. Exposes itself as an OpenAI-compatible model to Open WebUI
2. Injects system prompts and manages tool execution
3. Delegates LLM inference to a local Ollama instance

---

## Framework: FastAPI

| Considered | Verdict |
|------------|---------|
| **FastAPI** | **Selected** — async, Pydantic validation, auto OpenAPI docs, already used in this project |
| aiohttp | Manual validation, manual CORS, manual OpenAPI schemas |
| LangGraph/CrewAI | 200+ MB deps, opinionated abstractions — overkill for a single agent |
| Litestar | Good but adds learning curve with no real upside over FastAPI here |

If you need LangGraph later, call it as a library inside a FastAPI route — you don't need LangServe.

## LLM Provider: Ollama (Local)

| Feature | Detail |
|---------|--------|
| Cost | Free — runs locally |
| API | Already OpenAI-compatible (`/v1/chat/completions`) |
| Streaming | Native SSE support |
| Format conversion | None needed — speaks OpenAI format directly |
| Models | llama3.2, mistral, qwen, gemma2, etc. |
| Alternatives | LM Studio, vLLM, LocalAI — all use same OpenAI API format |

---

## Project Structure

```
agent-backend/
├── pyproject.toml                # Deps + metadata (8 production deps)
├── Dockerfile
├── docker-compose.yaml
├── .env.example
│
├── app/
│   ├── __init__.py
│   ├── main.py                   # App factory, CORS, lifespan, mount routers
│   ├── config.py                 # pydantic-settings: env vars
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── openai.py             # Pydantic schemas: Request/Response/Chunk
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py             # GET /health
│   │   ├── models.py             # GET /v1/models
│   │   └── chat.py               # POST /v1/chat/completions
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── base.py               # BaseAgent: system_prompt, run(), run_stream()
│   │   ├── llm.py                # LLM client (Ollama via httpx)
│   │   └── tools.py              # Tool definitions + execution
│   │
│   └── utils/
│       ├── __init__.py
│       └── logging.py            # structlog JSON logging
│
└── tests/
    ├── conftest.py               # TestClient fixture, mock LLM
    ├── test_health.py
    ├── test_models.py
    └── test_chat.py
```

---

## File-by-File Reference

### `app/config.py` — Configuration

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    port: int = 4000
    host: str = "0.0.0.0"
    log_level: str = "info"

    # LLM Provider (Ollama default, works with any OpenAI-compatible local provider)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"        # Ollama ignores this, but some clients require it
    llm_model: str = "llama3.2"        # Model pulled in Ollama

    # Agent identity (how it appears in Open WebUI)
    agent_id: str = "my-agent"
    agent_name: str = "My Agent"

    class Config:
        env_file = ".env"


settings = Settings()
```

### `app/main.py` — App Factory

```python
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import health, models, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.start_time = time.time()
    yield


app = FastAPI(title=settings.agent_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(models.router)
app.include_router(chat.router)
```

### `app/models/openai.py` — Pydantic Schemas

```python
from __future__ import annotations
import time
import uuid
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message]
    stream: bool = False
    temperature: float | None = 0.7
    max_tokens: int | None = None
    top_p: float | None = None
    stop: str | list[str] | None = None


class Delta(BaseModel):
    role: str | None = None
    content: str | None = None


class Choice(BaseModel):
    index: int = 0
    message: Message | None = None
    delta: Delta | None = None
    finish_reason: str | None = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:8]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = ""
    choices: list[Choice] = []
    usage: Usage = Usage()


class ChatCompletionChunk(BaseModel):
    id: str = ""
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = ""
    choices: list[Choice] = []
```

### `app/routes/health.py` — Health Check

```python
import time
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    uptime = time.time() - request.app.state.start_time
    return {"status": "ok", "uptime_seconds": round(uptime, 1)}
```

### `app/routes/models.py` — Model Listing

```python
import time
from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": settings.agent_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "custom",
            }
        ],
    }
```

### `app/routes/chat.py` — Chat Completions

```python
import json
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.models.openai import ChatCompletionRequest, ChatCompletionResponse, Choice, Message, Usage
from app.agent.base import agent  # singleton instance

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    messages = [m.model_dump(exclude_none=True) for m in request.messages]

    if request.stream:
        return EventSourceResponse(
            _stream_generator(messages, request),
            media_type="text/event-stream",
        )

    # Non-streaming
    response_text = await agent.run(messages)
    return ChatCompletionResponse(
        model=request.model,
        choices=[
            Choice(
                message=Message(role="assistant", content=response_text),
                finish_reason="stop",
            )
        ],
        usage=Usage(),  # populate if your LLM returns token counts
    )


async def _stream_generator(messages: list[dict], request: ChatCompletionRequest):
    async for chunk_text in agent.run_stream(messages):
        chunk = {
            "id": "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "model": request.model,
            "choices": [{"index": 0, "delta": {"content": chunk_text}, "finish_reason": None}],
        }
        yield json.dumps(chunk)
    # Final chunk
    final = {
        "id": "chatcmpl-stream",
        "object": "chat.completion.chunk",
        "model": request.model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield json.dumps(final)
    yield "[DONE]"
```

### `app/agent/llm.py` — LLM Client

```python
from collections.abc import AsyncGenerator

import httpx

from app.config import settings


class LLMClient:
    """Calls any OpenAI-compatible local LLM provider (Ollama, LM Studio, vLLM)."""

    def __init__(self):
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model
        self.api_key = settings.llm_api_key

    async def complete(self, messages: list[dict]) -> str:
        """Non-streaming completion. Returns the full response text."""
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Streaming completion. Yields text chunks."""
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": messages, "stream": True},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    import json
                    chunk = json.loads(payload)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
```

### `app/agent/base.py` — Agent Logic

```python
from collections.abc import AsyncGenerator

from app.agent.llm import LLMClient


class BaseAgent:
    """
    Core agent logic, separated from HTTP concerns.

    To create a new agent:
    1. Subclass or instantiate with your system_prompt
    2. Register tools in self.tools (optional)
    3. The routes call run() or run_stream()
    """

    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.llm = LLMClient()

    def _prepare_messages(self, messages: list[dict]) -> list[dict]:
        """Prepend system prompt to the conversation."""
        return [{"role": "system", "content": self.system_prompt}] + messages

    async def run(self, messages: list[dict]) -> str:
        """Non-streaming: returns the full response text."""
        full_messages = self._prepare_messages(messages)
        return await self.llm.complete(full_messages)

    async def run_stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Streaming: yields text chunks."""
        full_messages = self._prepare_messages(messages)
        async for chunk in self.llm.stream(full_messages):
            yield chunk


# --- Instantiate your agent here ---
# Change the system prompt to define your agent's behavior.

agent = BaseAgent(
    system_prompt=(
        "You are a helpful assistant. "
        "Answer questions clearly and concisely."
    ),
)
```

### `app/agent/tools.py` — Tool Definitions (Extension Point)

```python
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class Tool:
    """
    A tool the agent can call via LLM function calling.

    Usage:
        1. Define a tool with its JSON Schema parameters
        2. Register it in the agent
        3. When the LLM returns tool_calls, the agent executes the handler
           and sends the result back in the conversation
    """

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., Awaitable[str]]


# --- Example tool ---
# async def get_weather(city: str) -> str:
#     return f"Weather in {city}: 25C, sunny"
#
# weather_tool = Tool(
#     name="get_weather",
#     description="Get current weather for a city",
#     parameters={
#         "type": "object",
#         "properties": {"city": {"type": "string", "description": "City name"}},
#         "required": ["city"],
#     },
#     handler=get_weather,
# )
```

### `app/utils/logging.py` — Structured Logging

```python
import structlog


def setup_logging(log_level: str = "info"):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()  # switch to JSONRenderer() in prod
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_level_from_name(log_level)
        ),
    )


def get_logger(name: str):
    return structlog.get_logger(name)
```

---

## Dependencies

### `pyproject.toml`

```toml
[project]
name = "agent-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sse-starlette>=2.0",
    "httpx>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]
```

8 production deps. Docker image ~150MB with `python:3.11-slim`.

### `.env.example`

```env
# Server
PORT=4000
HOST=0.0.0.0
LOG_LEVEL=info

# LLM Provider (Ollama)
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.2

# Agent
AGENT_ID=my-agent
AGENT_NAME=My Agent
```

---

## Monitoring — Zero Cost

| Layer | Tool | Cost |
|-------|------|------|
| Logging | `structlog` JSON logs (agent_id, latency_ms, status, tokens) | Free |
| Health | `GET /health` — Docker HEALTHCHECK target | Free |
| Log viewing | `docker logs --follow` | Free |
| **Upgrade path** | Add `opentelemetry-instrumentation-fastapi` then Grafana Cloud free tier (50GB/mo) | Free |

No Prometheus/Grafana stack needed for a single agent service.

---

## Docker

### `Dockerfile`

```dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app/ app/

EXPOSE 4000

HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:4000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4000"]
```

### `docker-compose.yaml`

Includes Ollama + agent. Merge-able into Open WebUI's compose.

```yaml
services:
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    restart: unless-stopped

  my-agent:
    build: .
    ports:
      - "4000:4000"
    environment:
      - LLM_BASE_URL=http://ollama:11434/v1
      - LLM_MODEL=llama3.2
    depends_on:
      - ollama
    restart: unless-stopped

volumes:
  ollama-data:
```

---

## Open WebUI Registration

1. Admin panel -> Settings -> Connections -> Add OpenAI connection
2. URL: `http://my-agent:4000/v1` (Docker network) or `http://localhost:4000/v1`
3. API Key: any non-empty string (e.g. `sk-1234`)
4. The agent appears in the model selector as `my-agent`

---

## Deployment Options

| Option | Cost | Best for |
|--------|------|----------|
| Self-hosted Docker (+ Ollama) | $0 | Production |
| fly.io free tier | $0 (3 VMs, 256MB) | Staging (agent only; Ollama needs GPU) |
| Colocated with Open WebUI | $0 | Simplest — share the same Ollama instance |

Agent is stateless — no database, no persistent volumes needed.
Ollama needs a volume for model weights.

---

## Quick Start

```bash
# 1. Ensure Ollama is running with a model
ollama pull llama3.2

# 2. Install and run
cd agent-backend
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload --port 4000

# 3. Test
curl http://localhost:4000/health
curl http://localhost:4000/v1/models

curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"my-agent","messages":[{"role":"user","content":"hello"}]}'

# 4. Test streaming
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"my-agent","messages":[{"role":"user","content":"hello"}],"stream":true}'

# 5. Docker
docker compose up
```
