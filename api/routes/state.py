"""State routes — thin request/response only; logic lives in services/."""
import datetime
import hashlib
import hmac
import json
import os
import re

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from api.logger import get_logger
from api.models.schemas import OsState
from api.services import firebase_client, metrics

log = get_logger(__name__)
bp = Blueprint("state", __name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _allowed_emails() -> set[str]:
    return {e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()}


def _today(supplied: str | None) -> str:
    """Trust the browser's local date when it looks like a date; else use UTC.

    The owner is in IST, so a UTC-derived 'today' is wrong for 5.5 hours a day.
    """
    if supplied and _DATE_RE.match(supplied):
        try:
            return datetime.date.fromisoformat(supplied).isoformat()
        except ValueError:
            pass
    return datetime.datetime.now(datetime.UTC).date().isoformat()


def _etag(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()[:32]


@bp.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "service": "kandula-os",
        "firebase_configured": bool(os.environ.get("FIREBASE_SERVICE_ACCOUNT")),
    })


@bp.get("/api/state")
def get_state():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return jsonify({"error": "missing bearer token"}), 401
    try:
        email = firebase_client.verify_user(header.removeprefix("Bearer "))
    except Exception:
        log.info("rejected /api/state: invalid token")
        return jsonify({"error": "invalid token"}), 401
    if email.lower() not in _allowed_emails():
        log.info("rejected /api/state: email not allowed")
        return jsonify({"error": "forbidden"}), 403

    state = firebase_client.get_state()
    if not state:
        return jsonify({"empty": True})

    state["metrics"] = metrics.summarize(
        state.get("tasks") or [],
        state.get("projects") or [],
        _today(request.args.get("today")),
    )

    tag = _etag(state)
    offered = {t.strip().strip('"') for t in request.headers.get("If-None-Match", "").split(",")}
    if tag in offered:
        return "", 304, {"ETag": f'"{tag}"', "Cache-Control": "private, no-cache"}

    response = jsonify(state)
    response.headers["ETag"] = f'"{tag}"'
    response.headers["Cache-Control"] = "private, no-cache"
    return response


@bp.post("/api/sync")
def post_sync():
    secret = os.environ.get("SYNC_SECRET", "")
    supplied = request.headers.get("X-Sync-Secret", "")
    if not secret or not hmac.compare_digest(secret, supplied):
        log.info("rejected /api/sync: bad secret")
        return jsonify({"error": "forbidden"}), 403
    try:
        state = OsState.model_validate(request.get_json(force=True, silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": "invalid payload", "detail": e.errors()}), 400

    payload = state.model_dump()
    summary = metrics.summarize(
        payload["tasks"], payload["projects"],
        _today(request.args.get("today")),
    )
    written = firebase_client.set_state(payload, metrics.history_point(summary))
    return jsonify({
        "ok": True,
        "tasks": len(state.tasks),
        "projects": len(state.projects),
        "open": summary["open"],
        "overdue": summary["overdue"],
        "history_points": len(written["history"]),
    })
