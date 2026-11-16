---
name: sync-cursor-pstack
description: "Re-sync this open-pstack checkout to Lauren Tan's cursor/plugins pstack after upstream changes. Use for /sync-cursor-pstack."
disable-model-invocation: true
---

# Sync Cursor pstack

Bring this checkout up to the current `pstack/` tree in `https://github.com/cursor/plugins.git`. Run it from the open-pstack repository root. [`UPSTREAM.md`](../../../../UPSTREAM.md) owns the exclusions and the recorded sync commit.

1. Run `python3 scripts/sync-cursor-pstack.py`. It fetches `cursor/main`, audits commits after the sync row, and applies `scripts/upstream-merge.py` to mapped files. It skips Cursor manifests, the guide, Benny, `make-bot-ui`, and `statechart/scripts/test/`. It does not commit, push, or move the sync row.
2. If the script says the tree is already at that commit, stop.
3. Resolve every `review` line before doing anything else. Keep the port's adaptation and take upstream's new intent beside it. A Cursor model slug in a skill stays a role pointer. Put a model change in `plugins/pstack/skills/poteto-mode/scripts/runner/registry/models.ts` only when that family already exists in the catalog. Delete a file upstream deleted once nothing in the tree still references it.
4. When `models.ts` changed, regenerate the catalog from `plugins/pstack/skills/poteto-mode/scripts` with `bun runner/registry/render.ts --write`.
5. After every review line is resolved, update the commit and upstream version in `UPSTREAM.md`, add the provenance row in `NOTICE.md`, and keep `README-UPSTREAM.md` when the merge checked it out. Record each new adaptation or exclusion in `UPSTREAM.md`. Do not move the sync row while a review line is open.
6. Run `python3 scripts/sync-cursor-pstack.py --audit-only`. No commits after the new row means the sync point matches. Then run the registry tests.
7. Do not commit or push unless the user asked.
