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
| Tracking _(Phase 2)_ | Sequences of detections: ids stay stable, a note hidden for fewer than `STABLE_FRAMES` frames survives | `tests/test_tracking.py` |
| Interface modes _(Phase 2)_ | `FakeSceneSource` drives bodies and selections; check pymunk shapes and placed/moved/removed events | `tests/test_interface.py` |
| Games _(Phase 3–4)_ | Scripted scenes, then assert game rules (ball reaches goal, tower built on placed) | `tests/games/` |
| Boundary _(Phase 2)_ | No module under `games/` imports `cv2` | `tests/test_boundaries.py` |
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
