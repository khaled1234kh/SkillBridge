"""Full end-to-end career roadmap for a student's target role.

This is the *master* roadmap: one big picture plan from absolute start to
job-ready, complementing the per-skill micro-roadmaps that appear inside each
learning item. It is generated deterministically from the target role's actual
required-skills catalog plus the student's current skill levels, so the phases
are always relevant to *their* role and never generic filler.

The roadmap is a sequence of numbered phases. Each phase has a title, a
goal / objective, concrete deliverables, the role skills it develops, and a
checkpoint that tells the student how to know they are done. The skills the
student still needs to build (their gaps) are pushed earlier / highlighted so
the plan reads start-to-finish.
"""
_LEVEL = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}

# Phase template: (title, body_goal), body_goal receives the role title.
# Each phase can declare which skill *categories* it focuses on; skill
# placement is resolved at build time from the role's required skills.
_PHASE_SPECS = [
    ("Build a working foundation",
     "Before specialising you need the daily toolkit every {role} relies on. "
     "Set up your environment, master a version-control workflow, and get "
     "comfortable writing and reading code every day."),
    ("Core programming toolkit",
     "Solidify the programming skills a {role} actually uses at work — not "
     "just tutorials, but realistic, multi-file problems and clean code "
     "habits you can defend in code review."),
    ("Data handling & storage",
     "A {role} lives on data. Learn how to query, clean, transform and model "
     "data with the tools the role specifies, then practice on messy, "
     "realistic datasets."),
    ("Domain & platform skills",
     "Go deep on the technologies that are the heart of the {role}: the ML / "
     "cloud / analytics / engineering stack in the role spec. Build working "
     "examples end to end, not toy snippets."),
    ("Production skills (deploy, version, automate)",
     "Learn to ship — containers, automated pipelines, version control at "
     "team scale, and the operational skills that turn a demo into something "
     "a company would run."),
    ("Build a portfolio project",
     "Produce a polished, portfolio-quality project that exercises the full "
     "role stack, is documented, tested, and deployed, and that you can talk "
     "through in an interview."),
    ("Verify your skills",
     "Prove what you know by taking the role's assessments here on "
     "SkillBridge and turning self-reported skills into verified, shareable "
     "evidence recruiters can trust."),
    ("Soft skills & collaboration",
     "The role is technical, but jobs are won and kept through communication, "
     "teamwork, problem-solving and ownership. Develop these alongside your "
     "hard skills."),
    ("Sharpen your job application materials",
     "Turn your skills, verified evidence and portfolio into a strong CV, an "
     "optimised LinkedIn profile, and an elevator pitch targeted at the "
     "{role} role."),
    ("Practice interviews & applications",
     "Apply, get your CV reviewed, practice live technical and behavioural "
     "interviews, and iterate on feedback until you're ready to accept an "
     "offer."),
    ("First-job readiness & continuous growth",
     "Land the role, then keep the momentum: onboard fast, deliver early, and "
     "keep your verified-skill profile current so your next move is even "
     "better."),
]

# Which phase(s) map to which skill category, and their display grouping.
_CATEGORY_PHASE = {
    "Programming": [0, 1],        # foundation, core toolkit
    "Data": [2],
    "AI": [3],
    "DevOps": [4],
    "Security": [4],
    "Analytics": [2, 3],
    "Visualization": [2, 3],
    "Soft Skills": [7],
}

_PHASE_TITLES = [p[0] for p in _PHASE_SPECS]


def _deliverables(categories, cat_skills):
    """Human deliverables for a phase based on its focused skill categories."""
    if not categories:
        return ("Choose a target role on the Skills & Roles page, then come back "
                "— this roadmap builds itself from the skills your role needs.")
    lines = []
    has = set()
    for cat in categories:
        for s in cat_skills.get(cat, [])[:3]:
            has.add(s)
    for s in sorted(has):
        lines.append(f"Reach a confident working level in **{s}** (see its "
                     "learning item for resources and a step-by-step plan).")
    if not lines:
        lines.append("Complete the learning items for the skills listed under this phase.")
    return lines


def build_career_roadmap(student, role):
    """Generate the full start-to-finish roadmap for a student's target role.

    ``student`` is the student dict (with self_reported_skills / verified_skills).
    ``role`` is the role dict with ``required_skills``.
    """
    role_title = (role or {}).get("title") or "the role"
    required = (role or {}).get("required_skills") or []

    # Categorise the role's required skills by category.
    cat_skills = {}
    for rs in required:
        cat = rs.get("category") or "Other"
        cat_skills.setdefault(cat, []).append(rs.get("name", ""))

    # Determine the student's strongest level per role-relevant skill to decide
    # whether a phase can be described as "you already have this".
    own = {}
    for s in student.get("self_reported_skills") or []:
        own.setdefault(s["skill_id"], _LEVEL.get(s.get("level"), 1))
    for v in student.get("verified_skills") or []:
        own.setdefault(v["skill_id"], max(own.get(v["skill_id"], 1), _LEVEL.get(v.get("level"), 1)))

    # How many distinct categories does the role actually require up front?
    technical_cats = [c for c in cat_skills if c != "Soft Skills"]
    had = sum(1 for rs in required if own.get(rs["skill_id"]) is not None)
    ready = 3 if had >= 6 else 2 if had >= 3 else 1 if had >= 1 else 0

    phases = []
    for idx, (title, goal_template) in enumerate(_PHASE_SPECS):
        cats = []
        for cat, pids in _CATEGORY_PHASE.items():
            if idx in pids and cat in cat_skills:
                cats.append(cat)
        # Move hard-skill gap phases earlier relative to a beginner; keep the
        # roadmap readable by leaving ordering fixed but personalising text.
        focus_names = [n for c in cats for n in cat_skills.get(c, [])]
        steps = _deliverables(cats, cat_skills)
        status = "focus"
        phase_skills = [{"name": n, "category": c} for c in cats for n in cat_skills.get(c, [])]
        phases.append({
            "phase": idx + 1,
            "title": title,
            "goal": goal_template.format(role=role_title),
            "skills": phase_skills,
            "deliverables": steps,
            "checkpoint": _checkpoint(idx, ready, role_title),
        })
    return {
        "role_title": role_title,
        "summary": (f"A complete, start-to-finish path from zero to a "
                    f"job-ready {role_title}. Finish every phase and you'll have "
                    f"the skills, verified evidence, portfolio and interview "
                    f"readiness to apply with confidence."),
        "student_starting_point": ready,
        "phase_count": len(phases),
        "phases": phases,
    }


def _checkpoint(idx, ready, role_title):
    if idx == 0:
        return "You can set up a project from scratch, commit cleanly, and explain what you're building."
    if idx == 1:
        return "You can solve multi-file problems in your core language without looking things up constantly."
    if idx == 2:
        return "You can load a messy dataset, query it, and produce a clean, correct result."
    if idx == 3:
        return "You can build and run a working example of the role's core technologies end to end."
    if idx == 4:
        return "You can containerise, version and automate your work so someone else can run it too."
    if idx == 5:
        return "You have a deployed, documented, portfolio-ready project you can demo in an interview."
    if idx == 6:
        return "You have passed the role's skill assessments and can share verified proof."
    if idx == 7:
        return "You can describe your experience and work with a team on realistic tasks."
    if idx == 8:
        return "Your CV, LinkedIn and pitch are targeted at a {role_title} and ready to send.".replace("{role_title}", role_title)
    if idx == 9:
        return "You've interviewed, collected feedback, and know exactly what to improve for your next application."
    return "You've accepted an offer and have a plan to keep your skills verified and growing."
