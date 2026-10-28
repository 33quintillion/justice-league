import logging

from sqlalchemy.orm import Session

from .config import get_settings
from .models import DevOutboxEmail

log = logging.getLogger("justice.email")


def send_email(db: Session, to: str, subject: str, body: str) -> None:
    backend = get_settings().email_backend
    if backend == "dev_outbox":
        db.add(DevOutboxEmail(to_email=to, subject=subject, body=body))
        log.info("dev_outbox: queued %r for %s", subject, to)
        return
    # No production mail provider is configured yet; fail loudly rather than pretend to send.
    raise RuntimeError(f"Email backend {backend!r} is not implemented")
