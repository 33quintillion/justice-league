from tests.conftest import register

CASE = {"title": "Defective washing machine", "matter_type": "consumer", "jurisdiction_code": "IN-MH",
        "summary": "Bought on 1 March; stopped working", "desired_outcome": "Refund"}


def test_case_crud_and_timeline():
    api = register("owner@example.com")
    c = api.post("/api/cases", CASE)
    assert c.status_code == 201, c.text
    cid = c.json()["id"]
    assert [x["id"] for x in api.get("/api/cases").json()] == [cid]
    assert api.patch(f"/api/cases/{cid}", {"stage": "notice_sent"}).json()["stage"] == "notice_sent"
    e2 = api.post(f"/api/cases/{cid}/events", {"event_date": "2026-03-10", "description": "Complaint to seller"}).json()
    api.post(f"/api/cases/{cid}/events", {"event_date": "2026-03-01", "description": "Purchase", "is_deadline": False})
    events = api.get(f"/api/cases/{cid}").json()["events"]
    assert [e["description"] for e in events] == ["Purchase", "Complaint to seller"]  # chronological
    assert all(e["origin"] == "user" for e in events)
    assert api.delete(f"/api/cases/{cid}/events/{e2['id']}").status_code == 204
    assert api.delete(f"/api/cases/{cid}").status_code == 204
    assert api.get(f"/api/cases/{cid}").status_code == 404


def test_case_isolation_between_users():
    alice, bob = register("alice@example.com"), register("bob@example.com")
    cid = alice.post("/api/cases", CASE).json()["id"]
    ev = alice.post(f"/api/cases/{cid}/events", {"event_date": "2026-01-01", "description": "private"}).json()
    assert bob.get("/api/cases").json() == []
    assert bob.get(f"/api/cases/{cid}").status_code == 404
    assert bob.patch(f"/api/cases/{cid}", {"title": "pwned"}).status_code == 404
    assert bob.post(f"/api/cases/{cid}/events", {"event_date": "2026-01-02", "description": "x"}).status_code == 404
    assert bob.delete(f"/api/cases/{cid}/events/{ev['id']}").status_code == 404
    assert bob.delete(f"/api/cases/{cid}").status_code == 404
    got = alice.get(f"/api/cases/{cid}").json()
    assert got["title"] == CASE["title"] and len(got["events"]) == 1


def test_event_cannot_be_deleted_through_another_case():
    alice = register("a2@example.com")
    # Same user, two cases: move them to premium so two open cases are allowed.
    from app.db import SessionLocal
    from app.models import Subscription, User
    with SessionLocal() as s:
        u = s.query(User).one()
        s.get(Subscription, u.id).plan_code = "premium"
        s.commit()
    c1 = alice.post("/api/cases", CASE).json()["id"]
    c2 = alice.post("/api/cases", CASE).json()["id"]
    ev = alice.post(f"/api/cases/{c1}/events", {"event_date": "2026-01-01", "description": "x"}).json()
    assert alice.delete(f"/api/cases/{c2}/events/{ev['id']}").status_code == 404


def test_unauthenticated_and_unverified_access():
    from tests.conftest import Api
    assert Api().get("/api/cases").status_code == 401
    unverified = register("u@example.com", verify=False)
    r = unverified.post("/api/cases", CASE)
    assert r.status_code == 403 and "verify" in r.json()["detail"]


def test_free_plan_case_limit_enforced_and_configurable():
    api = register("limit@example.com")
    first = api.post("/api/cases", CASE).json()["id"]
    r = api.post("/api/cases", CASE)
    assert r.status_code == 402 and "1 open case" in r.json()["detail"]
    # Closing a case frees the slot; reopening it while at the limit is blocked.
    api.patch(f"/api/cases/{first}", {"status": "closed"})
    second = api.post("/api/cases", CASE)
    assert second.status_code == 201
    assert api.patch(f"/api/cases/{first}", {"status": "open"}).status_code == 402


def test_case_input_validation():
    api = register("v@example.com")
    assert api.post("/api/cases", {**CASE, "matter_type": "astrology"}).status_code == 422
    assert api.post("/api/cases", {**CASE, "jurisdiction_code": "US-CA"}).status_code == 422
    assert api.get("/api/cases/not-a-uuid").status_code == 422
