# 0006. Detect notes with classical colour segmentation, not machine learning

- **Status:** Proposed
- **Date:** 2026-11-20
- **Deciders:** Ryan, Mahir

## Context

v1 only needs to find sticky notes: flat, brightly coloured, roughly square, on a fairly plain surface. Detection must run every frame on a laptop CPU alongside physics and drawing. The hard parts are lighting changes, the projector's own light tinting the notes, and hands passing over them.

## Options considered

1. **HSV colour thresholds + contours.** Threshold each configured colour in HSV, clean up with morphology, find contours, approximate to quadrilaterals, filter by area and squareness. Fast, explainable, testable on still images. Cons: needs tuning per room; confused by same-coloured clothing or posters.
2. **An object-detection model (YOLO-style).** Robust to lighting once trained. Cons: needs a labelled dataset we don't have, a heavier runtime, and it's harder to debug.
3. **Fiducial markers printed on notes (ArUco on every note).** Rock-solid IDs. Cons: kills the "grab any Post-it" magic.

## Decision

We will use **HSV thresholds + contour approximation** for v1, with per-colour ranges configured by `LORIKEET_NOTE_COLORS` and a tuning view in the debug overlay. Saturation does most of the work, because projected white light lowers a note's saturation less than it shifts its hue and brightness. Tracking (Phase 2) adds stable ids and debouncing so a hand covering a note doesn't delete it.

## Consequences

- Easier: everything runs on CPU in real time; tests use synthetic images and a few fixture photos.
- Harder: each new room may need retuning; games should keep the area under notes dark so projected colour doesn't wash them out.
- We're now committed to: fixture photos of real notes (no people in them; `docs/legal/privacy.md`) as the regression suite for detection.
