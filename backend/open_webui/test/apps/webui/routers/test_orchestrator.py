import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

# Bootstrap: inject a mock for open_webui.utils.chat BEFORE importing the
# orchestrator, because chat.py pulls in heavy server-side dependencies
# (database models, sockets, etc.) that are unavailable in a unit-test env.
# route_to_agent does `from open_webui.utils.chat import generate_chat_completion`
# *inside* the function body, so patching sys.modules here is sufficient —
# Python resolves the lazy import against sys.modules at call time.
_mock_chat_module = MagicMock()
_mock_generate_chat_completion = AsyncMock()
_mock_chat_module.generate_chat_completion = _mock_generate_chat_completion
sys.modules["open_webui.utils.chat"] = _mock_chat_module

from open_webui.utils.orchestrator import route_to_agent  # noqa: E402


_DEFAULT_MODELS = {
    "router-model": {
        "id": "router-model",
        "name": "Router",
        "owned_by": "openai",
        "pipe": None,
        "info": {"is_active": True, "meta": {"description": "Routing model"}},
    },
    "worker-a": {
        "id": "worker-a",
        "name": "Worker A",
        "owned_by": "openai",
        "pipe": None,
        "info": {"is_active": True, "meta": {"description": "General helper"}},
    },
}


def _make_request(
    enable_orchestrator: bool = True,
    routing_model: str = "router-model",
    system_prompt: str = "Route messages.",
    models: dict | None = None,
) -> MagicMock:
    req = MagicMock()
    req.app.state.config.ENABLE_ORCHESTRATOR = enable_orchestrator
    req.app.state.config.ORCHESTRATOR_ROUTING_MODEL = routing_model
    req.app.state.config.ORCHESTRATOR_SYSTEM_PROMPT = system_prompt
    req.app.state.MODELS = models if models is not None else dict(_DEFAULT_MODELS)
    return req


def _make_user() -> MagicMock:
    user = MagicMock()
    user.id = "user-1"
    return user


def _make_form_data(user_message: str = "Hello, help me.") -> dict:
    return {"messages": [{"role": "user", "content": user_message}]}


def _configure_llm(content: str) -> None:
    _mock_generate_chat_completion.reset_mock()
    _mock_generate_chat_completion.side_effect = None
    _mock_generate_chat_completion.return_value = {
        "choices": [{"message": {"content": content}}]
    }


def _run(coro):
    return asyncio.run(coro)


class TestDisabledOrchestrator:
    def test_returns_none_when_disabled(self):
        """ENABLE_ORCHESTRATOR=False → returns None, LLM never called."""
        _mock_generate_chat_completion.reset_mock()
        req = _make_request(enable_orchestrator=False)
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None
        _mock_generate_chat_completion.assert_not_called()


class TestRoutingModelConfig:
    def test_empty_routing_model_returns_none(self):
        """ORCHESTRATOR_ROUTING_MODEL='' → returns None."""
        req = _make_request(routing_model="")
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None

    def test_routing_model_absent_from_models_returns_none(self):
        """Routing model not present in MODELS dict → returns None."""
        req = _make_request(routing_model="ghost-model")
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None


class TestWorkerFiltering:
    _EXCLUDED_MODELS = {
        "router-model": {
            "id": "router-model",
            "owned_by": "orchestrator",  # routing model itself is orchestrator-owned, excluded
            "pipe": None,
            "info": {"is_active": True},
        },
        "arena-bot": {
            "id": "arena-bot",
            "owned_by": "arena",
            "pipe": None,
            "info": {"is_active": True},
        },
        "orch-bot": {
            "id": "orch-bot",
            "owned_by": "orchestrator",
            "pipe": None,
            "info": {"is_active": True},
        },
        "pipe-bot": {
            "id": "pipe-bot",
            "owned_by": "openai",
            "pipe": "some-pipe",
            "info": {"is_active": True},
        },
        "inactive-bot": {
            "id": "inactive-bot",
            "owned_by": "openai",
            "pipe": None,
            "info": {"is_active": False},
        },
    }

    def test_no_eligible_workers_returns_none(self):
        """All models are ineligible (arena/orchestrator/pipe/inactive) → returns None before LLM call."""
        _mock_generate_chat_completion.reset_mock()
        req = _make_request(models=self._EXCLUDED_MODELS)
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None
        _mock_generate_chat_completion.assert_not_called()

    def test_arena_model_excluded_from_candidates(self):
        """LLM suggests an arena model id → not in worker list → returns None."""
        models = {
            "router-model": {
                "id": "router-model",
                "owned_by": "openai",
                "pipe": None,
                "info": {"is_active": True},
            },
            "arena-bot": {
                "id": "arena-bot",
                "owned_by": "arena",
                "pipe": None,
                "info": {"is_active": True},
            },
            "worker-a": {
                "id": "worker-a",
                "owned_by": "openai",
                "pipe": None,
                "info": {"is_active": True, "meta": {"description": "Worker"}},
            },
        }
        _configure_llm("arena-bot")
        req = _make_request(models=models)
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None

    def test_inactive_model_excluded_from_candidates(self):
        """LLM suggests an inactive model id → not in worker list → returns None."""
        models = {
            "router-model": {
                "id": "router-model",
                "owned_by": "openai",
                "pipe": None,
                "info": {"is_active": True},
            },
            "inactive-bot": {
                "id": "inactive-bot",
                "owned_by": "openai",
                "pipe": None,
                "info": {"is_active": False},
            },
            "worker-a": {
                "id": "worker-a",
                "owned_by": "openai",
                "pipe": None,
                "info": {"is_active": True, "meta": {"description": "Worker"}},
            },
        }
        _configure_llm("inactive-bot")
        req = _make_request(models=models)
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None

    def test_pipe_model_excluded_from_candidates(self):
        """LLM suggests a pipe model id → not in worker list → returns None."""
        models = {
            "router-model": {
                "id": "router-model",
                "owned_by": "openai",
                "pipe": None,
                "info": {"is_active": True},
            },
            "pipe-bot": {
                "id": "pipe-bot",
                "owned_by": "openai",
                "pipe": "some-pipe",
                "info": {"is_active": True},
            },
            "worker-a": {
                "id": "worker-a",
                "owned_by": "openai",
                "pipe": None,
                "info": {"is_active": True, "meta": {"description": "Worker"}},
            },
        }
        _configure_llm("pipe-bot")
        req = _make_request(models=models)
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None


class TestValidRouting:
    def test_valid_worker_id_returned(self):
        """LLM returns a valid worker id → route_to_agent returns that id."""
        _configure_llm("worker-a")
        req = _make_request()
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result == "worker-a"

    def test_whitespace_stripped_from_response(self):
        """Trailing/leading whitespace in LLM response is stripped."""
        _configure_llm("  worker-a  ")
        req = _make_request()
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result == "worker-a"


class TestInvalidLLMResponses:
    def test_none_literal_response_returns_none(self):
        """LLM replies 'NONE' → returns None."""
        _configure_llm("NONE")
        req = _make_request()
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None

    def test_unknown_id_response_returns_none(self):
        """LLM returns an id that does not match any worker → returns None."""
        _configure_llm("does-not-exist")
        req = _make_request()
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None


class TestErrorHandling:
    def test_timeout_returns_none(self):
        """asyncio.TimeoutError during LLM call → returns None."""
        _mock_generate_chat_completion.reset_mock()
        _mock_generate_chat_completion.side_effect = asyncio.TimeoutError
        req = _make_request()
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None
        _mock_generate_chat_completion.side_effect = None

    def test_generic_exception_returns_none(self):
        """Unexpected Exception during LLM call → returns None."""
        _mock_generate_chat_completion.reset_mock()
        _mock_generate_chat_completion.side_effect = RuntimeError("network failure")
        req = _make_request()
        result = _run(route_to_agent(_make_form_data(), _make_user(), req))
        assert result is None
        _mock_generate_chat_completion.side_effect = None
