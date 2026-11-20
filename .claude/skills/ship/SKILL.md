---
name: ship
description: Get the current branch ready for review and open a PR. Use when the user says /ship, "open a PR", "ship it", or "ready for review".
---

# Ship

Stop and report at the first step that fails. Never skip a failing check to get the PR open.

1. **Branch sanity.** `git status` and `git branch --show-current`. If on `main`, stop: create a `feat/…`/`fix/…` branch first. If there are uncommitted changes, show them and ask before committing.
2. **Checks.** Run `make check`. Paste the real tail of the output. If anything fails, fix it or stop and ask.
3. **Self-review the diff.** `git diff main...HEAD`. Look for: leftover debug output, commented-out code, secrets, TODOs without an issue, files that don't belong to this PR's one concern.
4. **Rules check** against the `CLAUDE.md` non-negotiables. For each one this diff touches, say how the change respects it.
   - Camera capture, frame handling, or debug output changed → walk `docs/security/checklist.md` (frames stay in memory, nothing saved or sent unless `LORIKEET_DEBUG_SAVE_FRAMES=1`).
   - Anything drawn on the projector changed (games, calibration patterns) → no full-screen flashing faster than 3 times a second (`docs/security/threat-model.md` T6).
   - A game imports `cv2` or touches camera coordinates → stop. Games use `lorikeet.interface` only (ADR 0004) and see projector pixels only (ADR 0005).
   - New test fixture image → no people in it (`docs/legal/privacy.md`).
   - `src/lorikeet/interface.py` changed → it's the contract between the two lanes, so the other teammate must review it (`docs/workflow.md`).
   - New architectural choice → suggest `/new-adr`.
   - Finished a roadmap item → tick it in `docs/ROADMAP.md` only if it's demonstrated (test run, screenshot, recording).
5. **Write the PR body** using `.github/pull_request_template.md`. Fill every section honestly, including "AI assistance". Tick only boxes you actually verified.
6. **Push and open:** `git push -u origin HEAD`, then `gh pr create --title "<conventional title>" --body-file <tmpfile>`, with the title in Conventional Commit form (`feat(detection): …`).
7. **Auto-merge** (if `.github/workflows/automerge.yml` exists): the PR squash-merges as soon as required checks pass. To hold it for a human, add the `no-automerge` label or open it as a draft (`gh pr create --draft`).
8. Report the PR URL, whether it will auto-merge, and the one thing the reviewer should look at hardest.
