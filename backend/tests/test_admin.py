import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.conftest import Api, grant, register

SRC = {"title": "The Consumer Protection Act, 2019", "source_type": "legislation", "authority_level": "legislation",
       "jurisdiction_code": "IN", "official_url": "https://www.indiacode.nic.in/handle/123456789/0000",
       "publisher": "Legislative Department"}


def staff(email, *roles):
    api = register(email)
    grant(email, *roles)
    return api


def test_ordinary_user_has_no_admin_access():
    api = register("user@example.com")
    for url in ("/api/admin/users", "/api/admin/audit", "/api/admin/sources", "/api/admin/flags",
                "/api/admin/plans", "/api/admin/health", "/api/admin/jurisdictions"):
        assert api.get(url).status_code == 403, url
    assert Api().get("/api/admin/users").status_code == 401


@pytest.mark.parametrize("role,allowed,denied", [
    ("support", ["/api/admin/users"], ["/api/admin/audit", "/api/admin/sources", "/api/admin/flags", "/api/admin/plans"]),
    ("billing_admin", ["/api/admin/users", "/api/admin/plans"], ["/api/admin/audit", "/api/admin/sources", "/api/admin/flags"]),
    ("legal_researcher", ["/api/admin/sources", "/api/admin/jurisdictions"], ["/api/admin/users", "/api/admin/audit", "/api/admin/plans"]),
    ("content_reviewer", ["/api/admin/sources"], ["/api/admin/users", "/api/admin/audit", "/api/admin/flags"]),
    ("sysadmin", ["/api/admin/users", "/api/admin/audit", "/api/admin/flags", "/api/admin/health", "/api/admin/plans"], []),
])
def test_role_permission_matrix(role, allowed, denied):
    api = staff(f"{role}@example.com", role)
    for url in allowed:
        assert api.get(url).status_code == 200, (role, url)
    for url in denied:
        assert api.get(url).status_code == 403, (role, url)


def test_admin_cannot_read_case_content():
    user = register("private@example.com")
    cid = user.post("/api/cases", {"title": "Secret matter", "matter_type": "family", "jurisdiction_code": "IN",
                                   "summary": "very private facts"}).json()["id"]
    admin = staff("root@example.com", "sysadmin", "support", "billing_admin", "legal_researcher", "content_reviewer")
    assert admin.get(f"/api/cases/{cid}").status_code == 404
    listing = admin.get("/api/admin/users").text
    assert "very private facts" not in listing and "Secret matter" not in listing
    assert '"case_count":1' in listing.replace(" ", "")


def test_role_changes_require_reason_and_are_audited():
    admin = staff("root@example.com", "sysadmin")
    target = register("t@example.com")
    tid = target.get("/api/auth/me").json()["id"]
    assert admin.put(f"/api/admin/users/{tid}/roles", {"roles": ["support"], "reason": ""}).status_code == 422
    assert admin.put(f"/api/admin/users/{tid}/roles", {"roles": ["overlord"], "reason": "testing"}).status_code == 422
    r = admin.put(f"/api/admin/users/{tid}/roles", {"roles": ["support"], "reason": "New support hire"})
    assert r.status_code == 200 and r.json()["roles"] == ["support"]
    assert target.get("/api/admin/users").status_code == 200
    log = admin.get("/api/admin/audit?action=admin.roles_changed").json()
    assert log[0]["details"]["after"] == ["support"] and log[0]["details"]["reason"] == "New support hire"
    # Support staff cannot grant roles.
    assert target.put(f"/api/admin/users/{tid}/roles", {"roles": ["sysadmin"], "reason": "escalate"}).status_code == 403


def test_sysadmin_cannot_remove_own_sysadmin_role():
    admin = staff("root@example.com", "sysadmin")
    me = admin.get("/api/auth/me").json()["id"]
    assert admin.put(f"/api/admin/users/{me}/roles", {"roles": [], "reason": "oops test"}).status_code == 409


def test_suspension_revokes_sessions_and_blocks_login():
    support = staff("help@example.com", "support")
    victim = register("v@example.com")
    vid = victim.get("/api/auth/me").json()["id"]
    assert support.put(f"/api/admin/users/{vid}/suspension", {"suspended": True, "reason": "Abuse report #1"}).status_code == 200
    assert victim.get("/api/auth/me").status_code == 401
    from tests.conftest import PASSWORD
    assert Api().post("/api/auth/login", {"email": "v@example.com", "password": PASSWORD}).status_code == 403
    root = staff("root@example.com", "sysadmin")
    rid = root.get("/api/auth/me").json()["id"]
    assert support.put(f"/api/admin/users/{rid}/suspension", {"suspended": True, "reason": "try it"}).status_code == 403


def test_billing_admin_changes_plan_and_limit_follows():
    billing = staff("bill@example.com", "billing_admin")
    user = register("cust@example.com")
    uid = user.get("/api/auth/me").json()["id"]
    case = {"title": "x", "matter_type": "civil", "jurisdiction_code": "IN"}
    user.post("/api/cases", case)
    assert user.post("/api/cases", case).status_code == 402
    assert billing.put(f"/api/admin/users/{uid}/subscription", {"plan_code": "premium", "reason": "Pilot participant"}).status_code == 200
    assert user.post("/api/cases", case).status_code == 201
    # Plans are configurable: lowering the premium limit takes effect immediately.
    ent = billing.get("/api/admin/plans").json()[1]["entitlements"] | {"max_open_cases": 2}
    assert billing.patch("/api/admin/plans/premium", {"entitlements": ent}).status_code == 200
    assert user.post("/api/cases", case).status_code == 402
    assert billing.patch("/api/admin/plans/free", {"price_minor": 100}).status_code == 422


def test_source_requires_official_url_and_independent_review():
    researcher = staff("res@example.com", "legal_researcher")
    reviewer = staff("rev@example.com", "content_reviewer")
    for bad in ("http://www.indiacode.nic.in/x", "https://indiankanoon.example.com/x", "https://evilgov.in.attacker.com/x",
                "https://notgov.in/x"):
        assert researcher.post("/api/admin/sources", {**SRC, "official_url": bad}).status_code == 422, bad
    src = researcher.post("/api/admin/sources", SRC)
    assert src.status_code == 201 and src.json()["review_status"] == "pending_review"
    sid = src.json()["id"]
    assert reviewer.post("/api/admin/sources", SRC).status_code == 403  # reviewers cannot author
    assert researcher.post(f"/api/admin/sources/{sid}/review", {"decision": "verified", "notes": "self check"}).status_code == 403
    grant("res@example.com", "content_reviewer")
    assert researcher.post(f"/api/admin/sources/{sid}/review", {"decision": "verified", "notes": "self check"}).status_code == 409
    # Verification needs the official document on file (covered in test_research.py).
    r = reviewer.post(f"/api/admin/sources/{sid}/review", {"decision": "verified", "notes": "Matched against India Code"})
    assert r.status_code == 409 and "Upload the official document" in r.json()["detail"]
    r = reviewer.post(f"/api/admin/sources/{sid}/review", {"decision": "rejected", "notes": "Wrong URL for this Act"})
    assert r.status_code == 200 and r.json()["review_status"] == "rejected"


def test_feature_flags_and_jurisdictions():
    admin = staff("root@example.com", "sysadmin")
    assert admin.put("/api/admin/flags/ai_judge", {"enabled": True}).json()["enabled"] is True
    assert Api().get("/api/features").json()["ai_judge"] is True
    assert admin.put("/api/admin/flags/nope", {"enabled": True}).status_code == 404
    assert admin.patch("/api/admin/jurisdictions/IN-GA", {"enabled": False}).status_code == 200
    assert "IN-GA" not in [j["code"] for j in Api().get("/api/jurisdictions").json()]
    health = admin.get("/api/admin/health").json()
    assert health["database"] == "ok" and health["alembic_revision"] == "0003"
    assert health["ai_provider_configured"] is False


def test_audit_log_is_append_only(db):
    register("x@example.com")
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("UPDATE audit_logs SET action = 'tampered'"))
    db.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("DELETE FROM audit_logs"))
    db.rollback()
