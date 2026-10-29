"""Checks that official source links still resolve. Redirects are followed only within official domains."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from ..catalog import is_official_url as is_official
from ..models import LegalSource

USER_AGENT = "JusticeAI-LinkCheck/0.3 (+link integrity check; one request per source)"


def check_url(client: httpx.Client, url: str, max_redirects: int = 5) -> str:
    try:
        for _ in range(max_redirects + 1):
            r = client.head(url)
            if r.status_code in (405, 501):  # some servers refuse HEAD
                r = client.get(url)
            if r.is_redirect:
                nxt = urljoin(url, r.headers.get("location", ""))
                if not is_official(nxt):
                    return "broken"  # redirected off the official domain
                url = nxt
                continue
            return "ok" if r.status_code < 400 else "broken"
        return "broken"
    except httpx.HTTPError:
        return "unreachable"


def check_sources(sources: list[LegalSource], transport: httpx.BaseTransport | None = None) -> dict[str, int]:
    counts = {"ok": 0, "broken": 0, "unreachable": 0}
    with httpx.Client(timeout=15, follow_redirects=False, headers={"User-Agent": USER_AGENT}, transport=transport) as client:
        for src in sources:
            src.link_status = check_url(client, src.official_url)
            src.link_checked_at = datetime.now(timezone.utc)
            counts[src.link_status] += 1
    return counts
