# 0004. Games see only the Lorikeet interface: a Scene of notes, in two modes

- **Status:** Proposed
- **Date:** 2026-11-20
- **Deciders:** Ryan, Mahir

## Context

The README promises "an interface" that turns the camera feed into shapes and objects any game can use, in two modes: notes as **hard-bodied objects** (physics games) and notes as **selections** (strategy and tower-defense games). If games reach into OpenCV or camera frames directly, every game breaks when detection changes, games can't be tested without hardware, and the two lanes (vision and games) block each other.

## Options considered

1. **A narrow interface module.** Vision produces a `Scene` (a timestamped list of `Note`s: stable id, colour, polygon and centre in projector pixels). Two adapters sit on top: `bodies` (each note becomes a static pymunk shape) and `selections` (a note settling on a cell emits `placed`/`moved`/`removed` events, like a click). Games import only `lorikeet.interface`. Cons: one more layer to design up front.
2. **Games read detection output directly.** Less code at first. Cons: tight coupling; no fake input for tests; two people editing the same structures.

## Decision

We will put the contract in `src/lorikeet/interface.py`: `Note`, `Scene`, a `SceneSource` protocol (the live camera pipeline or a scripted fake), and the two mode adapters. Games depend on it and on nothing in `capture`, `calibration`, or `detection`. Changes to `interface.py` need review from *both* lanes.

## Consequences

- Easier: game tests run with a `FakeSceneSource` (no camera, no projector, CI-friendly), the vision lane can rewrite detection freely, and a later network bridge just serialises `Scene`.
- Harder: an interface change is a two-person decision.
- We're now committed to: no `import cv2` under `src/lorikeet/games/` (enforce with a test once games exist).
