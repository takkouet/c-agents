# Deployment Guide

This app has three components:

| Component | Description | Port |
|---|---|---|
| **Frontend** | SvelteKit UI (built into backend at build time) | — |
| **Backend** | FastAPI (Open WebUI) | 8080 (internal) |
| **Gemini Proxy** | OpenAI-compatible shim → Google Gemini API | 4000 (internal) |

Two deployment approaches are provided. Choose one.

---

## Prerequisites

- Docker + Docker Compose installed on the server
- A Google Gemini API key

---

## Setup (both approaches)

**1. Copy the example env file and fill in secrets:**

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
GEMINI_API_KEY=your-google-gemini-api-key
WEBUI_SECRET_KEY=$(openssl rand -base64 32)   # run this to generate
```

Optionally change the host port (default `3000`):

```bash
OPEN_WEBUI_PORT=3000
```

---

## Option A — Two containers (recommended for production)

**Services:** `gemini-proxy` + `open-webui` as independent containers.
Open WebUI waits for the proxy to be healthy before starting.

```
┌──────────────────────────────────────────────────────────┐
│  Host                                                    │
│                                                          │
│  ┌─────────────────────┐    ┌──────────────────────────┐ │
│  │   open-webui :8080  │───▶│  gemini-proxy :4000      │ │
│  │  (frontend+backend) │    │  (Docker internal DNS)   │ │
│  └─────────────────────┘    └──────────────────────────┘ │
│            │                                             │
│       port 3000                                          │
└────────────┼─────────────────────────────────────────────┘
             ▼
    http://<server-ip>:3000
```

**Files used:**
- [`Dockerfile`](Dockerfile) — builds Open WebUI (frontend + backend)
- [`Dockerfile.gemini-proxy`](Dockerfile.gemini-proxy) — builds the proxy
- [`docker-compose.prod.yaml`](docker-compose.prod.yaml)

**Commands:**

```bash
# First deploy / after code changes
docker compose -f docker-compose.prod.yaml up -d --build

# Subsequent deploys (no code changes)
docker compose -f docker-compose.prod.yaml up -d

# View logs
docker compose -f docker-compose.prod.yaml logs -f

# Stop
docker compose -f docker-compose.prod.yaml down
```

**When to rebuild** (`--build`):
- After changing `gemini_proxy.py` or `backend/data/meeting_data.py`
- After changing any frontend/backend source files

---

## Option B — Single container (simpler, less isolation)

**Services:** both processes run inside the one Open WebUI container via [`backend/start.prod.sh`](backend/start.prod.sh).

```
┌─────────────────────────────────────────────────────────┐
│  Host                                                   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  open-webui container                            │   │
│  │                                                  │   │
│  │   uvicorn :8080 ──▶ python gemini_proxy.py :4000 │   │
│  │   (open-webui)       (localhost, same container) │   │
│  └──────────────────────────────────────────────────┘   │
│            │                                            │
│       port 3000                                         │
└────────────┼────────────────────────────────────────────┘
             ▼
    http://<server-ip>:3000
```

**Files used:**
- [`Dockerfile`](Dockerfile) — builds Open WebUI (frontend + backend + proxy code)
- [`docker-compose.single.yaml`](docker-compose.single.yaml)
- [`backend/start.prod.sh`](backend/start.prod.sh) — starts proxy then Open WebUI

**Commands:**

```bash
# First deploy / after code changes
docker compose -f docker-compose.single.yaml up -d --build

# Subsequent deploys
docker compose -f docker-compose.single.yaml up -d

# View logs
docker compose -f docker-compose.single.yaml logs -f

# Stop
docker compose -f docker-compose.single.yaml down
```

> **Note:** If the proxy crashes, Open WebUI continues running but AI requests will fail.
> Use Option A if you need independent restarts.

---

## Accessing the app

Once deployed, open a browser and navigate to:

```
http://<server-ip>:<OPEN_WEBUI_PORT>
```

Example with default port: `http://127.0.1.0:3000`

---

## Data persistence

Both options mount a Docker volume at `/app/backend/data` inside the container:

| File | Contents |
|---|---|
| `webui.db` | User accounts, chat history, settings |
| `meeting_booking.db` | Meeting room bookings |
| `vector_db/` | RAG document embeddings |
| `uploads/` | Uploaded files |

Data survives container restarts and rebuilds. To reset all data:

```bash
docker volume rm open-webui-data
```

---

## Comparison

| | Option A (two containers) | Option B (single container) |
|---|---|---|
| Isolation | Each service restarts independently | One crash can affect both |
| Complexity | Two images to build | One image |
| Networking | Docker DNS (`http://gemini-proxy:4000`) | localhost inside container |
| Recommended for | Production | Simple / resource-limited environments |
