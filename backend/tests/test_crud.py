"""Phase 1 / 2 — CRUD tests for each of the five record types."""
import pytest

from app import models


def test_skill_crud(db):
    sk = models.create_skill("Kubernetes", "DevOps")
    assert sk["id"] and sk["name"] == "Kubernetes"
    got = models.get_skill(sk["id"])
    assert got["category"] == "DevOps"
    assert models.update_skill(sk["id"], name="K8s", category="Container") == 1
    got = models.get_skill(sk["id"])
    assert got["name"] == "K8s" and got["category"] == "Container"
    assert models.delete_skill(sk["id"]) == 1
    assert models.get_skill(sk["id"]) is None


def test_company_crud(db):
    c = models.create_company("Acme Data", "Analytics")
    assert c["id"] and c["industry"] == "Analytics"
    assert models.update_company(c["id"], industry="AI") == 1
    assert models.get_company(c["id"])["industry"] == "AI"
    models.delete_company(c["id"])
    assert models.get_company(c["id"]) is None


def test_role_crud(db):
    comp = models.create_company("Acme Data", "Analytics")
    role = models.create_role(comp["id"], "Data Engineer", [
        {"name": "SQL", "category": "Data", "level": "Advanced"},
        {"name": "Python", "category": "Programming", "level": "Intermediate"},
    ])
    assert role["id"]
    assert len(role["required_skills"]) == 2
    assert {s["name"] for s in role["required_skills"]} == {"SQL", "Python"}

    updated = models.update_role(role["id"], title="Senior Data Engineer",
                                 required_skills=[{"name": "SQL", "category": "Data", "level": "Advanced"}])
    assert updated["title"] == "Senior Data Engineer"
    assert len(updated["required_skills"]) == 1

    assert models.delete_role(role["id"]) == 1
    assert models.get_role(role["id"]) is None


def test_student_crud(db):
    s = models.create_student("Test Student", "test@student.edu", "Test University")
    assert s["id"]
    assert models.update_student(s["id"], university="Another University")["university"] == "Another University"
    assert models.get_student(s["id"])["email"] == "test@student.edu"
    models.delete_student(s["id"])
    assert models.get_student(s["id"]) is None


def test_assessment_attempt_crud(db):
    sid = models.create_student("S", "s@student.edu", "U")["id"]
    sk = models.create_skill("TerraformPlus", "DevOps")
    a = models.create_assessment_attempt(
        sid, sk["id"], "[]", '["x"]', 80.0, 1, '[]', "Beginner", "Intermediate")
    assert a["id"] and a["score"] == 80.0 and a["passed"] == 1
    got = models.get_assessment_attempt(a["id"])
    assert got["skill_name"] == "TerraformPlus"
    assert models.delete_assessment_attempt(a["id"]) == 1


def test_user_login_roles(client):
    r = client.post("/api/login", json={"email": "aisha@student.edu", "password": "demo1234"})
    assert r.status_code == 200 and r.json()["role"] == "Student"
    r = client.post("/api/login", json={"email": "hr@northstar.com", "password": "demo1234"})
    assert r.json()["role"] == "Company"
    r = client.post("/api/login", json={"email": "admin@univ.edu", "password": "demo1234"})
    assert r.json()["role"] == "University Admin"
    r = client.post("/api/login", json={"email": "aisha@student.edu", "password": "wrong"})
    assert r.status_code == 401
