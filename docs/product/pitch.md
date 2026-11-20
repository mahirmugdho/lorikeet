# Lorikeet: pitch

Source idea, verbatim: [idea.md](idea.md).

## Problem

Video games live behind glass. Even "physical" games mean a controller, a phone, or a body-tracking camera that reads you, not the world around you. There's no easy way to make a wall or a table *be* the game, where moving a real object changes the level.

## Who it's for

- **Players** in a shared space (a living room, a club night, a classroom demo) who want a game they can touch and rearrange together.
- **Game makers** who want physical input without building computer vision: write a game against Lorikeet's interface and get sticky notes as bodies or selections for free.

## Core loop (v1)

1. Mount a webcam so it sees the whole projected area. Plug the projector in as an extended display. Run Lorikeet.
2. **Calibrate:** the projector shows four ArUco markers. Lorikeet finds them in the camera image and saves the camera→projector homography.
3. Players stick Post-its on the surface.
4. Each frame, Lorikeet finds every note (HSV colour + contours), converts it to projector pixels, and tracks it with a stable id.
5. The game receives a `Scene` through one of two modes:
   - **Bodies:** each note is a static rigid shape (pymunk). *Puzzle:* draw ramps and walls with notes to guide a ball to the goal.
   - **Selections:** a note settling on a grid cell is a `placed` event, like a click. *Tower defense:* place a note on a cell to build a tower there; peel it off to sell it.
6. The game draws onto the projection, right on and around the notes. Players move notes, and the game reacts.

## v1 scope

- Calibration with projected ArUco markers, saved per room
- Note detection for four configurable colours, in projector coordinates
- Tracking: stable ids, debounce for hands passing over notes
- The interface (`Note`, `Scene`, `SceneSource`) with both modes, plus a fake source for tests
- Debug overlay: outlines projected on every detected note, plus a colour-tuning view
- Two original demo games: a physics puzzle (bodies) and a tower defense (selections)

## Non-goals (v1)

- Hand, finger, or body tracking
- Recognising arbitrary objects (ML models), or depth cameras
- Multiple projectors or cameras, curved surfaces
- A network bridge for Godot, Unity, or web games (the interface keeps this possible later, ADR 0004)
- Online multiplayer, accounts, leaderboards, installers, app stores
- Recording or streaming gameplay video

## Risks

| Risk | Why it bites | Plan |
| --- | --- | --- |
| Projected light tints notes | The game draws on the notes it's detecting, so colours shift frame to frame | Keep the area under notes dark; threshold on saturation; debounce (ADR 0006) |
| Webcam auto-exposure drift | Brightness changes with the projected image, so thresholds wander | Lock exposure where supported; per-room tuning view |
| Latency | Camera (~33 ms) + CV + physics + projector lag adds up; over ~150 ms feels mushy | Measure end-to-end in Phase 1; profile before optimising |
| Hands occlude notes | A note vanishes while someone reaches past it | Note removal waits `LORIKEET_STABLE_FRAMES` |
| Demo-room lighting | Bright rooms wash out projection *and* detection | Test in a dim room first; document the ideal setup in `docs/setup.md` |
| Photosensitivity | Fullscreen flashes (calibration, effects) can trigger seizures | Hard rule: no more than 3 flashes/second (threat model T6) |
| Camera privacy | Frames capture bystanders | Frames stay in memory; opt-in local debug only (ADR 0007) |

## Open questions

Mahir decides:

1. **Stack.** Python + OpenCV + pygame-ce + pymunk (ADR 0002) or something else? The scaffold uses Python, but only `geometry.py` and tooling depend on it, so swapping now is cheap.
2. **Purpose and license.** Portfolio (MIT), class project (no LICENSE), or product (proprietary)? ADR 0003.

Claude's calls, to confirm:

3. **Lanes.** Ryan owns vision (camera → notes), Mahir owns games (notes → play), and both own the interface. `docs/workflow.md`
4. **Calibration by projected ArUco markers** rather than clicking corners by hand. ADR 0005
5. **Selections semantics.** A note that settles on a cell is `placed`; moving it is `moved`; removing it is `removed`. There's no "hover". ADR 0004
6. **Camera feed treated as personal data**, which gives us a threat model, a privacy doc, and no people in fixtures. ADR 0007
7. **Surface-agnostic.** Wall or table both work. The puzzle's gravity points toward the projector's bottom edge.
8. **v1 scope and non-goals** as listed above, including no network bridge in v1.
