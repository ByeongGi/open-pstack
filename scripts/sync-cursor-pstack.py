#!/usr/bin/env python3
"""Fetch Cursor's pstack and apply the mechanical half of a sync.

Reads the commit row in the working tree's UPSTREAM.md, fetches cursor/main,
and lists pstack commits after that row. --audit-only stops there. Otherwise
it runs scripts/upstream-audit.py against HEAD and scripts/upstream-merge.py
after dropping paths this port never imports. It does not resolve review rows,
edit UPSTREAM.md, commit, or push.

    python3 scripts/sync-cursor-pstack.py --audit-only
    python3 scripts/sync-cursor-pstack.py
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROW = re.compile(r"^\| Commit \| `([0-9a-f]{40})` \|$", re.MULTILINE)
CURSOR = "https://github.com/cursor/plugins.git"
EXCLUDED_PREFIXES = (
    "pstack/skills/statechart/scripts/test/",
    "pstack/skills/make-bot-ui/",
    "pstack/.cursor-plugin/",
    "pstack/docs/",
    "pstack/automations/",
)
EXCLUDED_EXACT = {"pstack/plugin.json"}


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=check)


def commit_row(text):
    match = ROW.search(text)
    if not match:
        raise SystemExit("UPSTREAM.md must contain exactly one full commit row")
    return match.group(1)


def excluded(path):
    return path in EXCLUDED_EXACT or path.startswith(EXCLUDED_PREFIXES)


def have_commit(sha):
    return git("cat-file", "-e", sha + "^{commit}", check=False).returncode == 0


def ensure_cursor(recorded):
    remotes = git("remote").stdout.split()
    if "cursor" not in remotes:
        git("remote", "add", "cursor", CURSOR)
    git("fetch", "--depth=100", "cursor", "main")
    for _ in range(8):
        if have_commit(recorded) and git("merge-base", "--is-ancestor", recorded, "cursor/main", check=False).returncode == 0:
            return
        deepened = git("fetch", "--deepen=400", "cursor", "main", check=False)
        if deepened.returncode != 0:
            git("fetch", "cursor", "main")
    if not have_commit(recorded):
        raise SystemExit(f"recorded sync commit {recorded} is not in cursor/main history")
    if git("merge-base", "--is-ancestor", recorded, "cursor/main", check=False).returncode != 0:
        raise SystemExit(f"recorded sync commit {recorded} is not an ancestor of cursor/main")


def pstack_commits(recorded):
    log = git("log", "--reverse", "--format=%H%x09%cs%x09%s", recorded + "..cursor/main", "--", "pstack/")
    commits = []
    for line in log.stdout.splitlines():
        sha, date, subject = line.split("\t", 2)
        commits.append({"sha": sha, "date": date, "subject": subject})
    return commits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-only", action="store_true", help="Fetch and report. Do not change the tree.")
    args = parser.parse_args()
    recorded = commit_row((ROOT / "UPSTREAM.md").read_text())
    head_row = commit_row(git("show", "HEAD:UPSTREAM.md").stdout)
    ensure_cursor(recorded)
    commits = pstack_commits(recorded)
    print(f"recorded {recorded}")
    print(f"cursor/main {git('rev-parse', 'cursor/main').stdout.strip()}")
    print(f"pstack commits after the recorded row: {len(commits)}")
    for commit in commits:
        print(f"  {commit['sha'][:12]} {commit['date']} {commit['subject']}")
    if not commits:
        print("in sync")
        return 0
    if args.audit_only:
        if recorded != head_row:
            print("audit tool reads the committed UPSTREAM.md row; commit the row before applying")
            return 0
        audit = subprocess.run(
            [sys.executable, "scripts/upstream-audit.py", "--port", "HEAD", "--upstream", "cursor/main"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        summary = json.loads(audit.stdout)["summary"]
        print(json.dumps(summary, sort_keys=True))
        return 0
    if recorded != head_row:
        print("refusing to apply: the working-tree sync row differs from HEAD. Commit it or restore it first.")
        return 2
    audit = subprocess.run(
        [sys.executable, "scripts/upstream-audit.py", "--port", "HEAD", "--upstream", "cursor/main"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    report = json.loads(audit.stdout)
    kept, dropped = [], []
    for change in report["changes"]:
        path = change["upstream_path"]
        if excluded(path):
            dropped.append(path)
        else:
            kept.append(change)
    report["changes"] = kept
    print(f"excluded without applying: {len(dropped)}")
    for path in dropped:
        print(f"  excluded {path}")
    if not kept:
        print("no mapped changes. Record the new sync commit in UPSTREAM.md.")
        return 0
    with tempfile.NamedTemporaryFile("w", prefix="pstack-sync-", suffix=".json", delete=False) as handle:
        json.dump(report, handle)
        audit_path = handle.name
    merged = subprocess.run([sys.executable, "scripts/upstream-merge.py", audit_path], cwd=ROOT)
    print(f"audit {audit_path}")
    return merged.returncode


if __name__ == "__main__":
    sys.exit(main())
