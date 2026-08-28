# BRIEF — Personal OS (core + dashboard)

**Date:** 2026-07-17 · **Owner:** Rudra · **Repo:** `kandula-os/` · **Status:** built; shipped as a public repo 2026-08-28

> Historical document. It records what was agreed before the build and is kept
> unedited apart from this note and the repo rename. What actually shipped is in
> [ARCHITECTURE.md](ARCHITECTURE.md); the delta is logged in `memory/kandula-os.md`.

## Problem
Rudra's context (projects, tasks, people, preferences) is scattered across Gmail, Calendar, Notion, and his head. No single system feeds it to his AI or shows him state at a glance. Mornings start with manual triage.

## User
Rudra, solo. No multi-user, ever (non-goal).

## MVP

**A. OS core — plain files in `personal-os/` (zero code)**
1. `profile.md` — working memory: identity, active projects, people, preferences.
2. `memory/` — one markdown file per active project.
3. `TASKS.md` — single source of truth for tasks, strict format, AI-groomed.
4. `ROUTINES.md` — what runs when, so any future session knows the system.

**B. Routines — Cowork scheduled tasks (zero code)**
5. Morning brief, daily ~07:00 IST: calendar + urgent Gmail + top-3 from task state.
6. Weekly review, Sunday: AI proposes memory/task updates, Rudra approves.

**C. Dashboard — Flask + Firebase on Vercel (stack contract)**
7. One page: today's top tasks, projects with status/next-action, last-sync timestamp.
8. `POST /api/sync` — routines push parsed TASKS.md + project state to Firestore (secret header, Pydantic-validated).
9. `GET /api/state` — JSON state for the page (auth required).
10. Sign-in: Firebase Auth (Google), allowlist = Rudra's email only.

## Non-goals (MVP)
Habit/finance/health modules · Notion task sync · autonomous email sending · mobile app · charts beyond the basics · multi-user/auth roles.

## Data model (Firestore)
```
os_state/current   { generated_at, source, tasks: [{id, title, priority, due?, project?}],
                     projects: [{name, status, next_action}], brief_note? }
```
One doc. No collections-per-entity until something needs history (YAGNI).

## Routes
```
GET  /            dashboard page (Jinja + vanilla JS)
GET  /api/state   JSON state          [Firebase Auth token, email allowlist]
POST /api/sync    upsert os_state     [X-Sync-Secret header, Pydantic schema]
```

## Success criteria (verifiable)
1. Fresh Cowork session, ask "what should I focus on today?" → answer cites real projects/tasks from the memory files.
2. Morning brief delivered daily by 07:15 IST containing today's calendar + top-3 tasks.
3. Edit TASKS.md → next sync → change visible on the deployed dashboard.
4. Dashboard rejects any Google account other than Rudra's; /api/sync rejects requests without the secret.
5. Deployed on Vercel free tier; every route answers well under the 10s timeout.

## Risks & probes
1. **Desktop offline during scheduled runs** — scheduled tasks run headless; TASKS.md on the desktop may be unreachable. Mitigation: Firestore (`os_state/current`) is the runtime source for briefs; files sync to it whenever the desktop is connected. Resolve exact flow in DESIGN.
2. **firebase-admin on Vercel serverless** — cold starts + credentials via env var. Probe: 20-line spike route before full build.
3. **TASKS.md format drift** — strict format documented in the file header; `/api/sync` validates with Pydantic and rejects garbage.

## Stack-fit check
No background workers (Cowork scheduled tasks are the external trigger) · state in Firestore, never in memory · secrets in env/Vercel dashboard · all routes trivially under 10s · vanilla HTML/CSS/JS, no frameworks · official SDKs (firebase-admin).
