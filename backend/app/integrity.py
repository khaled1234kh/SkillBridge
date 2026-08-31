"""Integrity monitoring heuristics for proctored assessments.

Simulates proctoring via non-invasive signals (no webcam/biometrics):
  - tab-switch / focus-loss events
  - timing anomalies (attempt too fast to be plausible for the question count)
  - suspected pasted-AI-text on free-text answers (heuristic classifier)

Each detection function returns an integrity flag dict with a stable code,
a label, and a severity. The frontend both reports local events (tab switches)
and submits free-text answers / timing for server-side checks.
"""
import re

UNUSUAL_FILL_SPEED_SECS = 8.0  # faster than this per question = suspicious
UNUSUAL_TOTAL_SECS_PER_Q = 12.0  # whole attempt finished faster than this = timing anomaly


def flag_tab_switch():
    return {
        "code": "tab_switch",
        "label": "Tab switch detected",
        "severity": "warning",
        "detail": "The assessment window lost focus during the attempt, which can indicate navigating away from the test.",
    }


def flag_timing_anomaly(total_seconds, question_count):
    per_q = total_seconds / max(question_count, 1)
    return {
        "code": "timing_anomaly",
        "label": "Timing anomaly",
        "severity": "warning",
        "detail": f"Attempt completed in {total_seconds:.0f}s ({per_q:.1f}s per question), which is implausibly fast for {question_count} questions.",
    }


# ---------------------------------------------------------------- AI-text detection

# Phrases and stylistic patterns more typical of polished generative text than
# of a student's own rushed free-text answer.
_AI_MARKERS = [
    re.compile(r"\b(in conclusion|furthermore|moreover|overall)\b", re.I),
    re.compile(r"\b(leverag|utiliz|harness|streamline|robust)\w*", re.I),
    re.compile(r"\b(it is (important|essential|crucial) to)\b", re.I),
    re.compile(r"\b(comprehensive|seamless|cutting-edge|state-of-the-art)\b", re.I),
    re.compile(r"\bbelow is a|here is a (detailed|summary|breakdown)\b", re.I),
    re.compile(r"\b\d+(st|nd|rd|th)\b.*\b(step|firstly|secondly)\b", re.I),
    re.compile(r"\bit('| i)?s worth noting\b", re.I),
]

# Em-dash and parenthetical density can indicate polished generated prose.
_AI_PATTERNS = [
    (lambda t: len(t.split()) >= 60, "Long, unbroken prose answer"),
    (lambda t: t.count("—") >= 3 or t.count("–") >= 3, "Heavy em/en-dash usage"),
    (lambda t: len(re.findall(r"\([^)]*\)", t)) >= 4, "Dense parentheticals"),
]


def detect_ai_text(text):
    """Return (is_flagged: bool, flags: list[dict]). Returns empty flags if clean."""
    if not text or not text.strip():
        return False, []
    flags = []
    marker_hits = []
    for pat in _AI_MARKERS:
        m = pat.search(text)
        if m:
            marker_hits.append(m.group(0))
    if len(marker_hits) >= 2:
        flags.append({
            "code": "ai_text",
            "label": "Possible AI-generated answer",
            "severity": "high",
            "detail": f"Free-text answer contains multiple stylistic markers common in generated prose ({', '.join(sorted(set(marker_hits)))}).",
        })
    for fn, label in _AI_PATTERNS:
        if fn(text):
            flags.append({
                "code": "ai_text_pattern",
                "label": "Possible AI-generated answer",
                "severity": "high",
                "detail": label,
            })
            break
    return bool(flags), flags


def evaluate_attempt(question_count, total_seconds, free_text_answers, local_tab_switches, ai_flags=None):
    """Combine locally-detected and server-side detected signals into the full
    flag list for a result screen. AI flags may be supplied by the client's own
    checks; we re-run the server-side heuristic here for authority."""
    flags = []

    if local_tab_switches:
        for _ in range(local_tab_switches):
            flags.append(flag_tab_switch())

    if ai_flags:
        flags.extend(ai_flags)

    for text in (free_text_answers or []):
        flagged, fl = detect_ai_text(text)
        if flagged:
            for f in fl:
                if f not in flags:
                    flags.append(f)

    if total_seconds is not None and question_count:
        if total_seconds / question_count < UNUSUAL_TOTAL_SECS_PER_Q:
            flags.append(flag_timing_anomaly(total_seconds, question_count))

    # de-duplicate tab switch if count == 0 handled; ensure list always JSON-safe
    return flags
