"""Legal source management: registry, original-document ingestion, review, relations, freshness, links."""
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import audit
from ..catalog import is_official_url
from ..config import get_settings
from ..db import get_db
from ..deps import require
from ..models import Jurisdiction, LegalSource, SourceDocument, SourceRelation, SourceSection, User
from ..permissions import Perm
from ..research import ingest, links
from ..research.search import RELATION_KINDS, relations_affecting, source_warnings
from ..schemas import DocumentOut, RelationIn, ReviewIn, SectionOut, SourceIn, SourceOut, SourcePatch

router = APIRouter(prefix="/api/admin/sources", tags=["admin-sources"])

OFFICIAL_URL_MESSAGE = "Source URL must be an https link on an official government domain (for example indiacode.nic.in or sci.gov.in)"


def _source(db: Session, source_id: uuid.UUID) -> LegalSource:
    src = db.get(LegalSource, source_id)
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    return src


def _current_doc(db: Session, source_id: uuid.UUID) -> SourceDocument | None:
    return db.scalar(select(SourceDocument).where(SourceDocument.source_id == source_id, SourceDocument.is_current.is_(True)))


def _send_back_for_review(src: LegalSource) -> None:
    src.review_status = "pending_review"
    src.reviewed_by = None


@router.get("", response_model=list[SourceOut])
def list_sources(
    review_status: str | None = None, stale: bool = False,
    _: User = Depends(require(Perm.SOURCES_READ)), db: Session = Depends(get_db),
):
    stmt = select(LegalSource).order_by(LegalSource.created_at.desc())
    if review_status:
        stmt = stmt.where(LegalSource.review_status == review_status)
    if stale:
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().reverify_after_days)
        stmt = stmt.where(LegalSource.review_status == "verified", LegalSource.last_verified_at < cutoff)
    return db.scalars(stmt).all()


@router.post("", response_model=SourceOut, status_code=201)
def create_source(
    body: SourceIn, request: Request,
    actor: User = Depends(require(Perm.SOURCES_WRITE)), db: Session = Depends(get_db),
):
    if not is_official_url(body.official_url):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, OFFICIAL_URL_MESSAGE)
    if db.get(Jurisdiction, body.jurisdiction_code) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown jurisdiction")
    src = LegalSource(**body.model_dump(), created_by=actor.id, review_status="pending_review")
    db.add(src)
    db.flush()
    audit.record(db, "source.created", actor_id=actor.id, target_type="legal_source", target_id=src.id, request=request)
    db.commit()
    return src


@router.get("/{source_id}")
def source_detail(source_id: uuid.UUID, _: User = Depends(require(Perm.SOURCES_READ)), db: Session = Depends(get_db)):
    src = _source(db, source_id)
    docs = db.scalars(select(SourceDocument).where(SourceDocument.source_id == src.id).order_by(SourceDocument.uploaded_at.desc())).all()
    cur = next((d for d in docs if d.is_current), None)
    sections = db.scalars(select(SourceSection).where(SourceSection.document_id == cur.id).order_by(SourceSection.ordinal)).all() if cur else []
    rels = relations_affecting(db, [src.id]).get(src.id, [])
    return {
        "source": SourceOut.model_validate(src).model_dump(mode="json"),
        "documents": [DocumentOut.model_validate(d).model_dump(mode="json") for d in docs],
        "sections": [SectionOut.model_validate(s).model_dump(mode="json") for s in sections],
        "relations": rels,
        "warnings": source_warnings(src, rels),
    }


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(
    source_id: uuid.UUID, body: SourcePatch, request: Request,
    actor: User = Depends(require(Perm.SOURCES_WRITE)), db: Session = Depends(get_db),
):
    src = _source(db, source_id)
    changes = body.model_dump(exclude_unset=True, exclude={"reason"})
    for k, v in changes.items():
        setattr(src, k, v)
    _send_back_for_review(src)
    audit.record(db, "source.updated", actor_id=actor.id, target_type="legal_source", target_id=src.id,
                 details={"changes": body.model_dump(mode="json", exclude_unset=True)}, request=request)
    db.commit()
    return src


@router.post("/{source_id}/documents", status_code=201)
async def upload_document(
    source_id: uuid.UUID, request: Request,
    file: UploadFile = File(...),
    retrieved_from_url: str = Form(..., max_length=1000),
    retrieved_at: date = Form(...),
    actor: User = Depends(require(Perm.SOURCES_WRITE)), db: Session = Depends(get_db),
):
    """Stores an officially obtained file, extracts and splits its text, and sends the source for review."""
    src = _source(db, source_id)
    if not is_official_url(retrieved_from_url):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The file must have been downloaded from an official government domain")
    if retrieved_at > date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Retrieval date cannot be in the future")
    data = await file.read(ingest.MAX_UPLOAD_BYTES + 1)
    if len(data) > ingest.MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File is larger than 25 MB")
    try:
        media_type = ingest.sniff_media_type(data, file.content_type)
        text = ingest.extract_text(data, media_type)
    except ingest.IngestError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    parsed = ingest.split_sections(text, src.source_type, src.title)

    db.execute(update(SourceDocument).where(SourceDocument.source_id == src.id).values(is_current=False))
    doc = SourceDocument(
        source_id=src.id, filename=(file.filename or "upload")[:300], media_type=media_type, sha256=ingest.sha256(data),
        size_bytes=len(data), content=data, retrieved_from_url=retrieved_from_url, retrieved_at=retrieved_at,
        uploaded_by=actor.id, is_current=True, extracted_chars=len(text),
    )
    db.add(doc)
    db.flush()
    db.add_all(
        SourceSection(source_id=src.id, document_id=doc.id, ordinal=i, ref=p.ref, ref_key=p.ref_key, heading=p.heading[:500], text=p.text)
        for i, p in enumerate(parsed)
    )
    _send_back_for_review(src)
    audit.record(db, "source.document_uploaded", actor_id=actor.id, target_type="legal_source", target_id=src.id,
                 details={"document_id": str(doc.id), "sha256": doc.sha256, "sections": len(parsed)}, request=request)
    db.commit()
    return {"document": DocumentOut.model_validate(doc).model_dump(mode="json"), "sections": len(parsed),
            "section_refs": [p.ref for p in parsed[:200]]}


@router.get("/{source_id}/documents/{document_id}/original")
def download_original(
    source_id: uuid.UUID, document_id: uuid.UUID,
    _: User = Depends(require(Perm.SOURCES_READ)), db: Session = Depends(get_db),
):
    doc = db.scalar(select(SourceDocument).where(SourceDocument.id == document_id, SourceDocument.source_id == source_id))
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    safe = "".join(c for c in doc.filename if c.isalnum() or c in "._-") or "original"
    return Response(doc.content, media_type=doc.media_type,
                    headers={"Content-Disposition": f'attachment; filename="{safe}"', "X-Content-SHA256": doc.sha256})


@router.post("/{source_id}/review", response_model=SourceOut)
def review_source(
    source_id: uuid.UUID, body: ReviewIn, request: Request,
    actor: User = Depends(require(Perm.SOURCES_REVIEW)), db: Session = Depends(get_db),
):
    src = _source(db, source_id)
    doc = _current_doc(db, src.id)
    if src.created_by == actor.id or (doc and doc.uploaded_by == actor.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "A source must be reviewed by someone other than its author or uploader")
    if body.decision == "verified":
        if doc is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Upload the official document before verifying: we only publish text we hold")
        src.last_verified_at = datetime.now(timezone.utc)
    src.review_status = body.decision
    src.reviewed_by = actor.id
    src.notes = (src.notes + "\n\n" if src.notes else "") + f"[review {body.decision}] {body.notes}"
    audit.record(db, "source.reviewed", actor_id=actor.id, target_type="legal_source", target_id=src.id,
                 details={"decision": body.decision, "document_sha256": doc.sha256 if doc else None}, request=request)
    db.commit()
    return src


@router.post("/{source_id}/relations", status_code=201)
def add_relation(
    source_id: uuid.UUID, body: RelationIn, request: Request,
    actor: User = Depends(require(Perm.SOURCES_WRITE)), db: Session = Depends(get_db),
):
    """Records that this source affects another one (e.g. an amending Act, an overruling judgment)."""
    src = _source(db, source_id)
    target = _source(db, body.target_source_id)
    if body.kind not in RELATION_KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"kind must be one of: {', '.join(RELATION_KINDS)}")
    if target.id == src.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A source cannot affect itself")
    rel = SourceRelation(from_source_id=src.id, to_source_id=target.id, kind=body.kind,
                         to_section_ref=body.target_section_ref.strip().lower(), effective_date=body.effective_date,
                         note=body.note, created_by=actor.id)
    db.add(rel)
    audit.record(db, "source.relation_added", actor_id=actor.id, target_type="legal_source", target_id=target.id,
                 details={"from": str(src.id), "kind": body.kind, "section": rel.to_section_ref}, request=request)
    db.commit()
    return {"id": rel.id}


@router.post("/check-links")
def check_links(request: Request, actor: User = Depends(require(Perm.SOURCES_WRITE)), db: Session = Depends(get_db)):
    sources = db.scalars(select(LegalSource)).all()
    counts = links.check_sources(sources, transport=getattr(request.app.state, "link_transport", None))
    audit.record(db, "source.links_checked", actor_id=actor.id, details=counts, request=request)
    db.commit()
    return counts


@router.get("/-/stats")
def stats(_: User = Depends(require(Perm.SOURCES_READ)), db: Session = Depends(get_db)):
    by_status = dict(db.execute(select(LegalSource.review_status, func.count()).group_by(LegalSource.review_status)).all())
    return {"by_review_status": by_status, "sections": db.scalar(select(func.count()).select_from(SourceSection))}
