"""Server-side STT fallback endpoint (Phase 4C.1 Brave blocker).

POST /api/students/{student_id}/tutor/stt accepts a base64 WAV so Live voice
still works from browsers whose Web Speech API cannot reach Google's speech
servers (e.g. Brave). The endpoint is lazy on `speech_recognition`, strips a
RIFF/WAVE container header down to raw PCM, transcribes offline-safe via a
monkeypatched recognizer, and maps recognize failures to honest status codes.

Never calls a paid API.
"""

import base64
import struct

import pytest

import app.jobs as jobs_mod


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(jobs_mod, "_fetch_all", lambda *a, **k: [])
    jobs_mod.clear_job_cache()


def _wav_bytes(rate=16000, bits=16, channels=1, payload=b"\x00\x00" * 100):
    bytes_per_sample = bits // 8
    block_align = channels * bytes_per_sample
    data_len = len(payload)
    header = bytearray(44)
    header[0:4] = b"RIFF"
    struct.pack_into("<I", header, 4, 36 + data_len)
    header[8:12] = b"WAVE"
    header[12:16] = b"fmt "
    struct.pack_into("<I", header, 16, 16)
    struct.pack_into("<H", header, 20, 1)          # PCM
    struct.pack_into("<H", header, 22, channels)
    struct.pack_into("<I", header, 24, rate)
    struct.pack_into("<I", header, 28, rate * block_align)
    struct.pack_into("<H", header, 32, block_align)
    struct.pack_into("<H", header, 34, bits)
    header[36:40] = b"data"
    struct.pack_into("<I", header, 40, data_len)
    return bytes(header) + payload


def _post_stt(client, headers, student_id, body):
    return client.post(f"/api/students/{student_id}/tutor/stt", json=body, headers=headers)


def test_stt_requires_login(client):
    r = client.post("/api/students/1/tutor/stt", json={"audio": "AA==", "language": "en"})
    assert r.status_code == 401


def test_stt_missing_audio_is_400(client, auth_headers):
    h = auth_headers("aisha@student.edu")
    r = _post_stt(client, h, 1, {"language": "en"})
    assert r.status_code == 400


def test_stt_invalid_base64_is_400(client, auth_headers):
    h = auth_headers("aisha@student.edu")
    r = _post_stt(client, h, 1, {"audio": "!!not-base64!!", "language": "en"})
    assert r.status_code == 400
    assert "Invalid base64 audio" in r.json()["detail"]


def test_stt_transcribes_wav(monkeypatch, client, auth_headers):
    import speech_recognition as sr
    from app import main

    captured = {}

    def fake_recognize(self, audio_data, language="en-US", **kw):
        captured["language"] = language
        captured["sample_rate"] = audio_data.sample_rate
        captured["sample_width"] = audio_data.sample_width
        return "explain docker simply"

    monkeypatch.setattr(sr.Recognizer, "recognize_google", fake_recognize)
    h = auth_headers("aisha@student.edu")
    r = _post_stt(client, h, 1, {
        "audio": base64.b64encode(_wav_bytes()).decode(),
        "language": "en",
    })
    assert r.status_code == 200
    assert r.json() == {"text": "explain docker simply"}
    assert captured["language"] == "en-US"
    assert captured["sample_rate"] == 16000
    assert captured["sample_width"] == 2


def test_stt_arabic_uses_ar_eg(monkeypatch, client, auth_headers):
    import speech_recognition as sr

    captured = {}

    def fake_recognize(self, audio_data, language="en-US", **kw):
        captured["language"] = language
        return "اشرحلي دوكر"

    monkeypatch.setattr(sr.Recognizer, "recognize_google", fake_recognize)
    h = auth_headers("aisha@student.edu")
    r = _post_stt(client, h, 1, {
        "audio": base64.b64encode(_wav_bytes()).decode(),
        "language": "ar",
    })
    assert r.status_code == 200
    assert r.json() == {"text": "اشرحلي دوكر"}
    assert captured["language"] == "ar-EG"


def test_stt_unknown_audio_returns_empty_text(monkeypatch, client, auth_headers):
    import speech_recognition as sr

    def no_speech(self, audio_data, language="en-US", **kw):
        raise sr.UnknownValueError()

    monkeypatch.setattr(sr.Recognizer, "recognize_google", no_speech)
    h = auth_headers("aisha@student.edu")
    r = _post_stt(client, h, 1, {"audio": base64.b64encode(_wav_bytes()).decode(), "language": "en"})
    assert r.status_code == 200
    assert r.json() == {"text": ""}


def test_stt_service_down_is_503(monkeypatch, client, auth_headers):
    import speech_recognition as sr

    def service_down(self, audio_data, language="en-US", **kw):
        raise sr.RequestError("google unreachable")

    monkeypatch.setattr(sr.Recognizer, "recognize_google", service_down)
    h = auth_headers("aisha@student.edu")
    r = _post_stt(client, h, 1, {"audio": base64.b64encode(_wav_bytes()).decode(), "language": "en"})
    assert r.status_code == 503
    assert "STT service unavailable" in r.json()["detail"]


def test_stt_rejects_other_students(client, auth_headers):
    # Non-owner: leila's token cannot read student 1 (aisha). The ownership
    # guard runs BEFORE transcription, so this never needs recognizer mocking.
    r = _post_stt(client, auth_headers("leila@student.edu"), 1,
                  {"audio": base64.b64encode(_wav_bytes()).decode(), "language": "en"})
    assert r.status_code in (403, 404)