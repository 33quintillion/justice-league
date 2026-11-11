"""Public legal library: verified sources only, no login required (rights information is never paywalled)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from ..catalog import MATTER_TYPES, SOURCE_TYPES
from ..db import get_db
from ..models import LegalSource, SourceDocument, SourceSection
from ..ratelimit import login_limiter
from ..research import citations
from ..research.search import relations_affecting, search, section_with_context, source_card, source_warnings

router = APIRouter(prefix="/api/library", tags=["library"])


def _limit(request: Request, bucket: str, n: int) -> None:
    ip = request.client.host if request.client else "?"
    if not login_limiter.hit(f"{bucket}:{ip}", n, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please wait a minute.")


@router.get("/search")
def library_search(
    request: Request,
    q: str = Query(min_length=2, max_length=300),
    jurisdiction: str | None = Query(default=None, max_length=10),
    practice_area: str | None = None,
    source_type: str | None = None,
    limit: int = Query(default=10, ge=1, le=25),
    db: Session = Depends(get_db),
):
    _limit(request, "search", 60)
    if practice_area and practice_area not in MATTER_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown practice area")
    if source_type and source_type not in SOURCE_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown source type")
    return search(db, q, jurisdiction=jurisdiction, practice_area=practice_area, source_type=source_type, limit=limit)


@router.get("/sources")
def list_verified(practice_area: str | None = None, jurisdiction: str | None = None, db: Session = Depends(get_db)):
    stmt = (
        select(LegalSource, SourceDocument)
        .join(SourceDocument, (SourceDocument.source_id == LegalSource.id) & SourceDocument.is_current.is_(True))
        .where(LegalSource.review_status == "verified")
        .order_by(LegalSource.title)
    )
    if practice_area:
        stmt = stmt.where(cast(LegalSource.practice_areas, JSONB).op("?")(practice_area))
    if jurisdiction:
        stmt = stmt.where(LegalSource.jurisdiction_code == jurisdiction)
    rows = db.execute(stmt).all()
    rels = relations_affecting(db, [s.id for s, _ in rows])
    return [
        source_card(s, d, rels.get(s.id, [])) | {"warnings": source_warnings(s, rels.get(s.id, []))}
        for s, d in rows
    ]


@router.get("/sources/{source_id}")
def verified_source(source_id: uuid.UUID, db: Session = Depends(get_db)):
    row = db.execute(
        select(LegalSource, SourceDocument)
        .join(SourceDocument, (SourceDocument.source_id == LegalSource.id) & SourceDocument.is_current.is_(True))
        .where(LegalSource.id == source_id, LegalSource.review_status == "verified")
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found in the verified library")
    src, doc = row
    rels = relations_affecting(db, [src.id]).get(src.id, [])
    sections = db.scalars(select(SourceSection).where(SourceSection.document_id == doc.id).order_by(SourceSection.ordinal)).all()
    return source_card(src, doc, rels) | {
        "warnings": source_warnings(src, rels),
        "sections": [{"id": str(s.id), "ref": s.ref, "heading": s.heading, "text": s.text,
                      "warnings": [w for w in source_warnings(src, rels, s.ref_key) if w not in source_warnings(src, rels)]}
                     for s in sections],
    }


@router.get("/sections/{section_id}")
def section(section_id: uuid.UUID, db: Session = Depends(get_db)):
    s = section_with_context(db, section_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Section not found in the verified library")
    return s


class VerifyIn(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)


@router.post("/verify-citations")
def verify_citations(body: VerifyIn, request: Request, db: Session = Depends(get_db)):
    """Stateless: the submitted text is checked and not stored."""
    _limit(request, "verify", 20)
    return citations.verify_text(db, body.text)
