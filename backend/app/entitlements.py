from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Case, Plan, User


def plan_for(db: Session, user: User) -> Plan:
    code = user.subscription.plan_code if user.subscription and user.subscription.status == "active" else "free"
    plan = db.get(Plan, code) or db.get(Plan, "free")
    if plan is None:
        raise RuntimeError("Plans are not seeded; run `python -m app.cli seed`")
    return plan


def limit(db: Session, user: User, key: str) -> int | None:
    """Returns the numeric limit for an entitlement, or None for unlimited."""
    value = plan_for(db, user).entitlements.get(key, 0)
    return None if value is None else int(value)


def open_case_count(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(Case).where(Case.owner_id == user.id, Case.status == "open"))
