# Setup

## Machine (macOS)

```bash
brew install uv gh                 # Python toolchain + GitHub CLI
gh auth login
git clone https://github.com/mahirmugdho/lorikeet.git ~/code/lorikeet
cd ~/code/lorikeet
make setup                         # uv installs Python 3.13 and syncs .venv
make check                         # should end with "N passed"
cp .env.example .env               # local settings (no secrets); used from Phase 1
```

Clone into `~/code/`, **not** `~/Documents/` or `~/Desktop/`. If iCloud "Desktop & Documents" sync is on, it creates `file 2.md` conflict copies inside `.git` and corrupts the repo.

Editor: VS Code with the Python and Ruff extensions. Point the interpreter at `.venv/bin/python`.

## Play at your desk (no hardware)

```bash
uv run lorikeet
```

Desk play needs no projector or camera. Two windows open:

- **The game window** is the projection: exactly what would go on the wall. Stuck-down notes get a pencil outline, and the paper itself isn't drawn, because on the wall it's real. Press D here to see what the game is told about each note.
- **The desk window** shows the same game drawn in pencil, with the notes as paper. Play here: drag a note from the pad at the bottom onto the desk, drag placed notes to move them, roll the wheel to turn the one you hold, and right-click to peel one off. Tab hides the pad.

Esc in either window quits. Without a projector the windows share this screen; move or resize them as you like. With a projector plugged in, `uv run lorikeet --output projector` puts the game window on the wall and keeps the desk window here.

## Hardware _(from Phase 1)_

Parts are in [BUY.md](BUY.md). Room setup:

1. Plug in the projector as an **extended** display (System Settings → Displays → turn off mirroring). Note its display index and set `LORIKEET_DISPLAY_INDEX` in `.env`.
2. Mount the webcam so it sees the entire projected area, as close to the projector lens as practical (less skew means better detection). Set `LORIKEET_CAMERA_INDEX`.
3. Give the app that runs Python (Terminal or VS Code) camera access: System Settings → Privacy & Security → Camera.
4. Dim the room. Bright ambient light washes out both the projection and note colours.
5. Run calibration (`uv run lorikeet calibrate`, Phase 1) whenever the camera or projector moves.

## Claude Code

`.claude/` is committed and gives every session:

- `settings.json`: allowlisted `make`/`uv`/`git`/`gh` read commands, denies for `.env` reads and force-pushes or direct pushes to `main`, a hook that ruff-formats every edited `.py` file, and the team plugin set (superpowers, code review, security, GitHub, context7).
- `skills/ship/`: `/ship` checks, self-reviews, and opens a PR.
- `skills/new-adr/`: `/new-adr` records a decision in `docs/adr/`.

Personal overrides go in `.claude/settings.local.json` (gitignored). Start each session by reading `CLAUDE.md`, which Claude does automatically.

## GitHub settings checklist

Ryan has Write access; Mahir owns the repo. Owner-only settings are marked **Mahir**.

| Setting | Status |
| --- | --- |
| CI `Check` runs on PRs and pushes to `main` | Done (in the scaffold PR) |
| `no-automerge` label | Done (Ryan) |
| Squash-only merges, auto-merge, delete branch on merge | **Mahir**: block below |
| Dependabot alerts + security fixes, secret scanning + push protection | **Mahir**: block below |
| Private vulnerability reporting (used by `SECURITY.md` and the issue chooser) | **Mahir**: block below |
| `main` ruleset: PR required, 1 approval + code owner, last push approved by someone else, `Check` must pass, no force-push or delete; the repo admin (Mahir) can bypass it when merging a PR | **Mahir**: block below, **after** `Check` has run once |
| `CLAUDE_CODE_OAUTH_TOKEN` secret for `@claude` | **Mahir** (secrets need Admin): see Secrets |

Mahir, run this from the repo root once the scaffold PR's `Check` has reported:

```bash
R=mahirmugdho/lorikeet
gh repo edit $R --enable-squash-merge --enable-merge-commit=false --enable-rebase-merge=false \
  --delete-branch-on-merge --enable-auto-merge --enable-wiki=false --enable-projects=false
gh api -X PUT repos/$R/vulnerability-alerts
gh api -X PUT repos/$R/automated-security-fixes
gh api -X PATCH repos/$R --input - <<'EOF'
{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}
EOF
gh api -X PUT repos/$R/private-vulnerability-reporting
gh api -X POST repos/$R/rulesets --input .github/rulesets/main.json
```

Until auto-merge is enabled on the repo, `automerge.yml` fails on every PR that doesn't carry the `no-automerge` label. That failure is harmless (it's not a required check), but it's noisy.

## Secrets

| Secret | Needed for | How |
| --- | --- | --- |
| `CLAUDE_CODE_OAUTH_TOKEN` | `@claude` in issues and PRs (`claude.yml`) | Run `/install-github-app` in Claude Code, or `claude setup-token` and add it as a repo secret |
| `AUTOMERGE_TOKEN` | Not needed: nothing deploys on push to `main` | Only if a push-triggered workflow is added later |

The app itself needs no secrets (`.env.example` holds settings only).

## Services by phase

None. Lorikeet runs entirely on one laptop with no server, database, or cloud service (ADR 0002, ADR 0007). A network bridge for outside engines is post-v1 and would bind to `127.0.0.1` only.
