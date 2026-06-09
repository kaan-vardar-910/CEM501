"""LLM-backed field extraction and report-text generation for daily reports.

Two responsibilities:

* :func:`extract_fields_from_sources` reads the combined source files for a
  report and asks Claude to pull only the facts explicitly present into a set
  of structured daily-report fields.
* :func:`generate_report_text` turns the structured report fields into a
  polished, formatted daily report ready for Word/PDF export.

Both functions reuse :func:`templates._call_claude` for client construction,
key handling and TLS/cert fixes, and degrade gracefully on any error.
"""

from __future__ import annotations

import json

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from daily_report_store import get_source_texts
from templates import _call_claude

_EXTRACT_SYSTEM = (
    "You are a construction site data analyst. Extract information from the "
    "provided text (field notes, emails, reports) to fill a construction daily "
    "report. Output must be QUANTITATIVE and terse.\n\n"
    "Rules:\n"
    "- Extract ONLY information explicitly present in the text.\n"
    "- Do not invent or assume data not found in the text.\n"
    "- Prioritise NUMBERS: counts, quantities, units, durations, %, grid "
    "lines, times. Lead every entry with the figure.\n"
    "- Write in short data fragments, NOT sentences. No filler words, no "
    "adjectives, no narrative. Use telegraphic style.\n"
    "- For manpower: 'trade x count' pairs (e.g. 'Carpenters x6, Laborers "
    "x4'). Add a total if derivable.\n"
    "- For equipment: 'name x count (status)' (e.g. 'Excavator x2 (active), "
    "Crane x1 (idle)').\n"
    "- For work_performed: 'item — qty/unit @ location' fragments "
    "(e.g. 'Footings poured — 45 m3 @ grid A-C').\n"
    "- For delays_issues: 'issue — impact (duration/qty)'.\n"
    "- For safety: counts/incidents only (e.g. 'Toolbox talk x1; 0 "
    "incidents').\n"
    '- If a field has no relevant data, return "".\n'
    "- Each field max ~40 words. Separate items with semicolons or newlines. "
    "Never copy tables or rows verbatim.\n\n"
    "Return ONLY a valid JSON object with exactly these keys:\n"
    "  work_performed, manpower, equipment,\n"
    "  delays_issues, safety_observations, visitors\n"
    "No markdown, no preamble, no explanation."
)

# Cap the combined source text so a folder of large spreadsheets cannot blow
# past the model's context or cause a truncated (unparseable) JSON reply.
_MAX_SOURCE_CHARS = 14000

_GENERATE_SYSTEM = (
    "You are a construction site superintendent producing a formal daily "
    "construction report. The report must be QUANTITATIVE and SCANNABLE — a "
    "data sheet, not an essay.\n\n"
    "Hard rules:\n"
    "- NO narrative paragraphs, NO introductions, NO closing remarks, NO "
    "filler or adjectives. Facts and numbers only.\n"
    "- Use the 7 sections as headers: Header, Weather, Manpower, Equipment, "
    "Work Performed, Delays/Issues, Safety.\n"
    "- Under each section use short bullet points (one data point per "
    "bullet). Lead each bullet with the number/quantity and unit.\n"
    "- Manpower and Equipment: show counts and a TOTAL headcount/unit count "
    "where derivable.\n"
    "- Work Performed: 'task — quantity unit @ location' style. Always keep "
    "quantities, units, grid lines, times.\n"
    "- Each bullet max ~15 words. Omit any section with no data by writing "
    "'None reported.'\n"
    "- Do NOT invent data not provided. Past tense for completed work.\n"
    "Output the report directly with no preamble."
)

_EXTRACT_KEYS = (
    "work_performed",
    "manpower",
    "equipment",
    "delays_issues",
    "safety_observations",
    "visitors",
)


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` fences and surrounding noise from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Drop the first fence line and any trailing fence.
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    # Fall back to the outermost {...} if extra prose slipped through.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    elif start != -1:
        # Truncated reply with no closing brace — keep from the first brace on.
        cleaned = cleaned[start:]
    return cleaned


def _salvage_json(text: str) -> dict:
    """Best-effort parse of (possibly truncated) JSON into the expected keys."""
    cleaned = _strip_json_fences(text)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        pass
    # The reply was cut off mid-string. Recover whole key/value pairs with a
    # simple regex so partial extractions are not thrown away entirely.
    import re

    result: dict = {}
    pattern = re.compile(r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"')
    for key, value in pattern.findall(cleaned):
        if key in _EXTRACT_KEYS:
            result[key] = value.replace('\\n', '\n').replace('\\"', '"')
    return result


def extract_fields_from_sources(report_id: str) -> dict:
    """Extract structured daily-report fields from a report's source files.

    Returns a dict with the six extractable keys, or ``{}`` if there are no
    source files or the model output could not be parsed.
    """
    combined = get_source_texts(report_id)
    if not combined.strip():
        return {}
    if len(combined) > _MAX_SOURCE_CHARS:
        combined = combined[:_MAX_SOURCE_CHARS] + "\n\n[...truncated...]"

    user_prompt = f"Extract daily report fields from:\n\n{combined}"
    raw = _call_claude(_EXTRACT_SYSTEM, user_prompt, max_tokens=3000)
    if raw.startswith("[ERROR]"):
        print(f"[reports] Extraction failed: {raw}")
        return {}

    parsed = _salvage_json(raw)
    if not parsed:
        print("[reports] Extraction returned no parseable fields.")
        return {}

    return {key: str(parsed.get(key, "") or "") for key in _EXTRACT_KEYS}


def generate_report_text(report: dict) -> str:
    """Generate the final formatted daily-report text from report fields."""
    user_prompt = (
        f"Project: {report.get('project_name', '')}\n"
        f"Report No: {report.get('report_number', '')}\n"
        f"Date: {report.get('date', '')}\n"
        f"Prepared By: {report.get('prepared_by', '')}\n"
        f"Weather Morning: {report.get('weather_morning', '')}\n"
        f"Weather Afternoon: {report.get('weather_afternoon', '')}\n"
        f"Manpower: {report.get('manpower', '')}\n"
        f"Equipment: {report.get('equipment', '')}\n"
        f"Work Performed: {report.get('work_performed', '')}\n"
        f"Delays/Issues: {report.get('delays_issues', '')}\n"
        f"Safety Observations: {report.get('safety_observations', '')}\n"
        f"Visitors: {report.get('visitors', '')}"
    )
    return _call_claude(_GENERATE_SYSTEM, user_prompt, max_tokens=2000)


if __name__ == "__main__":
    print("--- daily_report_generator self-test ---")
    sample = {
        "project_name": "Metro Station A",
        "report_number": "DR-001",
        "date": "2026-06-08",
        "prepared_by": "J. Smith",
        "weather_morning": "Clear sky, 21\u00b0C",
        "weather_afternoon": "Partly cloudy, 26\u00b0C",
        "manpower": "6 carpenters, 4 laborers, 2 operators",
        "equipment": "1 tower crane (operational), 2 excavators",
        "work_performed": "Poured footings at grid lines A through C.",
        "delays_issues": "Concrete delivery delayed 2 hours.",
        "safety_observations": "Toolbox talk held; no incidents.",
        "visitors": "City inspector at 14:00.",
    }
    print(generate_report_text(sample))
