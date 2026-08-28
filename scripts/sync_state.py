"""Parse TASKS.md + memory/ and POST the state to the dashboard.

Stdlib only. Run from the repo root:

    python scripts/sync_state.py            # lint, then push
    python scripts/sync_state.py --check    # lint only, exit 1 on drift
    python scripts/sync_state.py --dry-run  # lint + print the payload, send nothing

Env (or .env.local): SYNC_URL, SYNC_SECRET.

TASKS.md line format (strict — /api/sync rejects drift):
    - [ ] P1 Title text | due:2026-07-20 | project:kandula-os
    - [x] P2 Done task
Memory file header format (first lines of memory/<project>.md):
    status: active|paused|done
    next: one-line next action
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TASK_RE = re.compile(r"^- \[( |x)\] (P[1-3]) ([^|]+?)(?:\s*\|\s*(.*))?$")
# Anything that opens like a task line; used to catch near-misses the strict
# pattern would otherwise skip in silence.
LOOSE_RE = re.compile(r"^\s*[-*]\s*\[.?\]")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEADER_RE = re.compile(r"^(status|next):\s*(.+)$")

VALID_STATUS = ("active", "paused", "done")


class DriftError(Exception):
    """A file broke the documented format. Carries per-line complaints."""

    def __init__(self, problems):
        self.problems = problems
        super().__init__(f"{len(problems)} formatting problem(s)")


def load_env_local():
    path = os.path.join(ROOT, ".env.local")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def parse_tasks():
    """Return (tasks, problems). A problem is (line_no, text, reason)."""
    tasks, problems = [], []
    path = os.path.join(ROOT, "TASKS.md")
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    in_comment = False
    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip()

        # The file documents its own format inside an HTML comment; those
        # example lines are not tasks and must not be linted as drift.
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if "<!--" in line and "-->" not in line:
            in_comment = True
            continue

        match = TASK_RE.match(line)
        if not match:
            if LOOSE_RE.match(line):
                problems.append((i, line.strip(), "does not match `- [ ] P1 Title | key:value`"))
            continue

        done, priority, title, extras = (
            match.group(1) == "x", match.group(2), match.group(3).strip(), match.group(4) or "")
        task = {"id": f"t{i}", "title": title, "priority": priority, "done": done,
                "due": None, "project": None}

        for part in filter(None, (p.strip() for p in extras.split("|"))):
            key, _, value = part.partition(":")
            key, value = key.strip(), value.strip()
            if key not in ("due", "project"):
                problems.append((i, part, "unknown field — only `due:` and `project:` are allowed"))
            elif not value:
                problems.append((i, part, f"`{key}:` has no value"))
            elif key == "due" and not DATE_RE.match(value):
                problems.append((i, part, "due date must be YYYY-MM-DD"))
            else:
                task[key] = value

        tasks.append(task)

    seen = set()
    for task in tasks:
        key = (task["title"], task["project"])
        if key in seen:
            problems.append((0, task["title"], "duplicate task title within the same project"))
        seen.add(key)

    return tasks, problems


def parse_projects():
    """Return (projects, problems) from the headers of memory/*.md."""
    projects, problems = [], []
    mem = os.path.join(ROOT, "memory")
    for fname in sorted(os.listdir(mem)):
        if not fname.endswith(".md") or fname.startswith("_"):
            continue
        head = {"status": None, "next": None}
        with open(os.path.join(mem, fname), encoding="utf-8") as fh:
            for line in fh.read().splitlines()[:10]:
                match = HEADER_RE.match(line.strip())
                if match:
                    head[match.group(1)] = match.group(2).strip()

        if head["status"] is None:
            problems.append((0, f"memory/{fname}", "missing a `status:` header line"))
            continue
        if head["status"] not in VALID_STATUS:
            problems.append((0, f"memory/{fname}",
                             f"status must be one of {', '.join(VALID_STATUS)}"))
            continue
        projects.append({"name": fname[:-3], "status": head["status"],
                         "next_action": head["next"]})
    return projects, problems


def build_state():
    """Parse both sources. Raises DriftError if anything is malformed."""
    tasks, task_problems = parse_tasks()
    projects, project_problems = parse_projects()
    problems = task_problems + project_problems
    if problems:
        raise DriftError(problems)
    return {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "source": "sync_state.py",
        "tasks": tasks,
        "projects": projects,
    }


def post(state, url, secret):
    today = datetime.date.today().isoformat()
    request = urllib.request.Request(
        f"{url.rstrip('/')}/api/sync?today={today}",
        data=json.dumps(state).encode(),
        headers={"Content-Type": "application/json", "X-Sync-Secret": secret},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.read().decode()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sync TASKS.md + memory/ to the dashboard.")
    parser.add_argument("--check", action="store_true", help="validate formatting only")
    parser.add_argument("--dry-run", action="store_true", help="print the payload, send nothing")
    args = parser.parse_args(argv)

    load_env_local()

    try:
        state = build_state()
    except DriftError as drift:
        print(f"TASKS.md / memory drift — {len(drift.problems)} problem(s):", file=sys.stderr)
        for line_no, text, reason in drift.problems:
            where = f"line {line_no}" if line_no else "file"
            print(f"  {where}: {reason}\n    {text}", file=sys.stderr)
        return 1

    counts = f"{len(state['tasks'])} tasks, {len(state['projects'])} projects"
    if args.check:
        print(f"format OK — {counts}")
        return 0
    if args.dry_run:
        print(json.dumps(state, indent=2))
        print(f"\ndry run — nothing sent ({counts})", file=sys.stderr)
        return 0

    url, secret = os.environ.get("SYNC_URL"), os.environ.get("SYNC_SECRET")
    if not url or not secret:
        print("Set SYNC_URL and SYNC_SECRET (env or .env.local).", file=sys.stderr)
        return 2

    try:
        status, body = post(state, url, secret)
    except urllib.error.HTTPError as err:
        print(f"sync failed: HTTP {err.code}\n{err.read().decode()}", file=sys.stderr)
        return 1
    except urllib.error.URLError as err:
        print(f"sync failed: {err.reason}", file=sys.stderr)
        return 1

    print(status, body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
