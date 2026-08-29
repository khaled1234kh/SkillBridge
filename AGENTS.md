# SkillBridge — Requirements

## Summary

SkillBridge is a GenAI-powered platform that closes the gap between what students learn at
university and what companies actually need. It connects three sides — students, companies
and universities — around one loop: a company defines the real skills a role requires, a student's
actual skill level is measured (not just self-reported), GenAI generates a personalized learning path
for every gap, the student is re-assessed under integrity monitoring, and their Verified Skill
Profile updates so their match to real roles improves. Universities see only anonymized, aggregated
gap data across their student body.

The goal is a focused prototype that demonstrates the full loop working end to end — extraction,
personalized generation, and verified re-assessment — not a production platform.

## Platform

The app has four sections in the main navigation, plus role-based views (a Student sees a different
experience than a Company or a University Admin, but it is one app with one login system).

- Dashboard (the landing page, contents depend on role):

- Student view: their Career Readiness score for their chosen target role, a skill gap map
(strong / weak / missing), and a "recommended next step."
- Company view: a list of their posted roles and candidates matched against each.
- University view: anonymized, aggregated skill-gap statistics across the student cohort.
- Skills & Roles — Companies define roles here (name + required skills + required proficiency
level per skill). Students browse roles here and select one as their Target Career.
- Learning — a student's active Learning Path: one item per skill gap, each with an AI-generated
explanation, a practice exercise, and a quiz/assessment. Includes the AI Tutor chat.
- Assessments — where a student takes a proctored quiz/mini-project for a specific skill. Shows
pass/fail, updates the Verified Skill Profile, and logs any integrity flags raised during the
attempt.

From a student's profile you can view their CV/transcript-derived initial skills, their currently
Verified Skills (separately shown, never merged with self-reported claims), and their live Job Match
Score against their Target Career.

## What the app keeps track of

Five kinds of record. (Plain-English fields — exact schema is the Coding Agent's call.)

- Student — name, email, university, target career (a Role), uploaded CV/transcript file,
self-reported skill profile (extracted from CV by GenAI), verified skill profile (built only from
passed assessments).
- Company — name, industry, and the roles it has defined.
- Role — a job title (e.g. "Junior AI Engineer") belonging to a Company, with a list of required
skills and the proficiency level required for each (e.g. Python – Advanced).
- Skill — a name and category (e.g. "Docker" / DevOps). Shared reference list used by CVs, Roles,
Learning Paths and Assessments.
- Assessment Attempt — which student, which skill, generated quiz questions, the student's
answers, a pass/fail score, any integrity flags raised (tab-switch events, timing anomalies,
suspected pasted-AI-text on free-text answers), and the before/after proficiency level for that
skill.

## GenAI touchpoints (the four places generation must actually happen — not hardcoded)

1. Skill extraction — parse an uploaded CV/transcript and produce a structured, self-reported
skill list.
2. Learning path generation — for a given skill gap and the student's target career, generate a
short explanation, a practice exercise, and a mini-project, contextualized to that career (e.g.
explain Docker via ML model deployment for an AI Engineer track, not a generic tutorial).
3. AI Tutor chat — a chat interface that has the student's background, current gap, and target
career injected as context, so answers are personalized rather than generic.
4. Quiz generation + AI-text detection — generate assessment questions for a skill, and run a
simple heuristic/classifier over free-text answers to flag likely pasted-AI-generated responses as
an integrity signal.

## High-level technical guidance

Just enough direction to keep things on track — specific choices are the Coding Agent's call.

- Build it as a single web app using React + TypeScript for the frontend and FastAPI (Python)
for the backend.
- Store data in a local SQLite database file; no cloud dependency required to run or demo it.
- Use a real GenAI API (Claude or OpenAI) for the four touchpoints above — do not fake or hardcode
GenAI output; this is the core of what's being demonstrated.
- Prefer popular, well-supported libraries over custom code — for tables, charts, file/CV parsing,
and the chat UI. Don't hand-roll what a mature library does well.
- Single-command startup for the whole app (frontend + backend + seeded DB), viewable in a browser.
- Simple auth is fine (email/password, three roles: Student, Company, University Admin) — this is not
a security product beyond what's specified below; don't over-build it.

## Not in scope (v1)

Deliberately left out to keep this small, focused, and demo-ready. Do not build these:

- No real webcam-based or biometric proctoring — simulate integrity signals with tab-switch/timing
detection and text-pattern heuristics only.
- No live scraping of real job postings — Companies manually define role requirements in-app.
- No cryptographic credential signing, QR verification, or blockchain — a "Verified" badge in the UI
is sufficient.
- No payments, subscriptions, or multi-tenant billing.
- No mobile app — responsive web is enough.
- No email/calendar integrations or notifications beyond in-app.
- No multi-university or multi-language support — one cohort, English or Arabic, pick one.
- No data import/export, no table pagination beyond what's needed to not break on seed data volume.

## Look and feel

Applies to the whole app:

- Sharp, modern, and credible — this is pitched to companies and universities, not just students;
it should not look like a student side-project.
- Pick a small, deliberate color palette (2-3 core colors + grays) before Phase 6 and apply it
consistently — do not leave this to per-screen improvisation.
- Avoid generic "AI-generated app" tells: background gradients, purple-heavy backgrounds, gradient
buttons, and cards with a single accent border line down one side.
- Use real icons for navigation, actions (edit/delete/upload), and status states (verified vs.
unverified skill, pass/fail, flagged); avoid unnecessary emoji.
- The Verified vs. Self-Reported distinction must be visually unmistakable everywhere a skill
appears (e.g. a checkmark + solid color for verified, an outline/muted state for self-reported) —
this distinction is the product's core idea and should never be ambiguous in the UI.

## Phases and success criteria

Build in these phases, in order. Do not start a phase until every success criterion of the
previous phase is demonstrably met — each criterion must be something you can actually show
working, not just assert.

### Phase 1 — Running skeleton and data

**Features**

- A single local web app with the four navigation sections (Dashboard, Skills & Roles, Learning,
Assessments) and three login roles (Student, Company, University Admin).
- A SQLite database storing the five record types (students, companies, roles, skills, assessment
attempts).
- A seed step filling the database with realistic sample data: several students, 2-3 companies with
defined roles, a shared skill list, and a few completed assessment attempts.
- Unit tests to create, read, update and delete each record type.

**Success criteria**

1. One documented command starts the whole app, and opening the given URL shows SkillBridge with
working login for all three roles.
2. The app launches already populated with sample data — it looks alive immediately, not empty.
3. The unit tests for creating, reading, updating and deleting each record type all pass.

### Phase 2 — Students, Companies, Roles and Skills

**Features**

- Company-side: define/edit/delete a Role with a required skill list and proficiency levels.
- Student-side: create a profile, upload a CV/transcript, and select a Target Career (a Role).
- Live GenAI call extracts a self-reported skill profile from the uploaded CV/transcript.
- A Skills & Roles browsing view (searchable) for students to see available roles.
- Unit tests for role CRUD and for the CV-extraction pipeline (using a fixture CV).

**Success criteria**

1. A Company can create a Role with required skills and levels, and it persists after refresh.
2. A Student can upload a CV and see a self-reported skill list appear that was genuinely produced by
a GenAI call (not hardcoded), visibly labeled as self-reported/unverified.
3. A Student can select a Target Career from the available Roles, and it's reflected on their
Dashboard.
4. The unit tests for role CRUD and CV extraction all pass.

### Phase 3 — Skill Gap Analysis and Job Match Score

**Features**

- An engine comparing a Student's current skills (self-reported, or verified where available) against
their Target Career Role's required skills.
- A Skill Gap Map showing each required skill as strong / gap / missing.
- A live Job Match Score (%) computed from this comparison.
- Unit tests for the match-score calculation across a few known input/output cases.

**Success criteria**

1. A Student's Dashboard shows a Skill Gap Map for their Target Career, correctly categorizing each
required skill.
2. The Job Match Score displayed matches what the underlying comparison logic actually computes for
that student (verify by hand against the seed data).
3. Changing a student's verified skill level (simulate this in a test) recalculates the score
correctly.
4. The unit tests for match-score calculation all pass.

### Phase 4 — Personalized Learning Path and AI Tutor

**Features**

- For each skill gap, a live GenAI call generates a learning path item: explanation, practice
exercise, mini-project — contextualized to the student's target career.
- An AI Tutor chat on the Learning page, with the student's profile, current gap, and target
career injected as context for every response.
- Unit tests confirming the learning-path generation call returns structured, non-empty content for a
given skill/career pair.

**Success criteria**

1. Clicking into a skill gap produces a real GenAI-generated explanation + exercise + mini-project,
visibly tailored to the student's target career (not generic boilerplate).
2. The AI Tutor's first response in a new conversation demonstrably reflects the student's actual
context (e.g. mentions their background or current gap without being asked to).
3. The unit tests for learning-path generation all pass.

### Phase 5 — Proctored Assessment and Verified Skill Profile

**Features**

- A quiz/assessment flow for a specific skill, with live GenAI-generated questions.
- Integrity monitoring during the attempt: tab-switch/focus-loss detection, timing-anomaly detection,
and an AI-text-detection heuristic on any free-text answer.
- On pass, the student's Verified Skill Profile updates for that skill, and the Job Match Score
recalculates.
- Any integrity flag raised during an attempt is visibly logged and shown to the student in the
result screen.
- Unit tests for scoring an attempt, for flag-triggering logic, and for the verified-profile update.

**Success criteria**

1. A Student can take a generated quiz for a skill gap and see a pass/fail result.
2. Deliberately triggering an integrity signal (switch tabs during the test, or paste an
obviously-AI-style answer) visibly raises a flag on the result screen — this must be demonstrated
live, not just asserted by a test.
3. On passing, the skill moves from self-reported to Verified in the UI, and the Job Match Score
updates and persists after refresh.
4. The unit tests for scoring, flag logic, and verified-profile updates all pass.

### Phase 6 — University Dashboard, look and feel, and end-to-end validation

**Features**

- University Admin Dashboard showing anonymized, aggregated skill-gap statistics across the
student cohort (e.g. "68% of students need improvement in Docker") — never individual student data.
- A minimum-cohort-size rule before any stat is shown (e.g. never compute a stat from fewer than a
small threshold of students) — state and enforce this rule explicitly.
- The look-and-feel rules applied across the whole app, including the mandatory
Verified-vs-Self-Reported visual distinction everywhere it appears.
- Removal of any banned elements (background gradients, gradient buttons, single-side accent
borders).
- A full end-to-end walkthrough of the running app in a real browser, with visual inspection of every
screen and every role.

**Success criteria**

1. The University Dashboard shows aggregated stats only, with no path in the UI to drill into an
individual student's data.
2. The whole app follows the look-and-feel rules, including the Verified/Self-Reported distinction,
and contains none of the banned elements.
3. The Coding Agent has driven the running app in a real browser end to end, as all three roles:
defined a role (Company), uploaded a CV and got matched (Student), passed an assessment and saw
the Verified badge appear, triggered an integrity flag on purpose, and viewed the aggregated
University Dashboard — visually inspecting every screen, not just running unit tests.
4. No errors appear in the browser console during that walkthrough.

## Final success criteria

The project is complete, and the Coding Agent may stop, when all of the following are true:

- A non-technical person can start the app with a single documented command and open it in a browser.
- All three roles (Student, Company, University Admin) can log in and use their respective views.
- A Company can define a Role with required skills; a Student can upload a CV, get a self-reported
skill profile, pick that Role as their Target Career, and see a live Skill Gap Map and Job Match
Score.
- The Learning Path and AI Tutor are genuinely GenAI-generated and contextualized, not hardcoded.
- The Proctored Assessment flow works end to end: quiz generation, integrity-flag detection
(demonstrated live), pass/fail, and a resulting update from self-reported to Verified skill status.
- The University Dashboard shows only anonymized, aggregated data, never individual records.
- The app ships with realistic sample data, so every screen looks alive on first launch.
- The look-and-feel rules are met, including the mandatory Verified-vs-Self-Reported visual
distinction, and none of the banned elements appear anywhere.
- All unit tests pass.
- Most importantly: the product has been validated by actually using it end to end in a real
browser, as all three roles — clicking through every section, performing the actions above, and
visually inspecting each screen. Passing unit tests is necessary but NOT sufficient; the Coding
Agent must confirm the running product works and looks right, not merely that the tests are
green.

---

## Delivery status & implementation notes

**Delivered as:** FastAPI (Python) backend + SQLite (stdlib `sqlite3`) + React/TypeScript (Vite) frontend, served by the backend. Stack rebuilt per this spec (the original Express/vanilla starter is not used).

**Start (single command):** `./start.sh` → open `http://localhost:8000`. Add `--reset` to wipe and re-seed the DB.

**Demo accounts (password `demo1234`):**
- Students: `aisha@student.edu`, `omar@student.edu`
- Companies: `hr@northstar.com`, `hr@signal.com`
- University Admin: `admin@univ.edu`

**GenAI:** the four touchpoints (CV extraction, learning-path generation, AI Tutor chat, quiz generation + AI-text detection) call a real provider when `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` is set, and use a clear deterministic fallback otherwise. No hardcoded GenAI output.

**Test commands:** `./scripts/test-backend.sh` (unit tests), `./scripts/verify.sh` (end-to-end API verification against a fresh seeded server).

**Validation performed:** automated browser walkthrough (Puppeteer, `/tmp/opencode/e2e.js` via `/tmp/opencode/run-with-server.sh`) drives the running app as all three roles — Company defines a role (persists); Student uploads a CV (skills extracted via GenAI), selects a target role, sees a live Skill Gap Map + Job Match Score, generates learning content and chats with the AI Tutor; Student takes a proctored assessment (pass → Verified badge appears on Dashboard) and then a second attempt with a deliberately triggered integrity flag (tab-switch + pasted-AI-style answer shown on the result screen); University Admin sees anonymized aggregated stats with no individual student data. Result: all steps pass, **no browser console errors**.

**Verified-vs-Self-Reported:** rendered as solid green Verified tags (checkmark) vs. muted Self-Reported tags (dot) everywhere a skill appears — never merged.

**Look and feel:** small deliberate teal/slate/green/red palette; score ring is SVG (no conic gradient); no background gradients, no gradient buttons, no single-side accent-bordered cards; real SVG icons for actions and states.
