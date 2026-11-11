import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .catalog import AUTHORITY_LEVELS, CASE_STAGES, LANGUAGES, LEGAL_STATUSES, MATTER_TYPES, SOURCE_TYPES


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _one_of(allowed: list[str], name: str):
    def check(v):
        if v is not None and v not in allowed:
            raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
        return v

    return check


def _check_areas(v: list[str] | None) -> list[str] | None:
    if v is None:
        return v
    bad = [a for a in v if a not in MATTER_TYPES]
    if bad:
        raise ValueError(f"Unknown practice areas: {', '.join(bad)}")
    return sorted(set(v))


# ---- auth ----
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(default="", max_length=120)
    accept_terms: bool

    @field_validator("accept_terms")
    @classmethod
    def must_accept(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the terms and privacy notice")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class TokenIn(BaseModel):
    token: str = Field(max_length=200)


class MeOut(ORM):
    id: uuid.UUID
    email: str
    display_name: str
    email_verified: bool
    roles: list[str]
    permissions: list[str]
    plan_code: str
    csrf_token: str


# ---- settings ----
class SettingsOut(ORM):
    display_name: str
    preferred_language: str
    country_code: str
    state_code: str | None
    retention_days: int | None
    consent_ai_processing: bool
    consent_training_use: bool
    consent_updated_at: datetime | None


class SettingsIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    preferred_language: str | None = None
    state_code: str | None = Field(default=None, max_length=10)
    clear_state: bool = False
    retention_days: int | None = Field(default=None, ge=30, le=3650)
    keep_until_deleted: bool = False
    consent_ai_processing: bool | None = None
    consent_training_use: bool | None = None

    _lang = field_validator("preferred_language")(_one_of(LANGUAGES, "preferred_language"))


class PasswordConfirmIn(BaseModel):
    password: str = Field(max_length=200)
    confirm_text: Literal["DELETE MY ACCOUNT"]


# ---- cases ----
class CaseEventIn(BaseModel):
    event_date: date
    description: str = Field(min_length=1, max_length=5000)
    is_deadline: bool = False


class CaseEventOut(ORM):
    id: uuid.UUID
    event_date: date
    description: str
    is_deadline: bool
    origin: str
    created_at: datetime


class CaseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    matter_type: str
    jurisdiction_code: str = Field(max_length=10)
    stage: str = "not_started"
    summary: str = Field(default="", max_length=20000)
    desired_outcome: str = Field(default="", max_length=5000)

    _mt = field_validator("matter_type")(_one_of(MATTER_TYPES, "matter_type"))
    _st = field_validator("stage")(_one_of(CASE_STAGES, "stage"))


class CasePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    matter_type: str | None = None
    jurisdiction_code: str | None = Field(default=None, max_length=10)
    stage: str | None = None
    summary: str | None = Field(default=None, max_length=20000)
    desired_outcome: str | None = Field(default=None, max_length=5000)
    status: Literal["open", "closed"] | None = None

    _mt = field_validator("matter_type")(_one_of(MATTER_TYPES, "matter_type"))
    _st = field_validator("stage")(_one_of(CASE_STAGES, "stage"))


class CaseSummaryOut(ORM):
    id: uuid.UUID
    title: str
    matter_type: str
    jurisdiction_code: str
    stage: str
    status: str
    created_at: datetime
    updated_at: datetime


class CaseOut(CaseSummaryOut):
    summary: str
    desired_outcome: str
    events: list[CaseEventOut]


# ---- public catalog ----
class JurisdictionOut(ORM):
    code: str
    name: str
    kind: str
    parent_code: str | None
    enabled: bool


class PlanOut(ORM):
    code: str
    name: str
    description: str
    price_minor: int | None
    currency: str
    billing_interval: str | None
    renewal_terms: str
    entitlements: dict
    is_public: bool
    sort_order: int


# ---- admin ----
class AdminUserOut(BaseModel):
    """Account metadata only. Never includes case content."""

    id: uuid.UUID
    email: str
    display_name: str
    email_verified: bool
    is_suspended: bool
    roles: list[str]
    plan_code: str
    created_at: datetime
    case_count: int


class RolesIn(BaseModel):
    roles: list[str]
    reason: str = Field(min_length=5, max_length=500)


class SuspendIn(BaseModel):
    suspended: bool
    reason: str = Field(min_length=5, max_length=500)


class SubscriptionIn(BaseModel):
    plan_code: str
    reason: str = Field(min_length=5, max_length=500)


class PlanPatch(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    description: str | None = None
    price_minor: int | None = Field(default=None, ge=0)
    clear_price: bool = False
    billing_interval: Literal["month", "year"] | None = None
    renewal_terms: str | None = None
    entitlements: dict | None = None
    is_public: bool | None = None


class SourceIn(BaseModel):
    title: str = Field(min_length=3, max_length=400)
    source_type: str
    authority_level: str
    jurisdiction_code: str = Field(max_length=10)
    official_url: str = Field(max_length=1000)
    publisher: str = Field(default="", max_length=200)
    citation: str = Field(default="", max_length=300)
    effective_date: date | None = None
    legal_status: str = "unknown"
    notes: str = Field(default="", max_length=5000)
    practice_areas: list[str] = Field(default_factory=list, max_length=20)
    language: str = "en"

    _t = field_validator("source_type")(_one_of(SOURCE_TYPES, "source_type"))
    _l = field_validator("language")(_one_of(LANGUAGES, "language"))

    _pa = field_validator("practice_areas")(_check_areas)
    _a = field_validator("authority_level")(_one_of(AUTHORITY_LEVELS, "authority_level"))
    _s = field_validator("legal_status")(_one_of(LEGAL_STATUSES, "legal_status"))


class SourceOut(ORM):
    id: uuid.UUID
    title: str
    source_type: str
    authority_level: str
    jurisdiction_code: str
    official_url: str
    publisher: str
    citation: str
    effective_date: date | None
    legal_status: str
    review_status: str
    notes: str
    created_by: uuid.UUID | None
    created_at: datetime
    reviewed_by: uuid.UUID | None
    last_verified_at: datetime | None
    practice_areas: list[str]
    language: str
    link_status: str
    link_checked_at: datetime | None


class SourcePatch(BaseModel):
    """Metadata corrections. Any change sends the source back for review."""

    title: str | None = Field(default=None, min_length=3, max_length=400)
    citation: str | None = Field(default=None, max_length=300)
    effective_date: date | None = None
    legal_status: str | None = None
    practice_areas: list[str] | None = None
    reason: str = Field(min_length=5, max_length=1000)

    _s = field_validator("legal_status")(_one_of(LEGAL_STATUSES, "legal_status"))
    _pa = field_validator("practice_areas")(_check_areas)


class RelationIn(BaseModel):
    target_source_id: uuid.UUID
    kind: str
    target_section_ref: str = Field(default="", max_length=30)
    effective_date: date | None = None
    note: str = Field(default="", max_length=2000)


class DocumentOut(ORM):
    id: uuid.UUID
    filename: str
    media_type: str
    sha256: str
    size_bytes: int
    retrieved_from_url: str
    retrieved_at: date
    uploaded_by: uuid.UUID | None
    uploaded_at: datetime
    is_current: bool
    extracted_chars: int


class SectionOut(ORM):
    id: uuid.UUID
    ordinal: int
    ref: str
    heading: str
    text: str


class ReviewIn(BaseModel):
    decision: Literal["verified", "rejected"]
    notes: str = Field(min_length=5, max_length=2000)


class FlagOut(ORM):
    key: str
    description: str
    enabled: bool
    updated_at: datetime


class FlagIn(BaseModel):
    enabled: bool


class JurisdictionPatch(BaseModel):
    enabled: bool


class AuditOut(ORM):
    id: int
    created_at: datetime
    actor_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    details: dict
    ip: str
