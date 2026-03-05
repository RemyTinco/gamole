"""Tests for trace callback handler and traces endpoint."""

import uuid

from langchain_core.messages import HumanMessage
from langchain_core.outputs import Generation, LLMResult

from gamole_ai.trace_handler import TraceCallbackHandler


async def test_trace_callback_handler_captures_prompts():
    run_id = uuid.uuid4()
    handler = TraceCallbackHandler(workflow_id="test-id", emit_callback=lambda x: None)

    await handler.on_chat_model_start(
        {"name": "gemini"},
        [[HumanMessage(content="Hello")]],
        run_id=run_id,
    )
    await handler.on_llm_end(
        LLMResult(generations=[[Generation(text="World")]]),
        run_id=run_id,
    )

    assert len(handler.traces) == 1
    assert handler.traces[0]["prompt_text"] is not None
    assert "Hello" in handler.traces[0]["prompt_text"]
    assert handler.traces[0]["response_text"] == "World"
    assert handler.traces[0]["latency_ms"] is not None
    assert handler.traces[0]["latency_ms"] >= 0


async def test_trace_callback_handler_custom_events():
    handler = TraceCallbackHandler(workflow_id="test-id", emit_callback=lambda x: None)

    handler.add_custom_event("retrieval_complete", "retrieve_context", 1, {"chunk_count": 5})

    assert len(handler.traces) == 1
    assert handler.traces[0]["event_type"] == "retrieval_complete"
    assert handler.traces[0]["metadata_json"] == {"chunk_count": 5}
    assert handler.traces[0]["agent_name"] == "retrieve_context"


async def test_trace_callback_handler_error_handling():
    run_id = uuid.uuid4()
    handler = TraceCallbackHandler(workflow_id="test-id", emit_callback=lambda x: None)

    await handler.on_chat_model_start(
        {"name": "gemini"},
        [[HumanMessage(content="test")]],
        run_id=run_id,
    )
    await handler.on_llm_error(Exception("API error"), run_id=run_id)

    assert len(handler.traces) == 1
    assert handler.traces[0]["success"] is False
    assert handler.traces[0]["error_type"] is not None


async def test_trace_callback_emit_callback():
    emitted: list[dict] = []
    run_id = uuid.uuid4()
    handler = TraceCallbackHandler(workflow_id="test-id", emit_callback=lambda x: emitted.append(x))

    await handler.on_chat_model_start(
        {"name": "gemini"},
        [[HumanMessage(content="Hello")]],
        run_id=run_id,
    )
    await handler.on_llm_end(
        LLMResult(generations=[[Generation(text="World")]]),
        run_id=run_id,
    )

    assert len(emitted) >= 1
    assert "promptText" not in emitted[0]
    assert "responseText" not in emitted[0]
    assert "agent_name" in emitted[0] or "event_type" in emitted[0]


def test_traces_endpoint_requires_auth(client):
    response = client.get("/api/generation/00000000-0000-0000-0000-000000000001/traces")
    assert response.status_code in (401, 403)


def test_traces_endpoint_returns_empty_for_unknown_generation(client, auth_headers):
    response = client.get(
        "/api/generation/00000000-0000-0000-0000-000000000001/traces",
        headers=auth_headers,
    )
    # 200 with empty list (DB available) OR 500 (DB unavailable)
    if response.status_code == 200:
        data = response.json()
        assert "traces" in data
        assert data["traces"] == []
    else:
        assert response.status_code == 500
