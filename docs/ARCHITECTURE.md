# Architecture

Kandula OS is three parts that barely know about each other: **markdown files**
you edit by hand, a **sync script** that reads them, and a **read-only dashboard**
that renders whatever was last synced.

The files are the source of truth. Firestore is a cache with a nice view on top.
Delete the whole deployment and you still have your OS.

## System context

```mermaid
flowchart LR
  subgraph desktop["Desktop — source of truth"]
    TASKS["TASKS.md"]
    MEM["memory/*.md"]
    PROFILE["profile.md"]
  end

  subgraph script["scripts/sync_state.py — stdlib only"]
    LINT["lint: strict format"]
    BUILD["build payload"]
  end

  subgraph vercel["Vercel — Flask serverless"]
    SYNC["POST /api/sync"]
    STATE["GET /api/state"]
    METRICS["metrics.summarize"]
    PAGE["GET / — dashboard page"]
  end

  FS[("Firestore<br/>os_state/current")]
  BROWSER["Browser — vanilla JS"]
  ROUTINES["Scheduled routines<br/>morning brief, weekly review"]

  TASKS --> LINT
  MEM --> LINT
  LINT --> BUILD
  BUILD -->|"X-Sync-Secret"| SYNC
  SYNC --> METRICS
  METRICS --> FS
  FS --> STATE
  STATE -->|"Firebase ID token"| BROWSER
  PAGE --> BROWSER
  FS --> ROUTINES
  PROFILE -.->|"read by routines"| ROUTINES
```

Two things carry state into the cloud, and each has its own credential: the sync
script holds a shared secret, the browser holds a Google identity. Neither can do
the other's job.

## Writing state: the sync path

`sync_state.py` refuses to send anything it cannot parse. Drift is caught on the
desktop, with a line number, before it ever reaches the network.

```mermaid
sequenceDiagram
  autonumber
  actor You
  participant CLI as sync_state.py
  participant API as POST /api/sync
  participant M as metrics.py
  participant FS as Firestore

  You->>CLI: python scripts/sync_state.py
  CLI->>CLI: parse TASKS.md plus memory/*.md
  alt format drift
    CLI-->>You: line number, reason, exit 1
  else clean
    CLI->>API: JSON payload with X-Sync-Secret
    API->>API: hmac.compare_digest on the secret
    API->>API: pydantic validate, extra fields forbidden
    API->>M: summarize(tasks, projects, today)
    M-->>API: counts, overdue, focus, per-project
    API->>FS: set state plus capped history array
    FS-->>API: ok
    API-->>CLI: counts written
    CLI-->>You: 200 plus summary line
  end
```

Three gates stand between a typo and the database: the linter, the shared secret,
and the schema. Each rejects a different class of mistake.

## Reading state: the dashboard path

```mermaid
sequenceDiagram
  autonumber
  actor You
  participant B as Browser
  participant G as Google Sign-In
  participant API as GET /api/state
  participant FB as Firebase Admin
  participant FS as Firestore

  You->>B: open the dashboard
  B->>B: render cached state from localStorage
  B->>G: signInWithPopup
  G-->>B: ID token
  B->>API: Bearer token plus If-None-Match plus local date
  API->>FB: verify_id_token
  FB-->>API: email
  API->>API: email in ALLOWED_EMAILS
  alt not on the allowlist
    API-->>B: 403
  else allowed
    API->>FS: read os_state/current
    API->>API: compute metrics for the supplied date
    alt ETag matches
      API-->>B: 304, no body
    else changed
      API-->>B: 200 plus state, metrics, history
    end
  end
```

The page paints from `localStorage` before the network answers, so a reload feels
instant and an offline reload still shows the last known state. `If-None-Match`
means an unchanged dashboard costs one empty 304 rather than a full payload.

## Module map

```mermaid
flowchart TD
  IDX["api/index.py<br/>app, CSP, error handlers"]
  RT["api/routes/state.py<br/>auth, ETag, request shape"]
  SCH["api/models/schemas.py<br/>pydantic, extra forbidden"]
  MET["api/services/metrics.py<br/>pure functions, no I/O"]
  FBC["api/services/firebase_client.py<br/>the only firebase_admin import"]
  TPL["templates plus static<br/>no build step"]

  IDX --> RT
  IDX --> TPL
  RT --> SCH
  RT --> MET
  RT --> FBC

  classDef pure fill:#1f3b2e,stroke:#6fa88a,color:#e9edf3
  classDef edge fill:#3b2a20,stroke:#d97757,color:#e9edf3
  class MET,SCH pure
  class FBC,RT edge
```

The rule that keeps this small: **routes stay thin, services stay pure, one file
owns the SDK.** `metrics.py` takes `today` as an argument and touches nothing
else, so every number on the dashboard is reproducible in a unit test. Swapping
Firestore for anything else means rewriting one file.

## Data model

One document. No collections-per-entity until something actually needs history
beyond the rolling window.

```mermaid
erDiagram
  OS_STATE ||--o{ TASK : contains
  OS_STATE ||--o{ PROJECT : contains
  OS_STATE ||--o{ HISTORY_POINT : "keeps last 90"

  OS_STATE {
    string generated_at "ISO 8601, set by the sync client"
    string source "which script wrote this"
    string brief_note "optional, set by a routine"
  }
  TASK {
    string id "line-derived, t42"
    string title "max 300 chars"
    string priority "P1 P2 or P3"
    bool done
    string due "YYYY-MM-DD, optional"
    string project "optional"
  }
  PROJECT {
    string name "filename in memory/"
    string status "active paused or done"
    string next_action "optional"
  }
  HISTORY_POINT {
    string date "one per day, replaced on re-sync"
    int open
    int done
    int overdue
  }
```

`history` lives inside the same document rather than its own collection. One read
serves the entire dashboard, no composite index is ever needed, and 90 points of
four integers is a rounding error against the 1 MB document limit.

## Trust boundaries

```mermaid
flowchart TB
  subgraph trusted["Trusted — your machine"]
    FILES["markdown files"]
    SYNCER["sync_state.py"]
  end

  subgraph server["Server — validates everything"]
    SECRET{"X-Sync-Secret<br/>constant-time compare"}
    SCHEMA{"pydantic schema<br/>extra fields forbidden"}
    TOKEN{"Firebase ID token"}
    ALLOW{"email allowlist"}
  end

  subgraph public["Public internet"]
    ANYONE["anyone"]
    OWNER["you, signed in"]
  end

  FILES --> SYNCER --> SECRET --> SCHEMA --> DB[("Firestore")]
  ANYONE --> TOKEN
  OWNER --> TOKEN
  TOKEN --> ALLOW --> DB

  SECRET -.->|"403"| REJECT["rejected"]
  SCHEMA -.->|"400"| REJECT
  TOKEN -.->|"401"| REJECT
  ALLOW -.->|"403"| REJECT
```

Firestore runs in locked mode: **no client ever reads it directly.** The browser
holds an identity, not a database credential. A stolen ID token still has to
belong to an allowlisted email, and it grants read access to one document.

The page ships a strict Content-Security-Policy with no `unsafe-inline`. The
Firebase web config travels as a `data-` attribute on `<body>` rather than an
inline `<script>`, which is why no nonce or hash is needed anywhere.

## Cost and limits

| Concern | Where it lands |
|---|---|
| Firestore reads | 1 per dashboard load, 0 on a 304 |
| Firestore writes | 1 per sync, and syncs are manual |
| Cold start | one `firebase_admin` init, cached on the module for warm invocations |
| Response time | no external call on the page route; well inside Vercel's 10s limit |
| Payload | one document, capped history, 200-task schema ceiling |

Everything fits the free tier for a single user, which was the point.

## Deliberate omissions

Writing tasks from the browser (the files are the source of truth, and a second
writer means conflict resolution) · multi-user or roles · a task history beyond
90 points · a framework or build step · a background worker · charts beyond the
two that answer "what is on fire" and "am I trending down".

Each of these is a real feature. None of them is needed by one person keeping
their week straight, and each would cost more than it returns today.
