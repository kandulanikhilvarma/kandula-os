# ROUTINES — what runs when

| Routine | Schedule | What it does |
|---|---|---|
| Morning brief | daily ~07:00 IST | Scheduled task: today's calendar (GCal) + urgent unread (Gmail) + top-3 open P1/P2 tasks (from TASKS.md if the desktop is connected, else the last synced state) → short brief |
| Weekly review | Sunday 18:00 IST | Scheduled task: propose `profile.md` / `memory/` updates, list stalled tasks, draft next week's top-3. Rudra approves every edit. |
| Sync | after any TASKS.md / memory edit session | `python scripts/sync_state.py` lints both sources, then pushes state to the dashboard |

Rules:
- Routines DRAFT, never send. Autonomy is earned per-workflow after ~10 clean runs.
- If a routine's output annoys you, edit its prompt — that IS building the OS.
- Scheduled tasks are managed in Cowork (list/update/delete from any session).

## Sync commands

```bash
python scripts/sync_state.py --check     # validate formatting, change nothing
python scripts/sync_state.py --dry-run   # print the exact payload, send nothing
python scripts/sync_state.py             # lint, then push to the dashboard
python scripts/preflight.py              # verify env vars before a deploy
```

`--check` exits non-zero and names the offending line, so it works as a
pre-commit gate or a step in any routine that edits TASKS.md.
