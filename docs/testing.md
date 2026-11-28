# Testing

## Commands

| Command | Runs |
| --- | --- |
| `make check` | ruff format check → ruff lint → pyright → pytest (exactly what CI's `Check` job runs) |
| `make test` | pytest only |
| `uv run pytest -q tests/test_geometry.py -k centre` | one file or test |

## What's tested where

CI has no camera and no display, so everything below runs headless.

| Layer | How | Path |
| --- | --- | --- |
| Geometry (homography) | Known correspondences and geometric facts (diagonals cross at the centre) | `tests/test_geometry.py` |
| Calibration _(Phase 1)_ | Render ArUco markers into a synthetic image, warp it with a known homography, check we recover it | `tests/test_calibration.py` |
| Detection _(Phase 1)_ | Synthetic images (numpy-drawn notes) plus fixture photos of real notes, asserting count, colour, and corners within tolerance | `tests/test_detection.py`, `tests/fixtures/` |
| Tracking _(Phase 2)_ | Timed sequences of detections: ids stay stable, a piece hidden for less than `LORIKEET_HIDDEN_SECONDS` survives, a moved piece gets a new id | `tests/test_tracking.py` |
| Interface _(Phase 1)_ | Pieces reject bad shapes; `changes()` reports placed and removed for each state change; `FakeSceneSource` plays scripted scenes | `tests/test_interface.py` |
| Games _(Phase 3–4)_ | Scripted scenes, then assert game rules (ball reaches goal, tower built on placed). Nest: level files load strictly; each level's stored solution wins and the go note alone doesn't; eggs, note colours, win and replay rules; the same notes always play out the same, at any frame rate | `tests/games/` |
| Desk | A fake clock drives desk notes through tracking's rules (settle, hidden grace, new id when moved); mouse drags, the palette and the sketch overlay (including the boil's timing) are checked on plain surfaces | `tests/desk/` |
| View | Outlines are placed and turned clockwise; ids are unique; things come back to front by layer | `tests/test_view.py` |
| Renderers | The flat renderer on SDL's headless driver: things drawn where they are and turned by their angle, the overlay layer laid on top | `tests/render/` |
| Launcher and debug overlay | A fake renderer stands in for the window (no display): the game gets the source's scenes and its view reaches the renderer; overlays get every event and draw in order onto a layer cleared each frame. Drawing onto the layer looks the same as drawing straight onto the frame. The debug overlay draws only edges, and only after D | `tests/test_app.py`, `tests/test_debug.py`, `tests/desk/test_overlay.py` |
| Boundary | `interface.py` imports only the standard library, and `view.py` only that plus the interface; games import nothing of Lorikeet's but those two; renderers never import a game, the desk or the launcher | `tests/test_boundaries.py` |
| On hardware | By hand: photo or clip attached to the PR | PR template |

Tests that touch pygame set `SDL_VIDEODRIVER=dummy`. Nothing in the test suite opens a camera.

## Fixtures

- Fixture photos show **notes on a surface, with no people**: no faces, hands, or reflections of people. Crop if needed (`docs/legal/privacy.md`).
- Keep them small (downscale to ≤ 640 px wide, JPEG) so the repo stays light.
- Name them for what they test: `yellow-pink-dim-room.jpg`, `hand-over-note.jpg` (the hand is an object prop, or a gloved shape cropped above the wrist).

## Rules

1. **Test behaviour, not implementation.** Assert what a caller sees (corners, ids, events), not which OpenCV calls ran.
2. **One reason to fail.** Each test checks one thing and says what in its name.
3. **Every bug gets a regression test** that fails before the fix and passes after.
4. **Never loosen a test to go green.** If a tolerance must change, the PR says why with evidence.
5. **No hardware in CI.** If logic can't be tested without the camera, move the logic out of the camera code.
6. **Deterministic.** Seed any randomness (`np.random.default_rng(seed)`), and fix timestamps in tracking tests.
