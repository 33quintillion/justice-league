import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog


def record(
    db: Session,
    action: str,
    *,
    actor_id: uuid.UUID | None,
    target_type: str = "",
    target_id: str | uuid.UUID = "",
    details: dict | None = None,
    request: Request | None = None,
) -> None:
    """Adds an audit row to the current transaction. Callers commit."""
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            details=details or {},
            ip=(request.client.host if request and request.client else ""),
        )
    )
