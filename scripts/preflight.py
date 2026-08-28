"""Check that the environment is deploy-ready before you touch the Vercel UI.

    python scripts/preflight.py

Reads .env.local (or the ambient environment) and reports what is missing or
malformed. Exits non-zero if anything would break a deploy. Never prints a
secret value — only whether it is present and the right shape.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sync_state import load_env_local  # noqa: E402

REQUIRED_JSON = {
    "FIREBASE_SERVICE_ACCOUNT": ("type", "project_id", "private_key", "client_email"),
    "FIREBASE_WEB_CONFIG": ("apiKey", "authDomain", "projectId"),
}


def check_json_var(name, required_keys):
    raw = os.environ.get(name)
    if not raw:
        return "missing — see docs/DEPLOY.md"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as err:
        return f"not valid JSON ({err.msg}) — paste it as a single line"
    if not isinstance(parsed, dict):
        return "must be a JSON object"
    absent = [k for k in required_keys if not parsed.get(k)]
    if absent:
        return f"missing key(s): {', '.join(absent)}"
    return None


def check_emails():
    raw = os.environ.get("ALLOWED_EMAILS", "")
    emails = [e.strip() for e in raw.split(",") if e.strip()]
    if not emails:
        return "empty — nobody would be able to sign in"
    if any("@" not in e for e in emails):
        return "contains an entry without '@'"
    return None


def check_secret():
    secret = os.environ.get("SYNC_SECRET", "")
    if not secret:
        return "missing — /api/sync would reject every request"
    if len(secret) < 24:
        return f"only {len(secret)} chars; use at least 24 random characters"
    return None


def main():
    load_env_local()

    results = []
    for name, keys in REQUIRED_JSON.items():
        results.append((name, check_json_var(name, keys)))
    results.append(("ALLOWED_EMAILS", check_emails()))
    results.append(("SYNC_SECRET", check_secret()))

    url = os.environ.get("SYNC_URL")
    results.append(("SYNC_URL", None if url else "missing — sync_state.py has nowhere to POST"))

    failures = [(name, problem) for name, problem in results if problem]
    width = max(len(name) for name, _ in results)
    for name, problem in results:
        mark = "FAIL" if problem else " ok "
        print(f"[{mark}] {name.ljust(width)}  {problem or 'present and well-formed'}")

    if failures:
        print(f"\n{len(failures)} problem(s). Fix these before deploying.", file=sys.stderr)
        return 1
    print("\nAll checks passed. Safe to deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
