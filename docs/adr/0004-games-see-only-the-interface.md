# 0004. Games see only the Lorikeet interface: a Scene of pieces

- **Status:** Accepted, 2026-11-26. Ryan accepted option 1 on #6.
- **Date:** 2026-11-25 (first drafted 2026-11-20 with two built-in modes; amended before acceptance)
- **Deciders:** Ryan, Mahir

## Context

The README promises "an interface" that turns the camera feed into shapes any game can use: as **hard-bodied objects** in physics games, or as **selections** in strategy and tower-defense games. If games reach into OpenCV or camera frames directly, every game breaks when detection changes, games can't be tested without hardware, and the two lanes (vision and games) block each other.

What's on the surface isn't always a Post-it: any solid-coloured sticky object should work, and touching notes can merge into one shape. Detection is noisy, too. Outlines wobble by a pixel or two, a hand reaching past a note hides it, and the game's own projected light can briefly look like a note.

## Options considered

1. **One interface; each game interprets it.** Each frame, the vision code hands over a `Scene`: a snapshot of every piece, each with a stable id, a colour, a state, and its shape in projector pixels. A physics game turns pieces into bodies. A tower defense compares two scenes to find what was placed and removed. Cons: each game does its own interpreting, though a shared helper covers the common case.
2. **One interface with two built-in modes** (this ADR's first draft): a `bodies` adapter that builds pymunk shapes and a `selections` adapter that emits grid events. Cons: the contract grows by two adapters and a pymunk dependency, and each new kind of game would need a new mode.
3. **Games read detection output directly.** Less code at first. Cons: tight coupling, no fake input for tests, and two people editing the same structures.

## Decision

We will go with option 1, and put the contract in `src/lorikeet/interface.py`, which imports only the standard library:

- **`Piece`** is a frozen record of one sticky thing, or of several touching ones merged into one. It has an `id`, a `color`, a `state`, an `outline` (its true shape, which can be concave), and `parts` (convex polygons covering the outline, for physics engines). Coordinates are plain tuples of floats in projector pixels (ADR 0005), not numpy arrays.
- **Games see three states.** `MOVING` means seen this frame and still shifting. `SETTLED` means held still long enough to count as placed, with its outline frozen. `HIDDEN` means a settled piece the camera can't see right now, probably because of a hand. Tracking has two more states that games never see: blobs it hasn't confirmed yet (so a projected ball's motion blur never becomes a piece), and pieces that are gone.
- **A moved piece is a new piece.** A settled piece never changes. If it moves, or a note is stuck against it, it ends, and a new piece with a new id starts. Ids are never reused.
- **A hidden piece lasts 2 seconds** (`LORIKEET_HIDDEN_SECONDS`) before it's gone. Only settled pieces get this grace period: a piece that vanishes while still `MOVING` is dropped at once. Timings are in seconds, not frames, because webcams drop frames in dim rooms.
- **A `Scene`** is the capture time plus a tuple of pieces with unique ids.
- **A `SceneSource`** is a protocol with one method, `latest()`, which returns the newest scene without waiting for the camera. The live pipeline implements it, and so does `FakeSceneSource`, which plays scripted scenes for tests.
- **`changes(before, after)`** treats a piece as placed while it's `SETTLED` or `HIDDEN`, and reports the pieces that entered that group (`placed`) and left it (`removed`). There's no `moved` event.
- **Colours are names** configured per room (`LORIKEET_PIECE_COLORS`), so adding a colour never changes the interface. Each colour's thresholds, and which colours merge, are detection settings calibrated per setup (ADR 0006).

Games depend on this module and on nothing in `capture`, `calibration`, `detection`, or `tracking`. Changes to `interface.py` need review from *both* lanes.

## Consequences

- Easier: game tests run on a `FakeSceneSource` (no camera, no projector, CI-friendly), the vision lane can rewrite detection and tracking freely, and a later network bridge just serialises `Scene`.
- Easier: a game never updates a settled piece. It only creates and destroys pieces by id.
- Harder: an interface change is a two-person decision.
- Harder: sticking a note against a placed piece replaces it with a bigger one, so a tower defense sees the old tower removed and a new one placed. Spacing grid cells so notes on them don't touch avoids this.
- Harder: a piece peeled off the surface stays in the scene, `HIDDEN`, for 2 seconds.
- We're now committed to: no OpenCV and no vision modules imported under `src/lorikeet/games/`, and an interface that imports only the standard library. `tests/test_boundaries.py` enforces both.
