# Lorikeet: Projector + CV for physical interaction with games

**Turns a projector, a webcam, and sticky notes into physical play surfaces for games.**

> This README describes the target. [ROADMAP](docs/ROADMAP.md) tracks what's real. Today that's Phase 0: the scaffold, plus the camera-to-projector geometry and its tests.

## What and why

Lorikeet is an application that creates an interface to use projectors as a way to create physical play surfaces for video games. **This is done through a video feed that is processed with computer vision libraries and then output as shapes and objects that can then be used as various inputs for games and other applications.** With Lorikeet, our games include ones where Post-it notes are hard-bodied surfaces for a puzzle game, and one where Post-it notes are the inputs for a tower-defense game.

Lorikeet's interface has two modes:

1. **Bodies:** inputs are hard-bodied objects in a space. Games that need physics (platformers, puzzles) use the notes as their environment.
2. **Selections:** inputs are selections within a space. Players treat the projection like a giant trackpad, and each note acts like a mouse selection or key press. Good for strategy, planning, and tower-defense games.

How it works: the projector shows four markers, and the webcam finds them to learn how its view maps onto the projection. After that, every sticky note the camera sees becomes a shape in projector coordinates, and the game draws right on top of it.

## Quickstart

These are the commands that work today:

```bash
brew install uv                    # once: Python toolchain
git clone https://github.com/mahirmugdho/lorikeet.git ~/code/lorikeet
cd ~/code/lorikeet
make setup                         # Python 3.13 + dependencies into .venv
make check                         # format, lint, types, tests
```

Running the projector app arrives in Phase 1. Full machine setup is in [docs/setup.md](docs/setup.md), and hardware is in [docs/BUY.md](docs/BUY.md).

## Stack

Decided in [ADR 0002](docs/adr/0002-python-desktop-stack.md). Python 3.13 with uv, plus:

- NumPy for the geometry
- OpenCV (headless) for capture, ArUco calibration, and colour detection
- pygame-ce for the fullscreen projector window
- pymunk for 2D physics
- pytest, ruff, and pyright for testing and linting

Everything runs on one laptop: no server, no accounts, and camera frames never leave the machine ([ADR 0007](docs/adr/0007-camera-frames-stay-local.md)).

## Layout

```
src/lorikeet/    the app: geometry, capture, calibration, detection, tracking, interface, games/
tests/           pytest
docs/            pitch, roadmap, ADRs, setup, workflow, testing, security, legal, parts list
.github/         CI, PR and issue templates, Dependabot, branch ruleset
CLAUDE.md        how Claude (and humans) work in this repo
```

## Team

Ryan ([@RyanS2025](https://github.com/RyanS2025)) and Mahir ([@mahirmugdho](https://github.com/mahirmugdho)). See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). See [ADR 0003](docs/adr/0003-license.md).
