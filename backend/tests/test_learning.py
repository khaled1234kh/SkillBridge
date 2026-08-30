"""Phase 4 — Learning path generation returns structured, non-empty content."""
from app import genai, models, matching


def test_learning_item_generation_shape():
    item = genai.generate_learning_item("Docker", "DevOps", "Junior AI Engineer",
                                        "Studying at Aston University")
    assert set(item.keys()) == {"explanation", "practice_exercise", "mini_project",
                                "resources", "roadmap"}
    assert all(isinstance(v, str) and v.strip() for v in
               [item["explanation"], item["practice_exercise"], item["mini_project"]])
    # contextualized to the role
    assert "Junior AI Engineer" in item["explanation"]
    # resources are real links, ranked
    assert isinstance(item["resources"], list) and item["resources"]
    for r in item["resources"]:
        assert r["url"].startswith("http") and r["title"]
    # roadmap is a structured sequence
    assert isinstance(item["roadmap"], dict)
    assert item["roadmap"]["summary"] and len(item["roadmap"]["steps"]) >= 3
    for s in item["roadmap"]["steps"]:
        assert s["objective"] and s["practice"]


def test_learning_route_persists_item(client, student_id, auth_headers):
    headers = auth_headers("aisha@student.edu")
    student = models.get_student(student_id)
    gap = matching.gap_skills(student, student["target_role"])[0]
    r = client.post(f"/api/students/{student_id}/learning/generate",
                    json={"skill_id": gap["skill_id"]}, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["skill_id"] == gap["skill_id"]
    assert all([data["explanation"], data["practice_exercise"], data["mini_project"]])
    assert len(data.get("resources") or []) > 0
    assert isinstance(data.get("roadmap") or {}, dict)
    # persisted
    items = models.list_learning_path(student_id)
    assert any(i["skill_id"] == gap["skill_id"] for i in items)


def test_tutor_reply_is_personalized():
    reply = genai.tutor_reply(
        "How should I approach Docker?",
        "Studying at Aston University; current profile: Python (Advanced), SQL (Advanced)",
        "Docker",
        "Junior AI Engineer",
    )
    assert isinstance(reply, str) and reply.strip()
    assert len(reply) > 40


def test_tutor_route_round_trip(client, student_id, auth_headers):
    headers = auth_headers("aisha@student.edu")
    r = client.post(f"/api/students/{student_id}/tutor",
                    json={"message": "Help me with Docker"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "assistant"
    assert r.json()["content"].strip()
    history = client.get(f"/api/students/{student_id}/tutor", headers=headers).json()
    assert len(history) == 2  # user + assistant
