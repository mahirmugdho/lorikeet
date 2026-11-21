# 0001. Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-11-20
- **Deciders:** Ryan, Mahir

## Context

Ryan and Mahir are building this with Claude, often across many sessions. Decisions made in a chat or a call disappear, and Claude starts every session without memory of them. We need a place where "why did we do it this way?" has a durable answer that both humans and Claude read.

## Options considered

1. **ADRs in the repo**: versioned with the code, reviewed in PRs, readable by Claude. Costs a few minutes per decision.
2. **Notion / Google Doc**: easy to edit, but drifts from the code and Claude can't see it by default.
3. **Nothing**: fastest now, most expensive later.

## Decision

We keep lightweight ADRs in `docs/adr/`, one decision per file, following `0000-template.md`. `CLAUDE.md` tells Claude to read them before changing anything they cover.

## Consequences

- Easier: onboarding, settling repeat debates, keeping Claude consistent across sessions.
- Harder: a small writing tax on big decisions.
- Committed to: never editing accepted ADRs; superseding instead.
