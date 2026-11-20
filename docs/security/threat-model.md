# Threat model

Lorikeet is a local desktop app with a camera pointed at a room. There are no accounts, no server, and no money. The real risks are **images of people leaking**, **players getting hurt by projected content**, and **untrusted code running with camera access**.

## Assets

| # | Asset | Why it matters |
| --- | --- | --- |
| A1 | Live camera frames | Images of whoever is in the room, often bystanders at demos |
| A2 | Saved debug frames (opt-in) | Same as A1, but persistent on disk |
| A3 | The public repo and its history | Anything committed is public and effectively permanent |
| A4 | Calibration file | Low sensitivity, but it's parsed at startup |
| A5 | Players' and bystanders' wellbeing | A bright projector can flash at people |
| A6 | The laptop | Runs our code and every dependency with camera access |

## Actors

- **Players and bystanders:** the people in frame. Not attackers, but their images are what we protect.
- **Us, the developers:** the most likely source of a leak, through a debug dump, a fixture, or a screenshot.
- **A compromised dependency:** a PyPI package that runs inside our process with camera access.
- **Someone on the same network:** relevant only once a network bridge exists (post-v1).
- **Anyone reading the public repo.**

## Threats

| # | Threat | Mitigation |
| --- | --- | --- |
| T1 | Frames saved to disk by default, or a debug flag left on, piles up images of people | Saving is opt-in (`LORIKEET_DEBUG_SAVE_FRAMES=1`), goes only to gitignored `.lorikeet/debug-frames/`, and shows an on-projector "REC" badge while on (ADR 0007) |
| T2 | Images with people committed: fixtures, screenshots, README GIFs, issue attachments | Fixture rule (no people), PR template checkbox, review; if it happens, rewrite history before anyone forks, and assume it's already copied |
| T3 | Frames leave the machine: telemetry, a crash reporter attaching frames, or a future network bridge | No network calls in the vision lane; no crash reporting that captures frames; a post-v1 bridge serialises `Scene` only (never frames) and binds to `127.0.0.1` |
| T4 | Supply-chain compromise: a dependency gains camera and file access | `uv.lock` pinned and committed, CI `--locked`, Dependabot, few dependencies, and every new one gets a line in its PR explaining why |
| T5 | Camera keeps running after the game exits or crashes | Exactly one owner of `VideoCapture`, released in a `try/finally` or context manager; the camera light is the user's check |
| T6 | Projected content triggers photosensitive seizures | **No more than 3 full-screen flashes per second** (WCAG 2.3.1 general flash threshold); calibration markers are static; avoid saturated-red flashing; effects fade instead of strobing |
| T7 | A crafted calibration file runs code when loaded | Calibration is JSON parsed into a 3×3 float array and validated; never `pickle` or `np.load(allow_pickle=True)` |

## Out of scope (v1)

Physical theft of the laptop, malware already on the machine, and attacks on the projector or webcam firmware.
