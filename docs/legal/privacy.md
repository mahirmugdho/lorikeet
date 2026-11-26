# Privacy: the camera sees people

> **Draft. Not legal advice.**

Lorikeet's webcam points at a play surface, and anyone standing near it is in frame. A frame showing a person is that person's image. We don't need images of people for anything, so we don't keep them.

## What Lorikeet keeps

| Data | Kept? | Where |
| --- | --- | --- |
| Live camera frames | **No.** Processed in memory, then discarded | — |
| Piece outlines, ids, colours | Only while the app runs | Memory |
| Calibration (a 3×3 matrix) | Yes | `.lorikeet/calibration.json` (gitignored) |
| Debug frames | **Only if you set `LORIKEET_DEBUG_SAVE_FRAMES=1`**, with a REC badge on the projection while it's on | `.lorikeet/debug-frames/` (gitignored, local) |

Nothing is sent over the network (ADR 0007).

## Rules

1. **No people in anything we commit or post**: test fixtures, screenshots, README media, issue attachments. Crop, stage the shot, or use a prop.
2. **Debug saving is a deliberate, temporary act.** Turn it on, reproduce the bug, turn it off, and delete the frames once you've fixed it.
3. **At demos, people should know there's a camera.** A small sign is enough: "This game uses a camera to see sticky notes. Nothing is recorded."
4. **Filming a demo for the README or a portfolio is a separate recording**, not Lorikeet's camera. Get permission from anyone identifiable in it. For anyone under 18, get a parent or guardian's OK, or keep them out of frame.
5. **Never paste frames with people into Claude, an issue, or a chat.**

## If this changes

Recording gameplay, streaming, sharing over the network, or any cloud feature changes the picture: frames would become stored or transmitted personal data. Write an ADR superseding 0007 and update this doc *before* building it.
