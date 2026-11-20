# 0002. Build Lorikeet as one local Python process (OpenCV + pygame-ce + pymunk)

- **Status:** Proposed. **Waiting on Mahir's call** in the scaffold PR.
- **Date:** 2026-11-20
- **Deciders:** Ryan, Mahir

## Context

Lorikeet has to read a webcam, find sticky notes, map them into projector space, simulate physics against them, and draw a fullscreen game on a second display, all with low enough latency that moving a note feels direct (target: under 150 ms from note movement to projected response). It runs in a room with a laptop, a projector, and a webcam. There's no server, no accounts, no database. Two people build it, and the CV is the hardest and least familiar part.

## Options considered

1. **Python, one process: OpenCV + pygame-ce + pymunk.** Python is OpenCV's best-supported binding and has the most CV examples. pymunk (Chipmunk2D) provides the rigid bodies for mode 1, and pygame-ce does fullscreen drawing on a chosen display. One language, one process, no protocol. Cons: pygame looks plain without effort, and Python makes demos harder to share than a URL.
2. **TypeScript in the browser: getUserMedia + OpenCV.js/MediaPipe + Matter.js.** Demo by URL, and the rendering is nicer. Cons: OpenCV.js is a ~10 MB WASM build with awkward memory management, and browser camera/fullscreen permissions vary by machine.
3. **Python CV + separate game engine (Godot/Unity) over a local WebSocket.** Best-looking games and lets anyone's engine plug in. Cons: two codebases, a wire protocol, and a second process to keep in sync from day one, all before a single game works.

## Decision

We will build v1 in **Python 3.13 with uv**: `opencv-python-headless` for capture and detection, `pygame-ce` for the fullscreen projector window, `pymunk` for physics, and `numpy` for geometry. Everything runs in one local process with no server or database. Option 1 is the shortest path to a note on a wall moving a ball in a game, and the interface boundary (ADR 0004) keeps option 3 open as a later add-on: a bridge that serialises the same `Scene` for outside engines.

`-headless` because we draw with pygame, not OpenCV's GUI. It avoids Qt clashing with SDL on macOS and missing `libGL` on CI.

## Consequences

- Easier: one toolchain (`make check`), CV examples translate directly, games are testable with plain pytest.
- Harder: polished visuals take more work in pygame, and sharing a demo means sharing a laptop or a recording.
- We're now committed to: a desktop install (uv + Python), and keeping cv2 out of game code so a future bridge stays possible.
- Dependencies arrive with the phase that uses them: numpy now, OpenCV + pygame-ce in Phase 1, pymunk in Phase 2.
