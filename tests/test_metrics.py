"""Metrics are pure functions over task dicts, so every case is a plain call."""
from api.services import metrics

TODAY = "2026-07-18"


def task(tid, priority="P2", done=False, due=None, project=None, title=None):
    return {"id": tid, "title": title or f"task {tid}", "priority": priority,
            "done": done, "due": due, "project": project}


def test_empty_state_has_no_completion_rate():
    summary = metrics.summarize([], [], TODAY)
    assert summary["open"] == 0
    assert summary["completion_rate"] == 0.0
    assert summary["focus"] == []


def test_counts_split_open_and_done():
    tasks = [task("a"), task("b", done=True), task("c", done=True)]
    summary = metrics.summarize(tasks, [], TODAY)
    assert (summary["open"], summary["done"], summary["total"]) == (1, 2, 3)
    assert summary["completion_rate"] == 0.667


def test_only_open_tasks_count_toward_priorities():
    tasks = [task("a", "P1"), task("b", "P1", done=True), task("c", "P3")]
    by_priority = metrics.summarize(tasks, [], TODAY)["by_priority"]
    assert by_priority == {"P1": 1, "P2": 0, "P3": 1}


def test_overdue_ignores_done_and_undated_tasks():
    tasks = [
        task("late", due="2026-07-01"),
        task("late-but-done", due="2026-07-01", done=True),
        task("undated"),
        task("future", due="2026-12-01"),
    ]
    summary = metrics.summarize(tasks, [], TODAY)
    assert summary["overdue"] == 1
    assert summary["overdue_ids"] == ["late"]


def test_due_today_and_week_are_exclusive_windows():
    tasks = [
        task("today", due=TODAY),
        task("in-week", due="2026-07-24"),
        task("edge-of-week", due="2026-07-25"),
        task("past-week", due="2026-07-26"),
    ]
    summary = metrics.summarize(tasks, [], TODAY)
    assert summary["due_today"] == 1
    assert summary["due_this_week"] == 2  # in-week + edge-of-week; not today, not past


def test_focus_puts_overdue_first_then_priority_then_due_date():
    tasks = [
        task("p1-later", "P1", due="2026-09-01"),
        task("p3-overdue", "P3", due="2026-07-01"),
        task("p1-sooner", "P1", due="2026-07-20"),
        task("p2-undated", "P2"),
    ]
    assert metrics.summarize(tasks, [], TODAY)["focus"] == [
        "p3-overdue", "p1-sooner", "p1-later",
    ]


def test_focus_caps_at_three():
    tasks = [task(str(i), "P1") for i in range(10)]
    assert len(metrics.summarize(tasks, [], TODAY)["focus"]) == 3


def test_unfiled_tasks_group_under_unfiled():
    tasks = [task("a", project="alpha"), task("b")]
    names = [row["name"] for row in metrics.summarize(tasks, [], TODAY)["by_project"]]
    assert set(names) == {"alpha", "unfiled"}


def test_projects_with_no_tasks_still_appear():
    projects = [{"name": "quiet", "status": "active", "next_action": None}]
    rows = metrics.summarize([], projects, TODAY)["by_project"]
    assert rows == [{"name": "quiet", "open": 0, "done": 0}]


def test_by_project_sorts_busiest_first():
    tasks = [task("a", project="big"), task("b", project="big"), task("c", project="small")]
    rows = metrics.summarize(tasks, [], TODAY)["by_project"]
    assert [r["name"] for r in rows] == ["big", "small"]


def test_active_projects_counted_by_status():
    projects = [
        {"name": "a", "status": "active", "next_action": None},
        {"name": "b", "status": "paused", "next_action": None},
        {"name": "c", "status": "active", "next_action": None},
    ]
    assert metrics.summarize([], projects, TODAY)["projects_active"] == 2


def test_history_point_keeps_only_the_trend_fields():
    summary = metrics.summarize([task("a", due="2026-07-01")], [], TODAY)
    assert metrics.history_point(summary) == {
        "date": TODAY, "open": 1, "done": 0, "overdue": 1,
    }
