from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import get_db
from ..deps import CSRF_COOKIE, SESSION_COOKIE, _load_session, current_session, current_user
from ..email import send_email
from ..models import AuthSession, EmailToken, Subscription, User, UserSettings
from ..permissions import permissions_for
from ..ratelimit import login_limiter
from ..schemas import LoginIn, MeOut, RegisterIn, TokenIn
from ..security import hash_password, hash_token, new_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

VERIFY_TTL = timedelta(hours=48)


def me_out(user: User, sess: AuthSession) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        email_verified=user.email_verified_at is not None,
        roles=sorted(user.role_names),
        permissions=sorted(permissions_for(user.role_names)),
        plan_code=user.subscription.plan_code if user.subscription else "free",
        csrf_token=sess.csrf_token,
    )


def _issue_verification(db: Session, user: User) -> None:
    token = new_token()
    db.add(
        EmailToken(
            user_id=user.id,
            purpose="verify_email",
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + VERIFY_TTL,
        )
    )
    link = f"{get_settings().public_app_url}/verify-email?token={token}"
    send_email(
        db,
        user.email,
        "Verify your JUSTICE AI email address",
        f"Open this link to verify your email address (valid for 48 hours):\n\n{link}\n\n"
        "If you did not create a JUSTICE AI account, you can ignore this message.",
    )


def _start_session(db: Session, user: User, request: Request, response: Response) -> AuthSession:
    s = get_settings()
    token = new_token()
    sess = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=new_token(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=s.session_ttl_hours),
        user_agent=(request.headers.get("user-agent") or "")[:300],
    )
    db.add(sess)
    max_age = s.session_ttl_hours * 3600
    response.set_cookie(
        SESSION_COOKIE, token, max_age=max_age, httponly=True, secure=s.cookie_secure, samesite="lax", path="/"
    )
    response.set_cookie(
        CSRF_COOKIE, sess.csrf_token, max_age=max_age, httponly=False, secure=s.cookie_secure, samesite="lax", path="/"
    )
    return sess


@router.post("/register", status_code=201, response_model=MeOut)
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        # Same status a fresh account would never get, but no detail on whether the email exists elsewhere.
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists. Try signing in.")
    user = User(email=email, password_hash=hash_password(body.password), display_name=body.display_name.strip())
    user.settings = UserSettings()
    user.subscription = Subscription(plan_code="free")
    db.add(user)
    db.flush()
    _issue_verification(db, user)
    sess = _start_session(db, user, request, response)
    audit.record(db, "auth.register", actor_id=user.id, target_type="user", target_id=user.id, request=request)
    db.commit()
    return me_out(user, sess)


@router.post("/login", response_model=MeOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    email = body.email.strip().lower()
    ip = request.client.host if request.client else "?"
    if not login_limiter.hit(f"login:{ip}:{email}", s.login_rate_limit, s.login_rate_window_s):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many sign-in attempts. Please wait and try again.")
    user = db.scalar(select(User).where(User.email == email))
    if not verify_password(user.password_hash if user else None, body.password) or user is None:
        audit.record(db, "auth.login_failed", actor_id=user.id if user else None, details={"email": email}, request=request)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    if user.is_suspended:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is suspended. Contact support.")
    sess = _start_session(db, user, request, response)
    audit.record(db, "auth.login", actor_id=user.id, target_type="user", target_id=user.id, request=request)
    db.commit()
    return me_out(user, sess)


@router.post("/logout", status_code=204)
def logout(response: Response, sess: AuthSession = Depends(current_session), db: Session = Depends(get_db)):
    db.delete(sess)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.post("/logout-all", status_code=204)
def logout_all(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    audit.record(db, "auth.logout_all", actor_id=user.id, target_type="user", target_id=user.id)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.get("/me", response_model=MeOut)
def me(request: Request, db: Session = Depends(get_db)):
    sess = _load_session(request, db)
    if sess is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    user = db.get(User, sess.user_id)
    if user is None or user.is_suspended:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account unavailable")
    return me_out(user, sess)


@router.post("/verify-email", status_code=204)
def verify_email(body: TokenIn, request: Request, db: Session = Depends(get_db)):
    """Unauthenticated on purpose: the emailed token is the credential, so the link works on any device."""
    tok = db.scalar(
        select(EmailToken).where(EmailToken.token_hash == hash_token(body.token), EmailToken.purpose == "verify_email")
    )
    now = datetime.now(timezone.utc)
    if tok is None or tok.used_at is not None or tok.expires_at <= now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This verification link is invalid or has expired")
    user = db.get(User, tok.user_id)
    tok.used_at = now
    if user.email_verified_at is None:
        user.email_verified_at = now
    audit.record(db, "auth.email_verified", actor_id=user.id, target_type="user", target_id=user.id, request=request)
    db.commit()


@router.post("/resend-verification", status_code=204)
def resend_verification(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.email_verified_at is not None:
        return
    key = f"verify:{user.id}"
    if not login_limiter.hit(key, 5, 3600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many verification emails. Try again later.")
    _issue_verification(db, user)
    db.commit()
