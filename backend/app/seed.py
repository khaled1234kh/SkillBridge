"""Seed the database with realistic sample data so the app looks alive on first launch.

Creates users for all three roles, several students, 2-3 companies with defined roles,
a shared skill list, self-reported skill profiles, a few completed assessment attempts,
and pre-generated learning content.
"""
from . import models, genai, matching
from .database import init_db, get_cursor

USERS = [
    # (email, password, role, display_name)
    ("aisha@student.edu", "demo1234", "Student", "Aisha Rahman"),
    ("omar@student.edu", "demo1234", "Student", "Omar Haddad"),
    ("leila@student.edu", "demo1234", "Student", "Leila Chen"),
    ("marcus@student.edu", "demo1234", "Student", "Marcus Torres"),
    ("priya@student.edu", "demo1234", "Student", "Priya Nair"),
    ("sara@student.edu", "demo1234", "Student", "Sara Kovač"),
    ("tomas@student.edu", "demo1234", "Student", "Tomas Lindqvist"),
    ("hr@northstar.com", "demo1234", "Company", "Northstar Labs"),
    ("hr@signal.com", "demo1234", "Company", "Signal Works"),
    ("admin@univ.edu", "demo1234", "University Admin", "University Analytics"),
]

STUDENTS = [
    ("aisha@student.edu", "Aisha Rahman", "Aston University", "role-ai"),
    ("omar@student.edu", "Omar Haddad", "Aston University", "role-ai"),
    ("leila@student.edu", "Leila Chen", "Aston University", "role-data"),
    ("marcus@student.edu", "Marcus Torres", "Aston University", "role-ai"),
    ("priya@student.edu", "Priya Nair", "Aston University", "role-data"),
    ("sara@student.edu", "Sara Kovač", "Aston University", "role-ai"),
    ("tomas@student.edu", "Tomas Lindqvist", "Aston University", "role-data"),
]

# Self-reported profile per student: list of (skill_name, level)
SELF_REPORTED = {
    "aisha@student.edu": [("Python", "Advanced"), ("Machine Learning", "Intermediate"),
                          ("Docker", "Beginner"), ("SQL", "Advanced"), ("Git", "Intermediate")],
    "omar@student.edu": [("Python", "Intermediate"), ("Machine Learning", "Beginner"),
                         ("Docker", "Beginner"), ("SQL", "Beginner")],
    "leila@student.edu": [("SQL", "Advanced"), ("Excel", "Advanced"), ("Python", "Intermediate"),
                          ("Tableau", "Intermediate")],
    "marcus@student.edu": [("Python", "Intermediate"), ("SQL", "Intermediate"),
                           ("Machine Learning", "Beginner"), ("Docker", "Beginner")],
    "priya@student.edu": [("SQL", "Intermediate"), ("Excel", "Intermediate"),
                          ("Python", "Beginner"), ("Tableau", "Beginner")],
    "sara@student.edu": [("Python", "Advanced"), ("Git", "Intermediate"), ("Docker", "Beginner"),
                         ("Machine Learning", "Intermediate"), ("SQL", "Intermediate")],
    "tomas@student.edu": [("SQL", "Beginner"), ("Excel", "Intermediate"), ("Python", "Beginner")],
}

# Some students already have verified skills from prior assessments.
VERIFIED = {
    "aisha@student.edu": [("Python", "Advanced"), ("SQL", "Advanced")],
    "leila@student.edu": [("SQL", "Advanced"), ("Excel", "Advanced")],
}

ROLES = [
    ("company-northstar", "Junior AI Engineer",
     "Build and deploy ML models and pipelines for real product features.",
     [("Python", "Advanced", "Programming"), ("Machine Learning", "Intermediate", "AI"),
      ("Docker", "Intermediate", "DevOps"), ("SQL", "Advanced", "Data")],
     "role-ai"),
    ("company-northstar", "Data Engineer",
     "Own the data pipelines and infrastructure that power analytics.",
     [("Python", "Advanced", "Programming"), ("SQL", "Advanced", "Data"),
      ("Docker", "Intermediate", "DevOps"), ("Git", "Intermediate", "DevOps")],
     "role-dataeng"),
    ("company-signal", "Data Analyst",
     "Turn raw data into insight and dashboards that drive decisions.",
     [("SQL", "Advanced", "Data"), ("Excel", "Advanced", "Analytics"),
      ("Python", "Intermediate", "Programming"), ("Tableau", "Intermediate", "Visualization")],
     "role-data"),
]

# Completed assessment attempts for richer seed data: (student_email, skill_name, score, passed, level_before, level_after, flags_count)
ATTEMPTS = [
    ("aisha@student.edu", "Python", 92, True, "Advanced", "Advanced", 0),
    ("aisha@student.edu", "SQL", 88, True, "Advanced", "Advanced", 0),
    ("leila@student.edu", "SQL", 90, True, "Advanced", "Advanced", 0),
    ("leila@student.edu", "Excel", 84, True, "Advanced", "Advanced", 0),
    ("sara@student.edu", "Python", 95, True, "Advanced", "Advanced", 1),
    ("omar@student.edu", "Python", 45, False, "Intermediate", "Intermediate", 1),
]


def _sample_cv(name, email, university, skills):
    lines = [
        f"{name}\n{email} | {university}",
        "EDUCATION", f"BSc Computer Science, {university}, expected 2027",
        "KEY SKILLS",
    ]
    lines.append(", ".join(f"{s} ({lvl})" for s, lvl in skills))
    lines += ["PROJECTS",
              "Built a data analysis dashboard for a coursework project.",
              "Worked on a team project applying machine learning methods to a real dataset.",
              "EXPERIENCE", "Internship contributing to software and data workflows."]
    return "\n".join(lines)


def seed():
    init_db()
    with get_cursor() as c:
        c.executescript("""
            DELETE FROM assessment_attempts; DELETE FROM tutor_messages;
            DELETE FROM learning_path_items; DELETE FROM verified_skills;
            DELETE FROM self_reported_skills; DELETE FROM role_skills;
            DELETE FROM roles; DELETE FROM students; DELETE FROM companies;
            DELETE FROM skills; DELETE FROM users;
        """)

    # companies + users
    company_ids = {}
    for email, pw, role, display in USERS:
        models.create_user(email, pw, role, display)
    companies = [
        ("hr@northstar.com", "Northstar Labs", "AI / Software"),
        ("hr@signal.com", "Signal Works", "Data & Analytics"),
    ]
    for email, name, industry in companies:
        u = models.get_user_by_email(email)
        comp = models.create_company(name, industry, user_id=u["id"])
        company_ids[email] = comp["id"]

    # roles
    role_ids = {}
    company_email_map = {
        "company-northstar": "hr@northstar.com",
        "company-signal": "hr@signal.com",
    }
    for company_key, title, desc, skills, key in ROLES:
        cid = company_ids[company_email_map[company_key]]
        role = models.create_role(cid, title, [
            {"name": n, "level": lvl, "category": cat} for (n, lvl, cat) in skills
        ], description=desc)
        role_ids[key] = role["id"]

    # students
    student_ids = {}
    for email, name, uni, role_key in STUDENTS:
        u = models.get_user_by_email(email)
        sid = models.create_student(name, email, uni, user_id=u["id"])["id"]
        models.update_student(sid, target_role_id=role_ids[role_key])
        student_ids[email] = sid

    # self-reported + verified skills
    for email, skills in SELF_REPORTED.items():
        models.replace_self_reported_skills(student_ids[email], [
            {"name": n, "level": lvl, "category": genai.FALLBACK_SKILL_CATEGORIES.get(n, "General")}
            for (n, lvl) in skills
        ])
    for email, skills in VERIFIED.items():
        for (n, lvl) in skills:
            sk = models.get_skill_by_name(n)
            models.update_verified_skill(student_ids[email], sk["id"], lvl)

    # pre-generate learning content for each student's current gaps (uses real GenAI if available)
    for email, sid in student_ids.items():
        _pregen_learning(sid)

    # completed assessment attempts
    for email, skill_name, score, passed, before, after, nflags in ATTEMPTS:
        sk = models.get_skill_by_name(skill_name)
        questions = genai.generate_quiz(skill_name, "seed", num_questions=3)
        flags = []
        for i in range(nflags):
            flags.append({"code": "tab_switch", "label": "Tab switch detected", "severity": "warning",
                          "detail": "Assessment window lost focus.", "seed": True})
        models.create_assessment_attempt(
            student_ids[email], sk["id"], question_json(questions), "[]",
            score, int(passed), flag_json(flags), before, after)
        # ensure verified profile consistent with passed attempts
        if passed and score >= 70:
            models.update_verified_skill(student_ids[email], sk["id"], after)


def question_json(questions):
    import json
    return json.dumps(questions)


def flag_json(flags):
    import json
    return json.dumps(flags)


def _pregen_learning(sid):
    student = models.get_student(sid)
    role = student.get("target_role")
    if not role:
        return
    gaps = matching.gap_skills(student, role)
    ctx = f"Studying at {student['university']}; focused on becoming a {role['title']}."
    for g in gaps:
        item = genai.generate_learning_item(g["skill_name"], g.get("category"), role["title"], ctx)
        models.upsert_learning_item(sid, g["skill_id"], item["explanation"],
                                    item["practice_exercise"], item["mini_project"])


if __name__ == "__main__":
    seed()
    print("Seed complete.")
