# Lorikeet

Lorikeet turns a projector, a webcam, and sticky notes into physical play surfaces for games. A camera watches the projected area, computer vision finds each Post-it, and Lorikeet hands each one to games as a **piece**, which a game treats as a **rigid body** (physics puzzles) or a **selection** (tower defense, strategy). Ryan (@RyanS2025) and Mahir (@mahirmugdho) are building it, with Claude.

## Start here

- [docs/product/pitch.md](docs/product/pitch.md): problem, core loop, v1 scope, open questions
- [docs/ROADMAP.md](docs/ROADMAP.md): phases, owners, what's actually done
- [docs/adr/](docs/adr/README.md): decisions. Read the ones covering what you're about to change.
- **Stack and license are settled:** ADR 0002 (Python + OpenCV + pygame-ce + pymunk) and ADR 0003 (MIT) are Accepted.

## Commands

| Command | What it does |
| --- | --- |
| `make setup` | Install Python 3.13 + dependencies into `.venv` (needs `brew install uv`) |
| `make check` | **Everything CI runs**: ruff format check, ruff lint, pyright, pytest |
| `make test` | Tests only (`uv run pytest -q`; add `-k name` for one) |
| `make lint` | ruff + pyright |
| `make fmt` | Format and apply safe lint fixes |
| `uv run lorikeet` | Run Lorikeet. For now: desk input (drag notes with the mouse) in a window; `--output projector` fills the projector. `--help` lists the options |
| `uv run --env-file .env lorikeet` | The same, with your `.env` settings (colours, note size, projector display) |
| `uv run lorikeet calibrate` | Recalibrate camera → projector _(after Phase 1)_ |

## Layout

```
src/lorikeet/
  geometry.py        camera→projector homography (Phase 0, tested)
  capture.py         webcam frames                       (Phase 1)
  calibration.py     ArUco markers → homography          (Phase 1)
  detection.py       HSV + contours → piece outlines     (Phase 1)
  tracking.py        stable piece ids, states            (Phase 2)
  interface.py       Piece, Scene, SceneSource, changes  (Phase 1, the contract)
  app.py             launcher: input + output -> a game; the only code that knows them
  desk/              desk input: drag notes on screen, no camera or projector
  debug.py           debug overlay (press D): what games are told about each piece
  games/puzzle/      physics puzzle: pieces as bodies    (Phase 3)
  games/tower_defense/  pieces as selections             (Phase 4)
tests/               pytest; mirrors src/, plus fixtures/ (no people in images)
docs/                product/, adr/, security/, legal/, ROADMAP, setup, workflow, testing, BUY
.github/             CI (Check), PR title, @claude, auto-merge, Dependabot, rulesets/main.json
```

## Non-negotiables

1. **Games import only `lorikeet.interface`.** No `cv2`, camera frames, or detection internals under `games/` (ADR 0004). `interface.py` itself imports only the standard library. `tests/test_boundaries.py` checks both.
2. **Projector pixels are the only coordinates past detection.** Convert with the calibration homography before a note leaves the vision code (ADR 0005).
3. **Camera frames stay in memory on this machine.** No saving, logging, or sending frames unless `LORIKEET_DEBUG_SAVE_FRAMES=1`, and then only to gitignored `.lorikeet/` (ADR 0007, [privacy](docs/legal/privacy.md)).
4. **No people in committed images**: fixtures, screenshots, and README media ([privacy](docs/legal/privacy.md)).
5. **Nothing flashes full-screen more than 3 times a second**, calibration patterns included ([threat model](docs/security/threat-model.md) T6).
6. **Logic is testable without hardware.** CI has no camera or display. Detection is tested on still images and games on a fake `SceneSource` ([testing](docs/testing.md)).
7. **`make check` is green before every PR. Never loosen a test to make it pass** ([testing](docs/testing.md)).
8. **Changes to `interface.py` need the other lane's review** ([workflow](docs/workflow.md)).

## How to work

- **Team: check open PRs first** (`gh pr list`) so you don't collide with your teammate's lane.
- **Plan before multi-file changes.** Write the plan (superpowers:writing-plans) and get a nod before editing.
- **Tests first for logic**: geometry, detection on fixture images, tracking, game rules.
- **Small PRs, one concern each**, reviewable in about 15 minutes. Squash-merged.
- **Conventional Commits.** Scopes: `geometry calibration detection tracking interface desk app puzzle tower-defense ci docs deps`. Example: `feat(detection): find yellow notes as quads`.
- **No AI co-authors.** Commits and PRs are authored by the human only. Never add a `Co-Authored-By: Claude` trailer or a "Generated with Claude Code" line to a commit message or PR body. `.claude/settings.json` turns Claude Code's byline off (`attribution`); don't add it by hand.
- A choice that's expensive to reverse gets an ADR: `/new-adr`.
- Ready for review: `/ship` (it runs `make check`, self-reviews, and opens the PR).
- **Verify, don't assume.** Run the test, look at the projector, paste the output. "Should work" isn't evidence.
- New dependency: add it with `uv add <pkg>` in the phase that first uses it, and commit `uv.lock`.
- Look up current API docs with context7 (OpenCV, pygame-ce, and pymunk APIs drift between versions).

## Which skill when

| Situation | Skill |
| --- | --- |
| New feature or game idea, fuzzy scope | `superpowers:brainstorming` |
| Starting a roadmap phase | `superpowers:writing-plans`, then `superpowers:executing-plans` |
| Writing logic | `superpowers:test-driven-development` |
| Bug or flaky detection | `superpowers:systematic-debugging` |
| About to say "done" | `superpowers:verification-before-completion` |
| Recording a decision | `/new-adr` |
| Opening a PR | `/ship` |
| Reviewing a PR | `code-review:code-review`, `pr-review-toolkit:review-pr` |
| Code works but is tangled | `code-simplifier` |
| Touching capture, files, or (later) network code | `claude-security`, `docs/security/checklist.md` |
| Updating this file | `claude-md-management:revise-claude-md` |

## Gotchas

- **`uv.lock` is committed**; CI runs `uv sync --locked`, so a stale lock fails loudly. Run `uv sync` after changing deps.
- **Python 3.13 is pinned** in `.python-version`. Homebrew's 3.14 is on the machine, but pygame-ce, pymunk, and OpenCV wheels lag new Pythons, so uv installs 3.13 itself.
- **Use `opencv-python-headless`**, never `opencv-python`. We draw with pygame; the GUI build drags in Qt, which fights SDL on macOS, and needs `libGL` on CI.
- **macOS camera permission** goes to the app that launches Python (Terminal, VS Code). Without it, `VideoCapture` opens but returns black or empty frames.
- **Camera index 0 may be the built-in camera or an iPhone** (Continuity Camera). External webcams land at 1+. Set `LORIKEET_CAMERA_INDEX`.
- **The projector must be an extended display, not mirrored**, or calibration is off by the resolution ratio.
- **The projection lights up the notes.** Whatever the game draws under a note shifts its colour. Keep the area under detected notes dark/neutral, and threshold mostly on saturation (ADR 0006).
- **Webcam auto-exposure and white balance drift** as the projected image changes. Lock them where the camera allows (`CAP_PROP_AUTO_EXPOSURE`); otherwise expect thresholds to wander.
- **Hands cover notes.** A settled piece that goes missing is `HIDDEN`, not removed, until it's been gone for `LORIKEET_HIDDEN_SECONDS` (2 s). Time settings are in seconds, not frames, because webcams drop frames in dim rooms.
- **`Piece` in code, "note" in prose.** A piece is any solid-coloured sticky thing, or several touching ones merged. A moved piece is a new piece with a new id, so a settled piece never changes (ADR 0004).
- **Tests needing pygame** set `SDL_VIDEODRIVER=dummy`; nothing in CI may open a real window or camera. Tests that only draw on a `pygame.Surface` need no display at all.
- **Games never see input or output.** The launcher (`app.py`) gives a game `update(scene, dt)` and `draw(canvas)`, nothing else. Mouse, keyboard, the desk's paper and the debug overlay are overlays drawn after the game. `tests/test_boundaries.py` stops games importing the desk or the launcher.
- `docs/product/idea.md` is Mahir's original README, **verbatim**. Never edit it. Ruff 0.17+ formats code blocks inside Markdown too, so `idea.md` is excluded in `pyproject.toml`; keep it that way.
- Games must be original: no names, art, levels, or music from existing games.
- **Adding a teammate** means updating `.github/CODEOWNERS` *and* `include_comments_by_actor` in `.github/workflows/claude.yml`. Otherwise `@claude` ignores their comments.
