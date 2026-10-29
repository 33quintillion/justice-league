"""Checks citations and quotations in a piece of text against the verified library.

Phase 4 runs every AI answer and draft through this before it is shown; anything not verified is
flagged or removed rather than presented as law. Users can also paste text to check it.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import LegalSource, SourceDocument, SourceSection

_ACT_NAME = r"(?:the\s+)?((?:(?:\(?[A-Z0-9][\w'’()&,.-]*|of|to|from|and|for|the|in|on|with|under)\s+){0,14}?(?:Act|Code|Sanhita|Adhiniyam|Rules|Regulations|Constitution(?:\s+of\s+India)?)(?!\s+(?:of|to|for|on)\s+[A-Z])|Code\s+of\s+(?:[A-Z]\w+\s?){1,4}?(?=,|\s+\d{4}|\s*$|\s+[a-z]))(?:,?\s*(\d{4}))?"
STATUTE_RE = re.compile(
    r"\b(?P<unit>[Ss]ections?|[Ss]s?\.|[Aa]rticles?|[Aa]rt\.|[Rr]ules?|[Rr]egulations?)\s*"
    r"(?P<num>\d{1,4}[A-Z]{0,3})(?P<sub>(?:\s*\([0-9a-zA-Z]{1,5}\))*)\s+of\s+" + _ACT_NAME
)
CASE_RES = [
    re.compile(r"\(\d{4}\)\s*\d{1,3}\s*SCC\s*\d{1,5}"),
    re.compile(r"\bAIR\s+\d{4}\s+[A-Z][A-Za-z]{1,10}\s+\d{1,5}"),
    re.compile(r"\[\d{4}\]\s*\d{1,3}\s*S\.?\s?C\.?\s?R\.?\s*\d{1,5}"),
    re.compile(r"\b\d{4}\s+INSC\s+\d{1,5}"),
]
QUOTE_RE = re.compile(r"[“\"]([^”\"]{25,600})[”\"]")


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'")
    s = re.sub(r"\b(the|of|and)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()


@dataclass
class Finding:
    kind: str  # statute | case | quotation
    text: str
    status: str  # verified | section_not_found | source_not_verified | not_found
    message: str
    source_id: str | None = None
    section_id: str | None = None
    official_url: str | None = None
    warnings: list = field(default_factory=list)


def _current_sources(db: Session) -> list[LegalSource]:
    return list(db.scalars(select(LegalSource)).all())


def _find_source(sources: list[LegalSource], name: str, year: str | None) -> LegalSource | None:
    want = _norm(name)
    candidates = []
    for s in sources:
        title = _norm(s.title)
        if want and (want == title or (want in title and len(want) > 8)):
            if year and year not in s.title and year not in s.citation:
                continue
            candidates.append(s)
    # Prefer a verified source when the same name exists in several states of review.
    candidates.sort(key=lambda s: s.review_status != "verified")
    return candidates[0] if candidates else None


def verify_text(db: Session, text: str) -> dict:
    from .search import relations_affecting, source_warnings

    text = text[:50_000]
    sources = _current_sources(db)
    findings: list[Finding] = []

    for m in STATUTE_RE.finditer(text):
        num = m.group("num").lower()
        name, year = m.groups()[3], m.groups()[4]  # the two unnamed groups in _ACT_NAME
        src = _find_source(sources, name, year)
        cited = m.group(0).strip()
        if src is None:
            findings.append(Finding("statute", cited, "not_found", "This law is not in our verified library, so we cannot confirm this citation."))
            continue
        if src.review_status != "verified":
            findings.append(Finding("statute", cited, "source_not_verified", "We hold this source but it has not passed review yet.", str(src.id)))
            continue
        sec = db.scalar(
            select(SourceSection).join(SourceDocument, SourceDocument.id == SourceSection.document_id)
            .where(SourceSection.source_id == src.id, SourceSection.ref_key == num, SourceDocument.is_current.is_(True))
        )
        rel = relations_affecting(db, [src.id]).get(src.id, [])
        if sec is None:
            findings.append(Finding("statute", cited, "section_not_found",
                                    f"{src.title} is verified, but we could not find {m.group('unit')} {m.group('num')} in our copy.",
                                    str(src.id), None, src.official_url, source_warnings(src, rel)))
            continue
        findings.append(Finding("statute", cited, "verified", f"Matches {sec.ref} of {src.title}.", str(src.id), str(sec.id),
                                src.official_url, source_warnings(src, rel, sec.ref_key)))

    for rx in CASE_RES:
        for m in rx.finditer(text):
            cited = m.group(0)
            want = _ws(cited).replace(" ", "")
            src = next((s for s in sources if want and want in _ws(s.citation).replace(" ", "")), None)
            if src is None:
                findings.append(Finding("case", cited, "not_found", "This case citation is not in our verified library. Check it on the official court website."))
            elif src.review_status != "verified":
                findings.append(Finding("case", cited, "source_not_verified", "We hold this judgment but it has not passed review yet.", str(src.id)))
            else:
                rel = relations_affecting(db, [src.id]).get(src.id, [])
                findings.append(Finding("case", cited, "verified", f"Matches {src.title}.", str(src.id), None, src.official_url, source_warnings(src, rel)))

    quotes = [q.group(1) for q in QUOTE_RE.finditer(text)]
    if quotes:
        sections = db.execute(
            select(SourceSection, LegalSource)
            .join(LegalSource, LegalSource.id == SourceSection.source_id)
            .join(SourceDocument, SourceDocument.id == SourceSection.document_id)
            .where(LegalSource.review_status == "verified", SourceDocument.is_current.is_(True))
        ).all()
        for q in quotes:
            nq = _ws(q)
            hit = next(((sec, src) for sec, src in sections if nq in _ws(f"{sec.heading} {sec.text}")), None)
            if hit:
                sec, src = hit
                findings.append(Finding("quotation", q, "verified", f"Found word for word in {sec.ref} of {src.title}.",
                                        str(src.id), str(sec.id), src.official_url))
            else:
                findings.append(Finding("quotation", q, "not_found", "This quotation was not found word for word in any verified source."))

    return {
        "all_verified": all(f.status == "verified" for f in findings),
        "checked": len(findings),
        "findings": [asdict(f) for f in findings],
    }
