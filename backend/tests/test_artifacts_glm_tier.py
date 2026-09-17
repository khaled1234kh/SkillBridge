"""GLM-tier career artifacts + conversation-memory enrichment.

``ARTIFACT_MODEL`` (env-optional; served on NVIDIA NIM with the SAME key and
base URL as the interactive model — only the model string differs) is used ONLY
for latency-tolerant, low-frequency quality work:
  A) career artifacts: resume / cover letter / 6-month career plan, built from
     verified skills + target role + identity (advisory output only — it can
     never create or override Verified-Skill authority), and
  B) background conversation-memory enrichment (never blocks a reply; the
     deterministic digest always stands).

Interactive paths (chart/chat/live) must keep using the configured ``NIM_MODEL``
and must never route through the artifact model. Every artifact provider
failure resolves to a DETERMINISTIC draft built from the same trusted facts —
generation never fails and never invents claims.
"""

import pytest

from app import genai

ARTIFACT_MODEL = "z-ai/glm-5.3"


@pytest.fixture()
def artifact_enabled(monkeypatch):
    """Mirror the production ``env`` (ARTIFACT_MODEL set + a NIM key) so the
    artifact path is live while the interactive path still uses NIM_MODEL."""
    monkeypatch.setattr(genai, "ARTIFACT_MODEL", ARTIFACT_MODEL)
    monkeypatch.setattr(genai, "NIM_KEY", "nvapi-test-key")
    return genai


def _sample_skills():
    return {
        "verified_skills": [{"name": "Python", "level": "Advanced"}],
        "self_reported_skills": [{"name": "SQL", "level": "Beginner"}],
    }


def _msgs():
    return [
        {"id": 1, "role": "user", "content": "I want to become an AI Engineer."},
        {"id": 2, "role": "assistant", "content": "Let's plan that — start with Python."},
        {"id": 3, "role": "user", "content": "What about Docker?"},
        {"id": 4, "role": "assistant", "content": "Docker containers package apps."},
    ]


# ------------------------------------------------------------------ routing


def test_artifact_generation_routes_to_artifact_model_with_thinking_off(artifact_enabled, monkeypatch):
    calls = []

    def fake_call(system, user, **kwargs):
        calls.append((system, user, kwargs))
        return "A tailored GLM resume for Aisha Rahman, targeting an AI Engineering role at a technology company."

    monkeypatch.setattr(artifact_enabled, "_call_nim", fake_call)
    text, provider = artifact_enabled.generate_career_artifact(
        "resume", display_name="Aisha Rahman", target_role="AI Engineer",
        **_sample_skills(),
    )
    assert provider == "real"
    assert text == ("A tailored GLM resume for Aisha Rahman, targeting an AI "
                    "Engineering role at a technology company.")
    assert len(calls) == 1
    assert "Aisha Rahman" in calls[0][1]
    assert "AI Engineer" in calls[0][1]
    assert "Python (Advanced)" in calls[0][1]
    kwargs = calls[0][2]
    assert kwargs["model"] == ARTIFACT_MODEL
    assert kwargs["thinking"] is False
    assert kwargs["retries"] == 2, "artifact draws arm the bounded single-retry (2 attempts max)"
    assert kwargs["timeout"] == artifact_enabled.ARTIFACT_TIMEOUT_SECONDS


def test_artifact_generation_never_changes_verified_skill_input(artifact_enabled, monkeypatch):
    calls = []

    def fake_call(system, user, **kwargs):
        calls.append((system, user, kwargs))
        return "Some fuller GLM resume text that comfortably exceeds the minimum length floor."

    monkeypatch.setattr(artifact_enabled, "_call_nim", fake_call)
    artifact_enabled.generate_career_artifact(
        "career_plan", display_name="Aisha", target_role="AI Engineer",
        verified_skills=[{"name": "Python", "level": "Advanced"}],
        self_reported_skills=[{"name": "Python", "level": "Advanced"},
                              {"name": "SQL", "level": "Beginner"}],
    )
    # A skill self-reported-only must not be deduped away, and verified facts
    # pass through verbatim — the caller's trusted rows are authoritative.
    assert "Python (Advanced)" in calls[0][1]
    assert "SQL" in calls[0][1]


def test_interactive_complete_path_never_uses_artifact_model(artifact_enabled, monkeypatch):
    calls = []

    def fake_call(system, user, **kwargs):
        calls.append(kwargs)
        return "hello from nemotron"

    monkeypatch.setattr(artifact_enabled, "_call_nim", fake_call)
    reply = artifact_enabled.complete("sys", "usr")
    assert reply == "hello from nemotron"
    assert len(calls) == 1
    assert calls[0].get("model") is None
    assert ARTIFACT_MODEL not in str(calls[0])
    assert calls[0]["max_tokens"] == 1024


# ------------------------------------------------------------------ fallbacks


def test_deterministic_fallback_when_artifact_model_unset(monkeypatch):
    monkeypatch.setattr(genai, "ARTIFACT_MODEL", None)
    monkeypatch.setattr(genai, "NIM_KEY", "nvapi-test-key")

    def boom(*a, **k):
        raise AssertionError("provider must not be called without ARTIFACT_MODEL")

    monkeypatch.setattr(genai, "_call_nim", boom)
    text, provider = genai.generate_career_artifact(
        "resume", display_name="Aisha Rahman", target_role="AI Engineer",
        **_sample_skills(),
    )
    assert provider == "deterministic-fallback"
    assert "Aisha Rahman" in text
    assert "AI Engineer" in text
    assert "- Python (Advanced)" in text
    assert "review before sharing" in text


def test_deterministic_fallback_on_provider_failure(artifact_enabled, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("NIM down")

    monkeypatch.setattr(artifact_enabled, "_call_nim", boom)
    text, provider = artifact_enabled.generate_career_artifact(
        "resume", display_name="Aisha Rahman", target_role="AI Engineer",
        **_sample_skills(),
    )
    assert provider == "deterministic-fallback"
    assert "Aisha Rahman" in text
    assert "AI Engineer" in text


def test_generate_rejects_unknown_kind(artifact_enabled):
    with pytest.raises(ValueError):
        artifact_enabled.generate_career_artifact(
            "novel", display_name="Aisha", target_role="AI Engineer", **_sample_skills())


# ------------------------------------------------------------------ enrichment


def test_memory_enrichment_routes_to_artifact_model_and_is_bounded(monkeypatch):
    from app import tutor_memory

    calls = []

    def fake_artifact(system, user, max_tokens=700):
        calls.append((system, user, max_tokens))
        return "The student targets an AI Engineering role and is exploring Docker containers with the mentor."

    monkeypatch.setattr("app.tutor_memory.genai.artifact_model_enabled", lambda: True)
    monkeypatch.setattr("app.tutor_memory.genai._call_artifact", fake_artifact)
    enriched = tutor_memory._enrich_digest_with_artifact(_msgs(), previous="")
    assert calls
    assert enriched == ("The student targets an AI Engineering role and is "
                        "exploring Docker containers with the mentor.")
    assert len(enriched) <= tutor_memory.SUMMARY_CHAR_CAP


def test_memory_enrichment_bounded_to_cap(monkeypatch):
    from app import tutor_memory

    def fake_artifact(system, user, max_tokens=700):
        return "word " * 50000

    monkeypatch.setattr("app.tutor_memory.genai.artifact_model_enabled", lambda: True)
    monkeypatch.setattr("app.tutor_memory.genai._call_artifact", fake_artifact)
    enriched = tutor_memory._enrich_digest_with_artifact(_msgs(), previous="")
    assert enriched
    assert len(enriched) <= tutor_memory.SUMMARY_CHAR_CAP


def test_memory_enrichment_disabled_returns_empty_and_never_calls_provider(monkeypatch):
    from app import tutor_memory

    def bad(*a, **k):
        raise AssertionError("provider must not be called when artifact model is off")

    monkeypatch.setattr("app.tutor_memory.genai.artifact_model_enabled", lambda: False)
    monkeypatch.setattr("app.tutor_memory.genai._call_artifact", bad)
    assert tutor_memory._enrich_digest_with_artifact(_msgs(), previous="") == ""


def test_memory_enrichment_provider_failure_returns_empty(monkeypatch):
    from app import tutor_memory

    def boom(*a, **k):
        raise RuntimeError("GLM timeout")

    monkeypatch.setattr("app.tutor_memory.genai.artifact_model_enabled", lambda: True)
    monkeypatch.setattr("app.tutor_memory.genai._call_artifact", boom)
    assert tutor_memory._enrich_digest_with_artifact(_msgs(), previous="") == ""


# ------------------------------------------------------------------ endpoint


def test_artifact_endpoint_deterministic_when_unset(client, auth_headers, student_id):
    headers = auth_headers("aisha@student.edu")
    r = client.post(f"/api/students/{student_id}/artifacts", headers=headers,
                    json={"kind": "resume", "language": "en"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "resume"
    assert data["language"] == "en"
    assert data["artifact"]
    assert data["genai_provider"] == "deterministic-fallback"
    assert "Aisha" in data["artifact"]
    assert "Python" in data["artifact"]


def test_artifact_endpoint_uses_artifact_model(artifact_enabled, client, auth_headers,
                                               student_id, monkeypatch):
    calls = []

    def fake_call(system, user, **kwargs):
        calls.append(kwargs)
        return "A professional GLM cover letter written for Aisha Rahman, a SkillBridge student."

    monkeypatch.setattr(artifact_enabled, "_call_nim", fake_call)
    headers = auth_headers("aisha@student.edu")
    r = client.post(f"/api/students/{student_id}/artifacts", headers=headers,
                    json={"kind": "cover_letter", "language": "en"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "cover_letter"
    assert data["genai_provider"] == "real"
    assert calls
    assert calls[0]["model"] == ARTIFACT_MODEL
    assert calls[0]["thinking"] is False


def test_artifact_endpoint_arabic(client, auth_headers, student_id):
    headers = auth_headers("aisha@student.edu")
    r = client.post(f"/api/students/{student_id}/artifacts", headers=headers,
                    json={"kind": "career_plan", "language": "ar"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["language"] == "ar"
    assert any("\u0600" <= ch <= "\u06ff" for ch in data["artifact"])


def test_artifact_endpoint_requires_auth(client):
    r = client.post("/api/students/1/artifacts", json={"kind": "resume", "language": "en"})
    assert r.status_code == 401


def test_artifact_endpoint_forbids_other_student(client, auth_headers):
    headers = auth_headers("omar@student.edu")
    r = client.post("/api/students/1/artifacts", headers=headers,
                    json={"kind": "resume", "language": "en"})
    assert r.status_code in (403, 404)


def test_artifact_endpoint_rejects_bad_kind(client, auth_headers, student_id):
    headers = auth_headers("aisha@student.edu")
    r = client.post(f"/api/students/{student_id}/artifacts", headers=headers,
                    json={"kind": "poem", "language": "en"})
    assert r.status_code == 400


def test_artifact_endpoint_rejects_bad_language(client, auth_headers, student_id):
    headers = auth_headers("aisha@student.edu")
    r = client.post(f"/api/students/{student_id}/artifacts", headers=headers,
                    json={"kind": "resume", "language": "fr"})
    assert r.status_code == 400


# ------------------------------------------------------------------ retry


class _FakeResp:
    """Minimal httpx.Response stand-in for the provider-call tests."""

    def __init__(self, status_code=200, body=None, body_parse_error=False):
        self.status_code = status_code
        self._body = body
        self._body_parse_error = body_parse_error

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx as _httpx
            raise _httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=_httpx.Request("POST", "http://fake.nim"),
                response=self,
            )

    def json(self):
        if self._body_parse_error:
            raise ValueError("no json body")
        return self._body


def _empty_stream_resp():
    return _FakeResp(200, {"choices": [{"message": {"content": ""}}]})


def _nim_clean_state(monkeypatch, key="nvapi-test-key", model="nvidia/nemotron-3-super-120b-a12b"):
    monkeypatch.setattr(genai, "NIM_KEY", key)
    monkeypatch.setattr(genai, "NIM_MODEL", model)
    monkeypatch.setattr(genai, "_nim_circuit", {"failures": 0, "open_until": 0.0})


def test_call_nim_first_draw_drops_second_succeeds_returns_content(monkeypatch):
    """Bounded single-retry: 200-with-empty-stream (measured ~1/3 rapid-fire
    drop) is retried once and the second draw's content is returned."""
    import httpx

    calls = []

    def fake_post(url, **kw):
        calls.append(kw.get("timeout"))
        if len(calls) == 1:
            return _empty_stream_resp()
        return _FakeResp(200, {"choices": [{"message": {"content": "A complete resume text that is long enough."}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    _nim_clean_state(monkeypatch)
    out = genai._call_nim("sys", "usr", retries=2, timeout=60)
    assert out == "A complete resume text that is long enough."
    assert len(calls) == 2, "exactly ONE retry after the drop (2 attempts total)"
    assert calls[0] == 60


def test_call_nim_first_503_second_succeeds(monkeypatch):
    """HTTP 503 (overload) is retried once; content from the second draw."""
    import httpx

    calls = []

    def fake_post(url, **kw):
        calls.append(kw.get("timeout"))
        if len(calls) == 1:
            return _FakeResp(503, {"error": {"message": "Service temporarily overloaded"}})
        return _FakeResp(200, {"choices": [{"message": {"content": "A second-draw answer that is not empty."}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    _nim_clean_state(monkeypatch)
    out = genai._call_nim("sys", "usr", retries=2, timeout=60)
    assert out == "A second-draw answer that is not empty."
    assert len(calls) == 2


def test_call_nim_both_draws_drop_artifact_falls_back_cleanly(artifact_enabled, monkeypatch):
    """Both attempts drop (empty stream): after exactly 2 attempts the artifact
    generator resolves to its deterministic draft — clean fallback, 200 OK."""
    import httpx

    calls = []

    def fake_post(url, **kw):
        calls.append(1)
        return _empty_stream_resp()

    monkeypatch.setattr(httpx, "post", fake_post)
    _nim_clean_state(monkeypatch)
    text, provider = artifact_enabled.generate_career_artifact(
        "resume", display_name="Aisha Rahman", target_role="AI Engineer", **_sample_skills())
    assert provider == "deterministic-fallback"
    assert "Aisha Rahman" in text
    assert len(calls) == 2, "one bounded retry happens before the clean fallback"


def test_call_nim_never_retries_4xx(monkeypatch):
    """A 4xx (incl. 429) is NOT retried — exactly one attempt, immediate raise
    (the raw provider error propagates, exactly like pre-retry behavior for
    non-retryable statuses; callers catch it into their fallbacks)."""
    import httpx

    calls = []

    def fake_post(url, **kw):
        calls.append(1)
        return _FakeResp(429, {"error": {"message": "rate limited"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    _nim_clean_state(monkeypatch)
    with pytest.raises(httpx.HTTPStatusError) as ei:
        genai._call_nim("sys", "usr", retries=2, timeout=60)
    assert ei.value.response.status_code == 429
    assert len(calls) == 1


def test_call_nim_never_retries_200_with_content(monkeypatch):
    """A healthy 200-with-content is returned on the FIRST draw — no second
    provider call ever happens for a successful draw."""
    import httpx

    calls = []

    def fake_post(url, **kw):
        calls.append(1)
        return _FakeResp(200, {"choices": [{"message": {"content": "healthy first draw"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    _nim_clean_state(monkeypatch)
    assert genai._call_nim("sys", "usr", retries=2, timeout=60) == "healthy first draw"
    assert len(calls) == 1


def test_call_nim_skips_retry_when_remaining_budget_under_half(monkeypatch):
    """The retry is SKIPPED when less than half the path budget remains — a
    single slow draw must never exceed the bound (interactive guard / artifact
    timeout) by landing a second full draw."""
    import time as _time
    import httpx

    calls = []

    def fake_post(url, **kw):
        calls.append(kw.get("timeout"))
        _time.sleep(0.6)  # consume > half of the 1.0s budget on the first draw
        return _empty_stream_resp()

    monkeypatch.setattr(httpx, "post", fake_post)
    _nim_clean_state(monkeypatch)
    t0 = _time.time()
    with pytest.raises(RuntimeError):
        genai._call_nim("sys", "usr", retries=2, timeout=1.0)
    elapsed = _time.time() - t0
    assert len(calls) == 1, "no second draw when the budget gate is closed"
    assert elapsed < 2.0, "the bound is not blown by a gated retry"