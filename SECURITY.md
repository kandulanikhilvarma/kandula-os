# Security Policy

Kandula OS is a single-user personal system. It holds one person's task list and
project notes, and it is deployed by one person. There is no user base to
coordinate with, so disclosure is simple.

## Reporting a vulnerability

Email **kandulanikhilvarma@gmail.com** with `[security]` in the subject, or open
a [private security advisory](https://github.com/kandulanikhilvarma/kandula-os/security/advisories/new).

Please include what you found, how to reproduce it, and what an attacker gains.
Expect a reply within seven days.

Do not open a public issue for anything that exposes data or bypasses
authentication.

## Scope

In scope:

- Authentication or allowlist bypass on `GET /api/state`
- Shared-secret bypass on `POST /api/sync`
- Injection through `TASKS.md` or `memory/*.md` into the rendered dashboard
- Content-Security-Policy weaknesses that permit script execution
- Secret leakage through logs, error responses, or the rendered page

Out of scope:

- Anything requiring the owner's Google account or an already-leaked
  `SYNC_SECRET`
- Denial of service through request volume — this runs on a free tier for one
  user, and rate limiting is deliberately absent
- Findings in Firebase, Vercel, or Flask themselves; report those upstream

## Supported versions

The `main` branch is the only supported version.

## Design notes relevant to security

- Firestore runs in **locked mode**. No client reads it directly; only the
  server does, using a service account held in an environment variable.
- `POST /api/sync` compares its shared secret with `hmac.compare_digest`.
- `GET /api/state` verifies a Firebase ID token, then checks the email against
  `ALLOWED_EMAILS`. Both must pass.
- Every payload is validated by pydantic with `extra="forbid"`.
- The page ships a strict CSP with no `unsafe-inline`; the Firebase web config
  travels as a `data-` attribute rather than an inline script.
- Secrets live only in `.env.local` (gitignored) and the Vercel dashboard.
