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
| 8 | ✅ | ~~Usage metering not enforced.~~ Enforced in Phase 4 (monthly, IST; deleted answers still count). | Done. |
| 9 | 🟠 | No break-glass access flow for legitimate support access to a case; currently staff simply cannot access cases. | Design user-consented, time-limited, audited access grant. |
| 10 | 🟡 | Admin source-review uses a browser prompt for the review note. | Replace with an inline form. |
| 11 | 🟡 | Login CSRF relies on SameSite=Lax only. | Acceptable for now; add a pre-session CSRF token if embedding contexts appear. |
| 12 | 🟡 | `pgvector` is not installed in the dev container's Postgres. | Phase 3 starts with Postgres full-text search; add pgvector in deployment images. |
| 14 | 🔴 | No real legal sources loaded. Official sites are blocked from the dev environment and India Code's robots.txt disallows crawling. | Researchers upload official files via the admin console; get written confirmation of each site's terms before any automation. |
| 15 | 🟠 | Search is lexical only (English stemming); no semantic or Hindi search. | Add pgvector embeddings (hybrid ranking) where the extension is available; Hindi text configuration. |
| 16 | 🟠 | Amendment/repeal status is maintained by hand; nothing detects gazette changes. | Gazette monitoring workflow and periodic re-verification queue (already flagged after 180 days). |
| 17 | 🟠 | Source files are stored in Postgres (bytea) and not malware-scanned. | Move to encrypted object storage and add scanning with Phase 5 uploads. |
| 18 | 🟡 | Section splitter is heuristic; complex layouts (schedules, provisos, tables) may split imperfectly. | Reviewers see the section list before verifying; add per-site parsers as sources are added. |
| 13 | 🟡 | Jurisdiction codes follow ISO 3166-2:IN style but some ISO codes changed in 2023; treat as internal keys. | Add an `iso_code` column if interoperability needs it. |

| 19 | 🔴 | No live AI model has been run: no API key in this environment; prompts are untested against real output. | Set `ANTHROPIC_API_KEY` on the server, run the eval set, legal review before enabling flags. |
| 20 | 🟠 | Urgency detection is keyword-based (English, Hindi, romanised Hindi); misses unusual phrasing. | Expand with reviewed phrases; consider a classifier, keeping the rule-based check as the first line. |
| 21 | 🟠 | AI answers send the question, chosen case facts and retrieved law to Anthropic. Needs a DPDP Act review and a data-processing agreement before launch. | Legal/privacy review in Phase 7. |
| 22 | 🟡 | AI calls are synchronous (up to 180 s); a slow model ties up a worker. | Move to a background job with progress polling if latency is a problem. |

## Risks

- **Legal accuracy**: the largest product risk. Mitigated by verified-source-only citation, independent review workflow, eval datasets and qualified legal reviewers before release (Phase 7).
- **Source access terms**: some official sites may restrict automated access (e.g. captchas on eCourts). Needs a terms review and, where necessary, permission.
- **Regulatory**: Digital Personal Data Protection Act 2023 obligations, IT Act intermediary rules, consumer protection rules, and Bar Council of India rules on advertising/solicitation (relevant to lawyer listings). A qualified legal review is required before launch; nothing here claims compliance.
- **Abuse**: the AI roles could be misused to draft false complaints. Phase 4 safeguards: refusal policies, unsupported-allegation flags, user attestations on drafts.
