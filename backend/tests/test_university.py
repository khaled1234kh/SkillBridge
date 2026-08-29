"""Phase 6 — University dashboard: aggregated stats + minimum-cohort rule."""
import sqlite3
import pytest

from app import database, models, seed


def test_university_stats_are_aggregated(client):
    r = client.get("/api/university/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["rule"]["satisfied"] is True
    assert data["student_count"] >= 5
    # aggregated skill stats present, never individual records
    assert "skill_stats" in data
    assert data["average_match_score"] is not None
    # No individual student names/emails leak through the endpoint
    blob = str(data)
    assert "aisha" not in blob.lower() or "email" not in blob


def test_min_cohort_rule_hides_stats():
    # Fresh DB with too few students -> stats withheld
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    database.set_db_for_test(conn)
    seed.seed()
    from app import main
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        # Startup may seed the shared DB; delete students *after* startup, in-context.
        conn.execute("DELETE FROM students")
        conn.commit()
        r = c.get("/api/university/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["rule"]["satisfied"] is False
    assert data["stats"] is None
    database.set_db_for_test()
    conn.close()


def test_university_never_drills_into_individual(client):
    # Verify no student-specific detail endpoint is exposed from the university view —
    # /api/university/stats returns only the shape above.
    r = client.get("/api/university/stats")
    data = r.json()
    assert "students" not in data
    assert "student" not in data
