status: active
next: Create the Firebase project, set env vars, deploy to Vercel

# kandula-os

Personal operating system: markdown memory + scheduled routines + a Flask/Firebase
dashboard on Vercel. Built 2026-07-17 via build-pilot; brief in `docs/BRIEF.md`.
Renamed from `personal-os` to Kandula OS on 2026-08-28 when the repo went public.

## Decisions
- Firestore holds runtime state (`os_state/current`) so scheduled briefs work
  even when the desktop is offline; the markdown files remain the source of truth.
- Auth: Firebase Google sign-in, `ALLOWED_EMAILS` allowlist (just Rudra).
- Sync: `scripts/sync_state.py` parses TASKS.md + memory/ headers, POSTs to
  `/api/sync` with `X-Sync-Secret`. It lints before it sends.
- Rejected Mem0 MCP for memory — plain markdown wins until files stop scaling.
- Metrics are computed server-side in `api/services/metrics.py` (pure functions,
  no I/O) so the browser renders numbers rather than deriving them. One place to
  test, one place to fix.
- History is a capped 90-point array inside the state document, not its own
  collection: one read serves the whole dashboard and no index is needed.

## Log
- 2026-07-17: MVP built (core files, dashboard app, routines).
- 2026-08-28: Rebranded to Kandula OS. Added metrics service, ETag revalidation,
  CSP, sync linter, preflight check, command palette, charts, light/dark theming.
  Published as a public repo with CI.
