"""Data access layer — CRUD for the five record types plus supporting lookups.

Pure functions over sqlite3 Row dictionaries. Kept free of framework imports so
they can be unit tested in isolation.
"""
from .database import get_cursor

LEVEL_ORDER = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}
VALID_LEVELS = set(LEVEL_ORDER)


def _row(r):
    return dict(r) if r is not None else None


def _safe_user(r):
    """Strip plaintext password column from a user row before it leaks to any caller."""
    d = dict(r) if r is not None else None
    if d and "password" in d:
        del d["password"]
    return d


# ---------------------------------------------------------------- skills

def list_skills():
    with get_cursor() as c:
        rows = c.execute("SELECT * FROM skills ORDER BY name").fetchall()
        return [_row(r) for r in rows]


def _json_loads(value):
    if not value:
        return None
    import json
    try:
        return json.loads(value)
    except Exception:
        return None


def _json_dumps(value):
    if value is None:
        return None
    import json
    return json.dumps(value)


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


def create_company(name, industry, user_id=None, location=None):
    with get_cursor() as c:
        cur = c.execute("INSERT INTO companies (name, industry, location, user_id) VALUES (?,?,?,?)",
                        (name, industry, location, user_id))
        return get_company(cur.lastrowid)


def update_company(company_id, name=None, industry=None, location=None):
    with get_cursor() as c:
        cur = c.execute("UPDATE companies SET name=COALESCE(?,name), industry=COALESCE(?,industry), location=COALESCE(?,location) WHERE id=?",
                        (name, industry, location, company_id))
        return cur.rowcount


def delete_company(company_id):
    with get_cursor() as c:
        c.execute("DELETE FROM companies WHERE id=?", (company_id,))
    return 1


# ---------------------------------------------------------------- roles

def list_roles(company_id=None):
    with get_cursor() as c:
        q = """SELECT r.*, c.name AS company_name, c.location AS company_location
               FROM roles r JOIN companies c ON c.id=r.company_id"""
        if company_id is not None:
            q += " WHERE r.company_id=?"
        if company_id is None:
            q += " WHERE r.is_reference=0"
        q += " ORDER BY r.title"
        rows = c.execute(q, (company_id,) if company_id is not None else ()).fetchall()
        out = []
        for r in rows:
            rd = _row(r)
            rd["required_skills"] = role_skills(c, r["id"])
            out.append(rd)
        return out


def list_catalog_roles():
    """Reference roles seeded as the talent catalog (read-only baseline)."""
    with get_cursor() as c:
        rows = c.execute("SELECT r.*, c.name AS company_name FROM roles r "
                         "JOIN companies c ON c.id=r.company_id WHERE r.is_reference=1 ORDER BY r.title").fetchall()
        out = []
        for r in rows:
            rd = _row(r)
            rd["required_skills"] = role_skills(c, r["id"])
            out.append(rd)
        return out


def list_feed_roles(location=None, country=None, limit=8):
    """Live openings (company-posted, non-reference roles) ranked by how close
    they are to the requesting user's location: same location first, roles with
    no location (remote/global) next, the rest after. Supplies the 'available
    roles' live feed on the student dashboard."""
    location = (location or "").strip()
    country = (country or "").strip()
    with get_cursor() as c:
        rows = c.execute("""SELECT r.id, r.title, r.description, r.is_reference,
                                   c.name AS company_name, c.location AS company_location
                            FROM roles r JOIN companies c ON c.id=r.company_id
                            WHERE r.is_reference=0
                            ORDER BY r.title""").fetchall()
        out = []
        for r in rows:
            rd = _row(r)
            rd["required_skills"] = role_skills(c, r["id"])
            out.append(rd)
        def rank(r):
            loc = (r.get("company_location") or "").strip()
            if not loc:
                return 1
            if loc.lower() == location.lower():
                return 0
            if country and (country.lower() in loc.lower() or loc.lower() in country.lower()):
                return 0
            return 2
        out.sort(key=lambda r: (rank(r), 0 if not (r.get("company_location") or "").strip() else 1, r["title"].lower()))
        return out[:limit]


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


def create_role(company_id, title, required_skills, description=None, is_reference=0):
    """required_skills: list of {name, category, level}."""
    with get_cursor() as c:
        cur = c.execute("INSERT INTO roles (company_id, title, description, is_reference) VALUES (?,?,?,?)",
                        (company_id, title, description, int(is_reference)))
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
    allowed = {"name", "email", "university", "target_role_id", "cv_filename", "cohort_confirmed", "share_public"}
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
        rows = c.execute("""
            SELECT l.id, l.student_id, l.skill_id, s.name AS skill_name, s.category,
                   l.explanation, l.practice_exercise, l.mini_project, l.resources, l.roadmap, l.progress, l.generated_at
            FROM learning_path_items l JOIN skills s ON s.id=l.skill_id
            WHERE l.student_id=? ORDER BY s.name""", (student_id,)).fetchall()
        out = []
        for r in rows:
            d = _row(r)
            d["resources"] = _json_loads(d.get("resources"))
            d["roadmap"] = _json_loads(d.get("roadmap"))
            d["progress"] = _json_loads(d.get("progress")) or []
            out.append(d)
        return out


def get_learning_item(student_id, skill_id):
    with get_cursor() as c:
        r = c.execute("""
            SELECT l.id, l.student_id, l.skill_id, s.name AS skill_name, s.category,
                   l.explanation, l.practice_exercise, l.mini_project, l.resources, l.roadmap, l.progress, l.generated_at
            FROM learning_path_items l JOIN skills s ON s.id=l.skill_id
            WHERE l.student_id=? AND l.skill_id=?""", (student_id, skill_id)).fetchone()
        if not r:
            return None
        d = _row(r)
        d["resources"] = _json_loads(d.get("resources"))
        d["roadmap"] = _json_loads(d.get("roadmap"))
        d["progress"] = _json_loads(d.get("progress")) or []
        return d


def upsert_learning_item(student_id, skill_id, explanation, practice_exercise, mini_project,
                         resources=None, roadmap=None):
    with get_cursor() as c:
        c.execute("""INSERT INTO learning_path_items (student_id, skill_id, explanation, practice_exercise, mini_project, resources, roadmap)
                     VALUES (?,?,?,?,?,?,?)
                     ON CONFLICT(student_id, skill_id) DO UPDATE SET
                       explanation=excluded.explanation,
                       practice_exercise=excluded.practice_exercise,
                       mini_project=excluded.mini_project,
                       resources=excluded.resources,
                       roadmap=excluded.roadmap,
                       generated_at=datetime('now')""",
                  (student_id, skill_id, explanation, practice_exercise, mini_project,
                   _json_dumps(resources), _json_dumps(roadmap)))
        return get_learning_item(student_id, skill_id)


def update_learning_progress(student_id, skill_id, steps):
    """Persist the completed roadmap step numbers for a learning item."""
    with get_cursor() as c:
        c.execute("UPDATE learning_path_items SET progress=? WHERE student_id=? AND skill_id=?",
                  (_json_dumps(sorted(set(steps))), student_id, skill_id))
    return get_learning_item(student_id, skill_id)


def get_career_roadmap(student_id, role_id):
    with get_cursor() as c:
        row = c.execute("SELECT * FROM career_roadmaps WHERE student_id=? AND role_id=?",
                        (student_id, role_id)).fetchone()
        if not row:
            return None
        d = _row(row)
        d["roadmap"] = _json_loads(d["roadmap"])
        return d


def upsert_career_roadmap(student_id, role_id, roadmap):
    with get_cursor() as c:
        c.execute("""INSERT INTO career_roadmaps (student_id, role_id, roadmap)
                     VALUES (?,?,?)
                     ON CONFLICT(student_id, role_id) DO UPDATE SET
                       roadmap=excluded.roadmap,
                       generated_at=datetime('now')""",
                  (student_id, role_id, _json_dumps(roadmap)))
    return get_career_roadmap(student_id, role_id)


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
                              flags, level_before, level_after, per_question=None):
    with get_cursor() as c:
        cur = c.execute("""INSERT INTO assessment_attempts
                           (student_id, skill_id, questions, answers, score, passed, flags, per_question, level_before, level_after)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (student_id, skill_id, questions, answers, score, passed, flags,
                         per_question, level_before, level_after))
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

def create_user(email, role, display_name, password=None, auth_provider="local", google_sub=None, verified=0, country=None, university=None, location=None):
    """Create a user. Local accounts hash their password; Google accounts store none."""
    pw_col = password or ""  # legacy NOT NULL constraint; auth always uses password_hash
    hash_b64 = salt_b64 = None
    if password:
        from .auth import hash_password
        hash_b64, salt_b64 = hash_password(password)
    with get_cursor() as c:
        cur = c.execute(
            """INSERT INTO users (email, password, role, display_name, password_hash, password_salt, auth_provider, google_sub, verified, country, university, location)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (email, pw_col, role, display_name, hash_b64, salt_b64, auth_provider, google_sub, int(verified), country, university, location))
        return get_user(cur.lastrowid)


def get_user_by_email(email):
    with get_cursor() as c:
        return _safe_user(c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())


def get_user(user_id):
    with get_cursor() as c:
        return _safe_user(c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())


def get_user_by_google_sub(google_sub):
    with get_cursor() as c:
        return _safe_user(c.execute("SELECT * FROM users WHERE google_sub=?", (google_sub,)).fetchone())


def get_user_by_email_or_google_sub(email, google_sub=None):
    u = get_user_by_email(email)
    if u:
        return u
    if google_sub:
        return get_user_by_google_sub(google_sub)
    return None


def public_user(user):
    """Role-safe projection of a user record — never includes hash or salt."""
    return {"id": user["id"], "email": user["email"], "role": user["role"],
            "display_name": user["display_name"], "auth_provider": user.get("auth_provider", "local"),
            "verified": bool(user.get("verified")), "country": user.get("country") or "",
            "university": user.get("university") or "", "location": user.get("location") or ""}


def set_user_password(user_id, password):
    from .auth import hash_password
    hash_b64, salt_b64 = hash_password(password)
    with get_cursor() as c:
        c.execute("UPDATE users SET password_hash=?, password_salt=?, auth_provider='local' WHERE id=?",
                  (hash_b64, salt_b64, user_id))


def check_credentials(email, password):
    """Verify email/password. Returns the user row or None. Supports legacy
    plaintext rows so pre-upgrade seed accounts keep signing in.

    Reads the raw row (including the legacy 'password' column) for the
    comparison, but only ever returns a sanitized copy without it.
    """
    with get_cursor() as c:
        raw = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not raw:
        return None
    full = dict(raw)
    user = _safe_user(full)
    if user.get("auth_provider") == "google" or (user.get("password_hash") is None and user.get("auth_provider") == "google"):
        return None
    if user.get("password_hash"):
        from .auth import verify_password
        if verify_password(password, user["password_hash"], user["password_salt"]):
            return user
        return None
    # legacy plaintext
    if full.get("password") and hmac_compat(password, full["password"]):
        return user
    return None


def hmac_compat(a, b):
    import hmac as _hmac
    return _hmac.compare_digest(bytes(a, "utf-8"), bytes(b, "utf-8"))


# ---------------------------------------------------------------- sessions

def create_session(user_id, token=None):
    if token is None:
        from .auth import new_session_token
        token = new_session_token()
    with get_cursor() as c:
        c.execute("INSERT INTO sessions (token, user_id) VALUES (?,?)", (token, user_id))
    return token


def get_session_user(token):
    if not token:
        return None
    with get_cursor() as c:
        r = c.execute("""SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
                         WHERE s.token=?""", (token,)).fetchone()
        return _safe_user(r) if r else None


def delete_session(token):
    if not token:
        return
    with get_cursor() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (token,))


# ---------------------------------------------------------------- google registrations (role pending)

def upsert_google_registration(google_sub, email, display_name):
    with get_cursor() as c:
        c.execute("""INSERT INTO google_registrations (google_sub, email, display_name) VALUES (?,?,?)
                     ON CONFLICT(google_sub) DO UPDATE SET display_name=excluded.display_name""",
                  (google_sub, email, display_name))
        return _row(c.execute("SELECT * FROM google_registrations WHERE google_sub=?", (google_sub,)).fetchone())


def get_google_registration(google_sub):
    with get_cursor() as c:
        return _row(c.execute("SELECT * FROM google_registrations WHERE google_sub=?", (google_sub,)).fetchone())


def delete_google_registration(google_sub):
    with get_cursor() as c:
        c.execute("DELETE FROM google_registrations WHERE google_sub=?", (google_sub,))


# ---------------------------------------------------------------- password resets

def create_password_reset(user_id):
    from .auth import new_reset_token, reset_expiry_iso
    token = new_reset_token()
    with get_cursor() as c:
        c.execute("INSERT INTO password_resets (token, user_id, expires_at) VALUES (?,?,?)",
                  (token, user_id, reset_expiry_iso()))
        return _row(c.execute("SELECT * FROM password_resets WHERE token=?", (token,)).fetchone())


def get_password_reset(token):
    with get_cursor() as c:
        return _row(c.execute("SELECT * FROM password_resets WHERE token=?", (token,)).fetchone())


def consume_password_reset(token):
    """Mark a reset token used; returns affected user id, or None if unusable."""
    row = get_password_reset(token)
    if not row or row["used"]:
        return None
    from .auth import utcnow_iso
    if row["expires_at"] < utcnow_iso():
        return None
    with get_cursor() as c:
        c.execute("UPDATE password_resets SET used=1 WHERE token=?", (token,))
    return row["user_id"]


# ------------------------------------------------------------------ universities

def list_universities():
    """Countries with their universities, grouped and ordered."""
    groups = {}
    with get_cursor() as c:
        rows = c.execute("SELECT country, name FROM universities ORDER BY country, name").fetchall()
    for r in rows:
        groups.setdefault(r["country"], []).append(r["name"])
    return [{"country": ctry, "universities": names} for ctry, names in groups.items()]


def add_university(country, name):
    with get_cursor() as c:
        c.execute("INSERT OR IGNORE INTO universities (country, name) VALUES (?,?)", (country, name))


def list_locations():
    """Countries with their cities, grouped and ordered (cascading dropdown)."""
    groups = {}
    with get_cursor() as c:
        rows = c.execute("SELECT country, name FROM cities ORDER BY country, name").fetchall()
    for r in rows:
        groups.setdefault(r["country"], []).append(r["name"])
    return [{"country": ctry, "cities": names} for ctry, names in groups.items()]


def add_city(country, name):
    with get_cursor() as c:
        c.execute("INSERT OR IGNORE INTO cities (country, name) VALUES (?,?)", (country, name))


# ------------------------------------------------------------------ email verification

def create_email_verification(user_id):
    from .auth import new_reset_token, reset_expiry_iso
    token = new_reset_token()
    with get_cursor() as c:
        c.execute("INSERT INTO email_verifications (token, user_id, expires_at) VALUES (?,?,?)",
                  (token, user_id, reset_expiry_iso()))
        return _row(c.execute("SELECT * FROM email_verifications WHERE token=?", (token,)).fetchone())


def get_email_verification(token):
    with get_cursor() as c:
        return _row(c.execute("SELECT * FROM email_verifications WHERE token=?", (token,)).fetchone())


def consume_email_verification(token):
    """Mark a verification token used; returns affected user id, or None if unusable."""
    row = get_email_verification(token)
    if not row or row["used"]:
        return None
    from .auth import utcnow_iso
    if row["expires_at"] < utcnow_iso():
        return None
    with get_cursor() as c:
        c.execute("UPDATE email_verifications SET used=1 WHERE token=?", (token,))
    return row["user_id"]


def set_user_verified(user_id):
    with get_cursor() as c:
        c.execute("UPDATE users SET verified=1 WHERE id=?", (user_id,))
