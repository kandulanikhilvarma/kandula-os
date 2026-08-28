"""Firebase service layer — the ONLY file that touches firebase_admin.

Credentials come from the FIREBASE_SERVICE_ACCOUNT env var (the full
service-account JSON as a string). The app and the Firestore client are both
initialised lazily and cached at module level: on Vercel the module survives
between warm invocations, so a request after the first pays no setup cost.

History lives inside the single os_state/current document as a capped array
rather than its own collection — one document read serves the whole dashboard,
and no composite index is ever needed.
"""
import json
import os

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials, firestore

from api.logger import get_logger

log = get_logger(__name__)

_STATE_COLLECTION = "os_state"
_STATE_DOC = "current"
_HISTORY_CAP = 90

_db = None


class FirebaseNotConfigured(RuntimeError):
    pass


def _app() -> firebase_admin.App:
    try:
        return firebase_admin.get_app()
    except ValueError as no_app:
        raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if not raw:
            raise FirebaseNotConfigured(
                "FIREBASE_SERVICE_ACCOUNT env var not set") from no_app
        cred = credentials.Certificate(json.loads(raw))
        return firebase_admin.initialize_app(cred)


def _doc():
    global _db
    if _db is None:
        _db = firestore.client(app=_app())
    return _db.collection(_STATE_COLLECTION).document(_STATE_DOC)


def verify_user(id_token: str) -> str:
    """Verify a Firebase ID token; return the email. Raises on invalid."""
    decoded = fb_auth.verify_id_token(id_token, app=_app())
    return decoded.get("email", "")


def get_state() -> dict | None:
    doc = _doc().get()
    return doc.to_dict() if doc.exists else None


def merge_history(previous: dict | None, point: dict) -> list[dict]:
    """Append today's point, replacing any earlier point for the same date."""
    history = list((previous or {}).get("history") or [])
    history = [p for p in history if p.get("date") != point["date"]]
    history.append(point)
    history.sort(key=lambda p: p["date"])
    return history[-_HISTORY_CAP:]


def set_state(state: dict, history_point: dict) -> dict:
    """Write state plus the rolling history array. Returns what was written."""
    doc = _doc()
    snapshot = doc.get()
    state = dict(state)
    state["history"] = merge_history(snapshot.to_dict() if snapshot.exists else None,
                                     history_point)
    doc.set(state)
    log.info("os_state/current updated (source=%s, history=%d)",
             state.get("source"), len(state["history"]))
    return state
