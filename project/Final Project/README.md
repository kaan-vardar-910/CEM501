# CEM501 AI Communication Agent

A personal AI communication assistant for a construction project manager. It
reads and triages an email inbox, produces a daily morning digest, drafts
professional CEM documents (RFIs, submittal transmittals, weather delay
notices) and reply emails with the Anthropic Claude API, and sends approved
replies over SMTP — but only after mandatory human confirmation. It remembers
past interactions in a persistent JSON store and pushes urgent alerts to
Telegram. The project demonstrates all three course strands: verbal (demo
script + reflection), written (reader, triage, templates, digest) and agentic
(the full guarded pipeline with memory and multi-channel alerts).

## Prerequisites

- Python 3.10+
- A Gmail (or other IMAP/SMTP provider) **app password** for reading/sending
- An Anthropic API key (for document and summary generation)
- Optional: a Telegram bot token + chat id for urgent alerts

## Setup

1. Clone the repo.
2. Install dependencies:

```bash
pip install anthropic python-dotenv python-docx pypdf requests reportlab docx2pdf
```

> For best PDF quality, install **LibreOffice** (free):
> Windows: https://www.libreoffice.org/download/download/
> The app automatically detects and uses it if available, and falls back to
> `docx2pdf` (needs Microsoft Word) and then `reportlab` if neither is present.

3. Copy the environment template and fill in your real values:

```bash
cp .env.example .env
```

4. Test the reader with no credentials needed:

```bash
python project/reader.py
```

## How to run each module

| Command | What it does |
| --- | --- |
| `python project/reader.py` | Prints 3 test emails with color-coded triage (no credentials). |
| `python project/templates.py` | Generates a sample RFI (requires `ANTHROPIC_API_KEY`). |
| `python project/digest.py` | Prints the morning digest from 6 test emails (no credentials). |
| `python project/memory.py` | Runs the memory module self-test. |
| `python project/telegram_notifier.py` | Sends a test alert (requires Telegram config). |
| `python project/agent.py` | Full pipeline against your real inbox. |
| `python project/agent.py --dry-run` | Full pipeline, prints drafts, never sends. |
| `python project/agent.py --digest-only` | Fetch + digest only, no drafting. |
| `python project/agent.py --test` | Use hardcoded test emails, no inbox. |
| `python project/agent.py --test --dry-run` | Safe full demo, no credentials, no sends. |
| `python project/demo.py` | Guided 7-step narrated demonstration. |

## Daily Report Module

Daily Report creates structured daily construction reports stored with both
Word and PDF exports per report.

- **Report naming:** `DR-001_2026-06-07` (sequential number + date)
- **Storage:** `project/reports/[report_id]/` — each folder holds `report.json`,
  the generated `.docx`/`.pdf`, and a `source_files/` subfolder.

Features:

- Auto weather from the site location (set `SITE_LAT` and `SITE_LNG` in `.env`).
- Upload notes, emails, PDFs and spreadsheets
  (`.txt .pdf .docx .eml .xlsx .csv`) — the AI extracts only the fields that are
  explicitly present in the text.
- Edit, regenerate, finalize, and send reports with the existing send guardrails.
- Browse all past reports with full edit capability.

Open the dashboard, go to **Create Document → Daily Report**. The two views
(**+ New Report** / **📋 Past Reports**) handle creation and browsing.

Install (includes the report dependencies):

```bash
pip install anthropic python-dotenv python-docx pypdf openpyxl requests reportlab
```

Self-tests:

```bash
python project/daily_report_store.py       # storage/index round-trip
python project/daily_report_generator.py   # LLM text generation (needs API key)
python project/weather.py                  # weather fetch sample
```

## Milestone checklist

- [x] **M0** — First LLM calls documented (`project/logs/m0_first_calls.md`)
- [x] **M1** — CEM document generators (`project/templates.py`)
- [x] **M2** — IMAP reader + triage (`project/reader.py`)
- [x] **M3** — Daily digest with LLM summaries (`project/digest.py`)
- [x] **M4** — Full pipeline orchestrator with 4 guardrails (`project/agent.py`)
- [x] **M5** — Architecture documentation (`ARCHITECTURE.md`)
- [x] **BONUS** — Persistent memory (`project/memory.py`)
- [x] **BONUS** — Telegram multi-channel alerts (`project/telegram_notifier.py`)
- [x] **BONUS** — Guided demo script (`project/demo.py`)
- [x] **BONUS** — Academic reflection (`assignments/reflection.md`)
- [x] **Templates** — RFI, submittal, daily report (`project/templates/`)

## Safety notes

- `.env`, `sent_log.txt`, `memory.json` and session logs are gitignored.
- Use anonymized or fictional scenario data only — never paste real client PII
  or privileged correspondence into the LLM. See `ARCHITECTURE.md` Section 6.

## Student

- **Name:** [Your Name]
- **Student ID:** [Your ID]
