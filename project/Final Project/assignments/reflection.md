# Reflection: Building a Communication Agent for Construction Management

Building the CEM501 AI Communication Agent forced me to turn the communication
principles we discussed in lectures into code that actually has to behave. It is
one thing to be told that an email should be front-loaded; it is another to
write a system prompt that *guarantees* the request lands in the first sentence.
This essay reflects on what I learned by connecting the technical choices to the
course's written-communication theory.

## Strand B: Written communication in the code

The clearest place where the Week 2–3 material shows up is the `draft_email_reply()`
function. Its system prompt literally encodes the five-element email framework
and the front-loaded structure: "request in first sentence, supporting facts in
second paragraph, clear CTA with deadline, professional sign-off." I did not want
the model to "decide" how to organize a message, because the lecture's whole
point was that PMs are busy and bury-the-lede emails get ignored. The RFI
generator is even more prescriptive. The `draft_rfi()` system prompt enforces the
one-question-per-RFI rule we learned in Week 3 — "exactly ONE question per RFI" —
along with mandatory drawing and specification references and a dated schedule
impact. When I tested it, the contract-precise language requirement (no emotional
wording, explicit contract section references) carried straight into the delay
notice generator, which mirrors how the FMI/PlanGrid (2018) data framed rework
and disputes as largely a communication-quality problem. Writing these prompts
made me realize that good professional writing rules are, in effect, a
specification — and an LLM is much more useful when you hand it that spec rather
than hoping it infers it.

## LLM as a tool, not a replacement

The Noy and Zhang (2023) MIT study cited in Week 2 stuck with me: AI made writers
roughly 40% faster, but a striking share of participants simply pasted the output
without reviewing it. That finding is exactly the failure mode my agent is
designed to resist. The confirmation guardrail in `send_email()` prints the full
draft and refuses to proceed unless the user types `y`; there is no flag that
bypasses it. The design treats the model as a fast first-drafter, not an
author of record — the reminder line in every digest even says "AI summaries are
drafts, not official records." I also saw concrete hallucination while testing:
when I asked for an RFI, the model was happy to invent a plausible-looking RFI
number and a specific response date that I had never supplied. Those inventions
look authoritative, which is precisely why an unreviewed copy-paste would be
dangerous in a contractual document. The experience matched the McKinsey (2017)
observation that productivity tools only pay off when paired with discipline in
how they are used.

## The human-in-the-loop principle

Week 8 made the point that misdirected email is one of the most frequently
reported categories of data breach, and building the sender felt like the moment
that statistic became real. The send button is the most dangerous button in any
agent because it is irreversible and instantaneous: a single wrong recipient or a
leftover `[PLACEHOLDER]` cannot be un-sent. That is why I layered four guardrails
around it — confirmation, recipient validation (flagging unknown contacts and
typo'd domains like "gmial"), content checks for placeholders and empty subjects,
and rate limiting. For autonomous AI in construction specifically, this matters
because the recipients are owners, inspectors, and engineers of record whose
trust and the project's contractual position both ride on every message. The PMI
*Pulse of the Profession* research repeatedly ties project failure to poor
communication, and an agent that sent confidently-wrong emails at machine speed
would amplify exactly that risk rather than reduce it.

## What I learned

What surprised me most was how much of the engineering effort went into *not*
acting — the guardrails, the dry-run mode, the graceful fallbacks — rather than
into generation. I had assumed the hard part would be prompting; instead the hard
part was deciding where the human had to stay in control. If I did it again, I
would build the triage corrections loop earlier, because I only appreciated late
how valuable the `user_corrections` log is as a record of where my keyword rules
disagree with human judgment. The communication principle that most shaped my
system prompts was front-loading: once I committed to "the request goes first,"
every prompt got shorter, clearer, and easier to verify. More than any single
feature, that principle changed how I wrote the instructions to the model itself.

In the end, the project convinced me that the future of AI agents in CEM practice
is not autonomous send-and-forget messaging but disciplined human-in-the-loop
assistance that makes a project manager faster without ever taking away their
accountability.

### References
- FMI / PlanGrid (2018). *Construction Disconnected.*
- PMI. *Pulse of the Profession.*
- Noy, S., & Zhang, W. (2023). *Experimental evidence on the productivity effects
  of generative artificial intelligence.* MIT.
- McKinsey & Company (2017). *Reinventing Construction: A Route to Higher
  Productivity.*
