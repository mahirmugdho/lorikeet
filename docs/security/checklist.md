# Security & privacy checklist

Walk this when a change touches **camera capture, frame handling, files, logging, the network, dependencies, or anything drawn on the projector**. `/ship` step 4 points here. Reference: [threat-model.md](threat-model.md).

## Camera frames (T1, T3, T5)

- [ ] Frames stay in memory. No new `cv2.imwrite`, `np.save`, image logging, or temp files, unless gated by `LORIKEET_DEBUG_SAVE_FRAMES=1` and written under `.lorikeet/`
- [ ] Only derived data (polygons, ids, colours) leaves the vision lane
- [ ] No new network call anywhere in the vision lane
- [ ] The camera is released on every exit path (normal quit, exception, Ctrl-C)

## The repo (T2)

- [ ] New fixture images, screenshots, and GIFs contain no people (faces, hands, reflections)
- [ ] No frames pasted into issues, PR comments, or Claude sessions

## Dependencies (T4)

- [ ] Any new dependency is named and justified in the PR body
- [ ] `uv.lock` updated and committed; `make check` passes with `uv sync --locked`

## Projected output (T6)

- [ ] Nothing flashes full-screen more than 3 times a second
- [ ] Calibration patterns are static

## Files we read (T7)

- [ ] Calibration and config files are JSON or `.env`, validated on load. No `pickle`, no `allow_pickle=True`
