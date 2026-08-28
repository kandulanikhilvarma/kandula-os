"""Derived task metrics.

Pure functions over already-validated task dicts: no I/O, no clock, no config.
The caller supplies `today`, so every number here is reproducible in a test.
The dashboard renders what this returns and computes nothing of its own.
"""
import datetime

_FAR_FUTURE = "9999-12-31"
_PRIORITY_RANK = {"P1": 0, "P2": 1, "P3": 2}


def _open(tasks: list[dict]) -> list[dict]:
    return [t for t in tasks if not t.get("done")]


def _due(task: dict) -> str:
    """Due date as a sortable string; undated tasks sort last."""
    return task.get("due") or _FAR_FUTURE


def is_overdue(task: dict, today: str) -> bool:
    due = task.get("due")
    return bool(due) and due < today and not task.get("done")


def focus_order(tasks: list[dict], today: str) -> list[dict]:
    """Open tasks, most-urgent first: overdue, then priority, then due date."""
    return sorted(
        _open(tasks),
        key=lambda t: (
            not is_overdue(t, today),
            _PRIORITY_RANK.get(t.get("priority", "P3"), 3),
            _due(t),
            t.get("title", ""),
        ),
    )


def summarize(tasks: list[dict], projects: list[dict], today: str) -> dict:
    """One pass over the task list; everything the dashboard header needs."""
    week_out = (
        datetime.date.fromisoformat(today) + datetime.timedelta(days=7)
    ).isoformat()

    open_tasks = _open(tasks)
    done = len(tasks) - len(open_tasks)

    by_priority = {"P1": 0, "P2": 0, "P3": 0}
    for t in open_tasks:
        key = t.get("priority")
        if key in by_priority:
            by_priority[key] += 1

    per_project: dict[str, dict] = {}
    for t in tasks:
        name = t.get("project") or "unfiled"
        row = per_project.setdefault(name, {"name": name, "open": 0, "done": 0})
        row["done" if t.get("done") else "open"] += 1

    for p in projects:
        per_project.setdefault(p["name"], {"name": p["name"], "open": 0, "done": 0})

    overdue = [t for t in open_tasks if is_overdue(t, today)]
    due_today = [t for t in open_tasks if t.get("due") == today]
    due_week = [t for t in open_tasks if today < _due(t) <= week_out]

    return {
        "today": today,
        "open": len(open_tasks),
        "done": done,
        "total": len(tasks),
        "completion_rate": round(done / len(tasks), 3) if tasks else 0.0,
        "by_priority": by_priority,
        "overdue": len(overdue),
        "overdue_ids": [t["id"] for t in overdue],
        "due_today": len(due_today),
        "due_this_week": len(due_week),
        "projects_active": sum(1 for p in projects if p.get("status") == "active"),
        "by_project": sorted(
            per_project.values(), key=lambda r: (-r["open"], r["name"])
        ),
        "focus": [t["id"] for t in focus_order(tasks, today)[:3]],
    }


def history_point(summary: dict) -> dict:
    """The slice of a summary worth keeping per day for the trend chart."""
    return {
        "date": summary["today"],
        "open": summary["open"],
        "done": summary["done"],
        "overdue": summary["overdue"],
    }
