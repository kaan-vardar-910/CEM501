# CEM501 AI Communication Agent — Complete Project Overview

A production-style AI assistant for a **Construction Engineering & Management (CEM)**
project manager. It reads and triages an email inbox, writes a morning digest,
drafts and sends professional construction documents, generates structured daily
site reports, and pushes urgent alerts to Telegram — all from a single local web
dashboard, with a human always in the loop before anything is sent.

This document explains **every process, the architecture, and all features** in
one place. For the original CLI-era architecture decisions (ADRs) see
[`ARCHITECTURE.md`](ARCHITECTURE.md); for quick-start setup see [`README.md`](README.md).

---

## 1. What the system does (at a glance)

| Capability | Summary |
|---|---|
| **Inbox & Triage** | Fetch recent emails over IMAP, classify each as URGENT / ACTION / FYI / ARCHIVE. |
| **Morning Digest** | One-screen summary; LLM one-sentence summaries + recommended actions for the important mail. |
| **Reply & Send** | Turn a few words into a professional reply; send through 4 safety guardrails; attach saved documents. |
| **Create Document** | Generate RFIs, Submittal Transmittals and Delay Notices via the LLM; export to Word/PDF; email them. |
| **Contract extraction** | Read an uploaded contract and auto-fill Delay Notice fields (project, contract no., governing clause). |
| **Daily Report** | Upload site notes/emails/spreadsheets → LLM extracts quantitative fields → generate a formal report → export Word/PDF/Excel → email → finalize. |
| **Contacts** | Auto-captured senders; classify as Normal / VIP / Urgent to influence triage. |
| **Memory** | Cross-session stats + a browsable, filterable list of every saved document. |
| **Settings** | Sender profile (signature), default project, project city (auto-weather), editable triage keywords. |
| **Telegram alerts** | Manual and automatic push of URGENT emails to a Telegram chat (deduplicated). |

---

## 2. Technology stack

- **Language:** Python 3 (standard library first).
- **Web server:** `http.server.ThreadingHTTPServer` — no web framework. JSON
  endpoints + a single-page dashboard (`project/web/index.html`, vanilla JS).
- **LLM:** Anthropic Claude (`anthropic` SDK), model `claude-sonnet-4-6`.
- **Email:** `imaplib` (IMAP, read) and `smtplib` (SMTP, send), stdlib `email`.
- **Documents:** `python-docx` (Word), `reportlab` / `docx2pdf` (PDF),
  `openpyxl` (Excel), `pypdf` (read PDF source text).
- **Weather:** Open-Meteo free API (`httpx`).
- **Messaging:** Telegram Bot API (`requests`).
- **Reliability on Windows:** `truststore` (uses the OS certificate store to
  avoid `CERTIFICATE_VERIFY_FAILED` on intercepted TLS).
- **Config:** `python-dotenv` reads a local `.env`.

All external calls degrade gracefully: a missing key or a network failure
produces a readable warning/error string and never crashes the pipeline.

---

## 3. Architecture overview

The system is organized in four layers:

```
┌──────────────────────────────────────────────────────────────────┐
│  PRESENTATION   project/web/index.html (SPA: tabs, fetch() calls)  │
├──────────────────────────────────────────────────────────────────┤
│  API / ROUTING  project/webapp.py (ThreadingHTTPServer, JSON API)  │
├──────────────────────────────────────────────────────────────────┤
│  DOMAIN SERVICES                                                    │
│   reader · digest · templates · document_formatter ·               │
│   document_sender · daily_report_store · daily_report_generator ·   │
│   daily_report_excel · weather · contacts · profiles · memory ·     │
│   telegram_notifier · agent (guardrails+send)                       │
├──────────────────────────────────────────────────────────────────┤
│  DATA / EXTERNAL                                                    │
│   JSON files · outputs/ · reports/ · contracts/ ·                   │
│   IMAP · SMTP · Claude API · Telegram API · Open-Meteo             │
└──────────────────────────────────────────────────────────────────┘
```

Key principle: the **web UI and the CLI share the same domain code**. Triage,
drafting, guardrails and memory are identical whether invoked from the dashboard
or the terminal.

---

## 4. File & directory map

```
Final Project/
├─ project/
│  ├─ webapp.py                 # Web server + all JSON API endpoints
│  ├─ web/index.html            # Single-page dashboard (UI + JS)
│  ├─ agent.py                  # CLI entry, send guardrails, send_email_web()
│  ├─ reader.py                 # IMAP fetch + keyword triage engine
│  ├─ digest.py                 # Morning digest builder/renderer
│  ├─ templates.py              # Claude calls: RFI/Submittal/Delay/reply/summary/contract-extract
│  ├─ document_formatter.py     # Save generated text as .docx / .pdf
│  ├─ document_sender.py        # Email a document with attachments (guardrailed)
│  ├─ daily_report_store.py     # Daily report storage, indexing, source file extraction
│  ├─ daily_report_generator.py # LLM field extraction + report-text generation
│  ├─ daily_report_excel.py     # Styled multi-sheet Excel workbook builder
│  ├─ weather.py                # Open-Meteo morning/afternoon weather
│  ├─ contacts.py               # Contact book + importance overrides
│  ├─ profiles.py               # Sender profiles (signature, project, city)
│  ├─ memory.py                 # Cross-session JSON memory
│  ├─ telegram_notifier.py      # Telegram alerts/digest push
│  ├─ cities.py                 # City → (lat, lng) lookup for the location picker
│  ├─ demo.py                   # Scripted end-to-end demo
│  ├─ contacts.json             # Persisted contacts
│  ├─ profiles_config.json      # Persisted profiles + active profile
│  ├─ triage_config.json        # Persisted triage keyword overrides
│  ├─ memory.json               # Persisted memory
│  ├─ telegram_sent.json        # Dedup log of Telegram-alerted emails
│  ├─ sent_log.txt              # Audit trail of every send
│  ├─ outputs/                  # Generated RFIs/Submittals/Delay notices (docx/pdf)
│  ├─ reports/                  # Daily reports: index.json + per-report folders
│  ├─ contracts/               # Uploaded contract files (source material)
│  └─ templates/                # Reference markdown prompt templates
├─ ARCHITECTURE.md              # Original ADRs and component spec
├─ README.md                    # Setup & quick start
├─ PROJECT_OVERVIEW.md          # (this file)
├─ .env / .env.example          # Secrets / template
└─ .gitignore
```

### Data stores

- **JSON config files** (next to the modules): contacts, profiles, triage
  config, memory, Telegram dedup — all human-readable and hand-editable.
- **`outputs/`** — flat folder of generated documents named
  `DOCTYPE_YYYYMMDD_HHMMSS.ext` (e.g. `RFI_20260608_200555.pdf`).
- **`reports/`** — `index.json` (master list) plus one folder per report
  (`DR-NNN_<date>/`) containing `report.json`, the exported `.docx/.pdf/.xlsx`,
  and a `source_files/` subfolder of uploaded material.
- **`contracts/`** — uploaded contract documents used as source for extraction.

---

## 5. External integrations

| Integration | Protocol / API | Used by | Failure behavior |
|---|---|---|---|
| Mail (read) | IMAP over SSL (993) | `reader.py` | Falls back to built-in test emails if creds missing; conn closed in `finally`. |
| Mail (send) | SMTP + STARTTLS (587) | `agent.py`, `document_sender.py` | Catches auth/SMTP errors; nothing logged as sent on failure. |
| Claude | Anthropic SDK | `templates.py` (+ generators) | `_call_claude` returns `[ERROR] …`; callers keep running. |
| Telegram | Bot API (`sendMessage`) | `telegram_notifier.py` | Returns `False` on missing token/network; pipeline unaffected. |
| Weather | Open-Meteo REST | `weather.py` | Returns empty/placeholder summary on error. |

---

## 6. Core modules in detail

### 6.1 `reader.py` — fetch + triage

**Fetching.** Connects to IMAP over SSL, pulls the newest *N* messages
(`fetch_recent_emails`, newest-first), decodes RFC 2047 MIME headers
(`_decode_mime`), and extracts the **full plain-text body** (`_extract_body_text`
prefers `text/plain`, falls back to HTML with tags stripped). The full body is
kept separately from the 200-char `preview` so LLM summaries never see a
truncated email. The IMAP connection is always closed in a `finally` block, and
if credentials are missing the reader **transparently falls back** to three
built-in CEM test emails so the app is demoable with zero setup.

**Triage algorithm (`triage_email`).** Deterministic, fast and explainable — no
LLM call per email. Matching is **whole-word, case-insensitive** over the
combined `sender + subject` string (word boundaries via `\b`, so "schedule"
matches in "schedule update" but not in "Scheduler", while "RFI" still matches
inside "RFI-047"). Categories are evaluated in **strict severity order** and the
first hit wins, so an email can never be silently downgraded:

```
URGENT  →  ACTION  →  FYI  →  ARCHIVE   (highest matching severity wins)
```

**Override precedence (applied after keyword matching), highest authority last:**
1. Keyword match sets the base category.
2. **VIP sender name** (display contains an entry in `KNOWN_VIP`, e.g. "owner",
   "inspector", "architect"): raises the floor to **ACTION**, never demotes an
   URGENT.
3. **Contact-book importance** (looked up by exact email address) takes final
   precedence: `urgent` → forces **URGENT**; `vip` → at least **ACTION**;
   `normal` → no effect.

*Example:* subject "Weekly progress update" from `owner@example.com` who is a
`vip` contact → keywords say FYI, but the VIP/contact override lifts it to
ACTION so it surfaces near the top.

**Editable at runtime.** The four keyword sets (URGENT/ACTION/FYI + VIP names)
have factory defaults but can be overridden via `triage_config.json` from the
Settings tab. `save_triage_config()` normalizes/de-dupes input, falls back to
defaults for any empty set (so you can never end up with zero urgent keywords),
and `reload_triage_config()` mutates the **module-level lists in place** — the
running server picks up changes with **no restart**.

**Auto-capture.** Every fetched sender is upserted into the contact book as
`normal` (existing classifications preserved), then the in-memory
`email → importance` cache is refreshed so subsequent triage reflects it.

### 6.2 `digest.py` — morning digest
- Groups triaged emails; for **URGENT/ACTION only** it calls
  `summarize_with_action()` to produce a one-sentence summary + a very short
  recommended action (token-efficient: FYI/ARCHIVE get no LLM call).
- `build_digest_data()` returns a structured dict (counts, categories, action
  list, flagged VIP/urgent contacts) consumed by both the text renderer and the
  HTML dashboard.

### 6.3 `templates.py` — all LLM document generation
- `_call_claude(system, user, max_tokens)` — single choke point for the API key,
  client construction, TLS fix and error handling. `max_tokens` is tunable.
- Generators: `draft_rfi`, `draft_submittal_transmittal`, `draft_delay_notice`,
  `draft_email_reply`, `summarize_email`, `summarize_with_action`.
- `extract_contract_fields(text)` — reads contract text, returns JSON
  (`project_name`, `contract_no`, `contract_section`, `parties`) with salvage
  parsing; input capped to 14k chars.

### 6.4 `document_formatter.py` / `document_sender.py`
- Formatter saves generated text as styled **Word** and **PDF**, named under
  `outputs/`. `get_output_path()` builds the timestamped filename.
- Sender builds a **multipart** email with attachments and runs the same
  guardrails as `agent.py`, plus auto subject/body (`build_default_subject`,
  `build_default_body` — the cover note is LLM-drafted with a plain fallback).

### 6.5 Daily Report subsystem

This is the most involved feature. Three modules cooperate: a **store** (disk +
indexing), a **generator** (the two LLM passes), and an **Excel builder**.

#### `daily_report_store.py` — storage & indexing
- **Identity:** each report has a number `DR-NNN` and an id `DR-NNN_<date>`.
  `get_next_report_id()` reads the running counter in `index.json`.
- **On-disk layout:**
  ```
  reports/
  ├─ index.json                 # master list + last_report_number
  └─ DR-007_2026-06-08/
     ├─ report.json             # structured fields + status + metadata
     ├─ source_files/           # uploaded raw material (copied in)
     ├─ DR-007_2026-06-08.docx  # exports (created on Save as)
     ├─ DR-007_2026-06-08.pdf
     └─ DR-007_2026-06-08.xlsx
  ```
- **`report.json` shape (key fields):** `id`, `report_number`, `date`,
  `project_name`, `prepared_by`, `weather_morning`, `weather_afternoon`,
  `manpower`, `equipment`, `work_performed`, `delays_issues`,
  `safety_observations`, `visitors`, `source_files[]`, `status`
  (`draft` → `finalized`).
- **Source ingestion:** `upload_source_file()` copies the file in and runs
  `_extract_text()`, which understands **`.txt / .pdf / .docx / .eml / .xlsx /
  .xlsm / .csv`** (each with its own reader; failures are logged, never fatal).
  `get_source_texts()` concatenates all extracted text for the LLM.
- **Lifecycle helpers:** `find_today_draft()` (powers resume-today vs. start-
  fresh), `mark_finalized()`, `delete_report()`, `list_reports()` (newest first).

#### `daily_report_generator.py` — the two LLM passes
1. **Extraction** (`extract_fields_from_sources`): combines all source text
   (capped at `_MAX_SOURCE_CHARS = 14000` to protect the context window), then
   asks Claude (`max_tokens=3000`) to return **only JSON** for the six
   extractable fields. The system prompt forces **quantitative, telegraphic**
   output — lead with the number/unit, no sentences, e.g. `Carpenters x6,
   Laborers x4`, `Excavator x2 (active)`, `Footings poured — 45 m³ @ grid A-C`.
   It must extract **only what's in the text** (no invention) and never copy
   tables verbatim. Robustness: `_strip_json_fences` + `_salvage_json` recover
   whole key/value pairs even if the reply is **truncated mid-JSON**, so a
   partial answer is never thrown away.
2. **Generation** (`generate_report_text`): turns the structured fields into a
   **scannable, numbers-first** 7-section report (Header, Weather, Manpower,
   Equipment, Work Performed, Delays/Issues, Safety). The prompt forbids
   narrative paragraphs/filler, requires one data point per bullet (~15 words
   max), shows totals where derivable, and writes "None reported." for empty
   sections.

#### `daily_report_excel.py` — styled workbook
Builds a multi-sheet `.xlsx` (Labor & Progress Log, Machinery & Equipment Log,
HSE & Security Register) with a consistent color theme, fonts, borders, number
formats and formulas (e.g. gross/idle hours). Because Excel is built from the
**structured `report.json`**, the Excel export works even when no narrative text
has been generated.

### 6.6 Supporting modules
- **`weather.py`** — resolves site coordinates from the active profile (city) or
  `.env`, fetches morning/afternoon summaries from Open-Meteo.
- **`contacts.py`** — JSON contact book; importance levels `normal/vip/urgent`;
  `bulk_upsert_senders` for auto-capture; `cc_always` support.
- **`profiles.py`** — multiple sender profiles (name, title, company, phone,
  email, default project, **city + lat/lng**), an active profile, and a rendered
  signature block injected into every draft.
- **`memory.py`** — `memory.json`: sender profiles, sent history, user
  corrections, run stats.
- **`telegram_notifier.py`** — defensive `sendMessage` wrapper for alerts/digest.

---

## 7. Features end-to-end

### 7.1 Inbox & Triage
Load inbox → server fetches via IMAP (or test data) → each email triaged →
table sorted by severity. Auto-captures senders to Contacts. Optional
**Auto-alert new URGENT** checkbox and a manual **URGENT → Telegram** button.

### 7.2 Morning Digest
"Generate digest" → color-coded sections, bold highlights, an **Action Items /
To-do** list with very short **Recommended** actions, and VIP/Urgent contact
flags. Always reminds the reader that AI summaries are drafts.

### 7.3 Reply & Send (with attachments)
1. Open from an inbox email (carries subject, sender, body, 1-sentence summary).
2. Type a few words; **Draft professional reply** expands it via Claude using the
   original email as context.
3. Edit the draft. Optionally tick saved documents under **Attachments**
   (loaded from `outputs/` via `/api/outputs`).
4. **Review & send** runs the four guardrails; **Dry run** is on by default.

### 7.4 Create Document (RFI / Submittal / Delay Notice)
Pick a type, fill fields, **Generate** (LLM). **Save** to Word/PDF/Both (lands in
`outputs/` and triggers a browser download). **Send** opens a dialog with To/CC/
BCC, contact picker, auto subject/body, and attaches the generated file(s).

**Contract extraction (Delay Notice):** choose an uploaded contract → **Extract
fields** → `/api/contract-files/extract` reads the file and uses Claude to fill
**Project**, **Contract no.**, and the governing **Contract section**.

### 7.5 Daily Report (full lifecycle)
1. **+ New Report** — starts a fresh report (or resumes today's draft); auto
   number, profile defaults, auto-weather from the profile city. Clicking it
   when a report already has content asks before starting a brand-new one.
2. **Upload source files** — site notes, emails, spreadsheets, PDFs. Text is
   extracted and stored.
3. **Extract fields** — Claude pulls quantitative fields from all sources.
4. **Generate** — produces the terse, numbers-first report text.
5. **Save as** — Word, PDF, or **Excel** (Excel is built from structured data,
   so it works even without generated narrative). Files download automatically.
6. **Send** — emails the report; **Finalize** locks it.
7. **Past Reports** — list, open, edit, re-export, delete prior reports.

### 7.6 Contacts (People)
Auto-captured + manually addable. Classify **Normal / VIP / Urgent**; changes
apply to triage immediately. Used by the digest to flag important senders.

### 7.7 Contracts (Files)
Upload/list/delete contract documents in `contracts/`. They are the source for
Delay Notice contract extraction (and can be read by the daily report extractor).

### 7.8 Memory
Shows run stats, known profiles, sent history, and a **Saved Documents** table
that merges `outputs/` documents **and** daily-report exports. Each row has a
type badge, **Download**, and **Delete**; a **Filter by type** dropdown
(All / RFI / Submittal / Delay Notice / Daily Report) narrows the list.

### 7.9 Settings
- **Sender Profile:** identity + signature, default project (auto-filled into
  document forms), and **Project location (city)** → sets site lat/lng used by
  the Daily Report weather panel.
- **Triage Settings:** edit URGENT/ACTION/FYI keywords and VIP senders; **Save &
  apply** updates the live server with no restart.

### 7.10 Telegram alerts
URGENT emails can be pushed to a Telegram chat — manually (button) or
automatically (checkbox). `telegram_sent.json` deduplicates so the same email is
not alerted twice; a `force` option overrides dedup.

---

## 8. Safety guardrails (every send)

The send path is the highest-risk part of the system (a misdirected or
hallucinated email can do real damage), so **four guardrails** run on every send,
identically for the CLI and the web UI. The pure-logic checks
(`validate_recipient`, `check_content`, `_within_rate_limit`) live in `agent.py`
and are reused by `document_sender.py` and `send_email_web`.

1. **Human confirmation (mandatory, un-bypassable).**
   - CLI: an explicit `y` keystroke after the full To/Subject/Body is printed.
   - Web: the "Send" click **is** the confirmation, so guardrails 2–4 then run
     programmatically. Nothing is ever sent autonomously.

2. **Recipient validation (`validate_recipient`).**
   - **Hard block:** more than **5 recipients** (across To + CC + BCC) aborts the
     send entirely.
   - **Warnings (non-blocking):** recipient not in `KNOWN_CONTACTS`; domain looks
     like a typo (`gmial`, `yhaoo`, `outlok`).

3. **Content checks (`check_content`).** Warns on: empty subject; leftover
   placeholder tokens (`[INSERT]`, `[TODO]`, `[PLACEHOLDER]`, `[YOUR NAME]`);
   body shorter than 30 characters.

4. **Rate limiting (`_within_rate_limit`).** A rolling window allows at most
   `MAX_SENDS = 10` sends per `RATE_WINDOW_SECONDS = 600` (10 minutes). Old
   timestamps are pruned on each check; the new send is recorded **only on
   success**, so blocked/failed attempts don't consume the budget.

**Audit & safety defaults.** Every successful send is appended to `sent_log.txt`
(recipients, subject, body). **Dry run is on by default everywhere** — in dry-run
mode SMTP is skipped entirely and the response reports exactly what *would* have
been sent (including attachment count). SMTP auth/network errors are caught and
reported; nothing is logged as sent on failure.

---

## 9. Web API reference (selected)

> Base: `http://127.0.0.1:8000`. GET = read, POST = action. JSON in/out.

**Read / triage / digest**
- `GET /api/status`, `GET /api/inbox?test=true|false`
- `POST /api/draft-reply`, `POST /api/send` (`attachments[]` supported)

**Documents**
- `POST /api/rfi`, `/api/submittal`, `/api/delay`
- `POST /api/doc/save`, `/api/doc/draft-body`, `/api/doc/send`
- `GET /api/outputs`, `GET /api/output-file?name=…`, `POST /api/output-files/delete`

**Contracts**
- `GET /api/contract-files`, `POST /api/contract-files`,
  `/api/contract-files/delete`, `/api/contract-files/extract`

**Daily report**
- `POST /api/report/init` (`force_new`), `/save`, `/upload`, `/remove-source`,
  `/extract`, `/generate`, `/save-files`, `/subject-body`, `/send`, `/finalize`,
  `/delete`
- `GET /api/reports`, `GET /api/report?id=…`,
  `GET /api/report/file?id=…&fmt=docx|pdf|xlsx`, `POST /api/report-file/delete`

**Contacts / profiles / triage / memory / weather / cities / telegram**
- `GET|POST /api/contacts`, `GET|POST /api/profiles`, `GET|POST /api/triage-config`
- `GET /api/memory` (now includes `documents[]`)
- `GET /api/weather`, `GET /api/cities`, `POST /api/telegram-urgent`

---

## 10. Representative process flows

**Send a reply**
```
UI Reply tab → /api/draft-reply (Claude) → user edits → select attachments
   → /api/send → guardrails (confirm/recipient/content/rate) → SMTP → sent_log.txt
```

**Daily report**
```
+ New Report → /api/report/init → upload sources (/upload, text extracted)
   → /extract (Claude: quantitative fields) → /generate (Claude: terse report)
   → /save-files (docx/pdf/xlsx in reports/<id>/) → auto-download
   → /send (email) → /finalize (lock)
```

**Contract → Delay Notice**
```
Contracts tab: upload contract → Delay form: pick file → /contract-files/extract
   (read text + Claude) → fields auto-filled → Generate → Save/Send
```

---

## 11. Security & privacy

- All secrets via `os.getenv()` from a **gitignored** `.env`; nothing hardcoded.
- Use provider **app passwords**, not the account password.
- File-serving/upload endpoints resolve paths with `basename` + directory checks
  to prevent **path traversal** (only `outputs/`, `reports/`, `contracts/`).
- Intended for **anonymized or fictional** scenario data; do not paste real PII
  or privileged correspondence into the cloud LLM.

---

## 12. Running it

```bash
cd "project"
pip install -r ../requirements.txt          # anthropic, python-docx, reportlab,
                                            # openpyxl, pypdf, httpx, requests,
                                            # python-dotenv, truststore, colorama…
python webapp.py                            # → http://127.0.0.1:8000
```

Configure `.env` (see `.env.example`): `ANTHROPIC_API_KEY`, `EMAIL_ADDRESS`,
`EMAIL_PASSWORD`/`APP_PASSWORD`, `IMAP_SERVER`, `SMTP_HOST`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID`, and optional `SITE_LAT`/`SITE_LNG`. Without credentials the
app still runs on built-in test data, and LLM features show readable error text.

CLI/demo: `python agent.py` (interactive) or `python demo.py` (scripted). Module
self-tests: `python reader.py`, `python digest.py`,
`python daily_report_generator.py`, etc.

---

## 13. Limitations & future work

- Polling (no IMAP IDLE/push); a cron run mitigates digest latency.
- JSON file storage (no DB) — great for demos, not concurrent multi-user use.
- Triage is keyword-based (fast, explainable); novel phrasings can be
  miscategorized — `user_corrections` captures these for future tuning.
- Daily-report attachments to Reply & Send are currently sourced from `outputs/`
  only (report exports are downloadable from Memory).
- Future: WhatsApp/Slack channels, vector search over history, scheduled digests,
  attachment summarization, RFI log tracker, Procore/ACC integration.
```
