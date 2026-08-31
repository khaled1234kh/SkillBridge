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
        # each step carries real, titled source links (not bare rank numbers)
        assert isinstance(s.get("resources"), list) and s["resources"]
        item_urls = {r["url"] for r in item["resources"]}
        for r in s["resources"]:
            assert r["url"].startswith("http") and r["title"]
            assert r["url"] in item_urls  # step sources come from the ranked list
        assert s["resource_ranks"] and len(s["resource_ranks"]) == len(s["resources"])


def test_roadmap_steps_source_from_spread_resources():
    """Steps should draw from a spread of the ranked resources, never repeat the
    exact same source list as their neighbour, and together use the full list."""
    item = genai.generate_learning_item("SQL", "Data", "Data Analyst",
                                        "Studying at Aston University")
    per_step = {tuple(r["url"] for r in s["resources"]) for s in item["roadmap"]["steps"]}
    urls = [r["url"] for s in item["roadmap"]["steps"] for r in s["resources"]]
    item_urls = {r["url"] for r in item["resources"]}
    # every resource is cited somewhere in the roadmap
    assert item_urls <= set(urls)
    # consecutive steps never show the identical source list
    for a, b in zip(item["roadmap"]["steps"], item["roadmap"]["steps"][1:]):
        assert [r["url"] for r in a["resources"]] != [r["url"] for r in b["resources"]]
    # real titled sources, not bare rank numbers
    assert all(r["title"] for r in item["roadmap"]["steps"][0]["resources"])


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
