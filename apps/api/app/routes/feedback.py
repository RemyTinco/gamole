"""Feedback endpoints: track post-push edits to improve prompts over time."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from ..auth.middleware import auth_dependency

router = APIRouter()


class FeedbackInput(BaseModel):
    edited_stories: list[dict]
    notes: str | None = None


@router.post("/feedback/{generation_id}", dependencies=[Depends(auth_dependency)])
async def submit_feedback(generation_id: str, body: FeedbackInput):
    """Submit edited versions of stories for a generation (post-Linear push feedback)."""
    from gamole_db import DocumentVersion, Workflow, get_session

    async for session in get_session():
        wf = await session.get(Workflow, uuid.UUID(generation_id))
        if not wf:
            raise HTTPException(status_code=404, detail="Generation not found")

        # Compute diff summary
        original = wf.structured_output or {}
        diff_summary = _compute_diff_summary(original, body.edited_stories)

        # Store feedback as a document version
        dv = DocumentVersion(
            workflow_id=wf.id,
            type="FEEDBACK",
            content_markdown=json.dumps(body.edited_stories),
            feedback_json={
                "notes": body.notes,
                "diff_summary": diff_summary,
                "edited_story_count": len(body.edited_stories),
            },
        )
        session.add(dv)
        await session.commit()

        return {
            "id": str(dv.id),
            "generationId": generation_id,
            "diffSummary": diff_summary,
        }


@router.get("/feedback/stats", dependencies=[Depends(auth_dependency)])
async def feedback_stats():
    """Show statistics about how often stories get edited and which fields change most."""
    from gamole_db import DocumentVersion, get_session

    async for session in get_session():
        # Count feedback entries
        total_result = await session.execute(
            select(func.count(DocumentVersion.id)).where(DocumentVersion.type == "FEEDBACK")
        )
        total_feedback = total_result.scalar() or 0

        # Count total generations that received feedback
        gen_result = await session.execute(
            select(func.count(func.distinct(DocumentVersion.workflow_id))).where(
                DocumentVersion.type == "FEEDBACK"
            )
        )
        generations_with_feedback = gen_result.scalar() or 0

        # Aggregate field change counts from feedback_json
        all_feedback = await session.execute(
            select(DocumentVersion.feedback_json).where(
                DocumentVersion.type == "FEEDBACK",
                DocumentVersion.feedback_json.isnot(None),
            )
        )
        field_changes: dict[str, int] = {}
        total_edited_stories = 0
        for (fj,) in all_feedback:
            if fj and isinstance(fj, dict):
                total_edited_stories += fj.get("edited_story_count", 0)
                for field_name, count in fj.get("diff_summary", {}).get("field_changes", {}).items():
                    field_changes[field_name] = field_changes.get(field_name, 0) + count

        return {
            "totalFeedbackEntries": total_feedback,
            "generationsWithFeedback": generations_with_feedback,
            "totalEditedStories": total_edited_stories,
            "fieldChanges": field_changes,
        }


def _compute_diff_summary(original_output: dict, edited_stories: list[dict]) -> dict:
    """Compare original structured output with edited stories to identify what changed."""
    original_stories = []
    for epic in original_output.get("epics", []):
        for story in epic.get("stories", []):
            original_stories.append(story)

    field_changes: dict[str, int] = {}
    stories_changed = 0

    for edited in edited_stories:
        # Try to match by title
        matched = None
        for orig in original_stories:
            if orig.get("title") == edited.get("original_title", edited.get("title")):
                matched = orig
                break

        if matched:
            changed = False
            for field in ["title", "description", "acceptanceCriteria", "assumptions", "technicalNotes"]:
                orig_val = matched.get(field)
                edit_val = edited.get(field)
                if orig_val != edit_val and edit_val is not None:
                    field_changes[field] = field_changes.get(field, 0) + 1
                    changed = True
            if changed:
                stories_changed += 1
        else:
            stories_changed += 1  # New story

    return {
        "stories_changed": stories_changed,
        "field_changes": field_changes,
    }
