# Deploy

One Firebase project, one Vercel import. Roughly fifteen minutes the first time.
Run `python scripts/preflight.py` between steps — it tells you exactly which
variable is still missing without ever printing a secret.

## 1. Firebase project

1. [console.firebase.google.com](https://console.firebase.google.com) → **Add project**.
   Analytics is not needed.
2. **Build → Firestore Database → Create database.** Choose **production mode**
   (locked). This matters: no browser ever reads Firestore directly, only the
   Flask server does, so clients need zero read access.
3. Pick the region closest to you and create it.
4. **Build → Authentication → Get started → Google → Enable.** Set a support
   email, save.

## 2. Two config values

**Service account** (the server's credential):

1. Gear icon → **Project settings → Service accounts → Generate new private key**.
2. A JSON file downloads. Open it, and **collapse it to a single line** — this
   becomes `FIREBASE_SERVICE_ACCOUNT`.

   ```bash
   python -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1]))))" ~/Downloads/key.json
   ```

**Web config** (the browser's sign-in config, not a secret):

1. **Project settings → General → Your apps → Web app** (`</>` icon), register it.
2. Copy the `firebaseConfig` object. Convert it to JSON — keys need quotes —
   and keep it on one line. This becomes `FIREBASE_WEB_CONFIG`.

## 3. Local environment

```bash
cp .env.example .env.local
```

Fill in:

| Variable | Value |
|---|---|
| `FIREBASE_SERVICE_ACCOUNT` | the one-line service-account JSON |
| `FIREBASE_WEB_CONFIG` | the one-line web config JSON |
| `ALLOWED_EMAILS` | your Google address; comma-separated for more |
| `SYNC_SECRET` | 32+ random characters, generated below |
| `SYNC_URL` | your Vercel URL once step 4 is done |

```bash
python -c "import secrets;print(secrets.token_urlsafe(32))"   # SYNC_SECRET
python scripts/preflight.py                                   # verify
```

`.env.local` is gitignored. It must never be committed.

## 4. Vercel

1. [vercel.com/new](https://vercel.com/new) → import `kandula-os`.
2. Framework preset: **Other**. No build command, no output directory —
   `vercel.json` routes everything to `api/index.py`.
3. **Environment Variables** → add all four:
   `FIREBASE_SERVICE_ACCOUNT`, `FIREBASE_WEB_CONFIG`, `ALLOWED_EMAILS`,
   `SYNC_SECRET`. Paste each as a single line.
4. **Deploy.**

## 5. Authorize the domain

Back in Firebase: **Authentication → Settings → Authorized domains → Add domain**
→ your `*.vercel.app` hostname. Sign-in fails with an unhelpful popup error until
this is done.

## 6. First sync

Put the deployed URL into `.env.local` as `SYNC_URL`, then:

```bash
python scripts/sync_state.py
```

Expected:

```
200 {"ok": true, "tasks": 5, "projects": 1, "open": 4, "overdue": 0, "history_points": 1}
```

Open the dashboard, sign in with the allowlisted Google account, and the state
appears. The trend chart stays empty until a second sync on a different day —
that is correct, not a bug.

## Verify the security posture

```bash
curl -s https://<your-app>.vercel.app/api/health
# {"ok": true, "service": "kandula-os", "firebase_configured": true}

curl -s -o /dev/null -w "%{http_code}\n" https://<your-app>.vercel.app/api/state
# 401 — no token

curl -s -o /dev/null -w "%{http_code}\n" -X POST https://<your-app>.vercel.app/api/sync
# 403 — no shared secret
```

Any other codes mean an environment variable did not land. Check the Vercel
project's environment settings and redeploy.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "FIREBASE_WEB_CONFIG is not set on the server" on the page | The variable is missing or is not valid JSON. `preflight.py` will say which. |
| Sign-in popup opens then closes with an error | Vercel domain not added to Firebase authorized domains (step 5). |
| Dashboard shows 403 after signing in | Your email is not in `ALLOWED_EMAILS`, or it has a stray space. |
| `/api/sync` returns 403 | `SYNC_SECRET` differs between `.env.local` and Vercel. |
| `/api/sync` returns 400 | Payload failed validation. The response body names the offending field. |
| Dashboard is blank but `/api/health` is fine | Nothing synced yet. Run `python scripts/sync_state.py`. |

## Rotating the sync secret

Generate a new one, update it in the Vercel dashboard **and** `.env.local`,
redeploy. The old secret stops working immediately; there is no grace window by
design.
