GOOD_STATE = {
    "generated_at": "2026-07-17T10:00:00+00:00", "source": "test",
    "tasks": [{"id": "t1", "title": "Ship it", "priority": "P1", "done": False,
               "due": "2026-07-19", "project": "kandula-os"}],
    "projects": [{"name": "kandula-os", "status": "active", "next_action": "deploy"}],
}

AUTH = {"Authorization": "Bearer good-token"}
SECRET = {"X-Sync-Secret": "test-secret"}


def _sync(client, state=None, today="2026-07-18"):
    return client.post(f"/api/sync?today={today}", json=state or GOOD_STATE, headers=SECRET)


def test_index_renders_web_config_as_data_attribute(client):
    r = client.get("/")
    assert r.status_code == 200
    # config travels on <body>, not in an inline script, so CSP needs no exception
    assert b"data-firebase-config=" in r.data
    assert b"apiKey" in r.data


def test_security_headers_present(client):
    r = client.get("/")
    csp = r.headers["Content-Security-Policy"]
    assert "script-src 'self' https://www.gstatic.com" in csp
    assert "'unsafe-inline'" not in csp
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    assert r.get_json()["service"] == "kandula-os"


def test_unknown_api_path_is_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.get_json()["error"] == "not found"


def test_state_requires_token(client):
    assert client.get("/api/state").status_code == 401


def test_state_rejects_bad_token(client):
    assert client.get("/api/state", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_state_rejects_unlisted_email(client):
    r = client.get("/api/state", headers={"Authorization": "Bearer stranger-token"})
    assert r.status_code == 403


def test_state_empty_before_sync(client):
    r = client.get("/api/state", headers=AUTH)
    assert r.status_code == 200 and r.get_json().get("empty") is True


def test_sync_requires_secret(client):
    assert client.post("/api/sync", json=GOOD_STATE).status_code == 403


def test_sync_rejects_invalid_payload(client):
    r = client.post("/api/sync", json={"nope": 1}, headers=SECRET)
    assert r.status_code == 400


def test_sync_rejects_unknown_task_field(client):
    bad = {**GOOD_STATE, "tasks": [{**GOOD_STATE["tasks"][0], "owner": "me"}]}
    r = client.post("/api/sync", json=bad, headers=SECRET)
    assert r.status_code == 400


def test_sync_then_state_round_trip(client):
    r = _sync(client)
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True and body["open"] == 1 and body["history_points"] == 1

    r = client.get("/api/state?today=2026-07-18", headers=AUTH)
    assert r.get_json()["tasks"][0]["title"] == "Ship it"


def test_state_includes_server_computed_metrics(client):
    _sync(client)
    metrics = client.get("/api/state?today=2026-07-18", headers=AUTH).get_json()["metrics"]
    assert metrics["open"] == 1
    assert metrics["by_priority"]["P1"] == 1
    assert metrics["focus"] == ["t1"]
    assert metrics["due_this_week"] == 1


def test_state_today_param_drives_overdue(client):
    _sync(client)
    early = client.get("/api/state?today=2026-07-18", headers=AUTH).get_json()
    late = client.get("/api/state?today=2026-07-25", headers=AUTH).get_json()
    assert early["metrics"]["overdue"] == 0
    assert late["metrics"]["overdue"] == 1


def test_state_revalidates_with_etag(client):
    _sync(client)
    first = client.get("/api/state?today=2026-07-18", headers=AUTH)
    tag = first.headers["ETag"]
    assert tag

    again = client.get("/api/state?today=2026-07-18",
                       headers={**AUTH, "If-None-Match": tag})
    assert again.status_code == 304
    assert again.get_data() == b""


def test_etag_changes_when_state_changes(client):
    _sync(client)
    tag = client.get("/api/state?today=2026-07-18", headers=AUTH).headers["ETag"]

    changed = {**GOOD_STATE, "tasks": [{**GOOD_STATE["tasks"][0], "title": "Ship it twice"}]}
    _sync(client, changed)
    assert client.get("/api/state?today=2026-07-18", headers=AUTH).headers["ETag"] != tag


def test_history_accumulates_one_point_per_day(client):
    _sync(client, today="2026-07-18")
    _sync(client, today="2026-07-18")  # same day — replaces, does not append
    _sync(client, today="2026-07-19")

    history = client.get("/api/state?today=2026-07-19", headers=AUTH).get_json()["history"]
    assert [p["date"] for p in history] == ["2026-07-18", "2026-07-19"]


def test_parsers_output_validates_against_schema():
    import sync_state

    from api.models.schemas import OsState

    state = sync_state.build_state()
    validated = OsState.model_validate(state)
    assert len(validated.tasks) >= 1
    assert any(p.name == "kandula-os" for p in validated.projects)
