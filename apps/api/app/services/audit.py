"""Audit service - append-only audit log."""


async def log_event(event_type: str, workflow_id: str | None = None, payload: dict | None = None) -> None:
    """Write an audit log entry. Append-only — never UPDATE or DELETE."""
    pass
