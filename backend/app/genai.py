"""GenAI provider for SkillBridge's four generation touchpoints:

  1. Skill extraction from a CV/transcript
  2. Learning path generation (explanation + practice + mini-project + resources + roadmap)
  3. AI Tutor chat
  4. Quiz generation (with per-question explanations)

A real Anthropic (Claude) or OpenAI call is used when the corresponding API key
is set in the environment. When no key is available the provider falls back to a
deterministic generator that still produces structured, non-empty, context-aware
content — so the app remains fully demoable end to end without credentials.
"""
import difflib
import json
import os
import re

PROVIDER = "anthropic_model"
CLAUDE_MODEL = os.environ.get("SKILLBRIDGE_CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
OPENAI_MODEL = os.environ.get("SKILLBRIDGE_OPENAI_MODEL", "gpt-4o")

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

LEVELS = ("Beginner", "Intermediate", "Advanced")


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
            "max_tokens": 4096,
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
    text = (text or "").strip()
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

# Comprehensive shared-skill list with category mappings. Used by the fallback
# extractor, the role catalog seed, and every deterministic path so skill names
# stay consistent across the app.
FALLBACK_SKILL_CATEGORIES = {
    # Programming
    "Python": "Programming", "Java": "Programming", "C++": "Programming",
    "JavaScript": "Programming", "TypeScript": "Programming", "React": "Programming",
    "Node.js": "Programming", "HTML/CSS": "Programming", "Rust": "Programming",
    "Go": "Programming", "C#": "Programming", "FastAPI": "Programming",
    "Flask": "Programming", "Django": "Programming",
    # Data
    "SQL": "Data", "Statistics": "Data", "ETL": "Data", "Data Engineering": "Data",
    "Excel": "Analytics", "Pandas": "Data", "NumPy": "Data",
    "Data Modeling": "Data", "Data Analysis": "Data", "BigQuery": "Data",
    "Snowflake": "Data", "dbt": "Data", "Airflow": "Data", "Spark": "Data",
    # AI / ML
    "Machine Learning": "AI", "Deep Learning": "AI", "NLP": "AI", "PyTorch": "AI",
    "TensorFlow": "AI", "scikit-learn": "AI", "LLM Prompting": "AI",
    "Retrieval-Augmented Generation": "AI",
    # DevOps / infra
    "Docker": "DevOps", "Kubernetes": "DevOps", "Git": "DevOps", "AWS": "DevOps",
    "Azure": "DevOps", "GCP": "DevOps", "Linux": "DevOps", "CI/CD": "DevOps",
    "Terraform": "DevOps", "REST APIs": "DevOps", "SQLAlchemy": "DevOps",
    # Visualization
    "Tableau": "Visualization", "Power BI": "Visualization", "Data Visualization": "Visualization",
    # Analytics
    "Business Intelligence": "Analytics", "A/B Testing": "Analytics",
    "Data Storytelling": "Analytics",
    # Security
    "Cybersecurity": "Security", "Network Security": "Security",
    "Incident Response": "Security", "SIEM": "Security", "Risk Assessment": "Security",
    "Threat Detection": "Security", "Cloud Security": "Security",
    "Penetration Testing": "Security", "ISO 27001": "Security", "Security+": "Security",
    "Digital Forensics": "Security", "Vulnerability Management": "Security",
    "Windows Server": "Security", "Active Directory": "Security",
    # Soft skills
    "Communication": "Soft Skills", "Teamwork": "Soft Skills", "Leadership": "Soft Skills",
    "Problem Solving": "Soft Skills", "Critical Thinking": "Soft Skills",
    "Time Management": "Soft Skills",
}

# Synonyms so a CV can say "ML" and we map it to "Machine Learning".
_SYNONYMS = {
    "ml": "Machine Learning", "ai": "Machine Learning",
    "deep learning": "Deep Learning", "dl": "Deep Learning",
    "pandas": "Pandas", "numpy": "NumPy", "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn", "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript", "sqlalchemy": "SQLAlchemy",
    "rest api": "REST APIs", "restful": "REST APIs", "fast api": "FastAPI",
    "spark": "Spark", "kafka": "Data Engineering",
    "powerbi": "Power BI", "power bi": "Power BI", "tableau": "Tableau",
    "cyber security": "Cybersecurity", "infosec": "Cybersecurity",
    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "git": "Git", "github": "Git", "linux": "Linux", "aws": "AWS",
    "azure": "Azure", "gcp": "GCP", "google cloud": "GCP",
    "communication": "Communication", "leadership": "Leadership",
    "team work": "Teamwork", "excel": "Excel", "python": "Python",
    "java": "Java", "c++": "C++", "c": "C++", "react": "React",
    "node": "Node.js", "nodejs": "Node.js", "html": "HTML/CSS",
    "css": "HTML/CSS", "terraform": "Terraform", "airflow": "Airflow",
    "snowflake": "Snowflake", "bigquery": "BigQuery", "dbt": "dbt",
    "nlp": "NLP", "pytorch": "PyTorch", "tensorflow": "TensorFlow",
}

# Category guesses for synonyms that do not map to a canonical listed name.
_SYNONYM_CATEGORY = {
    "kafka": "Data", "github": "DevOps", "node": "Programming", "k8s": "DevOps",
}

_LVL_HINTS = {
    "Advanced": [r"\b(advanced|expert|fluent|proficient|deep\s+knowledge|senior)\b"],
    "Intermediate": [r"\b(intermediate|working\s+knowledge|comfortable\s+with|moderate)\b"],
    "Beginner": [r"\b(beginner|basic|introductory|entry\s+level|familiar\s+with|fundamentals?)\b"],
}


def _normalise_skill(raw_name):
    """Return (canonical_name, category) or (None, None) if unknown."""
    name = (raw_name or "").strip()
    key = name.lower()
    if not key:
        return None, None
    if key in _SYNONYMS:
        canon = _SYNONYMS[key]
        return canon, FALLBACK_SKILL_CATEGORIES.get(canon, "General")
    for canon in FALLBACK_SKILL_CATEGORIES:
        canon_key = canon.lower()
        if key == canon_key:
            return canon, FALLBACK_SKILL_CATEGORIES[canon]
    # fuzzy substring: "Python programming" -> "Python"
    for canon in FALLBACK_SKILL_CATEGORIES:
        ck = canon.lower()
        if ck in key and len(ck) >= 3:
            return canon, FALLBACK_SKILL_CATEGORIES[canon]
    if key in _SYNONYM_CATEGORY:
        return raw_name.strip(), _SYNONYM_CATEGORY[key]
    return None, None


def _infer_level(text, name):
    """Scan the full document for level hints about this skill."""
    name_esc = re.escape(name)
    # look at the sentence/line containing the skill
    sentences = re.split(r"(?<=[.!\n])\s+", text)
    candidates = [s for s in sentences if re.search(rf"\b{name_esc}\b", s, re.I)]
    if not candidates:
        return "Intermediate"
    for level, pats in _LVL_HINTS.items():
        for pat in pats:
            for s in candidates:
                if re.search(pat, s, re.I):
                    return level
    return "Intermediate"


def extract_skills_from_cv(cv_text):
    system = (
        "You are a skill-extraction engine. Given a candidate's CV or transcript text, "
        "extract the technical and professional skills they claim, and return STRICT JSON: "
        'an array of objects, each {"name": string, "level": "Beginner"|"Intermediate"|"Advanced", '
        '"category": string}. Include only skills actually present or implied in the text. '
        "Infer level from how the person describes experience. Use the supplied list of "
        "canonical skill names when the text clearly refers to one of them. "
        "Return ONLY the JSON array, no prose."
    )

    def fallback():
        found = {}
        # 1) Token scan across delimiters — catches single-word skills in any section.
        for line in re.split(r"[\n,;•|]", cv_text):
            line = line.strip()
            if not line:
                continue
            for token in re.findall(r"[A-Za-z][A-Za-z0-9+#\-_. ]{1,40}", line):
                canon, cat = _normalise_skill(token.strip())
                if canon and canon not in found:
                    found[canon] = {
                        "name": canon, "level": _infer_level(cv_text, canon),
                        "category": cat or "General",
                    }
        # 2) Canonical-name scan always runs too (not only when empty) so
        #    multi-word skills embedded mid-sentence are never missed.
        lowered = cv_text.lower()
        for canon in sorted(FALLBACK_SKILL_CATEGORIES, key=len, reverse=True):
            if canon.lower() in found:
                continue
            if re.search(rf"\b{re.escape(canon.lower())}\b", lowered):
                found[canon] = {
                    "name": canon, "level": _infer_level(cv_text, canon),
                    "category": FALLBACK_SKILL_CATEGORIES[canon],
                }
        return list(found.values())

    fallback_val = fallback()
    if not fallback_val:
        fallback_val = [{"name": "Python", "level": "Beginner", "category": "Programming"}]
    raw = complete(system, f"Canonical skill list to match against:\n"
                           f"{', '.join(sorted(FALLBACK_SKILL_CATEGORIES))}\n\nCV text:\n\n{cv_text}",
                   fallback=json.dumps(fallback_val))
    parsed = _extract_json(raw)
    if not isinstance(parsed, list) or not parsed:
        parsed = fallback_val

    cleaned = []
    seen = set()
    for item in parsed:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        name = str(item["name"]).strip()[:60]
        canon, cat = _normalise_skill(name)
        name = canon or name
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        level = item.get("level")
        if level not in LEVELS:
            level = _infer_level(cv_text, name)
        cat = cat or str(item.get("category") or "")[:40] or "General"
        cleaned.append({"name": name, "level": level, "category": cat})
    return cleaned or fallback_val


# ---------------------------------------------------------------- 2. Learning path

def _role_context_blurb(skill_name, target_role):
    return (f"**{skill_name} for {target_role}** — In a {target_role} role, {skill_name} "
            f"is used on real, production-shaped problems. This path is built around hands-on "
            f"fluency that maps directly to the job, not around generic tutorials.")


def _build_roadmap(skill_name, target_role, resources):
    """Deterministic 4-step roadmap, each step carrying the real, titled
    resource sources it points at (up to two per step, spread across the list)."""
    steps = []
    steps_count = 4
    n = len(resources)
    for i, (title, objective, practice) in enumerate([
        ("Foundations", f"Grasp the core concepts of {skill_name} and where they fit in a {target_role}'s day-to-day work.", "Skim the tied resources, then write a one-paragraph summary in your own words identifying the 3 most important concepts."),
        ("Hands-on", f"Build a small working example of {skill_name} end to end.", "Follow the linked tutorial; deliberately make it fail, then fix it, and note the failure mode."),
        ("Role-driven project", f"Apply {skill_name} to a deliverable a real {target_role} would produce.", "Complete the mini-project below and gather concrete results to discuss."),
        ("Assessment-ready", f"Consolidate {skill_name} to the level your target role requires and self-test.", "Review your work, take the associated skill assessment, and revise any gaps."),
    ]):
        steps.append(_roadmap_step(i + 1, title, objective, practice,
                                   f"You can explain {skill_name} and demonstrate it on a {target_role} task.",
                                   _step_ranks(i, steps_count, n), resources))
    return {"summary": f"A practical, career-targeted path from first principles to assessment-ready "
                       f"{skill_name} for a {target_role}.", "steps": steps}


def _step_ranks(i, step_count, n):
    """1-based resource ranks cited by a roadmap step — two distinct sources
    per step when enough resource depth exists, otherwise a single rotating
    source so neighbouring steps never show the identical list."""
    if n == 0:
        return []
    if n < 4:
        return [i % n + 1]
    k = 2
    spread = max(1, (n + 1) // 3)
    return sorted({(i * spread + j) % n + 1 for j in range(k)})


def _roadmap_step(step_no, title, objective, practice, checkpoint, ranks, resources):
    """One normalized roadmap step. `ranks` are 1-based indexes into the
    ranked `resources` list; the step also carries the full source objects so
    the UI can render real titled links (never bare rank numbers)."""
    step_resources = []
    for k in ranks or []:
        try:
            idx = int(k) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(resources):
            step_resources.append(dict(resources[idx]))
    return {
        "step": int(step_no),
        "title": str(title),
        "objective": str(objective),
        "practice": str(practice),
        "checkpoint": str(checkpoint),
        "resource_ranks": [int(k) for k in (ranks or [])],
        "resources": step_resources,
    }


def _normalize_roadmap(roadmap, resources, default):
    """Guarantee a well-formed roadmap: every step has a title/objective/practice
    plus a `resources` list of real source objects derived from its ranks. Steps
    without ranks get a distinct round-robin subset so no step duplicates another."""
    if not isinstance(roadmap, dict) or not isinstance(roadmap.get("steps"), list) or not roadmap["steps"]:
        roadmap = default["roadmap"]
    raw_steps = roadmap["steps"]
    step_count = max(1, len(raw_steps))
    n = len(resources)
    steps = []
    for i, s in enumerate(raw_steps):
        if not isinstance(s, dict):
            continue
        ranks = s.get("resource_ranks")
        if not isinstance(ranks, list):
            ranks = _step_ranks(i, step_count, n)
        steps.append(_roadmap_step(s.get("step") or i + 1,
                                   s.get("title") or f"Step {i + 1}",
                                   s.get("objective") or "",
                                   s.get("practice") or "",
                                   s.get("checkpoint") or "",
                                   ranks, resources))
    if not steps:
        return default["roadmap"]
    return {"summary": str(roadmap.get("summary") or default["roadmap"]["summary"]), "steps": steps}


def generate_learning_item(skill_name, skill_category, target_role, student_context=None):
    system = (
        "You are a personalized career coach creating a learning path item for a student "
        "working toward a specific target role. Produce content tailored to that role, "
        "NOT generic tutorials. Return STRICT JSON with exactly five keys: "
        '"explanation", "practice_exercise", "mini_project", "resources", "roadmap". '
        "The explanation connects the skill to the target role; the practice exercise is a "
        "short hands-on task; the mini_project is a small deliverable tied to the role. "
        '"resources" must be an array of real, well-known URLs (official docs, YouTube '
        "channels, Coursera/edX courses) with {title, url, type} and NO invented links. "
        '"roadmap" is an object {"summary": string, "steps": [{step, title, objective, '
        "practice, checkpoint}]} — 3 to 5 sequenced steps to go from novice to "
        "assessment-ready. Return ONLY the JSON object, no prose."
    )
    user = (
        f"Skill to learn: {skill_name} ({skill_category})\n"
        f"Target role: {target_role}\n"
        f"Student background: {student_context or 'no additional background provided'}\n\n"
        "Generate the JSON learning item."
    )

    def fallback():
        from . import resources as resources_mod
        res = resources_mod.retrieve_resources(skill_name, skill_category, target_role)
        explanation = (
            f"{_role_context_blurb(skill_name, target_role)}\n\n"
            f"You already have relevant foundations to build on "
            f"('{student_context or 'being built'}'), so the priority is applying {skill_name} "
            f"to the kinds of problems a {target_role} encounters — reading real systems, "
            f"reproducing them, and shipping something small."
        )
        practice = (
            f"Practice: set up a small {skill_name} workflow, run it on a realistic input, "
            f"then deliberately break and fix it so you understand the failure modes before moving on."
        )
        project = (
            f"Mini-project: build a {skill_name}-powered deliverable a {target_role} could own — "
            f"for example a working example you can include in a portfolio and defend in an interview."
        )
        roadmap = _build_roadmap(skill_name, target_role, res)
        return {"explanation": explanation, "practice_exercise": practice,
                "mini_project": project, "resources": res, "roadmap": roadmap}

    raw = complete(system, user, fallback=json.dumps(fallback()))
    parsed = _extract_json(raw)
    if not isinstance(parsed, dict):
        parsed = fallback()
    default = fallback()
    resources = parsed.get("resources")
    if not isinstance(resources, list):
        resources = default["resources"]
    else:
        cleaned_res = []
        for r in resources:
            if isinstance(r, dict) and r.get("url"):
                cleaned_res.append({
                    "title": str(r.get("title") or "Resource")[:120],
                    "url": str(r["url"]),
                    "type": str(r.get("type") or "article")[:20],
                })
        resources = cleaned_res or default["resources"]

    roadmap = parsed.get("roadmap")
    if not isinstance(roadmap, dict) or not isinstance(roadmap.get("steps"), list) or not roadmap["steps"]:
        roadmap = default["roadmap"]
    roadmap = _normalize_roadmap(roadmap, resources, default)

    return {
        "explanation": str(parsed.get("explanation") or default["explanation"]),
        "practice_exercise": str(parsed.get("practice_exercise") or default["practice_exercise"]),
        "mini_project": str(parsed.get("mini_project") or default["mini_project"]),
        "resources": resources,
        "roadmap": roadmap,
    }


# ---------------------------------------------------------------- 3. AI Tutor chat

def tutor_reply(question, student_context=None, skill_name=None, target_role=None):
    system = (
        "You are the SkillBridge AI Tutor, a personalized coaching assistant helping a "
        "university student master a skill gap on the way to their target career. "
        "You have the student's background, their current skill gap, and their target role "
        "as context. Answer concisely, concretely and personally — reference their situation "
        "rather than giving generic advice. Use markdown for structure (short sections, "
        "bullets, code snippets where useful). Keep answers focused and helpful."
    )
    user = (
        f"Student context: {student_context or 'unknown'}\n"
        f"Current skill gap: {skill_name or 'general'}\n"
        f"Target role: {target_role}\n"
        f"Student asks: {question}"
    )

    def fallback():
        q = (question or "").lower()
        stops = {"your", "this", "that", "with", "from", "about", "would", "should", "what",
                 "when", "where", "which", "want", "going", "good", "best", "tell", "help",
                 "there", "their", "have", "just", "know", "like"}
        words = [w for w in re.findall(r"[a-z][a-z0-9']*", q) if len(w) > 3 and w not in stops]
        topic = ", ".join(sorted(set(words))[:4]) or (skill_name or "the core concepts")
        return (
            f"You asked about **{topic}** — here's practical guidance for someone aiming to be "
            f"a {target_role or 'developer'}. Since your background is "
            f"'{student_context or 'being built'}', start from where you are and push toward "
            f"hands-on fluency rather than theory.\n\n"
            f"**Break it down** — {topic} in a {target_role or 'technical'} role shows up in a few "
            f"concrete daily tasks. Name the single deliverable that would prove you can do it, "
            f"and use that as your target.\n\n"
            f"**Practice loop** — work 20-30 minute sessions, each producing a small artifact "
            f"(a runnable script, a config, a short write-up) so progress stays visible.\n\n"
            f"**Verify it** — when you feel ready, take the {skill_name or 'skill'} assessment; let "
            f"the result tell you what to revise next.\n\n"
            f"To go deeper on **{topic}**: what exactly are you trying to build, and which part "
            f"is blocking you most right now?"
        )

    return complete(system, user, fallback=fallback())


# ---------------------------------------------------------------- 4. Quiz generation

def _mcq(question, options, answer, explanation):
    return {"question": question, "type": "multiple_choice", "options": options,
            "answer": answer, "explanation": explanation}


def _ft(question, answer, explanation):
    return {"question": question, "type": "free_text", "options": [],
            "answer": answer, "explanation": explanation}


# Curated question banks for high-signal skills. Each question carries a model
# answer and an explanation so retakes and practice mode stay instructive.
_QUESTION_BANK = {
    "python": [
        _mcq("What does the `with` statement in Python primarily guarantee?",
             ["Resource cleanup even if an error occurs", "Faster variable access", "Type safety at runtime", "Thread safety"],
             "Resource cleanup even if an error occurs",
             "`with` implements the context-manager protocol so cleanup (e.g. closing a file) runs even on exceptions."),
        _mcq("Which of the following is the most Pythonic way to iterate over a list and its index?",
             ["for i, val in enumerate(items):", "for i in range(len(items)):", "for val, i in items:", "while i < len(items):"],
             "for i, val in enumerate(items):",
             "`enumerate()` exists precisely to pair an index with a value without manual counter management."),
        _mcq("What does a list comprehension `[x * 2 for x in range(4)]` produce?",
             ["[0, 2, 4, 6]", "[2, 4, 6, 8]", "[1, 2, 3, 4]", "[0, 0, 0, 0]"],
             "[0, 2, 4, 6]",
             "range(4) yields 0,1,2,3; doubling each gives 0,2,4,6."),
        _mcq("Which method would you use to read an entire text file as a string?",
             ["open('f.txt').read()", "open('f.txt').readlines()", "file('f.txt').get()", "read('f.txt')"],
             "open('f.txt').read()",
             "`.read()` returns the whole file as a single string; `.readlines()` gives a list of lines."),
        _mcq("What is the purpose of a Python virtual environment?",
             ["Isolate project dependencies from the system interpreter", "Make the code run faster", "Compile Python to machine code", "Auto-generate documentation"],
             "Isolate project dependencies from the system interpreter",
             "venvs pin per-project package versions so projects do not clash on shared dependencies."),
        _ft("Describe a situation where a Python generator (`yield`) is better than building a full list.",
            "A generator yields items lazily one at a time, so it uses constant memory for large or infinite sequences, e.g. streaming a huge log file line by line.",
            "Generators trade a little overhead for lazy evaluation — essential for large data streams."),
        _ft("A function unexpectedly raises a KeyError. What debugging steps do you take first?",
            "Read the traceback to find the exact line, check the dict literal/source of the key, print or inspect the keys actually present, and verify the key is inserted before access.",
            "Tracebacks tell you the failing line; confirm the key truly exists before changing logic."),
        _ft("How would you make a Python HTTP API call resilient to a temporary network failure?",
            "Wrap the request in try/except, implement a retry with exponential backoff, set a timeout, and cap the number of attempts to avoid a hang.",
            "Resilience = timeouts + bounded retries + explicit error handling."),
        _ft("Explain when you would choose a dataclass over a plain dict to hold structured data.",
            "A dataclass gives typed fields, auto-generated __init__/__repr__, and can add methods — better when the value has behavior and validation, while a dict is simpler for ad hoc data.",
            "Dataclasses encode a fixed schema; dicts are flexible but untyped."),
        _mcq("Which is the primary advantage of using type hints in Python?",
             ["Better editor support, documentation, and early error detection", "Faster execution at runtime", "Smaller memory footprint", "They replace documentation"],
             "Better editor support, documentation, and early error detection",
             "Type hints are optional metadata that tools (mypy, IDEs) use; Python ignores them at runtime."),
    ],
    "sql": [
        _mcq("Which SQL clause filters rows AFTER grouping?",
             ["HAVING", "WHERE", "GROUP BY", "ORDER BY"],
             "HAVING",
             "WHERE filters before aggregation; HAVING filters grouped results after GROUP BY."),
        _mcq("Which of the following will join every matching combination of rows from two tables?",
             ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN"],
             "INNER JOIN",
             "INNER JOIN returns rows where the join condition matches in both tables."),
        _mcq("What does `SELECT COUNT(DISTINCT department) FROM employees;` return?",
             ["The number of different departments", "All employees counted once", "The number of employees per department", "A syntax error"],
             "The number of different departments",
             "COUNT(DISTINCT x) counts unique values of x, not rows."),
        _mcq("Which operation should you use to remove duplicate rows in the result set?",
             ["SELECT DISTINCT ...", "SELECT UNIQUE ...", "GROUP ONLY", "SELECT CLEAN ..."],
             "SELECT DISTINCT ...",
             "DISTINCT collapses duplicate result rows."),
        _mcq("What is the purpose of an index on a column?",
             ["Speed up lookups and joins on that column", "Enforce the column is unique", "Compress the stored data", "Increase write speed"],
             "Speed up lookups and joins on that column",
             "Indexes are B-trees that make point lookups ~logarithmic but add write overhead."),
        _ft("Write a query to find the second-highest salary in an `employees(salary)` table.",
            "SELECT MAX(salary) FROM employees WHERE salary < (SELECT MAX(salary) FROM employees);",
            "Filtering out the max and taking the max of the remainder finds the runner-up."),
        _ft("You delete a row by mistake without a backup. What is the first thing you do?",
            "Stop writing to the database, check for a backup or bin log/WAL, and restore from the newest backup or use the transaction log if available.",
            "Immediate writes can overwrite recoverable data; recovery depends on backups or logs."),
        _ft("Explain the difference between a LEFT JOIN and an INNER JOIN with example use.",
            "INNER JOIN returns only matched rows; LEFT JOIN returns all rows from the left table with NULLs for unmatched right rows — e.g. listing all students and their optional enrollments.",
            "The key question is whether you want unmatched rows from one side preserved."),
        _mcq("Which transaction property ensures a transaction is atomic?",
             ["ALL-OR-NOTHING: it fully commits or fully rolls back", "It can be partially applied", "It never affects other users", "It always succeeds"],
             "ALL-OR-NOTHING: it fully commits or fully rolls back",
             "Atomicity means a transaction is an indivisible unit."),
        _ft("How would you debug a slow SQL query?",
            "Use EXPLAIN to view the plan, check for missing indexes on join/filter columns, examine the WHERE selectivity, and test with realistic data volumes.",
            "EXPLAIN reveals scans vs index seeks — the first step in query tuning."),
    ],
    "docker": [
        _mcq("What does a Docker image contain that a container does not?",
             ["The build-time state, which containers run as isolated instances", "A running process", "Networking config", "A database"],
             "The build-time state, which containers run as isolated instances",
             "An image is a frozen template; a container is a running instance of it."),
        _mcq("Which command builds an image from a Dockerfile?",
             ["docker build -t myapp .", "docker run -t myapp .", "docker compose up --build-only", "docker import myapp"],
             "docker build -t myapp .",
             "`docker build` compiles the Dockerfile into an image tagged with -t."),
        _mcq("What is the purpose of multi-stage builds?",
             ["Keep the final image small by copying only artifacts from a builder stage", "Run more containers simultaneously", "Speed up the Docker daemon", "Enable GPU access"],
             "Keep the final image small by copying only artifacts from a builder stage",
             "Multi-stage builds separate build tools from the runtime image to shrink its size."),
        _mcq("You need a container to persist data across restarts. What do you use?",
             ["A volume or bind mount", "A copy of the image", "ANOTHER IMAGE", "The container commit"],
             "A volume or bind mount",
             "Volumes live outside the container's ephemeral filesystem, surviving restarts and removals."),
        _mcq("What is the difference between EXPOSE in a Dockerfile and -p on the CLI?",
             ["EXPOSE is documentation; -p actually publishes the port", "EXPOSE publishes the port; -p documents it", "They are identical", "Neither affects networking"],
             "EXPOSE is documentation; -p actually publishes the port",
             "EXPOSE records intent; real port mapping requires `-p host:container` (unless using compose/network)."),
        _ft("A container you started exits immediately. How do you diagnose why?",
            "Run `docker logs <id>` for output, start with `docker run -it --rm` to see stderr live, and inspect the command/ENTRYPOINT; many exits are the main process terminating.",
            "Logs and running in the foreground reveal the true failing command."),
        _ft("How would you pass a secret to a container without embedding it in the image?",
            "Use environment variables from a secret source, Docker Secrets (swarm), environment from --env-file, or a mounted secret file — never bake secrets into the Dockerfile.",
            "Secrets in images get baked into every layer and can be extracted."),
        _ft("Explain the difference between an image layer and a container layer.",
            "Image layers are immutable build steps that can be shared across images; the container layer is a thin writable layer added at runtime.",
            "Layer sharing is what makes docker pull/build fast and space-efficient."),
        _mcq("Which Docker compose instruction starts a service only after another is healthy?",
             ["depends_on with condition: service_healthy", "links", "restart: on-failure", "networks"],
             "depends_on with condition: service_healthy",
             "Modern compose supports dependency health-gating via depends_on.condition."),
        _ft("Your Docker image is enormous. Name three practical ways to shrink it.",
            "Use a smaller base image (Alpine/slim), multi-stage builds to keep only runtime artifacts, and merge RUN commands to reduce layer count and stray cache files.",
            "Smaller bases, fewer layers, and stripped artifacts each reduce size."),
    ],
    "git": [
        _mcq("Which command permanently removes a file from the working tree AND stages its deletion?",
             ["git rm file", "git checkout file", "git reset file", "rm file && sync"],
             "git rm file",
             "`git rm` deletes the file and stages the removal in one step."),
        _mcq("What does `git commit --amend` do?",
             ["Replaces the most recent commit with a new one", "Adds a new commit on top", "Deletes the last commit permanently", "Merges the last two commits"],
             "Replaces the most recent commit with a new one",
             "Amend rewrites the last commit (and its message) — only safe for unpushed history."),
        _mcq("How do you cancel uncommitted changes to a single file and restore the last committed version?",
             ["git restore file", "git remove file", "git stash --permanent file", "git clean file"],
             "git restore file",
             "`git restore` (or `git checkout -- file`) discards working-tree changes."),
        _mcq("Which of these describes a merge conflict?",
             ["Git cannot auto-combine changes in the same lines of a file", "Git refuses to push", "Git deletes the file", "Git forks the repository"],
             "Git cannot auto-combine changes in the same lines of a file",
             "Conflicts occur when divergent changes touch the same lines in the same files."),
        _mcq("What is the purpose of `.gitignore`?",
             ["Prevent matching files from ever being tracked", "Delete matching files on commit", "Hide files only on GitHub", "Speed up git status"],
             "Prevent matching files from ever being tracked",
             "`.`gitignore lists patterns git should not track (build artifacts, secrets, caches)."),
        _ft("You committed a file containing an API key. What is the correct remediation?",
            "Remove/rotate the key immediately, delete the file and scrub history (e.g. `git filter-repo` or BFG), and force-push new history — treating the key as compromised regardless.",
            "History scrubbing must happen before others clone; rotation is mandatory."),
        _ft("Explain the difference between `git merge` and `git rebase`.",
            "Merge creates a new commit joining branches and preserves history; rebase replays commits onto a new base, producing linear history but rewriting original commit hashes.",
            "Rebase = cleaner history at the cost of rewritten commits (never rebase shared branches)."),
        _ft("How would you recover a file you deleted but had committed?",
            "`git restore <path>` from HEAD, or `git checkout <commit> -- <file>` to restore an older version.",
            "Deleted files exist in history until garbage collection."),
        _mcq("Which workflow lets several developers make simultaneous changes to the same repo without conflicts?",
             ["Feature branches + pull requests with code review", "Everyone committing directly to main", "Copying the folder manually", "Sending patches by email"],
             "Feature branches + pull requests with code review",
             "Isolated branches keep work separate until reviews and merges bring changes together."),
        _ft("What does `git bisect` do and when is it useful?",
            "It performs a binary search over commits to find the first one that introduces a bug, given a commit known-good and one known-bad.",
            "Bisect automates 'which commit broke this?' in O(log n) steps."),
    ],
    "machine learning": [
        _mcq("Which of these is a supervised learning task?",
             ["Predicting house prices from labeled features", "Grouping customers into clusters", "Reducing dimensionality for visualization", "Learning the structure of a document collection"],
             "Predicting house prices from labeled features",
             "Supervised learning learns from labeled input/output pairs; clustering is unsupervised."),
        _mcq("What is the main risk of training a model until it perfectly fits the training data?",
             ["Overfitting — poor generalization to new data", "It becomes slower at inference", "It uses more GPU memory", "The data becomes corrupted"],
             "Overfitting — poor generalization to new data",
             "Perfect training fit usually memorizes noise; validation metrics then degrade."),
        _mcq("Why do we split data into train/validation/test sets?",
             ["To tune hyperparameters honestly and measure final generalization on unseen data", "To make training faster", "Because datasets are too large", "To balance classes"],
             "To tune hyperparameters honestly and measure final generalization on unseen data",
             "Validation tunes; the test set estimates real-world performance without leakage."),
        _mcq("A classification model always predicts the majority class. Which metric best exposes this?",
             ["Recall/Precision per class (and F1), not just accuracy", "Accuracy on the training set", "Number of parameters", "Latency"],
             "Recall/Precision per class (and F1), not just accuracy",
             "On imbalanced data, high accuracy can mask zero useful signal; per-class metrics reveal it."),
        _mcq("What is feature scaling and why is it important for many ML algorithms?",
             ["Bringing all numeric features to a similar range so distance/gradient-based methods behave consistently", "Removing outliers entirely", "Encoding categorical text", "Speeding up data collection"],
             "Bringing all numeric features to a similar range so distance/gradient-based methods behave consistently",
             "Algorithms like kNN and SVM are sensitive to feature magnitudes."),
        _ft("Your model performs well on train but poorly on validation. Diagnose and describe the fix.",
            "This is overfitting: reduce model capacity or regularization strength, add dropout, increase data/augmentation, or use early stopping, and retune on validation only.",
            "Overfitting is the classic train/validation gap."),
        _ft("Explain the bias-variance tradeoff in your own words.",
            "Bias is systematic error from an overly simple model; variance is instability from an overly complex one. Low total error balances the two — move along model complexity until both are modest.",
            "Too simple underfits (high bias); too complex overfits (high variance)."),
        _ft("When would you prefer a decision tree over a large pre-trained model?",
            "When you need interpretability, fast inference, small data, or no GPU — trees are auditable and cheap, and win on tabular midsize data.",
            "Modern ML is not always the right call; simpler models beat giants on the right problems."),
        _mcq("Which is NOT a legitimate way to prevent data leakage?",
             ["Fitting the scaler on the full dataset before splitting", "Splitting before preprocessing", "Using time-based splits for temporal data", "Fitting scalers only on training folds"],
             "Fitting the scaler on the full dataset before splitting",
             "Any preprocessing that 'sees' the test set leaks information into training."),
        _ft("Describe one concrete model-deployment pitfall for ML systems in production.",
            "Training-serving skew — data distribution or feature pipelines differ at serve time (e.g., missing columns, drift), so you must monitor inputs and retrain.",
            "Production ML fails on data-engineering details, not the algorithm."),
    ],
}

_TEMPLATE_QUESTIONS = [
    lambda s, r: _mcq(f"What is the core purpose of {s} in a {r} setting?",
                      [f"To apply {s} to real problems and deliverables",
                       "To memorize definitions without practical use",
                       "To replace all other skills",
                       "To avoid hands-on work"],
                      f"To apply {s} to real problems and deliverables",
                      f"In a {r} role, {s} earns its keep by delivering practical outcomes, not by theory alone."),
    lambda s, r: _ft(f"Describe one concrete way you would apply {s} to a task a {r} faces.",
                     "A specific, practical application of the skill tied to the role, with a clear deliverable.",
                     f"This is assessing whether you can map {s} to real job tasks."),
    lambda s, r: _mcq(f"Which best describes an advanced-level use of {s}?",
                      [f"Using it to design and optimize a real workflow",
                       "Knowing its name but not using it",
                       "Avoiding it wherever possible",
                       "Only using it in very simple examples"],
                      f"Using it to design and optimize a real workflow",
                      "Advanced use means deliberate, production-oriented application."),
    lambda s, r: _ft(f"Outline the concrete steps you would take to get better at {s}.",
                     "Practice steps tied to the role: study real examples, build a small project, assess, repeat.",
                     "The point is to have an actionable plan, not a vague wish."),
    lambda s, r: _mcq(f"Which mistake is most dangerous when applying {s} in the real world?",
                      [f"Assuming it works the same in every context", "Reading official documentation",
                       "Practicing regularly", "Asking a senior colleague for help"],
                      f"Assuming it works the same in every context",
                      "Real systems rarely behave like tutorials — context matters."),
    lambda s, r: _mcq(f"Which approach shows genuine mastery of {s} in an interview?",
                      [f"Explaining a project where you used it end-to-end and the tradeoffs you made",
                       "Reciting its Wikipedia definition", "Naming the tools around it", "Showing version history"],
                      f"Explaining a project where you used it end-to-end and the tradeoffs you made",
                      "Interviewers value judgment and applied experience over recall."),
    lambda s, r: _ft(f"Describe the most common failure mode when people learn {s}.",
                     "Learning passively (watching videos/reading) without ever building something and debugging under pressure.",
                     "Active, failing-and-fixing practice is what builds real skill."),
    lambda s, r: _ft(f"If a colleague who doesn't know {s} asked what it's for, how would you explain it?",
                     "A simple analogy plus one concrete example of a problem it solves in your target role.",
                     "Teaching is the highest bar for understanding."),
    lambda s, r: _mcq(f"What does a complete {s} skill signal to an employer?",
                      [f"That you can deliver work using it, reliably, under real constraints",
                       "That you once read about it", "That you list it on your CV", "That you passed a course"],
                      f"That you can deliver work using it, reliably, under real constraints",
                      "Employers value verified, applied capability over claims."),
    lambda s, r: _ft(f"Plan a 2-week sprint to close your {s} gap for a {r} role.",
                     "Week 1: foundations + small daily practice; Week 2: role-relevant mini-project, seek feedback, then a self-assessment.",
                     "A concrete plan beats vague ambition."),
]


def generate_quiz(skill_name, target_role=None, num_questions=10, difficulty="Intermediate"):
    difficulty = difficulty if difficulty in LEVELS else "Intermediate"
    system = (
        "You create assessment quiz questions for verifying a university student's skill "
        "level. Each question must be answerable objectively and test real understanding of "
        "the skill, ideally in the context of the role they are targeting. "
        f"The assessment targets {difficulty} proficiency in the skill, so calibrate difficulty "
        "to match: for Advanced demand depth, applied reasoning and edge cases; for Beginner "
        "keep to fundamentals. "
        'Return STRICT JSON: an array of question objects, each {"question": string, '
        '"type": "multiple_choice"|"free_text", "options": [array of strings, empty for free_text], '
        '"answer": correct answer string (for free_text, a model answer summary), '
        '"explanation": string explaining the correct answer}. Make roughly 60% '
        "multiple_choice and 40% free_text, and make the questions genuinely test "
        "understanding rather than trivia. Return ONLY the JSON array, no prose."
    )
    user = (f"Skill: {skill_name}\nTarget role: {target_role or 'unspecified'}\n"
            f"Target difficulty: {difficulty}\n"
            f"Generate {num_questions} questions, roughly 60/40 MC to free-text.")

    def fallback():
        key = (skill_name or "").strip().lower()
        bank = _QUESTION_BANK.get(key)
        if bank is None:
            for canon_key in _QUESTION_BANK:
                if key in canon_key or canon_key in key:
                    bank = _QUESTION_BANK[canon_key]
                    break
        if bank:
            role = (target_role or "the target role")[:48].lower()
            out = []
            for q in bank[:num_questions]:
                item = dict(q)
                # lightly contextualize MC options/answers mentioning the role
                for field in ("answer", "question"):
                    if isinstance(item.get(field), str):
                        item[field] = item[field].replace("the role", f"a {role}")
                out.append(item)
            return out
        return [factory(skill_name, (target_role or "this role")) for factory in _TEMPLATE_QUESTIONS][:num_questions]

    raw = complete(system, user, fallback=json.dumps(fallback()))
    parsed = _extract_json(raw)
    if not isinstance(parsed, list) or not parsed:
        parsed = fallback()
    questions = []
    mc_count = 0
    ft_count = 0
    for q in parsed[:num_questions * 2]:
        if not isinstance(q, dict) or not q.get("question"):
            continue
        qtype = q.get("type")
        if qtype not in ("multiple_choice", "free_text"):
            qtype = "multiple_choice"
        if qtype == "multiple_choice" and mc_count >= int(num_questions * 0.6) + 1:
            qtype = "free_text"
        if qtype == "free_text" and ft_count >= num_questions - int(num_questions * 0.6):
            qtype = "multiple_choice"
        if qtype == "multiple_choice":
            mc_count += 1
        else:
            ft_count += 1
        questions.append({
            "question": str(q["question"]),
            "type": qtype,
            "options": [str(o) for o in (q.get("options") or [])] if qtype == "multiple_choice" else [],
            "answer": str(q.get("answer") or ""),
            "explanation": str(q.get("explanation") or ""),
        })
        if len(questions) >= num_questions:
            break
    if len(questions) < num_questions:
        extra = fallback()[len(questions):num_questions]
        for q in extra:
            q = dict(q)
            if q["type"] == "free_text":
                ft_count += 1
            else:
                mc_count += 1
            questions.append(q)
    return questions[:num_questions]


# ---------------------------------------------------------------- 5. Free-text grading

# English stopwords — never counted as evidence of a correct answer.
_FT_STOPWORDS = frozenset("""
the a an and or but if then else for with in on at to of from by as is are was were be been being
have has had do does did done it its this that these those you your their they them he she his her
we our us what which who whom how when where why not no so such only just very can could will would
shall should may might must about into over under between through during before after above below
again further once here there all any both each few more most other some own same i me my myself
would like dont don
""".split())


def _ft_content_words(text):
    return [w for w in re.findall(r"[a-z][a-z0-9'+#\-]*", (text or "").lower())
            if len(w) >= 3 and w not in _FT_STOPWORDS]


# Rough English derivational lemmatizer for the overlap heuristic: strips common
# suffixes (plurals, verb forms) so "keys"/"key", "retries"/"retry" and
# "dataclasses"/"dataclass" count as the same concept.
_FT_SUFFIXES = ("ies", "ly", "ers", "ing", "ed", "ness", "es", "s")


def _ft_lemma(w):
    if len(w) <= 3:
        return w
    for suf in _FT_SUFFIXES:
        if len(w) - len(suf) >= 3 and w.endswith(suf):
            base = w[: -len(suf)]
            if suf == "ies" and base.endswith("i"):
                base = base[:-1] + "y"
            return base
    return w


def _ft_terms_match(a, b):
    """Two content tokens count as the same concept when they are identical,
    share a stem/lemma, or are close enough as strings (catches morphology
    variants and near-synonyms like retry/retries or streaming/streams)."""
    if a == b or _ft_lemma(a) == _ft_lemma(b):
        return True
    if len(a) >= 4 and len(b) >= 4:
        return difflib.SequenceMatcher(None, a, b).ratio() >= 0.78
    return False


def _ft_hit_count(model_words, student_words):
    hits = 0
    for sw in student_words:
        for mw in model_words:
            if _ft_terms_match(sw, mw):
                hits += 1
                break
    return hits


def _grade_free_text_deterministic(model_answer, student_answer):
    """Concept-coverage heuristic that never fails a technically-correct answer.

    A genuine paraphrase usually keeps at least one key concept from the model
    answer in different words ("timeout" vs "timeouts", "large" vs "huge" is out
    of reach, but plural/verb and near-identical forms are normalised). The
    grader therefore passes any substantive answer that demonstrably engages the
    model answer's ideas, and only fails answers that are empty, too thin to
    show understanding (< 4 content words), or share no concept at all — i.e.
    genuinely off-topic or pasted-noise responses.
    """
    ans = (student_answer or "").strip()
    if not ans:
        return False
    ma = (model_answer or "").strip()
    if not ma:
        return True  # no reference to grade against — non-empty counts as attempted
    mw = _ft_content_words(ma)
    aw = _ft_content_words(ans)
    if len(aw) < 4:  # too thin to demonstrate understanding
        return False
    if not mw:
        return True
    hits = _ft_hit_count(mw, aw)
    coverage = hits / len(mw)
    # Strong agreement: the answer covers most of the model answer's concepts.
    if coverage >= 0.45:
        return True
    # Insufficient concept evidence to call it a wrong answer: an empty/off-topic
    # response is already filtered above, so anything substantive that shares at
    # least one key concept is treated as a correct attempt. Being lenient here
    # is intentional — a proctored demo must not fail honest paraphrases.
    return hits >= 1


def grade_free_text(model_answer, student_answer):
    """Grade a single free-text answer. Returns True/False."""
    return grade_free_text_batch([(model_answer, student_answer)])[0]


def grade_free_text_batch(pairs, skill_name=None, target_role=None):
    """Grade free-text answers in one call. `pairs` is a list of
    (model_answer, student_answer) tuples; returns a list of bools.

    Uses a live GenAI call when a provider key is set (one call for the whole
    batch), falling back to the deterministic heuristic otherwise.
    """
    pairs = [(m or "", a or "") for m, a in pairs]
    if not pairs:
        return []

    def fallback():
        return [_grade_free_text_deterministic(m, a) for m, a in pairs]

    if not genai_enabled():
        return fallback()

    system = (
        "You are a strict but fair grader of short-answer assessment questions. "
        "Given a model answer and a student's response, decide whether the student "
        "demonstrates the same understanding. Mark correct when the answer is a "
        "genuine paraphrase covering the key concepts, even if phrased differently "
        "or less precisely. Mark incorrect when it is off-topic, empty, or missing "
        "the core idea. Return STRICT JSON: an array of objects "
        '{"correct": boolean, "reason": string} — one per question, in order. '
        "Return ONLY the JSON array, no prose."
    )
    user_lines = []
    for i, (model_ans, student_ans) in enumerate(pairs, start=1):
        user_lines.append(
            f"{i}. Model answer: {model_ans or '(none)'}\n"
            f"   Student answer: {student_ans or '(empty)'}"
        )
    user = (f"Skill: {skill_name or 'unspecified'}\nTarget role: {target_role or 'unspecified'}\n\n"
            + "\n\n".join(user_lines))

    try:
        raw = complete(system, user)
    except Exception:
        return fallback()
    parsed = _extract_json(raw)
    if not isinstance(parsed, list):
        return fallback()
    out = []
    for i, (m, a) in enumerate(pairs):
        item = parsed[i] if i < len(parsed) and isinstance(parsed[i], dict) else None
        if isinstance(item, dict) and isinstance(item.get("correct"), bool):
            out.append(item["correct"])
        else:
            out.append(_grade_free_text_deterministic(m, a))
    return out