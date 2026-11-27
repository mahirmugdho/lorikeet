# Architecture Decision Records

An ADR is a short note recording one decision: the context, the options, what we picked, and what it costs us. Six months from now, "why is it like this?" has an answer, for humans and for Claude.

**Rules**

- New ADR: use the `/new-adr` Claude skill, or copy `0000-template.md`.
- Starts `Proposed`. Becomes `Accepted` when the *other* teammate approves the PR that adds it.
- Accepted ADRs are never edited. To change course, write a new ADR that supersedes the old one.
- Write one when a choice is expensive to reverse: a service, a data shape, a security boundary, a rule the whole codebase follows.

| #                                               | Decision                                                            | Status                       |
| ----------------------------------------------- | ------------------------------------------------------------------- | ---------------------------- |
| [0001](0001-record-architecture-decisions.md)   | Record architecture decisions                                       | Accepted                     |
| [0002](0002-python-desktop-stack.md)            | One local Python process: OpenCV + pygame-ce + pymunk               | Accepted                     |
| [0003](0003-license.md)                         | Choose a license: MIT                                               | Accepted                     |
| [0004](0004-games-see-only-the-interface.md)    | Games see only the interface: a Scene of pieces                     | Accepted                     |
| [0005](0005-projector-space-coordinates.md)     | Projector pixels are the only game coordinates; ArUco calibration   | Proposed                     |
| [0006](0006-classical-color-detection.md)       | Detect notes with HSV colour segmentation, not ML                   | Proposed                     |
| [0007](0007-camera-frames-stay-local.md)        | Camera frames stay in memory on this machine                        | Proposed                     |
| [0008](0008-games-describe-a-view.md)           | Games describe a View; the renderer a player picks draws it         | Accepted                     |
