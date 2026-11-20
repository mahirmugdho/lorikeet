# 0007. Camera frames stay in memory on this machine

- **Status:** Proposed
- **Date:** 2026-11-20
- **Deciders:** Ryan, Mahir

## Context

Lorikeet points a webcam at a room, often at demos full of people who never agreed to be recorded. A frame is an image of whoever is standing there. Debugging CV makes it tempting to dump frames to disk, attach them to issues, or commit them as fixtures, and this repo is public.

## Options considered

1. **Frames live only in memory by default.** Saving frames is an explicit opt-in (`LORIKEET_DEBUG_SAVE_FRAMES=1`), goes to gitignored `.lorikeet/debug-frames/`, and shows an on-projector "recording" badge while on. Nothing is sent over the network. Fixtures are cropped or staged with no people. Cons: debugging needs a deliberate step.
2. **Save frames freely and clean up later.** Easier debugging. Cons: images of people end up in commits, issues, and screenshots, and git history is forever.

## Decision

We will keep **camera frames in memory and on this machine**. Only derived data (note polygons, ids, colours) leaves the vision lane. Any frame persistence is opt-in, visible, local, and gitignored. Test fixtures and screenshots in the repo contain no people. Details and rationale: `docs/legal/privacy.md`, `docs/security/threat-model.md`.

## Consequences

- Easier: demos are safe by default, and there's no personal data to protect, delete, or disclose.
- Harder: reproducing a detection bug means re-staging it or turning on the debug flag.
- We're now committed to: reviewing any new file write, log line, or network call in the vision lane against `docs/security/checklist.md`.
