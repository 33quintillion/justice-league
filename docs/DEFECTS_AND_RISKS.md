# Unresolved defects and technical risks

Kept current at the end of each phase. Severity: 🔴 must fix before any pilot, 🟠 before public launch, 🟡 improvement.

## Known limitations (Phase 2)

| # | Sev | Item | Plan |
|---|---|---|---|
| 1 | 🔴 | No production email backend. Verification works only through the development outbox. Production start-up refuses `dev_outbox`. | Integrate an email provider (SMTP/API) with bounce handling. |
| 2 | 🔴 | No password reset, no 2FA. Staff accounts especially need 2FA. | Phase 2.1: reset via single-use emailed token; TOTP for staff, mandatory before admin access in production. |
| 3 | 🔴 | Field-level encryption of case text is not implemented; relies on disk/volume encryption of the database host. | Envelope encryption for case summaries, events and documents with a KMS-held key (Phase 5, with uploads). |
| 4 | 🟠 | Login rate limiter is in-process memory: resets on restart and is per-instance. | Move to Redis or Postgres-backed counters before running more than one API instance. |
| 5 | 🟠 | Retention settings are stored but no scheduled purge job runs yet (the UI says so). | Scheduled worker that deletes closed cases past the user's retention window, with audit entries. |
| 6 | 🟠 | Hindi covers navigation, home, auth and key headings only; other strings fall back to English. Hindi copy needs native-speaker and legal-terminology review. | Move strings into dictionaries per page; professional translation; add more Indian languages. |
| 7 | 🟠 | No payment provider: plans are assigned by billing admins; prices are deliberately unset. | Phase 6. |
| 8 | 🟠 | Usage metering (`ai_questions_per_month`) is defined but not enforced because there are no AI questions yet. | Enforced in Phase 4 with a `usage_counters` table. |
| 9 | 🟠 | No break-glass access flow for legitimate support access to a case; currently staff simply cannot access cases. | Design user-consented, time-limited, audited access grant. |
| 10 | 🟡 | Admin source-review uses a browser prompt for the review note. | Replace with an inline form. |
| 11 | 🟡 | Login CSRF relies on SameSite=Lax only. | Acceptable for now; add a pre-session CSRF token if embedding contexts appear. |
| 12 | 🟡 | `pgvector` is not installed in the dev container's Postgres. | Phase 3 starts with Postgres full-text search; add pgvector in deployment images. |
| 13 | 🟡 | Jurisdiction codes follow ISO 3166-2:IN style but some ISO codes changed in 2023; treat as internal keys. | Add an `iso_code` column if interoperability needs it. |

## Risks

- **Legal accuracy**: the largest product risk. Mitigated by verified-source-only citation, independent review workflow, eval datasets and qualified legal reviewers before release (Phase 7).
- **Source access terms**: some official sites may restrict automated access (e.g. captchas on eCourts). Needs a terms review and, where necessary, permission.
- **Regulatory**: Digital Personal Data Protection Act 2023 obligations, IT Act intermediary rules, consumer protection rules, and Bar Council of India rules on advertising/solicitation (relevant to lawyer listings). A qualified legal review is required before launch; nothing here claims compliance.
- **Abuse**: the AI roles could be misused to draft false complaints. Phase 4 safeguards: refusal policies, unsupported-allegation flags, user attestations on drafts.
