## What & why

<!-- One or two sentences. What changes, and why now? Link the issue: Closes #123 -->

## How

<!-- The approach, and anything a reviewer would otherwise have to reverse-engineer. -->

## How I verified it

<!-- Real evidence, not "should work". Paste test output, screenshots, a preview link + what you clicked. -->

- [ ] `make check` passes locally
- [ ] Touches capture, calibration, detection, or a game? Tried it on the real projector + webcam, with a photo or clip attached

## Checklist

- [ ] One concern per PR; diff is reviewable in ~15 minutes
- [ ] Tests added/updated for new behavior
- [ ] Bug fix? A regression test reproduces the bug and now passes
- [ ] Docs updated if behavior, setup, or commands changed (`README`, `CLAUDE.md`, `docs/`)
- [ ] New architectural decision? ADR added in `docs/adr/` as `Accepted` (approving this PR accepts it)
- [ ] Roadmap box ticked only if the work is demonstrated

### Security & privacy (camera code, fixtures, anything projected)

- [ ] Camera frames stay in memory on this machine; nothing new saves or sends them (`docs/security/checklist.md`)
- [ ] New fixture images or screenshots contain no people
- [ ] Nothing new flashes full-screen more than 3 times a second

## AI assistance

<!-- What did Claude write vs. you? Anything you're unsure it got right? This helps the reviewer focus. -->

## Notes for the reviewer

<!-- Where to look hardest. Anything you want a second opinion on. -->
