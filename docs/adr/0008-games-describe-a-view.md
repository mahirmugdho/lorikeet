# 0008. Games describe a View; the renderer a player picks draws it

- **Status:** Accepted, 2026-11-27. Ryan approved #9.
- **Date:** 2026-11-26
- **Deciders:** Ryan, Mahir

## Context

Games will be drawn more than one way, and players should be able to pick: a flat look in pygame-ce first, then a clay look in a 3D engine. The launcher in PR #8 hands each game a pygame surface to draw on (`draw(canvas)`), which builds pygame into every game. A window belongs to one graphics library at a time. The desk's sketched notes and the debug overlay have to look the same whichever renderer runs.

## Options considered

1. **Games draw themselves** (`draw(canvas)`, as in PR #8). It's the simplest option, but every game is tied to pygame, and a new renderer means rewriting every game.
2. **Renderers read each game's own state.** No shared format is needed. But each renderer is written for one game and depends on its internals, so every new game needs every renderer rewritten for it.
3. **Games describe a `View` in a shared format, kept in `interface.py`.** All contracts stay in one file, with no new import rule. But it mixes two contracts with different readers, and the format will change often while renderers are built, landing in the file that's meant to stay stable.
4. **The same `View`, in its own `lorikeet/view.py`.** Each file holds one contract: `interface.py` is what's on the wall, and `view.py` is what to draw. Renderers never see `Piece` or `Scene`. The cost is one more allowed import in the boundary test.

## Decision

We will go with option 4.

- **What a game returns.** Each frame, a game returns a `View`: a tuple of things.
  - Each thing has a stable `id`, a `kind` ("terrain", "egg", "bird", "goal", "note", and so on), and a `shape`: a circle, or a polygon whose points are relative to `position`, before `angle` turns it.
  - It also has a `position` and `angle` in projector pixels (radians, clockwise on screen), a `layer` (back to front), and an optional `pose` hint ("hop", "cracked").
  - The id lets a renderer build a mesh once and then only move it.
  - Kinds are plain strings, like colour names, so a game can add one without touching `view.py`. A renderer draws a kind it doesn't know in a plain default.
- **Imports.** `view.py` imports only the standard library, plus `Point` and `Polygon` from `interface.py`. Games may import `lorikeet.interface` and `lorikeet.view` and nothing else from Lorikeet. Renderers import `lorikeet.view` and never a game. `tests/test_boundaries.py` checks both rules.
- **The game contract.** A game is `update(scene, dt)` plus `view() -> View`. It never draws, and it never sees input or output.
- **Renderers.** Renderers live in `lorikeet/render/`. The launcher picks one (`--renderer flat`, and others later) and tells it the output (window or projector). The renderer owns the window: it draws the `View`, multiplies it by the wall layer, lays the overlay layer on top unchanged, and passes input events back to the launcher.
- **Overlays.** Overlays (the desk, the debug overlay) hand the renderer two layers in projector pixels:
  - **The wall layer** is what's physically on the wall: white where it's bare, paper where the desk's notes are. Projected light lands on whatever it hits, so renderers multiply their frame by this layer. On the desk, the game's picture then lands on the paper notes just as it does on the real wall: an egg passing through a zone note shows on the note. With the camera, the real paper is on the real wall, and this layer stays white.
  - **The overlay layer** is what's in front of the wall, such as the desk's palette, the note in your hand, and the debug overlay. It's transparent and premultiplied, and renderers lay it on top without looking inside it.
  - Because renderers never look inside either layer, the desk looks the same under every renderer.

## Consequences

- Easier: one game runs under any renderer. Renderers are tested on hand-built `View`s, and games are tested without any drawing.
- Easier: a new renderer is one module, and it can draw every game.
- Harder: everything a game shows has to fit the format. Text or particles mean extending `view.py`.
- Harder: under a renderer that isn't pygame, both layers have to be copied to the graphics card whenever they change. Overlays take pygame input events, so that renderer must translate its own input into them.
- We're now committed to: games never draw; renderers never import games or change overlays; everything after the game stays in projector pixels (ADR 0005).
- Choosing the clay renderer's engine is a separate ADR, because it adds a dependency that ADR 0002 doesn't cover.
