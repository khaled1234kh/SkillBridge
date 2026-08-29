"""Phase 2 — CV skill-extraction pipeline using a fixture CV."""
import io

from app import genai, models


FIXTURE_CV = """\
Aisha Rahman
BSc Computer Science, Aston University

KEY SKILLS
Python (Advanced), Machine Learning (Intermediate), Docker (Beginner), SQL (Advanced)

PROJECTS
Built a machine learning dashboard and deployed a Docker container.
EXPERIENCE
Worked with SQL databases and Python scripting during an internship.
"""


def test_extract_skills_returns_structured_list():
    result = genai.extract_skills_from_cv(FIXTURE_CV)
    assert isinstance(result, list) and len(result) > 0
    for item in result:
        assert "name" in item and "level" in item and "category" in item
        assert item["level"] in ("Beginner", "Intermediate", "Advanced")
        assert item["name"].strip()


def test_extract_picks_up_known_skills():
    result = genai.extract_skills_from_cv(FIXTURE_CV)
    names = {r["name"].lower() for r in result}
    assert "python" in names and "sql" in names


def test_cv_upload_via_api_populates_self_reported(client, student_id):
    res = client.post(
        f"/api/students/{student_id}/cv",
        files={"file": ("aisha_cv.txt", io.BytesIO(FIXTURE_CV.encode()), "text/plain")},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["extracted"]) > 0
    # persisted to the student profile
    student = models.get_student(student_id)
    assert len(student["self_reported_skills"]) > 0
    # uploaded filename persisted
    assert student["cv_filename"] == "aisha_cv.txt"


def test_extraction_uses_real_or_fallback_provider_but_not_hardcoded_empty():
    # Ensure the provider path returns content regardless of API key presence;
    # verify that supplying empty/garbage CV text still yields a non-empty list.
    result = genai.extract_skills_from_cv("")
    assert len(result) > 0
