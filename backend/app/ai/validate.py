"""Post-validation of model output. Nothing the model writes reaches the user without passing through here.

- Statements may only cite sources that were actually retrieved; law statements without one are removed.
- Links that are not the official link of a retrieved source are removed.
- Numeric probabilities and percentages are removed (no invented confidence).
- Remaining text is run through the citation verifier and anything unverified is flagged to the user.
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from ..research.citations import verify_text
from .prompts import _BASE, _EXTRA, MUST_CITE

URL_RE = re.compile(r"(?:https?://|www\.)[^\s)\]>\"']+", re.I)
NUMERIC_RE = re.compile(
    r"\b\d{1,3}(?:\.\d+)?\s?(?:%|per\s?cent\b|percent\b)"
    r"|\b\d+\s?(?:in|out of)\s?\d+\s+(?:chance|odds)\b"
    r"|\b(?:odds|probability|likelihood|chance)s?\s+(?:of|is|are|at)\s+(?:about\s+|around\s+)?\d+(?:\.\d+)?\b",
    re.I,
)
LINK_REMOVED = "[link removed: not a verified source]"
NUMBER_REMOVED = "[numeric estimate removed]"


class OutputInvalid(Exception):
    pass


def _clean_text(s: str, allowed_urls: set[str], counts: dict) -> str:
    def url(m: re.Match) -> str:
        u = m.group(0).rstrip(".,;:")
        if u in allowed_urls:
            return m.group(0)
        counts["links_removed"] += 1
        return LINK_REMOVED + m.group(0)[len(u):]

    def num(_: re.Match) -> str:
        counts["numbers_removed"] += 1
        return NUMBER_REMOVED

    return NUMERIC_RE.sub(num, URL_RE.sub(url, s.strip()))


def validate(db: Session, role: str, data: dict, sources: list[dict]) -> tuple[dict, dict, list[str]]:
    """Returns (clean output, checks report, labels of the sources actually cited)."""
    if not isinstance(data, dict):
        raise OutputInvalid("not an object")
    props = _BASE | _EXTRA[role]
    labels = {s["label"] for s in sources}
    allowed_urls = {s["official_url"] for s in sources}
    counts = {"links_removed": 0, "numbers_removed": 0}
    removed: list[dict] = []
    invalid_ids: set[str] = set()
    cited: list[str] = []
    out: dict = {}

    for key, spec in props.items():
        val = data.get(key)
        if key == "status":
            if val not in spec["enum"]:
                raise OutputInvalid("bad status")
            out[key] = val
        elif spec["type"] == "string":
            out[key] = _clean_text(val if isinstance(val, str) else "", allowed_urls, counts)
        elif spec["items"]["type"] == "string":
            out[key] = [t for t in (_clean_text(x, allowed_urls, counts) for x in (val or []) if isinstance(x, str)) if t]
        else:
            items = []
            for item in val or []:
                if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
                    continue
                ids = [str(i).strip().upper() for i in item.get("source_ids") or []]
                good = list(dict.fromkeys(i for i in ids if i in labels))
                invalid_ids.update(i for i in ids if i not in labels)
                text = _clean_text(item["text"], allowed_urls, counts)
                if key in MUST_CITE and not good:
                    removed.append({"section": key, "text": text, "reason": "Not supported by any verified source we retrieved, so it was removed."})
                    continue
                cited += good
                items.append({"text": text, "source_ids": good})
            out[key] = items

    statements = [i for key, spec in props.items() if spec.get("items", {}).get("type") == "object" for i in out[key]]
    if out["status"] == "answered" and not any(i["source_ids"] for i in statements):
        out["status"] = "cannot_verify"
        removed.append({"section": "status", "text": "", "reason": "The answer did not rest on any verified source, so it is shown as unverified."})

    all_text = "\n".join(
        [out[k] for k, s in props.items() if s["type"] == "string" and k != "status"]
        + [t for k, s in props.items() if s["type"] == "array" and s["items"]["type"] == "string" for t in out[k]]
        + [i["text"] for i in statements]
    )
    check = verify_text(db, all_text)
    unverified = [f for f in check["findings"] if f["status"] != "verified"]
    report = {
        "removed": removed,
        "invalid_source_ids": sorted(invalid_ids),
        "links_removed": counts["links_removed"],
        "numbers_removed": counts["numbers_removed"],
        "citations_checked": check["checked"],
        "unverified_citations": [{"text": f["text"], "status": f["status"], "message": f["message"]} for f in unverified],
    }
    return out, report, list(dict.fromkeys(cited))
