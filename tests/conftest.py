"""Test fixtures: stub firebase_admin + in-memory Firestore. No network, ever."""
import sys
import types

_store = {}


def _make_stub():
    fa = types.ModuleType("firebase_admin")
    fa.App = object

    class _Doc:
        def __init__(self, key):
            self.key = key

        def get(self):
            snapshot = types.SimpleNamespace()
            snapshot.exists = self.key in _store
            snapshot.to_dict = lambda: _store.get(self.key)
            return snapshot

        def set(self, data):
            _store[self.key] = data

    class _Coll:
        def __init__(self, name):
            self.name = name

        def document(self, doc):
            return _Doc(f"{self.name}/{doc}")

    class _Client:
        def collection(self, name):
            return _Coll(name)

    def get_app():
        if not getattr(fa, "_inited", False):
            raise ValueError("no app")
        return "APP"

    fa.get_app = get_app
    fa.initialize_app = lambda cred=None: (setattr(fa, "_inited", True), "APP")[1]

    auth_mod = types.ModuleType("firebase_admin.auth")

    def verify_id_token(token, app=None):
        if token == "good-token":
            return {"email": "owner@example.com"}
        if token == "stranger-token":
            return {"email": "stranger@example.com"}
        raise ValueError("bad token")

    auth_mod.verify_id_token = verify_id_token
    cred_mod = types.ModuleType("firebase_admin.credentials")
    cred_mod.Certificate = lambda d: d
    fs_mod = types.ModuleType("firebase_admin.firestore")
    fs_mod.client = lambda app=None: _Client()
    fa.auth, fa.credentials, fa.firestore = auth_mod, cred_mod, fs_mod
    sys.modules.update({
        "firebase_admin": fa,
        "firebase_admin.auth": auth_mod,
        "firebase_admin.credentials": cred_mod,
        "firebase_admin.firestore": fs_mod,
    })


_make_stub()

import os  # noqa: E402

os.environ["FIREBASE_SERVICE_ACCOUNT"] = '{"type": "service_account"}'
os.environ["FIREBASE_WEB_CONFIG"] = '{"apiKey": "x", "authDomain": "y", "projectId": "z"}'
os.environ["ALLOWED_EMAILS"] = "owner@example.com"
os.environ["SYNC_SECRET"] = "test-secret"

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import pytest  # noqa: E402


@pytest.fixture()
def client():
    from api.index import app
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_store():
    _store.clear()
    yield
