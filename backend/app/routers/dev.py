"""Development-only endpoints. Not mounted unless JUSTICE_ENV is development or test."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import DevOutboxEmail, User

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.get("/outbox")
def my_outbox(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Shows only the signed-in user's own dev emails, newest first."""
    rows = db.scalars(
        select(DevOutboxEmail).where(DevOutboxEmail.to_email == user.email).order_by(DevOutboxEmail.id.desc()).limit(10)
    ).all()
    return [{"subject": r.subject, "body": r.body, "created_at": r.created_at} for r in rows]
