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
