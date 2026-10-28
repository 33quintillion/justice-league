import hmac
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuthSession, User
from .permissions import Perm, permissions_for
from .security import hash_token

SESSION_COOKIE = "justice_session"
CSRF_COOKIE = "justice_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _load_session(request: Request, db: Session) -> AuthSession | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    sess = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if sess is None or sess.expires_at <= datetime.now(timezone.utc):
        return None
    return sess


def current_session(request: Request, db: Session = Depends(get_db)) -> AuthSession:
    sess = _load_session(request, db)
    if sess is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    # CSRF: unsafe methods must echo the per-session token in a header (double submit).
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not hmac.compare_digest(sent, sess.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")
    return sess


def current_user(sess: AuthSession = Depends(current_session), db: Session = Depends(get_db)) -> User:
    user = db.get(User, sess.user_id)
    if user is None or user.is_suspended:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account unavailable")
    return user


def verified_user(user: User = Depends(current_user)) -> User:
    if user.email_verified_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please verify your email address first")
    return user


def require(perm: Perm) -> Callable[..., User]:
    def checker(user: User = Depends(current_user)) -> User:
        if perm not in permissions_for(user.role_names):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission for this action")
        return user

    return checker
