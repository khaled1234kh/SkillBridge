"""SkillBridge FastAPI application.

Single app serving both the REST API and the built React frontend.
"""
import json
import os
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import models, matching, genai, integrity, seed
from .database import init_db

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


@app.on_event("startup")
def on_startup():
    from .database import DB_PATH
    if not os.path.exists(DB_PATH):
        seed.seed()


# ------------------------------------------------------------------ auth

def _require_user(user_id: int):
    user = models.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _resolve_role_context(user):
    """Return (entity_type, entity) for a logged-in user."""
    if user["role"] == "Student":
        return "student", models.get_student_by_user(user["id"])
    if user["role"] == "Company":
        return "company", models.get_company_by_user(user["id"])
    return "university", None


@app.post("/api/login")
def login(body: dict):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    user = models.get_user_by_email(email)
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    entity_type, entity = _resolve_role_context(user)
    return {"id": user["id"], "email": user["email"], "role": user["role"],
            "display_name": user["display_name"], "entity_type": entity_type,
            "entity_id": entity["id"] if entity else None}


@app.get("/api/me/{user_id}")
def me(user_id: int):
    user = _require_user(user_id)
    entity_type, entity = _resolve_role_context(user)
    payload = {"id": user["id"], "email": user["email"], "role": user["role"],
               "display_name": user["display_name"], "entity_type": entity_type}
    if entity_type == "student":
        payload["student"] = entity
        payload["analysis"] = matching.analyze_student(entity["id"])
    elif entity_type == "company":
        payload["company"] = entity
        payload["roles"] = models.get_roles_by_company(entity["id"])
    return payload


# ------------------------------------------------------------------ skills catalog

@app.get("/api/skills")
def api_list_skills():
    return models.list_skills()


@app.post("/api/skills")
def api_create_skill(body: dict):
    return models.create_skill(body["name"], body.get("category", "General"))


@app.put("/api/skills/{skill_id}")
def api_update_skill(skill_id: int, body: dict):
    models.update_skill(skill_id, body.get("name"), body.get("category"))
    return models.get_skill(skill_id)


@app.delete("/api/skills/{skill_id}")
def api_delete_skill(skill_id: int):
    return {"deleted": models.delete_skill(skill_id)}


# ------------------------------------------------------------------ companies

@app.get("/api/companies")
def api_list_companies():
    return models.list_companies()


@app.post("/api/companies")
def api_create_company(body: dict):
    return models.create_company(body["name"], body.get("industry", ""), body.get("user_id"))


@app.delete("/api/companies/{company_id}")
def api_delete_company(company_id: int):
    models.delete_company(company_id)
    return {"deleted": True}


# ------------------------------------------------------------------ roles

@app.get("/api/roles")
def api_list_roles():
    return models.list_roles()


@app.get("/api/roles/{role_id}")
def api_get_role(role_id: int):
    role = models.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@app.post("/api/roles")
def api_create_role(body: dict):
    company_id = body["company_id"]
    return models.create_role(company_id, body["title"],
                              body.get("required_skills", []), body.get("description"))


@app.put("/api/roles/{role_id}")
def api_update_role(role_id: int, body: dict):
    models.update_role(role_id, body.get("title"), body.get("description"),
                       body.get("required_skills"))
    return models.get_role(role_id)


@app.delete("/api/roles/{role_id}")
def api_delete_role(role_id: int):
    models.delete_role(role_id)
    return {"deleted": True}


# ------------------------------------------------------------------ students

@app.get("/api/students")
def api_list_students():
    return models.list_students()


@app.get("/api/students/{student_id}")
def api_get_student(student_id: int):
    student = models.get_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@app.post("/api/students")
def api_create_student(body: dict):
    return models.create_student(body["name"], body["email"], body.get("university", ""),
                                 body.get("user_id"))


@app.put("/api/students/{student_id}")
def api_update_student(student_id: int, body: dict):
    fields = {k: v for k, v in body.items() if k in
              ("name", "email", "university", "target_role_id", "cv_filename")}
    return models.update_student(student_id, **fields)


@app.delete("/api/students/{student_id}")
def api_delete_student(student_id: int):
    models.delete_student(student_id)
    return {"deleted": True}


# ------------------------------------------------------------------ CV upload + extraction

@app.post("/api/students/{student_id}/cv")
def upload_cv(student_id: int, file: UploadFile = File(...)):
    content_bytes = file.file.read()
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
def api_student_analysis(student_id: int):
    analysis = matching.analyze_student(student_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Student has no target role")
    return analysis


# ------------------------------------------------------------------ learning

@app.post("/api/students/{student_id}/learning/generate")
def api_generate_learning(student_id: int, body: dict):
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
                                       item["practice_exercise"], item["mini_project"])


@app.get("/api/students/{student_id}/learning")
def api_list_learning(student_id: int):
    return models.list_learning_path(student_id)


# ------------------------------------------------------------------ AI tutor

@app.get("/api/students/{student_id}/tutor")
def api_tutor_history(student_id: int, skill_id: int = None):
    return models.list_tutor_messages(student_id, skill_id)


@app.post("/api/students/{student_id}/tutor")
def api_tutor_chat(student_id: int, body: dict):
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
def api_generate_assessment(student_id: int, body: dict):
    skill_id = body["skill_id"]
    student = models.get_student(student_id)
    role = student.get("target_role")
    skill = models.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    questions = genai.generate_quiz(skill["name"], role["title"] if role else "", num_questions=4)
    return {"skill": skill, "questions": questions}


@app.post("/api/students/{student_id}/assessments")
def api_submit_assessment(student_id: int, body: dict):
    skill_id = body["skill_id"]
    questions = body.get("questions", [])
    answers = body.get("answers", [])
    total_seconds = body.get("total_seconds")
    tab_switches = int(body.get("tab_switches") or 0)
    free_text_answers = body.get("free_text_answers") or []

    skill = models.get_skill(skill_id)
    student = models.get_student(student_id)

    flags = integrity.evaluate_attempt(len(questions), total_seconds, free_text_answers, tab_switches)

    # score multiple choice exactly; free text by keyword overlap against model answer
    correct = 0
    for i, q in enumerate(questions):
        ans = (answers[i] if i < len(answers) else "").strip().lower()
        model_ans = (q.get("answer") or "").strip().lower()
        if not model_ans:
            continue
        if q.get("type") == "multiple_choice":
            if ans == model_ans:
                correct += 1
        else:
            model_words = set(model_ans.split())
            ans_words = set(ans.split())
            if model_words and len(model_words & ans_words) / len(model_words) >= 0.4:
                correct += 1
    score = round((correct / max(len(questions), 1)) * 100, 1)
    passed = score >= PASS_THRESHOLD and not any(f["severity"] == "high" for f in flags)

    # level before/after
    level, _ = matching.effective_skill_level(student, skill_id)
    before = level or "Beginner"
    order = ["Beginner", "Intermediate", "Advanced"]
    after = before
    if passed:
        after = order[min(order.index(before) + (0 if order.index(before) == 2 else 1), 2)]

    models.create_assessment_attempt(student_id, skill_id, json.dumps(questions),
                                     json.dumps(answers), score, int(passed),
                                     json.dumps(flags), before, after)
    if passed:
        models.update_verified_skill(student_id, skill_id, after)

    return {
        "score": score,
        "passed": passed,
        "flags": flags,
        "questions": questions,
        "answers": answers,
        "level_before": before,
        "level_after": after,
        "analysis": matching.analyze_student(student_id),
    }


@app.get("/api/students/{student_id}/assessments")
def api_list_assessments(student_id: int):
    return models.list_assessment_attempts(student_id=student_id)


@app.get("/api/assessments")
def api_all_assessments():
    return models.list_assessment_attempts()


# ------------------------------------------------------------------ university

@app.get("/api/university/stats")
def api_university_stats():
    students = models.list_students()
    if len(students) < MIN_COHORT_SIZE:
        return {"rule": {"min_cohort_size": MIN_COHORT_SIZE, "satisfied": False,
                         "student_count": len(students)}, "stats": None,
                "message": f"Not enough students to compute statistics (need at least {MIN_COHORT_SIZE})."}
    analysis_rows = []
    for s in students:
        a = matching.analyze_student(s["id"])
        if a:
            analysis_rows.append(a)

    # aggregate per-required-skill statuses across all students with a target role
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

    avg_scores = [a["match_score"] for a in analysis_rows]
    return {
        "rule": {"min_cohort_size": MIN_COHORT_SIZE, "satisfied": True, "student_count": len(students)},
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
    app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(dist / "index.html"))


_mount_frontend()
