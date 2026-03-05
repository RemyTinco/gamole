"""TraceCallbackHandler - LangChain async callback for generation traces."""
from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from importlib import import_module
from typing import Protocol, TypedDict, cast, override

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult


def _estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ~= 4 characters."""
    return max(1, len(text) // 4)


def _format_messages(messages: list[list[BaseMessage]]) -> str:
    """Serialize grouped messages into a readable prompt payload."""
    parts: list[str] = []
    for msg_group in messages:
        for msg in msg_group:
            role = getattr(msg, "type", "unknown")
            content_obj = cast(object, msg.content)
            content = content_obj if isinstance(content_obj, str) else str(content_obj)
            parts.append(f"[{role.upper()}]\n{content}")
    return "\n\n---\n\n".join(parts)


def _extract_usage_counts(llm_output: Mapping[str, object]) -> tuple[int | None, int | None]:
    usage_data: Mapping[str, object] | None = None
    usage_metadata = llm_output.get("usage_metadata")
    if isinstance(usage_metadata, Mapping):
        usage_data = cast(Mapping[str, object], usage_metadata)
    token_usage = llm_output.get("token_usage")
    if usage_data is None and isinstance(token_usage, Mapping):
        usage_data = cast(Mapping[str, object], token_usage)

    if usage_data is None:
        return None, None

    input_tokens = usage_data.get("input_tokens")
    if input_tokens is None:
        input_tokens = usage_data.get("prompt_tokens")

    output_tokens = usage_data.get("output_tokens")
    if output_tokens is None:
        output_tokens = usage_data.get("completion_tokens")

    return _to_int(input_tokens), _to_int(output_tokens)


def _to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


class _PendingTrace(TypedDict):
    start_time: float
    model_name: str
    prompt_text: str


class _TraceRecord(TypedDict):
    id: str
    workflow_id: str
    agent_name: str
    event_type: str
    round_number: int
    prompt_text: str | None
    response_text: str | None
    model_name: str | None
    latency_ms: int | None
    token_in: int | None
    token_out: int | None
    cost_usd: float | None
    success: bool
    error_type: str | None
    metadata_json: dict[str, object] | None


class _SessionProtocol(Protocol):
    def add(self, item: object) -> None: ...

    def commit(self) -> Awaitable[None]: ...


class _AgentRunFactory(Protocol):
    def __call__(
        self,
        *,
        id: uuid.UUID,
        workflow_id: uuid.UUID,
        agent_name: str,
        event_type: str,
        round_number: int,
        prompt_text: str | None,
        response_text: str | None,
        model_name: str | None,
        latency_ms: int | None,
        token_in: int | None,
        token_out: int | None,
        cost_usd: float | None,
        success: bool,
        error_type: str | None,
        metadata_json: dict[str, object] | None,
    ) -> object: ...


class TraceCallbackHandler(AsyncCallbackHandler):
    """Captures LLM prompts, responses, timing, and token counts for observability."""

    workflow_id: str
    _emit_callback: Callable[[dict[str, object]], None] | None
    traces: list[_TraceRecord]
    _pending: dict[str, _PendingTrace]
    _current_round: int

    def __init__(
        self,
        workflow_id: str,
        emit_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        super().__init__()
        self.workflow_id = workflow_id
        self._emit_callback = emit_callback
        self.traces = []
        self._pending = {}
        self._current_round = 0

    def set_round(self, round_number: int) -> None:
        """Update current round number (called by graph nodes)."""
        self._current_round = round_number

    @override
    async def on_chat_model_start(
        self,
        serialized: dict[str, object],
        messages: list[list[BaseMessage]],
        *,
        run_id: object,
        **kwargs: object,
    ) -> None:
        """Capture full prompt at LLM call start."""
        del kwargs
        run_key = str(run_id)
        model_name = "unknown"
        serialized_kwargs = serialized.get("kwargs")
        if isinstance(serialized_kwargs, Mapping):
            kwargs_map = cast(Mapping[str, object], serialized_kwargs)
            model = kwargs_map.get("model")
            if isinstance(model, str):
                model_name = model
        if model_name == "unknown":
            serialized_name = serialized.get("name")
            if isinstance(serialized_name, str):
                model_name = serialized_name

        self._pending[run_key] = {
            "start_time": time.time(),
            "model_name": model_name,
            "prompt_text": _format_messages(messages),
        }

    @override
    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: object,
        **kwargs: object,
    ) -> None:
        """Capture response, compute latency and tokens, emit trace."""
        del kwargs
        run_key = str(run_id)
        pending = self._pending.pop(
            run_key,
            {
                "start_time": time.time(),
                "model_name": "unknown",
                "prompt_text": "",
            },
        )
        start_time = pending["start_time"]
        latency_ms = int((time.time() - start_time) * 1000)

        response_text = ""
        if response.generations and response.generations[0]:
            gen = response.generations[0][0]
            response_text = getattr(gen, "text", "") or str(gen)

        llm_output_raw = cast(object, response.llm_output)
        llm_output: Mapping[str, object] = (
            cast(Mapping[str, object], llm_output_raw)
            if isinstance(llm_output_raw, Mapping)
            else cast(Mapping[str, object], {})
        )
        token_in_raw, token_out_raw = _extract_usage_counts(llm_output)
        token_in = token_in_raw if token_in_raw is not None else _estimate_tokens(pending["prompt_text"])
        token_out = token_out_raw if token_out_raw is not None else _estimate_tokens(response_text)

        cost_usd = (token_in * 0.075 + token_out * 0.30) / 1_000_000

        model_name = pending["model_name"]
        trace: _TraceRecord = {
            "id": str(uuid.uuid4()),
            "workflow_id": self.workflow_id,
            "agent_name": model_name,
            "event_type": "agent_complete",
            "round_number": self._current_round,
            "prompt_text": pending["prompt_text"],
            "response_text": response_text,
            "model_name": model_name,
            "latency_ms": latency_ms,
            "token_in": token_in,
            "token_out": token_out,
            "cost_usd": cost_usd,
            "success": True,
            "error_type": None,
            "metadata_json": None,
        }
        self.traces.append(trace)

        if self._emit_callback:
            self._emit_callback(
                {
                    "id": trace["id"],
                    "agentName": model_name,
                    "eventType": "agent_complete",
                    "latencyMs": latency_ms,
                    "tokenIn": token_in,
                    "tokenOut": token_out,
                    "roundNumber": self._current_round,
                    "success": True,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                }
            )

    @override
    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: object,
        **kwargs: object,
    ) -> None:
        """Capture LLM errors."""
        del kwargs
        run_key = str(run_id)
        pending = self._pending.pop(
            run_key,
            {
                "start_time": time.time(),
                "model_name": "unknown",
                "prompt_text": "",
            },
        )
        start_time = pending["start_time"]
        latency_ms = int((time.time() - start_time) * 1000)

        trace: _TraceRecord = {
            "id": str(uuid.uuid4()),
            "workflow_id": self.workflow_id,
            "agent_name": pending["model_name"],
            "event_type": "agent_error",
            "round_number": self._current_round,
            "prompt_text": pending["prompt_text"],
            "response_text": None,
            "model_name": pending["model_name"],
            "latency_ms": latency_ms,
            "token_in": None,
            "token_out": None,
            "cost_usd": None,
            "success": False,
            "error_type": type(error).__name__,
            "metadata_json": {"error_message": str(error)},
        }
        self.traces.append(trace)

    def add_custom_event(
        self,
        event_type: str,
        agent_name: str,
        round_number: int,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Add a non-LLM trace event (retrieval, merge, supervisor decision, etc.)."""
        trace: _TraceRecord = {
            "id": str(uuid.uuid4()),
            "workflow_id": self.workflow_id,
            "agent_name": agent_name,
            "event_type": event_type,
            "round_number": round_number,
            "prompt_text": None,
            "response_text": None,
            "model_name": None,
            "latency_ms": None,
            "token_in": None,
            "token_out": None,
            "cost_usd": None,
            "success": True,
            "error_type": None,
            "metadata_json": metadata,
        }
        self.traces.append(trace)

        if self._emit_callback:
            self._emit_callback(
                {
                    "id": trace["id"],
                    "agentName": agent_name,
                    "eventType": event_type,
                    "roundNumber": round_number,
                    "success": True,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "metadata": metadata,
                }
            )

    async def persist(self, session: _SessionProtocol) -> None:
        """Bulk-insert all captured traces as AgentRun records."""
        if not self.traces:
            return

        models_module = import_module("gamole_db.models")
        agent_run_factory = cast(_AgentRunFactory, getattr(models_module, "AgentRun"))

        for trace in self.traces:
            run = agent_run_factory(
                id=uuid.UUID(trace["id"]),
                workflow_id=uuid.UUID(trace["workflow_id"]),
                agent_name=trace["agent_name"],
                event_type=trace["event_type"],
                round_number=trace["round_number"],
                prompt_text=trace["prompt_text"],
                response_text=trace["response_text"],
                model_name=trace["model_name"],
                latency_ms=trace["latency_ms"],
                token_in=trace["token_in"],
                token_out=trace["token_out"],
                cost_usd=trace["cost_usd"],
                success=trace["success"],
                error_type=trace["error_type"],
                metadata_json=trace["metadata_json"],
            )
            session.add(run)
        await session.commit()
        self.traces.clear()
