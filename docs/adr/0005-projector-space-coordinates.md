# 0005. Projector pixels are the only coordinates games see; calibrate with projected markers

- **Status:** Proposed
- **Date:** 2026-11-20
- **Deciders:** Ryan, Mahir

## Context

The webcam sees the projection at an angle and at a different resolution. A note at camera pixel (412, 230) means nothing to a game drawing at 1280x720. Mixing coordinate spaces is the classic projector-camera bug: everything is almost aligned, and off by more the further it is from the centre. The camera or projector also gets bumped between sessions.

## Options considered

1. **One coordinate space (projector pixels) behind a homography.** At startup the projector shows four ArUco markers at known projector positions; OpenCV finds them in the camera image; `cv2.findHomography` (or `lorikeet.geometry.homography_from_corners` for exactly four points) gives camera→projector. Detection converts every polygon before it leaves the vision lane. Cons: needs a calibration step per setup.
2. **Manual corner clicking.** The user clicks the four projection corners in a camera preview. Cons: slower, error-prone, needs a mouse at the projector.
3. **Games work in camera space.** No calibration. Cons: games can't draw where notes are; unusable.

## Decision

We will treat **projector pixels as the single coordinate system** for everything past detection, and calibrate automatically with projected ArUco markers (cv2.aruco is in core OpenCV since 4.7). The homography is saved to `LORIKEET_CALIBRATION_PATH` and reused until the user recalibrates. Calibration patterns are static (no flashing; see threat model T6).

## Consequences

- Easier: games are plain 2D code; a note's outline can be drawn exactly on the note (the Phase 1 debug overlay proves alignment).
- Harder: a flat surface is assumed. Curved or angled surfaces need a different model.
- We're now committed to: recalibrating after either device moves, and testing geometry with known homographies (`tests/test_geometry.py`).
