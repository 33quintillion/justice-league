"""Official-source importer, exercised against a mock network. All legal text is a fictional fixture."""
import httpx

from app.models import LegalSource
from app.research import official_import
from tests.conftest import Api, grant, register
from tests.test_research import ACT_TEXT

URL = "https://www.legislative.gov.in/static/uploads/test/fixture.pdf"


def manifest(tmp_path, url=URL):
    p = tmp_path / "m.json"
    p.write_text(
        '{"sources": [{"key": "fixture", "title": "The Fictional Tenancy (Test Fixture) Act, 2099", "citation": "Act No. 99 of 2099",'
        ' "source_type": "legislation", "authority_level": "legislation", "jurisdiction_code": "IN", "publisher": "Test",'
        f' "official_url": "{url}", "practice_areas": ["property_tenancy"]}}]}}'
    )
    return p


def transport(robots="User-agent: *\nAllow: /\n", body=ACT_TEXT.encode(), redirect_to=None, seen=None):
    def handler(req: httpx.Request):
        if seen is not None:
            seen.append(req)
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text=robots) if robots is not None else httpx.Response(404)
        if redirect_to:
            return httpx.Response(302, headers={"location": redirect_to})
        return httpx.Response(200, content=body)
    return httpx.MockTransport(handler)


def test_imports_once_and_waits_for_review(db, tmp_path, monkeypatch):
    monkeypatch.setattr(official_import, "MANIFEST", manifest(tmp_path))
    seen = []
    [o] = official_import.import_official(db, transport=transport(seen=seen), pause=0)
    assert o.status == "imported" and "5 sections" in o.detail
    assert all(r.headers["user-agent"].startswith("JusticeAI-OfficialSourceImporter") for r in seen)
    src = db.query(LegalSource).one()
    assert src.review_status == "pending_review" and src.legal_status == "unknown" and src.created_by is None
    assert Api().get("/api/library/search?q=eviction").json()["results"] == []
    # Re-running with the same official file changes nothing.
    [o2] = official_import.import_official(db, transport=transport(), pause=0)
    assert o2.status == "unchanged"
    # Any content reviewer may verify a system import; then it is public.
    rev = register("rev@example.com")
    grant("rev@example.com", "content_reviewer")
    assert rev.post(f"/api/admin/sources/{src.id}/review", {"decision": "verified", "notes": "Compared with the official PDF"}).status_code == 200
    assert Api().get("/api/library/search?q=eviction").json()["results"][0]["source"]["official_url"] == URL


def test_respects_robots_txt(db, tmp_path, monkeypatch):
    monkeypatch.setattr(official_import, "MANIFEST", manifest(tmp_path))
    seen = []
    [o] = official_import.import_official(db, transport=transport(robots="User-agent: *\nDisallow: /\n", seen=seen), pause=0)
    assert o.status == "blocked_by_robots" and [r.url.path for r in seen] == ["/robots.txt"]
    assert db.query(LegalSource).count() == 0


def test_refuses_redirects_off_official_domains(db, tmp_path, monkeypatch):
    monkeypatch.setattr(official_import, "MANIFEST", manifest(tmp_path))
    [o] = official_import.import_official(db, transport=transport(redirect_to="https://mirror.example.com/x.pdf"), pause=0)
    assert o.status == "failed" and "off official domains" in o.detail


def test_unreadable_file_is_not_stored(db, tmp_path, monkeypatch):
    monkeypatch.setattr(official_import, "MANIFEST", manifest(tmp_path))
    [o] = official_import.import_official(db, transport=transport(body=b"%PDF-1.4 broken"), pause=0)
    assert o.status == "failed" and db.query(LegalSource).count() == 0


def test_shipped_manifest_lists_only_official_https_urls():
    entries = official_import.load_manifest()
    assert {e["key"] for e in entries} >= {"constitution", "bns", "bnss", "bsa"}
    assert all(e["official_url"].startswith("https://www.") and ".gov.in/" in e["official_url"] for e in entries)
