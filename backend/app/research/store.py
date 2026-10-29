"""Shared by manual uploads and the official-source importer: store an original and its sections."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..models import LegalSource, SourceDocument, SourceSection
from . import ingest


def store_document(
    db: Session, src: LegalSource, data: bytes, *, filename: str, retrieved_from_url: str, retrieved_at: date,
    uploaded_by: uuid.UUID | None, declared_type: str | None = None,
) -> tuple[SourceDocument, list[ingest.ParsedSection]]:
    """Extracts and splits the file, makes it the source's current document and sends the source for review.

    Raises ingest.IngestError for unreadable files. The caller audits and commits.
    """
    media_type = ingest.sniff_media_type(data, declared_type)
    text = ingest.extract_text(data, media_type)
    parsed = ingest.split_sections(text, src.source_type, src.title)
    db.execute(update(SourceDocument).where(SourceDocument.source_id == src.id).values(is_current=False))
    doc = SourceDocument(
        source_id=src.id, filename=filename[:300], media_type=media_type, sha256=ingest.sha256(data),
        size_bytes=len(data), content=data, retrieved_from_url=retrieved_from_url, retrieved_at=retrieved_at,
        uploaded_by=uploaded_by, is_current=True, extracted_chars=len(text),
    )
    db.add(doc)
    db.flush()
    db.add_all(
        SourceSection(source_id=src.id, document_id=doc.id, ordinal=i, ref=p.ref, ref_key=p.ref_key,
                      heading=p.heading[:500], text=p.text)
        for i, p in enumerate(parsed)
    )
    src.review_status = "pending_review"
    src.reviewed_by = None
    return doc, parsed
