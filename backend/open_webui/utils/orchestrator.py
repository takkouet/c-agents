import asyncio
import json
import logging
from typing import Optional

log = logging.getLogger(__name__)


async def route_to_agent(form_data: dict, user, request) -> Optional[str]:
    config = request.app.state.config

    if not config.ENABLE_ORCHESTRATOR:
        return None

    routing_model = config.ORCHESTRATOR_ROUTING_MODEL
    if not routing_model or routing_model not in request.app.state.MODELS:
        return None

    worker_models = [
        model
        for model in request.app.state.MODELS.values()
        if model.get("owned_by") not in ("arena", "orchestrator")
        and not model.get("pipe")
        and model.get("info", {}).get("is_active", True)
    ]

    if not worker_models:
        return None

    agents = [
        {
            "id": model["id"],
            "name": model.get("name", model["id"]),
            "description": model.get("info", {}).get("meta", {}).get("description", ""),
        }
        for model in worker_models
    ]

    user_message = ""
    for msg in reversed(form_data.get("messages", [])):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        user_message = part.get("text", "")
                        break
            else:
                user_message = content
            break

    routing_form_data = {
        "model": routing_model,
        "messages": [
            {
                "role": "system",
                "content": config.ORCHESTRATOR_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Available agents:\n{json.dumps(agents, indent=2)}\n\n"
                    f"User message: {user_message}\n\n"
                    "Respond with ONLY the agent id that should handle this message. "
                    "If none are suitable, respond with 'NONE'."
                ),
            },
        ],
        "stream": False,
    }

    try:
        from open_webui.utils.chat import generate_chat_completion

        response = await asyncio.wait_for(
            generate_chat_completion(
                request,
                routing_form_data,
                user,
                bypass_filter=True,
            ),
            timeout=10.0,
        )

        selected_id = response["choices"][0]["message"]["content"].strip()

        if selected_id == "NONE":
            return None

        worker_ids = {m["id"] for m in worker_models}
        if selected_id in worker_ids:
            return selected_id

        log.warning(f"Orchestrator returned invalid model id: {selected_id!r}")
        return None

    except asyncio.TimeoutError:
        log.warning("Orchestrator routing timed out after 10 seconds")
        return None
    except Exception as e:
        log.error(f"Orchestrator routing error: {e}")
        return None
