# JUSTICE AI — Phase 1: requirements, architecture and plan

Status: Phase 1 complete, Phase 2 foundation implemented (see `PHASE_REPORTS.md`).

## 1. Product scope in one paragraph

A public-interest legal information platform for India. Users learn their rights, ask questions answered from verified official sources, organise their matters in private case workspaces, generate draft documents for review, simulate both sides of a dispute (explicitly hypothetical), and find lawyers and legal aid. It is never presented as a lawyer, advocate or court. Essential rights and emergency information are never paywalled.

## 2. Non-negotiable product rules (drive the design)

| Rule | Where it is enforced |
|---|---|
| No fabricated law, citations, links or lawyer profiles | Answers may only cite rows from `legal_sources` (Phase 3). Source URLs must be https on an official-domain allowlist; a second person must verify each source. Lawyer profiles carry a verification status (Phase 6). |
| AI Judge output is always hypothetical | Fixed label rendered by the server in every Judge response (Phase 4) and shown on the module page now. |
| Private cases are isolated per user | Every case query is scoped by `owner_id`; non-owned IDs return 404. Tested. |
| Staff cannot read case contents | No admin permission or endpoint exposes cases. A future break-glass flow must be purpose-bound and audited. Tested. |
| Sensitive actions are auditable, records cannot be silently changed | `audit_logs` is append-only via a Postgres trigger. Role, plan, suspension and source-review changes require a reason. Tested. |
| Uploaded documents and web pages are data, never instructions | Phase 3–5: retrieved text goes into delimited, quoted context; tool use is disabled for content-derived instructions; prompt-injection test suite. |
| No training on private data without opt-in | `consent_training_use` defaults to false, consent changes are audited. |
| Emergency info is free and not delayed | 112 banner on every page, Legal Aid page public; urgency detection (Phase 4) short-circuits questionnaires. |

## 3. Architecture

```
Browser ──HTTPS──> Next.js (frontend/, App Router, TypeScript)
                     │  /api/* rewritten (same origin → first-party cookies)
                     ▼
                  FastAPI (backend/app)
                   ├─ auth        sessions, email verification, rate limits
                   ├─ account     settings, consent, export, deletion
                   ├─ cases       private workspaces + timelines
                   ├─ admin       RBAC console API, audit, plans, sources, flags
                   ├─ public      jurisdictions, plans, catalog, features, health
                   ├─ research    (Phase 3) ingestion, hybrid search, citation verifier
                   ├─ ai          (Phase 4) provider-independent LLM gateway + 3 roles
                   ├─ documents   (Phase 5) upload, OCR, generation, versions
                   └─ services    (Phase 6) lawyers, legal aid, billing
                     │
                     ▼
                  PostgreSQL 16  ── source of truth (users, cases, sources, audit)
                  + full-text search now, pgvector when installed (Phase 3)
                  Object storage (Phase 5) ── encrypted documents, original source files
```

Why these choices: the spec recommends Next.js + FastAPI + Postgres; Python is the stronger ecosystem for OCR, parsing and retrieval. One Postgres database keeps transactional integrity between a source's metadata, its text chunks and the answers that cite it. The vector index is derived data and can be rebuilt from stored originals, so it is never the source of truth.

### Authentication and sessions
- Argon2id password hashes; constant-shape responses for unknown user vs wrong password.
- Opaque random session token in an `HttpOnly`, `SameSite=Lax`, `Secure` (outside dev) cookie; only its SHA-256 is stored, so a database leak does not yield live sessions.
- CSRF: per-session token returned to the client and required in `X-CSRF-Token` on every unsafe request.
- Email verification required before creating case workspaces. Login rate-limited per IP+email.
- Next: password reset, optional TOTP 2FA, and staff-mandatory 2FA before production.

### Permission model

Ordinary users have no roles. Staff roles map to permissions in `backend/app/permissions.py`:

| Permission | sysadmin | legal_researcher | content_reviewer | support | billing_admin |
|---|:-:|:-:|:-:|:-:|:-:|
| users.read | ✓ | | | ✓ | ✓ |
| users.suspend | ✓ | | | ✓ | |
| roles.manage | ✓ | | | | |
| subscriptions.manage | | | | | ✓ |
| plans.manage | ✓ | | | | ✓ |
| sources.read | ✓ | ✓ | ✓ | | |
| sources.write | | ✓ | | | |
| sources.review | | | ✓ | | |
| jurisdictions.manage | ✓ | ✓ | | | |
| flags.manage | ✓ | | | | |
| audit.read / health.read | ✓ | | | | |

Separation of duties: a source cannot be verified by its author; a sysadmin cannot remove their own sysadmin role; only a sysadmin can suspend a sysadmin. No permission grants case access.

### Data model (Phase 2 tables)
`users`, `user_roles`, `user_settings` (language, state, retention, consents), `auth_sessions`, `email_tokens`, `dev_outbox` (dev only), `jurisdictions` (India + 36 states/UTs), `cases`, `case_events` (with `origin` user/ai_suggested), `plans` (configurable entitlements; prices unset until the business decides), `subscriptions`, `legal_sources` (type, authority level, effective date, legal status, review status, last verified), `feature_flags`, `audit_logs`.

Planned: `source_documents` (stored original bytes + hash), `source_chunks` (text, section path, tsvector, embedding), `source_relations` (amends/repeals/overrules/stays), `answers` + `answer_citations` (exact source versions used), `conversations`, `documents` + `document_versions`, `lawyers` + `lawyer_verifications`, `usage_counters`.

### API contracts
FastAPI generates OpenAPI at `/api/docs` in development. Validation errors return `{detail, errors:[{field,message}]}` without echoing submitted values. All IDs are UUIDs.

### AI design (Phase 3–4 outline)
- Provider-independent gateway (`ai/providers/*`) with model + prompt versions stored per answer.
- Retrieval first: hybrid Postgres full-text + vector search over verified chunks, filtered by jurisdiction and effective date.
- Generation constrained to cite chunk IDs; a verifier rejects any citation not present in the retrieved set, any URL not from a stored source, and any quotation not found verbatim.
- Output structure separates: verified law / explanation / assumptions / uncertainty / "cannot verify".
- No numeric confidence scores; confidence is explained in words from evidence and source quality.
- Urgency classifier runs before any long flow and surfaces emergency contacts first.

## 4. Legal source availability and licensing (to confirm before Phase 3)

| Source | Use | Notes / constraints |
|---|---|---|
| India Code (indiacode.nic.in) | Central and state Acts, sections | Primary statute source. Check the site's terms for bulk retrieval; prefer polite, rate-limited fetching with stored originals. |
| Supreme Court of India (sci.gov.in) | Judgments | Official PDFs; metadata quality varies, so case number/date need verification. |
| eCourts (ecourts.gov.in) | High Court / district orders | Mostly per-case lookup; may restrict automated access (captcha). Treat as link-out, not bulk ingest, unless an API or permission is obtained. |
| eGazette (egazette.gov.in) | Notifications, rules | Needed for commencement dates and amendments. |
| DoJ, NALSA, state legal services authorities | Guidance, legal aid directory | Contact details must be re-verified on a schedule. |
| State government and High Court sites | State laws, rules | Heterogeneous formats; per-state connectors. |

Government legal texts in India are generally publicly accessible, but terms of use for automated access differ per site; this needs a written review (and legal advice) before bulk ingestion. Commercial case-law databases are out of scope unless licensed.

## 5. Roadmap

| Phase | Deliverable | Exit criteria |
|---|---|---|
| 1 | This document | Reviewed by product owner |
| 2 ✅ | Auth, navigation, layouts, settings, cases, admin console, audit | Backend + browser tests pass (see report) |
| 3 | Source ingestion (India Code first: e.g. Consumer Protection Act 2019, BNSS/BNS, Constitution Part III), chunking, hybrid search, citation verifier, Legal Library + Rights pages | Every displayed authority opens its official source; freshness tests; eval set v1 |
| 4 | LLM gateway; Ask AI, Advocate, Lawyer, Judge; urgency detection; prompt-injection defences | Eval set incl. "insufficient information" cases; zero unverifiable citations in eval |
| 5 | Uploads (PDF/DOCX/images + OCR, malware scan, encryption), Document Studio, versions, DOCX/PDF export | Upload security tests; generated drafts mark placeholders and separate user facts |
| 6 | Lawyer discovery + verification workflow, legal aid directory, payment provider, usage metering | All listings verified or labelled; entitlement tests |
| 7 | Security testing, accessibility audit, legal accuracy review with qualified reviewers | No critical vulns, no cross-user leaks, no systematic citation errors |
| 8 | Deployment, monitoring, backups + restore drill, incident response, limited pilot | Recovery tested; legal/privacy review signed off |
