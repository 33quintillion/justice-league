"""Private case workspaces. Every query is scoped to the owner; other users' cases return 404."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import current_user, verified_user
from ..entitlements import limit, open_case_count
from ..models import Case, CaseEvent, Jurisdiction, User
from ..schemas import CaseEventIn, CaseEventOut, CaseIn, CaseOut, CasePatch, CaseSummaryOut

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _owned_case(db: Session, user: User, case_id: uuid.UUID) -> Case:
    case = db.scalar(select(Case).where(Case.id == case_id, Case.owner_id == user.id))
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case


def _check_jurisdiction(db: Session, code: str) -> None:
    j = db.get(Jurisdiction, code)
    if j is None or not j.enabled:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unsupported jurisdiction")


def _check_case_limit(db: Session, user: User) -> None:
    max_cases = limit(db, user, "max_open_cases")
    if max_cases is not None and open_case_count(db, user) >= max_cases:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Your plan allows {max_cases} open case(s). Close a case or change plan to add more.",
        )


@router.get("", response_model=list[CaseSummaryOut])
def list_cases(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Case).where(Case.owner_id == user.id).order_by(Case.updated_at.desc())).all()


@router.post("", response_model=CaseOut, status_code=201)
def create_case(body: CaseIn, request: Request, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    _check_jurisdiction(db, body.jurisdiction_code)
    _check_case_limit(db, user)
    case = Case(owner_id=user.id, **body.model_dump())
    db.add(case)
    db.flush()
    audit.record(db, "case.created", actor_id=user.id, target_type="case", target_id=case.id, request=request)
    db.commit()
    return case


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _owned_case(db, user, case_id)


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(case_id: uuid.UUID, body: CasePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = _owned_case(db, user, case_id)
    changes = body.model_dump(exclude_unset=True)
    if "jurisdiction_code" in changes:
        _check_jurisdiction(db, changes["jurisdiction_code"])
    if changes.get("status") == "open" and case.status == "closed":
        _check_case_limit(db, user)
    for k, v in changes.items():
        if v is not None:
            setattr(case, k, v)
    db.commit()
    db.refresh(case)
    return case


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: uuid.UUID, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = _owned_case(db, user, case_id)
    db.delete(case)
    audit.record(db, "case.deleted", actor_id=user.id, target_type="case", target_id=case_id, request=request)
    db.commit()


@router.post("/{case_id}/events", response_model=CaseEventOut, status_code=201)
def add_event(case_id: uuid.UUID, body: CaseEventIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = _owned_case(db, user, case_id)
    ev = CaseEvent(case_id=case.id, origin="user", **body.model_dump())
    db.add(ev)
    db.commit()
    return ev


@router.delete("/{case_id}/events/{event_id}", status_code=204)
def delete_event(case_id: uuid.UUID, event_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = _owned_case(db, user, case_id)
    ev = db.scalar(select(CaseEvent).where(CaseEvent.id == event_id, CaseEvent.case_id == case.id))
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    db.delete(ev)
    db.commit()
