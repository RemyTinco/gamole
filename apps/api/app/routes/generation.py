"""Generation endpoints: start workflow, track progress, stream events, retrieve results.

Features: DB persistence, human-in-the-loop editing, cost tracking.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from ..auth.middleware import auth_dependency

router = APIRouter()


def _format_cost(raw: dict | None) -> dict | None:
    """Convert snake_case cost breakdown from DB to camelCase for frontend."""
    if not raw:
        return None
    agents = raw.get("agents", {})
    per_agent = {}
    for name, data in agents.items():
        per_agent[name] = {
            "inputTokens": data.get("input_tokens", 0),
            "outputTokens": data.get("output_tokens", 0),
            "costUsd": data.get("cost_usd", 0),
        }
    return {
        "totalInputTokens": raw.get("total_input_tokens", 0),
        "totalOutputTokens": raw.get("total_output_tokens", 0),
        "totalCostUsd": raw.get("total_cost_usd", 0),
        "perAgent": per_agent,
    }


# In-memory state (G19: single concurrent generation)
_active_generation: dict | None = None
_generation_events: dict[str, list[dict]] = {}
_event_queues: dict[str, list[asyncio.Queue]] = {}


def _emit(generation_id: str, event_type: str, data: dict) -> None:
    """Push an SSE event to all listeners and store it."""
    event = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _generation_events.setdefault(generation_id, []).append(event)
    for queue in _event_queues.get(generation_id, []):
        queue.put_nowait(event)


async def _get_or_create_workspace(session) -> Any:
    """Get or create a default user and workspace for standalone API use."""
    from gamole_db import User, Workspace

    result = await session.execute(select(Workspace).limit(1))
    ws = result.scalar_one_or_none()
    if ws:
        return ws.id

    user = User(email="api@gamole.dev")
    session.add(user)
    await session.flush()
    workspace = Workspace(user_id=user.id)
    session.add(workspace)
    await session.flush()
    return workspace.id


async def _run_main_workflow(generation_id: str, input_text: str, document: str, context: dict) -> None:
    """Background task: run the main LangGraph workflow after discovery answers submitted."""
    global _active_generation
    from gamole_ai.cost_tracker import CostTracker, set_tracker
    from gamole_ai.trace_handler import TraceCallbackHandler
    from gamole_db import Workflow, get_session

    tracker = CostTracker()
    ctx_token = set_tracker(tracker)
    trace_handler = TraceCallbackHandler(
        workflow_id=generation_id,
        emit_callback=lambda data: _emit(generation_id, "trace", data),
    )

    try:
        from app.orchestrator.graph import WorkflowState, workflow

        _emit(generation_id, "status", {
            "generationId": generation_id,
            "status": "running",
            "message": "Starting main workflow",
        })

        initial_state: WorkflowState = {
            "input": input_text,
            "document": document,
            "context": context,
            "round": 0,
            "critiques": [],
            "quality_score": 0,
            "status": "CONTEXT_RETRIEVED",
            "structured_output": None,
            "discovery_questions": None,
            "discovery_answers": None,
            "qa_critique": None,
            "dev_critique": None,
            "po_critique": None,
            "qa_doc": None,
            "dev_doc": None,
            "po_doc": None,
            "_trace_handler": trace_handler,
        }

        last_status = "CONTEXT_RETRIEVED"
        final_document = document
        final_quality_score = 0.0

        async for chunk in workflow.astream(
            initial_state,
            config={"callbacks": [trace_handler]},
        ):
            for node_name, update in chunk.items():
                new_status = update.get("status", last_status)
                if new_status != last_status:
                    last_status = new_status
                    _emit(generation_id, "progress", {
                        "generationId": generation_id,
                        "node": node_name,
                        "status": new_status,
                        "round": update.get("round", 0),
                        "qualityScore": update.get("quality_score", 0),
                    })
                if update.get("document"):
                    final_document = update["document"]
                if update.get("quality_score"):
                    final_quality_score = update["quality_score"]

        async for session in get_session():
            await trace_handler.persist(cast(Any, session))

        # Update DB: workflow paused at USER_EDITING
        async for session in get_session():
            wf = await session.get(Workflow, uuid.UUID(generation_id))
            if wf:
                wf.status = "USER_EDITING"
                wf.document = final_document
                wf.quality_score = final_quality_score
                wf.cost_breakdown = tracker.to_dict()
                await session.commit()

        _emit(generation_id, "user_edit_required", {
            "generationId": generation_id,
            "message": "Document ready for review. Edit and finalize when ready.",
            "document": final_document,
        })

    except Exception as e:
        try:
            async for session in get_session():
                wf = await session.get(Workflow, uuid.UUID(generation_id))
                if wf:
                    wf.status = "FAILED"
                    wf.cost_breakdown = tracker.to_dict()
                    await session.commit()
        except Exception:
            pass
        _emit(generation_id, "error", {
            "generationId": generation_id,
            "error": str(e),
        })
    finally:
        from gamole_ai.cost_tracker import clear_tracker

        clear_tracker(ctx_token)
        _active_generation = None


async def _run_generation(generation_id: str, input_text: str) -> None:
    """Background task: run the discovery LangGraph workflow and emit discovery questions."""
    global _active_generation
    import sys

    sys.path.insert(0, "/tmp/gamole/apps/api")

    from gamole_ai.cost_tracker import CostTracker, set_tracker
    from gamole_ai.trace_handler import TraceCallbackHandler
    from gamole_db import Workflow, get_session

    # Set up cost tracker
    tracker = CostTracker()
    ctx_token = set_tracker(tracker)
    trace_handler = TraceCallbackHandler(
        workflow_id=generation_id,
        emit_callback=lambda data: _emit(generation_id, "trace", data),
    )

    try:
        from app.orchestrator.graph import WorkflowState, discovery_workflow

        _emit(generation_id, "status", {
            "generationId": generation_id,
            "status": "running",
            "message": "Starting discovery",
        })

        initial_state: WorkflowState = {
            "input": input_text,
            "document": input_text,
            "context": {},
            "round": 0,
            "critiques": [],
            "quality_score": 0,
            "status": "INITIALIZED",
            "structured_output": None,
            "discovery_questions": None,
            "discovery_answers": None,
            "qa_critique": None,
            "dev_critique": None,
            "po_critique": None,
            "qa_doc": None,
            "dev_doc": None,
            "po_doc": None,
            "_trace_handler": trace_handler,
        }

        final_questions: list = []
        final_context: dict = {}

        async for chunk in discovery_workflow.astream(
            initial_state,
            config={"callbacks": [trace_handler]},
        ):
            for _node_name, update in chunk.items():
                if update.get("discovery_questions"):
                    final_questions = update["discovery_questions"]
                if update.get("context"):
                    final_context = update["context"]

        async for session in get_session():
            await trace_handler.persist(cast(Any, session))

        # Persist to DB with AWAITING_DISCOVERY status
        async for session in get_session():
            wf = await session.get(Workflow, uuid.UUID(generation_id))
            if wf:
                wf.status = "AWAITING_DISCOVERY"
                wf.state_json = {
                    "discovery": {
                        "questions": final_questions,
                        "context": final_context,
                    }
                }
                await session.commit()

        # Emit discovery questions event
        _emit(generation_id, "discovery_questions", {"questions": final_questions})

        # Release lock — user may take minutes/hours to answer
        _active_generation = None

    except Exception as e:
        try:
            async for session in get_session():
                wf = await session.get(Workflow, uuid.UUID(generation_id))
                if wf:
                    wf.status = "FAILED"
                    wf.cost_breakdown = tracker.to_dict()
                    await session.commit()
        except Exception:
            pass
        _emit(generation_id, "error", {
            "generationId": generation_id,
            "error": str(e),
        })
        _active_generation = None
    finally:
        from gamole_ai.cost_tracker import clear_tracker

        clear_tracker(ctx_token)

class GenerationInput(BaseModel):
    input: str


@router.post("/generation", dependencies=[Depends(auth_dependency)])
async def start_generation(body: GenerationInput):
    global _active_generation
    if _active_generation is not None:
        raise HTTPException(status_code=409, detail="A generation is already in progress")

    generation_id = str(uuid.uuid4())
    _active_generation = {"id": generation_id}

    # Persist to DB
    from gamole_db import Workflow, get_session

    try:
        async for session in get_session():
            workspace_id = await _get_or_create_workspace(session)
            wf = Workflow(
                id=uuid.UUID(generation_id),
                workspace_id=workspace_id,
                status="INITIALIZED",
                input_text=body.input,
                input_mode="form",
                target_team_id="default",
            )
            session.add(wf)
            await session.commit()
    except Exception:
        # If DB fails, still allow generation to run (graceful degradation)
        pass

    asyncio.create_task(_run_generation(generation_id, body.input))

    return {"id": generation_id, "status": "running"}


@router.get("/generation", dependencies=[Depends(auth_dependency)])
async def list_generations():
    from gamole_db import Workflow, get_session

    try:
        async for session in get_session():
            result = await session.execute(
                select(Workflow).order_by(Workflow.created_at.desc())
            )
            workflows = []
            for wf in result.scalars().all():
                workflows.append({
                    "id": str(wf.id),
                    "status": wf.status,
                    "createdAt": wf.created_at.isoformat() if wf.created_at else None,
                    "hasOutput": wf.structured_output is not None,
                    "qualityScore": wf.quality_score,
                    "costBreakdown": _format_cost(wf.cost_breakdown),
                })
            return {"workflows": workflows}
    except Exception:
        return {"workflows": []}


@router.get("/generation/{generation_id}", dependencies=[Depends(auth_dependency)])
async def get_generation(generation_id: str):
    from gamole_db import Workflow, get_session

    try:
        async for session in get_session():
            wf = await session.get(Workflow, uuid.UUID(generation_id))
            if not wf:
                raise HTTPException(status_code=404, detail="Generation not found")
            return {
                "id": str(wf.id),
                "status": wf.status,
                "createdAt": wf.created_at.isoformat() if wf.created_at else None,
                "structuredOutput": wf.structured_output,
                "document": wf.document,
                "qualityScore": wf.quality_score,
                "costBreakdown": _format_cost(wf.cost_breakdown),
                "error": None,
                "discoveryQuestions": (wf.state_json or {}).get("discovery", {}).get("questions"),
            }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Generation not found")


@router.get("/generation/{generation_id}/output", dependencies=[Depends(auth_dependency)])
async def get_generation_output(generation_id: str):
    """Get the structured output (epics/stories) ready for Linear push."""
    from gamole_db import Workflow, get_session

    try:
        async for session in get_session():
            wf = await session.get(Workflow, uuid.UUID(generation_id))
            if not wf:
                raise HTTPException(status_code=404, detail="Generation not found")
            if wf.status not in ("READY_TO_PUSH", "PUSHED_TO_LINEAR") and wf.structured_output is None:
                raise HTTPException(status_code=400, detail=f"Generation is {wf.status}, not completed")
            if not wf.structured_output:
                raise HTTPException(status_code=400, detail="No structured output available")
            return wf.structured_output
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Generation not found")


@router.get("/generation/{generation_id}/traces", dependencies=[Depends(auth_dependency)])
async def get_generation_traces(generation_id: str):
    """Get all trace events for a generation (full prompt/response text)."""
    from gamole_db import AgentRun, get_session
    from gamole_types.schemas.trace import TraceEvent

    try:
        async for session in get_session():
            result = await session.execute(
                select(AgentRun)
                .where(AgentRun.workflow_id == uuid.UUID(generation_id))
                .order_by(AgentRun.created_at.asc())
            )
            traces = result.scalars().all()
            return {
                "traces": [
                    TraceEvent.model_validate(t, from_attributes=True).model_dump(mode="json")
                    for t in traces
                ]
            }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid generation ID")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
class DocumentUpdateInput(BaseModel):
    document: str


@router.put("/generation/{generation_id}/document", dependencies=[Depends(auth_dependency)])
async def update_generation_document(generation_id: str, body: DocumentUpdateInput):
    """Update the document text during editable phases."""
    from gamole_db import Workflow, get_session

    async for session in get_session():
        wf = await session.get(Workflow, uuid.UUID(generation_id))
        if not wf:
            raise HTTPException(status_code=404, detail="Generation not found")
        if wf.status not in ("USER_EDITING", "READY_TO_PUSH"):
            raise HTTPException(
                status_code=400,
                detail=f"Generation is {wf.status}, not in an editable state",
            )

        if wf.status == "READY_TO_PUSH":
            wf.status = "USER_EDITING"
            wf.structured_output = None

        wf.document = body.document
        await session.commit()
        return {"id": str(wf.id), "status": wf.status, "document": wf.document}


class StructuredOutputUpdateInput(BaseModel):
    structured_output: dict




@router.put("/generation/{generation_id}/structured-output", dependencies=[Depends(auth_dependency)])
async def update_structured_output(generation_id: str, body: StructuredOutputUpdateInput):
    """Update the structured output (epics/stories) during READY_TO_PUSH phase."""
    from gamole_db import Workflow, get_session
    from gamole_types import GeneratedOutput

    # Validate the structured output against the Pydantic schema
    try:
        validated = GeneratedOutput(**body.structured_output)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid structured output: {e}")

    async for session in get_session():
        wf = await session.get(Workflow, uuid.UUID(generation_id))
        if not wf:
            raise HTTPException(status_code=404, detail="Generation not found")
        if wf.status not in ("READY_TO_PUSH", "PUSHED_TO_LINEAR"):
            raise HTTPException(status_code=400, detail=f"Generation is {wf.status}, not ready for editing")
        wf.structured_output = validated.model_dump(by_alias=True)
        await session.commit()
        return {"id": str(wf.id), "status": wf.status, "structuredOutput": wf.structured_output}

@router.post("/generation/{generation_id}/finalize", dependencies=[Depends(auth_dependency)])
async def finalize_generation(generation_id: str):
    """Trigger the structuring step after user editing."""
    from gamole_ai.cost_tracker import CostTracker, clear_tracker, set_tracker
    from gamole_ai.trace_handler import TraceCallbackHandler
    from gamole_db import Workflow, get_session

    document = ""
    existing_cost: dict = {}
    async for session in get_session():
        wf = await session.get(Workflow, uuid.UUID(generation_id))
        if not wf:
            raise HTTPException(status_code=404, detail="Generation not found")
        if wf.status != "USER_EDITING":
            raise HTTPException(status_code=400, detail=f"Generation is {wf.status}, not in USER_EDITING state")

        document = wf.document or wf.input_text
        existing_cost = wf.cost_breakdown or {}

    # Run structure step
    tracker = CostTracker()
    ctx_token = set_tracker(tracker)
    trace_handler = TraceCallbackHandler(
        workflow_id=generation_id,
        emit_callback=lambda data: _emit(generation_id, "trace", data),
    )
    try:
        from app.orchestrator.graph import WorkflowState, finalize_workflow

        state: WorkflowState = {
            "input": "",
            "document": document,
            "context": {},
            "round": 0,
            "critiques": [],
            "quality_score": 0,
            "status": "USER_EDITING",
            "structured_output": None,
            "discovery_questions": None,
            "discovery_answers": None,
            "qa_critique": None,
            "dev_critique": None,
            "po_critique": None,
            "qa_doc": None,
            "dev_doc": None,
            "po_doc": None,
            "_trace_handler": trace_handler,
        }

        final_state = await finalize_workflow.ainvoke(
            state,
            config={"callbacks": [trace_handler]},
        )

        async for session in get_session():
            await trace_handler.persist(cast(Any, session))

        # Merge cost data
        finalize_cost = tracker.to_dict()
        merged_cost = {
            "total_input_tokens": existing_cost.get("total_input_tokens", 0) + finalize_cost["total_input_tokens"],
            "total_output_tokens": existing_cost.get("total_output_tokens", 0) + finalize_cost["total_output_tokens"],
            "total_cost_usd": round(existing_cost.get("total_cost_usd", 0) + finalize_cost["total_cost_usd"], 6),
            "agents": {**existing_cost.get("agents", {}), **finalize_cost["agents"]},
        }

        # Update DB
        async for session in get_session():
            wf = await session.get(Workflow, uuid.UUID(generation_id))
            if wf:
                wf.structured_output = final_state.get("structured_output")
                wf.status = "READY_TO_PUSH"
                wf.cost_breakdown = merged_cost
                await session.commit()

        _emit(generation_id, "complete", {
            "generationId": generation_id,
            "message": "Generation complete",
            "structured": final_state.get("structured_output") is not None,
        })

        return {
            "id": generation_id,
            "status": "READY_TO_PUSH",
            "structuredOutput": final_state.get("structured_output"),
            "costBreakdown": merged_cost,
        }
    except Exception as e:
        _emit(generation_id, "error", {
            "generationId": generation_id,
            "error": str(e),
        })
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        clear_tracker(ctx_token)


class DiscoveryAnswersInput(BaseModel):
    answers: list[dict]


@router.post("/generation/{generation_id}/discovery-answers", dependencies=[Depends(auth_dependency)])
async def submit_discovery_answers(generation_id: str, body: DiscoveryAnswersInput):
    """Submit answers to discovery questions and resume the main workflow."""
    global _active_generation
    from gamole_db import Workflow, get_session

    # Load workflow from DB
    questions: list = []
    context: dict = {}
    input_text = ""
    async for session in get_session():
        wf = await session.get(Workflow, uuid.UUID(generation_id))
        if not wf:
            raise HTTPException(status_code=404, detail="Generation not found")
        if wf.status != "AWAITING_DISCOVERY":
            raise HTTPException(
                status_code=400,
                detail=f"Generation is {wf.status}, not AWAITING_DISCOVERY",
            )

        # Load discovery data from state_json
        discovery_data = (wf.state_json or {}).get("discovery", {})
        questions = discovery_data.get("questions", [])
        context = discovery_data.get("context", {})

        # Validate answer count
        if len(body.answers) != len(questions):
            raise HTTPException(
                status_code=422,
                detail=f"Expected {len(questions)} answers, got {len(body.answers)}",
            )

        # Validate non-empty answers
        for ans in body.answers:
            if not ans.get("answer", "").strip():
                raise HTTPException(status_code=422, detail="All answers must be non-empty")

        input_text = wf.input_text

    # Call enrich_document
    from gamole_ai.agents.discovery import enrich_document
    from gamole_types.schemas.discovery import (
        DiscoveryAnswer,
        DiscoveryEnrichmentInput,
        DiscoveryQuestion,
    )

    discovery_questions = [DiscoveryQuestion(**q) for q in questions]
    discovery_answers = [DiscoveryAnswer(**a) for a in body.answers]
    enrich_input = DiscoveryEnrichmentInput(
        original_input=input_text,
        context=json.dumps(context),
        questions=discovery_questions,
        answers=discovery_answers,
    )
    enrichment_result = await enrich_document(enrich_input)
    enriched_document = enrichment_result.enriched_document

    # Re-retrieve RAG context using enriched document for better relevance
    from gamole_ai.context_formatter import format_context
    from gamole_ai.reranker import rerank
    from gamole_ai.retrieval import retrieve_context

    fresh_bundle = await retrieve_context(enriched_document)
    if fresh_bundle.code_chunks:
        fresh_bundle.code_chunks = rerank(fresh_bundle.code_chunks, enriched_document)
    format_context(fresh_bundle)
    fresh_context = fresh_bundle.model_dump(by_alias=True)

    # Persist enriched document + answers + fresh context to DB
    async for session in get_session():
        wf = await session.get(Workflow, uuid.UUID(generation_id))
        if wf:
            wf.document = enriched_document
            wf.status = "CONTEXT_RETRIEVED"
            existing_state = wf.state_json or {}
            existing_state.setdefault("discovery", {})
            existing_state["discovery"]["answers"] = [a.model_dump() for a in discovery_answers]
            existing_state["discovery"]["enriched_document"] = enriched_document
            wf.state_json = existing_state
            await session.commit()

    # Re-acquire lock and spawn main workflow with fresh context
    _active_generation = {"id": generation_id}
    asyncio.create_task(_run_main_workflow(generation_id, input_text, enriched_document, fresh_context))

    return {"status": "running"}


@router.get("/generation/{generation_id}/stream")
async def stream_generation(generation_id: str):
    """SSE endpoint for streaming generation progress. Public (UUID = capability token)."""

    queue: asyncio.Queue = asyncio.Queue()
    _event_queues.setdefault(generation_id, []).append(queue)

    async def event_generator():
        for event in _generation_events.get(generation_id, []):
            yield {"event": event["type"], "data": json.dumps(event)}

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {"event": event["type"], "data": json.dumps(event)}
                    if event["type"] in ("complete", "error"):
                        break
                except asyncio.TimeoutError:
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({
                            "type": "heartbeat",
                            "data": {"generationId": generation_id},
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }),
                    }
        finally:
            queues = _event_queues.get(generation_id, [])
            if queue in queues:
                queues.remove(queue)

    return EventSourceResponse(event_generator())
