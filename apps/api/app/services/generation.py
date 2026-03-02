"""Generation service - orchestrates the LangGraph workflow."""

from ..orchestrator.graph import run_workflow


async def start_generation(input_text: str, workspace_id: str) -> dict:
    """Start a new generation workflow."""
    result = await run_workflow(input_text)
    return result
