"""Environment-driven configuration. Nothing secret is hardcoded; see .env.example."""
from functools import lru_cache
import os


class Settings:
    def __init__(self) -> None:
        self.env = os.getenv("JUSTICE_ENV", "development")
        self.database_url = os.getenv(
            "DATABASE_URL", "postgresql+psycopg://justice:justice_dev@localhost:5432/justice"
        )
        self.public_app_url = os.getenv("PUBLIC_APP_URL", "http://localhost:3000")
        # Secure cookies are on everywhere except plain-http local development.
        self.cookie_secure = os.getenv("COOKIE_SECURE", "false" if self.env in ("development", "test") else "true") == "true"
        self.session_ttl_hours = int(os.getenv("SESSION_TTL_HOURS", "168"))
        self.email_backend = os.getenv("EMAIL_BACKEND", "dev_outbox" if self.env != "production" else "smtp")
        self.bootstrap_admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower() or None
        self.login_rate_limit = int(os.getenv("LOGIN_RATE_LIMIT", "10"))  # attempts per window
        self.login_rate_window_s = int(os.getenv("LOGIN_RATE_WINDOW_SECONDS", "900"))
        self.reverify_after_days = int(os.getenv("REVERIFY_AFTER_DAYS", "180"))
        if self.env == "production" and self.email_backend == "dev_outbox":
            raise RuntimeError("dev_outbox email backend must not be used in production")

    @property
    def is_dev(self) -> bool:
        return self.env in ("development", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()
