"""
Gemini ↔ OpenAI format conversion utilities.
Extracted from gemini_proxy.py so all agents can share them.
"""

import json
import time
import uuid


def openai_messages_to_gemini(messages: list) -> tuple[list, str | None]:
    """Convert OpenAI messages array to Gemini contents + system_instruction."""
    system_parts: list[str] = []
    contents: list[dict] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Normalise content to a list of parts
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
            system_parts.append(
                content if isinstance(content, str)
                else " ".join(p.get("text", "") for p in parts)
            )
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


def make_orchestration_sse(step: str, **kwargs) -> bytes:
    """Build an SSE line carrying an orchestration event for the frontend sidebar."""
    payload = {"type": "orchestration", "step": step, **kwargs}
    return f"data: {json.dumps(payload)}\n\n".encode()
