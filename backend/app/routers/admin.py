"""Admin console API. Every mutation is audited and requires a stated reason where it affects a user.

No endpoint here returns case content, timelines or documents.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import require
from ..models import AuditLog, AuthSession, Case, FeatureFlag, Jurisdiction, LegalSource, Plan, Subscription, User, UserRole
from ..permissions import Perm, Role
from ..schemas import (
    AdminUserOut, AuditOut, FlagIn, FlagOut, JurisdictionOut, JurisdictionPatch, PlanOut, PlanPatch,
    RolesIn, SubscriptionIn, SuspendIn,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _user_out(u: User, case_count: int) -> AdminUserOut:
    return AdminUserOut(
        id=u.id, email=u.email, display_name=u.display_name, email_verified=u.email_verified_at is not None,
        is_suspended=u.is_suspended, roles=sorted(u.role_names),
        plan_code=u.subscription.plan_code if u.subscription else "free", created_at=u.created_at,
        case_count=case_count,
    )


def _get_user(db: Session, user_id: uuid.UUID) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return u


def _case_count(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Case).where(Case.owner_id == user_id))


# ---- users ----
@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    q: str = Query(default="", max_length=200), limit: int = Query(default=50, le=200), offset: int = 0,
    _: User = Depends(require(Perm.USERS_READ)), db: Session = Depends(get_db),
):
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q.lower()}%"))
    return [_user_out(u, _case_count(db, u.id)) for u in db.scalars(stmt).all()]


@router.put("/users/{user_id}/roles", response_model=AdminUserOut)
def set_roles(
    user_id: uuid.UUID, body: RolesIn, request: Request,
    actor: User = Depends(require(Perm.ROLES_MANAGE)), db: Session = Depends(get_db),
):
    wanted = set(body.roles)
    unknown = wanted - set(Role._value2member_map_)
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown roles: {', '.join(sorted(unknown))}")
    target = _get_user(db, user_id)
    if target.id == actor.id and Role.SYSADMIN not in wanted:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot remove your own sysadmin role")
    before = target.role_names
    target.roles = [r for r in target.roles if r.role in wanted] + [
        UserRole(role=r, granted_by=actor.id) for r in wanted - before
    ]
    audit.record(db, "admin.roles_changed", actor_id=actor.id, target_type="user", target_id=target.id,
                 details={"before": sorted(before), "after": sorted(wanted), "reason": body.reason}, request=request)
    db.commit()
    db.refresh(target)
    return _user_out(target, _case_count(db, target.id))


@router.put("/users/{user_id}/suspension", response_model=AdminUserOut)
def set_suspension(
    user_id: uuid.UUID, body: SuspendIn, request: Request,
    actor: User = Depends(require(Perm.USERS_SUSPEND)), db: Session = Depends(get_db),
):
    target = _get_user(db, user_id)
    if target.id == actor.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot suspend yourself")
    if Role.SYSADMIN in target.role_names and Role.SYSADMIN not in actor.role_names:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a sysadmin can suspend a sysadmin")
    target.is_suspended = body.suspended
    if body.suspended:
        db.query(AuthSession).filter(AuthSession.user_id == target.id).delete()
    audit.record(db, "admin.suspension_changed", actor_id=actor.id, target_type="user", target_id=target.id,
                 details={"suspended": body.suspended, "reason": body.reason}, request=request)
    db.commit()
    return _user_out(target, _case_count(db, target.id))


@router.put("/users/{user_id}/subscription", response_model=AdminUserOut)
def set_subscription(
    user_id: uuid.UUID, body: SubscriptionIn, request: Request,
    actor: User = Depends(require(Perm.SUBSCRIPTIONS_MANAGE)), db: Session = Depends(get_db),
):
    if db.get(Plan, body.plan_code) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown plan")
    target = _get_user(db, user_id)
    before = target.subscription.plan_code if target.subscription else None
    if target.subscription is None:
        target.subscription = Subscription(plan_code=body.plan_code)
    else:
        target.subscription.plan_code = body.plan_code
        target.subscription.status = "active"
    audit.record(db, "admin.subscription_changed", actor_id=actor.id, target_type="user", target_id=target.id,
                 details={"before": before, "after": body.plan_code, "reason": body.reason}, request=request)
    db.commit()
    return _user_out(target, _case_count(db, target.id))


# ---- plans ----
@router.get("/plans", response_model=list[PlanOut])
def list_plans(_: User = Depends(require(Perm.PLANS_MANAGE)), db: Session = Depends(get_db)):
    return db.scalars(select(Plan).order_by(Plan.sort_order)).all()


@router.patch("/plans/{code}", response_model=PlanOut)
def update_plan(
    code: str, body: PlanPatch, request: Request,
    actor: User = Depends(require(Perm.PLANS_MANAGE)), db: Session = Depends(get_db),
):
    plan = db.get(Plan, code)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    changes = body.model_dump(exclude_unset=True, exclude={"clear_price"})
    if body.entitlements is not None:
        for k, v in body.entitlements.items():
            if v is not None and not isinstance(v, (int, bool)):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Entitlement {k} must be a number, boolean or null")
    if code == "free" and (body.price_minor or 0) > 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The free plan cannot have a price")
    for k, v in changes.items():
        if v is not None:
            setattr(plan, k, v)
    if body.clear_price:
        plan.price_minor = None
    audit.record(db, "admin.plan_updated", actor_id=actor.id, target_type="plan", target_id=code,
                 details=body.model_dump(mode="json", exclude_unset=True), request=request)
    db.commit()
    return plan


# ---- jurisdictions ----
@router.get("/jurisdictions", response_model=list[JurisdictionOut])
def all_jurisdictions(_: User = Depends(require(Perm.JURISDICTIONS_MANAGE)), db: Session = Depends(get_db)):
    return db.scalars(select(Jurisdiction).order_by(Jurisdiction.kind, Jurisdiction.name)).all()


@router.patch("/jurisdictions/{code}", response_model=JurisdictionOut)
def update_jurisdiction(
    code: str, body: JurisdictionPatch, request: Request,
    actor: User = Depends(require(Perm.JURISDICTIONS_MANAGE)), db: Session = Depends(get_db),
):
    j = db.get(Jurisdiction, code)
    if j is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Jurisdiction not found")
    j.enabled = body.enabled
    audit.record(db, "admin.jurisdiction_changed", actor_id=actor.id, target_type="jurisdiction", target_id=code,
                 details={"enabled": body.enabled}, request=request)
    db.commit()
    return j


# ---- feature flags ----
@router.get("/flags", response_model=list[FlagOut])
def list_flags(_: User = Depends(require(Perm.FLAGS_MANAGE)), db: Session = Depends(get_db)):
    return db.scalars(select(FeatureFlag).order_by(FeatureFlag.key)).all()


@router.put("/flags/{key}", response_model=FlagOut)
def set_flag(
    key: str, body: FlagIn, request: Request,
    actor: User = Depends(require(Perm.FLAGS_MANAGE)), db: Session = Depends(get_db),
):
    f = db.get(FeatureFlag, key)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flag not found")
    f.enabled = body.enabled
    audit.record(db, "admin.flag_changed", actor_id=actor.id, target_type="flag", target_id=key,
                 details={"enabled": body.enabled}, request=request)
    db.commit()
    return f


# ---- audit & health ----
@router.get("/audit", response_model=list[AuditOut])
def audit_log(
    action: str | None = None, limit: int = Query(default=100, le=500),
    _: User = Depends(require(Perm.AUDIT_READ)), db: Session = Depends(get_db),
):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return db.scalars(stmt).all()


@router.get("/health")
def system_health(_: User = Depends(require(Perm.HEALTH_READ)), db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    count = lambda m: db.scalar(select(func.count()).select_from(m))  # noqa: E731
    return {
        "database": "ok",
        "alembic_revision": db.scalar(text("select version_num from alembic_version")),
        "counts": {
            "users": count(User), "cases": count(Case), "legal_sources": count(LegalSource),
            "active_sessions": db.scalar(select(func.count()).select_from(AuthSession)
                                         .where(AuthSession.expires_at > datetime.now(timezone.utc))),
        },
    }
