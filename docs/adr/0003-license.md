# 0003. Choose a license

- **Status:** Accepted, 2026-11-21. Mahir chose MIT.
- **Date:** 2026-11-20
- **Deciders:** Ryan, Mahir

## Context

The repository is public on Mahir's account and has no LICENSE file. With no license, default copyright applies: people can read the code but not legally reuse it. The right answer depends on what Lorikeet is for, which hasn't been settled.

## Options considered

1. **MIT (portfolio or side project).** Anyone can reuse it with attribution, which suits a public portfolio piece or hackathon project. Cons: anyone can also commercialise it.
2. **No LICENSE file (class project).** Course rules usually govern code written for a class, and some courses forbid open-licensing coursework. Cons: the public repo stays "look, don't reuse".
3. **Proprietary, "All rights reserved" (product or startup).** `Copyright (c) 2026 Ryan and Mahir. All rights reserved.` plus "No use, copying, or distribution without written permission." Cons: a public repo with a proprietary license is unusual; making the repo private would be more consistent.

## Decision

We will license Lorikeet under **MIT**. The scaffold PR, which accepts this ADR, adds the `LICENSE` file and updates the README's License section.

## Consequences

- Easier (MIT): reuse in portfolios and talks, outside contributions.
- Harder (MIT): changing to proprietary later doesn't claw back copies already released under MIT.
- We're now committed to: not adding third-party code or assets with incompatible licenses (check before copying sprites, sounds, or sample code).
