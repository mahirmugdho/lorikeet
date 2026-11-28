---
name: new-adr
description: Create a new Architecture Decision Record in docs/adr. Use when the user says /new-adr, "write an ADR", "record this decision", or when a change picks a library, service, data shape, or pattern that future work will depend on.
---

# New ADR

1. List `docs/adr/` and take the next number (4 digits, zero-padded).
2. Ask (or infer from the conversation) the decision in one sentence. If you can't state it in one sentence, it's two ADRs.
3. Copy `docs/adr/0000-template.md` to `docs/adr/NNNN-short-kebab-title.md` and fill every section:
   - **Context**: the forces at play, in plain language. Link the issue/PR.
   - **Options considered**: at least two real options, with honest pros and cons.
   - **Decision**: what we chose and why it beat the others.
   - **Consequences**: what gets easier, what gets harder, what we're now committed to.
4. Status is `Accepted`, with the date. The other teammate approving the PR that adds the ADR is what accepts it, so nobody opens a second PR to flip the status. If they request changes, edit the ADR on the same PR.
5. If this replaces an older ADR: set the old one's status to `Superseded by NNNN` (the only edit ever allowed to an accepted ADR) and link back from the new one.
6. Add a row to the index in `docs/adr/README.md`.
7. Keep it under one screen. An ADR records a decision; it isn't a design doc.
