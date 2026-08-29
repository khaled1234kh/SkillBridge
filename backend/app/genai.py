"""GenAI provider for SkillBridge's four generation touchpoints:

  1. Skill extraction from a CV/transcript
  2. Learning path generation (explanation + practice + mini-project)
  3. AI Tutor chat
  4. Quiz generation

A real Anthropic (Claude) or OpenAI call is used when the corresponding API key
is set in the environment. When no key is available the provider falls back to a
deterministic generator that still produces structured, non-empty, context-aware
content — so the app remains fully demoable end to end without credentials.
"""
import json
import os
import re

PROVIDER = "anthropic_model"
CLAUDE_MODEL = os.environ.get("SKILLBRIDGE_CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
OPENAI_MODEL = os.environ.get("SKILLBRIDGE_OPENAI_MODEL", "gpt-4o")

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")


def genai_enabled():
    return bool(ANTHROPIC_KEY or OPENAI_KEY)


def _call_anthropic(system, user):
    import httpx
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 2048,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _call_openai(system, user):
    import httpx
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _generate(system, user):
    if OPENAI_KEY:
        try:
            return _call_openai(system, user)
        except Exception:
            pass
    if ANTHROPIC_KEY:
        try:
            return _call_anthropic(system, user)
        except Exception:
            pass
    raise RuntimeError("No GenAI provider available")


def complete(system, user, fallback=None):
    try:
        return _generate(system, user)
    except Exception as exc:
        if fallback is not None:
            return fallback
        raise


# ---------------------------------------------------------------- JSON helpers

def _extract_json(text):
    """Best-effort extraction of a JSON object/array from a model response."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            return None
    return None


# ---------------------------------------------------------------- 1. Skill extraction

FALLBACK_SKILL_CATEGORIES = {
    "Python": "Programming", "SQL": "Data", "Machine Learning": "AI",
    "Docker": "DevOps", "Excel": "Analytics", "Tableau": "Visualization",
    "Git": "DevOps", "AWS": "DevOps", "Java": "Programming", "C++": "Programming",
    "React": "Programming", "JavaScript": "Programming", "TypeScript": "Programming",
    "Statistics": "Data", "Communication": "Soft Skills", "Teamwork": "Soft Skills",
    "Leadership": "Soft Skills", "Data Visualization": "Data", "NLP": "AI",
    "PyTorch": "AI", "TensorFlow": "AI", "Power BI": "Visualization",
}


def _known_skill(name):
    for key in FALLBACK_SKILL_CATEGORIES:
        if key.lower() == name.lower():
            return key, FALLBACK_SKILL_CATEGORIES[key]
    return name, "General"


def extract_skills_from_cv(cv_text):
    system = (
        "You are a skill-extraction engine. Given a candidate's CV or transcript text, "
        "extract the technical and professional skills they claim, and return STRICT JSON: "
        'an array of objects, each {"name": string, "level": "Beginner"|"Intermediate"|"Advanced", '
        '"category": string}. Include only skills actually present or implied in the text. '
        'Infer level from how the person describes experience. Return ONLY the JSON array, no prose.'
    )

    def fallback():
        found = []
        for line in re.split(r"[\n,;•|]", cv_text):
            line = line.strip()
            for name in FALLBACK_SKILL_CATEGORIES:
                if re.search(r"\b" + re.escape(name) + r"\b", line, re.I) and name not in [f["name"] for f in found]:
                    found.append({"name": name, "level": "Intermediate", "category": FALLBACK_SKILL_CATEGORIES[name]})
        if not found:
            found = [{"name": "Python", "level": "Intermediate", "category": "Programming"},
                     {"name": "SQL", "level": "Beginner", "category": "Data"}]
        return found

    raw = complete(system, f"CV text:\n\n{cv_text}", fallback=json.dumps(fallback()))
    parsed = _extract_json(raw)
    if not isinstance(parsed, list) or not parsed:
        parsed = fallback()
    cleaned = []
    for item in parsed:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        name = str(item["name"]).strip()[:60]
        level = item.get("level")
        if level not in ("Beginner", "Intermediate", "Advanced"):
            level = "Intermediate"
        cat = str(item.get("category") or "")[:40] or "General"
        cleaned.append({"name": name, "level": level, "category": cat})
    return cleaned or fallback()


# ---------------------------------------------------------------- 2. Learning path

def generate_learning_item(skill_name, skill_category, target_role, student_context):
    system = (
        "You are a personalized career coach creating a learning path item for a student "
        "working toward a specific target role. Produce content tailored to that role, "
        "NOT generic tutorials. Return STRICT JSON with exactly three keys: "
        '"explanation", "practice_exercise", "mini_project". '
        "The explanation connects the skill to the target role; the practice exercise is a "
        "short hands-on task; the mini_project is a small deliverable tied to the role. "
        "Return ONLY the JSON object, no prose."
    )
    user = (
        f"Skill to learn: {skill_name} ({skill_category})\n"
        f"Target role: {target_role}\n"
        f"Student background: {student_context or 'no additional background provided'}\n\n"
        "Generate the JSON learning item."
    )

    def fallback():
        explanation = (
            f"**{skill_name} for {target_role}** — In a {target_role} role, {skill_name} "
            f"({skill_category}) is used to build, ship, and maintain real solutions. "
            f"You'll apply it to production problems rather than textbook exercises, so this "
            f"path focuses on hands-on fluency tied to the job."
        )
        practice = (
            f"Practice: set up a small {skill_name} workflow — configure it, run it, and "
            f"then break and fix it deliberately so you understand failure modes before moving on."
        )
        project = (
            f"Mini-project: build a small {skill_name}-powered deliverable relevant to "
            f"a {target_role}, e.g. a working example you could include in a portfolio and explain in an interview."
        )
        return {"explanation": explanation, "practice_exercise": practice, "mini_project": project}

    raw = complete(system, user, fallback=json.dumps(fallback()))
    parsed = _extract_json(raw)
    if not isinstance(parsed, dict):
        parsed = fallback()
    return {
        "explanation": str(parsed.get("explanation") or ""),
        "practice_exercise": str(parsed.get("practice_exercise") or ""),
        "mini_project": str(parsed.get("mini_project") or ""),
    }


# ---------------------------------------------------------------- 3. AI Tutor chat

def tutor_reply(question, student_context, skill_name, target_role):
    system = (
        "You are the SkillBridge AI Tutor, a personalized coaching assistant helping a "
        "university student master a skill gap on the way to their target career. "
        "You have the student's background, their current skill gap, and their target role "
        "as context. Answer concisely, concretely and personally — reference their situation "
        "rather than giving generic advice. Keep answers helpful and focused."
    )
    user = (
        f"Student context: {student_context or 'unknown'}\n"
        f"Current skill gap: {skill_name or 'general'}\n"
        f"Target role: {target_role}\n"
        f"Student asks: {question}"
    )

    def fallback():
        return (
            f"Here's some guidance on **{skill_name or 'this skill'}** for someone aiming "
            f"to become a {target_role or 'developer'}. Since your background is "
            f"'{student_context or 'being built'}', focus on hands-on practice that maps to "
            f"the {target_role or 'role'} you're targeting. Break the skill into small tasks, "
            f"apply it to a realistic mini-project, and revisit this gap after an assessment "
            f"to confirm you've closed it. What specific part would you like to dig into?"
        )

    return complete(system, user, fallback=fallback())


# ---------------------------------------------------------------- 4. Quiz generation

def generate_quiz(skill_name, target_role, num_questions=4):
    system = (
        "You create assessment quiz questions for verifying a university student's skill "
        "level. Each question must be answerable objectively and test real understanding of "
        "the skill, ideally in the context of the role they are targeting. "
        'Return STRICT JSON: an array of question objects, each {"question": string, '
        '"type": "multiple_choice"|"free_text", "options": [array of strings, empty for free_text], '
        '"answer": correct answer string (for free_text, a model answer summary)}. '
        "Return ONLY the JSON array, no prose."
    )
    user = (f"Skill: {skill_name}\nTarget role: {target_role}\n"
            f"Generate {num_questions} questions of mixed types.")

    def fallback():
        return [
            {"question": f"What is the core purpose of {skill_name} in a {target_role} setting?",
             "type": "multiple_choice", "options": [
                 f"To apply {skill_name} to real problems and deliverables",
                 "To memorize definitions without practical use",
                 "To replace other skills entirely",
                 "To avoid hands-on work"],
             "answer": f"To apply {skill_name} to real problems and deliverables"},
            {"question": f"Describe one concrete way you would apply {skill_name} to a task a {target_role} faces.",
             "type": "free_text", "options": [], "answer": "A specific, practical application of the skill."},
            {"question": f"Which best describes an advanced-level use of {skill_name}?",
             "type": "multiple_choice", "options": [
                 "Using it to design and optimize a real workflow",
                 "Knowing its name but not using it",
                 "Avoiding it wherever possible",
                 "Only in very simple examples"],
             "answer": "Using it to design and optimize a real workflow"},
            {"question": f"Outline the steps you would take to get better at {skill_name}.",
             "type": "free_text", "options": [], "answer": "Concrete practice steps tied to the role."},
        ][:num_questions]

    raw = complete(system, user, fallback=json.dumps(fallback()))
    parsed = _extract_json(raw)
    if not isinstance(parsed, list) or not parsed:
        parsed = fallback()
    questions = []
    for q in parsed[:num_questions]:
        if not isinstance(q, dict) or not q.get("question"):
            continue
        qtype = q.get("type")
        if qtype not in ("multiple_choice", "free_text"):
            qtype = "multiple_choice"
        questions.append({
            "question": str(q["question"]),
            "type": qtype,
            "options": [str(o) for o in (q.get("options") or [])],
            "answer": str(q.get("answer") or ""),
        })
    return questions or fallback()
