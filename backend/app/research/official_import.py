"""Fetches official legal texts listed in official_sources.json, politely and only where robots.txt allows.

Usage: python -m app.cli import-official [KEY ...]
Each imported file becomes the source's current document and waits for a human reviewer: nothing
imported here is published until someone with the content reviewer role verifies it.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..catalog import is_official_url
from ..models import LegalSource, SourceDocument
from . import ingest
from .store import store_document

MANIFEST = Path(__file__).with_name("official_sources.json")
USER_AGENT = "JusticeAI-OfficialSourceImporter/0.4 (public-interest legal information; one request per file)"
MAX_BYTES = 80 * 1024 * 1024
PAUSE_SECONDS = 3.0


@dataclass
class Outcome:
    key: str
    status: str  # imported | unchanged | blocked_by_robots | failed
    detail: str


def load_manifest(path: Path | None = None) -> list[dict]:
    entries = json.loads((path or MANIFEST).read_text(encoding="utf-8"))["sources"]
    for e in entries:
        if not is_official_url(e["official_url"]):
            raise ValueError(f"{e['key']}: {e['official_url']} is not an official https URL")
    return entries


def _client(transport: httpx.BaseTransport | None) -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(60, connect=20), follow_redirects=False, transport=transport,
        headers={"User-Agent": USER_AGENT}, verify=os.environ.get("SSL_CERT_FILE") or True,
    )


def robots_allows(client: httpx.Client, url: str) -> bool:
    p = urlparse(url)
    r = client.get(f"{p.scheme}://{p.netloc}/robots.txt")
    rp = RobotFileParser()
    if r.status_code in (401, 403):
        return False  # the convention: access-restricted robots.txt means disallow everything
    if r.status_code >= 400:
        return True  # no robots.txt: no restriction stated
    rp.parse(r.text.splitlines())
    return rp.can_fetch(USER_AGENT, url)


def download(client: httpx.Client, url: str) -> bytes:
    for _ in range(5):
        r = client.get(url)
        if r.is_redirect:
            nxt = str(r.next_request.url) if r.next_request else ""
            if not is_official_url(nxt):
                raise ingest.IngestError(f"redirected off official domains to {nxt!r}")
            url = nxt
            continue
        r.raise_for_status()
        if len(r.content) > MAX_BYTES:
            raise ingest.IngestError("file larger than 80 MB")
        return r.content
    raise ingest.IngestError("too many redirects")


def import_official(db: Session, keys: list[str] | None = None, transport: httpx.BaseTransport | None = None,
                    pause: float = PAUSE_SECONDS) -> list[Outcome]:
    entries = [e for e in load_manifest() if not keys or e["key"] in keys]
    outcomes: list[Outcome] = []
    with _client(transport) as client:
        for i, e in enumerate(entries):
            if i:
                time.sleep(pause)
            try:
                if not robots_allows(client, e["official_url"]):
                    outcomes.append(Outcome(e["key"], "blocked_by_robots", "robots.txt does not allow automated access"))
                    continue
                data = download(client, e["official_url"])
            except (httpx.HTTPError, ingest.IngestError) as err:
                outcomes.append(Outcome(e["key"], "failed", f"{type(err).__name__}: {err}"))
                continue

            src = db.scalar(select(LegalSource).where(LegalSource.official_url == e["official_url"]))
            if src is None:
                src = LegalSource(
                    title=e["title"], source_type=e["source_type"], authority_level=e["authority_level"],
                    jurisdiction_code=e["jurisdiction_code"], official_url=e["official_url"], publisher=e["publisher"],
                    citation=e["citation"], practice_areas=e["practice_areas"], notes=e.get("notes", ""),
                    legal_status="unknown", review_status="pending_review", created_by=None,
                )
                db.add(src)
                db.flush()
            current = db.scalar(select(SourceDocument).where(SourceDocument.source_id == src.id, SourceDocument.is_current.is_(True)))
            if current and current.sha256 == ingest.sha256(data):
                outcomes.append(Outcome(e["key"], "unchanged", "official file identical to the stored copy"))
                continue
            try:
                doc, parsed = store_document(
                    db, src, data, filename=Path(urlparse(e["official_url"]).path).name,
                    retrieved_from_url=e["official_url"], retrieved_at=date.today(), uploaded_by=None,
                )
            except ingest.IngestError as err:
                db.rollback()
                outcomes.append(Outcome(e["key"], "failed", str(err)))
                continue
            audit.record(db, "source.official_import", actor_id=None, target_type="legal_source", target_id=src.id,
                         details={"key": e["key"], "sha256": doc.sha256, "sections": len(parsed)})
            db.commit()
            outcomes.append(Outcome(e["key"], "imported", f"{len(parsed)} sections, {doc.extracted_chars:,} characters, sha256 {doc.sha256[:12]}…"))
    return outcomes
