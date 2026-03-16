"""
title: Compliance Agent
description: Handles regulatory compliance checking, employee training compliance, audit readiness, incident severity scoring, and policy gap analysis
requirements: aiohttp,certifi
"""

import json
import re
import ssl
import time
import uuid
from datetime import date, datetime, timedelta
from typing import AsyncGenerator, Callable, Optional

import aiohttp
import certifi
from pydantic import BaseModel, Field

_ssl_ctx = ssl.create_default_context(cafile=certifi.where())

# ──────────────────────────────────────────────────────────────────────
# Mock Data
# ──────────────────────────────────────────────────────────────────────

EMPLOYEES_COMPLIANCE = {
    "EMP-001": {
        "name": "Sarah Chen",
        "role": "Marketing Manager",
        "department": "Marketing",
        "data_access_level": "confidential",
        "completed_training": [
            {"module": "Data Privacy Fundamentals", "completed": "2026-01-15", "expires": "2027-01-15"},
            {"module": "Anti-Harassment", "completed": "2025-11-20", "expires": "2026-11-20"},
        ],
        "pending_training": [
            {"module": "GDPR Compliance", "due": "2026-03-01", "status": "overdue"},
            {"module": "Social Media Policy", "due": "2026-04-15", "status": "pending"},
        ],
        "certifications": [],
        "policy_acknowledgements": ["IT Security Policy v3.2", "Data Classification Policy v2.1"],
    },
    "EMP-002": {
        "name": "James Rivera",
        "role": "Software Engineer",
        "department": "Engineering",
        "data_access_level": "restricted",
        "completed_training": [
            {"module": "Secure Coding Practices", "completed": "2026-02-10", "expires": "2027-02-10"},
            {"module": "Data Privacy Fundamentals", "completed": "2025-12-05", "expires": "2026-12-05"},
            {"module": "Anti-Harassment", "completed": "2025-10-15", "expires": "2026-10-15"},
        ],
        "pending_training": [],
        "certifications": [
            {"name": "Security Awareness Certification", "obtained": "2025-08-01", "expires": "2026-08-01"},
        ],
        "policy_acknowledgements": ["IT Security Policy v3.2", "Code of Conduct v5.0", "Source Code Policy v2.0"],
    },
    "EMP-003": {
        "name": "Lisa Park",
        "role": "Data Architect",
        "department": "Engineering",
        "data_access_level": "restricted",
        "completed_training": [
            {"module": "Secure Coding Practices", "completed": "2025-09-20", "expires": "2026-09-20"},
            {"module": "Data Privacy Fundamentals", "completed": "2026-01-10", "expires": "2027-01-10"},
        ],
        "pending_training": [
            {"module": "Anti-Harassment", "due": "2026-02-28", "status": "overdue"},
        ],
        "certifications": [
            {"name": "Security Awareness Certification", "obtained": "2025-06-15", "expires": "2026-06-15"},
        ],
        "policy_acknowledgements": ["IT Security Policy v3.2", "Source Code Policy v2.0"],
    },
    "EMP-004": {
        "name": "Ahmed Hassan",
        "role": "Security Lead",
        "department": "IT",
        "data_access_level": "top_secret",
        "completed_training": [
            {"module": "Secure Coding Practices", "completed": "2026-01-20", "expires": "2027-01-20"},
            {"module": "Data Privacy Fundamentals", "completed": "2026-01-20", "expires": "2027-01-20"},
            {"module": "Anti-Harassment", "completed": "2026-01-05", "expires": "2027-01-05"},
            {"module": "Incident Response Procedures", "completed": "2026-02-01", "expires": "2027-02-01"},
        ],
        "pending_training": [],
        "certifications": [
            {"name": "Security Awareness Certification", "obtained": "2026-01-10", "expires": "2027-01-10"},
            {"name": "CISSP", "obtained": "2024-05-01", "expires": "2027-05-01"},
        ],
        "policy_acknowledgements": [
            "IT Security Policy v3.2",
            "Code of Conduct v5.0",
            "Data Classification Policy v2.1",
            "Incident Response Policy v1.0",
        ],
    },
    "EMP-005": {
        "name": "David Kim",
        "role": "Business Analyst",
        "department": "Sales",
        "data_access_level": "confidential",
        "completed_training": [
            {"module": "Data Privacy Fundamentals", "completed": "2025-08-15", "expires": "2026-08-15"},
        ],
        "pending_training": [
            {"module": "Anti-Harassment", "due": "2026-01-31", "status": "overdue"},
            {"module": "CRM Data Handling", "due": "2026-03-15", "status": "pending"},
        ],
        "certifications": [],
        "policy_acknowledgements": ["IT Security Policy v3.2"],
    },
    "EMP-006": {
        "name": "Maria Santos",
        "role": "Operations Manager",
        "department": "Operations",
        "data_access_level": "internal",
        "completed_training": [
            {"module": "Data Privacy Fundamentals", "completed": "2025-11-01", "expires": "2026-11-01"},
            {"module": "Anti-Harassment", "completed": "2026-02-15", "expires": "2027-02-15"},
        ],
        "pending_training": [
            {"module": "Workplace Safety", "due": "2026-04-01", "status": "pending"},
        ],
        "certifications": [],
        "policy_acknowledgements": ["IT Security Policy v3.2", "Code of Conduct v5.0"],
    },
    "EMP-007": {
        "name": "Priya Patel",
        "role": "UX Designer",
        "department": "Product",
        "data_access_level": "internal",
        "completed_training": [
            {"module": "Data Privacy Fundamentals", "completed": "2026-02-20", "expires": "2027-02-20"},
            {"module": "Anti-Harassment", "completed": "2025-12-10", "expires": "2026-12-10"},
        ],
        "pending_training": [],
        "certifications": [],
        "policy_acknowledgements": ["IT Security Policy v3.2", "Code of Conduct v5.0"],
    },
    "EMP-008": {
        "name": "Tom Zhang",
        "role": "Software Engineer",
        "department": "Engineering",
        "data_access_level": "restricted",
        "completed_training": [
            {"module": "Secure Coding Practices", "completed": "2025-07-01", "expires": "2026-07-01"},
            {"module": "Data Privacy Fundamentals", "completed": "2025-06-15", "expires": "2026-06-15"},
        ],
        "pending_training": [
            {"module": "Anti-Harassment", "due": "2026-03-30", "status": "pending"},
        ],
        "certifications": [],
        "policy_acknowledgements": ["IT Security Policy v3.2", "Code of Conduct v5.0"],
    },
}

ROLE_REQUIREMENTS = {
    "Marketing Manager": {
        "required_training": ["Data Privacy Fundamentals", "GDPR Compliance", "Anti-Harassment", "Social Media Policy"],
        "required_certifications": [],
        "required_acknowledgements": ["IT Security Policy v3.2", "Data Classification Policy v2.1", "Acceptable Use Policy v4.0"],
    },
    "Software Engineer": {
        "required_training": ["Secure Coding Practices", "Data Privacy Fundamentals", "Anti-Harassment"],
        "required_certifications": ["Security Awareness Certification"],
        "required_acknowledgements": ["IT Security Policy v3.2", "Code of Conduct v5.0", "Source Code Policy v2.0"],
    },
    "Data Architect": {
        "required_training": ["Secure Coding Practices", "Data Privacy Fundamentals", "Anti-Harassment"],
        "required_certifications": ["Security Awareness Certification"],
        "required_acknowledgements": ["IT Security Policy v3.2", "Code of Conduct v5.0", "Source Code Policy v2.0"],
    },
    "Security Lead": {
        "required_training": [
            "Secure Coding Practices",
            "Data Privacy Fundamentals",
            "Anti-Harassment",
            "Incident Response Procedures",
        ],
        "required_certifications": ["Security Awareness Certification"],
        "required_acknowledgements": [
            "IT Security Policy v3.2",
            "Code of Conduct v5.0",
            "Data Classification Policy v2.1",
            "Incident Response Policy v1.0",
        ],
    },
    "Business Analyst": {
        "required_training": ["Data Privacy Fundamentals", "Anti-Harassment", "CRM Data Handling"],
        "required_certifications": [],
        "required_acknowledgements": ["IT Security Policy v3.2", "Code of Conduct v5.0"],
    },
    "Operations Manager": {
        "required_training": ["Data Privacy Fundamentals", "Anti-Harassment", "Workplace Safety"],
        "required_certifications": [],
        "required_acknowledgements": ["IT Security Policy v3.2", "Code of Conduct v5.0"],
    },
    "UX Designer": {
        "required_training": ["Data Privacy Fundamentals", "Anti-Harassment"],
        "required_certifications": [],
        "required_acknowledgements": ["IT Security Policy v3.2", "Code of Conduct v5.0"],
    },
}

REGULATIONS = {
    "GDPR": {
        "full_name": "General Data Protection Regulation",
        "applies_when": ["personal_data", "eu_citizens", "data_processing", "customer_data", "gdpr", "european", "eu"],
        "requirements": [
            {"id": "GDPR-1", "title": "Lawful Basis for Processing", "status": "compliant"},
            {"id": "GDPR-2", "title": "Data Protection Impact Assessment", "status": "partial"},
            {"id": "GDPR-3", "title": "Right to Erasure Procedures", "status": "non_compliant"},
            {"id": "GDPR-4", "title": "Data Breach Notification (72h)", "status": "compliant"},
            {"id": "GDPR-5", "title": "Data Protection Officer Appointed", "status": "compliant"},
            {"id": "GDPR-6", "title": "Consent Management", "status": "partial"},
        ],
    },
    "PCI-DSS": {
        "full_name": "Payment Card Industry Data Security Standard",
        "applies_when": ["credit_card", "payment", "cardholder", "transaction", "pci", "card_data"],
        "requirements": [
            {"id": "PCI-1", "title": "Install and maintain firewall", "status": "compliant"},
            {"id": "PCI-2", "title": "Encrypt cardholder data", "status": "compliant"},
            {"id": "PCI-3", "title": "Restrict access to cardholder data", "status": "partial"},
            {"id": "PCI-4", "title": "Regular security testing", "status": "non_compliant"},
            {"id": "PCI-5", "title": "Maintain vulnerability management", "status": "partial"},
        ],
    },
    "SOX": {
        "full_name": "Sarbanes-Oxley Act",
        "applies_when": ["financial_reporting", "audit", "sox", "accounting", "internal_controls", "financial_statements"],
        "requirements": [
            {"id": "SOX-1", "title": "Internal Controls over Financial Reporting", "status": "compliant"},
            {"id": "SOX-2", "title": "Management Assessment of Controls", "status": "compliant"},
            {"id": "SOX-3", "title": "External Auditor Attestation", "status": "partial"},
            {"id": "SOX-4", "title": "Whistleblower Protection", "status": "compliant"},
        ],
    },
    "HIPAA": {
        "full_name": "Health Insurance Portability and Accountability Act",
        "applies_when": ["health", "medical", "patient", "hipaa", "phi", "healthcare", "health_data"],
        "requirements": [
            {"id": "HIPAA-1", "title": "Privacy Rule Compliance", "status": "partial"},
            {"id": "HIPAA-2", "title": "Security Rule (Administrative)", "status": "compliant"},
            {"id": "HIPAA-3", "title": "Security Rule (Physical)", "status": "compliant"},
            {"id": "HIPAA-4", "title": "Security Rule (Technical)", "status": "partial"},
            {"id": "HIPAA-5", "title": "Breach Notification Rule", "status": "compliant"},
        ],
    },
}

DEPARTMENT_AUDIT_STATUS = {
    "Engineering": {
        "document_retention": {"score": 85, "status": "green"},
        "training_compliance": {"score": 72, "status": "amber"},
        "access_controls": {"score": 91, "status": "green"},
        "process_documentation": {"score": 68, "status": "amber"},
    },
    "IT": {
        "document_retention": {"score": 92, "status": "green"},
        "training_compliance": {"score": 95, "status": "green"},
        "access_controls": {"score": 88, "status": "green"},
        "process_documentation": {"score": 82, "status": "green"},
    },
    "Marketing": {
        "document_retention": {"score": 65, "status": "amber"},
        "training_compliance": {"score": 55, "status": "red"},
        "access_controls": {"score": 70, "status": "amber"},
        "process_documentation": {"score": 60, "status": "red"},
    },
    "Sales": {
        "document_retention": {"score": 72, "status": "amber"},
        "training_compliance": {"score": 48, "status": "red"},
        "access_controls": {"score": 75, "status": "amber"},
        "process_documentation": {"score": 70, "status": "amber"},
    },
    "Finance": {
        "document_retention": {"score": 95, "status": "green"},
        "training_compliance": {"score": 90, "status": "green"},
        "access_controls": {"score": 93, "status": "green"},
        "process_documentation": {"score": 88, "status": "green"},
    },
    "Operations": {
        "document_retention": {"score": 78, "status": "amber"},
        "training_compliance": {"score": 80, "status": "green"},
        "access_controls": {"score": 74, "status": "amber"},
        "process_documentation": {"score": 72, "status": "amber"},
    },
}

ORGANIZATIONAL_POLICIES = {
    "IT Security Policy v3.2": {
        "regulation_coverage": ["GDPR-1", "PCI-1", "PCI-2", "HIPAA-3"],
        "last_updated": "2025-09-15",
    },
    "Data Classification Policy v2.1": {
        "regulation_coverage": ["GDPR-2", "PCI-3", "HIPAA-1"],
        "last_updated": "2025-06-01",
    },
    "Incident Response Policy v1.0": {
        "regulation_coverage": ["GDPR-4", "HIPAA-5"],
        "last_updated": "2025-03-20",
    },
    "Code of Conduct v5.0": {
        "regulation_coverage": ["SOX-4"],
        "last_updated": "2025-01-10",
    },
    "Acceptable Use Policy v4.0": {
        "regulation_coverage": ["PCI-5"],
        "last_updated": "2024-11-01",
    },
    "Source Code Policy v2.0": {
        "regulation_coverage": [],
        "last_updated": "2025-07-15",
    },
}

# ──────────────────────────────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are the Compliance Agent for C-Agents, an enterprise AI assistant specializing \
in regulatory compliance, internal audit, and policy management.

Your expertise includes:
- Employee compliance tracking (training, certifications, policy acknowledgements)
- Regulatory requirement analysis (GDPR, PCI-DSS, SOX, HIPAA)
- Audit readiness assessment and gap analysis
- Incident severity scoring and escalation guidance
- Policy-to-regulation mapping and gap identification

When reporting compliance status:
- Use exact dates for expirations and deadlines
- Flag overdue items prominently with the number of days overdue
- Calculate compliance scores as: (completed / total) × 100
- For audit readiness, use weighted category scores (each 25%)

Risk levels for incident scoring:
- Critical (80–100): Immediate C-suite notification, regulatory filing within 24h
- High (60–79): VP notification, incident response team activation
- Medium (40–59): Director notification, remediation plan within 48h
- Low (0–39): Manager notification, standard remediation

Use the [DATA] section for precise numbers. Lead with the most urgent items. \
Be specific about required actions and deadlines.\
"""


# ──────────────────────────────────────────────────────────────────────
# Pipe
# ──────────────────────────────────────────────────────────────────────


class Pipe:
    class Valves(BaseModel):
        OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", description="Ollama base URL")
        MODEL: str = Field(default="phi4-mini", description="Ollama model")
        OVERDUE_GRACE_DAYS: int = Field(default=0, description="Days past due before flagging")

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        return [{"id": "compliance-agent", "name": "Compliance Agent"}]

    # ── helpers ──────────────────────────────────────────────────────

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

    async def _call_ollama(self, messages: list[dict]) -> dict:
        url = f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions"
        payload = {"model": self.valves.MODEL, "messages": messages, "stream": False}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status != 200:
                        return self._empty_response(self.valves.MODEL)
                    return await resp.json()
        except Exception as e:
            print(f"[compliance-agent] LLM error: {e!r}", flush=True)
            return self._empty_response(self.valves.MODEL)

    async def _stream_ollama(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        url = f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions"
        payload = {"model": self.valves.MODEL, "messages": messages, "stream": True}
        session = aiohttp.ClientSession()
        try:
            resp = await session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=300))
            if resp.status != 200:
                yield f"Error contacting LLM (status {resp.status})"
                return
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                if line == "data: [DONE]":
                    break
                if line.startswith("data: "):
                    yield line
        finally:
            await session.close()

    # ── business logic ──────────────────────────────────────────────

    def _today(self) -> date:
        return date.today()

    def _find_employee(self, query: str) -> tuple[str | None, dict | None]:
        """Find employee by name or ID."""
        q = query.lower()
        for eid, emp in EMPLOYEES_COMPLIANCE.items():
            if eid.lower() in q or emp["name"].lower() in q:
                return eid, emp
        return None, None

    def _check_employee_compliance(self, query: str) -> str:
        """Cross-reference employee status against role requirements."""
        eid, emp = self._find_employee(query)
        if not emp:
            return "No matching employee. Available: " + ", ".join(
                f"{eid} ({e['name']})" for eid, e in EMPLOYEES_COMPLIANCE.items()
            )

        reqs = ROLE_REQUIREMENTS.get(emp["role"], {})
        today = self._today()

        # Training check
        req_training = reqs.get("required_training", [])
        completed_names = {t["module"] for t in emp["completed_training"]}
        training_lines = []
        completed_count = 0
        for mod in req_training:
            if mod in completed_names:
                t = next(t for t in emp["completed_training"] if t["module"] == mod)
                exp = datetime.strptime(t["expires"], "%Y-%m-%d").date()
                days_to_exp = (exp - today).days
                if days_to_exp < 0:
                    training_lines.append(f"  ✗ {mod}: EXPIRED {abs(days_to_exp)} days ago")
                elif days_to_exp < 30:
                    training_lines.append(f"  ⚠ {mod}: Expiring in {days_to_exp} days ({t['expires']})")
                    completed_count += 1
                else:
                    training_lines.append(f"  ✓ {mod}: Valid until {t['expires']}")
                    completed_count += 1
            else:
                # Check pending
                pending = next((p for p in emp["pending_training"] if p["module"] == mod), None)
                if pending and pending["status"] == "overdue":
                    due = datetime.strptime(pending["due"], "%Y-%m-%d").date()
                    days_overdue = (today - due).days - self.valves.OVERDUE_GRACE_DAYS
                    training_lines.append(f"  ✗ {mod}: OVERDUE by {days_overdue} days (was due {pending['due']})")
                elif pending:
                    training_lines.append(f"  ○ {mod}: Pending (due {pending['due']})")
                else:
                    training_lines.append(f"  ✗ {mod}: NOT STARTED")

        # Certification check
        req_certs = reqs.get("required_certifications", [])
        cert_names = {c["name"] for c in emp["certifications"]}
        cert_lines = []
        cert_count = 0
        for cert in req_certs:
            if cert in cert_names:
                c = next(c for c in emp["certifications"] if c["name"] == cert)
                exp = datetime.strptime(c["expires"], "%Y-%m-%d").date()
                days_to_exp = (exp - today).days
                if days_to_exp < 0:
                    cert_lines.append(f"  ✗ {cert}: EXPIRED {abs(days_to_exp)} days ago")
                else:
                    cert_lines.append(f"  ✓ {cert}: Valid until {c['expires']}")
                    cert_count += 1
            else:
                cert_lines.append(f"  ✗ {cert}: MISSING")

        # Policy acknowledgements check
        req_acks = reqs.get("required_acknowledgements", [])
        ack_set = set(emp["policy_acknowledgements"])
        ack_lines = []
        ack_count = 0
        for policy in req_acks:
            if policy in ack_set:
                ack_lines.append(f"  ✓ {policy}: Acknowledged")
                ack_count += 1
            else:
                ack_lines.append(f"  ✗ {policy}: NOT ACKNOWLEDGED")

        # Overall score
        total_reqs = len(req_training) + len(req_certs) + len(req_acks)
        total_met = completed_count + cert_count + ack_count
        score = (total_met / total_reqs * 100) if total_reqs else 100

        return (
            f"Compliance Report: {emp['name']} ({eid})\n"
            f"  Role: {emp['role']} | Dept: {emp['department']}\n"
            f"  Data access level: {emp['data_access_level']}\n"
            f"  Compliance Score: {score:.0f}% ({total_met}/{total_reqs} requirements met)\n\n"
            f"  Training ({completed_count}/{len(req_training)}):\n" + "\n".join(training_lines) + "\n\n"
            f"  Certifications ({cert_count}/{len(req_certs)}):\n"
            + ("\n".join(cert_lines) if cert_lines else "    None required") + "\n\n"
            f"  Policy Acknowledgements ({ack_count}/{len(req_acks)}):\n" + "\n".join(ack_lines)
        )

    def _identify_regulations(self, query: str) -> str:
        """Match scenario keywords against regulation database."""
        q = query.lower().replace("-", "_").replace(" ", "_")
        words = set(re.findall(r"\w+", q))
        applicable = []

        for reg_id, reg in REGULATIONS.items():
            overlap = words & set(reg["applies_when"])
            if overlap or reg_id.lower() in q:
                compliant = sum(1 for r in reg["requirements"] if r["status"] == "compliant")
                partial = sum(1 for r in reg["requirements"] if r["status"] == "partial")
                non_comp = sum(1 for r in reg["requirements"] if r["status"] == "non_compliant")
                total = len(reg["requirements"])
                readiness = ((compliant + partial * 0.5) / total * 100) if total else 0

                req_lines = "\n".join(
                    f"    [{r['status'].upper()}] {r['id']}: {r['title']}"
                    for r in reg["requirements"]
                )
                applicable.append(
                    f"{reg_id} — {reg['full_name']}\n"
                    f"  Matched keywords: {', '.join(overlap) if overlap else reg_id}\n"
                    f"  Readiness: {readiness:.0f}% ({compliant} compliant, {partial} partial, {non_comp} non-compliant)\n"
                    f"  Requirements:\n{req_lines}"
                )

        if not applicable:
            return "No matching regulations identified. Supported: GDPR, PCI-DSS, SOX, HIPAA."
        return "Applicable Regulations:\n\n" + "\n\n".join(applicable)

    def _audit_readiness(self, query: str) -> str:
        """Audit readiness assessment for a department."""
        q = query.lower()
        dept = None
        for d in DEPARTMENT_AUDIT_STATUS:
            if d.lower() in q:
                dept = d
                break
        if not dept:
            # Show all departments
            lines = []
            for d, cats in DEPARTMENT_AUDIT_STATUS.items():
                avg = sum(c["score"] for c in cats.values()) / len(cats)
                rag = "GREEN" if avg >= 80 else "AMBER" if avg >= 60 else "RED"
                lines.append(f"  {d}: {avg:.0f}% [{rag}]")
            return "Audit Readiness — All Departments:\n" + "\n".join(lines)

        cats = DEPARTMENT_AUDIT_STATUS[dept]
        weighted_total = sum(c["score"] * 0.25 for c in cats.values())
        overall_rag = "GREEN" if weighted_total >= 80 else "AMBER" if weighted_total >= 60 else "RED"

        cat_lines = "\n".join(
            f"  {name.replace('_', ' ').title()} (25%): {c['score']}/100 [{c['status'].upper()}]"
            for name, c in cats.items()
        )

        return (
            f"Audit Readiness: {dept}\n"
            f"  Overall Score: {weighted_total:.0f}/100 [{overall_rag}]\n\n"
            f"  Categories:\n{cat_lines}"
        )

    def _score_incident(self, query: str) -> str:
        """Calculate incident severity score from description."""
        q = query.lower()

        # Data sensitivity (30%)
        if any(w in q for w in ["ssn", "social security", "passport", "government_id"]):
            sensitivity = 100
            sensitivity_label = "Highly Sensitive PII (SSN/passport)"
        elif any(w in q for w in ["credit card", "bank account", "financial", "payment"]):
            sensitivity = 90
            sensitivity_label = "Financial data"
        elif any(w in q for w in ["medical", "health", "patient", "phi"]):
            sensitivity = 85
            sensitivity_label = "Protected Health Information"
        elif any(w in q for w in ["pii", "personal", "email", "address", "phone"]):
            sensitivity = 70
            sensitivity_label = "Personal Identifiable Information"
        elif any(w in q for w in ["internal", "confidential", "proprietary"]):
            sensitivity = 40
            sensitivity_label = "Internal/Confidential"
        else:
            sensitivity = 20
            sensitivity_label = "General/Public"

        # Record count (25%)
        nums = re.findall(r"([\d,]+)\s*(?:record|user|employee|customer|account|row|entry|file)", q)
        if nums:
            count = int(nums[0].replace(",", ""))
            if count >= 100000:
                records_score = 100
            elif count >= 10000:
                records_score = 85
            elif count >= 1000:
                records_score = 65
            elif count >= 100:
                records_score = 40
            else:
                records_score = 20
            records_label = f"{count:,} records"
        else:
            records_score = 50
            records_label = "Unknown record count (assumed moderate)"

        # External exposure (20%)
        if any(w in q for w in ["public", "internet", "s3 bucket", "exposed", "open access", "leaked"]):
            exposure = 100
            exposure_label = "Publicly accessible"
        elif any(w in q for w in ["third party", "vendor", "partner", "shared"]):
            exposure = 70
            exposure_label = "Third-party exposure"
        elif any(w in q for w in ["internal", "employee only", "intranet"]):
            exposure = 30
            exposure_label = "Internal only"
        else:
            exposure = 50
            exposure_label = "Unknown exposure scope"

        # Duration factor — affects exposure score
        duration_match = re.search(r"(\d+)\s*(day|week|month|hour|year)", q)
        if duration_match:
            amt = int(duration_match.group(1))
            unit = duration_match.group(2)
            if unit.startswith("week"):
                amt *= 7
            elif unit.startswith("month"):
                amt *= 30
            elif unit.startswith("year"):
                amt *= 365
            elif unit.startswith("hour"):
                amt = max(1, amt // 24)
            if amt > 30:
                exposure = min(100, exposure + 15)
            elif amt > 7:
                exposure = min(100, exposure + 10)

        # Regulatory impact (15%)
        reg_impact = 0
        matched_regs = []
        for reg_id, reg in REGULATIONS.items():
            if any(kw in q for kw in reg["applies_when"]):
                matched_regs.append(reg_id)
                reg_impact = max(reg_impact, 80)
        if not matched_regs:
            # Infer from data type
            if sensitivity >= 70:
                reg_impact = 60
                matched_regs = ["Likely applicable (PII detected)"]
            else:
                reg_impact = 20
        reg_label = ", ".join(matched_regs) if matched_regs else "None identified"

        # Remediation status (10%)
        if any(w in q for w in ["fixed", "remediated", "resolved", "patched", "contained"]):
            remediation = 10
            rem_label = "Remediated"
        elif any(w in q for w in ["in progress", "investigating", "working on"]):
            remediation = 40
            rem_label = "In progress"
        else:
            remediation = 80
            rem_label = "Not remediated"

        # Final score
        total = (
            sensitivity * 0.30
            + records_score * 0.25
            + exposure * 0.20
            + reg_impact * 0.15
            + remediation * 0.10
        )

        if total >= 80:
            level = "CRITICAL"
            action = "Immediate C-suite notification. Begin regulatory breach notification within 72 hours. Activate incident response team NOW."
        elif total >= 60:
            level = "HIGH"
            action = "Notify VP and Legal immediately. Activate incident response team. Begin containment within 4 hours."
        elif total >= 40:
            level = "MEDIUM"
            action = "Notify Director. Create remediation plan within 48 hours. Document for audit trail."
        else:
            level = "LOW"
            action = "Notify Manager. Standard remediation process. Log in incident register."

        return (
            f"Incident Severity Assessment\n"
            f"  Overall Score: {total:.0f}/100 — {level}\n\n"
            f"  Breakdown:\n"
            f"    Data sensitivity (30%): {sensitivity}/100 — {sensitivity_label}\n"
            f"    Record count (25%): {records_score}/100 — {records_label}\n"
            f"    External exposure (20%): {exposure}/100 — {exposure_label}\n"
            f"    Regulatory impact (15%): {reg_impact}/100 — {reg_label}\n"
            f"    Remediation status (10%): {remediation}/100 — {rem_label}\n\n"
            f"  Recommended Action:\n    {action}"
        )

    def _policy_gaps(self, query: str) -> str:
        """Find policy gaps for a specific regulation."""
        q = query.lower()
        reg = None
        for rid, r in REGULATIONS.items():
            if rid.lower() in q or r["full_name"].lower() in q:
                reg = (rid, r)
                break
        if not reg:
            return "Specify a regulation to check gaps: GDPR, PCI-DSS, SOX, HIPAA."

        rid, r = reg
        # Build coverage map
        all_req_ids = {req["id"] for req in r["requirements"]}
        covered = {}
        for policy_name, policy in ORGANIZATIONAL_POLICIES.items():
            for cov_id in policy["regulation_coverage"]:
                if cov_id in all_req_ids:
                    covered[cov_id] = (policy_name, policy["last_updated"])

        lines = []
        for req in r["requirements"]:
            if req["id"] in covered:
                pname, updated = covered[req["id"]]
                age = (self._today() - datetime.strptime(updated, "%Y-%m-%d").date()).days
                stale = " ⚠ OUTDATED (>365 days)" if age > 365 else ""
                lines.append(f"  ✓ {req['id']}: {req['title']}\n    Covered by: {pname} (updated {updated}){stale}")
            else:
                lines.append(f"  ✗ {req['id']}: {req['title']}\n    NO POLICY COVERAGE — gap identified")

        gaps = sum(1 for req in r["requirements"] if req["id"] not in covered)
        return (
            f"Policy Gap Analysis: {rid} ({r['full_name']})\n"
            f"  Requirements covered: {len(covered)}/{len(all_req_ids)}\n"
            f"  Gaps identified: {gaps}\n\n"
            + "\n".join(lines)
        )

    def _analyze_and_gather(self, user_message: str) -> str:
        """Determine intent and gather data."""
        msg = user_message.lower()

        # Employee compliance
        _, emp = self._find_employee(user_message)
        if emp:
            return self._check_employee_compliance(user_message)

        # Incident scoring — look for incident-related keywords
        if any(w in msg for w in [
            "incident", "breach", "leak", "exposed", "compromised", "unauthorized",
            "vulnerability", "attack", "records exposed", "data loss",
        ]):
            return self._score_incident(user_message)

        # Regulation check
        if any(w in msg for w in ["regulation", "regulatory", "comply", "compliance requirement", "what regulations", "what do we need"]):
            return self._identify_regulations(user_message)

        # Specific regulation name
        for rid in REGULATIONS:
            if rid.lower() in msg:
                if any(w in msg for w in ["gap", "policy", "coverage", "missing"]):
                    return self._policy_gaps(user_message)
                return self._identify_regulations(user_message)

        # Audit readiness
        if any(w in msg for w in ["audit", "readiness", "assessment"]):
            return self._audit_readiness(user_message)

        # Policy gaps
        if any(w in msg for w in ["gap", "policy gap", "coverage"]):
            return self._policy_gaps(user_message)

        # Department check
        for dept in DEPARTMENT_AUDIT_STATUS:
            if dept.lower() in msg:
                return self._audit_readiness(user_message)

        # Scenario-based regulation check
        if any(w in msg for w in [
            "store", "process", "collect", "handle", "credit card", "customer data",
            "personal data", "health data", "financial", "payment",
        ]):
            return self._identify_regulations(user_message)

        # Default: show overall audit status
        return self._audit_readiness(user_message)

    # ── main entry point ────────────────────────────────────────────

    async def pipe(
        self,
        body: dict,
        __user__: dict,
        __event_emitter__: Callable = None,
        __task__: str = None,
        __metadata__: dict = None,
    ) -> AsyncGenerator[str, None] | str:
        if __task__:
            result = await self._call_ollama(body.get("messages", []))
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        messages = body.get("messages", [])
        user_message = self._extract_last_user_message(messages)
        streaming = body.get("stream", False)

        context = self._analyze_and_gather(user_message)
        augmented = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n[DATA]\n{context}"},
        ] + messages

        if not streaming:
            result = await self._call_ollama(augmented)
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        return self._stream_ollama(augmented)
