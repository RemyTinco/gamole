"""LangGraph workflow: retrieve_context -> draft -> [qa, dev, po] parallel -> merge -> supervise -> (USER_EDITING pause) -> structure.

Conditional edge: loop back to draft if quality below threshold and round < 5.
Max 5 iterations. Final step structures the refined document into epics/stories.

Features:
- Parallel QA/Dev/PO reviews (fan-out/fan-in)
- Human-in-the-loop: USER_EDITING pause between supervisor approval and structuring
- Cost tracking per agent call
"""

import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from gamole_ai.agents.dev import run as run_dev
from gamole_ai.agents.draft import run as run_draft
from gamole_ai.agents.po import run as run_po
from gamole_ai.agents.qa import run as run_qa
from gamole_ai.agents.structurer import run as run_structurer
from gamole_ai.agents.supervisor import run as run_supervisor
from gamole_ai.agents.types import MAX_CRITIQUE_ROUNDS, AgentInput
from gamole_ai.cost_tracker import track_usage
from gamole_ai.retrieval import retrieve_context


class WorkflowState(TypedDict):
    input: str
    document: str
    context: dict[str, Any]
    round: int
    critiques: list[str]
    quality_score: float
    status: str
    structured_output: dict[str, Any] | None
    # Parallel review results
    qa_critique: str | None
    dev_critique: str | None
    po_critique: str | None
    qa_doc: str | None
    dev_doc: str | None
    po_doc: str | None


def _to_agent_input(state: WorkflowState, bump_round: bool = False) -> AgentInput:
    return AgentInput(
        document=state["document"],
        context=json.dumps(state["context"]),
        round=max(1, state["round"] + (1 if bump_round else 0)),
        previous_critiques=state["critiques"],
    )


def _estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ≈ 4 chars."""
    return len(text) // 4


async def retrieve_context_node(state: WorkflowState) -> dict:
    bundle = await retrieve_context(state["input"])
    return {
        "context": bundle.model_dump(by_alias=True),
        "status": "CONTEXT_RETRIEVED",
    }


async def draft_node(state: WorkflowState) -> dict:
    agent_input = _to_agent_input(state, bump_round=True)
    result = await run_draft(agent_input)
    input_tokens = _estimate_tokens(agent_input.document + agent_input.context)
    output_tokens = _estimate_tokens((result.revised_doc or "") + result.critique)
    track_usage("draft", input_tokens, output_tokens)
    return {
        "document": result.revised_doc or state["document"],
        "critiques": state["critiques"] + [result.critique],
        "round": state["round"] + 1,
        "status": "DRAFT_GENERATED",
    }


async def review_qa_node(state: WorkflowState) -> dict:
    agent_input = _to_agent_input(state)
    result = await run_qa(agent_input)
    input_tokens = _estimate_tokens(agent_input.document + agent_input.context)
    output_tokens = _estimate_tokens((result.revised_doc or "") + result.critique)
    track_usage("qa", input_tokens, output_tokens)
    return {
        "qa_doc": result.revised_doc or state["document"],
        "qa_critique": result.critique,
    }


async def review_dev_node(state: WorkflowState) -> dict:
    agent_input = _to_agent_input(state)
    result = await run_dev(agent_input)
    input_tokens = _estimate_tokens(agent_input.document + agent_input.context)
    output_tokens = _estimate_tokens((result.revised_doc or "") + result.critique)
    track_usage("dev", input_tokens, output_tokens)
    return {
        "dev_doc": result.revised_doc or state["document"],
        "dev_critique": result.critique,
    }


async def review_po_node(state: WorkflowState) -> dict:
    agent_input = _to_agent_input(state)
    result = await run_po(agent_input)
    input_tokens = _estimate_tokens(agent_input.document + agent_input.context)
    output_tokens = _estimate_tokens((result.revised_doc or "") + result.critique)
    track_usage("po", input_tokens, output_tokens)
    return {
        "po_doc": result.revised_doc or state["document"],
        "po_critique": result.critique,
    }


async def merge_reviews_node(state: WorkflowState) -> dict:
    """Merge parallel review results: pick the last revised doc and combine critiques."""
    # Use PO doc as final (last reviewer), or fallback
    merged_doc = state.get("po_doc") or state.get("dev_doc") or state.get("qa_doc") or state["document"]
    new_critiques = []
    for c in [state.get("qa_critique"), state.get("dev_critique"), state.get("po_critique")]:
        if c:
            new_critiques.append(c)
    return {
        "document": merged_doc,
        "critiques": state["critiques"] + new_critiques,
        "status": "PO_REVIEWED",
    }


async def supervise_node(state: WorkflowState) -> dict:
    agent_input = _to_agent_input(state)
    result = await run_supervisor(agent_input)
    input_tokens = _estimate_tokens(agent_input.document + agent_input.context)
    output_tokens = _estimate_tokens(result.reason)
    track_usage("supervisor", input_tokens, output_tokens)
    return {
        "quality_score": result.quality_score or state["quality_score"],
        "status": "QUALITY_EVALUATED" if result.ready or result.force_stop else "SUPERVISOR_REFINED",
        "_supervisor_ready": result.ready,
        "_supervisor_force_stop": result.force_stop,
    }


async def user_editing_node(state: WorkflowState) -> dict:
    """Pause point for human-in-the-loop editing. The workflow stops here.
    The generation runner detects USER_EDITING status and pauses."""
    return {
        "status": "USER_EDITING",
    }


async def structure_node(state: WorkflowState) -> dict:
    """Convert the refined prose document into structured epics/stories."""
    output = await run_structurer(state["document"])
    input_tokens = _estimate_tokens(state["document"])
    output_text = json.dumps(output.model_dump(by_alias=True))
    output_tokens = _estimate_tokens(output_text)
    track_usage("structurer", input_tokens, output_tokens)
    return {
        "structured_output": output.model_dump(by_alias=True),
        "status": "STRUCTURED",
    }


def should_continue(state: WorkflowState) -> str:
    """Conditional edge: loop back to draft or go to user editing."""
    if state["status"] == "QUALITY_EVALUATED":
        return "user_editing"
    if state.get("_supervisor_ready") or state.get("_supervisor_force_stop"):
        return "user_editing"
    if state["round"] >= MAX_CRITIQUE_ROUNDS:
        return "user_editing"
    return "draft"


# Build the graph
graph = StateGraph(WorkflowState)

graph.add_node("retrieve_context", retrieve_context_node)
graph.add_node("draft", draft_node)
graph.add_node("review_qa", review_qa_node)
graph.add_node("review_dev", review_dev_node)
graph.add_node("review_po", review_po_node)
graph.add_node("merge_reviews", merge_reviews_node)
graph.add_node("supervise", supervise_node)
graph.add_node("user_editing", user_editing_node)
graph.add_node("structure", structure_node)

graph.set_entry_point("retrieve_context")
graph.add_edge("retrieve_context", "draft")

# Parallel fan-out: draft -> qa, dev, po simultaneously
graph.add_edge("draft", "review_qa")
graph.add_edge("draft", "review_dev")
graph.add_edge("draft", "review_po")

# Fan-in: all three reviews -> merge
graph.add_edge("review_qa", "merge_reviews")
graph.add_edge("review_dev", "merge_reviews")
graph.add_edge("review_po", "merge_reviews")

graph.add_edge("merge_reviews", "supervise")

graph.add_conditional_edges("supervise", should_continue, {
    "user_editing": "user_editing",
    "draft": "draft",
})

# user_editing is a terminal node for the pre-finalize workflow
graph.add_edge("user_editing", END)

# structure -> END (used separately in finalize flow)
graph.add_edge("structure", END)

workflow = graph.compile()

# Separate graph for the finalize step (structure only)
finalize_graph = StateGraph(WorkflowState)
finalize_graph.add_node("structure", structure_node)
finalize_graph.set_entry_point("structure")
finalize_graph.add_edge("structure", END)
finalize_workflow = finalize_graph.compile()


async def run_workflow(input_text: str) -> dict:
    """Run the full workflow and return the final state."""
    initial_state: WorkflowState = {
        "input": input_text,
        "document": input_text,
        "context": {},
        "round": 0,
        "critiques": [],
        "quality_score": 0,
        "status": "INITIALIZED",
        "structured_output": None,
        "qa_critique": None,
        "dev_critique": None,
        "po_critique": None,
        "qa_doc": None,
        "dev_doc": None,
        "po_doc": None,
    }

    final_state = await workflow.ainvoke(initial_state)
    return dict(final_state)
