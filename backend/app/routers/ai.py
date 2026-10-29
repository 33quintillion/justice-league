"""AI roles: Ask AI, AI Lawyer, AI Advocate and AI Judge. Answers are private to their owner."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import current_user, verified_user
from ..models import AIAnswer, Case, FeatureFlag, Jurisdiction, User
from ..ratelimit import login_limiter
from ..ai import pipeline, prompts, urgency
from ..ai.provider import ProviderError, get_provider
from ..ai.validate import OutputInvalid

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _flag_on(db: Session, key: str) -> bool:
    f = db.get(FeatureFlag, key)
    return bool(f and f.enabled)


@router.get("/status")
def ai_status(request: Request, db: Session = Depends(get_db)):
    p = get_provider(request.app)
    return {
        "configured": p is not None,
        "model": p.model if p else None,
        "roles": {k: {"title": v["title"], "needs_case": v["needs_case"], "enabled": _flag_on(db, v["flag"])} for k, v in prompts.ROLES.items()},
        "judge_label": prompts.JUDGE_LABEL,
        "disclaimer": prompts.DISCLAIMER,
    }


class UrgencyIn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


@router.post("/urgency")
def check_urgency(body: UrgencyIn, request: Request):
    """Public and stateless: no login, no consent and nothing stored, so it can never block emergency help."""
    ip = request.client.host if request.client else "?"
    if not login_limiter.hit(f"urgency:{ip}", 120, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. If you are in danger, call 112.")
    return urgency.detect(body.text)


@router.get("/usage")
def my_usage(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return pipeline.usage(db, user)


class AskIn(BaseModel):
    question: str = Field(min_length=5, max_length=4000)
    case_id: uuid.UUID | None = None
    jurisdiction_code: str | None = Field(default=None, max_length=10)


@router.post("/{role}", status_code=201)
def ask(role: str, body: AskIn, request: Request, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    spec = prompts.ROLES.get(role)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown AI role")
    if not _flag_on(db, spec["flag"]):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"{spec['title']} is not switched on yet.")
    s = user.settings
    if s is None or not s.consent_ai_processing:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Allow AI processing in Settings before using the AI roles. Emergency and rights information stays available without it.")
    provider = get_provider(request.app)
    if provider is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The AI service is not configured on this server yet, so no answer can be generated.")
    case = None
    if body.case_id:
        case = db.scalar(select(Case).where(Case.id == body.case_id, Case.owner_id == user.id))
        if case is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    elif spec["needs_case"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{spec['title']} works on one of your cases. Choose a case first.")
    jurisdiction = body.jurisdiction_code or (case.jurisdiction_code if case else None) or (s.state_code if s else None)
    if jurisdiction and db.get(Jurisdiction, jurisdiction) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown jurisdiction")
    if not login_limiter.hit(f"ai:{user.id}", 10, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many questions in a short time. Please wait a minute.")
    u = pipeline.usage(db, user)
    if u["limit"] is not None and u["used"] >= u["limit"]:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, f"You have used all {u['limit']} AI answers in your plan this month. Rights information and the legal library stay free.")

    try:
        a = pipeline.run(db, provider=provider, user=user, role=role, question=body.question.strip(),
                         jurisdiction=jurisdiction, case=case, language=s.preferred_language if s else "en")
    except ProviderError as e:
        db.rollback()
        audit.record(db, "ai.failed", actor_id=user.id, details={"role": role, "error": type(e).__name__}, request=request)
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    except OutputInvalid as e:
        db.rollback()
        audit.record(db, "ai.failed", actor_id=user.id, details={"role": role, "error": "output_invalid"}, request=request)
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The AI answer did not pass our checks, so we are not showing it. Please try again.") from e
    # The question and answer stay out of the audit log: only that an answer was produced, and how.
    audit.record(db, "ai.answered", actor_id=user.id, target_type="ai_answer", target_id=a.id,
                 details={"role": role, "status": a.status, "llm_called": a.llm_called, "urgency": a.urgency["level"],
                          "sources": len(a.citations), "prompt_version": a.prompt_version}, request=request)
    db.commit()
    return pipeline.answer_out(a)


def _owned(db: Session, user: User, answer_id: uuid.UUID) -> AIAnswer:
    a = db.scalar(select(AIAnswer).where(AIAnswer.id == answer_id, AIAnswer.user_id == user.id, AIAnswer.deleted_at.is_(None)))
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Answer not found")
    return a


@router.get("/answers/mine")
def my_answers(role: str | None = None, case_id: uuid.UUID | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(AIAnswer).where(AIAnswer.user_id == user.id, AIAnswer.deleted_at.is_(None)).order_by(AIAnswer.created_at.desc()).limit(100)
    if role:
        stmt = stmt.where(AIAnswer.role == role)
    if case_id:
        stmt = stmt.where(AIAnswer.case_id == case_id)
    return [{"id": str(a.id), "role": a.role, "question": a.question[:200], "status": a.status,
             "case_id": str(a.case_id) if a.case_id else None, "created_at": a.created_at.isoformat()}
            for a in db.scalars(stmt).all()]


@router.get("/answers/{answer_id}")
def get_answer(answer_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return pipeline.answer_out(_owned(db, user, answer_id))


@router.delete("/answers/{answer_id}", status_code=204)
def delete_answer(answer_id: uuid.UUID, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = _owned(db, user, answer_id)
    a.erase()
    audit.record(db, "ai.answer_deleted", actor_id=user.id, target_type="ai_answer", target_id=answer_id, request=request)
    db.commit()
