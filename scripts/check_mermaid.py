"""Fail the build on Mermaid that GitHub's pinned renderer chokes on.

    python scripts/check_mermaid.py [paths...]      # defaults to the repo root

GitHub renders Mermaid with an older release than the docs assume. The failure
mode is silent — the diagram becomes "Unable to render rich display" — so this
runs in CI instead of being noticed months later.

Checks: unclosed fences, ampersands inside a diagram, and a missing diagram type
on the opening line.
"""
import os
import re
import sys

FENCE_RE = re.compile(r"^\s*```(\w*)\s*$")
DIAGRAM_TYPES = (
    "flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram",
    "stateDiagram-v2", "erDiagram", "journey", "gantt", "pie", "gitGraph",
    "mindmap", "timeline", "quadrantChart", "xychart-beta", "block-beta",
)


def check_file(path):
    """Return a list of (line_no, problem) for one markdown file."""
    problems = []
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    in_block = False
    start = 0
    body = []

    for i, line in enumerate(lines, start=1):
        fence = FENCE_RE.match(line)
        if fence and not in_block and fence.group(1) == "mermaid":
            in_block, start, body = True, i, []
            continue
        if fence and in_block and not fence.group(1):
            if not body:
                problems.append((start, "empty mermaid block"))
            elif body[0].split(" ")[0].split("(")[0] not in DIAGRAM_TYPES:
                problems.append((start + 1, f"unknown diagram type: {body[0][:40]!r}"))
            in_block = False
            continue
        if in_block:
            body.append(line.strip())
            if "&" in line:
                problems.append((i, "'&' does not render on GitHub — write 'and' instead"))

    if in_block:
        problems.append((start, "mermaid block is never closed"))
    return problems


def markdown_files(targets):
    for target in targets:
        if os.path.isfile(target):
            yield target
            continue
        for root, dirs, names in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith((".", "__", "node_modules"))]
            for name in sorted(names):
                if name.endswith(".md"):
                    yield os.path.join(root, name)


def main(argv):
    targets = argv or [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    total = 0
    checked = 0

    for path in markdown_files(targets):
        problems = check_file(path)
        checked += 1
        for line_no, problem in problems:
            print(f"{path}:{line_no}: {problem}", file=sys.stderr)
        total += len(problems)

    if total:
        print(f"\n{total} mermaid problem(s) across {checked} file(s).", file=sys.stderr)
        return 1
    print(f"mermaid OK — {checked} markdown file(s) checked")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
