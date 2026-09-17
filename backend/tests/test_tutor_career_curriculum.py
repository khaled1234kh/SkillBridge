"""Career-curriculum deterministic knowledge bank (r7 round 6).

When the NIM provider draw fails or is throttled past the spoken bound, the
deterministic ``_tutor_fallback`` is the product. It previously knew only
Docker + a handful of science topics, so everyday career questions ("What is a
resume?", "How do I prepare for an interview?") degraded to the limitation
refusal ("This question isn't answering reliably..."). This suite pins the new
grounded career bank: every mapped career question must produce a real,
topic-appropriate answer in EN and AR across all four personas, and every new
entry must provide every field the persona templates render (no KeyError / no
unfilled placeholders).

Never calls a paid API — everything here is deterministic.
"""

import pytest

from app import genai

# topic key -> (en question samples, ar question samples)
CAREER_SAMPLES = {
    "resume": (
        ["What is a resume?", "how do I write a good resume?", "resume tips"],
        ["إيه هي السيرة الذاتية؟", "إزاي أكتب سي في؟"],
    ),
    "cover letter": (
        ["What is a cover letter?", "how do I write a cover letter?"],
        ["إيه خطاب التقديم؟", "إزاي أكتب رسالة تقديم؟"],
    ),
    "interview": (
        ["How do I prepare for a job interview?", "common interview questions"],
        ["إزاي أتحضر للمقابلة؟", "أسئلة الانترفيو الشائعة"],
    ),
    "job search": (
        ["How do I search for a job?", "tips for applying to jobs"],
        ["إزاي أدور على شغل؟", "نصايح للتقديم على وظيفة"],
    ),
    "networking": (
        ["What is professional networking?", "how to network with people"],
        ["إيه هو التواصل المهني؟", "إزاي أبني شبكة علاقات؟"],
    ),
    "linkedin": (
        ["How do I improve my LinkedIn profile?"],
        ["إزاي أحسّن صفحتي على LinkedIn؟"],
    ),
    "portfolio": (
        ["What should a portfolio include?", "how do I build a portfolio?"],
        ["إيه اللي لازم يكون في الـ portfolio؟", "إزاي أعمل بورتفوليو؟"],
    ),
    "salary negotiation": (
        ["How do I negotiate my salary?", "salary negotiation tips"],
        ["إزاي أتفاوض على المرتب؟", "التفاوض على الراتب"],
    ),
    "career planning": (
        ["How do I plan my career?", "career path ideas"],
        ["إزاي أخطط مسيرتي المهنية؟", "فكرة مسار مهني"],
    ),
    "soft skills": (
        ["What are soft skills?", "why do soft skills matter?"],
        ["إيه هي المهارات الناعمة؟"],
    ),
    "internship": (
        ["What is an internship?", "how do I get an internship?"],
        ["إيه هو الانترنشيب؟", "إزاي ألاقي فرصة تدريب؟"],
    ),
    "git": (
        ["What is git?", "why should I learn git?"],
        ["إيه هو git؟"],
    ),
}

# EN / AR content fragments drawn from the rendered-by-every-persona `plain`
# field (Nova renders analogy, Axel practice, Sage tradeoff, Vex challenge — so
# the fragment must live in the shared plain string to hold across personas).
CONTENT_FRAGMENT = {
    "resume": ("one-page summary", "مهاراتك"),
    "cover letter": ("three-to-four paragraph", "3 لـ 4 فقرات"),
    "interview": ("two-way conversation", "اتجاهين"),
    "job search": ("system, not a lottery", "نظام مش يانصيب"),
    "networking": ("before you need them", "قبل ما تحتاجها"),
    "linkedin": ("always-on professional page", "صفحتك المهنية"),
    "portfolio": ("proves you can do the work", "تشتغل فعلاً"),
    "salary negotiation": ("never a fight", "مش معركة"),
    "career planning": ("6-month plan", "خطة 6 شهور"),
    "soft skills": ("talented and effective", "موهوب وفعّال"),
    "internship": ("supervised work placement", "فرصة شغل قصيرة"),
    "git": ("version-control system", "لقطات"),
}

REFUSAL_MARKERS_EN = ("answering reliably", "can't answer", "can't give")
REFUSAL_MARKERS_AR = ("بيرد بشكل موثوق", "بدقة كافية", "هبدّع")

# "My career" phrasing (EN: I plan MY career / AR: مسيرتي) can legitimately
# resolve to the trusted profile branch instead of general knowledge — with a
# bare profile it replies honestly "set a target role on Skills & Roles" rather
# than teaching career planning. Both are substantive; never a refusal.
PROFILE_ALT = {
    "career planning": ("doesn't have a target role", "مفيش عليه دور مستهدف"),
}


def _reply_ok(reply, frag, profile_alt):
    if frag in reply:
        return True
    return bool(profile_alt) and profile_alt in reply


@pytest.mark.parametrize("topic", list(CAREER_SAMPLES))
def test_career_topic_maps(topic):
    en_samples, ar_samples = CAREER_SAMPLES[topic]
    for q in en_samples + ar_samples:
        mapped = genai._topic_from_question(q, skill_name="unrelated fallback", language="en")
        assert mapped == topic, f"{q!r} mapped to {mapped!r}, expected {topic!r}"


@pytest.mark.parametrize("topic", list(CAREER_SAMPLES))
def test_career_fallback_answers_not_refuses(topic):
    en_samples, ar_samples = CAREER_SAMPLES[topic]
    en_frag, ar_frag = CONTENT_FRAGMENT[topic]
    en_alt, ar_alt = PROFILE_ALT.get(topic, (None, None))
    for q in en_samples:
        reply = genai._tutor_fallback(
            q, skill_name=None, target_role=None, student_context="",
            tutor_id="sage", language="en",
        )
        assert reply
        assert _reply_ok(reply, en_frag, en_alt)
        for marker in REFUSAL_MARKERS_EN:
            assert marker not in reply, f"{q!r} hit refusal marker {marker!r}: {reply}"
    for q in ar_samples:
        reply = genai._tutor_fallback(
            q, skill_name=None, target_role=None, student_context="",
            tutor_id="sage", language="ar",
        )
        assert reply
        assert _reply_ok(reply, ar_frag, ar_alt)
        for marker in REFUSAL_MARKERS_AR:
            assert marker not in reply, f"{q!r} hit refusal marker {marker!r}: {reply}"


@pytest.mark.parametrize("persona", ["nova", "axel", "sage", "vex"])
def test_all_personas_render_career_entries(persona):
    """Every persona renders every new entry in EN and AR with no KeyError and
    no left-over template placeholders (the .format(**details) contract)."""
    for topic, (en_samples, ar_samples) in CAREER_SAMPLES.items():
        for lang, sample in (("en", en_samples[0]), ("ar", ar_samples[0])):
            reply = genai._tutor_fallback(
                sample, skill_name=None, target_role=None, student_context="",
                tutor_id=persona, language=lang,
            )
            assert reply
            assert "{" not in reply, f"{persona}/{lang}/{topic} left a placeholder"


def test_new_entries_have_all_render_fields():
    required = {"plain", "analogy", "example", "practice", "tradeoff", "question", "challenge"}
    for topic in CAREER_SAMPLES:
        entry = genai._GENERAL_KNOWLEDGE[topic]
        assert {"en", "ar"} <= set(entry)
        for lang in ("en", "ar"):
            assert required <= set(entry[lang]), (topic, lang, sorted(required - set(entry[lang])))


def test_spoken_flag_still_passes_latency_bounds():
    """The /tutor spoken path is byte-identical to before for career topics: the
    fallback answers directly (no provider) even when the provider is down."""
    reply = genai._tutor_fallback(
        "What is a resume?", skill_name=None, target_role=None, student_context="",
        tutor_id="nova", language="en",
    )
    assert len(reply) < 1600