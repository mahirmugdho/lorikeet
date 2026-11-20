# Contributing

Lorikeet is built by Ryan (@RyanS2025) and Mahir (@mahirmugdho).

## Get set up

Follow [docs/setup.md](docs/setup.md). In short: `brew install uv`, clone into `~/code/`, `make setup`, `make check`.

## Make a change

The full loop is in [docs/workflow.md](docs/workflow.md):

1. Pick or open an issue and check `gh pr list` for overlap.
2. Branch: `feat/…`, `fix/…`, `docs/…`.
3. Write tests first for logic; try hardware changes on the real projector + webcam.
4. `make check` green.
5. `/ship` (or open the PR yourself with the template filled).
6. The other teammate reviews; it squash-merges when `Check` passes.

## House rules

- The non-negotiables in [CLAUDE.md](CLAUDE.md) apply to humans too: games see only the interface, projector coordinates only, frames stay local, no people in committed images, no fast flashing.
- PR titles are Conventional Commits: `feat(detection): …`. CI checks this.
- Decisions that are expensive to reverse get an ADR in [docs/adr/](docs/adr/README.md).
- Security issues: see [.github/SECURITY.md](.github/SECURITY.md). Don't open public issues for them.
