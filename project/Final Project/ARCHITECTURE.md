# ARCHITECTURE — CEM501 AI Communication Agent

## Section 1 — Overview

The CEM501 AI Communication Agent is a personal assistant for a construction
project manager that reads an email inbox, triages every message by urgency,
produces a daily morning digest, drafts professional CEM documents and reply
emails, and sends approved replies only after explicit human confirmation. It
connects to four external systems: a mail provider over **IMAP** (port 993,
SSL) for reading, the same provider over **SMTP** (port 587, STARTTLS) for
sending, the **Anthropic Claude API** for all natural-language generation, and
the **Telegram Bot API** for pushing urgent alerts to a second channel. It is
designed to be run from the command line with anonymized or fictional scenario
data and keeps a small persistent memory between sessions.

## Section 2 — Components

### Reader
- **Responsibility:** Connect to IMAP, fetch the most recent emails and extract
  sender, subject, date and a body preview.
- **Input:** IMAP credentials from `.env`; a count of messages to fetch.
- **Output:** A list of email dicts (`sender`, `subject`, `date`, `preview`,
  `triage_category`).
- **File:** `project/reader.py`

### Classifier (built into Reader)
- **Responsibility:** Assign each email one of URGENT / ACTION / FYI / ARCHIVE
  using whole-word keyword matching plus a VIP sender floor.
- **Input:** Sender display string and subject line.
- **Output:** A single triage category string.
- **File:** `project/reader.py` (`triage_email`)

### Templates / Drafter
- **Responsibility:** Generate formal CEM documents (RFI, submittal
  transmittal, delay notice), reply emails and one-sentence summaries via the
  Claude API.
- **Input:** Structured field arguments (project, drawing ref, spec ref, etc.)
  and `ANTHROPIC_API_KEY`.
- **Output:** Generated document text (also printed).
- **File:** `project/templates.py`

### Digest
- **Responsibility:** Group triaged emails by category and render the morning
  digest, summarizing only URGENT/ACTION items to save tokens.
- **Input:** A list of triaged email dicts.
- **Output:** A formatted digest string (also printed).
- **File:** `project/digest.py`

### Sender
- **Responsibility:** Send a reply over SMTP after passing all four guardrails;
  log every send to an audit file.
- **Input:** Recipient, subject, body and a dry-run flag; SMTP credentials.
- **Output:** Boolean success; an appended line in `sent_log.txt`.
- **File:** `project/agent.py` (`send_email`)

### Memory
- **Responsibility:** Persist sender profiles, sent history, user corrections
  and run statistics across sessions.
- **Input:** The in-memory dict and incremental updates.
- **Output:** `project/memory.json` on disk; category hints on read.
- **File:** `project/memory.py`

### Telegram Notifier
- **Responsibility:** Push URGENT alerts and the digest to a Telegram chat as a
  second channel.
- **Input:** Subject/sender/preview (or digest text); bot token and chat id.
- **Output:** Boolean success; a delivered Telegram message.
- **File:** `project/telegram_notifier.py`

## Section 3 — Data Flow Diagram

```
                         ┌───────────────────────┐
                         │   Templates / Drafter │
                         │   (Claude API)        │
                         └───────────┬───────────┘
                                     │ generated draft text
                                     ▼
IMAP ──raw msgs──> Reader ──parsed email──> Triage ──category──> Drafter
                      ▲                        │                    │
                      │                        │ URGENT alert       │ draft reply
   credentials (.env) │                        ▼                    ▼
                      │                  Telegram API          Guardrails
                      │                                       (confirm, recipient,
                      │                                        content, rate-limit)
                      │                                             │ approved
   category hint <────┴──────── Memory <──profile/stats update─────┤
   (read on triage)             (memory.json)                      ▼
                                     ▲                            Sender
                                     │ sent_history write           │ MIME
                                     └──────────────────────────────┤
                                                                     ▼
                                                                   SMTP
```

Arrow legend: IMAP→Reader carries raw RFC822 messages; Reader→Triage carries
parsed email fields; Triage→Drafter carries the category that selects which
emails get a reply; Triage→Telegram carries URGENT alert payloads; Templates→
Drafter carries the generated draft text; Drafter→Guardrails carries the draft
awaiting approval; Guardrails→Sender carries the approved email; Sender→SMTP
carries the MIME message; Memory↔pipeline carries category hints (read) and
profile/stats/sent-history (write).

## Section 4 — Design Decisions (ADR)

### ADR-001: Human-in-the-loop confirmation before every send
- **Decision:** No email is ever sent without an explicit, un-bypassable `y`
  confirmation showing the full To/Subject/Body.
- **Context:** Misdirected and erroneous email is among the most common and
  most damaging communication failures; an autonomous send loop could broadcast
  a hallucinated or mis-addressed message instantly.
- **Consequences:** The agent cannot run fully unattended, but every outbound
  message has a human accountable for it. This is the core safety property of
  the system.

### ADR-002: Keyword-based triage vs. LLM-based triage
- **Decision:** Triage uses deterministic whole-word keyword matching, not an
  LLM call.
- **Context:** Triage runs on every message; an LLM call per email is slow,
  costly and non-deterministic, and triage rules in CEM are well understood.
- **Consequences:** Triage is instant, free, fully explainable and testable
  offline. The trade-off is that novel phrasings may be miscategorized; the
  `user_corrections` memory log captures these for future tuning.

### ADR-003: Polling vs. push notifications for new emails
- **Decision:** The agent polls the inbox on each run rather than subscribing to
  push (IMAP IDLE / webhooks).
- **Context:** The agent is a command-line tool run on demand (or via cron),
  not a long-lived daemon; push infrastructure adds operational complexity.
- **Consequences:** Simple, stateless runs that fit a "morning digest" workflow.
  The trade-off is latency between an email arriving and being seen; a scheduled
  cron run mitigates this and is noted as a future extension.

### ADR-004: Persistent JSON file vs. database for memory
- **Decision:** Memory is a single human-readable `memory.json` file.
- **Context:** The data set is small (sender profiles, recent history) and the
  project values inspectability during demos over query performance.
- **Consequences:** Zero setup, easy to read/edit/reset by hand, trivially
  gitignored. The trade-off is no concurrent access and no rich queries; a
  vector database is listed as a future extension.

## Section 5 — Error Handling

- **LLM API times out / errors:** `_call_claude` catches all exceptions and
  returns a readable `[ERROR] ...` string. The pipeline keeps running; a draft
  simply shows the error text and the operator declines to send.
- **IMAP connection fails:** Connection and auth errors are caught; the
  connection is always closed in a `finally` block. If credentials are missing
  the reader transparently falls back to test data.
- **SMTP authentication fails:** `send_email` catches `SMTPAuthenticationError`
  separately, prints a clear message and returns `False`; nothing is logged as
  sent.
- **Email matches multiple triage categories:** Categories are checked in
  severity order (URGENT → ACTION → FYI → ARCHIVE); the highest matching
  severity wins, so an email can never be silently downgraded.
- **Rate limit hit during a run:** Guardrail 4 prunes the rolling 10-minute
  window and, if the cap is reached, prints an error and returns `False` without
  contacting SMTP.
- **Telegram API unreachable:** All Telegram calls are wrapped in try/except and
  return `False` on any network or config problem; the main pipeline never
  crashes because a side-channel alert failed.

## Section 6 — Security and Privacy

- **The `.env` pattern:** Every credential is read with `os.getenv()` from a
  local `.env` file that is listed in `.gitignore`. No secret is ever hardcoded,
  so the repository can be shared without leaking credentials.
- **App passwords vs. regular passwords:** The agent uses provider-issued
  16-character **app passwords**, not the account's primary password. App
  passwords are scoped to a single application and can be revoked individually,
  limiting blast radius if one leaks.
- **What NOT to paste into LLMs:** Do not send client data, personally
  identifiable information (PII), or privileged legal correspondence to the
  cloud model. Use anonymized or fictional scenario data.
- **Data protection note:** Construction projects involve personal data of
  subcontractors and employees. Pasting real project emails into cloud-based
  LLMs without anonymization may have legal implications depending on
  jurisdiction. This agent is designed for use with anonymized or fictional
  scenario data. Production deployment requires enterprise API agreements.

## Section 7 — Future Extensions

- **Multi-channel expansion:** Add WhatsApp and Slack alongside Telegram.
- **Vector database:** Semantic search over historical emails for context.
- **Scheduled runs:** A cron job to deliver the digest every morning
  automatically.
- **Attachment summarizer:** Parse and summarize PDFs and drawing sheets.
- **RFI log tracker:** A status dashboard tracking open/closed RFIs and overdue
  responses.
- **Platform integration:** Connect to construction management platforms
  (e.g., Procore, Autodesk Construction Cloud) for two-way sync.
