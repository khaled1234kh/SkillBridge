"""Seed the database with realistic sample data so the app looks alive on first launch.

Creates users for all three roles, several students, companies with defined roles,
a shared skill list, self-reported skill profiles, a curated reference "talent
catalog" of realistic roles, a few completed assessment attempts, and
pre-generated learning content.
"""
from . import models, genai, matching
from .database import init_db, get_cursor

USERS = [
    # (email, role, display_name, password)
    ("aisha@student.edu", "Student", "Aisha Rahman", "demo1234"),
    ("omar@student.edu", "Student", "Omar Haddad", "demo1234"),
    ("leila@student.edu", "Student", "Leila Chen", "demo1234"),
    ("marcus@student.edu", "Student", "Marcus Torres", "demo1234"),
    ("priya@student.edu", "Student", "Priya Nair", "demo1234"),
    ("sara@student.edu", "Student", "Sara Kovač", "demo1234"),
    ("tomas@student.edu", "Student", "Tomas Lindqvist", "demo1234"),
    ("hr@northstar.com", "Company", "Northstar Labs", "demo1234"),
    ("hr@signal.com", "Company", "Signal Works", "demo1234"),
    ("admin@univ.edu", "University Admin", "University Analytics", "demo1234"),
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

# Internal company-defined roles (companies manage these themselves).
INTERNAL_ROLES = [
    ("hr@northstar.com", "Junior AI Engineer",
     "Build and deploy ML models and pipelines for real product features.",
     [("Python", "Advanced", "Programming"), ("Machine Learning", "Intermediate", "AI"),
      ("Docker", "Intermediate", "DevOps"), ("SQL", "Advanced", "Data")],
     "role-ai"),
    ("hr@northstar.com", "Data Engineer",
     "Own the data pipelines and infrastructure that power analytics.",
     [("Python", "Advanced", "Programming"), ("SQL", "Advanced", "Data"),
      ("Docker", "Intermediate", "DevOps"), ("Git", "Intermediate", "DevOps")],
     "role-dataeng"),
    ("hr@signal.com", "Data Analyst",
     "Turn raw data into insight and dashboards that drive decisions.",
     [("SQL", "Advanced", "Data"), ("Excel", "Advanced", "Analytics"),
      ("Python", "Intermediate", "Programming"), ("Tableau", "Intermediate", "Visualization")],
     "role-data"),
]

# Reference catalog roles (read-only baseline from the SkillBridge Talent Catalog).
# Complete 8-14 skill lists per track so students get realistic, substantial gaps.
CATALOG_ROLES = [
    ("Junior AI Engineer",
     "Build, deploy, and maintain machine-learning features end to end.",
     [("Python", "Advanced", "Programming"), ("Machine Learning", "Intermediate", "AI"),
      ("Deep Learning", "Beginner", "AI"), ("SQL", "Advanced", "Data"),
      ("Statistics", "Intermediate", "Data"), ("Pandas", "Intermediate", "Data"),
      ("scikit-learn", "Intermediate", "AI"), ("Docker", "Intermediate", "DevOps"),
      ("Git", "Intermediate", "DevOps"), ("REST APIs", "Intermediate", "DevOps"),
      ("Communication", "Beginner", "Soft Skills"), ("Teamwork", "Beginner", "Soft Skills")]),
    ("Data Engineer",
     "Design and operate the pipelines, storage, and infrastructure behind analytics.",
     [("Python", "Advanced", "Programming"), ("SQL", "Advanced", "Data"),
      ("Docker", "Intermediate", "DevOps"), ("Data Engineering", "Intermediate", "Data"),
      ("ETL", "Intermediate", "Data"), ("Airflow", "Beginner", "Data"),
      ("Spark", "Beginner", "Data"), ("Cloud Security", "Beginner", "Security"),
      ("Git", "Intermediate", "DevOps"), ("CI/CD", "Intermediate", "DevOps"),
      ("Communication", "Beginner", "Soft Skills"), ("Problem Solving", "Intermediate", "Soft Skills")]),
    ("Data Analyst",
     "Transform raw data into decisions, dashboards, and stories for stakeholders.",
     [("SQL", "Advanced", "Data"), ("Excel", "Advanced", "Analytics"),
      ("Python", "Intermediate", "Programming"), ("Pandas", "Intermediate", "Data"),
      ("Tableau", "Intermediate", "Visualization"), ("Data Visualization", "Intermediate", "Visualization"),
      ("Statistics", "Intermediate", "Data"), ("Data Analysis", "Intermediate", "Data"),
      ("Data Storytelling", "Beginner", "Analytics"), ("Business Intelligence", "Beginner", "Analytics"),
      ("Communication", "Intermediate", "Soft Skills"), ("Critical Thinking", "Intermediate", "Soft Skills")]),
    ("Cloud Security Engineer",
     "Secure cloud workloads and respond to threats across the infrastructure.",
     [("Cybersecurity", "Intermediate", "Security"), ("Cloud Security", "Intermediate", "Security"),
      ("AWS", "Intermediate", "DevOps"), ("Linux", "Intermediate", "DevOps"),
      ("Network Security", "Intermediate", "Security"), ("Threat Detection", "Beginner", "Security"),
      ("Incident Response", "Beginner", "Security"), ("Vulnerability Management", "Intermediate", "Security"),
      ("Risk Assessment", "Intermediate", "Security"), ("Python", "Beginner", "Programming"),
      ("Communication", "Intermediate", "Soft Skills"), ("Critical Thinking", "Advanced", "Soft Skills")]),
    ("Financial Data Analyst",
     "Analyze financial data and build models that inform investment decisions.",
     [("Excel", "Advanced", "Analytics"), ("SQL", "Advanced", "Data"),
      ("Statistics", "Advanced", "Data"), ("Python", "Intermediate", "Programming"),
      ("Pandas", "Intermediate", "Data"), ("Data Visualization", "Intermediate", "Visualization"),
      ("Power BI", "Intermediate", "Visualization"), ("Business Intelligence", "Intermediate", "Analytics"),
      ("Risk Assessment", "Intermediate", "Security"), ("A/B Testing", "Intermediate", "Analytics"),
      ("Communication", "Intermediate", "Soft Skills"), ("Time Management", "Beginner", "Soft Skills")]),
]

# Completed assessment attempts for richer seed data.
ATTEMPTS = [
    ("aisha@student.edu", "Python", 92, True, "Advanced", "Advanced", 0),
    ("aisha@student.edu", "SQL", 88, True, "Advanced", "Advanced", 0),
    ("leila@student.edu", "SQL", 90, True, "Advanced", "Advanced", 0),
    ("leila@student.edu", "Excel", 84, True, "Advanced", "Advanced", 0),
    ("sara@student.edu", "Python", 95, True, "Advanced", "Advanced", 1),
    ("omar@student.edu", "Python", 45, False, "Intermediate", "Intermediate", 1),
]


UNIVERSITIES = [
    # ("Country", ["universities", ...])
    ("United Kingdom", ["Aston University", "University of Birmingham", "Imperial College London",
                        "University of Oxford", "University of Cambridge", "University of Manchester",
                        "King's College London", "University of Edinburgh"]),
    ("United States", ["Arizona State University", "Georgia Institute of Technology", "MIT",
                       "Stanford University", "University of California, Berkeley", "Carnegie Mellon University",
                       "University of Texas at Austin", "University of Washington"]),
    ("United Arab Emirates", ["Khalifa University", "American University of Sharjah", "United Arab Emirates University",
                             "University of Sharjah", "Zayed University", "Abu Dhabi University"]),
    ("Saudi Arabia", ["King Fahd University of Petroleum and Minerals", "King Abdulaziz University",
                      "King Saud University", "KAUST", "Prince Sultan University", "Effat University"]),
    ("Egypt", ["Cairo University", "Ain Shams University", "Alexandria University", "Nile University",
               "American University in Cairo", "German University in Cairo", "Future University in Egypt",
               "Helwan University", "Misr International University"]),
    ("India", ["Indian Institute of Technology (IIT), Bombay", "Indian Institute of Technology (IIT), Delhi",
               "Birla Institute of Technology and Science (BITS) Pilani", "VIT Vellore",
               "National Institute of Technology (NIT) Trichy", "Delhi University"]),
    ("Germany", ["Technical University of Munich", "RWTH Aachen", "University of Stuttgart",
                 "KIT Karlsruhe", "LMU Munich", "Humboldt University of Berlin"]),
    ("Canada", ["University of Toronto", "University of Waterloo", "University of British Columbia",
                "McGill University", "University of Alberta", "Simon Fraser University"]),
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


def _category(name):
    return genai.FALLBACK_SKILL_CATEGORIES.get(name, "General")


def seed():
    init_db()
    with get_cursor() as c:
        c.executescript("""
            DELETE FROM google_registrations; DELETE FROM password_resets;
            DELETE FROM email_verifications;
            DELETE FROM sessions; DELETE FROM assessment_attempts; DELETE FROM tutor_messages;
            DELETE FROM learning_path_items; DELETE FROM verified_skills;
            DELETE FROM self_reported_skills; DELETE FROM role_skills;
            DELETE FROM roles; DELETE FROM students; DELETE FROM companies;
            DELETE FROM skills; DELETE FROM users;
        """)

    # users (password hashed via the new create_user signature).
    # Seed/demo accounts are pre-verified so the app works on first launch.
    # Every account carries a location so the live roles feed is demoable.
    USER_META = {
        "aisha@student.edu": ("United Kingdom", "Birmingham"),
        "omar@student.edu": ("United Kingdom", "Birmingham"),
        "leila@student.edu": ("United Kingdom", "Birmingham"),
        "marcus@student.edu": ("United Kingdom", "Birmingham"),
        "priya@student.edu": ("United Kingdom", "Birmingham"),
        "sara@student.edu": ("United Kingdom", "Birmingham"),
        "tomas@student.edu": ("United Kingdom", "Birmingham"),
        "hr@northstar.com": ("United Kingdom", "Birmingham"),
        "hr@signal.com": ("United Kingdom", "London"),
        "admin@univ.edu": ("United Kingdom", "Birmingham"),
    }
    for email, role, display, password in USERS:
        country, location = USER_META.get(email, ("", ""))
        models.create_user(email, role, display, password=password, verified=1,
                           country=country, location=location)

    # reference country + university list (used by the cascading signup dropdown)
    with get_cursor() as c:
        c.execute("DELETE FROM universities")
    for country, unis in UNIVERSITIES:
        for uni in unis:
            models.add_university(country, uni)

    # companies
    company_ids = {}
    companies = [
        ("hr@northstar.com", "Northstar Labs", "AI / Software", "Birmingham"),
        ("hr@signal.com", "Signal Works", "Data & Analytics", "London"),
        ("catalog@skillbridge.io", "SkillBridge Talent Catalog", "Reference", ""),
    ]
    for email, name, industry, location in companies:
        u = (models.get_user_by_email(email) if not email.startswith("catalog")
             else {"id": None})
        comp = models.create_company(name, industry, user_id=u["id"], location=location)
        company_ids[email] = comp["id"]

    # internal roles
    role_ids = {}
    for email, title, desc, skills, key in INTERNAL_ROLES:
        role = models.create_role(company_ids[email], title, [
            {"name": n, "level": lvl, "category": cat} for (n, lvl, cat) in skills
        ], description=desc)
        role_ids[key] = role["id"]

    # reference catalog roles
    catalog_company_id = company_ids["catalog@skillbridge.io"]
    for title, desc, skills in CATALOG_ROLES:
        models.create_role(catalog_company_id, title, [
            {"name": n, "level": lvl, "category": cat} for (n, lvl, cat) in skills
        ], description=desc, is_reference=1)

    # students (with cohort confirmed for the university view)
    student_ids = {}
    for email, name, uni, role_key in STUDENTS:
        u = models.get_user_by_email(email)
        sid = models.create_student(name, email, uni, user_id=u["id"])["id"]
        models.update_student(sid, target_role_id=role_ids[role_key], cohort_confirmed=1)
        student_ids[email] = sid

    # self-reported + verified skills
    for email, skills in SELF_REPORTED.items():
        models.replace_self_reported_skills(student_ids[email], [
            {"name": n, "level": lvl, "category": _category(n)}
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
                                    item["practice_exercise"], item["mini_project"],
                                    item.get("resources") or [], item.get("roadmap") or None)


if __name__ == "__main__":
    seed()
    print("Seed complete.")