status: paused
next: Resume once the dashboard is live and the first sync has run

# routines

Scheduled tasks that read the OS core and draft output. Definitions and rules
live in `ROUTINES.md`; this file tracks the work of building them.

## Decisions
- Routines draft, never send. Autonomy is earned per-workflow after roughly ten
  clean runs.
- Firestore (`os_state/current`) is the runtime source for briefs, so a
  scheduled run still works when the desktop is offline.

## Log
- 2026-08-28: Paused until the dashboard is deployed — a brief that cannot read
  synced state is not worth scheduling yet.
