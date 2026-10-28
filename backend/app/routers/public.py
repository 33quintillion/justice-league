"""Public, unauthenticated reference data. Essential information is never paywalled."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..catalog import CASE_STAGES, LANGUAGES, MATTER_TYPES
from ..db import get_db
from ..models import FeatureFlag, Jurisdiction, Plan
from ..schemas import JurisdictionOut, PlanOut

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    return {"status": "ok", "database": "ok"}


@router.get("/catalog")
def catalog():
    return {"matter_types": MATTER_TYPES, "case_stages": CASE_STAGES, "languages": LANGUAGES}


@router.get("/jurisdictions", response_model=list[JurisdictionOut])
def jurisdictions(db: Session = Depends(get_db)):
    return db.scalars(
        select(Jurisdiction).where(Jurisdiction.enabled.is_(True)).order_by(Jurisdiction.kind, Jurisdiction.name)
    ).all()


@router.get("/plans", response_model=list[PlanOut])
def plans(db: Session = Depends(get_db)):
    return db.scalars(select(Plan).where(Plan.is_public.is_(True)).order_by(Plan.sort_order)).all()


@router.get("/features")
def features(db: Session = Depends(get_db)):
    """Enabled flags only, so the UI can show which modules are live."""
    return {f.key: f.enabled for f in db.scalars(select(FeatureFlag)).all()}
