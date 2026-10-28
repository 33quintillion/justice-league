from tests.conftest import PASSWORD, Api, register


def test_register_login_logout_flow():
    api = register("asha@example.com", verify=False)
    me = api.get("/api/auth/me").json()
    assert me["email"] == "asha@example.com" and me["email_verified"] is False and me["plan_code"] == "free"
    assert api.post("/api/auth/logout").status_code == 204
    assert api.get("/api/auth/me").status_code == 401

    api2 = Api()
    assert api2.post("/api/auth/login", {"email": "ASHA@example.com", "password": PASSWORD}).status_code == 200
    assert api2.get("/api/auth/me").json()["email"] == "asha@example.com"


def test_session_cookie_is_httponly_and_password_not_stored_plain(db):
    api = Api()
    r = api.post("/api/auth/register", {"email": "b@example.com", "password": PASSWORD, "accept_terms": True})
    cookies = r.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("justice_session="))
    assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie
    from app.models import User
    u = db.query(User).one()
    assert PASSWORD not in u.password_hash and u.password_hash.startswith("$argon2")


def test_register_validation():
    api = Api()
    assert api.post("/api/auth/register", {"email": "x@example.com", "password": "short", "accept_terms": True}).status_code == 422
    assert api.post("/api/auth/register", {"email": "x@example.com", "password": PASSWORD, "accept_terms": False}).status_code == 422
    assert api.post("/api/auth/register", {"email": "not-an-email", "password": PASSWORD, "accept_terms": True}).status_code == 422
    register("dup@example.com", verify=False)
    assert Api().post("/api/auth/register", {"email": "dup@example.com", "password": PASSWORD, "accept_terms": True}).status_code == 409


def test_wrong_password_and_unknown_user_look_the_same():
    register("c@example.com", verify=False)
    a = Api().post("/api/auth/login", {"email": "c@example.com", "password": "wrong password!"})
    b = Api().post("/api/auth/login", {"email": "nobody@example.com", "password": "wrong password!"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_login_rate_limited():
    register("d@example.com", verify=False)
    codes = [Api().post("/api/auth/login", {"email": "d@example.com", "password": "nope nope nope"}).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_email_verification_token_single_use(db):
    import re
    from app.models import DevOutboxEmail
    api = register("e@example.com", verify=False)
    token = re.search(r"token=([\w-]+)", db.query(DevOutboxEmail).one().body).group(1)
    assert api.post("/api/auth/verify-email", {"token": token}).status_code == 204
    assert api.get("/api/auth/me").json()["email_verified"] is True
    assert api.post("/api/auth/verify-email", {"token": token}).status_code == 400
    assert api.post("/api/auth/verify-email", {"token": "made-up"}).status_code == 400


def test_csrf_required_for_unsafe_methods():
    api = register("f@example.com")
    api.csrf = None
    r = api.post("/api/cases", {"title": "x", "matter_type": "consumer", "jurisdiction_code": "IN"})
    assert r.status_code == 403 and "CSRF" in r.json()["detail"]
    api.csrf = "forged"
    assert api.post("/api/auth/logout").status_code == 403


def test_logout_all_revokes_every_session():
    a = register("g@example.com")
    b = Api()
    b.post("/api/auth/login", {"email": "g@example.com", "password": PASSWORD})
    assert a.post("/api/auth/logout-all").status_code == 204
    assert b.get("/api/auth/me").status_code == 401


def test_security_headers_present():
    r = Api().get("/api/health")
    assert r.json() == {"status": "ok", "database": "ok"}
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"


def test_validation_errors_do_not_echo_input():
    r = Api().post("/api/auth/register", {"email": "secret-value-123", "password": PASSWORD, "accept_terms": True})
    assert r.status_code == 422 and "secret-value-123" not in r.text
