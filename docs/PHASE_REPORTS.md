# Phase reports

## Phase 1 — Audit and architecture (2026-10-28)

- Repository audit: no existing JUSTICE AI code; started a clean monorepo (`backend/`, `frontend/`, `docs/`).
- Delivered: [ARCHITECTURE.md](ARCHITECTURE.md) — product rules → enforcement points, system architecture, auth/session design, permission matrix, data model, AI/RAG design outline, legal source availability and licensing questions, roadmap with exit criteria.

## Phase 2 — Working foundation (2026-10-28)

### Completed and working (tested)
- **Accounts**: registration (terms acceptance), login, logout, sign out of all devices, email verification (single-use, 48h tokens), Argon2id hashes, opaque session tokens (only hashes stored), HttpOnly/SameSite cookies, CSRF header on all unsafe requests, login rate limiting, suspended-account blocking.
- **Settings**: name, language (English/Hindi, saved to account), state/UT (36 seeded), data retention preference, AI-processing and training-use consent (training off by default; changes audited), JSON data export, account deletion with password + typed confirmation.
- **My Cases**: private workspaces (20 practice areas, jurisdiction, stage, account of facts, desired outcome), edit, close/reopen, delete; chronological timeline with deadline marking; strict per-user isolation (other users get 404).
- **Plans/entitlements**: Free/Premium/Professional/Institutional with configurable entitlements; the open-case limit is enforced; prices left unset ("not yet announced") instead of invented.
- **Admin console** with role-based tabs: users (metadata + case counts only), roles, suspension, plan assignment (all with mandatory reason), legal source registry with official-domain URL allowlist and independent review, plans editor, feature flags, jurisdictions, append-only audit log, system health.
- **UI**: JUSTICE AI brand (ivory/navy/burgundy/champagne), 12-item navigation, home dashboard with the 7 actions, emergency 112 banner on every page, concise disclaimer, skip link, keyboard focus styles, responsive down to 375px. Modules not yet built show an honest status page with no fake controls.
- **Ops**: Alembic migration (tested down/up), seed + operator CLI, structured logs, security headers, documented env vars.

### Test results
- Backend: **35/35 passed** (`python -m pytest`), against real PostgreSQL 16 — auth, CSRF, rate limit, verification, case isolation (IDOR), entitlements, settings validation, consent audit, export, deletion, full role/permission matrix, admin cannot read case content, source review separation of duties, audit-log immutability (DB trigger), security headers.
- Browser (Playwright/Chromium, production build): **15/15 journeys passed**, twice in a row after fixes.
- Defects found by browser testing and fixed: consent checkbox did not respond until the server replied; mobile menu stayed open after navigating; saved state/UT could be shown as "Not set" when the state list loaded after the settings (same race fixed in the case edit form); duplicate disclaimer on home; mobile menu overlapped the header.

### Known limitations
See [DEFECTS_AND_RISKS.md](DEFECTS_AND_RISKS.md). Most important: no production email provider, no password reset/2FA, no field-level encryption yet, in-memory rate limiter, retention purge job not running, Hindi only partially translated and unreviewed, no payments.

### Next priorities
1. Phase 2.1 hardening: password reset, staff 2FA, email provider.
2. Phase 3: ingest a first verified slice of India Code (e.g. Constitution Part III, Consumer Protection Act 2019, BNSS arrest/bail provisions), full-text + vector search, citation verifier, Legal Library and My Legal Rights pages.

## Phase 3 — Legal research (2026-10-28)

### Key finding first
The official sites (indiacode.nic.in, sci.gov.in, egazette.gov.in, nalsa.gov.in) are blocked by this development environment's network policy, and **India Code's robots.txt disallows automated fetching**. So ingestion is built around files a legal researcher downloads by hand from the official site and uploads with its official URL and download date. No real legal text has been loaded yet: everything in tests is a clearly fictional "Test Fixture ... Act, 2099".

### Completed and working (tested)
- **Original documents stored byte-for-byte** (PDF or UTF-8 text, 25 MB limit, type sniffed from bytes, SHA-256 recorded, downloadable by staff). Scanned PDFs are rejected with a clear message until OCR arrives in Phase 5.
- **Section splitting** for Acts (handles lettered sections like 3A and skips page footnotes), Articles for the Constitution, numbered paragraphs for judgments, and a fallback for unstructured guidance.
- **Review workflow**: a source cannot be verified without its official document; the creator or uploader cannot verify it; any new document version or metadata correction sends it back for review. Only verified sources appear anywhere public.
- **Search** (Postgres full-text, weighted by heading): jurisdiction-aware (a state search includes central law and notes when both match), filters for area and type, highlighted snippets, and a partial-match fallback for natural questions that requires several shared terms so one stray word cannot "ground" an answer. When nothing matches it says so and does not guess.
- **Every result carries** title, section, citation, authority level, jurisdiction, legal status, effective date, last verification date, document hash and a View Original Source link.
- **Status and freshness**: recorded relations (amends, repeals, overrules, stays…) produce warnings on the affected section or whole source; unknown status is disclosed; sources past the re-verification window (default 180 days) are flagged and listed for reviewers; an official-link checker marks broken links and links that redirect off official domains.
- **Citation and quotation verifier**: checks section/Article/Rule references, SCC/AIR/SCR/INSC case citations and quotations word-for-word against verified sources. Phase 4 will run every AI answer through it. Also available to users in the Legal Library.
- **UI**: Legal Library (search, browse, citation checker), source pages with section anchors, My Legal Rights by area (verified sources only; plain-language guides await legal reviewers), and an admin source workspace (upload, section preview, review, metadata correction, relations, link check, stale filter).
- **Legal evaluation dataset v1**: 26 questions across 11 categories (insufficient information, outdated law, conflicting sources, fabrication bait, urgent safety, misuse, prompt injection…) with expected behaviours. Reference answers are intentionally blank for qualified reviewers. `python -m app.research.evaluate` reports grounding coverage.

### Test results
- Backend: **61/61 passed** against PostgreSQL 16 (26 new Phase 3 tests including a generated PDF, link checks via a mock transport, and parser tests on real-world Act name shapes).
- Browser (Chromium, production build, separate e2e database): **Phase 3 9/9** and **Phase 2 15/15** journeys passed.
- Defects found and fixed during testing: citations to Acts whose names contain lowercase words or numbers ("Code of Civil Procedure", "Right to Information Act") were not recognised; natural-language questions returned nothing; the first fallback then matched off-topic sections on a single shared word.

### Known limitations
- No real sources yet (see key finding). Coverage on the evaluation set is therefore 0 real questions grounded.
- Search is lexical (English stemming). pgvector is not installed here, so semantic search and Hindi-language search are still to come.
- Status changes (amendments, repeals) are recorded by researchers; nothing detects them automatically.
- The link checker runs on demand from the admin console, not on a schedule, and cannot reach the official sites from this environment.
- Uploaded files are not yet malware-scanned (they are never executed or rendered as HTML; scanning lands with user uploads in Phase 5).

### Next priorities
1. Decide how sources get loaded: a researcher uploads official files through the admin console, or the environment allows the official domains (subject to each site's terms).
2. Phase 4: provider-independent LLM gateway and the three AI roles, answering only from retrieved verified sections and passing the citation verifier, plus urgent-matter detection.

## Phase 4 — AI roles (2026-10-29)

### Key finding first
The four AI roles work end to end, but **no live model has answered a question yet**: this server has no Anthropic API key, so the AI endpoints honestly reply "not configured" and the pages say so. Every test runs against a fake provider (backend) or a local stand-in for the Anthropic API (browser journeys), which exercises the real request and response code. And because no real law is loaded yet (Phase 3 finding), a live model would currently answer "cannot verify" to almost everything, by design.

### Completed and working (tested)
- **LLM gateway** (`backend/app/ai/provider.py`): one `generate()` interface; the Anthropic implementation uses `claude-opus-5-5` (configurable with `JUSTICE_AI_MODEL`), structured outputs (a JSON schema per role), effort `medium`, a 180-second timeout, and server-side refusal fallback (`fallbacks: "default"`). Refusals, truncation, malformed output, bad keys and outages become plain messages; nothing is shown half-checked. Without `ANTHROPIC_API_KEY` the gateway reports "not configured".
- **Four roles**, each behind its feature flag (off until an administrator turns it on):
  - **Ask AI**: short grounded answers.
  - **AI Lawyer**: also gives options, procedure and documents to gather.
  - **AI Advocate**: works on one of the user's cases, giving issues, supporting points, an evidence checklist and weaknesses.
  - **AI Judge**: works on a case, covering issues, agreed and disputed facts, missing evidence, both sides' arguments, burden of proof, a hypothetical assessment in words and what could change it. Every Judge page and answer carries "Hypothetical AI legal analysis — not an actual judicial decision" (set by the server, not the model).
- **Retrieval first**: up to 8 verified sections are retrieved, using the question and, for case roles, the case title and summary. If nothing verified matches, the answer is "cannot verify", **the model is not called**, and it does not count towards usage.
- **Prompt-injection defences**: source text, the question and case facts sit inside delimited blocks that the model is told are data. Angle brackets in that text are neutralised so it cannot close a block (tested with a hostile source).
- **Every answer is checked before it is shown** (`backend/app/ai/validate.py`):
  - Statements may cite only sources that were actually retrieved.
  - Legal statements without a source are removed, and the user is told.
  - Links other than a retrieved source's official link are removed.
  - Percentages and odds are removed.
  - All remaining text goes through the Phase 3 citation verifier, and anything unverifiable is flagged.
  - An answer with no supported point becomes "cannot verify".
- **Urgent-help detection** (English, Hindi and romanised Hindi; rule-based, no AI, no login, nothing stored) covers violence, domestic violence, sexual violence, child safety, self-harm, arrest or detention and same-day or next-day deadlines. It shows "Call 112" and free legal aid at once, before the answer arrives. It names no helpline numbers beyond 112.
- **Consent and limits**:
  - AI processing consent is required; the Settings text now names Anthropic as the provider.
  - A verified email is required.
  - The plan's `ai_questions_per_month` is enforced, counted per calendar month in IST.
  - There is a per-user rate limit.
  - Deleting an answer erases its content but still counts towards usage, so the limit cannot be reset.
- **Records**:
  - Each answer stores the role, model, prompt version, provider request id, token counts, the checks report, and for every source the label, whether it was cited, the section text and the document SHA-256.
  - Answers are private to their owner: there is no staff endpoint, and this is tested.
  - Answers are included in the account export.
  - Deleting a case erases the answers about it.
  - The audit log records that an answer was produced, never its content.
- **UI**:
  - Pages for the four roles share one component, which shows a sources list with "View original source", library links and the document version.
  - It also lists what the checks removed or flagged, and the user's previous answers with delete.
  - Case pages link to AI Advocate and AI Judge.
  - The admin feature-flag toggles are now optimistic.

### Test results
- Backend: **103/103 passed** (37 new Phase 4 tests: urgency in English and Hindi, every gate, grounding, removals, injection, Judge label and no numbers, limits, privacy, export, and the Anthropic request shape and error handling via a mock transport).
- Browser (Chromium, production build, e2e database, local Anthropic stand-in): **Phase 4 9/9**, **Phase 3 9/9**, **Phase 2 15/15**.
- Defects found and fixed during testing:
  - The admin flag checkbox did not change state until the server replied.
  - The answer-history Delete button was invisible (wrong button style).
  - The Phase 2 journey still expected the AI pages to be placeholders.

### Known limitations
- **No live model run yet** (no API key here). The prompts have not been tuned against real model output, and the evaluation set has not been run through a model.
- Answer quality depends on the library, which holds no real law yet.
- Urgency detection is keyword-based: it can miss unusual phrasing and can over-trigger. It errs towards showing help.
- Hindi questions only find English sources through shared words; Hindi search awaits Phase 3's Hindi text configuration.
- The rate limiter is in-memory (defect 4).

### Next priorities
1. Add `ANTHROPIC_API_KEY` to the server environment (never to the repo), then run the evaluation set through the live model and review the answers with a qualified legal reviewer before switching any flag on for users.
2. Load real law (official domains allowed, then reviewed by a content reviewer).
3. Phase 5: uploads, OCR and Document Studio.
