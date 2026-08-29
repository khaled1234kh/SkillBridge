"""Data access layer — CRUD for the five record types plus supporting lookups.

Pure functions over sqlite3 Row dictionaries. Kept free of framework imports so
they can be unit tested in isolation.
"""
from .database import get_cursor

LEVEL_ORDER = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}
VALID_LEVELS = set(LEVEL_ORDER)


def _row(r):
    return dict(r) if r is not None else None


# ---------------------------------------------------------------- skills

def list_skills():
    with get_cursor() as c:
        rows = c.execute("SELECT * FROM skills ORDER BY name").fetchall()
        return [_row(r) for r in rows]


def get_skill(skill_id):
    with get_cursor() as c:
        return _row(c.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone())


def get_skill_by_name(name):
    with get_cursor() as c:
        return _row(c.execute("SELECT * FROM skills WHERE name=?", (name,)).fetchone())


def create_skill(name, category):
    with get_cursor() as c:
        cur = c.execute("INSERT INTO skills (name, category) VALUES (?,?)", (name, category))
        return get_skill(cur.lastrowid)


def get_or_create_skill(name, category):
    existing = get_skill_by_name(name)
    if existing:
        return existing
    return create_skill(name, category)


def update_skill(skill_id, name=None, category=None):
    with get_cursor() as c:
        cur = c.execute("UPDATE skills SET name=COALESCE(?,name), category=COALESCE(?,category) WHERE id=?",
                        (name, category, skill_id))
        return cur.rowcount


def delete_skill(skill_id):
    with get_cursor() as c:
        cur = c.execute("DELETE FROM skills WHERE id=?", (skill_id,))
        return cur.rowcount


# ---------------------------------------------------------------- companies

def list_companies():
    with get_cursor() as c:
        return [_row(r) for r in c.execute("SELECT * FROM companies ORDER BY name").fetchall()]


def get_company(company_id):
    with get_cursor() as c:
        return _row(c.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone())


def get_company_by_user(user_id):
    with get_cursor() as c:
        return _row(c.execute("SELECT * FROM companies WHERE user_id=?", (user_id,)).fetchone())


def create_company(name, industry, user_id=None):
    with get_cursor() as c:
        cur = c.execute("INSERT INTO companies (name, industry, user_id) VALUES (?,?,?)",
                        (name, industry, user_id))
        return get_company(cur.lastrowid)


def update_company(company_id, name=None, industry=None):
    with get_cursor() as c:
        cur = c.execute("UPDATE companies SET name=COALESCE(?,name), industry=COALESCE(?,industry) WHERE id=?",
                        (name, industry, company_id))
        return cur.rowcount


def delete_company(company_id):
    with get_cursor() as c:
        c.execute("DELETE FROM companies WHERE id=?", (company_id,))
    return 1


# ---------------------------------------------------------------- roles

def list_roles():
    with get_cursor() as c:
        rows = c.execute("""SELECT r.*, c.name AS company_name
                            FROM roles r JOIN companies c ON c.id=r.company_id
                            ORDER BY r.title""").fetchall()
        out = []
        for r in rows:
            rd = _row(r)
            rd["required_skills"] = role_skills(c, r["id"])
            out.append(rd)
        return out


def role_skills(cur, role_id):
    return [_row(r) for r in cur.execute("""
        SELECT rs.required_level, s.id AS skill_id, s.name, s.category
        FROM role_skills rs JOIN skills s ON s.id=rs.skill_id
        WHERE rs.role_id=? ORDER BY s.name""", (role_id,)).fetchall()]


def get_role(role_id):
    with get_cursor() as c:
        r = c.execute("""SELECT r.*, c.name AS company_name
                         FROM roles r JOIN companies c ON c.id=r.company_id
                         WHERE r.id=?""", (role_id,)).fetchone()
        if not r:
            return None
        rd = _row(r)
        rd["required_skills"] = role_skills(c, role_id)
        return rd


def get_roles_by_company(company_id):
    with get_cursor() as c:
        rows = c.execute("SELECT * FROM roles WHERE company_id=?", (company_id,)).fetchall()
        out = []
        for r in rows:
            rd = _row(r)
            rd["required_skills"] = role_skills(c, r["id"])
            out.append(rd)
        return out


def create_role(company_id, title, required_skills, description=None):
    """required_skills: list of {name, category, level}."""
    with get_cursor() as c:
        cur = c.execute("INSERT INTO roles (company_id, title, description) VALUES (?,?,?)",
                        (company_id, title, description))
        role_id = cur.lastrowid
        for rs in required_skills:
            sk = get_or_create_skill(rs["name"], rs.get("category", "General"))
            c.execute("INSERT INTO role_skills (role_id, skill_id, required_level) VALUES (?,?,?)",
                      (role_id, sk["id"], rs["level"]))
        return get_role(role_id)


def update_role(role_id, title=None, description=None, required_skills=None):
    with get_cursor() as c:
        c.execute("UPDATE roles SET title=COALESCE(?,title), description=COALESCE(?,description) WHERE id=?",
                  (title, description, role_id))
        if required_skills is not None:
            c.execute("DELETE FROM role_skills WHERE role_id=?", (role_id,))
            for rs in required_skills:
                sk = get_or_create_skill(rs["name"], rs.get("category", "General"))
                c.execute("INSERT INTO role_skills (role_id, skill_id, required_level) VALUES (?,?,?)",
                          (role_id, sk["id"], rs["level"]))
        return get_role(role_id)


def delete_role(role_id):
    with get_cursor() as c:
        c.execute("DELETE FROM roles WHERE id=?", (role_id,))
        # clear students' target roles pointing here
        c.execute("UPDATE students SET target_role_id=NULL WHERE target_role_id=?", (role_id,))
    return 1


# ---------------------------------------------------------------- students

def list_students():
    with get_cursor() as c:
        return [_row(r) for r in c.execute("SELECT * FROM students ORDER BY name").fetchall()]


def get_student(student_id):
    with get_cursor() as c:
        r = c.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        if not r:
            return None
        sd = _row(r)
        sd["self_reported_skills"] = student_self_reported(c, student_id)
        sd["verified_skills"] = student_verified(c, student_id)
        if sd.get("target_role_id"):
            sd["target_role"] = role_from_id(c, sd["target_role_id"])
        return sd


def get_student_by_user(user_id):
    with get_cursor() as c:
        r = c.execute("SELECT * FROM students WHERE user_id=?", (user_id,)).fetchone()
        if not r:
            return None
        return get_student(r["id"])


def student_self_reported(cur, student_id):
    return [_row(r) for r in cur.execute("""
        SELECT s.id AS skill_id, s.name, s.category, sr.level, sr.source
        FROM self_reported_skills sr JOIN skills s ON s.id=sr.skill_id
        WHERE sr.student_id=? ORDER BY s.name""", (student_id,)).fetchall()]


def student_verified(cur, student_id):
    return [_row(r) for r in cur.execute("""
        SELECT s.id AS skill_id, s.name, s.category, v.level, v.verified_at
        FROM verified_skills v JOIN skills s ON s.id=v.skill_id
        WHERE v.student_id=? ORDER BY s.name""", (student_id,)).fetchall()]


def role_from_id(cur, role_id):
    r = cur.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
    if not r:
        return None
    rd = _row(r)
    rd["required_skills"] = role_skills(cur, role_id)
    return rd


def create_student(name, email, university, user_id=None):
    with get_cursor() as c:
        cur = c.execute("INSERT INTO students (name, email, university, user_id) VALUES (?,?,?,?)",
                        (name, email, university, user_id))
        return get_student(cur.lastrowid)


def update_student(student_id, **fields):
    allowed = {"name", "email", "university", "target_role_id", "cv_filename"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return get_student(student_id)
    vals.append(student_id)
    with get_cursor() as c:
        c.execute(f"UPDATE students SET {', '.join(sets)} WHERE id=?", vals)
        return get_student(student_id)


def delete_student(student_id):
    with get_cursor() as c:
        c.execute("DELETE FROM students WHERE id=?", (student_id,))
    return 1


def replace_self_reported_skills(student_id, skills):
    """skills: list of {name, level} — replaces the student's full self-reported set."""
    with get_cursor() as c:
        c.execute("DELETE FROM self_reported_skills WHERE student_id=?", (student_id,))
        for s in skills:
            sk = get_or_create_skill(s["name"], s.get("category", "General"))
            c.execute("INSERT INTO self_reported_skills (student_id, skill_id, level, source) VALUES (?,?,?,?)",
                      (student_id, sk["id"], s["level"], s.get("source", "cv")))
        return get_student(student_id)


def update_verified_skill(student_id, skill_id, level):
    with get_cursor() as c:
        c.execute("""INSERT INTO verified_skills (student_id, skill_id, level, verified_at)
                     VALUES (?,?,?, datetime('now'))
                     ON CONFLICT(student_id, skill_id) DO UPDATE SET level=excluded.level, verified_at=datetime('now')""",
                  (student_id, skill_id, level))
        return get_student(student_id)


# ---------------------------------------------------------------- learning

def list_learning_path(student_id):
    with get_cursor() as c:
        return [_row(r) for r in c.execute("""
            SELECT l.id, l.student_id, l.skill_id, s.name AS skill_name, s.category,
                   l.explanation, l.practice_exercise, l.mini_project, l.generated_at
            FROM learning_path_items l JOIN skills s ON s.id=l.skill_id
            WHERE l.student_id=? ORDER BY s.name""", (student_id,)).fetchall()]


def get_learning_item(student_id, skill_id):
    with get_cursor() as c:
        return _row(c.execute("""
            SELECT l.id, l.student_id, l.skill_id, s.name AS skill_name, s.category,
                   l.explanation, l.practice_exercise, l.mini_project, l.generated_at
            FROM learning_path_items l JOIN skills s ON s.id=l.skill_id
            WHERE l.student_id=? AND l.skill_id=?""", (student_id, skill_id)).fetchone())


def upsert_learning_item(student_id, skill_id, explanation, practice_exercise, mini_project):
    with get_cursor() as c:
        c.execute("""INSERT INTO learning_path_items (student_id, skill_id, explanation, practice_exercise, mini_project)
                     VALUES (?,?,?,?,?)
                     ON CONFLICT(student_id, skill_id) DO UPDATE SET
                       explanation=excluded.explanation,
                       practice_exercise=excluded.practice_exercise,
                       mini_project=excluded.mini_project,
                       generated_at=datetime('now')""",
                  (student_id, skill_id, explanation, practice_exercise, mini_project))
        return get_learning_item(student_id, skill_id)


# ---------------------------------------------------------------- tutor

def add_tutor_message(student_id, skill_id, role, content):
    with get_cursor() as c:
        cur = c.execute("INSERT INTO tutor_messages (student_id, skill_id, role, content) VALUES (?,?,?,?)",
                        (student_id, skill_id, role, content))
        return _row(c.execute("SELECT * FROM tutor_messages WHERE id=?", (cur.lastrowid,)).fetchone())


def list_tutor_messages(student_id, skill_id=None):
    with get_cursor() as c:
        if skill_id:
            rows = c.execute("SELECT * FROM tutor_messages WHERE student_id=? AND skill_id=? ORDER BY id",
                             (student_id, skill_id)).fetchall()
        else:
            rows = c.execute("SELECT * FROM tutor_messages WHERE student_id=? ORDER BY id", (student_id,)).fetchall()
        return [_row(r) for r in rows]


# ---------------------------------------------------------------- assessments

def create_assessment_attempt(student_id, skill_id, questions, answers, score, passed,
                              flags, level_before, level_after):
    with get_cursor() as c:
        cur = c.execute("""INSERT INTO assessment_attempts
                           (student_id, skill_id, questions, answers, score, passed, flags, level_before, level_after)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (student_id, skill_id, questions, answers, score, passed, flags,
                         level_before, level_after))
        return get_assessment_attempt(cur.lastrowid)


def get_assessment_attempt(attempt_id):
    with get_cursor() as c:
        return _row(c.execute("""SELECT a.*, s.name AS skill_name
                                 FROM assessment_attempts a JOIN skills s ON s.id=a.skill_id
                                 WHERE a.id=?""", (attempt_id,)).fetchone())


def list_assessment_attempts(student_id=None, skill_id=None):
    with get_cursor() as c:
        q = "SELECT a.*, s.name AS skill_name FROM assessment_attempts a JOIN skills s ON s.id=a.skill_id"
        clauses, vals = [], []
        if student_id:
            clauses.append("a.student_id=?")
            vals.append(student_id)
        if skill_id:
            clauses.append("a.skill_id=?")
            vals.append(skill_id)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY a.id DESC"
        return [_row(r) for r in c.execute(q, vals).fetchall()]


def delete_assessment_attempt(attempt_id):
    with get_cursor() as c:
        c.execute("DELETE FROM assessment_attempts WHERE id=?", (attempt_id,))
    return 1


# ---------------------------------------------------------------- users / auth

def create_user(email, password, role, display_name):
    with get_cursor() as c:
        cur = c.execute("INSERT INTO users (email, password, role, display_name) VALUES (?,?,?,?)",
                        (email, password, role, display_name))
        return _row(c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone())


def get_user_by_email(email):
    with get_cursor() as c:
        return _row(c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())


def get_user(user_id):
    with get_cursor() as c:
        return _row(c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
