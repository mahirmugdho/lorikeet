# Roadmap

A box is ticked only when the work is merged **and** demonstrated (test run, screenshot, recording, or photo).

Owners follow the lanes in `docs/workflow.md`. Swap freely; just update this file.

## Phase 0: Scaffold

**Goal:** a repo where both of us and Claude can start building on day one. **Owner:** Ryan

- [ ] Tooling: uv, ruff, pyright, pytest, `make check`
- [ ] First real code: camera→projector homography (`geometry.py`) with tests
- [ ] CI `Check` green on GitHub
- [ ] Docs: pitch, roadmap, ADRs 0001–0007, setup, workflow, testing, security, legal, BUY
- [ ] Claude setup: `CLAUDE.md`, `.claude/settings.json`, `/ship`, `/new-adr`
- [x] Mahir decides stack (ADR 0002) and license (ADR 0003)

**Done when:** the scaffold PR is merged with CI green, and ADRs 0002/0003 are Accepted or superseded.

## Phase 1: See the notes

**Goal:** real Post-its on a real surface get outlined by the projector, exactly on top of them. **Owner:** Mahir

- [ ] `capture.py`: open the webcam by index, read frames, report FPS
- [ ] Fullscreen pygame-ce window on the projector display (`LORIKEET_DISPLAY_INDEX`)
- [ ] `calibration.py`: project 4 ArUco markers, find them, compute and save the homography
- [ ] `detection.py`: HSV thresholds + contours, so each note becomes a quad with a colour, in projector pixels
- [ ] Detection tests on synthetic images and 3+ fixture photos (no people)
- [ ] Debug overlay: outline every detected note on the projection; colour-tuning view
- [ ] Measure end-to-end latency (note moved → outline moved)

**Done when:** a photo or clip shows projected outlines sitting on real notes after calibration, and detection tests pass in CI.

## Phase 2: Track notes, define the interface

**Goal:** games get a stable, testable stream of notes in both modes, with no camera required. **Owner:** Mahir (vision and the interface)

- [ ] `tracking.py`: stable ids across frames, debounce for hands (`LORIKEET_STABLE_FRAMES`)
- [ ] `interface.py`: `Note`, `Scene`, `SceneSource`, `FakeSceneSource`
- [ ] Bodies mode: notes become static pymunk polygons
- [ ] Selections mode: `placed` / `moved` / `removed` events on a grid
- [ ] Test that nothing under `games/` imports `cv2`
- [ ] Sandbox demo: a ball bouncing off real notes

**Done when:** a recording shows a pymunk ball bouncing off real Post-its, and mode tests run on the fake source in CI.

## Phase 3: Puzzle game (bodies)

**Goal:** a playable physics puzzle where notes are the level. **Owner:** Ryan

- [ ] Ball spawn, goal zone, win detection
- [ ] 5+ levels with obstacles and par times
- [ ] Reset and next-level flow without touching the laptop
- [ ] Game-rule tests on scripted scenes

**Done when:** a recording shows someone beating a level by placing notes.

## Phase 4: Tower defense (selections)

**Goal:** a playable tower defense where placing a note builds a tower. **Owner:** Ryan, with Mahir once Phase 2 lands

- [ ] Grid, enemy path, waves
- [ ] Note placed on a cell builds a tower; removing it sells it
- [ ] Note colour picks tower type
- [ ] Rule tests on scripted selection events

**Done when:** a recording shows a wave defended with notes.

## Phase 5: Demo-ready

**Goal:** someone new can set it up from the docs and play both games. **Owners:** both

- [ ] Launcher: pick calibrate, puzzle, or tower defense from the projection
- [ ] Recalibration prompt when alignment drifts
- [ ] Demo GIF in the README (no bystanders in frame)
- [ ] Setup tested end-to-end by someone who isn't us, using only `docs/setup.md`

**Done when:** a first-time user goes from clone to playing in under 30 minutes, recorded.
