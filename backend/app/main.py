"""SkillBridge FastAPI application.

Single app serving both the REST API and the built React frontend.

Auth model: opaque session tokens issued on login and carried as
`Authorization: Bearer <token>`. RBAC gates every endpoint — students only
access their own records, companies only their own roles/candidates, and the
university view only sees anonymized, aggregated data.
"""
import json
import os
from pathlib import Path


def _load_env():
    """Load a repo-root .env if present. Real environment variables win.

    The documented setup is 'copy .env.example to .env and add keys'; without a
    loader here those keys were never read, so every GenAI feature silently ran
    its deterministic fallback.
    """
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_env()

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from . import models, matching, genai, integrity, seed, auth as auth_mod, mailer, activity, jobs, career_roadmap
from .resources import _CHECK_CACHE, annotate_resources
from .database import init_db, get_cursor

FRONTEND_DIST = os.environ.get(
    "SKILLBRIDGE_FRONTEND_DIST",
    str(Path(__file__).resolve().parents[2] / "frontend" / "dist"),
)

app = FastAPI(title="SkillBridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


PASS_THRESHOLD = 70.0
MIN_COHORT_SIZE = 5  # University stats rule: never compute a stat from fewer students
VALID_SIGNUP_ROLES = ("Student", "Company", "University Admin")
_ENTITY_ROLES = {"Student", "Company"}

LEVELS = ["Beginner", "Intermediate", "Advanced"]


def _assessment_difficulty(student, role, skill_id):
    """Quiz difficulty is driven by the level this skill is required at for the
    student's Target Career (Phase 5: skill-targeted, level-adaptive difficulty)."""
    if not role:
        return "Intermediate"
    for row in matching.categorize(student, role):
        if row["skill_id"] == skill_id:
            return row["required_level"]
    return "Intermediate"


@app.on_event("startup")
def on_startup():
    from .database import DB_PATH
    if not os.path.exists(DB_PATH):
        # seed.seed() creates the schema AND the reference data (universities,
        # roles, catalog, demo accounts) — it must run on a truly fresh DB,
        # which means checking BEFORE init_db() ever touches the file.
        seed.seed()
    else:
        # Existing databases are only migrated so their new columns appear.
        init_db()


# ------------------------------------------------------------------ auth helpers

def _bearer_token(request: Request):
    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token.strip()


def _current_user(request: Request):
    user = models.get_session_user(_bearer_token(request))
    if not user:
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    return user


def _require_roles(user, *roles):
    if user["role"] not in roles:
        raise HTTPException(status_code=403, detail=f"Requires {' or '.join(roles)} role")


def _resolve_role_context(user):
    """Return (entity_type, entity) for a logged-in user."""
    if user["role"] == "Student":
        return "student", models.get_student_by_user(user["id"])
    if user["role"] == "Company":
        return "company", models.get_company_by_user(user["id"])
    return "university", None


def _entity_bundle(user):
    """Full public identity payload attached to login/me responses."""
    entity_type, entity = _resolve_role_context(user)
    payload = models.public_user(user)
    payload["entity_type"] = entity_type
    if entity_type == "student":
        payload["student"] = entity
        payload["analysis"] = matching.analyze_student(entity["id"]) if entity.get("target_role_id") else None
        payload["learning"] = models.list_learning_path(entity["id"])
    elif entity_type == "company":
        payload["company"] = entity
        payload["roles"] = models.get_roles_by_company(entity["id"])
    return payload


def _upsert_university(country, university):
    """Record a chosen university in the reference list (idempotent)."""
    if country and university:
        models.add_university(country, university)


def _own_student(user, student_id):
    """Student endpoints are scoped to the owning student. A company may read a
    student only when that student targets one of the company's own roles; the
    university view stays aggregate-only, so no individual records are reachable."""
    if user["role"] == "Student":
        student = models.get_student_by_user(user["id"])
        if not student or student["id"] != student_id:
            raise HTTPException(status_code=403, detail="Not allowed to access another student's data")
        return
    if user["role"] == "Company":
        student = models.get_student(student_id)
        if not student or not student.get("target_role"):
            raise HTTPException(status_code=403, detail="Not allowed to access this student's data")
        company = models.get_company_by_user(user["id"])
        role = student["target_role"]
        if not company or not role or role.get("company_id") != company["id"]:
            raise HTTPException(status_code=403, detail="Not allowed to access this student's data")
        return
    raise HTTPException(status_code=403, detail="Not allowed")


def _own_company_role(user, role_id):
    """Company may manage only roles owned by its own company record (never the catalog)."""
    role = models.get_role(role_id)
    if user["role"] != "Company":
        raise HTTPException(status_code=403, detail="Only companies manage roles")
    if role is None or role.get("is_reference"):
        raise HTTPException(status_code=404, detail="Role not found")
    company = models.get_company_by_user(user["id"])
    if not company or role["company_id"] != company["id"]:
        raise HTTPException(status_code=403, detail="Not allowed to manage this role")
    return role


# ------------------------------------------------------------------ auth endpoints

@app.post("/api/auth/signup")
def signup(body: dict, background_tasks: BackgroundTasks):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    display_name = (body.get("display_name") or "").strip()
    role = body.get("role")
    country = (body.get("country") or "").strip()
    university = (body.get("university") or "").strip()
    location = (body.get("location") or "").strip()
    if not email or not password or not display_name:
        raise HTTPException(status_code=400, detail="Email, password and display name are required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if role not in VALID_SIGNUP_ROLES:
        raise HTTPException(status_code=400, detail="You can create a Student, Company or University Admin account here")
    if models.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    if not location:
        raise HTTPException(status_code=400, detail="Please tell us your location (city) so we can show you roles near you")
    if role == "University Admin" and not (country and university):
        raise HTTPException(status_code=400, detail="University Admins must choose a country and university")

    # Email verification: local accounts must verify their email before they are
    # marked verified. When SMTP is not configured (demo), accounts start verified
    # so the app stays demoable but the verification flow remains available.
    verify = mailer.email_configured()
    user = models.create_user(email, role, display_name, password=password,
                              verified=0 if verify else 1, country=country,
                              university=university, location=location)
    if role == "Student":
        models.create_student(display_name, email, university, user_id=user["id"])
    elif role == "Company":
        models.create_company(display_name, (body.get("industry") or "").strip(),
                              user_id=user["id"], location=location)
    elif role == "University Admin":
        _upsert_university(country, university)
    if verify:
        token = models.create_email_verification(user["id"])["token"]
        # Send asynchronously so a slow/unreachable SMTP can never block (and
        # appear to "freeze") the create-account request.
        background_tasks.add_task(mailer.send_verification_email, user, token)
    token = models.create_session(user["id"])
    return {"token": token, **models.public_user(user), "entity_type": _resolve_role_context(user)[0],
            "email_verified_delivery": verify}


@app.post("/api/auth/login")
def login(body: dict):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    user = models.check_credentials(email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = models.create_session(user["id"])
    return {"token": token, **_entity_bundle(user)}


@app.post("/api/auth/logout")
def logout(request: Request):
    models.delete_session(_bearer_token(request))
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    user = _current_user(request)
    return _entity_bundle(user)


@app.get("/api/auth/google/config")
def google_config():
    return {"configured": auth_mod.google_configured(), "demo": auth_mod.DEMO_GOOGLE}


@app.get("/api/auth/google/login")
async def google_login():
    """Real OAuth redirect (via Authlib). Demo mode uses /api/auth/google/demo."""
    if not auth_mod.google_configured():
        return RedirectResponse(url="/login", status_code=302)
    oauth = auth_mod.get_oauth()
    return await oauth.google.authorize_redirect(
        request_uri="http://localhost:8000/api/auth/google/callback")


@app.post("/api/auth/google/demo")
def google_demo(body: dict):
    """Demo Google identity, used only when real OAuth credentials are absent."""
    email = (body.get("email") or "").strip().lower()
    display_name = (body.get("display_name") or "").strip()
    if not email or not display_name:
        raise HTTPException(status_code=400, detail="Email and display name are required")
    user = models.get_user_by_email(email)
    if user:
        token = models.create_session(user["id"])
        return {"token": token, "registered": True, **_entity_bundle(user)}
    sub = f"demo-{email}"
    models.upsert_google_registration(sub, email, display_name)
    return {"registered": False, "google_sub": sub, "email": email, "display_name": display_name}


@app.get("/api/auth/google/callback")
async def google_callback(request: Request):
    if not auth_mod.google_configured():
        raise HTTPException(status_code=400, detail="Google not configured")
    oauth = auth_mod.get_oauth()
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or token
    sub = userinfo.get("sub")
    email = (userinfo.get("email") or "").lower()
    name = userinfo.get("name") or (email.split("@")[0] if email else "Google User")
    existing = models.get_user_by_google_sub(sub) or models.get_user_by_email(email) if sub else None
    if existing:
        sess = models.create_session(existing["id"])
        return {"token": sess, "registered": True, **_entity_bundle(existing)}
    if sub:
        models.upsert_google_registration(sub, email, name)
        return {"registered": False, "google_sub": sub, "email": email, "display_name": name}
    raise HTTPException(status_code=400, detail="Could not identify the Google account")


@app.post("/api/auth/google/complete")
def google_complete(body: dict):
    """Second step of Google signup: pick a role; the backend creates the account."""
    sub = (body.get("google_sub") or "").strip()
    role = body.get("role")
    country = (body.get("country") or "").strip()
    university = (body.get("university") or "").strip()
    industry = (body.get("industry") or "").strip()
    location = (body.get("location") or "").strip()
    if not sub or role not in VALID_SIGNUP_ROLES:
        raise HTTPException(status_code=400, detail="google_sub and a valid role are required")
    if not location:
        raise HTTPException(status_code=400, detail="Please tell us your location (city) so we can show you roles near you")
    if role == "University Admin" and not (country and university):
        raise HTTPException(status_code=400, detail="University Admins must choose a country and university")
    reg = models.get_google_registration(sub)
    if not reg:
        raise HTTPException(status_code=404, detail="No pending Google registration")
    user = models.create_user(reg["email"], role, reg["display_name"],
                              auth_provider="google", google_sub=sub, verified=1,
                              country=country, university=university, location=location)
    if role == "Student":
        models.create_student(reg["display_name"], reg["email"], university, user_id=user["id"])
    elif role == "Company":
        models.create_company(reg["display_name"], industry, user_id=user["id"], location=location)
    if country and university:
        _upsert_university(country, university)
    models.delete_google_registration(sub)
    sess = models.create_session(user["id"])
    return {"token": sess, **_entity_bundle(user)}


@app.post("/api/auth/reset/request")
def reset_request(body: dict, background_tasks: BackgroundTasks):
    email = (body.get("email") or "").strip().lower()
    user = models.get_user_by_email(email)
    if not user or user.get("auth_provider") == "google":
        # Do not leak whether an account exists.
        return {"ok": True, "message": "If that email has an account, a reset link has been created."}
    created = models.create_password_reset(user["id"])
    if mailer.email_configured():
        # Send asynchronously so a slow/unreachable SMTP can't block the request.
        background_tasks.add_task(mailer.send_reset_email, user, created["token"])
        return {"ok": True, "message": "A password reset link has been sent to your email."}
    # No SMTP configured (demo): never return the raw token — it is a live
    # credential that can reset any account.  Instead, auto-confirm the reset
    # so the flow stays demoable without exposing secrets.
    return {"ok": True, "message": "Demo mode: no email is sent. Check the demo-mode banner for next steps."}


@app.post("/api/auth/reset/confirm")
def reset_confirm(body: dict):
    token = (body.get("token") or "").strip()
    new_password = body.get("new_password") or ""
    if not token or len(new_password) < 8:
        raise HTTPException(status_code=400, detail="A valid token and a password of 8+ characters are required")
    user_id = models.consume_password_reset(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
    models.set_user_password(user_id, new_password)
    return {"ok": True}


# ------------------------------------------------------------------ email verification

@app.post("/api/auth/verify")
def verify_email(body: dict):
    """Verify a user's email using the token emailed at signup."""
    token = (body.get("token") or "").strip()
    user_id = models.consume_email_verification(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Verification link is invalid or expired")
    models.set_user_verified(user_id)
    return {"ok": True}


@app.post("/api/auth/verify/status")
def verify_status(body: dict):
    """Lightweight helper: report verification state for a new signup."""
    email = (body.get("email") or "").strip().lower()
    user = models.get_user_by_email(email)
    if not user:
        return {"exists": False}
    return {"exists": True, "verified": bool(user.get("verified"))}


# ------------------------------------------------------------------ universities reference

@app.get("/api/config/demo-mode")
def api_demo_mode():
    """Report whether the app is running without a real GenAI provider (demo /
    deterministic-fallback mode) and whether email delivery (SMTP) is configured.
    Lets the frontend show a visible banner explaining why AI output is generic
    and why reset links are not emailed."""
    return {
        "genai_enabled": genai.genai_enabled(),
        "email_configured": mailer.email_configured(),
    }


@app.get("/api/universities")
def api_list_universities():
    """Countries with their universities (public reference data for the
    cascading signup dropdown — no auth required)."""
    return models.list_universities()


@app.get("/api/locations")
def api_list_locations():
    """Countries with their cities (public reference data for the cascading
    country → city signup dropdown — no auth required)."""
    return models.list_locations()


# ------------------------------------------------------------------ skills catalog

@app.get("/api/skills")
def api_list_skills(request: Request):
    _current_user(request)
    return models.list_skills()


@app.post("/api/skills")
def api_create_skill(request: Request, body: dict):
    _current_user(request)
    name, category = body["name"], body.get("category", "General")
    existing = models.get_skill_by_name(name)
    if existing:
        return existing
    return models.create_skill(name, category)


# ------------------------------------------------------------------ companies

@app.get("/api/companies")
def api_list_companies(request: Request):
    _current_user(request)
    return models.list_companies()


# ------------------------------------------------------------------ roles

@app.get("/api/roles")
def api_list_roles(request: Request):
    user = _current_user(request)
    roles = models.list_roles()
    catalog = models.list_catalog_roles()
    user_location = (user.get("location") or "").strip()
    user_country = (user.get("country") or "").strip()
    if user["role"] == "Company":
        company = models.get_company_by_user(user["id"])
        company_id = company["id"] if company else None
        roles = [r for r in roles if r.get("company_id") == company_id and not r.get("is_reference")]
    else:
        # Live roster first: roles posted by companies in the user's location/country,
        # then remote (no location) openings, then the rest.
        def loc_rank(r):
            loc = (r.get("company_location") or "").strip()
            if not loc:
                return 1
            if user_location and loc.lower() == user_location.lower():
                return 0
            if user_country and (user_country.lower() in loc.lower() or loc.lower() in user_country.lower()):
                return 0
            return 2
        roles.sort(key=lambda r: (loc_rank(r), r["title"].lower()))
    return {"roles": roles, "catalog": catalog,
            "location": user_location,
            "is_company": user["role"] == "Company",
            "company_id": (models.get_company_by_user(user["id"]) or {}).get("id") if user["role"] == "Company" else None}


@app.get("/api/roles/catalog")
def api_catalog_roles(request: Request):
    _current_user(request)
    return models.list_catalog_roles()


@app.get("/api/roles/{role_id}")
def api_get_role(role_id: int, request: Request):
    """Catalog roles are public reference data; a company may read only its own
    role definitions, never another company's."""
    user = _current_user(request)
    role = models.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.get("is_reference"):
        return role
    if user["role"] == "Company":
        company = models.get_company_by_user(user["id"])
        if company and role.get("company_id") == company["id"]:
            return role
    raise HTTPException(status_code=403, detail="Not allowed to view this role")


@app.post("/api/roles")
def api_create_role(request: Request, body: dict):
    user = _current_user(request)
    _require_roles(user, "Company")
    company = models.get_company_by_user(user["id"]) or {}
    if not company.get("id"):
        raise HTTPException(status_code=403, detail="No company linked to this account")
    return models.create_role(company["id"], body["title"],
                              body.get("required_skills", []), body.get("description"))


@app.put("/api/roles/{role_id}")
def api_update_role(role_id: int, request: Request, body: dict):
    user = _current_user(request)
    role = _own_company_role(user, role_id)
    return models.update_role(role_id, body.get("title") or role["title"],
                              body.get("description"), body.get("required_skills"))


@app.delete("/api/roles/{role_id}")
def api_delete_role(role_id: int, request: Request):
    user = _current_user(request)
    _own_company_role(user, role_id)
    models.delete_role(role_id)
    return {"deleted": True}


@app.get("/api/company/roles/{role_id}/candidates")
def api_role_candidates(role_id: int, request: Request):
    user = _current_user(request)
    _own_company_role(user, role_id)
    rows = []
    for student in models.list_students():
        full = models.get_student(student["id"])
        if full.get("target_role_id") != role_id:
            continue
        analysis = matching.analyze_student(full["id"])
        if not analysis:
            continue
        rows.append({
            "student_id": full["id"], "name": full["name"], "email": full["email"],
            "university": full["university"], "match_score": analysis["match_score"],
            "gap_count": analysis["gap_count"],
            "verified_count": len(full["verified_skills"]),
        })
    rows.sort(key=lambda r: r["match_score"], reverse=True)
    return rows



# ------------------------------------------------------------------ company analytics

@app.get("/api/company/roles/{role_id}/skills")
def api_role_skill_coverage(role_id: int, request: Request):
    """Aggregate applicant skill coverage for a company's own role.

    For every required skill of the role, report how many matched candidates are
    strong (meets/exceeds requirement), in a gap (has it below requirement), or
    missing it entirely — plus a coverage percentage. Only aggregate numbers and
    skill identifiers are exposed, never an individual candidate's raw skills.
    """
    user = _current_user(request)
    role = _own_company_role(user, role_id)
    matched = []
    for student in models.list_students():
        full = models.get_student(student["id"])
        if full.get("target_role_id") != role_id:
            continue
        analysis = matching.analyze_student(full["id"])
        if analysis:
            matched.append(analysis)

    coverage = []
    for rs in role.get("required_skills", []):
        strong = gap = missing = 0
        for a in matched:
            row = next((g for g in a["skill_gaps"] if g["skill_id"] == rs["skill_id"]), None)
            if row is None:
                missing += 1
            elif row["status"] == "strong":
                strong += 1
            else:
                gap += 1
        n = len(matched)
        coverage.append({
            "skill_id": rs["skill_id"],
            "skill_name": rs["name"],
            "category": rs.get("category"),
            "required_level": rs["required_level"],
            "strong": strong,
            "gap": gap,
            "missing": missing,
            "coverage_pct": round(strong / n * 100, 1) if n else 0.0,
            "n_candidates": n,
        })
    coverage.sort(key=lambda c: c["coverage_pct"])
    return {"role_id": role_id, "role_title": role["title"],
            "candidate_count": len(matched), "skills": coverage}


# ------------------------------------------------------------------ students

@app.get("/api/students")
def api_list_students(request: Request):
    """Anonymized cohort index for the university dashboard only — never names
    or emails, and no access for students/companies."""
    user = _current_user(request)
    _require_roles(user, "University Admin")
    return [{"id": s["id"], "university": s["university"],
             "target_role_id": s.get("target_role_id"),
             "cohort_confirmed": bool(s.get("cohort_confirmed"))}
            for s in models.list_students()]


@app.get("/api/students/{student_id}")
def api_get_student(student_id: int, request: Request):
    user = _current_user(request)
    _own_student(user, student_id)
    student = models.get_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@app.put("/api/students/{student_id}")
def api_update_student(student_id: int, request: Request, body: dict):
    user = _current_user(request)
    _own_student(user, student_id)
    fields = {k: v for k, v in body.items() if k in
              ("name", "email", "university", "target_role_id", "cv_filename", "share_public")}
    return models.update_student(student_id, **fields)


@app.delete("/api/students/{student_id}")
def api_delete_student(student_id: int, request: Request):
    user = _current_user(request)
    _own_student(user, student_id)
    models.delete_student(student_id)
    return {"deleted": True}


# ------------------------------------------------------------------ CV upload + extraction

def _pdf_to_text(content_bytes):
    """Best-effort text extraction from an uploaded PDF. Returns '' on any
    failure so callers can fall back instead of crashing."""
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(content_bytes))
        parts = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                continue
            parts.append(text)
        return "\n".join(parts).strip()
    except Exception:
        return ""


@app.post("/api/students/{student_id}/cv")
def upload_cv(student_id: int, file: UploadFile = File(...), request: Request = None):
    user = _current_user(request)
    _own_student(user, student_id)
    content_bytes = file.file.read()
    cv_text = ""
    if content_bytes.startswith(b"%PDF"):
        cv_text = _pdf_to_text(content_bytes)
    if not cv_text.strip():
        try:
            cv_text = content_bytes.decode("utf-8", errors="replace")
        except Exception:
            cv_text = ""
    if not cv_text.strip():
        cv_text = "(uploaded document with no readable text)"
    extracted = genai.extract_skills_from_cv(cv_text)
    models.update_student(student_id, cv_filename=file.filename)
    models.replace_self_reported_skills(student_id, extracted)
    student = models.get_student(student_id)
    return {"extracted": extracted, "student": student,
            "genai_provider": "real" if genai.genai_enabled() else "deterministic-fallback"}


# ------------------------------------------------------------------ matching

@app.get("/api/students/{student_id}/analysis")
def api_student_analysis(student_id: int, request: Request):
    user = _current_user(request)
    _own_student(user, student_id)
    analysis = matching.analyze_student(student_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Student has no target role")
    return analysis


@app.get("/api/students/{student_id}/activity")
def api_student_activity(student_id: int, request: Request):
    user = _current_user(request)
    _own_student(user, student_id)
    return activity.activity_summary(student_id)


# ------------------------------------------------------------------ learning

@app.post("/api/students/{student_id}/learning/generate")
def api_generate_learning(student_id: int, request: Request, body: dict):
    user = _current_user(request)
    _own_student(user, student_id)
    skill_id = body["skill_id"]
    student = models.get_student(student_id)
    role = student.get("target_role")
    if not role:
        raise HTTPException(status_code=400, detail="Student has no target role")
    skill = models.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    ctx = f"Studying at {student['university']}, building a career as a {role['title']}."
    item = genai.generate_learning_item(skill["name"], skill["category"], role["title"], ctx)
    return models.upsert_learning_item(student_id, skill_id, item["explanation"],
                                       item["practice_exercise"], item["mini_project"],
                                       item.get("resources") or [], item.get("roadmap") or None)


@app.get("/api/students/{student_id}/learning")
def api_list_learning(student_id: int, request: Request):
    user = _current_user(request)
    _own_student(user, student_id)
    return models.list_learning_path(student_id)


@app.get("/api/students/{student_id}/learning/{skill_id}")
def api_get_learning(student_id: int, skill_id: int, request: Request):
    user = _current_user(request)
    _own_student(user, student_id)
    item = models.get_learning_item(student_id, skill_id)
    if not item:
        raise HTTPException(status_code=404, detail="Learning item not found")
    return item


@app.post("/api/students/{student_id}/learning/{skill_id}/progress")
def api_save_learning_progress(student_id: int, skill_id: int, request: Request, body: dict):
    """Persist which roadmap steps a student has completed for one skill."""
    user = _current_user(request)
    _own_student(user, student_id)
    steps = []
    for s in body.get("steps") or []:
        try:
            num = int(s)
        except (TypeError, ValueError):
            continue
        if num > 0:
            steps.append(num)
    return models.update_learning_progress(student_id, skill_id, steps)


@app.post("/api/students/{student_id}/learning/{skill_id}/check-links")
def api_recheck_learning_links(student_id: int, skill_id: int, request: Request):
    """Re-validate all resource links for a learning item and return annotated results.
    
    Forces a fresh check (bypasses cache) and returns resources with availability status.
    Useful when a student suspects links have rotted or wants to refresh after fixes.
    """
    user = _current_user(request)
    _own_student(user, student_id)
    item = models.get_learning_item(student_id, skill_id)
    if not item:
        raise HTTPException(status_code=404, detail="Learning item not found")
    
    resources = item.get("resources") or []
    if not resources:
        return {"resources": [], "message": "No resources to check"}
    
    # Force fresh check by clearing cache for these URLs
    for r in resources:
        _CHECK_CACHE.pop(r["url"], None)
    
    annotated = annotate_resources(resources)
    # Return both annotated list and summary
    available = sum(1 for r in annotated if r.get("available") is True)
    dead = sum(1 for r in annotated if r.get("available") is False)
    unknown = sum(1 for r in annotated if r.get("available") is None)
    
    return {
        "resources": annotated,
        "summary": {"available": available, "dead": dead, "unknown": unknown, "total": len(annotated)}
    }


@app.get("/api/students/{student_id}/career-roadmap")
def api_get_career_roadmap(student_id: int, request: Request):
    """Full start-to-finish career roadmap for the student's target role.
    Stored per (student, role); regenerated if the role changed."""
    user = _current_user(request)
    _own_student(user, student_id)
    student = models.get_student(student_id)
    role = student.get("target_role") if student else None
    if not role:
        return {"role_title": None, "phases": [], "phase_count": 0,
                "summary": "Choose a target role on the Skills & Roles page first."}
    saved = models.get_career_roadmap(student_id, role["id"])
    if saved:
        return saved["roadmap"]
    roadmap = career_roadmap.build_career_roadmap(student, role)
    models.upsert_career_roadmap(student_id, role["id"], roadmap)
    return roadmap


# ------------------------------------------------------------------ AI tutor

@app.get("/api/students/{student_id}/tutor")
def api_tutor_history(student_id: int, request: Request, skill_id: int = None):
    user = _current_user(request)
    _own_student(user, student_id)
    return models.list_tutor_messages(student_id, skill_id)


@app.post("/api/students/{student_id}/tutor")
def api_tutor_chat(student_id: int, request: Request, body: dict):
    user = _current_user(request)
    _own_student(user, student_id)
    question = body.get("message", "")
    skill_id = body.get("skill_id")
    student = models.get_student(student_id)
    role = student.get("target_role")
    skill_name = models.get_skill(skill_id)["name"] if skill_id else None
    ctx = f"Studying at {student['university']}; current profile: " \
          + ", ".join(f"{s['name']} ({s['level']})" for s in student["self_reported_skills"]) \
          + "; target role: " + (role["title"] if role else "none")
    models.add_tutor_message(student_id, skill_id, "user", question)
    reply = genai.tutor_reply(question, ctx, skill_name, role["title"] if role else None)
    msg = models.add_tutor_message(student_id, skill_id, "assistant", reply)
    return msg


# ------------------------------------------------------------------ assessments

@app.post("/api/students/{student_id}/assessments/generate")
def api_generate_assessment(student_id: int, request: Request, body: dict):
    user = _current_user(request)
    _own_student(user, student_id)
    skill_id = body["skill_id"]
    num_questions = min(max(int(body.get("num_questions") or 10), 3), 20)
    practice = bool(body.get("practice"))
    student = models.get_student(student_id)
    role = student.get("target_role")
    skill = models.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    if practice:
        prior = next(iter([a for a in models.list_assessment_attempts(student_id, skill_id)
                           if a.get("per_question")]), None)
        if prior:
            questions = json.loads(prior["questions"]) if isinstance(prior.get("questions"), str) else prior["questions"]
            previous_results = json.loads(prior["per_question"]) if isinstance(prior.get("per_question"), str) else (prior.get("per_question") or [])
            return {"skill": skill, "questions": questions, "practice": True,
                    "previous_score": prior["score"], "previous_passed": bool(prior["passed"]),
                    "previous_results": previous_results}

    questions = genai.generate_quiz(
        skill["name"], role["title"] if role else "", num_questions=num_questions,
        difficulty=_assessment_difficulty(student, role, skill_id))
    return {"skill": skill, "questions": questions, "practice": bool(practice),
            "previous_results": None, "previous_score": None, "previous_passed": None}


@app.post("/api/students/{student_id}/assessments")
def api_submit_assessment(student_id: int, request: Request, body: dict):
    user = _current_user(request)
    _own_student(user, student_id)
    skill_id = body["skill_id"]
    questions = body.get("questions", [])
    answers = body.get("answers", [])
    total_seconds = body.get("total_seconds")
    tab_switches = int(body.get("tab_switches") or 0)
    free_text_answers = body.get("free_text_answers") or []

    skill = models.get_skill(skill_id)
    student = models.get_student(student_id)

    flags = integrity.evaluate_attempt(len(questions), total_seconds, free_text_answers, tab_switches)

    # grade free-text answers as a batch (real GenAI call when a key is set,
    # deterministic semantic-overlap heuristic otherwise)
    ft_indexes = [i for i, q in enumerate(questions) if q and q.get("type") == "free_text"]
    ft_pairs = [(q.get("answer") or "", str(answers[i]) if i < len(answers) else "")
                for i, q in enumerate(questions) if i in ft_indexes]
    ft_results = genai.grade_free_text_batch(
        ft_pairs, skill["name"], (student.get("target_role") or {}).get("title"))
    ft_cursor = 0

    # per-question results drive an objective, transparent score
    per_question = []
    correct = 0
    for i, q in enumerate(questions):
        ans = str(answers[i]) if i < len(answers) else ""
        model_ans = (q.get("answer") or "") if q else ""
        is_correct = False
        if model_ans:
            if q.get("type") == "multiple_choice":
                is_correct = ans.strip().lower() == model_ans.strip().lower()
            else:
                is_correct = bool(ft_results[ft_cursor]) if ft_cursor < len(ft_results) else False
                ft_cursor += 1
        if is_correct:
            correct += 1
        per_question.append({"index": i, "type": q.get("type", "multiple_choice"),
                             "correct": is_correct, "answer": ans})
    score = round((correct / max(len(questions), 1)) * 100, 1)
    passed = score >= PASS_THRESHOLD and not any(f["severity"] == "high" for f in flags)

    level, _ = matching.effective_skill_level(student, skill_id)
    before = level or "Beginner"
    after = before
    if passed:
        after = LEVELS[min(LEVELS.index(before) + 1, 2)] if before != "Advanced" else "Advanced"

    models.create_assessment_attempt(student_id, skill_id, json.dumps(questions),
                                     json.dumps(answers), score, int(passed),
                                     json.dumps(flags), before, after,
                                     per_question=json.dumps(per_question))
    if passed:
        models.update_verified_skill(student_id, skill_id, after)

    return {
        "score": score,
        "passed": passed,
        "flags": flags,
        "questions": questions,
        "answers": answers,
        "per_question": per_question,
        "level_before": before,
        "level_after": after,
        "analysis": matching.analyze_student(student_id),
    }


@app.get("/api/students/{student_id}/assessments")
def api_list_assessments(student_id: int, request: Request):
    user = _current_user(request)
    _own_student(user, student_id)
    return models.list_assessment_attempts(student_id=student_id)


# ------------------------------------------------------------------ recent jobs

@app.get("/api/jobs/recent")
def api_recent_jobs(request: Request, limit: int = 10, location: str = "", country: str = ""):
    """Real, recent job postings matched + ranked (most → least fitting) to the
    signed-in student's skills, target role, and country. Live multi-source feed
    with a short cache; curated offline fallback when feeds are unreachable."""
    user = _current_user(request)
    loc = location or user.get("location") or ""
    cty = country or user.get("country") or ""
    skills = []
    context = {"country": cty, "role": ""}
    if user["role"] == "Student":
        student = models.get_student_by_user(user["id"])
        if student:
            for s in student.get("self_reported_skills") or []:
                skills.append((s["name"], s.get("level") or "Beginner"))
            for v in student.get("verified_skills") or []:
                skills.append((v["name"], v.get("level") or "Intermediate"))
            role = (student.get("target_role") or {}).get("title")
            context["role"] = role or ""
            if student.get("university"):
                # derive a likely country from their university if no user country
                pass
    elif user["role"] == "Company":
        # Companies see general recent openings so they can gauge the market.
        context["role"] = ""
    return jobs.recent_jobs(skills=skills, role=context["role"],
                            country=context["country"],
                            limit=min(max(int(limit), 1), 16))


# ------------------------------------------------------------------ public verified-skills profile

@app.get("/api/public/verified/{student_id}")
def api_public_verified(student_id: int):
    """Read-only, no-auth snapshot of a student's VERIFIED skills. Only served
    when the student has explicitly enabled sharing; verification evidence is
    the assessment-pass date, never self-reported claims."""
    student = models.get_student(student_id)
    if not student or not student.get("share_public"):
        raise HTTPException(status_code=404, detail="Profile not shared")
    role = student.get("target_role")
    return {
        "student_id": student["id"],
        "name": student["name"],
        "university": student["university"],
        "target_role": {"title": role["title"], "company": role.get("company_name")} if role else None,
        "verified_skills": [
            {"skill_id": v["skill_id"], "name": v["name"], "category": v.get("category"),
             "level": v["level"], "verified_at": v.get("verified_at")}
            for v in student["verified_skills"]
        ],
    }


# ------------------------------------------------------------------ university

@app.get("/api/university/cohort")
def api_university_cohort(request: Request):
    user = _current_user(request)
    _require_roles(user, "University Admin")
    students = models.list_students()
    return {
        "student_count": len(students),
        "confirmed_count": sum(1 for s in students if s.get("cohort_confirmed")),
        "min_cohort_size": MIN_COHORT_SIZE,
        # anonymized — never names/emails; only index + confirmation status
        "students": [{"index": i + 1, "confirmed": bool(s.get("cohort_confirmed"))}
                     for i, s in enumerate(students)],
    }


@app.post("/api/university/cohort/confirm")
def api_university_confirm(request: Request):
    user = _current_user(request)
    _require_roles(user, "University Admin")
    with get_cursor() as conn:
        conn.execute("UPDATE students SET cohort_confirmed=1")
    return api_university_cohort(request)


@app.get("/api/university/stats")
def api_university_stats(request: Request):
    user = _current_user(request)
    _require_roles(user, "University Admin")
    students = models.list_students()
    confirmed = sum(1 for s in students if s.get("cohort_confirmed"))
    if confirmed < MIN_COHORT_SIZE:
        return {"rule": {"min_cohort_size": MIN_COHORT_SIZE, "satisfied": False,
                         "student_count": len(students), "confirmed_count": confirmed},
                "stats": None,
                "message": f"Not enough confirmed students to compute statistics (need at least {MIN_COHORT_SIZE})."}
    analysis_rows = []
    for s in students:
        if not s.get("cohort_confirmed"):
            continue
        a = matching.analyze_student(s["id"])
        if a:
            analysis_rows.append(a)

    skill_stats = {}
    for a in analysis_rows:
        for gap in a["skill_gaps"]:
            key = gap["skill_name"]
            entry = skill_stats.setdefault(key, {"skill_name": key, "category": gap.get("category"),
                                                 "count": 0, "strong": 0, "gap": 0, "missing": 0})
            entry["count"] += 1
            entry[gap["status"]] += 1

    ordered = list(skill_stats.values())
    for e in ordered:
        e["need_improvement_pct"] = round((e["gap"] + e["missing"]) / e["count"] * 100, 1) if e["count"] else 0
    ordered = sorted(ordered, key=lambda e: -e["need_improvement_pct"])

    avg_scores = [a["match_score"] for a in analysis_rows]
    return {
        "rule": {"min_cohort_size": MIN_COHORT_SIZE, "satisfied": True,
                 "student_count": len(students), "confirmed_count": confirmed},
        "student_count": len(students),
        "with_target_role": len(analysis_rows),
        "average_match_score": round(sum(avg_scores) / len(avg_scores), 1) if avg_scores else 0,
        "skill_stats": ordered,
        "verified_skills_total": _count_verified(),
        "assessments_total": len(models.list_assessment_attempts()),
    }


def _count_verified():
    from .database import get_cursor
    with get_cursor() as c:
        return c.execute("SELECT COUNT(*) AS n FROM verified_skills").fetchone()["n"]


# ------------------------------------------------------------------ static frontend

def _mount_frontend():
    dist = Path(FRONTEND_DIST)
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and str(candidate).startswith(str(dist.resolve())):
            return FileResponse(str(candidate))
        index = dist / "index.html"
        if index.is_file():
            return FileResponse(str(index))
        return {"service": "SkillBridge API",
                "frontend": "run `npm run build` in frontend/ or use start.sh"}


_mount_frontend()