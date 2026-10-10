# Workstreams

Parallel lines of work, one notes file each. `STATUS.md` (repo root) is the common
status document and links here; it is updated by the orchestrator after each round of
work. Each workstream's agent owns its own file and keeps it current, so any later session
can pick the work up from it.

Every file follows the same outline:

* **Goal**: what the workstream delivers.
* **State**: done / in progress / blocked, with the date.
* **Done**: what was built or found, with file paths.
* **How to test / reproduce**: commands, saved states, inputs.
* **Open issues** and **Next steps**.

Rules: English only. No ROM-derived data (no Japanese text, no extracted graphics or
bytes), since these files are part of the repository. Machine-local artefacts (text logs,
save states, screenshots) live under `build/` or a scratch folder and are referenced by
path only.

| Workstream | File |
|---|---|
| Standalone Windows player | `player.md` |
| Patch distribution (BPS) | `patch-distribution.md` |
| Emulation core: saves, BIOS, harness options | `core.md` |
| Release package | `release.md` |
| Short names for fixed-width fields | `short-names.md` |
| Text coverage by play-testing, round 1 (per area) | `explore-<area>.md` |
| Text coverage by play-testing, round 2 (per area) | `explore2-<area>.md` |
| Graphics pipeline: design, library, build integration, verification | `gfx-pipeline.md` |
| Graphics fonts (`title16`) | `gfx-fonts.md` |
| Graphics survey (every graphic the game loads) | `gfx-survey.md` |
| Pre-drawn Japanese graphics (per target) | `gfx-<target>.md` |
