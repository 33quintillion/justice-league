"""Grounded answer pipeline shared by the four AI roles.

Order matters: urgency first (never blocked), then consent, configuration and plan limits, then retrieval of
verified sections. With nothing verified to rely on we say so without calling the model at all.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..entitlements import limit
from ..models import AIAnswer, AIAnswerCitation, Case, SourceSection, User
from ..research.search import search
from . import prompts, urgency
from .provider import LLMProvider
from .validate import validate

MAX_SOURCES = 8
MAX_TOKENS = 16000
IST = ZoneInfo("Asia/Kolkata")


def period_start(now: datetime | None = None) -> datetime:
    """Usage resets at the start of each calendar month, Indian Standard Time."""
    now = (now or datetime.now(timezone.utc)).astimezone(IST)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def usage(db: Session, user: User) -> dict:
    used = db.scalar(
        select(func.count()).select_from(AIAnswer)
        .where(AIAnswer.user_id == user.id, AIAnswer.counts_toward_usage.is_(True), AIAnswer.created_at >= period_start())
    )
    return {"used": used, "limit": limit(db, user, "ai_questions_per_month"), "period_start": period_start().isoformat()}


def case_context(case: Case) -> dict:
    return {
        "title": case.title, "matter_type": case.matter_type, "jurisdiction_code": case.jurisdiction_code,
        "stage": case.stage, "summary": case.summary, "desired_outcome": case.desired_outcome,
        "events": [{"event_date": e.event_date.isoformat(), "description": e.description, "is_deadline": e.is_deadline,
                    "origin": e.origin} for e in case.events],
    }


def retrieve(db: Session, question: str, jurisdiction: str | None, case: Case | None) -> list[dict]:
    queries = [question]
    if case is not None:
        queries += [f"{case.title} {case.matter_type.replace('_', ' ')}", case.summary[:400]]
    seen: dict[str, dict] = {}
    for q in queries:
        if len(q.strip()) < 2:
            continue
        for r in search(db, q, jurisdiction=jurisdiction, limit=MAX_SOURCES)["results"]:
            seen.setdefault(r["section_id"], r)
        if len(seen) >= MAX_SOURCES:
            break
    results = list(seen.values())[:MAX_SOURCES]
    if not results:
        return []
    texts = dict(db.execute(select(SourceSection.id, SourceSection.text).where(SourceSection.id.in_([r["section_id"] for r in results]))).all())
    out = []
    for i, r in enumerate(results, 1):
        src = r["source"]
        out.append({
            "label": f"S{i}", "section_id": r["section_id"], "source_id": src["id"], "title": src["title"],
            "ref": r["ref"], "heading": r["heading"], "jurisdiction_code": src["jurisdiction_code"],
            "official_url": src["official_url"], "document_sha256": src["document_sha256"] or "",
            "warnings": r["warnings"], "text": next(t for k, t in texts.items() if str(k) == r["section_id"]),
        })
    return out


def _empty(role: str) -> dict:
    schema = prompts.schema_for(role)["properties"]
    return {k: ("" if s["type"] == "string" else []) for k, s in schema.items()}


def no_sources_response(role: str) -> dict:
    r = _empty(role) | {"status": "cannot_verify"}
    r["summary"] = (
        "We could not find a verified legal source in our library for this question, so we are not answering it. "
        "This does not mean no law applies: our library is still growing."
    )
    r["next_steps"] = [
        "Check the official text on India Code (indiacode.nic.in) or the relevant government website.",
        "Speak to a qualified advocate, or contact your District Legal Services Authority for free legal aid.",
    ]
    return r


def run(
    db: Session, *, provider: LLMProvider, user: User, role: str, question: str,
    jurisdiction: str | None, case: Case | None, language: str,
) -> AIAnswer:
    urg = urgency.detect(question + ("\n" + case.summary if case else ""))
    sources = retrieve(db, question, jurisdiction, case)
    answer = AIAnswer(
        user_id=user.id, case_id=case.id if case else None, role=role, question=question,
        jurisdiction_code=jurisdiction, language=language, urgency=urg, prompt_version=prompts.PROMPT_VERSION,
    )
    if not sources:
        answer.status = "cannot_verify"
        answer.response = no_sources_response(role)
        answer.checks = {"reason": "no_verified_sources"}
    else:
        gen = provider.generate(
            system=prompts.system_prompt(role),
            user=prompts.build_user_message(question=question, sources=sources, language=language,
                                            case=case_context(case) if case else None),
            schema=prompts.schema_for(role), max_tokens=MAX_TOKENS,
        )
        clean, report, cited = validate(db, role, gen.data, sources)
        report["served_by_fallback_model"] = gen.served_by_fallback
        answer.status, answer.response, answer.checks = clean["status"], clean, report
        answer.llm_called = answer.counts_toward_usage = True
        answer.provider, answer.model = provider.name, gen.model
        answer.provider_request_id = gen.request_id or ""
        answer.input_tokens, answer.output_tokens = gen.input_tokens, gen.output_tokens
        for s in sources:
            answer.citations.append(AIAnswerCitation(
                label=s["label"], cited=s["label"] in cited, source_id=s["source_id"], section_id=s["section_id"],
                document_sha256=s["document_sha256"], source_title=s["title"][:400], section_ref=s["ref"][:60],
                official_url=s["official_url"], section_text=s["text"],
            ))
    db.add(answer)
    db.flush()
    return answer


def answer_out(a: AIAnswer) -> dict:
    out = {
        "id": str(a.id), "role": a.role, "title": prompts.ROLES[a.role]["title"], "question": a.question,
        "case_id": str(a.case_id) if a.case_id else None, "jurisdiction_code": a.jurisdiction_code,
        "status": a.status, "created_at": a.created_at.isoformat(), "response": a.response, "checks": a.checks,
        "urgency": a.urgency, "llm_called": a.llm_called, "model": a.model, "prompt_version": a.prompt_version,
        "disclaimer": prompts.DISCLAIMER,
        "sources": [
            {"label": c.label, "cited": c.cited, "source_id": str(c.source_id) if c.source_id else None,
             "section_id": str(c.section_id) if c.section_id else None, "title": c.source_title, "ref": c.section_ref,
             "official_url": c.official_url, "document_sha256": c.document_sha256, "text": c.section_text}
            for c in a.citations
        ],
    }
    if a.role == "judge":
        out["label"] = prompts.JUDGE_LABEL
    return out
