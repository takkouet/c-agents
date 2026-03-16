"""
title: Semiconductor Agent
description: Handles semiconductor industry questions — chip specifications, foundry technology, EDA tools (Cadence, Synopsys, Siemens), simulation & verification (Xcelium, VCS, Verilator), RTL/FPGA design, market trends, supply chain, and technology roadmaps
requirements: aiohttp,certifi
"""

import json
import re
import ssl
import time
import uuid
from typing import AsyncGenerator, Callable, Optional

import aiohttp
import certifi
from pydantic import BaseModel, Field

_ssl_ctx = ssl.create_default_context(cafile=certifi.where())

# ──────────────────────────────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are the Semiconductor Agent for C-Agents, an enterprise AI assistant specializing \
in the semiconductor industry.

Your expertise includes:
- Foundry technology and process nodes (TSMC, Samsung, Intel, GlobalFoundries)
- Chip architecture and specifications (CPUs, GPUs, AI accelerators, FPGAs)
- Advanced packaging (chiplet, 2.5D/3D, CoWoS, EMIB, Foveros)
- Lithography and equipment (EUV, High-NA EUV, ASML)
- Memory technology (HBM, DDR5, NAND, emerging memories)
- Supply chain dynamics, capacity, and lead times
- Market trends, revenue data, and competitive landscape
- Technology roadmaps and future process nodes

Domain vocabulary you understand: process node, gate-all-around (GAA), FinFET, backside power delivery (BSPDN), \
transistor density, wafer size, die yield, tape-out, PDK, IP blocks, EDA, \
fabless, IDM, OSAT, CoWoS, InFO, EMIB, Foveros, UCIe, chiplet, \
HBM3e, GDDR7, CXL, PCIe Gen6, TSMC N2/N3/N5, Samsung SF2/SF3, Intel 18A/20A, \
Cadence Xcelium, Synopsys VCS, Verilator, Mentor/Siemens Questa, simulation, verification, \
RTL, SystemVerilog, VHDL, UVM, formal verification, static timing analysis (STA), \
place-and-route, synthesis, ChipStack, FPGA, ASIC design flow.

Guidelines:
- When you have [KNOWLEDGE CONTEXT] from Notes, use it as your primary source and cite it
- When you have [WEB SEARCH RESULTS], integrate them for current/recent information
- Always mention the source of your information (Notes knowledge base or web search)
- If neither context is available, answer from your training knowledge but clearly state limitations
- Be precise with technical specifications: cite nm dimensions, transistor counts, TDP, etc.
- For market/financial data, note the date of the information

Format responses with clear structure, use technical accuracy, and provide context for \
non-expert readers when appropriate.\
"""

# Keywords that indicate the user wants current/recent information
# (triggers web search)
CURRENT_INFO_KEYWORDS = [
    "latest", "recent", "news", "today", "this week", "this month", "this quarter",
    "q1", "q2", "q3", "q4", "2026", "2025", "earnings", "revenue", "stock",
    "announced", "announcement", "launched", "released", "update",
    "market share", "forecast", "outlook", "guidance", "quarterly",
    "acquisition", "merger", "partnership", "contract", "deal",
]

# Keywords that can be answered from knowledge base alone
KNOWLEDGE_ONLY_KEYWORDS = [
    "what is", "explain", "how does", "how do", "definition", "define",
    "compare", "vs", "versus", "difference between",
    "specification", "spec", "architecture", "design",
    "roadmap", "process node", "technology",
]


# ──────────────────────────────────────────────────────────────────────
# Pipe
# ──────────────────────────────────────────────────────────────────────


class Pipe:
    class Valves(BaseModel):
        OLLAMA_BASE_URL: str = Field(
            default="http://localhost:11434",
            description="Ollama base URL",
        )
        MODEL: str = Field(
            default="phi4-mini",
            description="Ollama model for response generation",
        )
        ENABLE_WEB_SEARCH: bool = Field(
            default=True,
            description="Enable web search for current information",
        )
        WEB_SEARCH_RESULT_COUNT: int = Field(
            default=5,
            description="Number of web search results to fetch",
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        return [{"id": "semiconductor-agent", "name": "Semiconductor Agent"}]

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
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    async def _call_ollama(self, messages: list[dict]) -> dict:
        url = f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions"
        payload = {"model": self.valves.MODEL, "messages": messages, "stream": False}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status != 200:
                        return self._empty_response(self.valves.MODEL)
                    return await resp.json()
        except Exception as e:
            print(f"[semiconductor-agent] LLM error: {e!r}", flush=True)
            return self._empty_response(self.valves.MODEL)

    async def _stream_ollama(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        url = f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions"
        payload = {"model": self.valves.MODEL, "messages": messages, "stream": True}
        session = aiohttp.ClientSession()
        try:
            resp = await session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=300)
            )
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

    # ── web search ──────────────────────────────────────────────────

    def _needs_web_search(self, user_message: str) -> bool:
        """Determine if the query needs live web search results."""
        msg = user_message.lower()
        # If it matches current-info keywords, search
        if any(kw in msg for kw in CURRENT_INFO_KEYWORDS):
            return True
        # If it's purely a knowledge/explanation question, skip search
        if any(kw in msg for kw in KNOWLEDGE_ONLY_KEYWORDS):
            return False
        # Default: don't search for general questions
        return False

    def _build_search_query(self, user_message: str) -> str:
        """Build a focused search query from the user message."""
        # Add "semiconductor" context if not already present
        msg = user_message.strip()
        semi_keywords = [
            "semiconductor", "chip", "foundry", "tsmc", "samsung", "intel",
            "asml", "nvidia", "amd", "qualcomm", "nm", "process node",
            "wafer", "hbm", "ddr", "nand", "euv",
        ]
        has_context = any(kw in msg.lower() for kw in semi_keywords)
        if not has_context:
            msg = f"semiconductor {msg}"
        return msg

    async def _web_search(self, user_message: str) -> str:
        """Perform web search using DuckDuckGo and return formatted results."""
        query = self._build_search_query(user_message)
        try:
            from open_webui.retrieval.web.duckduckgo import search_duckduckgo

            results = search_duckduckgo(query, count=self.valves.WEB_SEARCH_RESULT_COUNT)
        except ImportError:
            print("[semiconductor-agent] DuckDuckGo search not available, trying fallback", flush=True)
            try:
                from open_webui.retrieval.web.utils import search_duckduckgo as fallback_search
                results = fallback_search(query, count=self.valves.WEB_SEARCH_RESULT_COUNT)
            except Exception:
                return ""
        except Exception as e:
            print(f"[semiconductor-agent] Web search error: {e!r}", flush=True)
            return ""

        if not results:
            return ""

        lines = []
        for i, result in enumerate(results[:self.valves.WEB_SEARCH_RESULT_COUNT], 1):
            title = result.title or ""
            link = result.link or ""
            snippet = result.snippet or ""
            lines.append(f"[{i}] {title}\n    URL: {link}\n    {snippet}")

        return "\n\n".join(lines)

    # ── main entry point ────────────────────────────────────────────

    async def pipe(
        self,
        body: dict,
        __user__: dict,
        __event_emitter__: Callable = None,
        __task__: str = None,
        __metadata__: dict = None,
    ) -> AsyncGenerator[str, None] | str:
        # Background tasks (title generation, etc.)
        if __task__:
            result = await self._call_ollama(body.get("messages", []))
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        messages = body.get("messages", [])
        user_message = self._extract_last_user_message(messages)
        streaming = body.get("stream", False)

        # ── RAG context from Notes is already in messages ──
        # Open WebUI's middleware injects knowledge from attached Notes
        # into the messages before they reach this pipe function.
        # We just need to check if any RAG context is present.
        has_rag = any(
            "<source" in (m.get("content", "") if isinstance(m.get("content"), str) else "")
            for m in messages
        )

        # ── Web search for current information ──
        web_context = ""
        if self.valves.ENABLE_WEB_SEARCH and self._needs_web_search(user_message):
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": "Searching the web...", "done": False}}
                )
            web_context = await self._web_search(user_message)
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": "Search complete", "done": True}}
                )

        # ── Build augmented messages ──
        system = SYSTEM_PROMPT

        # Add source context notes
        source_notes = []
        if has_rag:
            source_notes.append(
                "You have [KNOWLEDGE CONTEXT] from Notes embedded in the conversation. "
                "Use this as your primary source of truth for technical specifications and reference data."
            )
        if web_context:
            system += f"\n\n[WEB SEARCH RESULTS]\n{web_context}"
            source_notes.append(
                "You have [WEB SEARCH RESULTS] with current information. "
                "Integrate these with your knowledge to provide up-to-date answers."
            )
        if not has_rag and not web_context:
            source_notes.append(
                "No Notes knowledge base or web search results are available for this query. "
                "Answer from your training knowledge but note any limitations on recency."
            )

        if source_notes:
            system += "\n\n[SOURCE GUIDANCE]\n" + "\n".join(source_notes)

        augmented = [{"role": "system", "content": system}] + messages

        if not streaming:
            result = await self._call_ollama(augmented)
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

        return self._stream_ollama(augmented)
