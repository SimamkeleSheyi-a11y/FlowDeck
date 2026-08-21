"""
The single write path for activity history. Every other app that wants to
record something calls log_activity() rather than creating ActivityEvent
rows directly — keeps "never trust the frontend to generate authoritative
history" (Phase 1 doc, Section 8) true at the code level too: there's
exactly one place events get written, and it's always called from inside a
view after a mutation has already succeeded server-side.
"""
from .models import ActivityEvent


def log_activity(
    *,
    actor,
    event_type,
    workspace=None,
    project=None,
    task=None,
    target_type: str = "",
    target_id=None,
    metadata: dict | None = None,
) -> ActivityEvent:
    return ActivityEvent.objects.create(
        actor=actor,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        workspace=workspace,
        project=project,
        task=task,
        metadata=metadata or {},
    )
