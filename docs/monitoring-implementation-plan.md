# Monitoring Implementation Plan for C-Agents / Open WebUI

## Context

The project needs infrastructure monitoring and LLM-specific observability. The codebase already has a full OpenTelemetry integration (`metrics.py`, `setup.py`) with HTTP metrics and user gauges, plus rich analytics APIs for token usage — but **no collector, storage, or visualization layer** is deployed. We need to close that gap with minimal complexity.

---

## Stack Options Analysis

### Option A: OTel Collector + Prometheus + Grafana

| Pros | Cons |
|---|---|
| Fully decoupled — app code unchanged | 3 extra containers (~330 MB RAM) |
| Unified pipeline for traces + metrics + logs | More config files (collector YAML, prom, grafana) |
| Collector can filter/aggregate before storage | Extra network hop (app → collector → prometheus) |
| Industry standard | Overkill for single-node deployment |

### Option B: Direct Prometheus Exporter + Prometheus + Grafana (Recommended)

| Pros | Cons |
|---|---|
| Only 2 extra containers (~180 MB RAM) | App exposes `/metrics` on separate port |
| Simplest data path: app → scrape → query | No pipeline filtering/transformation |
| `opentelemetry-exporter-prometheus` translates OTel → Prometheus automatically | Still need collector later if you want trace forwarding |
| Coexists with existing OTLP push exporter | |
| Fewest moving parts to debug | |

### Option C: Lighter Alternatives

- **VictoriaMetrics + Grafana**: 3-5x less RAM than Prometheus, but less ecosystem support. Good if RAM is critical.
- **Uptime Kuma**: Health/uptime only — cannot store custom time-series metrics. Not suitable.
- **OTel + Jaeger**: Traces only, no metric dashboards. Complementary, not a replacement.

### Recommendation: **Option B**

Two containers instead of three, ~180 MB total, zero disruption to existing OTLP code. The `PrometheusMetricReader` from the OTel SDK handles all format translation automatically. If traces/logs are needed later, add a collector then — the app code won't change.

---

## Metrics We Can Monitor

### Already Implemented (HTTP-level, in `metrics.py`)
- `http.server.requests` — counter by method/route/status
- `http.server.duration` — histogram (ms) by method/route/status
- `webui.users.total` — observable gauge
- `webui.users.active` — observable gauge
- `webui.users.active.today` — observable gauge

### New LLM-Specific Metrics to Add

| Metric | Type | Attributes | Description |
|---|---|---|---|
| `llm.tokens.input` | Counter | `model` | Cumulative input tokens |
| `llm.tokens.output` | Counter | `model` | Cumulative output tokens |
| `llm.request.duration` | Histogram (ms) | `model`, `stream` | End-to-end chat completion latency |
| `llm.request.errors` | Counter | `model`, `error_type` | Failed LLM requests |
| `llm.requests.total` | Counter | `model`, `stream` | Total LLM chat completions |
| `llm.active_chats` | UpDownCounter | — | In-flight chat requests |
| `llm.cost.estimated` | Counter (USD) | `model` | Estimated cost (optional, config-driven) |

### Data Already in DB (queryable via analytics API, not Prometheus)
- Token usage by model/user with date filtering
- Message counts per model/user/chat
- Daily/hourly time-series
- Feedback history (thumbs up/down)

---

## Implementation

### Step 1: Add dependency

**File:** `backend/requirements.txt`

Add `opentelemetry-exporter-prometheus==0.60b1` (matches installed OTel SDK version `1.39.1`).

### Step 2: Add env vars

**File:** `backend/open_webui/env.py`

- `OTEL_METRICS_PROMETHEUS_PORT` (default `9464`) — port for `/metrics` endpoint
- `LLM_COST_CONFIG` (optional JSON) — per-model token pricing for cost estimation

### Step 3: Extend metrics module

**File:** `backend/open_webui/utils/telemetry/metrics.py`

1. Import `PrometheusMetricReader` from `opentelemetry.exporter.prometheus`
2. Add it as a second reader in `_build_meter_provider()` (alongside existing OTLP reader)
3. Add `LLMMetrics` singleton class exposing all 6-7 instruments:
   ```python
   class LLMMetrics:
       _instance = None
       def __new__(cls):
           if cls._instance is None:
               cls._instance = super().__new__(cls)
               meter = metrics.get_meter("open_webui.llm")
               cls._instance.tokens_input = meter.create_counter("llm.tokens.input", unit="tokens")
               cls._instance.tokens_output = meter.create_counter("llm.tokens.output", unit="tokens")
               cls._instance.request_duration = meter.create_histogram("llm.request.duration", unit="ms")
               cls._instance.request_errors = meter.create_counter("llm.request.errors")
               cls._instance.requests_total = meter.create_counter("llm.requests.total")
               cls._instance.active_chats = meter.create_up_down_counter("llm.active_chats")
           return cls._instance
   ```
4. Add `View` entries for new instruments to limit cardinality

### Step 4: Instrument the middleware

**File:** `backend/open_webui/utils/middleware.py`

All chat completions flow through two handlers:
- `streaming_chat_response_handler` (~line 3039)
- `non_streaming_chat_response_handler` (~line 2908)

At each handler:
- **Entry:** `start_time = time.perf_counter()`, increment `requests_total` + `active_chats`
- **Usage captured:** where `normalize_usage()` is called → record `tokens_input`, `tokens_output`
- **Done/exit:** record `request_duration`, decrement `active_chats`
- **Error blocks:** increment `request_errors` with `error_type` attribute

All instrumentation guarded by `if ENABLE_OTEL_METRICS:`.

### Step 5: Create monitoring config files

```
monitoring/
├── prometheus.yml                          # Scrape config (targets: open-webui:9464)
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── prometheus.yml              # Auto-provision Prometheus datasource
    │   └── dashboards/
    │       └── dashboards.yml              # Point to /var/lib/grafana/dashboards
    └── dashboards/
        └── open-webui.json                 # Pre-built dashboard
```

**Prometheus config** (`monitoring/prometheus.yml`):
```yaml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'open-webui'
    static_configs:
      - targets: ['open-webui:9464']
```

**Grafana datasource provisioning** (`monitoring/grafana/provisioning/datasources/prometheus.yml`):
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

**Grafana dashboard provisioning** (`monitoring/grafana/provisioning/dashboards/dashboards.yml`):
```yaml
apiVersion: 1
providers:
  - name: 'default'
    orgId: 1
    folder: 'C-Agents'
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

### Step 6: Update Docker Compose

**File:** `docker-compose.prod.yaml`

Add to existing `open-webui` service environment:
```yaml
- ENABLE_OTEL=true
- ENABLE_OTEL_METRICS=true
- OTEL_METRICS_PROMETHEUS_PORT=9464
```

Add new services:
```yaml
prometheus:
  image: prom/prometheus:v3.2.1
  container_name: prometheus
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    - prometheus-data:/prometheus
  ports:
    - "9090:9090"
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.retention.time=30d'
    - '--storage.tsdb.retention.size=1GB'
  restart: unless-stopped

grafana:
  image: grafana/grafana-oss:11.5.2
  container_name: grafana
  volumes:
    - grafana-data:/var/lib/grafana
    - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
    - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro
  ports:
    - "3001:3000"
  environment:
    - GF_SECURITY_ADMIN_USER=admin
    - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
    - GF_USERS_ALLOW_SIGN_UP=false
  restart: unless-stopped
```

Add volumes:
```yaml
volumes:
  open-webui-data: {}
  prometheus-data: {}
  grafana-data: {}
```

### Step 7: Pre-built Grafana Dashboard

**File:** `monitoring/grafana/dashboards/open-webui.json`

| Row | Panel | Type | PromQL |
|---|---|---|---|
| 1 | Total LLM Requests | Stat | `sum(llm_requests_total)` |
| 1 | Active Chats | Gauge | `llm_active_chats` |
| 1 | Tokens (24h) | Stat | `sum(increase(llm_tokens_input_total[24h])) + sum(increase(llm_tokens_output_total[24h]))` |
| 1 | Active Users | Stat | `webui_users_active_today` |
| 2 | Request Rate by Model | Time series | `sum(rate(llm_requests_total[5m])) by (model)` |
| 2 | P95 Latency by Model | Time series | `histogram_quantile(0.95, sum(rate(llm_request_duration_bucket[5m])) by (le, model))` |
| 3 | Token Usage by Model | Stacked bar | `sum(increase(llm_tokens_input_total[1h])) by (model)` |
| 3 | Input vs Output Tokens | Pie chart | `sum(llm_tokens_input_total)` vs `sum(llm_tokens_output_total)` |
| 4 | Error Rate | Time series | `sum(rate(llm_request_errors_total[5m])) by (model, error_type)` |
| 4 | HTTP Request Rate | Time series | `sum(rate(http_server_requests_total[5m])) by (http_route)` |
| 5 | HTTP Latency (P95) | Time series | `histogram_quantile(0.95, sum(rate(http_server_duration_bucket[5m])) by (le, http_route))` |
| 5 | Users (total/active) | Time series | `webui_users_total`, `webui_users_active` |

---

## Files Summary

| Action | File |
|---|---|
| Modify | `backend/requirements.txt` — add `opentelemetry-exporter-prometheus` |
| Modify | `backend/open_webui/env.py` — add `OTEL_METRICS_PROMETHEUS_PORT`, `LLM_COST_CONFIG` |
| Modify | `backend/open_webui/utils/telemetry/metrics.py` — add PrometheusMetricReader + LLMMetrics class |
| Modify | `backend/open_webui/utils/middleware.py` — instrument chat handlers with LLM metrics |
| Modify | `docker-compose.prod.yaml` — add prometheus + grafana services |
| Create | `monitoring/prometheus.yml` |
| Create | `monitoring/grafana/provisioning/datasources/prometheus.yml` |
| Create | `monitoring/grafana/provisioning/dashboards/dashboards.yml` |
| Create | `monitoring/grafana/dashboards/open-webui.json` |

---

## Verification

1. `docker compose -f docker-compose.prod.yaml up --build`
2. Make a few chat requests through the UI
3. Check `http://localhost:9464/metrics` — should see `llm_tokens_input_total`, `llm_requests_total`, etc.
4. Check `http://localhost:9090/targets` — Prometheus should show `open-webui` as UP
5. Open `http://localhost:3001` (admin/admin) — Grafana dashboard should populate with live data
