# M0 — First LLM Calls

Three sample Claude calls captured from the terminal during early testing, using
generic CEM scenarios (no real project names or contract numbers). Output is
reproduced as printed.

---

## Prompt 1 — Draft an RFI

**Input**

> Draft an RFI for a conflict between a structural drawing and a specification
> section regarding rebar spacing at a pile cap.

**Output**

```
RFI Number: [to be assigned]
Date: 2026-06-06
Project: Commercial Office Building
To: Engineer of Record
Subject: Drawing S-204 vs. Section 03 21 00 — Rebar spacing conflict at pile cap

Question: At the pile cap (Drawing S-204, Detail 3), the structural drawing
shows #8 bars at 8 in. on center, while Specification Section 03 21 00,
Paragraph 2.3, requires a minimum clear spacing that the 8 in. dimension does
not satisfy for the specified bar size and cover. Which requirement governs the
reinforcing layout at this location?

Suggested Resolution: Contractor proposes to adopt the specification's minimum
clear-spacing requirement and increase the on-center dimension accordingly to
maintain code-required cover, pending Engineer of Record confirmation.

Impact if Unanswered: Pile cap reinforcing fabrication and placement cannot be
released. A response is requested by 2026-06-11 to avoid delaying the pile cap
pour scheduled for 2026-06-15.

Attachments: Drawing S-204 (Detail 3); Specification Section 03 21 00 excerpt.
```

---

## Prompt 2 — Professional schedule request email

**Input**

> Write a professional email requesting an updated CPM schedule from the general
> contractor, with a response deadline of 5 business days.

**Output**

```
Subject: Request for Updated CPM Schedule — Response Required by [date + 5 business days]

Dear [General Contractor PM],

Please provide an updated CPM schedule reflecting current progress and any
revised activity sequencing no later than five business days from today.

The most recent baseline no longer matches observed field progress, and an
updated network is required to validate the critical path, confirm milestone
dates, and support the upcoming owner-architect-contractor meeting. Please
include the schedule narrative and identify any changes to critical-path
activities.

Kindly confirm receipt of this request and the expected delivery date. If the
five-business-day window presents any difficulty, advise immediately so we can
coordinate.

Best regards,
[Project Manager]
[Project / Company]
```

---

## Prompt 3 — Submittal transmittal elements

**Input**

> List the key elements a submittal transmittal letter must contain under a
> standard construction contract.

**Output**

```
1. Header / identification — project name, submittal number, revision, date,
   and the responsible spec section number.
2. Description of enclosed items — each item listed with quantity and
   manufacturer/supplier.
3. Contractor compliance certification — a signed statement that the submittal
   has been reviewed and conforms to the contract documents.
4. Action requested — the specific review action sought (approve, approve as
   noted, revise and resubmit) and the requested return date.
5. Distribution list — all parties receiving copies (architect, engineer,
   owner, file).
6. References and attachments — exact spec section, related drawings, and any
   certifications or test data enclosed.
```

---

## Reflection (5 sentences)

The model did several things well: every response was cleanly structured,
adopted an appropriately formal and unemotional professional tone, and matched
the requested output formatting almost exactly. However, it also hallucinated
specifics it was never given — most notably an invented paragraph reference
("Paragraph 2.3") in the RFI and a concrete pour date that I had not supplied —
which is exactly the kind of confident fabrication that would be dangerous in a
contractual document. The prompts improved noticeably between the first and third
attempts: once I added explicit output-format scaffolding and the one-question
rule, the RFI stopped drifting into multiple questions and the submittal list
covered all six required elements without prompting twice. The clear lesson is
that an LLM is an excellent first-drafter but a poor source of facts: it will
invent clause numbers and dates to fill gaps unless a human verifies them. For
professional CEM practice this confirms the project's core design principle —
keep a human in the loop to check every reference and date before any document
leaves the office.
