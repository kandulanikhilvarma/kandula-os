"""Flask entrypoint — Vercel's Python runtime serves `app` from this file."""
import json
import os

from flask import Flask, jsonify, render_template, request

VERSION = "1.0.0"

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:  # local dev only; on Vercel, env vars come from the dashboard
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env.local"))
except ImportError:
    pass

app = Flask(__name__,
            template_folder=os.path.join(_ROOT, "templates"),
            static_folder=os.path.join(_ROOT, "static"))
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000  # assets are cache-busted by ?v=

from api.routes.state import bp as state_bp  # noqa: E402

app.register_blueprint(state_bp)

# The page loads Firebase Auth from gstatic and talks to Google's identity
# endpoints; nothing else is reachable. There is no inline script to allow —
# the web config travels as a data attribute on <body>.
_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://www.gstatic.com",
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self' https://identitytoolkit.googleapis.com "
    "https://securetoken.googleapis.com https://www.googleapis.com",
    "frame-src https://accounts.google.com https://*.firebaseapp.com",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
    "object-src 'none'",
])


@app.after_request
def security_headers(response):
    response.headers.setdefault("Content-Security-Policy", _CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=(), interest-cohort=()")
    return response


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not found"}), 404
    return render_template("index.html", **_page_context()), 200


@app.get("/")
def index():
    return render_template("index.html", **_page_context())


def _page_context() -> dict:
    try:
        parsed = json.loads(os.environ.get("FIREBASE_WEB_CONFIG", "{}"))
    except json.JSONDecodeError:
        parsed = {}
    return {"firebase_web_config": json.dumps(parsed), "version": VERSION}
