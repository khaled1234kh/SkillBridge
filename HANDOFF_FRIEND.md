# SkillBridge — Continuation Handoff

**Date:** 2026-09-17
**Repo:** https://github.com/khaled1234kh/SkillBridge
**Baseline commit:** fbf9ad5 "Initial upload of SkillBridge project"
**From:** Khaled (previous dev)
**To:** The next developer / agent picking this up

## TL;DR — read this first

1. **Read `AGENTS.md` first.** Its top entry is the most recent status. Nothing supersedes it.
2. **The current blocker is Live voice in Brave.** STT works, the backend `/tutor` returns HTTP 200 with a valid reply, but the mentor **does not speak** and the UI **does not return to Listening**. Backend is verified healthy — **the bug is frontend-side in the voice engine**.
3. **Get the DevTools `[voice-live]` trace from one Live turn** to pinpoint the exact stage (see section 5).
4. **Do NOT start Phase 4D** until Phase 4C.1 is human-accepted.

## 1. What this project is

SkillBridge is a GenAI-powered career-readiness platform.

Core loop: CV/Profile -> Target Role -> Skill Gap -> Diagnostic -> Personalized Learning -> Learn -> Practice -> Mini Check -> Final Assessment -> Verified Skill -> Jobs / Career Roadmap

**Trust invariant (non-negotiable):** only the official Final Assessment (pass >= 70%) creates a Verified Skill. Learning, practice, chat, and mock interview never do.

Stack:
- Backend: FastAPI + Uvicorn (backend/app/), SQLite (backend/skillbridge.db).
- Frontend: React + Vite + TypeScript (frontend/src/).
- GenAI: NVIDIA NIM (https://integrate.api.nvidia.com/v1).
- Voice TTS: ElevenLabs (eleven_multilingual_v2).
- Voice STT (Brave fallback): Google Speech Recognition via speech_recognition (/tutor/stt).

## 2. How to run

Prereqs: Python 3.12, Node.js, and a repo-root `env` file (see section 3).

Backend - MUST run with CWD=backend:

    cd backend
    ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Frontend - dev:

    cd frontend
    npm install
    npm run dev

Frontend - build + serve statically:

    npm run build

Important: uvicorn must run with CWD=backend (the `app` package + skillbridge.db live under backend/), not the repo root.

## 3. env file

Create a repo-root `env` file (never commit it - it is in .gitignore):

    # NVIDIA NIM (GenAI) - required
    NVIDIA_API_KEY=nvapi-...
    NIM_MODEL=nvidia/nemotron-3-super-120b-a12b
    NIM_BASE_URL=https://integrate.api.nvidia.com/v1
    NIM_TIMEOUT_SECONDS=90
    NIM_DISABLE_THINKING=1

    # Optional artifact tier (resume / cover_letter / career_plan)
    ARTIFACT_MODEL=nvidia/nemotron-3-super-120b-a12b
    ARTIFACT_TIMEOUT_SECONDS=60

    # ElevenLabs (TTS) - required for voice; free tier works with premade voice IDs
    ELEVENLABS_API_KEY=sk_...
    ELEVENLABS_MODEL=eleven_multilingual_v2
    ELEVENLABS_NOVA_VOICE_ID=Xb7hH8MSUJpSbSDYk0k2
    ELEVENLABS_AXEL_VOICE_ID=TX3LPaxmHKxFdv7VOQHJ
    ELEVENLABS_SAGE_VOICE_ID=XrExE9yKIg1WjnnlVkGX
    ELEVENLABS_VEX_VOICE_ID=N2lVS1w4EtoT3dr4eOWO

Note: nvidia/nemotron-3-ultra-550b-a55b 404s on the free NIM account - do not use it. The super-120b is the final selected model.

## 4. Current blocker - Live voice does not respond in Brave

Symptom (reported by the user):
- Open Live in Brave.
- Hold the mic, say "Explain Docker simply", release.
- The transcript appears correctly in the UI.
- The backend receives POST /api/students/{id}/tutor and returns HTTP 200 with a valid reply.
- The mentor never speaks. No TTS audio plays. The UI never returns to Listening.

What is already verified healthy:
- POST /tutor/stt returns a correct transcript.
- POST /tutor returns 200 with a non-empty reply (live probe: 383-char fallback reply in 6.2s on port 8001).
- POST /tutor/tts returns 200 with audio/mpeg when called directly (79KB-420KB).
- The backend access log shows POST /tutor -> 200 with no subsequent /tutor/tts line - i.e. the frontend dies between receiving the reply and requesting audio.

Where the bug almost certainly is:
The frontend voice state machine. Specifically frontend/src/lib/voiceSession.ts (reply(), speakReply()), frontend/src/hooks/useVoiceSession.ts, and frontend/src/components/VoiceMode.tsx. Prior rounds already hardened two silent-skip hazards (see section 6), but the user still reports the symptom.

## 5. How to debug - the decisive step

Ask the user for the DevTools console trace. In Brave, open DevTools -> Console, run one Live turn ("Explain Docker simply"), and capture every line prefixed `[voice-live]`.

Expected stages in order:

    stt.server_final   -> transcript received
    tutor.sent         -> /tutor request dispatched
    tutor.ok           -> /tutor response received (has reply)
    tts.sent           -> /tutor/tts request dispatched
    tts.ok             -> audio blob received
    play.start         -> audio.play() called
    play.end           -> audio genuinely ended

Interpretation table:

- tutor.ok absent -> think state stuck / request aborted. Look at voiceSession.reply(), abort signal, sessionId guard.
- tts.sent absent -> speakReply() never ran, or pre-play guard silently skipped. Look at voiceSession.speakReply().
- tts.ok absent -> TTS fetch failed (network, 401, timeout). Look at api.ts fetchTutorTtsBlob, TTS_FETCH_TIMEOUT_MS.
- play.start absent -> autoplay rejected, or audio blob empty. Look at useTTSPlayer.playTtsBlob, primeAutoplay().
- play.end absent -> playback hung / interrupted. Look at useTTSPlayer, hush().

Also capture any tutor.error / tts.error lines - they carry kind and status.

## 6. What has already been tried (do not repeat blindly)

From AGENTS.md (read the full history there):

- reply() now wraps onAssistantReply in try/catch so a UI handler throw cannot reject the promise and strand the session.
- speakReply() pre-play guard relaxed: a processing -> replyReady -> speaking transition is now allowed.
- listenPrimary() no-ops in server-STT mode (skipBrowserStt) so a broken browser recognizer cannot deadlock after an interrupt.
- injectTranscript() now wins over playback/in-flight reply like a deliberate barge-in.
- playTtsBlob retries play() on the next user gesture if autoplay is rejected.
- Mic is routed to a zero-gain node (no self-echo).
- fetchTutorTtsBlob has a 30s abort timer.
- isBraveBrowser() detects Brave via UA Brave/ OR navigator.brave.
- Spoken timeout lowered: _SPOKEN_TIMEOUT_SECONDS = 5 on the backend.

Still unresolved. The next debugger must start from the [voice-live] trace, not from re-reading this list.

## 7. Completed phases (do not restart)

- Phase 1, 1.5, 2, 3: complete.
- Phase 4A (conversation memory / trust language): complete.
- Phase 4B.1 (Live loop, echo/barge-in fixes): complete.
- Phase 4B.2 (explicit EN | Arabic, no Auto in Live): complete.
- Phase 4C.1 (mentor voice identity, spoken style, latency observability, STT fallback): IMPLEMENTED / awaiting human acceptance.
- Phase 4C.2 (career-artifact tier, NIM super-120b primary): complete.
- Phase 4D: NOT STARTED.

## 8. Do NOT

- Do NOT rebuild the project from scratch.
- Do NOT reset / revert / stash / clean the repo.
- Do NOT delete existing modified/untracked files.
- Do NOT recreate completed Learning features.
- Do NOT start Phase 4D.
- Do NOT redesign the Orb, Interview Mode, or the conversation architecture.
- Do NOT commit .env, env, keys, *.db, *.sqlite, .venv/, node_modules/, frontend/dist/, or tsconfig.tsbuildinfo.

## 9. Gates / tests to run before claiming a fix

Frontend (from frontend/):

    npx tsc --noEmit
    node scripts/check-copilot-voice-unit.mjs
    node scripts/check-mentor-live-phase4b1.mjs
    node scripts/check-tutor-profiles.mjs
    npm run build

Expected: tsc clean; check-copilot-voice-unit 226 passed / 0 failed; other contracts OK; build clean (chunk-size advisory only).

Backend (from backend/, using the .venv at repo root):

    ..\.venv\Scripts\python.exe -m pytest tests/test_tutor_spoken.py tests/test_tts_voice_config.py tests/test_tutor_stt_fallback.py -q

Expected: all green (28 spoken + tts-config + 8 stt-fallback).

## 10. Key files to inspect first

- frontend/src/lib/voiceSession.ts - the state machine (start / reply / speakReply / bargeIn / injectTranscript).
- frontend/src/hooks/useVoiceSession.ts - React hook wrapper, error kinds, language persistence.
- frontend/src/components/VoiceMode.tsx - UI: mic hold-to-release, useServerSTT, primeAutoplay, .v-lang selector.
- frontend/src/components/CopilotPanel.tsx - opens Live, passes studentId + resolved language.
- frontend/src/hooks/useTTSPlayer.ts - audio playback, autoplay retry.
- frontend/src/lib/browserDetect.ts - isBraveBrowser().
- frontend/src/lib/api.ts - fetch helpers (tutorStt, tutor TTS blob, uploadCv).
- backend/app/genai.py - NIM calls, spoken path, _SPOKEN_TIMEOUT_SECONDS, _short_spoken_identity.
- backend/app/main.py - /tutor, /tutor/stt, /tutor/tts, /artifacts endpoints.
- backend/app/tts.py - ElevenLabs synthesis + per-mentor voice mapping.

## 11. Where to read more

- AGENTS.md - full phase-by-phase history. Top entry is latest.
- docs/HANDOFF_2026-09-17.md - Learning-side handoff (diagnostic / path / practice / mini-check / curated Python reliability). Different workstream from Live voice.
- HANDOFF.md - older project-wide handoff.
- docs/session-transcript-sanitized.json - full sanitized session transcript (real keys redacted).

## 12. Contact

Original dev: Khaled - khaled1234kh@users.noreply.github.com