import asyncio
import json
import logging
import time
import uuid
from typing import Optional

from open_webui.utils.orchestration_broadcast import publish

log = logging.getLogger(__name__)


def _user_can_access_model(user, model_id: str, request) -> bool:
    """Return True if user has read access to the given model."""
    from open_webui.utils.models import check_model_access

    model = request.app.state.MODELS.get(model_id)
    if not model:
        return False
    try:
        check_model_access(user, model)
        return True
    except Exception:
        return False


async def _emit(session_id: str, step: str, message: str, **kwargs):
    """Publish an orchestration event to all WebSocket subscribers."""
    try:
        await publish(
            {
                "step": step,
                "session_id": session_id,
                "message": message,
                "timestamp": time.time(),
                **kwargs,
            }
        )
    except Exception as e:
        log.warning(f"Failed to emit orchestration event: {e}")


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

    session_id = str(uuid.uuid4())
    await _emit(session_id, "session_start", "Analyzing your request...")

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

    await _emit(
        session_id,
        "routing",
        "Selecting the best agent...",
        agents=agents,
    )

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
            if not _user_can_access_model(user, selected_id, request):
                await _emit(
                    session_id,
                    "permission_denied",
                    "You don't have permission to access this agent. Please contact your admin.",
                    agent_id=selected_id,
                )
                return "PERMISSION_DENIED", session_id

            selected_name = next(
                (a["name"] for a in agents if a["id"] == selected_id),
                selected_id,
            )
            await _emit(
                session_id,
                "agent_active",
                f"Delegated to {selected_name}",
                agent_id=selected_id,
                agent_label=selected_name,
                agent_icon="🤖",
                agent_dept="",
                action=f"Handling request",
            )
            return selected_id, session_id

        log.warning(f"Orchestrator returned invalid model id: {selected_id!r}")
        return None

    except asyncio.TimeoutError:
        log.warning("Orchestrator routing timed out after 10 seconds")
        return None
    except Exception as e:
        log.error(f"Orchestrator routing error: {e}")
        return None
