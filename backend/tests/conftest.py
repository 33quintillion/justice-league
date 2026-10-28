"""Tests run against a real PostgreSQL database (TEST_DATABASE_URL), migrated with Alembic."""
import os

os.environ["JUSTICE_ENV"] = "test"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://justice:justice_dev@localhost:5432/justice_test"
)

import re  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DevOutboxEmail, User, UserRole  # noqa: E402
from app.ratelimit import login_limiter  # noqa: E402
from app.seed import seed  # noqa: E402

PASSWORD = "correct horse battery"


@pytest.fixture(scope="session", autouse=True)
def migrated():
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_db():
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    with SessionLocal() as db:
        seed(db)
    login_limiter.reset()
    yield


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


class Api:
    """A browser-like client: keeps cookies and sends the CSRF header like the frontend does."""

    def __init__(self) -> None:
        self.c = TestClient(app, base_url="http://testserver")
        self.csrf = None

    def _h(self, headers=None):
        h = dict(headers or {})
        if self.csrf:
            h["x-csrf-token"] = self.csrf
        return h

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, json=None, headers=None):
        r = self.c.post(url, json=json, headers=self._h(headers))
        if url in ("/api/auth/register", "/api/auth/login") and r.status_code in (200, 201):
            self.csrf = r.json()["csrf_token"]
        return r

    def patch(self, url, json=None):
        return self.c.patch(url, json=json, headers=self._h())

    def put(self, url, json=None):
        return self.c.put(url, json=json, headers=self._h())

    def delete(self, url):
        return self.c.delete(url, headers=self._h())


def register(email: str, verify: bool = True) -> Api:
    api = Api()
    r = api.post("/api/auth/register", {"email": email, "password": PASSWORD, "display_name": "T", "accept_terms": True})
    assert r.status_code == 201, r.text
    if verify:
        with SessionLocal() as s:
            body = s.scalars(select(DevOutboxEmail).where(DevOutboxEmail.to_email == email)).first().body
        token = re.search(r"token=([\w-]+)", body).group(1)
        assert api.post("/api/auth/verify-email", {"token": token}).status_code == 204
    return api


def grant(email: str, *roles: str) -> None:
    with SessionLocal() as s:
        u = s.scalar(select(User).where(User.email == email))
        for r in roles:
            u.roles.append(UserRole(role=r))
        s.commit()


@pytest.fixture
def make_user():
    return register
