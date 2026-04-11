# CEM501: Communication Skills for CEM
## Week 6: Reports & LLM Summarization (Strand B)
**Spring 2026 | Dr. Eyuphan Koc | Bogazici University**

---

### Learning Objectives

By the end of this lecture, you will be able to:

- Explain why construction reports are **legal documents**, not paperwork
- Write a structured daily construction report from raw field notes
- Understand how LLMs tokenize, read, and summarize text
- Design a digest pipeline using Claude Code that summarizes project communications

---

## Part I: Construction Reports — More Than Paperwork

---

### The Golden Rule of Construction Law

> **"If it was not documented, it did not happen."**

This is not a figure of speech — it is a legal reality.

- Daily reports, inspection logs, and progress records are **primary evidence** in construction claims
- Writing a good report is **risk management**, not busywork

---

### 1.1 The Report Ecosystem on a Construction Project

**The scale of information on a real project:**

- A single hospital project (2020–2022) accumulated **6,000+ files** across shared workspaces and **3,000+ unique email threads** in two years
- Industry surveys consistently report that construction professionals spend a significant portion of each workday on email and information retrieval

*Source: [CooperLink: Construction Email Management](https://www.cooperlink.io/post/construction-project-partners-how-to-efficiently-manage-emails-and-collaborate-finally) (Joseph Bracops Hospital Project data)*

---

### Types of Reports You Will Encounter

| Report Type | Frequency | Primary Audience | Purpose |
|-------------|-----------|-----------------|---------|
| **Daily Report** | Every workday | PM, Owner, Legal record | Weather, labor, equipment, work performed, issues |
| **Weekly Progress** | Weekly | Owner, Lender | % complete, schedule status, cost status |
| **Monthly Pay Application** | Monthly | Owner, Accounting | Earned value, invoicing |
| **Incident / Safety** | As needed | Safety officer, OSHA | Accidents, near-misses, corrective actions |
| **Inspection Report** | As needed | QA/QC, Architect | Compliance with specs and drawings |
| **Punch List** | Near completion | Subcontractors, Owner | Outstanding deficiencies to close out |
| **Change Order Log** | Ongoing | PM, Owner, Contractor | Scope changes, cost and time impacts |

**Today's focus → the Daily Report**

---

### 1.2 Daily Reports as Legal Evidence

A daily report written at 5 PM today can become the decisive evidence in a **$60 million dispute** three years from now.

**From the Arcadis 2025 Global Construction Disputes Report** (15th edition):

- Average U.S. construction dispute value jumped **~40% in 2024** — from $43M to over **$60M**
- Average resolution time: **12.5 months**
- Leading cause (3rd consecutive year): **errors and omissions in contract documents**

*Source: [Arcadis 2025 Global Construction Disputes Report (PDF)](https://media.arcadis.com/-/media/project/arcadiscom/com/expertise/global/contract-solutions/2025/2025-15th-annual-construction-disputes-report-final-19jun25.pdf)*

---

### Why Daily Reports Are Admissible in Court

Daily reports qualify as **business records** — an exception to the hearsay rule — but **only if** they meet these four conditions:

| # | Condition | What It Means |
|---|-----------|--------------|
| 1 | **Created by someone present** | The author witnessed the events described |
| 2 | **Prepared contemporaneously** | Written at or shortly after the events — not days later |
| 3 | **Part of regular business practice** | Not created specifically for litigation |
| 4 | **Factual and objective** | Not editorialized opinions |

**Fail any one of these → the report may be inadmissible.**

*Source: [Miller Nash LLP: Rules of Evidence in Construction Claims](https://www.millernash.com/industry-news/what-do-the-rules-of-evidence-have-to-do-with-documenting-a-construction-claim-everything)*

---

### A Real Case: The Baltimore Tunnel Dispute

During construction of the **Baltimore Metro subway tunnels** (MTA Contract NW-03-02, 1976), the general tunnel superintendent at **Fruin-Colnon Corporation** adopted a simple habit:

- He dictated daily observations into a **hand-held cassette recorder** during his 75-minute commute between Baltimore and Washington, D.C. — recording on the drive home and completing notes on the return trip the next morning
- The cassette was transcribed by a project secretary each day
- These **shift-by-shift records** covered all three daily shifts

**The result:** During a **three-week hearing** before the Maryland Board of Contract Appeals, these recordings proved **"invaluable"** — the contractor secured additional compensation and contract time for differing site conditions.

**The lesson:** It was not brilliance or eloquence that won the case. It was the **discipline of same-day documentation**.

*Source: Bartholomew, S.H. (2002). Construction Contracting: Business and Legal Principles, Ch. 21. [Available via Virginia Tech Libraries](https://pressbooks.lib.vt.edu/constructioncontracting/chapter/documentation-and-records/). MSBCA case records: Fruin-Colnon Corp. and Horn Construction Co., Inc., Nos. 1001–1025 (1979–1987).*

---

### 1.3 Good vs. Poor Documentation — The Stakes

**Scenario A — Good documentation saves $2.4M:**
- GC encounters unexpected rock during hospital foundation excavation
- Superintendent's daily reports record: exact date, hours on rock removal, equipment mobilized, crews affected
- **47 consecutive daily reports** with consistent entries
- Arbitrator awards **$2.4 million**

**Scenario B — Poor documentation loses $1.8M:**
- Subcontractor claims 62 days of owner-caused delay
- Daily reports filed only **3–4 days per week**
- Vague entries like *"waited for materials"* — no dates, quantities, or responsible parties
- **Claim denied**

> **Takeaway:** The party with better documentation almost always prevails. You cannot retroactively create good documentation.

*Source: [ConsensusDocs: Proactively Addressing Construction Claims](https://www.consensusdocs.org/news/proactively-addressing-potential-construction-claims/)*

---

## Part II: What Makes a Good Daily Report

---

### 2.1 The Seven Required Elements

Omitting any one creates a gap that opposing counsel **will** exploit.

| # | Element | Why It Matters |
|---|---------|---------------|
| 1 | **Date, project name, report number** | Establishes the chain of documentation |
| 2 | **Weather** (morning + afternoon) | Supports or refutes weather delay claims |
| 3 | **Manpower** (by trade, sub, count) | Proves staffing levels and contractor performance |
| 4 | **Equipment** (status: active, idle, standby) | Documents idle equipment costs for claims |
| 5 | **Work performed** (locations, quantities, %) | The factual core of the report |
| 6 | **Delays, issues, RFI status** | Real-time record of impediments |
| 7 | **Safety and visitors** | OSHA compliance and witness documentation |

> **Tip:** Log weather at **multiple times** throughout the day. An afternoon thunderstorm that halted concrete pouring will not appear in a morning-only weather entry.

---

### 2.2 Example: A Well-Written Daily Report

```
==================================================
DAILY CONSTRUCTION REPORT
Project: Bogazici Research Center — Phase 2
Date: March 12, 2026       Report #: DCR-047
Prepared by: A. Yilmaz, Assistant PM
Weather:  Morning 8°C overcast, light wind
          Afternoon 12°C partly cloudy
          Impact: None
==================================================

MANPOWER (Total on site: 30)
  Ironworkers    (Sub: Demir AS)     — 12
  Concrete       (Sub: Beton Ltd)    —  8
  Electricians   (Sub: Elektrik Co)  —  4
  General labor                      —  6

EQUIPMENT ON SITE
  Tower crane (TC-01)   — operational, full day
  Concrete pump         — active 09:00–14:00
  Backhoe               — IDLE (awaiting excavation permit)

WORK PERFORMED
  - Completed rebar placement, Level 3 slab,
    Grid A1–A5 (100%)
  - Poured concrete, Level 2 columns, Grid B3–B7
    (12 m3, mix C30/37)
  - Continued electrical rough-in, Level 1 east wing
    (~60% complete)
  - Formwork stripping, Level 2 slab, Grid A1–A3

DELAYS / ISSUES
  - Curtain wall anchor submittal: pending architect
    review (RFI-032, submitted Feb 28 — 12 days
    outstanding)
  - Backhoe idle: excavation permit for utility trench
    delayed by municipality — 3rd day idle
  - Concrete delivery was 45 min late (arrived 09:45
    vs. scheduled 09:00); no schedule impact

SAFETY
  - Toolbox talk: working at heights (28 attendees)
  - No incidents or near-misses

VISITORS
  - S. Ozkan (Owner's rep) — site walk 10:00–11:30
  - Structural inspector — L2 column rebar check,
    APPROVED

PHOTOS ATTACHED: 4 (rebar placement L3, concrete
pour L2, idle backhoe, formwork stripping)
==================================================
```

---

### 2.3 What Makes This Report Effective

Look at the qualities that give this report **evidentiary value**:

| Quality | Example from Report | Why It Matters |
|---------|-------------------|---------------|
| **Specific locations** | Grid A1–A5, Level 3 | Not "worked on the building" |
| **Quantities** | 12 m3 of C30/37 | Verifiable progress for payment |
| **Named subcontractors** | Demir AS, Beton Ltd | Clear accountability |
| **Status flags** | 100%, ~60%, IDLE, APPROVED | At-a-glance progress |
| **Time references** | "09:45 vs. scheduled 09:00" | Precision for delay analysis |
| **Days outstanding** | "12 days outstanding" on RFI-032 | Builds the delay narrative |
| **Photo references** | 4 photos tied to entries | Visual evidence |

---

### 2.4 Common Mistakes in Daily Reports

| Mistake | Bad Example | Why It Hurts |
|---------|------------|-------------|
| Vague work descriptions | "Worked on concrete" | Cannot prove what was done |
| Missing quantities | "Poured columns" | Cannot verify progress or payment |
| No location references | "Installed rebar" | Where? Which level? Which grid? |
| Skipping "no incident" entries | Leaving safety blank | Looks like safety was not monitored |
| Editorializing | "Owner is being unreasonable about the RFI" | Undermines objectivity as business record |
| Inconsistent filing | Reports only 3–4 days/week | Gaps suggest incomplete monitoring |

> **Tip:** Write **"No incidents or near-misses"** rather than leaving the safety section empty. An empty field looks like negligence. A "none" entry proves you checked.

---

## Part III: LLM Summarization — How AI Reads and Condenses

Your project generates daily reports, emails, RFIs, meeting minutes, and inspection logs — potentially hundreds of pages per week.

**No human can read all of it carefully.** This is where LLM summarization becomes practical.

But first — you need to understand what happens under the hood.

---

### 3.1 Tokens — How the AI Reads

An LLM does not read words the way you do. It reads **tokens** — fragments of text, typically smaller than words.

> **Analogy:** Think of tokens like syllables. You read "unbelievable" as one word. The AI breaks it into pieces: `un` + `believ` + `able`. Each piece is a token. Common short words like "the" are single tokens. Longer or rarer words get split.

**The technical process:**
- Called **tokenization** — typically using Byte-Pair Encoding (BPE)
- Text is split into fragments, each assigned a numerical ID
- The model sees a **sequence of numbers**, not letters or words

*Source: [Sean Trott: Tokenization in LLMs, Explained](https://seantrott.substack.com/p/tokenization-in-large-language-models)*

---

### Token Math — Rules of Thumb

| Input | Approximate Tokens |
|-------|-------------------|
| 1,000 words | ~1,300–1,500 tokens |
| A typical daily report (300–400 words) | ~400–600 tokens |
| A one-page email | ~200–400 tokens |
| 30 emails from one day | ~6,000–12,000 tokens |

**Why this matters:** LLMs have a hard limit on how many tokens they can process at once.

---

### 3.2 Context Windows — The AI's Working Memory

The **context window** = total tokens an LLM can hold at once.

Your instruction + the input text + the generated output must **all fit** inside it.

**Current context window sizes (April 2026):**

| Model | Context Window | Practical Equivalent |
|-------|---------------|---------------------|
| **Claude Opus 4.6 / Sonnet 4.6** | 200K tokens (1M available) | up to ~650K words |
| **GPT-4.1** | 1,000,000 tokens | ~650K words |
| **Gemini 2.5 Pro** | 1,000,000 tokens | ~650K words |

*Sources: [AIMultiple: AI Context Windows (2026)](https://aimultiple.com/ai-context-window); [Elvex: Context Length Comparison (2026)](https://www.elvex.com/blog/context-length-comparison-ai-models-2026)*

---

### The Catch: Bigger Is Not Always Better

These numbers sound huge, but there is a critical caveat:

**Models degrade before hitting their limit.**

- Effective capacity is typically **60–70% of the advertised maximum**
- Models may "forget" information in the middle of a long input — a phenomenon called **"lost in the middle"**
- A model claiming 1M tokens may become unreliable well before that

> **Analogy:** A context window is like your desk. A bigger desk lets you spread out more documents, but you still focus on what is right in front of you. Stack 500 pages on a large desk — you will still lose track of what is on page 247.

---

### 3.3 What Happens When You Say "Summarize This"

Summarization is **lossy compression** — the model decides what matters and generates a shorter version.

**What gets kept depends entirely on your prompt:**

| Prompt | Result Quality |
|--------|---------------|
| "Summarize this" | Generic, unfocused — the model **guesses** what matters |
| "Summarize this for a project manager in 3 bullets" | Better — **audience and format** specified |
| "Extract all safety incidents, delays, and outstanding RFIs" | Best — **targeted extraction**, not open-ended summary |

> **Takeaway:** "Summarize this" is the weakest possible prompt. It is like telling an intern "read this and tell me what's important" without explaining your role or priorities. Always specify **who** the summary is for and **what categories** to extract.

---

### 3.4 Chunking — When the Input Is Too Large

**Problem:** You need to summarize 200 daily reports (~100K tokens). Even with a large context window, accuracy degrades.

**Solution: Map-Reduce Summarization**

```
200 reports
   ├── Chunk 1 (reports 1–20)   → Summary A
   ├── Chunk 2 (reports 21–40)  → Summary B
   ├── ...
   └── Chunk 10 (reports 181–200) → Summary J
                                        ↓
                            Final combined summary
```

- Split into manageable groups → summarize each → combine summaries
- Trades one long, unreliable pass for **multiple short, reliable passes**
- For our digest pipeline, a morning's emails (10–30 messages) typically fit in one pass

---

### 3.5 Hallucination Risks in Summarization

LLMs can **hallucinate** — generate information that sounds plausible but is **factually wrong or absent from the source**.

This is the **#1 risk** when using AI for construction documentation.

---

### How Often Do LLMs Hallucinate?

The **Vectara Hallucination Leaderboard** (updated February 2026) evaluates how often LLMs fabricate facts when summarizing 7,700+ articles:

| Model | Hallucination Rate | Factual Consistency |
|-------|-------------------|-------------------|
| Gemini 2.5 Flash Lite | 3.3% | 96.7% |
| GPT-4.1 | 5.6% | 94.4% |
| Gemini 2.5 Pro | 7.0% | 93.0% |
| GPT-4o | 9.6% | 90.4% |
| Claude Haiku 4.5 | 9.8% | 90.2% |
| Claude Opus 4.5 | 10.9% | 89.1% |
| Claude Sonnet 4.5 | 12.0% | 88.0% |

Even the best models hallucinate **3–5% of the time** on summarization.

*Source: [Vectara Hallucination Leaderboard (GitHub)](https://github.com/vectara/hallucination-leaderboard)*

---

### What Does This Mean for Construction?

In medical text summarization, a 2025 study found:
- **1.47% hallucination rate** and **3.45% omission rate** in LLM-generated clinical notes

*Source: [npj Digital Medicine: Clinical Safety of LLM Summarization (2025)](https://www.nature.com/articles/s41746-025-01670-7)*

**Construction example:**

If you summarize 30 emails and the model fabricates one detail — say, it states an RFI was **"approved"** when the original said **"under review"** — a crew could proceed with unapproved work.

> **Takeaway:** LLM summaries are **drafts, not records**. Always treat AI-generated summaries as a first pass requiring human verification. Never file an AI summary as an official project document without review.

---

## Part IV: Building a Digest Pipeline

---

### 4.1 What the Digest Generator Does

Your `digest.py` takes emails from `reader.py` (Week 5) and produces a **one-page morning digest** a PM can read in 2 minutes.

**Pipeline:**

```
reader.py (fetch emails)
    → group by triage category
    → summarize URGENT/ACTION via LLM
    → list FYI subjects
    → count ARCHIVE
    → format and print digest
```

---

### 4.2 Building It Step by Step with Claude Code

Open your terminal and launch Claude Code:
```
cd ~/cem501-agent/project && claude
```

---

**Step 1 — Describe the pipeline:**

```
"Create digest.py that takes a list of email dictionaries
with keys: subject, sender, body, and triage_category.
Group emails by category. For URGENT and ACTION emails,
include a one-line summary of each. For FYI, list subject
lines only. Skip ARCHIVE emails (just show count).
Output a formatted text digest with a header showing
the date and time."
```

---

**Step 2 — Review the code:**

```
"Explain the group_by_category function line by line"
```

---

**Step 3 — Test with hardcoded data:**

```
"Add a test function with 6 sample construction emails
(2 URGENT, 2 ACTION, 1 FYI, 1 ARCHIVE) and run the
digest on them"
```

---

**Step 4 — Add LLM summarization:**

```
"Add a summarize_email(body) function that uses the
Anthropic API to generate a one-sentence summary.
Use it for URGENT and ACTION emails only."
```

---

**Step 5 — Connect to your reader:**

```
"Import fetch_recent and triage_email from reader.py
so the digest pulls from my actual inbox"
```

---

### 4.3 Example Digest Output

```
=== PROJECT MORNING DIGEST ===
Generated: March 13, 2026 at 07:15
Covering: 10 emails from last 12 hours
============================================

--- URGENT (1) ---
[1] From: OSHA Inspector
    Subject: Fall protection deficiency — immediate
             correction required
    Summary: Inspector found missing guardrails on
             Level 4 east. Correction required before
             work resumes above Level 3.

--- ACTION (3) ---
[2] From: Project Architect
    Subject: RFI-047 Response: Rebar spacing at Pier 3
    Summary: Architect approved Option B (150mm
             spacing). Proceed with installation.

[3] From: Concrete Supplier
    Subject: Updated delivery schedule for Week 12
    Summary: Thursday pour moved to Friday due to
             plant maintenance. Adjust formwork crew.

[4] From: Owner's Rep
    Subject: Schedule review meeting — agenda needed
    Summary: Requesting agenda items by EOD Wednesday
             for Friday OAC meeting.

--- FYI (4) ---
  - Weekly safety stats — February summary
  - Subcontractor insurance cert renewal (Demir AS)
  - Project photo album updated
  - Industry newsletter: New OSHA silica dust rules

--- ARCHIVE (2 emails skipped) ---
============================================
=== END DIGEST ===
```

> **Reminder:** The digest is a **triage tool** — it tells you which 2–3 emails need attention right now. URGENT and ACTION summaries are AI-generated drafts. Always click through to the original email before taking action.

---

## Tool Demo: Claude Code Session (Live, ~10 min)

The instructor will build the digest generator live, demonstrating:

1. Describing what you want in **plain language**
2. **Reviewing** generated code before accepting
3. Testing **incrementally**
4. Iterating with follow-up instructions ("add error handling," "make the output cleaner")

**Watch for:** The instructor reviews AI output before accepting — the same principle as reviewing an AI summary before filing it as a project record.

---

## Assignments

See **[Week06_Assignment.md](Week06_Assignment.md)** for homework and milestone details.

---

### Further Reading

**Construction Documentation:**
- Bartholomew, S.H. (2002). *Construction Contracting: Business and Legal Principles.* Ch. 21: Documentation and Records. [Available via Virginia Tech Libraries](https://pressbooks.lib.vt.edu/constructioncontracting/chapter/documentation-and-records/)
- [Arcadis (2025). Global Construction Disputes Report, 15th Edition (PDF)](https://media.arcadis.com/-/media/project/arcadiscom/com/expertise/global/contract-solutions/2025/2025-15th-annual-construction-disputes-report-final-19jun25.pdf)
- [Miller Nash LLP: Rules of Evidence in Construction Claims](https://www.millernash.com/industry-news/what-do-the-rules-of-evidence-have-to-do-with-documenting-a-construction-claim-everything)
- [ConsensusDocs: Proactively Addressing Construction Claims](https://www.consensusdocs.org/news/proactively-addressing-potential-construction-claims/)

**LLM Summarization and Hallucination:**
- [Vectara Hallucination Leaderboard (GitHub)](https://github.com/vectara/hallucination-leaderboard)
- [npj Digital Medicine: Clinical Safety of LLM Summarization (2025)](https://www.nature.com/articles/s41746-025-01670-7)
- [Anthropic Prompt Engineering Guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview)
- [Sean Trott: Tokenization in LLMs, Explained](https://seantrott.substack.com/p/tokenization-in-large-language-models)

**Information Overload in Construction:**
- [CooperLink: Construction Email Management](https://www.cooperlink.io/post/construction-project-partners-how-to-efficiently-manage-emails-and-collaborate-finally)
- [RICS: Information Overload — Creating Clarity as a PM](https://ww3.rics.org/uk/en/journals/construction-journal/information-overload-creating-clarity-as-a-project-manager.html)
- [ResearchGate: Project Information Overload & PMIS in Construction (2023)](https://www.researchgate.net/publication/372546196_Project_Information_Overload_Role_of_PMIS_in_Managerial_Decision-Making_A_Study_in_Construction_Companies_of_Oman)

---
**Dr. Eyuphan Koc** | eyuphan.koc@bogazici.edu.tr
