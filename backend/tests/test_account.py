from sqlalchemy import func, select

from app.models import AuditLog, Case, User
from tests.conftest import PASSWORD, Api, register


def test_settings_update_and_validation():
    api = register("s@example.com")
    s = api.get("/api/account/settings").json()
    assert s["preferred_language"] == "en" and s["country_code"] == "IN" and s["consent_training_use"] is False
    r = api.patch("/api/account/settings", {"preferred_language": "hi", "state_code": "IN-KA", "retention_days": 365,
                                            "display_name": "Asha"})
    assert r.status_code == 200, r.text
    assert r.json()["preferred_language"] == "hi" and r.json()["state_code"] == "IN-KA" and r.json()["retention_days"] == 365
    assert api.patch("/api/account/settings", {"preferred_language": "fr"}).status_code == 422
    assert api.patch("/api/account/settings", {"state_code": "IN-ZZ"}).status_code == 422
    assert api.patch("/api/account/settings", {"retention_days": 1}).status_code == 422
    r = api.patch("/api/account/settings", {"keep_until_deleted": True, "clear_state": True})
    assert r.json()["retention_days"] is None and r.json()["state_code"] is None


def test_consent_changes_are_audited(db):
    api = register("consent@example.com")
    api.patch("/api/account/settings", {"consent_ai_processing": True})
    row = db.scalars(select(AuditLog).where(AuditLog.action == "account.consent_changed")).one()
    assert row.details == {"consent_ai_processing": True}


def test_export_contains_own_data_only():
    a, b = register("ea@example.com"), register("eb@example.com")
    a.post("/api/cases", {"title": "Mine", "matter_type": "employment", "jurisdiction_code": "IN"})
    b.post("/api/cases", {"title": "Theirs", "matter_type": "employment", "jurisdiction_code": "IN"})
    r = a.get("/api/account/export")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["account"]["email"] == "ea@example.com"
    assert [c["title"] for c in data["cases"]] == ["Mine"]
    assert "password" not in r.text.lower().replace("password_", "")


def test_account_deletion_removes_data_and_keeps_audit(db):
    api = register("del@example.com")
    api.post("/api/cases", {"title": "x", "matter_type": "civil", "jurisdiction_code": "IN"})
    assert api.post("/api/account/delete", {"password": "wrong password", "confirm_text": "DELETE MY ACCOUNT"}).status_code == 403
    assert api.post("/api/account/delete", {"password": PASSWORD, "confirm_text": "nope"}).status_code == 422
    assert api.post("/api/account/delete", {"password": PASSWORD, "confirm_text": "DELETE MY ACCOUNT"}).status_code == 204
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert db.scalar(select(func.count()).select_from(Case)) == 0
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "account.deleted")) == 1
    assert api.get("/api/auth/me").status_code == 401
    assert Api().post("/api/auth/login", {"email": "del@example.com", "password": PASSWORD}).status_code == 401


def test_public_catalog_needs_no_login():
    api = Api()
    j = api.get("/api/jurisdictions").json()
    assert len([x for x in j if x["parent_code"] == "IN"]) == 36
    plans = api.get("/api/plans").json()
    assert [p["code"] for p in plans] == ["free", "premium", "professional"]  # institutional is not public
    assert plans[0]["price_minor"] == 0 and plans[1]["price_minor"] is None  # unpriced until configured
    assert len(api.get("/api/catalog").json()["matter_types"]) == 20
    assert all(v is False for v in api.get("/api/features").json().values())
