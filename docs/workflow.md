# Workflow

## The loop

1. **Issue.** Every change starts as a GitHub issue (Bug or Feature template), or a roadmap checkbox.
2. **Branch** off fresh `main`: `feat/detection-quads`, `fix/calibration-flip`, `docs/setup-lighting`.
3. **Plan.** Multi-file changes get a written plan first (`superpowers:writing-plans`).
4. **Build + tests.** Tests first for logic. Hardware-facing changes also get tried on the real projector + webcam.
5. **Check:** `make check` must be green.
6. **Ship:** `/ship` self-reviews and opens the PR with the template filled.
7. **Review:** the *other* teammate reviews and approves (CODEOWNERS requests them automatically).
8. **Squash merge.** Auto-merge fires once `Check` passes and the review is in. The PR title becomes the commit on `main`.

## Conventions

| Thing | Rule |
| --- | --- |
| Branches | `feat/…`, `fix/…`, `docs/…`, `chore/…`, `refactor/…`, `test/…` |
| Commits & PR titles | Conventional Commits: `type(scope): summary`. `pr-title.yml` enforces it on PR titles |
| Scopes | `geometry calibration detection tracking interface puzzle tower-defense ci docs deps` |
| PR size | One concern, reviewable in ~15 minutes. Split anything bigger |
| Merging | Squash only. `main` changes only through PRs |
| Hold a PR | Open it as a draft or add the `no-automerge` label |
| ADRs | When a choice is expensive to reverse (library, data shape, coordinate system, security boundary): `/new-adr` |
| Roadmap | Tick a box only with evidence: test run, screenshot, recording, or photo |

## Working with Claude

- Claude reads `CLAUDE.md` every session. Keep it accurate; update it in the same PR as the change that makes it stale.
- Ask for a plan before multi-file work, and read it before saying go.
- Claude must show evidence: pasted test output, a screenshot, or a photo of the projector. Treat "should work" as "not verified".
- **No AI co-authors.** Commits and PRs carry only the human author: no `Co-Authored-By: Claude` trailers or "Generated with Claude Code" lines. Claude Code's byline is off in `.claude/settings.json`.
- Fill the PR template's **AI assistance** section honestly: what Claude wrote, and what you're unsure about.
- `@claude` in an issue or PR comment runs Claude in GitHub Actions (once `CLAUDE_CODE_OAUTH_TOKEN` is set). PRs it opens never auto-merge, so a human reviews them.
- Never paste camera frames with people in them into a Claude session, an issue, or a PR (ADR 0007).

## Reviewing each other's PRs

- Every PR needs the *other* person's approval. You can't approve your own.
- Review within a day. If you can't, say so in the PR.
- Check the non-negotiables in `CLAUDE.md` first, then correctness, then style.
- Pull the branch and run it on hardware when it touches capture, calibration, detection, or a game.
- "Request changes" means blocking. Use a plain comment for nits.
- Accepting an ADR: the reviewer comments "accept", the author flips its status to `Accepted` on the same PR, and the reviewer approves that final commit. The ruleset requires approval of the **last push** by someone other than the pusher, so a commit added after approval (by either of us, or by `@claude`) never merges unreviewed.

## Lanes

Agreed in the scaffold PR. Rename or swap it by editing this table in a PR.

| Lane | Owner | Owns | Rule |
| --- | --- | --- | --- |
| Vision (camera → notes) | Mahir | `capture`, `calibration`, `detection`, `tracking`, debug overlay | Emits notes in projector pixels only |
| Games (notes → play) | Ryan | `games/puzzle`, `games/tower_defense`, launcher | Imports `lorikeet.interface` only |
| Interface (the contract) | Mahir | `interface.py`, mode adapters, `FakeSceneSource` | Changes need the other lane's approval |
| Repo & docs | Both | CI, `.claude/`, `docs/` | Whoever notices it fixes it |

Before starting work, run `gh pr list` and check open PRs so you don't collide.
