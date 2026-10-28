"""Retrieval over verified sources. This is what the AI roles will call before answering (Phase 4)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Float, cast, func, literal_column, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Jurisdiction, LegalSource, SourceDocument, SourceRelation, SourceSection

SEVERE = {"repealed", "overruled", "stayed"}
CAUTION = {"amended", "partially_in_force"}
RELATION_KINDS = ["amends", "repeals", "overrules", "stays", "substitutes", "clarifies", "conflicts_with"]

MARK_START, MARK_END = "⟦", "⟧"  # ⟦ ⟧: highlight markers the UI renders as <mark> without HTML


def jurisdiction_codes(db: Session, code: str | None) -> list[str] | None:
    """A state's search includes central law; central law alone is 'IN'. None means no filter."""
    if not code:
        return None
    j = db.get(Jurisdiction, code)
    if j is None:
        return [code]
    return [j.code] + ([j.parent_code] if j.parent_code else [])


def relations_affecting(db: Session, source_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    out: dict[uuid.UUID, list[dict]] = {}
    if not source_ids:
        return out
    rows = db.execute(
        select(SourceRelation, LegalSource.title, LegalSource.review_status)
        .join(LegalSource, LegalSource.id == SourceRelation.from_source_id)
        .where(SourceRelation.to_source_id.in_(source_ids))
    ).all()
    for rel, by_title, by_status in rows:
        out.setdefault(rel.to_source_id, []).append(
            {
                "kind": rel.kind,
                "section_ref": rel.to_section_ref,
                "by_source_id": str(rel.from_source_id),
                "by_title": by_title,
                "by_source_verified": by_status == "verified",
                "effective_date": rel.effective_date.isoformat() if rel.effective_date else None,
                "note": rel.note,
            }
        )
    return out


def source_warnings(src: LegalSource, relations: list[dict], section_key: str | None = None) -> list[dict]:
    """Plain-language cautions shown next to an authority. Never hidden, never silently resolved."""
    w: list[dict] = []
    if src.legal_status in SEVERE:
        w.append({"level": "severe", "text": f"Marked as {src.legal_status}. It may no longer state the current law."})
    elif src.legal_status in CAUTION:
        w.append({"level": "caution", "text": f"Marked as {src.legal_status.replace('_', ' ')}. Check that this text reflects the current version."})
    elif src.legal_status == "unknown":
        w.append({"level": "caution", "text": "Current legal status has not been confirmed by our reviewers."})
    for r in relations:
        if r["section_ref"] and section_key and r["section_ref"].lower() != section_key:
            continue
        where = f"section {r['section_ref']}" if r["section_ref"] else "this source"
        lvl = "severe" if r["kind"] in ("repeals", "overrules", "stays") else "caution"
        w.append({"level": lvl, "text": f"{r['by_title']} {r['kind']} {where}" + (f" (from {r['effective_date']})" if r["effective_date"] else "") + "."})
    days = get_settings().reverify_after_days
    if src.last_verified_at and src.last_verified_at < datetime.now(timezone.utc) - timedelta(days=days):
        w.append({"level": "caution", "text": f"Last verified more than {days} days ago; re-verification is due."})
    if src.link_status in ("broken", "unreachable"):
        w.append({"level": "caution", "text": "The official link failed our last automatic check."})
    return w


def source_card(src: LegalSource, doc: SourceDocument | None, relations: list[dict]) -> dict:
    return {
        "id": str(src.id),
        "title": src.title,
        "citation": src.citation,
        "source_type": src.source_type,
        "authority_level": src.authority_level,
        "jurisdiction_code": src.jurisdiction_code,
        "publisher": src.publisher,
        "official_url": src.official_url,
        "effective_date": src.effective_date.isoformat() if src.effective_date else None,
        "legal_status": src.legal_status,
        "last_verified_at": src.last_verified_at.isoformat() if src.last_verified_at else None,
        "practice_areas": src.practice_areas,
        # Version of the material used, so answers can record exactly what they relied on.
        "document_sha256": doc.sha256 if doc else None,
        "document_retrieved_at": doc.retrieved_at.isoformat() if doc else None,
        "relations": relations,
    }


def search(
    db: Session,
    q: str,
    *,
    jurisdiction: str | None = None,
    practice_area: str | None = None,
    source_type: str | None = None,
    limit: int = 10,
) -> dict:
    q = q.strip()
    tsq = func.websearch_to_tsquery("english", q)
    vec = literal_column("source_sections.search_vector")
    rank = func.ts_rank_cd(vec, tsq, 32).cast(Float).label("rank")
    headline = func.ts_headline(
        "english", SourceSection.text, tsq,
        f"StartSel={MARK_START}, StopSel={MARK_END}, MaxWords=45, MinWords=20, MaxFragments=2, FragmentDelimiter= … ",
    ).label("snippet")
    stmt = (
        select(SourceSection, LegalSource, SourceDocument, rank, headline)
        .join(LegalSource, LegalSource.id == SourceSection.source_id)
        .join(SourceDocument, SourceDocument.id == SourceSection.document_id)
        .where(vec.op("@@")(tsq))
        .where(LegalSource.review_status == "verified", SourceDocument.is_current.is_(True))
        .order_by(literal_column("rank").desc(), SourceSection.ordinal)
        .limit(limit)
    )
    codes = jurisdiction_codes(db, jurisdiction)
    if codes:
        stmt = stmt.where(LegalSource.jurisdiction_code.in_(codes))
    if practice_area:
        stmt = stmt.where(cast(LegalSource.practice_areas, JSONB).op("?")(practice_area))
    if source_type:
        stmt = stmt.where(LegalSource.source_type == source_type)
    rows = db.execute(stmt).all() if q else []

    rels = relations_affecting(db, list({r.LegalSource.id for r in rows}))
    results = []
    for sec, src, doc, rk, snippet in rows:
        r = rels.get(src.id, [])
        results.append(
            {
                "section_id": str(sec.id),
                "ref": sec.ref,
                "heading": sec.heading,
                "snippet": snippet,
                "rank": round(rk, 4),
                "source": source_card(src, doc, r),
                "warnings": source_warnings(src, r, sec.ref_key),
            }
        )

    notes: list[str] = []
    if not results:
        notes.append(
            "No verified source in our library matched. This does not mean no law applies: our library is still growing. "
            "Check the official source or ask a qualified advocate or your legal services authority."
        )
    jur = {r["source"]["jurisdiction_code"] for r in results}
    if "IN" in jur and len(jur) > 1:
        notes.append("Both central and state sources matched. Which one applies, or whether both do, depends on the facts.")
    if any(w["level"] == "severe" for r in results for w in r["warnings"]):
        notes.append("Some results may no longer be good law. Read the warnings before relying on them.")
    return {"query": q, "jurisdiction_filter": codes, "results": results, "notes": notes}


def section_with_context(db: Session, section_id: uuid.UUID) -> dict | None:
    row = db.execute(
        select(SourceSection, LegalSource, SourceDocument)
        .join(LegalSource, LegalSource.id == SourceSection.source_id)
        .join(SourceDocument, SourceDocument.id == SourceSection.document_id)
        .where(SourceSection.id == section_id, LegalSource.review_status == "verified", SourceDocument.is_current.is_(True))
    ).first()
    if row is None:
        return None
    sec, src, doc = row
    r = relations_affecting(db, [src.id]).get(src.id, [])
    return {
        "section_id": str(sec.id), "ref": sec.ref, "heading": sec.heading, "text": sec.text,
        "source": source_card(src, doc, r), "warnings": source_warnings(src, r, sec.ref_key),
    }

