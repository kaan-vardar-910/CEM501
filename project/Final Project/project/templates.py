"""CEM document generators backed by the Anthropic Claude API (Milestone M1).

Each function builds a carefully constrained system prompt that encodes the
construction-communication rules taught in the course (one question per RFI,
CSI submittal format, contractually precise delay notices, front-loaded
emails) and returns the model's text. All functions degrade gracefully when
the API key is missing or the API call fails, so they never crash a caller.
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Some Windows/corporate networks intercept TLS, which makes Python's bundled
# CA store unable to verify api.anthropic.com (CERTIFICATE_VERIFY_FAILED).
# truststore makes Python trust the OS certificate store, matching the browser.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

# Model and token budget. The original spec model (claude-sonnet-4-20250514)
# reaches end-of-life on 2026-06-15, so we use its current successor.
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1000


def _call_claude(
    system_prompt: str, user_prompt: str, max_tokens: int = MAX_TOKENS
) -> str:
    """Send a single-turn request to Claude and return the text response.

    Centralises client construction, key loading and error handling so each
    document function stays focused on its prompt. ``max_tokens`` can be raised
    for longer outputs (e.g. daily reports). Returns a readable error string
    (never raises) so callers can keep running.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "[ERROR] ANTHROPIC_API_KEY is not set. Add it to your .env file to "
            "generate live documents."
        )
    try:
        import anthropic
    except ImportError:
        return (
            "[ERROR] The 'anthropic' package is not installed. Run: "
            "pip install anthropic"
        )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Concatenate any text blocks the model returns.
        return "".join(
            block.text for block in response.content if hasattr(block, "text")
        ).strip()
    except Exception as error:  # noqa: BLE001 - surface any SDK/network error.
        return f"[ERROR] Claude API call failed: {error}"


def _append_signature(
    user_prompt: str, signature: str, sign_off: bool = False
) -> str:
    """Append an active-profile signature instruction to a user prompt.

    When ``sign_off`` is True the block is presented as an email sign-off;
    otherwise as a "Prepared by" attribution for formal documents. The model is
    told to use it verbatim so it does not invent placeholder names.
    """
    if not signature:
        return user_prompt
    if sign_off:
        label = (
            "End the email with exactly this sign-off block; do not invent a "
            "name, title, company, or placeholder:"
        )
    else:
        label = (
            "Attribute the document using exactly this 'Prepared by' block; do "
            "not invent names or placeholders:"
        )
    return f"{user_prompt}\n\n{label}\n{signature}"


def draft_rfi(
    project_name: str,
    drawing_ref: str,
    spec_ref: str,
    issue: str,
    suggested_resolution: str,
    affected_trade: str,
    activity_start_date: str,
    response_deadline: str,
    signature: str = "",
) -> str:
    """Draft a formal single-question RFI and return it as text.

    Enforces the Week 3 RFI best practices: exactly one question, formal
    technical language, explicit drawing and spec references, a suggested
    resolution and a dated schedule-impact statement.
    """
    system_prompt = (
        "You are a senior project engineer on a commercial construction "
        "project. Write a formal RFI following industry best practices. "
        "Rules: exactly ONE question per RFI, formal technical language, "
        "always reference drawing numbers and spec sections, include "
        "suggested resolution, state schedule impact with specific dates, "
        "keep body under 200 words.\n\n"
        "Use exactly this output format:\n"
        "RFI Number: [to be assigned]\n"
        "Date: [current date]\n"
        "Project: [project_name]\n"
        "To: Engineer of Record\n"
        "Subject: [drawing_ref] vs [spec_ref] — [brief description]\n"
        "Question: [single specific question]\n"
        "Suggested Resolution: [contractor interpretation]\n"
        "Impact if Unanswered: [schedule consequence + response deadline]\n"
        "Attachments: [list]"
    )
    user_prompt = (
        f"Project: {project_name}\n"
        f"Drawing reference: {drawing_ref}\n"
        f"Specification reference: {spec_ref}\n"
        f"Issue: {issue}\n"
        f"Suggested resolution: {suggested_resolution}\n"
        f"Affected trade: {affected_trade}\n"
        f"Affected activity start date: {activity_start_date}\n"
        f"Response deadline: {response_deadline}"
    )
    user_prompt = _append_signature(user_prompt, signature)
    result = _call_claude(system_prompt, user_prompt)
    print(result)
    return result


def draft_submittal_transmittal(
    project_name: str,
    submittal_no: str,
    revision: str,
    spec_section: str,
    description: str,
    supplier: str,
    copies: str,
    certs: str,
    action: str,
    notes: str,
    signature: str = "",
) -> str:
    """Draft a one-page CSI-format submittal transmittal and return it."""
    system_prompt = (
        "You are a project engineer preparing a formal submittal transmittal "
        "for a construction project. Use CSI format, include contractor "
        "compliance certification, keep to one page, list all enclosed items "
        "with quantities, reference exact spec section number.\n\n"
        "Structure the output as: Header -> Item list -> Contractor "
        "certification -> Action requested -> Distribution list."
    )
    user_prompt = (
        f"Project: {project_name}\n"
        f"Submittal number: {submittal_no}\n"
        f"Revision: {revision}\n"
        f"Spec section: {spec_section}\n"
        f"Description: {description}\n"
        f"Supplier/manufacturer: {supplier}\n"
        f"Copies enclosed: {copies}\n"
        f"Certifications enclosed: {certs}\n"
        f"Action requested: {action}\n"
        f"Notes: {notes}"
    )
    user_prompt = _append_signature(user_prompt, signature)
    result = _call_claude(system_prompt, user_prompt)
    print(result)
    return result


_CONTRACT_EXTRACT_SYSTEM = (
    "You read a construction contract and extract a few specific fields to "
    "pre-fill a delay notice. Return ONLY a minified JSON object with exactly "
    "these keys: project_name, contract_no, contract_section, parties. "
    "Rules:\n"
    "- project_name: the project/works title named in the contract.\n"
    "- contract_no: the contract / agreement number or reference.\n"
    "- contract_section: the clause number AND short title that governs "
    "delays / extension of time / force majeure (e.g. '8.4 Extension of "
    "Time'). Pick the single most relevant one.\n"
    "- parties: 'Employer/Owner vs Contractor' names if present, else ''.\n"
    "- If a value is not found in the text, use an empty string. Never invent "
    "values. Output JSON only, no prose, no code fences."
)


def extract_contract_fields(contract_text: str) -> dict:
    """Extract delay-notice fields from raw contract text via Claude.

    Returns a dict with keys project_name, contract_no, contract_section,
    parties. On any failure returns the same keys with empty strings so the
    caller can keep running.
    """
    import json
    import re

    blank = {
        "project_name": "",
        "contract_no": "",
        "contract_section": "",
        "parties": "",
    }
    text = (contract_text or "").strip()
    if not text:
        return blank
    # Cap input so we never blow the token budget on a long contract.
    if len(text) > 14000:
        text = text[:14000]
    raw = _call_claude(
        _CONTRACT_EXTRACT_SYSTEM,
        f"CONTRACT TEXT:\n{text}",
        max_tokens=600,
    )
    try:
        return {**blank, **json.loads(raw)}
    except Exception:  # noqa: BLE001 - try to salvage a JSON object substring.
        match = re.search(r"\{.*\}", raw or "", re.S)
        if match:
            try:
                return {**blank, **json.loads(match.group(0))}
            except Exception:  # noqa: BLE001
                pass
    return blank


def draft_delay_notice(
    project_name: str,
    contract_no: str,
    contract_section: str,
    start_date: str,
    end_date: str,
    affected_activities: list[str],
    days_requested: int,
    supporting_data: str,
    signature: str = "",
) -> str:
    """Draft a contractually precise weather delay notice and return it."""
    system_prompt = (
        "You are a project manager writing a formal weather delay notice. Be "
        "contractually precise. Required elements: contract section reference, "
        "specific date range, daily measurement data, affected activity IDs, "
        "days requested (compensable vs. non-compensable), CTA with deadline. "
        "Tone: professional, factual, no emotional language."
    )
    activities = ", ".join(affected_activities)
    user_prompt = (
        f"Project: {project_name}\n"
        f"Contract number: {contract_no}\n"
        f"Contract section governing delays: {contract_section}\n"
        f"Delay start date: {start_date}\n"
        f"Delay end date: {end_date}\n"
        f"Affected activity IDs: {activities}\n"
        f"Days requested: {days_requested}\n"
        f"Supporting daily measurement data: {supporting_data}"
    )
    user_prompt = _append_signature(user_prompt, signature)
    result = _call_claude(system_prompt, user_prompt)
    print(result)
    return result


def draft_email_reply(
    original_subject: str,
    original_body: str,
    reply_intent: str,
    project_context: str,
    signature: str = "",
) -> str:
    """Draft a front-loaded professional reply email and return it.

    Encodes the Week 2 five-element / front-loaded email structure: the request
    appears in the first sentence, facts follow, and a dated CTA closes it.
    """
    system_prompt = (
        "You are a professional CEM project manager. The user gives you the "
        "email they received plus a few words describing how they want to "
        "respond. Expand those few words into a complete, polished reply, "
        "staying faithful to the user's intent and facts and never inventing "
        "commitments, dates, or numbers they did not provide. Write with: a "
        "specific subject line including project name, front-loaded structure "
        "(main point in the first sentence), supporting facts, a clear CTA with "
        "deadline where relevant, and a professional sign-off. Never use "
        "emotional language. Include contract references where relevant. Keep "
        "under 200 words. Output only the email."
    )
    user_prompt = (
        f"Project context: {project_context}\n"
        f"Original subject: {original_subject}\n"
        f"Original email received:\n{original_body}\n\n"
        f"The user's short answer to expand into a professional reply:\n"
        f"{reply_intent}"
    )
    user_prompt = _append_signature(user_prompt, signature, sign_off=True)
    result = _call_claude(system_prompt, user_prompt)
    print(result)
    return result


def summarize_email(body: str, sentences: int = 1) -> str:
    """Return an action-focused summary of an email body.

    ``sentences`` controls the length: 1 for the compact digest line, 2 for the
    richer summary shown in the dashboard triage table.
    """
    if sentences <= 1:
        system_prompt = (
            "Summarize this construction project email in one sentence, "
            "focusing on the action required or key information. Be specific."
        )
    else:
        system_prompt = (
            f"Summarize this construction project email in exactly {sentences} "
            "sentences. First sentence: the key point or what the email is "
            "about. Second sentence: the action required or impact. Be "
            "specific and concise; no preamble. Summarize only the text "
            "provided; never ask for more content or note that it may be "
            "incomplete."
        )
    # Cap very long bodies (e.g. newsletters) to keep summary calls cheap while
    # still giving the model enough context to summarise accurately.
    result = _call_claude(system_prompt, body[:6000])
    return result


def summarize_with_action(body: str) -> dict:
    """Return both a one-sentence summary and a recommended next action.

    Produced in a single LLM call to keep digest generation cheap. Returns a
    dict ``{"summary": str, "action": str}``; on a parsing miss the whole
    response falls back into ``summary`` and ``action`` is left blank.
    """
    system_prompt = (
        "You are a CEM project manager's assistant. Read the construction "
        "email and reply in EXACTLY two lines, no preamble, no extra text:\n"
        "SUMMARY: <one sentence on the key point / what it is about>\n"
        "ACTION: <the recommended next action for the PM, as a very short "
        "imperative phrase of at most 6 words, e.g. 'Reply to architect by "
        "Friday' or 'Stop work, re-inspect guardrails'>\n"
        "Base everything only on the provided text; never invent dates, "
        "numbers or commitments, and never ask for more content."
    )
    raw = _call_claude(system_prompt, body[:6000])
    return _parse_summary_action(raw)


def _parse_summary_action(raw: str) -> dict:
    """Split a 'SUMMARY: ...\\nACTION: ...' reply into its two fields."""
    summary, action = "", ""
    for line in (raw or "").splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("SUMMARY:"):
            summary = stripped.split(":", 1)[1].strip()
        elif upper.startswith("ACTION:"):
            action = stripped.split(":", 1)[1].strip()
    if not summary:
        # Model ignored the format; use the whole reply as the summary.
        summary = (raw or "").strip()
    return {"summary": summary, "action": action}


if __name__ == "__main__":
    # Generates a sample RFI; requires ANTHROPIC_API_KEY in .env.
    print("Generating a sample RFI (requires ANTHROPIC_API_KEY)...\n")
    draft_rfi(
        project_name="Riverside Commercial Tower",
        drawing_ref="S-204",
        spec_ref="Section 03 21 00",
        issue=(
            "Rebar spacing shown on the structural drawing conflicts with the "
            "minimum clear spacing required by the specification at the pile cap."
        ),
        suggested_resolution=(
            "Adopt the larger spacing from the specification to maintain "
            "code-required concrete cover."
        ),
        affected_trade="Concrete / reinforcing steel",
        activity_start_date="2026-06-15",
        response_deadline="2026-06-11",
    )
