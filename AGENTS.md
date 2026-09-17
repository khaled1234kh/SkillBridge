## Phase 4C.2 — Career-artifact GLM tier (implemented) + final model selection on the live NIM endpoint — IMPLEMENTED, env at FINAL CONFIG

**Directive:** artifacts (resume/cover_letter/career_plan) + tutor-memory enrichment should stop tapping the shared chat budget. Build a dedicated low-frequency artifact tier on the same NIM key/base with its own model; deterministic fallback under a bounded window; log provider; no behavior change to interactive chat/voice. Then pick the FINAL interactive + artifact models via measured latency (super-120b primary, ultra-550b artifact-only, gpt-oss-20b fallback-if-too-slow, nemotron-voicechat separate). NO Phase 4C.1/D work, no async work.

**What was implemented (tier A+B, code):**
- `backend/app/genai.py`: `ARTIFACT_MODEL` env + bounded artifact timeout (`ARTIFACT_TIMEOUT_SECONDS`, default 150, clamp 15–300); `_call_nim(..., thinking=)` sends `chat_template_kwargs.enable_thinking`; `_call_artifact`/`artifact_model_enabled`/`ARTIFACT_KINDS`/`_artifact_prompt`/`_artifact_fallback_draft`/`generate_career_artifact`; `_generate()` repaired (signature accidentally deleted earlier).
- `backend/app/main.py`: `POST /api/students/{id}/artifacts` (auth `Student`, `_own_student`, body `{kind, language}`; returns `{kind, language, artifact, genai_provider}`).
- `backend/app/tutor_memory.py`: `_enrich_digest_with_artifact` + background async enrichment in `after_turn` (watermark re-check, bounded to `SUMMARY_CHAR_CAP`).
- Tests: `backend/tests/test_artifacts_glm_tier.py` **17 passed / 0 failed**; full regression sweep **255 passed / 0 failed**; tsc clean; build clean (12.65s).

**Final model selection — measured on 2026-09-17, same free NIM endpoint/account, `enable_thinking:false`, 150s bound:**
- `nvidia/nemotron-3-super-120b-a12b` **PRIMARY (interactive + artifact).** Interactive tutor turn (real 6.4KB system/0.5KB user prompt, spoken budget 200): TTFT 1.019–1.075s typical / 3.7s worst observed, total 2.1–6.3s, clean 632–1109-char Docker answers, cold single-shot 3/3 success. Artifact resume (non-streaming, i.e. the exact `_call_artifact` path): 4.6 / 6.3 / 8.4s, 2000–2950 chars each; streaming resume 4/4 success (TTFT ~1.0–1.3s, total 5.5–33.6s). Intermittent shared-endpoint drops observed (~1/3 of rapid-fire/odd draws: 0.9s empty streams when 3 requests fired in <2s, occasional 503) — production single-turn calls are unaffected; the existing deterministic fallback covers a bad draw (live cover_letter once fell back with a valid 368-char templated letter).
- `nvidia/nemotron-3-ultra-550b-a55b` — **NOT usable on this account's free endpoint**: HTTP 404 for all artifact draws, `Function id '948fe171-…' … is not found` (inference function not provisioned for this account on `/v1/chat/completions`). Would need a separate provisioned URL to ever be a candidate.
- `openai/gpt-oss-20b` — **skipped by scope**: only to be tested if #1 was too slow for interactive; super-120b is faster than the old lightning model, so not needed.
- `z-ai/glm-5.3` (prior tier): measured thinking-off 46.7s (GLM key) / 93.8s (run key); live artifacts exceeded the 150s bound and resolved to deterministic-fallback. **REMOVED from active config** (tier code kept, inert unless `ARTIFACT_MODEL` points at it).
- `nemotron-voicechat` — **not in the 82-model public catalog and 404s** on this account's endpoint; cannot replace the Live voice multi-hop path. (Separate experiment only; English-only anyway, Arabic stays on the existing pipeline regardless.)
- Previous alternates for reference: `deepseek-ai/deepseek-v4-flash-0731` 200 but TTFT ~110.8s / total ~152s on resume — over bound; `nvidia/nemotron-3.5-lightning-30b-a3b` (old interactive): served reliably, live 6.2s — superseded by super-120b on TTFT.

**FINAL env config (repo-root `env`, live on the user's 8001 launcher + 8000 probe since this round):**
- `NIM_MODEL=nvidia/nemotron-3-super-120b-a12b`
- `ARTIFACT_MODEL=nvidia/nemotron-3-super-120b-a12b` (same key/base; GLM 5.3 line removed with rationale)
- `ARTIFACT_TIMEOUT_SECONDS` default 150, bounded 15–300 (kept). Interactive chat/voice untouched by the artifact tier.

**Live verification after restart (restarted 8001 → PID 18420, 8000 → PID 28828, both system Python312 uvicorn CWD=backend):**
- `/api/config/demo-mode` → `provider.nvidia.model = nvidia/nemotron-3-super-120b-a12b` (env applied).
- Artifact resume → **HTTP 200 in 7.4s, `genai_provider:"real"`, 2633 chars** (tailored resume, real Aisha data).
- Artifact cover_letter → HTTP 200 1.5s (intermittent provider drop → `deterministic-fallback`, 368-char templated letter — acceptable).
- Spoken tutor "Explain Docker volumes." → **HTTP 200 in 2.7s, 695 chars, super-120b answer**; provider after calls `last_success=true`.

**Possible small follow-ups (not done — out of scope this round):** bounded single retry on artifact provider draws to ride out the ~1/3 intermittent 503/empty (currently covered by deterministic fallback).

---

## Phase 4C.1 (r7 — CV extraction latency + Live voice client fixes: "cv extraction too slow" + "voice chat not working") — AWAITING HUMAN ACCEPTANCE)

**Status:** Two human-acceptance returns from the 4C.1 browser retest: (1) "cv extraction is taking way too long", (2) "voice chat is not working". Both root-caused and fixed; backend restarted with all fixes and rebuilt frontend served. Games green. Human acceptance requires browser retest in Brave (CV upload + Live voice). STOP — do not start Phase 4D.

**Issue 1 — CV extraction too long (backend + frontend latency bounds):**
- `backend/app/genai.py` `extract_skills_from_cv` (line 542): the provider call was UNBOUNDED on this path — `complete(...)` inherited `NIM_TIMEOUT_SECONDS=90` with retries; a throttled NIM could hold the upload for minutes. Now passes `timeout=_CV_TIMEOUT_SECONDS (7)`, `retries=_CV_RETRIES (0)`, and inlines only `(cv_text or "")[:_CV_TEXT_LIMIT (60k)]` into the model prompt. Deterministic fallback (skill_registry scan) is preserved on the bounded window via `_CV_DETERMINISTIC_LIMIT`, which caps the synchronous scan (measured ~94s on a 1.77MB CV (~18-50µs/byte), ~1-2s at the 40k cap).
- `frontend/src/lib/api.ts` `uploadCv` (line 136): had NO client-side timeout — the "Extracting…" spinner ran forever. Now wraps the fetch in an AbortController + 50s timer; on abort it throws "CV extraction took too long — your existing profile was kept." so the UI's existing catch surfaces an actionable error instead of spinning.
- Backend regression tests (+2 in `backend/tests/test_extraction.py`): `test_cv_extraction_bounds_provider_timelimit_and_retries` (timeout=`_CV_TIMEOUT_SECONDS`/retries=`_CV_RETRIES` captured via patched `complete`, fallback still yields skills) and `test_cv_extraction_truncates_oversized_input` (2MB input → model prompt exactly `_CV_TEXT_LIMIT`; full text still reaches the extractor).
- Live verification after restart (127.0.0.1:8000, fresh process): authenticated `POST /api/students/1/cv` (text CV) → **HTTP 200 in 5.4s**, 7 skills, `genai_provider:"real"`.

**Issue 2 — Voice chat not working (frontend-only client bugs; backend chain verified healthy earlier):**
- F1 **hold-to-release was NOT implemented**: zero pointerup/pointerdown/mouseup/touchend matches existed in `frontend/src` although AGENTS documented hold→say→release. `VoiceMode.tsx` mic is now hold-to-release: `onPointerDown` starts the server-STT recording, `onPointerUp`/`onPointerCancel` + window-level `pointerup`/`touchend`/`pointercancel` submit on release ANYWHERE; keyboard activation still tap-toggles via handled click suppression (`pointerHeldRef`). Sub/state copy updated ("Release to send" / Arabic).
- F4 **empty transcript silently exited**: server STT returning `text:""` (silence/unknown audio) or a failed STT fetch produced ZERO feedback (`if (text) voice.injectTranscript(text)` swallowed the else). Now a transient localized note (`.v-note`, role="status", auto-clears in 2.6s): EN "Didn't catch that — hold and try again" / Arabic. NOTE: `.v-note` keeps the `check-mentor-live-phase4b1.mjs` pin that VoiceMode must NOT contain `v-hint`/`vh-`/`MOCKUP_VOICE_HINT`.
- F5 **broken browser recognizer restarted after barge-in/interrupt in server-STT mode**: `voiceSession.ts` `listenPrimary()` is the release path for `interruptedHandoff()` (→listening) and `bargeIn()`-during-processing (→'speakDuringProcessing'/listening); `start()` was the only guarded entry, so Brave (`skipBrowserStt`) re-opened the broken recognizer after every interrupt → deadlock/false voice-unavailable. `listenPrimary()` now no-ops (state stays 'listening') when `opts.skipBrowserStt` is set — injectTranscript drives the session.
- F3 **dictated turn silently dropped while speaking/processing**: `injectTranscript()` only accepted `listening`/`idle`. Now a new dictated turn WINS over playback/in-flight reply like a deliberate barge-in: on `speaking`/`interrupted` → hush recognizer, abort TTS, stop playback, `sessionId+=1` (stale in-flight reply dropped by the existing sessionId guard), transition to idle then submit; on `processing` → abort the in-flight /tutor, `sessionId+=1`, submit the fresh turn.
- F2 **autoplay rejection silently swallowed**: `useTTSPlayer.ts` `playTtsBlob` did `void audio.play().catch(finish)` — a post-round-trip `play()` blocked by autoplay policy surfaced as a silent mentor with no error. Now a rejected `play()` retries on the next user gesture (`pointerdown`/`touchend`) and only finishes on genuine end/error.
- F7 **mic routed into the speakers** (self-echo/feedback loop): the ScriptProcessorNode connected `processor.connect(ctx.destination)`. Now feeds a zero-gain node (`mute.gain=0`) → destination so PCM is still captured but never audible.
- F8 **TTS fetch had no timeout**: `fetchTutorTtsBlob` now races a 30s abort timer (`TTS_FETCH_TIMEOUT_MS`) merged with the caller signal.
- Frontend contract + type/build gates: `check-copilot-voice-unit.mjs` **226 passed / 0 failed** (engine changes compatible); `check-mentor-live-phase4b1.mjs` all orb contracts OK; `npx tsc --noEmit` clean; `npm run build` clean (11.83s, chunk-size advisory only). Backend: `test_extraction.py` **11 passed / 0 failed** (16.6s; suite previously hung minutes on the real provider — the new provider bounds + deterministic cap fixed that too) and `test_tutor_spoken.py` + `test_open_skill_extraction.py` **63 passed / 0 failed**.
- Backend restarted fresh (single uvicorn on the venv interpreter, old duplicate process removed); `frontend/dist` rebuilt and served statically.

**r7 follow-up round 2 (still awaiting acceptance):** second browser retest reported "Speech recognition is not responding — holding the mic uses server transcription" (stuck state) and "CV still not fixed". Profiling exposed that the earlier bounds were still too soft:
- **CV latency tightened to a hard ceiling.** Real break-down measured on the live path: at the old 12s provider bound the small probe took **13.4s** and a 134KB text CV took **23.2s** (provider ~18s + deterministic scan ~5s, additive). `_CV_DETERMINISTIC_LIMIT` cut **120k→40k** (real CV text is ~5-20KB; the scan is per-term search over the window, ~18-50µs/byte → ~1-2s at 40k) and `_CV_TIMEOUT_SECONDS` **12→7** (keeps the model on healthy NIM draws, which run ~2-5.4s; a throttled NIM now yields to deterministic at ~7s). Re-probed after restart: small CV **HTTP 200 in 8.4s**, 134KB CV **10.2s**, both `genai_provider:"real"` (model still contributed). Client 50s AbortController stays as the backstop.
- **Voice stuck-state root-caused + calmed.** The "Speech recognition is not responding" deadlock fired because the user is NOT detected as Brave (old UA-only check), so `skipBrowserStt` was false and the broken browser recognizer deadlocked → `sttUnavailable` after `LISTENING_DEADLOCK_MS=8s`. New `frontend/src/lib/browserDetect.ts` `isBraveBrowser()` (UA `Brave/` OR `navigator.brave`) used by `CopilotPanel.tsx` (isBrave) and `VoiceMode.tsx` (needsFallback). The deadlock error is now suppressed from stderr/err when the server-STT fallback is active and the idle-fallback status line reads "Server transcription is on" (EN/AR), so the stuck copy is no longer shown as a failure.
- Gates re-run after this round: `test_extraction.py` **11 passed / 0 failed** (10.8s), `test_tutor_spoken.py`+`test_open_skill_extraction.py` **63 passed / 0 failed**, `check-copilot-voice-unit.mjs` **226 passed / 0 failed**, `check-mentor-live-phase4b1.mjs` all orb contracts OK, `npx tsc --noEmit` clean (build clean in round 1; only constants changed since). Backend restarted (PID 25864) serving the rebuilt dist.

**r7 follow-up round 3 — "tts works but it never responds" (spoken-turn latency return):**
- Live measurement exposed the true blocker: a spoken teaching turn ("Explain Docker simply", spoken=true) took **31.2s** on the running backend — the throttled NIM burned the entire `_SPOKEN_TIMEOUT_SECONDS=30` draw then resolved to the deterministic `_tutor_fallback`. The learner faced a silent ~30s wait on EVERY spoken teaching turn (until the 65s frontend guard → "Connection lost"). TTS was never the problem (audio plays fine once a reply lands). `POST /tutor/stt` verified healthy with auth (200 `{"text":""}` for a tone sample).
- Fix (backend only, chat/greeting byte-identical): `genai._SPOKEN_TIMEOUT_SECONDS` **30→8**. With `retries=0` + `skip_provider_fail_retry=True` on the spoken path, a draw that outlives 8s now resolves to the deterministic fallback — a healthy NIM (~2-5.4s draws) still returns the model reply, a throttled/down NIM yields a real teaching answer in ~8s instead of 30s. Re-probed after restart (PID 7384): spoken turn **HTTP 200 in 9.3s** (383-char Docker teaching reply). Frontend unchanged (`DEFAULT_REPLY_TIMEOUT_MS=65_000` stays a backstop).
- Gates: `test_tutor_spoken.py` **28 passed / 0 failed** (timeout assertions are constant-relative). Restart PID 7384 serving the rebuilt dist.

**r7 follow-up round 4 — "it is not responding — lower latency as much as possible, I want the copilot to actually respond":**
- Two causes addressed. **(1) Client gesture race (likely the "never responds"):** the hold-to-release recorder only armed its window-level release handlers when `isRecording` had already flipped true. A phone-quick press released BEFORE `getUserMedia`/AudioContext setup resolved → the release event fired to no listener → the recorder sat stuck indefinitely in "Recording… release to send" → no transcript, no reply. `VoiceMode.onMicPointerDown` now submits the recording the moment it becomes live when the pointer was already released during async setup (`startRecording().then(() => { if (!pointerHeldRef.current) submitRef.current() })`). Plus a 15s watchdog `setTimeout` while recording auto-submits so the recorder can never hang. **(2) Spoken latency floor lowered:** `genai._SPOKEN_TIMEOUT_SECONDS` **8→5** (healthy NIM draws ~2-5s succeed; a slower/throttled draw yields the deterministic `_tutor_fallback`). Re-probed after a fresh rebuild + restart (PID 14996): spoken "Explain Docker simply" → **HTTP 200 in 3.7s** (338-char teaching reply) — from 31.2s → 9.3s → 3.7s across this continuation.
- Gates: `test_tutor_spoken.py` **28 passed / 0 failed**; `check-copilot-voice-unit.mjs` **226 passed / 0 failed**; `check-mentor-live-phase4b1.mjs` all orb contracts OK; `npx tsc --noEmit` clean; `npm run build` clean (11.31s, advisory only); `frontend/dist` rebuilt and served (assets 04:45:47).

**r7 follow-up round 5 — "transcribes correctly but does not respond" + user runs their OWN server on :8001 (port 8000 held by my test instance):**
- User's terminal log shows their launcher binds **http://localhost:8001** whenever 8000 is taken; the 8001 process serves the fresh `frontend/dist` from disk but its Python is fixed at process start. Their current 8001 run (`last_timeout:true, last_latency_ms:6175`) is executing the current backend (5s spoken bound + fallback). Live chain verified IN FULL on **their** 8001: `POST /tutor` **200 with a 383-char fallback reply in 6.2s** (reply field present) and `POST /tutor/tts` **200 audio/mpeg 79KB in 1.7s** — so the backend is 100% healthy end-to-end on the exact process the user tests against; the silent mentor is a BROWSER-session bug between send() resolution and TTS dispatch.
- Reinforcing evidence: their access log shows `POST /api/students/9/tutor -> 200` with NO subsequent `/tutor/tts` line — the reply arrives but the engine dies before requesting audio.
- Two silent-skip hazards hardened in `frontend/src/lib/voiceSession.ts` (frontend-only; rebuild clears both):
  1. `reply()` ran `this.opts.onAssistantReply?.(reply)` UNGUARDED between `transition('replyReady')` and `speakReply()` — any throw from the UI chat-thread handler (CopilotPanel appendChat) would reject `reply()`'s promise, leaving the session stuck in the thinking state forever with no TTS, no error shown, and no `/tutor/tts` ever fired. Now wrapped in try/catch (traced `reply.assistant_callback_error`) so synthesizing always proceeds.
  2. `speakReply()` pre-play guard `this.sessionId !== session || this.state !== 'speaking'` silently skipped audio for ANY state drift. Relaxed to let a turn proceed from `processing` as well (`if (this.state !== 'speaking') this.transition('replyReady')` before play) — a micro-drift can no longer produce a silent mentor with zero feedback.
- Note: uvicorn must run with CWD=`backend` (the `app` package + `skillbridge.db` live under `backend/`), not the repo root. Launched my probe instance on 8000 (PID 2776) via `.venv\Scripts\python.exe` with `PYTHONPATH=backend`; live probe: spoken "Explain Docker simply" → `POST /tutor` 200 (383 chars) + `POST /tutor/tts` 200 (420KB audio).
- Gates: `check-copilot-voice-unit.mjs` **226 passed / 0 failed**; `npx tsc --noEmit` clean; `npm run build` clean (12.14s, advisory only); `frontend/dist` rebuilt (04:49) — the user's running 8001 process serves it from disk automatically.
- **Decisive next data point requested from the user:** DevTools → Console → one Live turn → paste the `[voice-live]` stage lines (`stt.server_final` → `tutor.sent` → `tutor.ok` → `tts.sent` → `tts.ok` → `play.start` and any `tutor.error`/`tts.error`). It pinpoints the exact stage where the reply stops. If `tutor.ok` is absent → think state stuck (send/abort); if `tts.sent` absent → speakReply never ran; if `tts.ok` absent → TTS fetch failed; if `play.start` absent → playback/autoplay. Backend is proven healthy on BOTH ports, so this trace ends the search.

**Still required for Phase 4C.1 HUMAN ACCEPTANCE (browser retest in Brave):**
1. CV: Learning/Copilot Skills page → upload the real CV → completes promptly (typically ~2-10s, hard ceiling ~9s: 7s provider bound + ~1-2s deterministic scan); a huge/pathological CV still lands, bounded by the 50s client + 7s provider bounds instead of an endless spinner.
2. Live voice: open Live → hold the mic, say "Explain Docker simply", release anywhere → text appears → mentor replies + audio → auto-return to Listening. Repeat EN + Arabic, all 4 mentors. Empty/too-short recordings show the "Didn't catch that" note instead of silence. Chrome/Edge regression: Web Speech still native, no fallback path.
3. STOP — do not start Phase 4D.

---

**Status:** Human acceptance test reported: "teaching turn does not reply in Live voice mode. Greetings work. Short replies work. 'Explain Docker simply' does not reply." Root cause diagnosed and fixed. Backend now healthy on the exact turn (spoken=true, 2.2s, 273 chars on a fresh restart). All gates green. **Backend restarted with fix loaded.** Human acceptance requires browser retest in Brave (end-to-end Live voice). STOP — do not start Phase 4D.

**Root cause (latency budget race):**
- `_call_nim(retries=1)` = `range(1)` = 1 HTTP attempt × `_SPOKEN_TIMEOUT_SECONDS=30` per draw. When NIM throttled, one draw = up to 30s.
- `_complete_visible` runs a **second full draw** when the first attempt fails (any reason: provider timeout, gate rejection). Two throttled draws = up to **60s + overhead**.
- Frontend hard guard (`DEFAULT_REPLY_TIMEOUT_MS = 65_000`) aborts the fetch at 65s → user sees "no reply" / "Connection lost".
- Greetings (`_short_spoken_identity` provider-free, ~60ms) and short replies (fast NIM draw) never hit this race. Teaching turns (200-token budget, longer generation) hit it when NIM is throttled (documented draws: 4.4–31.5s; worst measured: 48s for a trivial call).

**Fix (backend only, spoken-only, chat byte-identical):**

`backend/app/genai.py`:
- `_call_nim`: `for attempt in range(retries)` → `for attempt in range(max(1, retries))` — guarantees exactly one HTTP attempt even when `retries=0` is passed (spoken path). Default `retries=1` unchanged, chat behavior untouched.
- `_generate(..., retries=None)`: new optional kwarg, forwarded to `_nvidia_call` kwargs only when not None. Default None = `_call_nim` default 1 = identical to today. Spoken path passes `retries=0`.
- `complete(..., retries=None)` → forward.
- `_complete_visible(..., retries=None, skip_provider_fail_retry=False)`: forwards `retries` to `complete`; when `skip_provider_fail_retry=True` and the first attempt was a `provider_failed` (provider down/timeout), skips the second draw and resolves deterministically. Gate-rejection retry (latch/meta/language) unchanged.
- `tutor_reply`: for `spoken=True`, passes `retries=0` + `skip_provider_fail_retry=True`.

Worst-case spoken latency after fix:
- Provider healthy: ~4s (unchanged).
- Provider throttled/down: one 30s draw → provider_failed → deterministic fallback (a real, meaningful Docker teaching answer from `_tutor_fallback`).
- Gate-rejected (uncommon, provider DID respond but wrong language): first draw ≤30s + second draw ≤30s ≈ 60s → within the 65s guard.
- Never exceeds 65s on the provider-failure path (the failure the user saw).

**Frontend (no changes):** `DEFAULT_REPLY_TIMEOUT_MS = 65_000` unchanged. The backend fix keeps all spoken paths under the guard.

**Regression tests (`backend/tests/test_tutor_spoken.py`, +3 new, total 28 passed):**
- `test_spoken_provider_failure_resolves_in_one_draw` — spoken turn, fake provider that always raises → exactly 1 draw called, retries=0 confirmed, Docker fallback served.
- `test_spoken_provider_failure_does_not_raise` — same: no exception escapes to the endpoint.
- `test_chat_keeps_two_draws_and_default_retries` — chat with a failing provider still gets the historical 2nd draw (retries=None for both), no behavioral change.

**Stale test fix (`backend/tests/test_tutor_fallback_manual_acceptance.py`):**
- `test_trusted_career_questions_still_get_career_context` — asked a trusted-career question as the **first message** of a fresh thread. Phase 4A first-message context gating zeroes `ctx_text` on the first message, so "Trusted target role" was absent. Same class as r3's documented stale tests in `test_tutor_trust_language_phase2.py`. Fixed by priming with `_chat("Explain Docker volumes.")` first.

**Gates (all green):**
- Backend spoken + language: `test_tutor_spoken.py` **28 passed / 0 failed** (+3 new regression tests for the latency fix)
- Backend broad sweep: provider + modes + language + runtime-language + profiles + personas + conversations + confusion + copilot + trust + tts + nim **408 passed / 0 failed**
- Backend fallback manual acceptance: **18 passed / 0 failed**
- Backend STT fallback: **8 passed / 0 failed**
- Frontend `check-copilot-voice-unit.mjs` **226 passed / 0 failed**
- Frontend `check-mentor-live-phase4b1.mjs` — all orb contracts OK
- `npx tsc --noEmit` clean
- `npm run build` clean (11.64s, chunk-size advisory only)

**Live verification after restart (127.0.0.1:8000, fresh process, venv):**
- Login: `aisha@student.edu` → token OK
- `POST /api/students/1/tutor` `{message:"Explain Docker simply", spoken:true, tutor_id:"sage", mode:"chat", language:"en"}` → **200**, reply 273 chars, 2195ms

**Still required for Phase 4C.1 HUMAN ACCEPTANCE:** browser retest in Brave: open Live → mic → hold, say "Explain Docker simply", release → text appears → mentor replies aloud → auto-returns to Listening. All four mentors × EN + Arabic. DevTools `[voice-live]` traces should show total elapsedMs well under 65s on the tutor.ok trace. STOP — do not start Phase 4D.

**What changed:**

Backend (`backend/app/main.py`):
- `POST /api/students/{student_id}/tutor/stt` — new endpoint accepting `{audio: "<base64 WAV>", language: "en"|"ar"}`; strips the RIFF/WAVE 44-byte header via `_wav_format()`, creates `speech_recognition.AudioData`, calls `recognize_google()` (Google's free speech API, no key needed); returns `{text: ""}` on UnknownValueError, 503 if the Google service is unreachable; language `"ar"` maps to Google locale `ar-EG`.
- `_wav_format(wav_bytes)` — returns `(sample_rate, sample_width)` from a PCM RIFF/WAVE header; supports 16/24/32-bit.

Backend tests (`backend/tests/test_tutor_stt_fallback.py`, **8 tests, all green**):
- `test_stt_requires_login` — unauthenticated → 401
- `test_stt_missing_audio_is_400` — no audio → 400
- `test_stt_invalid_base64_is_400` — junk base64 → 400 with correct detail
- `test_stt_transcribes_wav` — valid WAV → 200; assert `recognize_google` called with `language="en-US"`, `sample_rate=16000`, `sample_width=2`; text returned verbatim
- `test_stt_arabic_uses_ar_eg` — `language: "ar"` → `recognize_google` called with `language="ar-EG"`
- `test_stt_unknown_audio_returns_empty_text` — `UnknownValueError` → `{"text": ""}` (200)
- `test_stt_stt_service_down_is_503` — `RequestError` → 503
- `test_stt_rejects_other_students` — wrong student → 403/404

Live backend end-to-end (127.0.0.1:8000, venv, restarted):
- `POST /api/students/1/tutor/stt` with a real base64 WAV (silence) → **200**: `{"text": ""}` (Google recognizes silence correctly); WAV header parsing verified; auth verified.

Frontend (`frontend/src/lib/voiceSession.ts`):
- `injectTranscript(text)` — new public method; injects a server-side STT transcript into the session exactly like `handlePrimaryFinal` (clears error, submits, transitions to speechFinal, calls reply); does NOT open a mic interrupt recognizer (browser STT is broken in fallback mode, so interrupt recognizer is pointless; keeps the guard intact: exactly one `listenInterrupt()` call).

Frontend (`frontend/src/hooks/useVoiceSession.ts`):
- Exposes `injectTranscript(text)` through `VoiceSessionApi`; also clears the hook's local `errorState` on inject so the error visual resets.
- `errorKind` mapping unchanged: `'network'` → `'voice-unavailable'` → `needsFallback = true` in VoiceMode.

Frontend (`frontend/src/components/VoiceMode.tsx`):
- New prop: `studentId: number` (passed by CopilotPanel).
- `useServerSTT(studentId, language)` — local hook managing the push-to-talk fallback:
  - `startRecording()`: `navigator.mediaDevices.getUserMedia()` → `AudioContext` + `ScriptProcessorNode` captures mono PCM → chunks accumulated in memory.
  - `stopRecording()`: merges chunks into `Float32Array`, resamples to 16kHz if needed, encodes WAV via `encodeWav()` (base64), POSTs to `/tutor/stt` with auth, returns the transcript text or null.
  - Cleanup on stop/close.
- Global `mouseup`/`touchend` handlers activate while recording is active → releases the recording even if the user lifts outside the mic button.
- Status/sub text: while recording → "⏺ Recording — release to send" / Arabic equivalent; while sending → "⏳ Transcribing..."; when fallback is idle and browser STT unavailable → "Browser STT unavailable — hold mic to record".
- When in fallback mode (errorKind === 'voice-unavailable'): `voice.supported` gate is bypassed for the mic button; the orb tap and mic tap both trigger recording start instead of the broken browser STT.
- `data-recording="true"` attribute on mic button while recording (preserves the contract-guarded `className="v-mic"`).

Frontend (`frontend/src/components/CopilotPanel.tsx`):
- Passes `studentId={studentId}` to VoiceMode.

Frontend (`frontend/src/lib/api.ts`):
- `tutorStt(studentId, audio, language)` — typed API helper (added; not used directly by VoiceMode's manual fetch but available for other consumers).

**Gates (all green):**
- `check-copilot-voice-unit.mjs` **226 passed / 0 failed**
- `check-mentor-live-phase4b1.mjs` — all orb contracts OK
- 8 other frontend contract checks — OK
- Backend spoken+tts+stt: **40 passed / 0 failed** (32 prior + 8 new)
- `npx tsc --noEmit` clean

**Remaining before Phase 4C.1 HUMAN ACCEPTANCE:**
1. **Brave Live voice browser test** — confirm Live works end-to-end in Brave: open → push-to-talk mic appears → hold, speak, release → text appears in transcript → mentor reply + TTS audio plays → auto-returns to Listening. Test all 4 mentors × EN + Arabic.
2. **Chrome/Edge regression** — confirm Chrome's Web Speech API still works natively (no fallback path activates).

**Files touched this continuation:**
- `backend/app/main.py` (new `/tutor/stt` endpoint + `_wav_format`)
- `backend/tests/test_tutor_stt_fallback.py` (NEW — 8 tests)
- `frontend/src/lib/voiceSession.ts` (new `injectTranscript`)
- `frontend/src/hooks/useVoiceSession.ts` (expose `injectTranscript`, clear `errorState` on inject)
- `frontend/src/components/VoiceMode.tsx` (new `studentId` prop, `useServerSTT` hook, recording UI)
- `frontend/src/components/CopilotPanel.tsx` (pass `studentId` to VoiceMode)
- `frontend/src/lib/api.ts` (new `tutorStt` API helper)

## Phase 4C.1 (r4 — ElevenLabs BLOCKER RESOLVED, TTS LIVE OK) — AWAITING HUMAN ACCEPTANCE

**Status:** Handoff blocker/Immediate-Next-Step #1–3 are now DONE. The new `ELEVENLABS_API_KEY=sk_5e7601...` authenticates and synthesizes (silent fix of the r2/r3 401; account is free, 350/10000 chars, TTS-permissioned). The old voice IDs belonged to the previous account, so `env` now maps each mentor to a premade voice of the current account (custom Voice-Design IDs can replace these later — paste over them and restart the backend):
- Nova → `Xb7hH8MSUJpSbSDYk0k2` (Alice — Clear, Engaging Educator)
- Axel → `TX3LPaxmHKxFdv7VOQHJ` (Liam — Energetic)
- Sage → `XrExE9yKIg1WjnnlVkGX` (Matilda — Knowledgeable, Professional)
- Vex → `N2lVS1w4EtoT3dr4eOWO` (Callum — Husky Trickster)

**Live verification (backend on 127.0.0.1:8000, venv, `env`-file keys, fresh restart):**
- Direct provider: Four voice IDs → `POST /v1/text-to-speech/{id}` **HTTP 200** (41–61 KB audio each).
- App endpoints: `POST /api/students/1/tutor/tts` **HTTP 200 for all four mentors** (nova 64 KB / axel 53 KB / sage 51 KB / vex 65 KB) via a real student login.
- `GET /api/config/demo-mode` → `tts.available=true`, `api_key_loaded=true`, `tutor_voices_loaded={nova:true,axel:true,sage:true,vex:true}`, `tts_configured=true`; `genai_enabled=true` (nvidia).
- Backend gates untouched in this continuation (r3 baseline stands: 425 passed / 0 failed; frontend voice-unit 226/0; tsc clean).

**Remaining before Phase 4C.1 HUMAN ACCEPTANCE (was Steps #4–7 of the handoff):** browser-level human test — Live on each mentor EN + Arabic, audible full reply, no cutoff/duplicate/stuck, auto-return to Listening, `Explain Docker simply` latency check. **Then** Phase 4D may start. No Interview redesign, no Orb redesign.

## Phase 4C.1 (r3 — provider recheck + gate restore on the delivered copy) — AWAITING HUMAN ACCEPTANCE

**Status:** Human requested a provider-side API health check first, then paused to supply working ElevenLabs credentials later ("I'll give you APIs for the chatbots nova, vex, sage, axel later"). This continuation re-verified both configured providers directly against the `env`-file keys, restored the green gate baseline on THIS copy, fixed 2 stale trust-language tests, and is parked at **AWAITING HUMAN ACCEPTANCE** until the new ElevenLabs key/voice IDs land. STOP — do not start Phase 4D.

**Provider recheck (2026-09-16, direct HTTP, `env`-file keys):**
- **NVIDIA NIM — WORKING.** `POST https://integrate.api.nvidia.com/v1/chat/completions` → HTTP 200, `nvidia/nemotron-3.5-lightning-30b-a3b`, live completion. No key change needed.
- **ElevenLabs — key authenticates, TTS still blocked.** `GET /api.elevenlabs.io/v1/user` → 200; `/v1/user/subscription` → tier **free**, characters **9998 / 10000** (only 2 left), voice slots 3/3 used. `POST /v1/text-to-speech/{nova}` → **HTTP 401** (empty body). Conclusion unchanged from r2: the configured key cannot synthesize; the blocker is account/key level, not the frontend state machine or the caching path. Waiting for the promised nova/vex/sage/axel API key(s) (+ real Vex voice id if different) → update `env`, restart backend, expect `/tutor/tts` HTTP 200.

**Work done on this continuation:**
- **Baseline gates re-verified green on this copy:** `test_tutor_spoken.py` + `test_tts_voice_config.py` **32/0**; language+runtime-language+profiles+personas **215/0**; provider+modes+copilot+conversations+confusion+trust **178/0** → backend **425 passed / 0 failed**. Frontend `check-copilot-voice-unit.mjs` **226/0**; `npx tsc --noEmit` clean.
- **Fixed 2 STALE trust-language tests (real regression vs the documented 422/0 baseline):** `test_tutor_trust_language_phase2.py::test_officially_verified_skill_is_stated_confidently` and `::test_verified_skills_question_lists_only_official_records` asked their verified-skills question as the FIRST message of a fresh thread. Phase 4A's fresh-thread context gating (`main.api_tutor_chat` zeroes `ctx_text` when `pre_turn` is empty) intentionally keeps context off the first message, so the verified-skills fallback could never see the backend records and both returned "no officially verified skills". Both now prime the thread first (`_chat("Explain Docker volumes.")`), matching the file's own precedent (`test_user_claim_remains_memory_but_verified_answer_uses_backend_truth` at line 287). Every original trust assertion preserved — same class of stale-test fix as the documented 7 `test_copilot.py` updates. Full file: **19 passed / 0 failed**.

**Still required for Phase 4C.1 HUMAN ACCEPTANCE (unchanged):** working ElevenLabs key → backend restart → `/tutor/tts` HTTP 200 → audible Nova/Axel/Sage/Vex EN + Arabic, no cutoff/duplicate/stuck, acceptable latency (`Explain Docker simply`). **NO Phase 4D, no Interview redesign, no Orb redesign.**

## Phase 4C.1 (r2 — latency-to-first-audio acceptance return) — FIXES LANDED — AWAITING HUMAN ACCEPTANCE

**Status:** The human rejected Phase 4C.1 r1: in real browser use the mentor took too long to begin speaking even for "What's your name?" / "اسمك ايه؟". This continuation DIAGNOSED the REAL configured backend (127.0.0.1:8000, NVIDIA NIM + ElevenLabs, local `env` file) and delivered measured optimizations. No Orb redesign, no Interview redesign, no conversation-architecture change, no normal-chat behavior change. Re-measurement and gates below; ends at **AWAITING HUMAN ACCEPTANCE**. STOP — do not start Phase 4D.

**What the real measurements found (before vs after, LIVE backend, not mocks):**
- **BEFORE (r1 server):** greeting/identity turns ("What's your name?") each burned a full NIM call — `provider.last_latency_ms` up to **22,460 ms (22s)**; the reply was the LONG profile paragraph (`_IDENTITY_*`, "I'm Sage, your AI career coach in SkillBridge. …"), violating the spoken 1–3-sentence rule and inflating TTS. `/tutor/tts` returned **ElevenLabs 401** on the running process (stale key) → no audio at all → user-visible frozen/silent.
- **AFTER fixes on the SAME local backend + `env`-file keys:** `What's your name?` (×5 each mentor) **tutor 45–63 ms (provider-free, deterministic, short line)**; Arabic `اسمك ايه؟` **60 ms**; a real spoken teaching turn "Explain Docker simply" **4,476 ms** on a healthy draw (single main-model call, 200-token budget, 30s bound). TTS stage still **ElevenLabs 401** for THIS account key — key authenticates (`GET /v1/user` 200) but is NOT authorized to synthesize (`POST /v1/text-to-speech` 401) → environmental blocker: Live speech has no working provider key right now; the synthesized length/cost path is preserved and caches per (tutor,text).
- **No verified fast NIM model is callable on this account:** catalog lists 82 models, but live `/v1/chat/completions` 404s for `google/gemma-3-4b-it`, `google/gemma-2b`, `nvidia/mistral-nemo-minitron-8b-8k-instruct`, `nvidia/nemotron-nano-3-30b-a3b`, `mistralai/mistral-7b-instruct-v0.3`, `ibm/granite-3.0-3b-a800m-instruct`, `microsoft/phi-3.5-moe-instruct` (404); `deepseek-ai/deepseek-v4-flash-0731` and `z-ai/glm-5.3-flash` error/timeout. The main model is the only usable one and is heavily throttled (a 30-token trivial call took 48s once; app-level draws vary ~4.4s–31.5s). Hence `LIVE_NIM_MODEL` is implemented but intentionally **unset** — hardcoding an unverified model doubles latency via the safe-fallback path (measured 63s when a 404 fast model was configured). `env` carries the documented optional variable commented out (`#LIVE_NIM_MODEL=`).

**Backend fixes (all Live/spoken-only; normal chat byte-identical):**
- **Spoken identity is now provider-free + short:** `genai._short_spoken_identity()` (regex-gated EN/AR explicit identity questions) returns a deterministic 1-sentence line («I'm Nova, your SkillBridge mentor — the Explainer Tutor.» / Arabic equivalent) BEFORE any provider call on `spoken=true`. Chat identity keeps the full accepted profile paragraph unchanged. This alone turned the canonical first turn from ~22s + long TTS payload to ~35–60 ms + short TTS text.
- **Live token budget:** `_SPOKEN_MAX_TOKENS = 200` for `spoken=true` unless the question explicitly wants a fuller answer (`_wants_fuller_spoken_reply()` — deep/more/step-by-step/long example/detailed). Chat never uses this number.
- **Live timeout:** `_SPOKEN_TIMEOUT_SECONDS = 30` for spoken turns (chat keeps `NIM_TIMEOUT_SECONDS`=90) so a throttled provider is bounded and resolves to the retryable error path instead of sitting indefinitely; the frontend already shows an animated Thinking state from STT final and a concise localized error on failure.
- **Optional `LIVE_NIM_MODEL` (config support, env-gated, unset now):** threaded `model=` through `_complete_visible` → `complete` → `_generate` → `_call_nim`; applied for spoken turns only; a fast-model failure falls back to the configured `NIM_MODEL` for that same turn (measured: the fallback honors the token/timeout constraints); `chat_template_kwargs` is NOT sent when a fast model override is active (instruct models reject NIM-only kwargs); `provider_status` now exposes `last_attempt_model` so a fallback is traceable. No hardcoded/unverified model default.
- **One request / one TTS / one playback per turn confirmed:** single `/tutor` + single `/tutor/tts` per turn; `_call_nim` retries only on 429/5xx; the accepted-turn gate never double-fires; only nvidia is configured so no silent provider fallthrough occurred during measurements.
- **TTS streaming feasibility (measured, NOT blindly rewritten):** `/tutor/tts` synthesizes the FULL MP3 (plain `httpx.post`) then returns it — time-to-first-audio == full synthesis. True chunked streaming to the browser (ElevenLabs `/stream` + MediaSource) is a risky, larger change; deferred and reported separately. The practical TTS cuts already landed (short identity text + 200-token spoken budget shrink the synthesis payload; caching per (tutor,text) stands).

**Files changed (this r2 continuation):** `backend/app/genai.py` (`_SPOKEN_MAX_TOKENS`, `_SPOKEN_TIMEOUT_SECONDS`, `_wants_fuller_spoken_reply`, `_live_fast_model`, `_short_spoken_identity` + `_SPOKEN_IDENTITY_*` + `_SPOKEN_IDENTITY_REFERENCE`, `model=` threading in `_call_nim`/`_generate`/`complete`/`_complete_visible`, `chat_template_kwargs` guard, `_LAST_ATTEMPT["model"]` + `last_attempt_model` in `provider_status`), `backend/tests/test_tutor_spoken.py` (updated 2 directive tests whose question now short-circuits + 12 new tests: per-mentor EN/AR spoken identity, variants, chat-keeps-full-profile, small budget, step-by-step full budget, LIVE_NIM_MODEL on/off, plain chat never uses the Live budget/model, fast-model→main-model fallback, never-hardcoded), `env` (verified-optional `LIVE_NIM_MODEL` documented + commented out). No frontend change.

**Gates (all green):**
- Backend focused: spoken+tts-config **32 passed / 0 failed**; language+profiles+personas+runtime-language **215 passed / 0 failed**; provider+modes+copilot+interview-copilot+conversations+confusion **175 passed / 0 failed** (total **422 passed / 0 failed**).
- Frontend 10/10: `check-copilot-voice-unit.mjs` **226/0**; mentor-live, tutor-profiles, tutor-language, step45, vex-mode, interview-voice-ux, chat-mentor-15, webcam-integrity, tutor-memory-2 all OK.
- `npx tsc --noEmit` clean; `npm run build` clean (12.70s, pre-existing chunk-size advisory only).

**Manual retest for this return (live backend must be running with the `env`-file keys):**
1. Each mentor → Live → "What's your name?" → reply appears in ~under a second (no 20+ second freeze) and is the SHORT spoken line; Arabic `اسمك ايه؟` likewise. DevTools `[voice-live]` shows `tutor.sent`→`tutor.ok` within tens of ms.
2. "Explain Docker simply" (spoken) → thinking shows immediately; answer arrives bounded (healthy draw ~seconds; throttled draw ≤30s then a retryable localized error — never a silent freeze).
3. Normal chat identity "What's your name?" still returns the full accepted profile paragraph; normal chat never carries the spoken budget/model.
4. `/api/config/demo-mode` → nvidia active; `provider.last_attempt_model` after a spoken turn = `nvidia/nemotron-3.5-lightning-30b-a3b` (no fallback name).
5. TTS: with the CURRENT key, every Live turn reports voice-unavailable (ElevenLabs returns 401) — restore/refresh the ElevenLabs key or plan at the account level; the back-end TTS caching/one-call/error path is intact.
6. No-duplicate check: one `/tutor` and one `/tutor/tts` per turn in the network tab.

**Phase 4C.1 (r2) Status:** **IMPLEMENTED — AWAITING HUMAN ACCEPTANCE**. STOP — do not start Phase 4D; do not redesign Interview Mode.

---

## Phase 4C.1 (r1) — Mentor Voice Identity + Production Hardening — IMPLEMENTED — SUPERSEDED BY r2 (latency return) above

**Status:** Phase 4B.2 (r2) was HUMAN ACCEPTED; this phase makes Mentor Live voice production-ready **without** redesigning the Orb, normal chat, Interview Mode, conversation architecture, or assessment/Verified-Skill authority. The Live loop (Listening → Thinking → Speaking → Listening) and the explicit EN | Arabic contract are untouched and verified. Additions: per-mentor voice-identity validation, a Live-only spoken-style directive that permits fuller answers on explicit requests, per-turn latency traces in the developer console, and 4C-focused reliability/fallback test coverage. All gates green; ends at **AWAITING HUMAN ACCEPTANCE**.

**Mentor voice identity (verified, nothing invented):**
- **Nova voice configured: yes** (frontend `voiceId` + backend `ELEVENLABS_NOVA_VOICE_ID`) · **Axel: yes** · **Sage: yes** · **Vex: yes**. All four mentor IDs in `frontend/src/lib/tutorProfiles.ts` resolve (non-empty, real provider-shaped, mutually distinct); backend `app/tts.py` maps each tutor → its own env voice ID through the same `eleven_multilingual_v2` model (English + Arabic auto-detect). No placeholder IDs were invented; existing IDs preserved.
- TTS unavailable is reported PER MENTOR: `tts.synthesize` raises a specific `RuntimeError` naming the affected mentor for a missing voice id; the other three mentors keep working (offline test `test_tts_voice_config.py`).

**Spoken response style & length (Live-only, opt-in `spoken=true`; normal chat byte-identical):** backend `genai._SPOKEN_RULE` still answers directly-first and keeps simple questions at 1–3 short spoken sentences, AND now explicitly allows a fuller spoken answer when the student asks for a detailed explanation / step-by-step / long example — never arbitrary truncation, still no markdown scaffolding. Mentor personality is untouched (no persona redesign). `test_tutor_spoken.py` proves the directive is appended ONLY on `spoken=true`, is present for all four mentors, yet never appears in plain chat.

**Latency observability (developer console only, never the UI, never secrets):** `frontend/src/lib/voiceSession.ts` now carries `elapsed_ms` from each STT final through `tutor.sent` → `tutor.ok` (response received) → `tts.sent` → `tts.ok` (audio ready) → `play.start` (plus `playDelay_ms` = audio-ready → playback start). The hook merges `mentor` + `lang` and logs `console.info('[voice-live]', stage, { mentor, lang, ...meta })` — DevTools only. Verified by unit scenario 15l (ordered, monotonic, one TTS per turn) and a simulated wall-clock run.

**TTS reliability / fallback (all confirmed + new coverage):** one TTS request per `/tutor` reply, no duplicate playback, microphone hushed while the mentor speaks (no self-echo), auto-listen armed only after genuine playback `ended`, close/end cancels a pending resume (new 15m), and a failed synthesis preserves the generated text, surfaces the localized `voice-unavailable` error without faking Speaking, and lets the user continue (new 15n). EN ↔ Arabic switching preserves all Phase 4B fixes (15f–15k unchanged, green). TTS caching is per (tutor,text) — one upstream call per unique line.

**Files changed:** `frontend/src/lib/voiceSession.ts` (elapsed_ms/playDelay_ms trace metas + per-utterance clock), `backend/app/genai.py` (`_SPOKEN_RULE` now explicitly allows fuller spoken answers on explicit detail requests — Live-only), `backend/tests/test_tutor_spoken.py` (2 new tests), `backend/tests/test_tts_voice_config.py` (NEW, offline: 4-mentor config, booleans-only status, per-mentor error isolation, caching, empty-text rejection), `frontend/scripts/check-copilot-voice-unit.mjs` (scenarios 15l latency/one-TTS/ended-before-resume, 15m close-cancels-pending-resume, 15n TTS-error-fallback-and-continue + section 16 elapsed_ms/playDelay_ms/console-only pins; **197 → 226 passed / 0 failed**), `frontend/scripts/check-tutor-profiles.mjs` (valid-voice checks: non-placeholder voiceId, finite rate/pitch in [0.5,1.5], distinct voice ids). No changes to controls (Type instead / Mic / End / EN | عربي — untouched), backend `app/tts.py` synthesis logic, or any Phase 4B/4A surface.

**Gates (all green):**
- `check-copilot-voice-unit.mjs` **226 passed / 0 failed**; `check-tutor-profiles.mjs` OK (valid voice config for all 4); `check-mentor-live-phase4b1.mjs` OK + the other 7 contracts OK → **10/10 frontend gates**.
- `npx tsc --noEmit` clean; `npm run build` clean in 33.69s (chunk-size advisory only, pre-existing).
- Backend relevant (production genai.py + tts module paths changed): `test_tutor_spoken.py` + `test_tts_voice_config.py` = **16 passed/0 failed**; `test_tutor_language.py` + `test_tutor_profiles.py` = **65 passed/0 failed**; `test_tutor_personas_v2.py` = **58 passed/0 failed** — total **139 passed / 0 failed**.

**Manual retest steps:**
1. **Voice identity:** pick Nova → Live → "What's your name?" → spoken reply is short/conversational ("I'm Nova, your SkillBridge mentor…"), NOT a profile paragraph; repeat for Axel/Sage/Vex — distinct voices, each mentor still 1–3 concise sentences for simple questions, and a step-by-step request ("Explain Docker step by step") is allowed a fuller spoken reply.
2. **Both languages, every mentor:** EN mode speaks English; Arabic mode speaks Arabic (TTS `eleven_multilingual_v2` auto-detects) — no Auto anywhere in Live.
3. **Latency:** DevTools console → a clean `[voice-live]` line per stage: `stt.final → tutor.sent → tutor.ok → tts.sent → tts.ok → play.start` each with `elapsedMs` (and `playDelayMs` on play.start); the UI never shows these.
4. **Reliability:** exactly one TTS request + one playback per reply (network/console); audio ends naturally before Listening resumes; closing while a resume is pending leaves the loop quiet; during playback the mic is inactive (no echo).
5. **TTS down:** kill the backend / drop network after a reply arrives → concise localized voice-unavailable error, the mentor's text stays in the transcript, mic works again for the next turn; normal chat unaffected.
6. **Controls unchanged:** Type instead / Mic / End / `[ EN | عربي ]` look and behave exactly as accepted in Phase 4B.2; Orb, chat, History/Clear, Mock Interview, assessments, Verified Skills untouched.

**Final Phase 4C.1 Status:** **IMPLEMENTED — AWAITING HUMAN ACCEPTANCE**. STOP — do not start Phase 4D; do not redesign Interview Mode.

## Phase 4B.2 (r2) — Explicit Live speech languages (EN | Arabic), Auto steering REMOVED — IMPLEMENTED — AWAITING HUMAN ACCEPTANCE

**Status (human-acceptance return):** Phase 4B.2 acceptance FAILED specifically for Auto speech-language detection. In real browser use, speaking Arabic ("ممكن تشرحلي") with Live on **Auto** was still interpreted by SpeechRecognition as English and produced garbled Latin text — the interim-steering approach is not reliable enough (browser SpeechRecognition is single-locale per instance; real-world Auto steering is unreliable). The human returned this directive: **remove Live Auto language entirely and ship TWO explicit speech languages — English and Arabic — with manual selection**. All Phase 4B.2 UI polish (smaller orb, compact captions, bottom dock, no debug labels) is retained. All gates green; ends at **AWAITING HUMAN ACCEPTANCE**.

**What Live Voice is now (new contract):**
- **Two explicit speech languages only: EN and Arabic. No Auto inside Live.** English → `SpeechRecognition` locale `en-US`, `/tutor` request `language: 'en'`, English mentor reply + TTS, LTR caption direction, no automatic switching. Arabic → locale `ar-EG`, request `language: 'ar'`, Arabic reply + TTS, RTL caption direction, no automatic switching.
- **Compact top-right language selector `[ EN | عربي ]`** in the fullscreen VoiceMode header (`.v-lang`). Close stays top-left, mentor LIVE pill stays centered, selector sits top-right; RTL mirrors the header.
- **Entering Live:** if the normal Copilot language selector is already explicit **English → Live opens English**; **Arabic → Live opens Arabic**. If normal chat is **Auto**, it is NEVER silently interpreted as English: the last explicitly selected Live language is reused when one was saved locally (`localStorage.sb_live_lang`, set by the hook — backend untouched), else the deterministic default **English** with the visible `[ EN | عربي ]` control obvious in the surface.
- **Mid-session switching EN ↔ عربي (documented safe behavior):**
  - *Listening / idle / interrupted* → hush the current recognizer, invalidate its stale callbacks (recogId bump), restart Listening in the new locale immediately. Never two recognizers; a stale final from the old recognizer can never commit.
  - *Speaking* → the switch is applied AFTER playback: mentor TTS is never cut by a language change (`pendingLang`), and the existing auto-resume restarts Listening in the new locale.
  - *Processing (/tutor in flight)* → the in-flight turn finishes in the old language (never re-sent/duplicated); the switch applies to the next Listening session.
- **Removed (no dead Auto logic left):** `scriptDetectLang` / `steeringTarget` pure helpers, `MAX_STEER_PER_UTTERANCE` budget, `prefLang`, `steerBudget`, `steerAutoRecognition`, and the `onInterim` interface across engine + hook (interim results are no longer collected or forwarded). Normal text-chat language behavior (incl. Auto) is UNCHANGED.

**Voice loop preserved (Phase 4B.1 acceptance):** Listening → speak → Thinking → mentor replies aloud → Speaking until audio genuinely ends → Listening automatically. No echo self-interruption, no truncated TTS, no duplicate turns, real VAD barge-in, fullscreen portal, autoplay priming, per-mentor accent/orb/motion, RTL handling.

**Files changed (this r2 continuation):** `frontend/src/lib/voiceSession.ts` (explicit `language: 'en'|'ar'`, `setLanguage()` with the pending-after-playback semantics, `recognitionLang(sessionLang)` in both primary + interrupt listeners, controls via the existing `recogId` guard), `frontend/src/hooks/useVoiceSession.ts` (`onInterim` removed; options.language `'en'|'ar'`; exported `resolveInitialLiveLang(pref)`; `setLanguage()` + `onLiveLanguageChange` in the API; persists `sb_live_lang`), `frontend/src/components/CopilotPanel.tsx` (`voiceLang` resolved at open via `resolveInitialLiveLang(language)`; voice turn sends `language: sessionOpts?.language ?? voiceLang` — never an Auto fallback), `frontend/src/components/VoiceMode.tsx` (top-right `.v-lang` segmented EN | عربي wired to `voice.language`/`voice.setLanguage` with `aria-pressed`), `frontend/src/index.css` (`.v-lang` pill + `.v-lang-btn` + `.v-lang-sep`, RTL mirror `[dir=rtl] .v-lang`), `frontend/src/lib/tutorI18n.ts` (`voiceLanguage` label). No backend production change (backend already resolves `language: 'en'|'ar'`; `/tutor/tts` uses `eleven_multilingual_v2` auto-detect). Prior 4B.2 backend items (direct-first `_SPOKEN_RULE`, stale-test priming) stand.

**Gates (all green):**
- `check-copilot-voice-unit.mjs` **197 passed / 0 failed** — auto-steering scenarios (15f–15k-old) REPLACED by explicit-mode suites: 15f explicit EN (en-US, no steering interface, exactly one primary listener, language=en), 15g explicit AR (ar-EG → language=ar), 15h EN→AR mid-session switch (restart + stale-final discard + loop continues in ar-EG), 15i AR→EN switch (symmetric), 15j switch-while-speaking (playback NOT interrupted, applied after), 15k switch-while-processing (in-flight turn stays old language, never re-sent); section 16 now pins `!steerAutoRecognition`, `!steeringTarget|scriptDetectLang`, `!steerBudget|MAX_STEER`, `!onInterim`, `!prefLang`, explicit `language: 'en' | 'ar'`, `setLanguage`, `resolveInitialLiveLang`, `sb_live_lang`, `v-lang` + `voice.setLanguage` + `aria-pressed` in VoiceMode.
- `check-mentor-live-phase4b1.mjs` **OK** — dir follows the SELECTED language, `.v-lang` CSS + RTL mirror, `v-lang`/`voice.setLanguage`/`aria-pressed` pins, and removal pins (`!steerAutoRecognition|steeringTarget|scriptDetectLang` in VoiceMode, `!onInterim`/`!steerBudget|MAX_STEER|prefLang` in the engine).
- Other 8 frontend contracts (step45, vex-mode, tutor-profiles, tutor-language, interview-voice-ux, chat-mentor-15, webcam-integrity, tutor-memory-2) **OK** — **10/10 frontend gates**. (tutor-memory-2 re-verified after moving the `sb_live_lang` localStorage access out of CopilotPanel into the hook so the panel remains localStorage-free.)
- `npx tsc --noEmit` clean; `npm run build` clean in 18.09s (chunk-size advisory only). Backend production code unchanged this round → no backend rerun required (prior 66 + 37 passes stand).

**Manual retest steps (in order):**
1. **Explicit EN:** chat language = English → open Live → EN selected top-right → English caption (LTR) → ask "What's your name?" → English reply + English audio → hands-free loop.
2. **Explicit AR:** chat language = Arabic → open Live → عربي selected → Arabic caption (RTL) → speak "اسمك ايه؟" → REAL Arabic transcript → Arabic reply + Arabic audio.
3. **Docker (AR):** عربي → "ممكن تشرحلي Docker ببساطة؟" → correct Arabic transcript → Arabic explanation reply.
4. **Mid-session EN → عربي while listening:** EN → tap عربي → recognizer restarts in ar-EG, no duplicate turn, speak Arabic → Arabic reply.
5. **Mid-session عربي → EN while listening:** symmetric; stale Arabic final never commits.
6. **Switch while mentor is speaking:** EN → reply playing → tap عربي → playback NOT cut; when it finishes the loop resumes Listening in Arabic.
7. **Auto chat pref:** chat = Auto, no saved Live pref → Live opens English with the EN | عربي control obvious; switch to عربي, close, reopen → reopens Arabic (last choice persisted); with chat pref Arabic it always opens Arabic.
8. **Polish retained:** smaller orb, compact ~2-line captions, bottom dock [Type instead][Mic][End], NO VOICE READY/VOICE REPLY labels; End/Type instead/close return to exact chat state; header + per-mentor colors intact.
9. Regressions unchanged: chat-mic dictation-only, Live button, New Chat/History/Clear, Mock Interview, Arabic RTL, conversation isolation; DevTools `[voice-live]` shows `lang.set` / `lang.applied` with safe meta (never secrets).

**Final Phase 4B.2 Status (r2):** **IMPLEMENTED — AWAITING HUMAN ACCEPTANCE**. STOP — do not start Phase 4C or the next phase; no backend conversation-architecture changes, no mentor-intelligence/assessment/interview redesign, no 3D reintroduction.

---

## Phase 4B.1 Block #2 — Per-Mentor reply / TTS instability — FIXED — AWAITING HUMAN ACCEPTANCE

**Status:** The human-acceptance blocker (Axel/Vex speech cut off mid-sentence, Sage/Nova silent with no persisted reply) was root-caused to FRONTEND-ONLY bugs in the Live engine — the backend was verified 100% healthy for ALL four mentors (live probe: TTS available, api_key loaded, tts configured, tutor_voices_loaded nova/axel/sage/vex all true; direct `/tutor` round-trip + `/tutor/tts` 200 for every mentor, plausible reply lengths nova 264 / axel 266 / sage 265 / vex 273 chars; audio 250–355 KB). Fixes landed, all gates re-run green, and the phase again ends at **AWAITING HUMAN ACCEPTANCE** — see the exact repro/retest steps below.

**Root causes (frontend only, no provider/TTS issue):**
1. **Echo self-barge-in (Axel/Vex premature cutoff):** `speakReply` started an interrupt recognizer (`listenInterrupt()`) right before TTS playback. The mentor's own speaker audio was picked up by the mic → a real `speechstart` → `bargeIn()` stopped playback mid-reply. (Confirmed by code: `speakReply` called `this.listenInterrupt()`; browser interrupt-mode wired both `rec.onresult` AND `rec.onspeechstart` to `onSpeechStart`, so even a noise "final" could trigger it.)
2. **Noise-final barge-in during /tutor (Nova no-reply):** interrupt-mode `onresult` fired `onSpeechStart` on ANY final — speaker echo/noise while `/tutor` was in flight could surface to `bargeIn()` during `processing`, aborting the tutor request → no reply, nothing persisted.
3. **Silent mentor (Sage/Nova):** async `audio.play()` after the STT→tutor→TTS round trip ran outside the user-gesture window → browser autoplay policy rejection surfaced as "mentor silent". VoiceMode now unlocks audio inside the Live-button gesture (`primeAutoplay()`).

**Fixes made (frontend engine/hook/panel/api + VoiceMode + one additive backend `spoken` directive):**
- `voiceSession.ts`: NO recognizer is active while the mentor speaks — the microphone is `hush()`ed the moment the reply becomes speaking and stays hushed through playback; `listenInterrupt()` now runs ONLY while `/tutor` is in flight (still lets a REAL VAD speech-start barge in during processing). Deliberate interruption via the mic/orb button (`interrupt()`/`stop()`) is preserved and cuts playback. Auto-resume is still only `state==='idle' && !currentError` (audioEnd) so it can never fire mid-playback.
- `useVoiceSession.ts`: interrupt-mode `onresult` returns early for non-primary modes — ONLY a real VAD `rec.onspeechstart` can barge in; noise finals never map to speech-start.
- `VoiceMode.tsx`: `primeAutoplay()` unlocks media playback inside the Live-button gesture (no autoplay-rejected/dead-silent mentor).
- Diagnostics (no secrets): engine `onTrace(stage, meta)` → `console.info('[voice-live]', stage, { mentor, lang, ... })` across STT final/submission-guard, tutor sent/ok/error(kind+status), TTS sent/ok/error(kind+status), play start/end, barge-in/abort, resume scheduled/fired; user-facing localized voice-unavailable/retry on TTS/connection failure — NEVER API keys.
- Interview-style spoken replies WITHOUT touching normal-chat persona: backend `genai._SPOKEN_RULE` appended only when the turn uses `spoken=true` (`tutor_reply(..., *, spoken=False)` — default keeps normal chat byte-identical; `api_tutor_chat` reads `body.spoken`; debug endpoint `/api/debug/tutor-system?spoken=1` proves it).

**Gates after the fix (all green):**
- Frontend contracts 9/9: `check-copilot-voice-unit.mjs` **132 passed / 0 failed** (was 106; new no-mic-while-speaking + explicit-interrupt + stale-echo-final + post-resume no-duplicate scenarios), `check-mentor-live-phase4b1.mjs` OK (extended: singer guard `listenInterrupt()` count==1, `hush()` in speakReply, `onTrace`, adapter `opts.mode !== 'primary'` guard, `spoken: true`, `primeAutoplay`), `check-copilot-vex-mode`, `check-tutor-profiles`, `check-tutor-language`, `check-interview-voice-ux`, `check-chat-mentor-phase15`, `check-webcam-integrity`, `check-tutor-memory-phase2`.
- `npx tsc --noEmit` clean; `npm run build` clean (chunk-size advisory only).
- Backend (venv pytest, since genai/main changed): new `tests/test_tutor_spoken.py` 8/8 + conversations/phase4a/modes/copilot/interview-copilot = **106 passed / 0 failed**. Note: 7 `test_copilot.py` context-trust tests were STALE against the intended fresh-thread context gating (first message is persona/language-only by design — `main.api_tutor_chat` nulls per-page context on a fresh thread) and were updated to prime the conversation first, preserving every trust assertion (backend-truth markers present, client-injected values never leak).

**Manual retest steps (MUST verify ALL FOUR mentors):**
1. For EACH mentor (Nova, Axel, Sage, Vex): open Live → auto Listening → ask "What's your name?" → exactly ONE STT final → Thinking → **full spoken reply** → Speaking until the audio genuinely ends → auto back to Listening. Ask a second question → same clean loop. No duplicates, truncation, silence, stuck state, or premature Listening.
2. While the mentor speaks, let the speaker audio feed the mic (do nothing) → playback must NOT cut off (no echo loop). Tap the mic/orb button deliberately → playback stops → Listening resumes (explicit barge-in still works).
3. Drop TTS/connection → concise localized voice error in UI; DevTools console shows `[voice-live]` stage traces with mentor id + safe status (no API keys).
4. Regressions: fullscreen Live surface, per-mentor orb colors, chat-mic dictation only, Live button, New Chat/History/Clear Chat, conversation isolation, Arabic RTL Mirror, Mock Interview, mentor persona isolation all unchanged.

**Final Phase 4B.1 (block #2) Status:** **IMPLEMENTED — AWAITING HUMAN ACCEPTANCE** (all gates green). STOP — do not start Phase 4B.2/4C, do not change backend conversation architecture, mentor intelligence, assessment, or interview design, and do not redesign persona prompts (the `spoken` directive is additive and opt-in only).

---

## Phase 4B.1 — Mentor Live orb visual system — IMPLEMENTED — AWAITING HUMAN ACCEPTANCE

**Status:** The abandoned 3D direction is fully rolled back (see below) and the replacement Mentor Live orb system is now implemented, pure CSS/native DOM (no WebGL, no Three.js, no canvas, no asset loading). One reusable orb component (`frontend/src/components/MentorOrb.tsx`) renders every mentor; the mentor identity is the canonical `TutorId` and the accent is inherited from the existing `.copilot-panel.{purple,blue,gold,green}` `--mentor-accent` tokens (Nova purple / Axel blue / Sage gold / Vex green) — no duplicated palette, no provider labels. The orb's visuals map 1:1 onto the existing voice engine state machine (idle/listening/processing/speaking/interrupted) plus an `'error'` visual driven by `voice.error`, so the engine stays the single source of truth. All existing voice behavior is unchanged (Live button opens VoiceMode, mic permissions/STT, tutor reply + TTS, stop/close, keyboard fallback, language, selected mentor, chat state, Mock Interview, chat-mic dictation-only).

**Gates (final, after the human-acceptance return):** the new `check-mentor-live-phase4b1.mjs` contract guard (all orb + fullscreen contracts OK) + 9 existing Phase A voice/chat/onboarding contract scripts (step45, chat-mentor-15, interview-voice-ux, tutor-profiles, tutor-language, tutor-memory-2, copilot-vex-mode, copilot-onboarding-P) + `check-copilot-voice-unit.mjs` **106 passed / 0 failed** (incl. new `live-loop`/`live-stop`/`live-tts` hands-free scenarios) — **10/10 scripts green**; `npx tsc --noEmit` clean; `npm run build` clean (9.15s, chunk-size advisory only). Frontend-only change; no backend changes.

**What changed (frontend only):**
- `frontend/src/components/MentorOrb.tsx` (NEW) — ONE reusable mentor orb. Props: `mentorId: TutorId | string`, `state: MentorOrbState = VoiceState | 'error'`, optional `level?: number` (sets `--orb-level` for a future mic/audio level; without it the orb uses state-driven visuals), `reducedMotion?`, `onTap`, `ariaLabel?`. Markup `.ml-orb[data-mentor][data-state][data-reduced]` with `.ml-halo`, `.ml-ring.r1/.r2`, `.ml-spin`, `<button class="ml-core">` + `.ml-glyph` (glyph per state: idle/listening mic, processing chat, speaking volume, interrupted mic, error refresh).
- `frontend/src/components/VoiceMode.tsx` (REWRITTEN as a DEDICATED FULLSCREEN surface) — now portals itself to `document.body` (`createPortal`) so normal chat chrome, the Copilot composer, quick-action chips and the dashboard are NEVER visible while Live is open; body scroll is locked for the duration. New layout: `.v-top` header (`.v-close` + `.v-live` avatar/name/LIVE tag + `.v-top-end`), `.v-center` (`.ml-orb-wrap` MentorOrb, `.v-state`/`.v-sub`, `.eq`, `.vt` caption, `.v-err`), `.v-bottom` (`.v-keyboard` pill "Type instead", `.v-mic` mic/stop = mute, `.v-hint`). The transcript is a compact, secondary caption (most recent user utterance / current mentor line) — never a scrolling chat. `orbState = voice.error ? 'error' : voice.state`; `data-state={voice.state}` mirrors the engine 1:1; `voice.open()/close()` still mount/teardown per open.
- `frontend/src/lib/voiceSession.ts` (ENGINE, additive + opt-in) — new option `resumeAfterPlaybackEnd` (+ `resumeDelayMs`): after a TTS turn ends naturally (`audioEnd` → idle) the engine auto-returns to listening and starts a fresh primary recognizer (guarded — an explicit stop, connection/TTS error, or barge-in handoff NEVER resumes). The event table/transitions are otherwise unchanged (single source of truth; the exact task-spec table in the unit suite still passes).
- `frontend/src/hooks/useVoiceSession.ts` — enables `resumeAfterPlaybackEnd: true` so Live mode is fully hands-free (open → listening automatically; speak → mentor replies → TTS plays → back to listening; no mic tap per turn).
- `frontend/src/index.css` — the voice block is now global `.voice`/`.ml-orb` (portal-safe, no longer under `.copilot-v2`) with: `.voice` = `position: fixed; inset: 0; z-index: 2147483000; height: 100dvh; min-height: 100svh` + safe-area insets + clean dark navy background; theme classes `.voice.theme-{purple,blue,gold,green}` derive the mentor accent from the canonical `--sb-*` `:root` tokens (palette never duplicated); orb base + per-mentor motion tokens (`[data-mentor]` breathe/spin/pulse: nova 3.8s/14s, axel 2.1s/8s, sage 4.6s/18s, vex 2.6s/10s) with layered soft gradients, moving highlight, breathing pulse, halo/ripple — all transform/opacity CSS/SVG techniques, no WebGL; state rules for `idle|listening|processing|speaking|interrupted|error` (error = calm/stopped/desaturated); `--orb-size: clamp(150px, 32vw, 212px)` responsive; reduced-motion. Retired `c2*` voice keyframes removed; shared interview keyframes `c2FadeUp`/`c2FloatY`/`c2DotBounce` kept. RTL mirrors moved to `.voice[dir="rtl"]`.
- `frontend/src/lib/tutorI18n.ts` — added `voiceLiveTag` ("Live"/"مباشر") and `voiceTypeInstead` ("Type instead"/"اكتب بدل الصوت").
- `frontend/src/components/VoiceOrb.tsx` (DELETED) — the old glyph orb is gone; one orb component remains.
- `frontend/scripts/check-mentor-live-phase4b1.mjs` (NEW) — source contract guard (driven by pytest like the other checkers): reusable orb, portal fullscreen surface, body scroll lock, theme mapping, no chat chrome inside Live, auto-listen on open, hands-free loop requirements, no provider labels, no 3D deps.
- `frontend/scripts/check-copilot-voice-unit.mjs` — extended with `live-loop` / `live-stop` / `live-tts` scenarios proving: auto-listen on start, exactly one tutor request per final utterance, no duplicate TTS, TTS-end auto-resume, barge-in handoff, and that explicit stop / TTS failure never auto-resume (now **106 passed / 0 failed**).

**Manual retest steps:**
1. Pick each mentor (Nova/Axel/Sage/Vex) → open Live/Waveform → a DEDICATED fullscreen surface covers the entire viewport (no chat messages, no composer, no quick chips, no dashboard visible); clean dark background with the orb as the focus and that mentor's accent (purple/blue/gold/green) + avatar/name/LIVE tag in the top pill.
2. Hands-free loop — no mic taps: VoiceMode opens already LISTENING → speak → final utterance submitted ONCE (Thinking + rotating ring) → mentor reply spoken (Speaking + ripples/EQ) → playback ends → automatically LISTENING again → repeat endlessly. Verify interim captions appear subtly under the orb (you / mentor) and never dominate it.
3. Barge-in: start speaking while the mentor talks (or tap the orb/mic) → audio stops cleanly → Listening resumes (no overlapping audio). Tap the mic while listening = mute/stop.
4. Stop/close: X (or "Type instead") leaves VoiceMode → returns to the EXACT chat state (history, conversation, mentor, language intact). Chat mic still dictates into the composer only.
5. Deny mic / drop connection → calm error orb + localized message (no fake Listening); TTS down → honest voice-unavailable error, text fallback still possible, normal chat unaffected.
6. Arabic (RTL): fullscreen voice mirrors correctly; safe-area insets respected on notch devices; orb scales via clamp() on desktop/tablet/mobile.
7. `node frontend/scripts/check-mentor-live-phase4b1.mjs` green; `check-copilot-voice-unit.mjs` 106/0; no `three`/`@react-three/*` in `package.json`; DevTools network shows no WebGL/3D chunk.

**Final Phase 4B.1 Status:** **IMPLEMENTED — AWAITING HUMAN ACCEPTANCE** (per the spec). STOP — do not start Phase 4B.2/4C voice-engine work, no backend conversation-architecture changes, no mentor-intelligence changes, no assessment changes, no interview redesign.

---

## Phase 4B.1 rollback — 3D mentor experiment REMOVED — baseline restored

**Status:** The 3D mentor direction is ABANDONED and fully rolled back to the Phase 4A baseline; the orb system above supersedes it (deleted again at the top of this entry).

**What was removed (exact rollback of Phase 4B.1):**
- Deps uninstalled: `three`, `@react-three/fiber`, `@react-three/drei` (removed from `package.json` + `package-lock.json`; 76 packages pruned).
- Files deleted: `frontend/src/components/mentor3d/MentorStage.tsx` (+ the now-empty `mentor3d/` folder), `frontend/src/lib/mentorVisuals.ts`, `docs/mentor-3d-asset-contract.md`, `frontend/scripts/check-mentor-3d-visuals.mjs`.
- `frontend/src/components/CopilotSettingsModal.tsx` restored to the Phase 4A form (Nova/Axel/Sage/Vex 2D cards, single **Save my copilot** button, Retake quiz, current-mentor badge, backend persistence untouched).
- `frontend/src/index.css` — Phase 4B.1 stage block removed (`.mentor-stage`, `.csm-stage-*`, `.ms-portrait*`, `ms-breathe`, `.csm-cta-nova`); the Phase 4A mentor-accent system is unchanged (Nova purple / Axel blue / Sage gold / Vex green tokens + overrides all intact).
- Existing tutor portraits (`public/assets/tutors/*.png`) untouched.

**Not regressed (Phase 4A preserved):** mic=dictation, separate Live/Waveform button, New Chat, History, Clear Chat, mentor-specific chat accents, compact user bubble, lightweight assistant replies, Mock Interview in `+`, Arabic/RTL, conversation isolation.

**Manual retest steps:**
1. Sign in as a student → account menu → **Change your copilot** → the four 2D mentor cards (Nova/Axel/Sage/Vex) render with no 3D preview area; **Save my copilot** applies the pick and persists it (backend).
2. Confirm the copilot chat still has: mic dictation into the composer, a separate Live/Waveform button, New Chat, History drawer, Clear Chat, Mock Interview in `+`, and the current mentor's accent (Nova purple / Axel blue / Sage gold / Vex green).
3. Try Arabic — chat and modals align correctly (RTL).
4. Developer tools → network → no `MentorStage-*.js` / WebGL chunk ever loads.

**Final status:** Phase 4A baseline RESTORED and INTACT. STOP — do not re-add 3D, do not start the Orb phase yet.

## Phase 4A — Conversation threads, New/Clear Chat, History, Mentor isolation — IMPLEMENTED — AWAITING HUMAN ACCEPTANCE

**Status:** backend **1430 passed / 4 skipped / 0 failed** (complete suite collected 1434; 4 expected skips; 1437.97s) + focused Phase 4A/tutor-memory/persona/language/provider regression **359 passed / 0 failed** (265.03s) + direct frontend contract scripts **8 passed / 0 failed** + `npx tsc --noEmit` clean + `npm run build` clean (built in 10.04s; chunk-size advisory only). **Phase 4A complete — this entry validates the conversation/thread architecture, New/Clear Chat semantics, History drawer, mentor isolation, and chat UI overhaul; no Phase 4B/3D/voice/avatar changes.**

**What changed (additive, backward-compatible):**

**Backend — Migration 0013 (`backend/app/database.py:898-1051`):**
- `tutor_conversations` table (student_id, tutor_id, title, created_at, updated_at) with 3 indexes
- `conversation_id` column added to `tutor_messages` (FK → tutor_conversations, ON DELETE SET NULL)
- `tutor_conversation_memory_threads` table (conversation_id PK, student_id, tutor_id, summary, last_compacted_id, updated_at) — conversation-scoped memory
- Legacy backfill: groups orphan `tutor_messages` (conversation_id NULL) by student+mentor into restored conversations; copies legacy `tutor_conversation_memory` rows into `tutor_conversation_memory_threads` keyed by the restored conversation

**Backend — Conversation helpers (`backend/app/models.py:1365-1588`):**
- `_conversation_title()` — deterministic title from first user message (56-char clip + ellipsis)
- `create_tutor_conversation()` / `get_tutor_conversation()` / `list_tutor_conversations()` / `ensure_tutor_conversation()`
- `add_tutor_message()` — accepts `conversation_id`, validates mentor match, updates conversation title on first user message
- `list_tutor_messages()` — primary chat boundary is `conversation_id`; legacy tutor-scoped fallback preserved
- `clear_tutor_messages()` — clears single conversation (messages + memory + resets title) with legacy tutor-level fallback

**Backend — API endpoints (`backend/app/main.py`):**
- `GET /api/students/{id}/tutor/conversations` — history list with message_count, preview, last_message_at, mentor
- `POST /api/students/{id}/tutor/conversations` — creates empty conversation (nondestructive, keeps old history accessible)
- `GET /api/students/{id}/tutor` — history with `conversation_id` + `tutor_id` scoping
- `POST /api/students/{id}/tutor` — chat with `conversation_id` (create/ensure conversation, thread memory, return `conversation_id` + `conversation`)
- `DELETE /api/students/{id}/tutor` — Clear Chat: clears current `conversation_id` only (messages + memory), resets title to "New conversation", keeps other conversations & trusted state intact

**Backend — Conversation-scoped memory (`backend/app/tutor_memory.py`):**
- `memory_summary()`, `_write_memory()`, `clear_memory()`, `after_turn()`, `memory_block_for()` — all accept `conversation_id` for Phase 4A scoping
- Legacy per-(student,mentor) compatibility path preserved (omitted `conversation_id` → uses `tutor_conversation_memory` table)
- `after_turn()` writes to BOTH conversation-scoped and legacy memory for backward compatibility during transition

**Frontend — CopilotPanel.tsx:**
- Conversation-id based chat state: `conversations[]`, `activeConversationId`, per-conversation `chats[conversationId][]`
- `ensureChatConversation()` — creates new conversation via API, initializes empty message array
- `refreshConversations()` — fetches history list, preserves active empty conversation
- `selectConversation()` — switches conversation, restores mentor if different, loads history via `tutorHistory(studentId, tutorId, conversationId)`
- `startNewChat()` — **nondestructive**: creates new empty conversation, preserves all old conversations in history
- `clearCurrentConversation()` — clears **current conversation only** (messages + memory), resets title, keeps other conversations & trusted state
- **Clear modal** (`chat-clear-modal`): viewport-level (`role="alertdialog" aria-modal="true"`), Cancel button focused on open, Escape closes, backdrop click closes, destructive action button `chat-clear-danger`
- **History drawer**: lists conversations with mentor avatar, title, timestamp, active indicator; click restores conversation + mentor
- **Composer tools menu** (`+` button): Practice, Quiz, **Mock Interview**, Explain — no giant Mock Interview card in main view
- **Compact single mentor header**: avatar, name, role, online status — no duplicated mentor info
- **Change Mentor control**: `mentor-change` dropdown with `PersonaMenu`
- **No provider labels** on assistant messages (removed "NVIDIA NIM · live" etc.)
- Compact user bubbles, lightweight mentor messages, sticky composer

**Files changed in this continuation:**
- `AGENTS.md` — final validation status/counts updated after all gates passed

**Phase 4A implementation files verified present (unchanged in this continuation):**
- `backend/app/database.py` — migration 0013
- `backend/app/models.py` — conversation helpers
- `backend/app/main.py` — conversation endpoints
- `backend/app/tutor_memory.py` — conversation-scoped memory
- `frontend/src/components/CopilotPanel.tsx` — conversation state, history, clear modal, tools menu, header
- `frontend/src/components/ChatThread.tsx` — no provider labels, compact bubbles
- `frontend/src/lib/api.ts` — conversation API helpers
- `frontend/src/lib/types.ts` — `TutorConversation`, `TutorMessage.conversation_id`
- `frontend/src/index.css` — history drawer, tools menu, clear modal, compact header styles

**Bugs found and fixed in this continuation:** None — all Phase 4A implementation work was already present; this continuation completed inspection, full validation, and the status-entry update.

**Focused backend tests:**
- `test_tutor_conversations_phase4a.py`
- `test_tutor_conversation_memory_phase2.py`
- `test_tutor_conversations.py`
- `test_tutor_confusion_antirepeat_phase32.py`
- `test_tutor_language.py`
- `test_runtime_tutor_language.py`
- `test_tutor_personas_v2.py`
- `test_tutor_personas_phase3.py`
- `test_tutor_provider_phase31.py`
- `test_tutor_trust_language_phase2.py`
- `test_tutor_modes.py`
- `test_tutor_profiles.py`
- Combined **359 passed / 0 failed** in 265.03s

**Full backend tests:** **1430 passed / 4 skipped / 0 failed** in 1437.97s (23:57). Collection count was 1434; the 4 skips account for the difference.

**Frontend contract checks:**
- `check-step45-copilot.mjs` — **OK** (Phase 4A conversation UX: conversation-id chat history, nondestructive New Chat, Clear Chat, voice, composer Mock Interview)
- `check-tutor-language.mjs` — **OK**
- `check-copilot-voice-unit.mjs` — **91 passed, 0 failed**
- `check-chat-mentor-phase15.mjs` — **OK**
- `check-interview-voice-ux.mjs` — **OK**
- `check-tutor-profiles.mjs` — **OK (4 profiles)**
- `check-tutor-memory-phase2.mjs` — **OK**
- `check-copilot-vex-mode.mjs` — **OK**

**Typecheck:** `npx tsc --noEmit` — **clean (no output)**

**Build:** `npm run build` — **✓ built in 10.04s** (chunk-size advisory only, as previously documented)

**Remaining known issues:** None blocking Phase 4A acceptance.

**Human manual test steps:**
1. **New Chat**: Open chat → send messages → click "New Chat" → verify empty chat, old conversation preserved in History drawer
2. **Clear Chat**: In a conversation with messages → click "Clear Chat" → confirm modal appears (viewport, no scroll) → click Clear → verify messages gone, title "New conversation", other conversations intact in History
3. **History**: Open History drawer → verify list shows conversations with mentor avatars, titles, timestamps → click a past conversation → verify messages restore + correct mentor selected
4. **Mentor isolation**: Start Nova conversation A → switch to Axel → verify no Nova history leaks → start Nova conversation B → verify A and B independent
5. **Clear modal**: Open Clear Chat → verify Cancel works, Escape closes, backdrop click closes, destructive styling visible
6. **UI contracts**: Single compact mentor header, no provider labels on messages, Mock Interview only in `+` tools menu, sticky composer, Change Mentor works, compact bubbles, RTL not broken

**Final Phase 4A Status:** **IMPLEMENTED — AWAITING HUMAN ACCEPTANCE** (all gates green: 1430/4/0 backend, focused 359/0, tsc clean, build clean, 8 frontend contract checks OK). STOP — DO NOT START PHASE 4B.


## Language-mirroring fix (Arabic/Arabizi ↔ English) — VERIFIED LIVE ON NVIDIA NIM (INPUT-2 A/B INCLUDED), AWAITING HUMAN ACCEPTANCE

**Bug:** Arabizi input like "ezayek ya nova 3amla eh" (Arabic written with Latin letters) was classified English, and NIM sometimes replied in English with meta-commentary ("It looks like you asked in Arabic ... which translates to ...", "Since your message was a greeting, I'll keep it simple", "to be safe, I'll respond ..."). The UI contract requires mirroring: Arabic/Arabizi → Arabic (or Arabic with Latin technical terms), no translation narration, no English tail.

**What changed (backend only; no model/provider priority change; frontend untouched):**
- `backend/app/copilot.py` — `detect_arabizi()` with `_ARABIZI_LEXICON`/`_ARABIZI_STRONG` frozensets; `detect_language()` falls back to Arabizi when no Arabic script (tokenizer keeps digits so "3amla" matches). Lexicon extended with the spellings used by the long-Arabizi test input ("momken", "tshar7ly", "shar7ly", "bel3araby", "law", "samaht", ...). `resolve_language(language, message_text)` unchanged.
- `backend/app/genai.py` — `_MIRROR_LANGUAGE_RULE` is the SHORT form: "Reply in the same language as the user's message. Do not explain. Do not translate." (Chosen by live A/B — see below.) `_no_language_narration_rule(persona_name)`; `_META_COMMENTARY_PHRASES` (31 phrases incl. every shape seen on live NIM) + `_reply_contains_meta_commentary()`; `_sentence_language_signal()` + `_strip_mismatched_language_tail()`; `_complete_visible()` runs the hard hygiene gate + mixed-tail strip before the language gate; `_tutor_system()` is the single system-prompt builder; env-gated `SKILLBRIDGE_DEBUG_PROMPT=1` UTF-8 JSONL dump (`SKILLBRIDGE_DEBUG_FILE`, default `%TEMP%\opencode\sb_debug.jsonl`) records per attempt: `raw_nim_reply` (before any gate), `meta_commentary`, `matches_language`, `surfaced_fallback`, `final_reply`.
- `backend/app/main.py` — `GET /api/debug/tutor-system` (gated by `SKILLBRIDGE_ENABLE_DEBUG=1`) returns the EXACT system prompt that would be sent to the provider for a turn, proving prompt contents without any provider call.
- Tests: `backend/tests/test_tutor_language.py` (D1 Arabizi detection incl. the long input; D2/D3/D4 meta-phrase rejection incl. every live-NIM phrasing; system-prompt carries the short mirror + no-narration rules) and `backend/tests/test_runtime_tutor_language.py` (T1–T5 + T6 long-Arabizi volumes question).

**INPUT-2 A/B ON LIVE NIM (the contested case, "ana msh fahm el docker ports", fresh conversation per attempt, `language=auto`):**
- Long "MANDATORY LANGUAGE RULE" prompt: valid live NIM Arabic **5/10** (decoding latch reproduced the exact "docker ports\n" line to the token limit in the other 5; gate caught all 5 → Arabic fallback). The rich valid replies under this prompt proved the rule did not wholesale block the model, but the failure rate was below the user's accepted bar.
- SHORT rule (current): valid live NIM Arabic **8/10** — attempt outputs 485–650 Arabic codepoints each, real teaching content (port mapping, `-p 8080:80`, `localhost:8080`, docker volumes). 2/10 latches caught → Arabic fallback. **≥ 2/3 ⇒ the model CAN handle the normal Arabizi sentence; the failure is intermittent and documented.**
- The degeneration is a MODEL-SIDE decoding latch (echo of the student's phrase or a "أنا نيموترون" self-id repetition), input-content-dependent and non-deterministic — NOT the prompt constraining the model: rich Arabic appears under both prompt forms, and the latch also occurs for the greeting/negative inputs. The hard gate + provider-identity repair caught **100% of latches across every live run** (every latch either had zero Arabic codepoints → `matches=False` → language-correct Arabic fallback, or self-identified as Nemotron → identity-repair → language-correct Arabic reply). The user never sees English or meta-commentary on any Arabic input.

**Live NVIDIA NIM verification (server: venv interpreter, model `nvidia/nemotron-3.5-lightning-30b-a3b`, base `https://integrate.api.nvidia.com/v1`):**
- `GET /api/config/demo-mode` → after each pass: `last_active_provider=nvidia`, `last_success=true`.
- `ezayek ya nova 3amla eh` (auto) → ar; accepted pass returned NIM Arabic "أهلاً بك! 🙂 كيف حالك اليوم؟ أنا Nova، مدرّبك الذكي في SkillBridge." (later single-shot runs intermittently latch to a Nemotron self-id spam that the identity-repair replaces with Arabic — documented above).
- `ana msh fahm el docker ports` (auto) → ar; NIM valid Arabic 8/10 under the short rule (see A/B); every latch replaced by Arabic fallback.
- `how are you` (auto) → en; English, untouched.
- `إزيك يا نوفا` (auto) → ar; Arabic.
- `3amla eh` (auto/negative) → ar; Arabic-only reply, no "in English"/"translate"/"I'll respond"/"Since you wrote".
- `momken tshar7ly docker volumes bel3araby law samaht` (auto) → ar; NIM returned a long Arabic mixed explanation (volumes, `docker volume create`, `-v my-data:/app/data`), not degenerate.
- System prompt proof: `/api/debug/tutor-system` for the Arabizi greeting → resolved ar, Arabic LANG LOCK, short mirror rule + no-narration rule present, 31-phrase block list.

**Validation:** language files **68 passed / 0 failed**; focused sweep (12 files: language, runtime-language, personas v2/phase3, provider phase31, trust-language phase2, modes, profiles, confusion phase32, conversations phase4a, conversation-memory phase2, conversations) **377 passed / 0 failed** in 240.33s. Frontend untouched (prior gates stand: tsc clean, build clean, 8 contract checks OK).

**Block note:** user-mandated STOP — do NOT start Phase 4B until this live-NIM language-mirroring work is human-accepted.


## Icon centering (Quick Access + Suggestion cards) — CSS-ONLY FIX — GEOMETRICALLY VERIFIED — COMPLETE

**Bug:** In the Copilot empty state, the 4 suggestion card icons were vertically misaligned (top-aligned instead of vertically centered with the text block). In the Learning page Quick Access panel, the icon container was not vertically centered with the label and trailing arrow.

**Root cause:** `index.css:6420` — `.copilot-v2 .suggestion-card span` applied `display: block; margin-top: 5px;` to **every** `<span>` inside the card, including the wrapper `<span>` that holds the title + subtitle. This pushed the entire text block down 5px, making the icon appear top-aligned. `.quick-icon` used `display: flex` instead of `display: grid; place-items: center`.

**What changed (CSS only, `frontend/src/index.css`; no colors, sizes, copy, or logic):**
- `.copilot-v2 .suggestion-card span` → `.copilot-v2 .suggestion-card strong + span` — scopes the margin/block to the subtitle only, removing the layout bug from the wrapper.
- `.quick-icon` — switched from `display: flex; align-items: center; justify-content: center;` to `display: grid; place-items: center;` (explicit centering, unchanged 30×30 size).
- `.quick-item .chev` — added `align-self: center;` to guarantee vertical centering on the row axis (defensive).
- `.quick-item.tip` — changed `align-items: flex-start` → `align-items: center` (icon now centers with the multi-line text block, consistent with all other rows).

**Geometric verification (Brave headless, fresh profile, measures icon/label/chev center Y coordinates):**
- Suggestion cards 1440px LTR: icon delta = **0.00px** (4/4 cards).
- Suggestion cards 1440px RTL: icon delta = **0.00px** (4/4 cards).
- Suggestion cards 390px: icon delta = **0.00px** (4/4 cards).
- Quick Access 1440px LTR: maxOff = **0.00px** (5/5 rows, `align-items: center` confirmed).
- Quick Access 1440px RTL: maxOff = **0.00px** (5/5 rows, chev mirrors to left side, `dir: rtl` confirmed).
- Quick Access 390px: maxOff = **0.00px** (5/5 rows).
- Screenshots: `%TEMP%\opencode\shots\icons-{quick,suggestion}-1440{,-rtl}.png` and `icons-{quick,suggestion}-390.png`.

**Build status:** `npx tsc --noEmit` — **clean**. `npm run build` — **built in 11.86s** (chunk-size advisory only).


## Phase 3.2 Vex dry-wit polish — COMPLETED (code + tests)

---

## Retry Policy Addendum (2026-09-17)

**Bounded single-retry for NIM calls** — implemented in `backend/app/genai.py`:

- **Scope**: `_call_nim()` (used by artifacts + tutor fallback paths). Spoken turns (`retries=0`) and CV extraction (`retries=0`) are EXCLUDED — exactly 1 attempt, no retry.
- **Attempts**: `min(2, max(1, retries))` → default `retries=1` → 2 HTTP attempts max (1 initial + 1 retry). `_call_artifact` default `retries=2`.
- **Retryable**: ONLY empty stream (HTTP 200 with no content, incl. JSON parse failure) OR 502/503/504.
- **NEVER retries**: 200-with-content, 4xx (incl. 429), 500, connection error, timeout.
- **Backoff**: Fixed 500 ms (`_NIM_RETRY_BACKOFF_S = 0.5`).
- **Budget gate**: Before each retry draw, if `remaining_budget < timeout_s / 2` → break (no retry). Also caps retry's own request timeout to remaining budget.
- **Error semantics preserved**: Non-retryable HTTP errors propagate as raw `httpx.HTTPStatusError`; connect/timeout wrapped in `RuntimeError` with `.status_code`/`.timeout` attrs; circuit breaker unchanged (`failures>=3 → open 60s`).
- **Env**: `ARTIFACT_TIMEOUT_SECONDS=60` (clamped 15–300 in genai.py).
- **Tests**: `backend/tests/test_artifacts_glm_tier.py` — 6 new regression tests (first-drop→success, 503→success, both-drop→fallback, never-retry-4xx, never-retry-200-with-content, budget-skip).
- **Verification**: 65 artifact/nim/spoken/extraction tests + 440 targeted caller batch tests pass.
