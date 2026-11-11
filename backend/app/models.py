"""Relational schema. PostgreSQL is the source of truth for users, cases, sources and audit records."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    roles: Mapped[list[UserRole]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    settings: Mapped[UserSettings | None] = relationship(
        cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    subscription: Mapped[Subscription | None] = relationship(
        cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )

    @property
    def role_names(self) -> set[str]:
        return {r.role for r in self.roles}


class UserRole(Base):
    """Staff roles. Ordinary users have no rows here."""

    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(40))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    country_code: Mapped[str] = mapped_column(String(2), default="IN")
    state_code: Mapped[str | None] = mapped_column(String(10))
    # None means "keep until I delete it"; otherwise inactive cases older than this are purged.
    retention_days: Mapped[int | None] = mapped_column(Integer)
    consent_ai_processing: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_training_use: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str] = mapped_column(String(300), default="")


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(30))  # verify_email
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DevOutboxEmail(Base):
    """Development-only mail sink so verification works without SMTP. Disabled in production."""

    __tablename__ = "dev_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    to_email: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)  # "IN", "IN-MH"
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))  # country | state | union_territory
    parent_code: Mapped[str | None] = mapped_column(ForeignKey("jurisdictions.code"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    matter_type: Mapped[str] = mapped_column(String(40))
    jurisdiction_code: Mapped[str] = mapped_column(ForeignKey("jurisdictions.code"))
    stage: Mapped[str] = mapped_column(String(40), default="not_started")
    summary: Mapped[str] = mapped_column(Text, default="")
    desired_outcome: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    events: Mapped[list[CaseEvent]] = relationship(
        cascade="all, delete-orphan", order_by="CaseEvent.event_date", lazy="selectin"
    )


class CaseEvent(Base):
    """A user-supplied fact on the case timeline. Never AI-authored without being labelled as such."""

    __tablename__ = "case_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    event_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    is_deadline: Mapped[bool] = mapped_column(Boolean, default=False)
    origin: Mapped[str] = mapped_column(String(20), default="user")  # user | ai_suggested
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Plan(Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    # Price in paise; None means "not yet priced" and the plan cannot be purchased.
    price_minor: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    billing_interval: Mapped[str | None] = mapped_column(String(10))  # month | year
    renewal_terms: Mapped[str] = mapped_column(Text, default="")
    entitlements: Mapped[dict] = mapped_column(JSON, default=dict)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Subscription(Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LegalSource(Base):
    """Metadata for an authoritative legal source. Content ingestion and indexing arrive in Phase 3."""

    __tablename__ = "legal_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(400))
    source_type: Mapped[str] = mapped_column(String(30))
    authority_level: Mapped[str] = mapped_column(String(30))
    jurisdiction_code: Mapped[str] = mapped_column(ForeignKey("jurisdictions.code"))
    official_url: Mapped[str] = mapped_column(String(1000))
    publisher: Mapped[str] = mapped_column(String(200), default="")
    citation: Mapped[str] = mapped_column(String(300), default="")
    effective_date: Mapped[date | None] = mapped_column(Date)
    legal_status: Mapped[str] = mapped_column(String(30), default="unknown")  # in_force, amended, repealed...
    review_status: Mapped[str] = mapped_column(String(20), default="pending_review")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Phase 3
    practice_areas: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(10), default="en")
    link_status: Mapped[str] = mapped_column(String(20), default="unchecked")  # ok | broken | unreachable
    link_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    """Append-only (enforced by a database trigger). actor_id has no FK so records survive account deletion."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(40), default="")
    target_id: Mapped[str] = mapped_column(String(80), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")


class SourceDocument(Base):
    """An original official file for a legal source, stored byte-for-byte with its hash.

    The vector/full-text index is derived from this; the original stays the source of truth.
    """

    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("legal_sources.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    media_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    retrieved_from_url: Mapped[str] = mapped_column(String(1000))
    retrieved_at: Mapped[date] = mapped_column(Date)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    extracted_chars: Mapped[int] = mapped_column(Integer, default=0)


class SourceSection(Base):
    """One citable unit (statute section or judgment paragraph) of a source document."""

    __tablename__ = "source_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("legal_sources.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    ref: Mapped[str] = mapped_column(String(60))  # "Section 2", "Para 14", "Part 3"
    ref_key: Mapped[str] = mapped_column(String(30), index=True)  # normalised: "2", "14", "35a"
    heading: Mapped[str] = mapped_column(String(500), default="")
    text: Mapped[str] = mapped_column(Text)
    # search_vector is a generated tsvector column added in the migration (GIN indexed).


class SourceRelation(Base):
    """A recorded effect of one source on another (amends, repeals, overrules, stays...)."""

    __tablename__ = "source_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("legal_sources.id", ondelete="CASCADE"), index=True)
    to_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("legal_sources.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    to_section_ref: Mapped[str] = mapped_column(String(30), default="")  # blank = whole source
    effective_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIAnswer(Base):
    """One AI role response, private to its owner. Staff have no endpoint that reads these."""

    __tablename__ = "ai_answers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # ask | lawyer | advocate | judge
    question: Mapped[str] = mapped_column(Text)
    jurisdiction_code: Mapped[str | None] = mapped_column(String(10))
    language: Mapped[str] = mapped_column(String(10), default="en")
    status: Mapped[str] = mapped_column(String(30))  # answered | cannot_verify | needs_more_information
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    checks: Mapped[dict] = mapped_column(JSON, default=dict)
    urgency: Mapped[dict] = mapped_column(JSON, default=dict)
    llm_called: Mapped[bool] = mapped_column(Boolean, default=False)
    counts_toward_usage: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str] = mapped_column(String(30), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    prompt_version: Mapped[str] = mapped_column(String(40), default="")
    provider_request_id: Mapped[str] = mapped_column(String(120), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    # Deleting an answer erases its content but keeps this row so monthly usage cannot be reset by deleting.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def erase(self) -> None:
        self.question, self.response, self.checks, self.urgency = "", {}, {}, {}
        self.case_id, self.deleted_at = None, utcnow()
        self.citations.clear()

    citations: Mapped[list[AIAnswerCitation]] = relationship(
        cascade="all, delete-orphan", order_by="AIAnswerCitation.label", lazy="selectin"
    )


class AIAnswerCitation(Base):
    """The exact source version an answer relied on, kept even if the library later changes."""

    __tablename__ = "ai_answer_citations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    answer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_answers.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(10))  # S1, S2 ... as used in the answer
    cited: Mapped[bool] = mapped_column(Boolean, default=False)  # False: retrieved and shown to the model only
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("legal_sources.id", ondelete="SET NULL"))
    section_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_sections.id", ondelete="SET NULL"))
    document_sha256: Mapped[str] = mapped_column(String(64), default="")
    source_title: Mapped[str] = mapped_column(String(400))
    section_ref: Mapped[str] = mapped_column(String(60), default="")
    official_url: Mapped[str] = mapped_column(String(1000))
    section_text: Mapped[str] = mapped_column(Text, default="")
