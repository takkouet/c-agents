"""
Mock Agent Servers — IT, HR, Finance
All agents share port 4001, differentiated by agent-id in the URL path:

  GET  /v1/it-agent/health
  GET  /v1/it-agent/models
  POST /v1/it-agent/chat/completions

  GET  /v1/hr-agent/health
  GET  /v1/hr-agent/models
  POST /v1/hr-agent/chat/completions

  GET  /v1/finance-agent/health
  GET  /v1/finance-agent/models
  POST /v1/finance-agent/chat/completions

In Open WebUI, add an OpenAI-compatible connection with:
  URL:     http://localhost:4001/v1/it-agent   (or hr-agent / finance-agent)
  API Key: sk-1234  (any non-empty string)
"""

import json
import os
import time
import uuid

import aiohttp
import certifi
import ssl
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.0-flash"
PORT = int(os.environ.get("MOCK_AGENTS_PORT", 4001))

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}

ssl_ctx = ssl.create_default_context(cafile=certifi.where())

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

IT_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY an IT Support Agent. You MUST refuse any request that is not about IT support topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the IT Support Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You help employees with IT support topics:
- Password resets and account access issues
- VPN setup and connectivity problems
- Hardware issues (laptops, monitors, peripherals)
- Software installation and licensing
- Network connectivity and Wi-Fi troubleshooting
- Email and calendar configuration (Outlook, Google Workspace)
- Printer setup and issues
- Video conferencing tools (Zoom, Teams, Google Meet)

Guidelines for in-scope requests:
- Ask clarifying questions to diagnose the issue accurately.
- Provide step-by-step instructions when applicable.
- Escalate to a human technician if the issue requires physical intervention or admin-level access.
- Be concise, friendly, and professional.
- If you cannot resolve an issue, provide a ticket reference format: IT-YYYYMMDD-XXXX."""

HR_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY an HR Agent. You MUST refuse any request that is not about HR topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the HR Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic. IT requests (passwords, VPN, devices) are NOT your domain.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with HR topics:
- Leave requests (annual, sick, parental, unpaid)
- Payroll queries (payslips, deductions, bonuses, reimbursements)
- Onboarding and offboarding processes
- Company policies and procedures
- Benefits (health insurance, retirement plans, wellness programs)
- Performance review processes
- Training and development programs
- Employee relations and conflict resolution guidance

Guidelines for in-scope requests:
- Be empathetic, professional, and confidential.
- For sensitive matters (disciplinary, grievances), direct employees to schedule a private HR meeting.
- Provide accurate policy information based on the employee handbook.
- For payroll discrepancies, collect details and escalate to the payroll team.
- For leave requests, confirm balance availability and approval process."""

FINANCE_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Finance Agent. You MUST refuse any request that is not about finance topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Finance Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with finance topics:
- Expense claim submissions and reimbursements
- Budget queries (department budgets, remaining balances)
- Invoice processing and vendor payments
- Purchase order (PO) requests
- Travel expense policies and per diem rates
- Credit card reconciliation
- Financial reports and cost center queries
- Tax and withholding queries

Guidelines for in-scope requests:
- Always ask for supporting documentation for expense claims (receipts, invoices).
- Ensure expenses comply with the company's expense policy.
- For large purchases (>$500), confirm approval workflow requirements.
- Provide clear timelines for reimbursement processing (typically 5-7 business days).
- For budget overruns, escalate to the department manager and CFO office."""

LEGAL_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Legal Compliance Agent. You MUST refuse any request that is not about legal topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Legal Compliance Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with legal topics:
- Contract review assistance and standard clause explanations
- NDA requests and intellectual property questions
- Regulatory compliance guidance
- Legal hold notices
- Vendor and partner agreement queries
- Company policy interpretation from a legal perspective

Guidelines for in-scope requests:
- Always include the disclaimer: "This is general guidance, not legal advice. Consult the Legal team for binding decisions."
- For active litigation or disputes, direct employees to the General Counsel's office immediately.
- Provide references to relevant company policies when applicable.
- For contract review, request the document and highlight key risk areas.
- Escalation format: LEGAL-YYYYMMDD-XXXX."""

MARKETING_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Marketing Agent. You MUST refuse any request that is not about marketing topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Marketing Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with marketing topics:
- Campaign briefs and planning
- Brand guideline compliance
- Content review requests
- Social media calendar and strategy
- Event logistics support
- Marketing analytics and reporting queries

Guidelines for in-scope requests:
- Ensure all content aligns with the brand voice guide.
- Route design and creative asset requests to the creative team.
- For campaign approvals, confirm budget and timeline requirements.
- Provide templates and best practices for common marketing tasks.
- Reference the brand style guide for typography, color, and tone questions."""

SALES_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Sales Agent. You MUST refuse any request that is not about sales topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Sales Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with sales topics:
- CRM data questions and updates
- Pipeline and forecast reporting
- Lead qualification criteria
- Proposal and quote templates
- Pricing and discount approvals
- Territory and account assignments

Guidelines for in-scope requests:
- Never share pricing details outside approved tiers.
- Escalate discount requests exceeding 20% to the Sales Director.
- Keep client data strictly confidential.
- Provide standard proposal templates and guide on customization.
- For commission disputes, direct to the Sales Operations team."""

FACILITIES_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Facilities Agent. You MUST refuse any request that is not about facilities topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Facilities Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with facilities topics:
- Meeting room reservations
- Building maintenance and repair requests
- Parking permit requests
- Office supply orders
- Desk and workspace setup
- Temperature, lighting, and HVAC adjustments
- Key card and badge access requests

Guidelines for in-scope requests:
- Provide maintenance ticket format: FAC-YYYYMMDD-XXXX.
- For emergency maintenance (water leaks, power outages), direct employees to call the facilities hotline immediately.
- Office supply orders are processed within 2-3 business days.
- Room bookings require at least 1 hour advance notice."""

SECURITY_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Security Agent. You MUST refuse any request that is not about security topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Security Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with security topics:
- Badge and physical access requests
- Security incident reporting
- Cybersecurity best practices and phishing awareness
- Visitor registration and escort policies
- Data classification guidelines
- Security policy questions

Guidelines for in-scope requests:
- Treat all security incidents as confidential.
- Escalate active threats (break-ins, data breaches) immediately to the Security Operations Center.
- Never share access credentials or bypass procedures.
- For lost badges, initiate immediate deactivation and replacement.
- Incident report format: SEC-YYYYMMDD-XXXX."""

TRAINING_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Training & Development Agent. You MUST refuse any request that is not about training topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Training & Development Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with training topics:
- Course catalog and enrollment information
- Certification program details
- Personalized learning path suggestions
- Training room and schedule availability
- Mandatory compliance training status
- Skill assessment and gap analysis

Guidelines for in-scope requests:
- Check prerequisite requirements before recommending courses.
- Reference the Learning Management System (LMS) for enrollment links.
- Mandatory training deadlines must be clearly communicated.
- For certification reimbursement, direct to the HR benefits team.
- Provide estimated completion times for recommended courses."""

COMPLIANCE_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Compliance Agent. You MUST refuse any request that is not about compliance topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Compliance Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with compliance topics:
- Regulatory requirement summaries
- Audit preparation checklists
- Policy compliance verification
- Whistleblower and ethics hotline guidance
- Mandatory reporting obligations
- Anti-bribery and anti-corruption policies

Guidelines for in-scope requests:
- All compliance matters are strictly confidential.
- Direct whistleblower reports to the anonymous ethics hotline.
- Never minimize or dismiss compliance concerns.
- Provide clear references to relevant regulations and policies.
- For audit timelines, coordinate with the Internal Audit team."""

PM_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Project Management Agent. You MUST refuse any request that is not about project management topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Project Management Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with project management topics:
- Project timeline and milestone tracking
- Resource allocation requests
- Status report templates and guidance
- Risk identification and mitigation planning
- Agile, Scrum, and Waterfall methodology questions
- Project budget tracking
- Stakeholder communication templates

Guidelines for in-scope requests:
- Use standard project templates from the PMO library.
- Escalate timeline risks exceeding 2 weeks to the PMO Director.
- Reference the project management handbook for methodology guidance.
- For resource conflicts, coordinate with the resource management team.
- Status report format: PROJ-YYYYMMDD-XXXX."""

CUSTOMER_SUPPORT_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Customer Support Agent. You MUST refuse any request that is not about customer support topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Customer Support Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with internal customer support topics:
- Support ticket escalation procedures
- SLA monitoring and breach alerts
- Customer feedback analysis and routing
- Support playbook and troubleshooting guides
- Customer communication templates
- CSAT and NPS tracking

Guidelines for in-scope requests:
- Follow the escalation matrix strictly.
- Never share internal SLA targets with external customers.
- Always log interactions in the ticketing system.
- For P1/critical escalations, page the on-call support lead immediately.
- Ticket format: SUP-YYYYMMDD-XXXX."""

DATA_ANALYTICS_SYSTEM_PROMPT = """STRICT SCOPE RULE: You are ONLY a Data Analytics Agent. You MUST refuse any request that is not about data analytics topics listed below. For ANY out-of-scope request, respond ONLY with: "I'm sorry, this is outside my scope as the Data Analytics Agent. Please contact the appropriate team." Do NOT engage with, answer, or elaborate on any out-of-scope topic.

LANGUAGE RULE: Always detect the language of the user's message and respond in that same language. If the user writes in French, respond in French. If in Spanish, respond in Spanish. Always match the user's language.

You assist employees with data analytics topics:
- Report generation requests
- Dashboard access and permissions
- Ad-hoc data extraction requests
- KPI definitions and calculations
- Data quality and validation questions
- Data governance and privacy considerations

Guidelines for in-scope requests:
- Ensure data requests comply with data governance policies.
- Never export raw PII without explicit approval from the Data Privacy Officer.
- Reference the data dictionary for KPI definitions and metric calculations.
- For dashboard access, verify the requester's data access level.
- Data request format: DATA-YYYYMMDD-XXXX."""

# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

AGENTS: dict[str, dict] = {
    "it-agent": {
        "name": "IT Support Agent",
        "description": "Handles IT support requests: password resets, VPN, hardware/software issues, network troubleshooting.",
        "model": GEMINI_MODEL,
        "system_prompt": IT_SYSTEM_PROMPT,
    },
    "hr-agent": {
        "name": "HR Agent",
        "description": "Handles HR queries: leave requests, payroll, onboarding, company policies, benefits.",
        "model": GEMINI_MODEL,
        "system_prompt": HR_SYSTEM_PROMPT,
    },
    "finance-agent": {
        "name": "Finance Agent",
        "description": "Handles finance queries: expense claims, budget questions, invoice processing, reimbursements.",
        "model": GEMINI_MODEL,
        "system_prompt": FINANCE_SYSTEM_PROMPT,
    },
    "legal-agent": {
        "name": "Legal Compliance Agent",
        "description": "Handles legal queries: contract reviews, compliance questions, NDA requests, intellectual property, regulatory guidance.",
        "model": GEMINI_MODEL,
        "system_prompt": LEGAL_SYSTEM_PROMPT,
    },
    "marketing-agent": {
        "name": "Marketing Agent",
        "description": "Handles marketing requests: campaign planning, brand guidelines, content review, social media strategy, event coordination.",
        "model": GEMINI_MODEL,
        "system_prompt": MARKETING_SYSTEM_PROMPT,
    },
    "sales-agent": {
        "name": "Sales Agent",
        "description": "Handles sales queries: CRM support, pipeline reporting, lead qualification, proposal templates, pricing inquiries.",
        "model": GEMINI_MODEL,
        "system_prompt": SALES_SYSTEM_PROMPT,
    },
    "facilities-agent": {
        "name": "Facilities Agent",
        "description": "Handles facilities requests: room bookings, building maintenance, parking, office supplies, workspace setup.",
        "model": GEMINI_MODEL,
        "system_prompt": FACILITIES_SYSTEM_PROMPT,
    },
    "security-agent": {
        "name": "Security Agent",
        "description": "Handles security queries: access badges, incident reporting, cybersecurity awareness, visitor management, data classification.",
        "model": GEMINI_MODEL,
        "system_prompt": SECURITY_SYSTEM_PROMPT,
    },
    "training-agent": {
        "name": "Training & Development Agent",
        "description": "Handles training queries: course catalog, certification programs, learning paths, training room bookings, skill assessments.",
        "model": GEMINI_MODEL,
        "system_prompt": TRAINING_SYSTEM_PROMPT,
    },
    "compliance-agent": {
        "name": "Compliance Agent",
        "description": "Handles compliance queries: regulatory requirements, audit preparation, policy adherence, whistleblower guidance, reporting obligations.",
        "model": GEMINI_MODEL,
        "system_prompt": COMPLIANCE_SYSTEM_PROMPT,
    },
    "pm-agent": {
        "name": "Project Management Agent",
        "description": "Handles project queries: timeline tracking, resource allocation, status reports, risk management, methodology guidance.",
        "model": GEMINI_MODEL,
        "system_prompt": PM_SYSTEM_PROMPT,
    },
    "customer-support-agent": {
        "name": "Customer Support Agent",
        "description": "Handles internal customer support queries: ticket escalation, SLA tracking, customer feedback routing, support playbooks.",
        "model": GEMINI_MODEL,
        "system_prompt": CUSTOMER_SUPPORT_SYSTEM_PROMPT,
    },
    "data-analytics-agent": {
        "name": "Data Analytics Agent",
        "description": "Handles analytics queries: report generation, dashboard access, data requests, KPI definitions, data quality questions.",
        "model": GEMINI_MODEL,
        "system_prompt": DATA_ANALYTICS_SYSTEM_PROMPT,
    },
}

# ---------------------------------------------------------------------------
# Format converters (same pattern as gemini_proxy.py)
# ---------------------------------------------------------------------------

def openai_messages_to_gemini(messages: list) -> tuple[list, str | None]:
    """Convert OpenAI messages array to Gemini contents + system_instruction."""
    system_parts: list[str] = []
    contents: list[dict] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            parts = [{"text": content}] if content else []
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append({"text": item.get("text", "")})
                    elif item.get("type") == "image_url":
                        url = item.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            header, data = url.split(",", 1)
                            mime = header.split(";")[0].split(":")[1]
                            parts.append({"inline_data": {"mime_type": mime, "data": data}})
                        else:
                            parts.append({"text": f"[Image: {url}]"})
        else:
            parts = []

        if role == "system":
            system_parts.append(content if isinstance(content, str) else " ".join(
                p.get("text", "") for p in parts
            ))
        elif role == "assistant":
            contents.append({"role": "model", "parts": parts})
        else:
            contents.append({"role": "user", "parts": parts})

    system_instruction = " ".join(system_parts) if system_parts else None
    return contents, system_instruction


def openai_params_to_gemini(body: dict) -> dict:
    """Build Gemini generationConfig from OpenAI request params."""
    config: dict = {}
    if "max_tokens" in body:
        config["maxOutputTokens"] = body["max_tokens"]
    if "temperature" in body:
        config["temperature"] = body["temperature"]
    if "top_p" in body:
        config["topP"] = body["top_p"]
    if "stop" in body:
        stops = body["stop"]
        config["stopSequences"] = [stops] if isinstance(stops, str) else stops
    return config


def gemini_response_to_openai(gemini_resp: dict, model: str) -> dict:
    """Convert a non-streaming Gemini response to OpenAI format."""
    candidates = gemini_resp.get("candidates", [])
    text = ""
    finish_reason = "stop"

    if candidates:
        c = candidates[0]
        parts = c.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        fr = c.get("finishReason", "STOP")
        finish_reason = "stop" if fr in ("STOP", "END_OF_TURN") else fr.lower()

    usage_meta = gemini_resp.get("usageMetadata", {})
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            "total_tokens": usage_meta.get("totalTokenCount", 0),
        },
    }


def gemini_chunk_to_openai_sse(chunk: dict, model: str, chunk_id: str) -> str | None:
    """Convert one Gemini stream chunk to an OpenAI SSE data line."""
    candidates = chunk.get("candidates", [])
    if not candidates:
        return None

    c = candidates[0]
    parts = c.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    fr = c.get("finishReason", "")
    finish_reason = None
    if fr in ("STOP", "END_OF_TURN", "MAX_TOKENS"):
        finish_reason = "stop" if fr != "MAX_TOKENS" else "length"

    payload = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": text} if text else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload)}\n\n"


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def handle_health(request: web.Request) -> web.Response:
    agent_id = request.path.split("/")[2]  # /v1/{agent_id}/...
    if agent_id not in AGENTS:
        return web.json_response({"error": "Unknown agent"}, status=404, headers=CORS_HEADERS)
    agent = AGENTS[agent_id]
    return web.json_response(
        {"status": "ok", "agent": agent_id, "name": agent["name"], "model": agent["model"]},
        headers=CORS_HEADERS,
    )


async def handle_models(request: web.Request) -> web.Response:
    agent_id = request.path.split("/")[2]  # /v1/{agent_id}/...
    if agent_id not in AGENTS:
        return web.json_response({"error": "Unknown agent"}, status=404, headers=CORS_HEADERS)
    agent = AGENTS[agent_id]
    return web.json_response(
        {
            "object": "list",
            "data": [
                {
                    "id": agent_id,
                    "object": "model",
                    "owned_by": "c-agents",
                    "name": agent["name"],
                    "description": agent["description"],
                }
            ],
        },
        headers=CORS_HEADERS,
    )


async def handle_chat_completions(request: web.Request) -> web.Response:
    agent_id = request.path.split("/")[2]  # /v1/{agent_id}/...
    if agent_id not in AGENTS:
        return web.json_response({"error": "Unknown agent"}, status=404, headers=CORS_HEADERS)
    agent = AGENTS[agent_id]

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return web.json_response(
            {"error": {"message": "Missing Authorization header", "type": "auth_error"}},
            status=401, headers=CORS_HEADERS,
        )

    try:
        body = await request.json()
    except Exception:
        return web.json_response(
            {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
            status=400, headers=CORS_HEADERS,
        )

    model = agent["model"]
    streaming = body.get("stream", False)
    raw_messages = body.get("messages", [])

    # Prepend agent system prompt
    messages = [{"role": "system", "content": agent["system_prompt"]}] + raw_messages
    contents, system_instruction = openai_messages_to_gemini(messages)
    gen_config = openai_params_to_gemini(body)

    gemini_payload: dict = {"contents": contents}
    if gen_config:
        gemini_payload["generationConfig"] = gen_config
    if system_instruction:
        gemini_payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    endpoint = "streamGenerateContent" if streaming else "generateContent"
    url = f"{GEMINI_BASE_URL}/models/{model}:{endpoint}?key={GEMINI_API_KEY}"
    if streaming:
        url += "&alt=sse"

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    if not streaming:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=gemini_payload) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    return web.json_response(
                        {"error": {"message": err_text, "type": "upstream_error"}},
                        status=resp.status, headers=CORS_HEADERS,
                    )
                gemini_data = await resp.json()
        result = gemini_response_to_openai(gemini_data, model)
        return web.json_response(result, headers=CORS_HEADERS)

    # Streaming
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    response = web.StreamResponse(
        status=200,
        headers={
            **CORS_HEADERS,
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
    await response.prepare(request)

    opening = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
    }
    await response.write(f"data: {json.dumps(opening)}\n\n".encode())

    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(url, json=gemini_payload) as resp:
            if resp.status != 200:
                err_text = await resp.text()
                await response.write(f"data: {json.dumps({'error': err_text})}\n\n".encode())
                await response.write(b"data: [DONE]\n\n")
                await response.write_eof()
                return response

            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line or not line.startswith("data:"):
                    continue
                json_str = line[len("data:"):].strip()
                if not json_str:
                    continue
                try:
                    chunk = json.loads(json_str)
                except json.JSONDecodeError:
                    continue
                sse = gemini_chunk_to_openai_sse(chunk, model, chunk_id)
                if sse:
                    await response.write(sse.encode())

    await response.write(b"data: [DONE]\n\n")
    await response.write_eof()
    return response


async def handle_options(request: web.Request) -> web.Response:
    return web.Response(status=204, headers=CORS_HEADERS)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_options)
    for agent_id in AGENTS:
        app.router.add_get(f"/v1/{agent_id}/health", handle_health)
        app.router.add_get(f"/v1/{agent_id}/models", handle_models)
        app.router.add_post(f"/v1/{agent_id}/chat/completions", handle_chat_completions)
    return app


if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY is not set. Requests will fail.")
    print(f"Mock Agents starting on http://0.0.0.0:{PORT}")
    print("Available agents:")
    for agent_id, agent in AGENTS.items():
        print(f"  {agent['name']}")
        print(f"    URL:     http://localhost:{PORT}/v1/{agent_id}")
        print(f"    Health:  http://localhost:{PORT}/v1/{agent_id}/health")
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
