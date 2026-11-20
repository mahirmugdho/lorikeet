# Security Policy

## Reporting a vulnerability

Please **don't open a public issue** for security problems.

Report privately through GitHub: **Security tab → Report a vulnerability** on this repository. If that's unavailable, contact the maintainers listed in the README.

Include what you found, how to reproduce it, and what an attacker could do with it. We'll acknowledge within 72 hours and keep you updated until it's fixed.

## What's in scope

- Camera frames being saved, logged, or sent off the machine without the user explicitly turning that on
- Images of people ending up in the repository (test fixtures, screenshots, debug dumps)
- A local network bridge (planned after v1) that other machines on the network can reach
- Projected content that flashes fast enough to be a photosensitivity risk (more than 3 full-screen flashes per second)
- Leaked secrets, auth bypasses, XSS, injection

## Out of scope

- Denial-of-service and volumetric attacks
- Findings that need a compromised device or browser extension

## Supported versions

Only the latest `main` (and its production deployment, if any) is supported.
