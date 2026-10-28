import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import CSRF_COOKIE, SESSION_COOKIE, current_user
from ..models import Case, Jurisdiction, User, UserSettings
from ..schemas import CaseOut, PasswordConfirmIn, SettingsIn, SettingsOut
from ..security import verify_password

router = APIRouter(prefix="/api/account", tags=["account"])


def _settings(user: User) -> UserSettings:
    if user.settings is None:
        user.settings = UserSettings()
    return user.settings


def settings_out(user: User) -> SettingsOut:
    s = _settings(user)
    return SettingsOut(
        display_name=user.display_name,
        preferred_language=s.preferred_language,
        country_code=s.country_code,
        state_code=s.state_code,
        retention_days=s.retention_days,
        consent_ai_processing=s.consent_ai_processing,
        consent_training_use=s.consent_training_use,
        consent_updated_at=s.consent_updated_at,
    )


@router.get("/settings", response_model=SettingsOut)
def get_settings_(user: User = Depends(current_user)):
    return settings_out(user)


@router.patch("/settings", response_model=SettingsOut)
def update_settings(body: SettingsIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _settings(user)
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
    if body.preferred_language is not None:
        s.preferred_language = body.preferred_language
    if body.clear_state:
        s.state_code = None
    elif body.state_code is not None:
        j = db.get(Jurisdiction, body.state_code)
        if j is None or not j.enabled or j.parent_code != s.country_code:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown state or union territory")
        s.state_code = j.code
    if body.keep_until_deleted:
        s.retention_days = None
    elif body.retention_days is not None:
        s.retention_days = body.retention_days
    consent_changed = {}
    for field in ("consent_ai_processing", "consent_training_use"):
        v = getattr(body, field)
        if v is not None and v != getattr(s, field):
            setattr(s, field, v)
            consent_changed[field] = v
    if consent_changed:
        s.consent_updated_at = datetime.now(timezone.utc)
        audit.record(db, "account.consent_changed", actor_id=user.id, target_type="user", target_id=user.id,
                     details=consent_changed, request=request)
    db.add(user)
    db.commit()
    return settings_out(user)


@router.get("/export")
def export_account(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Everything we hold about the user, as JSON. Password hashes and session tokens are excluded."""
    cases = db.scalars(select(Case).where(Case.owner_id == user.id).order_by(Case.created_at)).all()
    audit.record(db, "account.exported", actor_id=user.id, target_type="user", target_id=user.id, request=request)
    db.commit()
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "email_verified_at": user.email_verified_at.isoformat() if user.email_verified_at else None,
            "created_at": user.created_at.isoformat(),
            "plan_code": user.subscription.plan_code if user.subscription else "free",
        },
        "settings": settings_out(user).model_dump(mode="json"),
        "cases": [CaseOut.model_validate(c).model_dump(mode="json") for c in cases],
    }
    return Response(
        content=json.dumps(payload, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="justice-ai-export.json"'},
    )


@router.post("/delete", status_code=204)
def delete_account(
    body: PasswordConfirmIn, request: Request, response: Response,
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password is incorrect")
    user_id = user.id
    # Cascades remove settings, sessions, roles, subscription, cases and their timelines.
    db.delete(user)
    audit.record(db, "account.deleted", actor_id=user_id, target_type="user", target_id=user_id, request=request)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
