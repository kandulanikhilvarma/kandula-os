"""The sync linter is the guard against TASKS.md format drift, so it gets tests."""
import pytest
import sync_state

from api.services import firebase_client


def write_tasks(tmp_path, monkeypatch, body):
    (tmp_path / "TASKS.md").write_text(body, encoding="utf-8")
    (tmp_path / "memory").mkdir(exist_ok=True)
    monkeypatch.setattr(sync_state, "ROOT", str(tmp_path))


def test_parses_a_well_formed_file(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch,
                "- [ ] P1 Deploy it | due:2026-07-19 | project:kandula-os\n"
                "- [x] P2 Write the brief\n")
    tasks, problems = sync_state.parse_tasks()
    assert problems == []
    assert tasks[0]["due"] == "2026-07-19"
    assert tasks[0]["project"] == "kandula-os"
    assert tasks[1]["done"] is True


def test_ignores_example_lines_inside_html_comments(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch,
                "<!-- FORMAT:\n"
                "      - [ ] P1 Task title | due:YYYY-MM-DD | project:name\n"
                "-->\n"
                "- [ ] P1 A real task\n")
    tasks, problems = sync_state.parse_tasks()
    assert problems == []
    assert len(tasks) == 1


def test_flags_a_bad_priority(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch, "- [ ] P9 Nope\n")
    _, problems = sync_state.parse_tasks()
    assert len(problems) == 1 and problems[0][0] == 1


def test_flags_a_bad_due_date(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch, "- [ ] P1 Task | due:19-07-2026\n")
    _, problems = sync_state.parse_tasks()
    assert "YYYY-MM-DD" in problems[0][2]


def test_flags_an_unknown_field(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch, "- [ ] P1 Task | owner:me\n")
    _, problems = sync_state.parse_tasks()
    assert "unknown field" in problems[0][2]


def test_flags_duplicate_titles_in_the_same_project(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch,
                "- [ ] P1 Same | project:a\n- [ ] P2 Same | project:a\n")
    _, problems = sync_state.parse_tasks()
    assert any("duplicate" in p[2] for p in problems)


def test_same_title_in_different_projects_is_fine(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch,
                "- [ ] P1 Same | project:a\n- [ ] P2 Same | project:b\n")
    _, problems = sync_state.parse_tasks()
    assert problems == []


def test_project_needs_a_status_header(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch, "")
    (tmp_path / "memory" / "thing.md").write_text("# no header\n", encoding="utf-8")
    projects, problems = sync_state.parse_projects()
    assert projects == []
    assert "status:" in problems[0][2]


def test_project_rejects_an_unknown_status(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch, "")
    (tmp_path / "memory" / "thing.md").write_text("status: sideways\n", encoding="utf-8")
    _, problems = sync_state.parse_projects()
    assert "status must be one of" in problems[0][2]


def test_underscore_files_are_not_projects(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch, "")
    (tmp_path / "memory" / "_template.md").write_text("status: active\n", encoding="utf-8")
    projects, problems = sync_state.parse_projects()
    assert projects == [] and problems == []


def test_build_state_raises_on_drift(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch, "- [ ] P1 Task | owner:me\n")
    with pytest.raises(sync_state.DriftError):
        sync_state.build_state()


def test_check_mode_reports_drift_via_exit_code(tmp_path, monkeypatch, capsys):
    write_tasks(tmp_path, monkeypatch, "- [ ] P9 Bad\n")
    assert sync_state.main(["--check"]) == 1
    assert "drift" in capsys.readouterr().err


def test_check_mode_passes_on_clean_files(tmp_path, monkeypatch, capsys):
    write_tasks(tmp_path, monkeypatch, "- [ ] P1 Fine\n")
    assert sync_state.main(["--check"]) == 0
    assert "format OK" in capsys.readouterr().out


def test_dry_run_sends_nothing_and_prints_payload(tmp_path, monkeypatch, capsys):
    write_tasks(tmp_path, monkeypatch, "- [ ] P1 Fine\n")

    def explode(*_args, **_kwargs):
        raise AssertionError("dry run must not hit the network")

    monkeypatch.setattr(sync_state.urllib.request, "urlopen", explode)
    assert sync_state.main(["--dry-run"]) == 0
    assert '"source": "sync_state.py"' in capsys.readouterr().out


def test_missing_env_is_a_distinct_exit_code(tmp_path, monkeypatch):
    write_tasks(tmp_path, monkeypatch, "- [ ] P1 Fine\n")
    monkeypatch.delenv("SYNC_URL", raising=False)
    monkeypatch.delenv("SYNC_SECRET", raising=False)
    monkeypatch.setattr(sync_state, "load_env_local", lambda: None)
    assert sync_state.main([]) == 2


def test_history_replaces_the_point_for_the_same_date():
    previous = {"history": [{"date": "2026-07-18", "open": 5}]}
    merged = firebase_client.merge_history(previous, {"date": "2026-07-18", "open": 2})
    assert merged == [{"date": "2026-07-18", "open": 2}]


def test_history_stays_sorted_and_capped():
    previous = {"history": [{"date": f"2026-01-{d:02d}", "open": d} for d in range(1, 29)]}
    merged = firebase_client.merge_history(previous, {"date": "2025-12-31", "open": 0})
    assert merged[0]["date"] == "2025-12-31"
    assert len(merged) <= firebase_client._HISTORY_CAP
