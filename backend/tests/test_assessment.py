"""Phase 5 — Proctored assessment: scoring, flag logic, verified-profile update."""
from app import integrity, models


def test_timing_anomaly_flag():
    flags = integrity.evaluate_attempt(question_count=4, total_seconds=30,
                                       free_text_answers=[], local_tab_switches=0)
    codes = {f["code"] for f in flags}
    assert "timing_anomaly" in codes


def test_tab_switch_flag():
    flags = integrity.evaluate_attempt(4, 300, [], local_tab_switches=2)
    assert sum(1 for f in flags if f["code"] == "tab_switch") == 2


def test_ai_text_detection():
    polished = ("In conclusion, the comprehensive approach leverages robust infrastructure "
                "to streamline operations. Furthermore, it is essential to harness state-of-the-art "
                "methodologies. Moreover, we utilize cutting-edge techniques.")
    flagged, flag = integrity.detect_ai_text(polished)
    assert flagged and any(f["code"] == "ai_text" for f in flag)

    plain = "I set up docker and ran the container. It worked."
    flagged, flag = integrity.detect_ai_text(plain)
    assert not flagged


def test_evaluate_merges_client_and_server_flags():
    flags = integrity.evaluate_attempt(4, 60, ["In conclusion, robust and comprehensive work"],
                                       local_tab_switches=1)
    codes = {f["code"] for f in flags}
    assert "tab_switch" in codes and "ai_text" in codes


def test_high_severity_flag_forces_fail(client, student_id, auth_headers):
    # Generate a quiz, answer everything with the model answer (would otherwise pass),
    # but include a clearly AI-styled free-text answer which is a high-severity flag.
    headers = auth_headers("aisha@student.edu")
    docker = models.get_skill_by_name("Docker")
    r = client.post(f"/api/students/{student_id}/assessments/generate",
                    json={"skill_id": docker["id"]}, headers=headers)
    assert r.status_code == 200
    questions = r.json()["questions"]
    answers = [q["answer"] for q in questions]
    poisoned = "In conclusion, we leverage a robust and comprehensive framework. Furthermore, it is essential to utilize cutting-edge and seamless approaches. Moreover, this streamlines and harnesses state-of-the-art methodologies for overall improvement."
    res = client.post(f"/api/students/{student_id}/assessments", json={
        "skill_id": docker["id"], "questions": questions, "answers": answers,
        "total_seconds": 300, "tab_switches": 0,
        "free_text_answers": [poisoned],
    }, headers=headers)
    data = res.json()
    assert data["score"] >= 70  # semantically answered correctly
    assert data["passed"] is False  # but high-severity ai_text flag forces fail
    assert any(f["code"] == "ai_text" for f in data["flags"])


def test_clean_pass_updates_verified_profile(client, student_id, auth_headers):
    headers = auth_headers("aisha@student.edu")
    student = models.get_student(student_id)
    docker = models.get_skill_by_name("Docker")
    before_verified = {v["name"] for v in student["verified_skills"]}

    r = client.post(f"/api/students/{student_id}/assessments/generate",
                    json={"skill_id": docker["id"], "num_questions": 10}, headers=headers)
    questions = r.json()["questions"]
    assert len(questions) == 10  # real 10-question assessment
    answers = [q["answer"] for q in questions]

    res = client.post(f"/api/students/{student_id}/assessments", json={
        "skill_id": docker["id"], "questions": questions, "answers": answers,
        "total_seconds": 300, "tab_switches": 0, "free_text_answers": [],
    }, headers=headers)
    data = res.json()
    assert data["passed"] is True
    assert data["score"] >= 70
    assert len(data.get("per_question") or []) == len(questions)

    updated = models.get_student(student_id)
    assert "Docker" in {v["name"] for v in updated["verified_skills"]}
    # skill moved into verified profile
    assert "Docker" in {v["name"] for v in updated["verified_skills"]}


def test_fail_does_not_verify(client, student_id, auth_headers):
    headers = auth_headers("aisha@student.edu")
    # Wrong answers -> score below threshold -> no verification
    skill = models.create_skill("K8s", "DevOps")
    r = client.post(f"/api/students/{student_id}/assessments/generate",
                    json={"skill_id": skill["id"]}, headers=headers)
    questions = r.json()["questions"]
    answers = ["definitely wrong" for _ in questions]
    res = client.post(f"/api/students/{student_id}/assessments", json={
        "skill_id": skill["id"], "questions": questions, "answers": answers,
        "total_seconds": 300, "tab_switches": 0, "free_text_answers": [],
    }, headers=headers)
    data = res.json()
    assert data["passed"] is False
    assert "K8s" not in {v["name"] for v in models.get_student(student_id)["verified_skills"]}


def test_practice_mode_reuses_prior_attempt(client, student_id, auth_headers):
    headers = auth_headers("aisha@student.edu")
    docker = models.get_skill_by_name("Docker")
    # first attempt -> 10 questions
    r = client.post(f"/api/students/{student_id}/assessments/generate",
                    json={"skill_id": docker["id"], "num_questions": 10}, headers=headers)
    questions = r.json()["questions"]
    answers = [q["answer"] for q in questions]
    res = client.post(f"/api/students/{student_id}/assessments", json={
        "skill_id": docker["id"], "questions": questions, "answers": answers,
        "total_seconds": 300, "tab_switches": 0, "free_text_answers": [],
    }, headers=headers)
    assert res.json()["passed"] is True

    # practice mode returns the SAME questions plus previous per-question results
    r = client.post(f"/api/students/{student_id}/assessments/generate",
                    json={"skill_id": docker["id"], "num_questions": 10, "practice": True}, headers=headers)
    data = r.json()
    assert data["practice"] is True
    assert data["previous_score"] is not None
    assert len(data["questions"]) == 10
    assert len(data["previous_results"]) == 10
