# Workstream notes

These are the detailed working notes from development. Each line of work (a
"workstream") kept its own file while it ran. A file describes the state at
its last update, so some of its open items may have been finished since.
[STATUS.md](../../STATUS.md) has the current state and
[docs/history.md](../history.md) the order of events.

Each file follows the same outline: the goal, the state with its date, what
was done (with file paths), how to test or reproduce it, open issues, and next
steps. The notes follow the repository's rules: English only, and no data from
the game (no Japanese text, no extracted graphics or bytes). Machine-local
material such as text logs, save states and screenshots lives under `build/`
or a scratch folder, and the notes refer to it by path only.

## Engineering

| Notes | Scope | Final state |
|---|---|---|
| [player.md](player.md) | Windows player: window, keyboard and gamepad, audio, saves, save states, the patch applied at load, opening a `.zip`, menus | Done; checked end to end by `release_test.py` |
| [patch-distribution.md](patch-distribution.md) | Making and applying the BPS patch with no data from the game inside; release checks | Done; the audit passes |
| [core.md](core.md) | Emulator core: the BIOS chip size code, flash command emulation in the core and the harness, harness options such as `--poke` | Done 2026-10-09, reviewed |
| [release.md](release.md) | `VERSION`, the icon and version resource, the package zip, the web patcher | Done; the manual checks (steps 6 to 8) are left to the owner |
| [short-names.md](short-names.md) | Copy tables (`sites=`) for fixed-width fields: 8-letter character names, short item and class names | Done 2026-10-09; checked in play (see its check table) |

The save-safe ROM layout has no notes file of its own; see "Save-safe layout"
in [docs/history.md](../history.md) and `tools/patch/layout.py`.

## Play-testing

Round 1 covered one area of the game per file. Its findings were merged into
one plan and applied on 2026-10-09.

| Notes | Area |
|---|---|
| [explore-organize.md](explore-organize.md) | HQ and organize screens: units, characters, status, class change, equipment |
| [explore-map.md](explore-map.md) | Stage map play: moving units, liberating towns, hidden places, treasure, encounters |
| [explore-battle.md](explore-battle.md) | Battles: battle screens, tactics, results, level-ups |
| [explore-towns.md](explore-towns.md) | Shops, churches, the Items and Tarot commands, stock prompts |
| [explore-data.md](explore-data.md) | Save, load, continue and suspend; Monitor settings; title; game over |
| [explore-progress.md](explore-progress.md) | Story progression: stages 0 to 2 cleared; with testing aids, every stage's story card and opening, the five endings and the staff roll |

Round 2 went deeper. Its plan was applied on 2026-10-10.

| Notes | Area |
|---|---|
| [explore2-story-early.md](explore2-story-early.md) | Story stages 2 to 6 |
| [explore2-story-late.md](explore2-story-late.md) | Stages 7 to 17, the endings, the staff roll and game over |
| [explore2-systems.md](explore2-systems.md) | Shops, churches, recruiting, class change, items, tarot, persuasion, link menus |
| [explore2-battle.md](explore2-battle.md) | Battles in depth |

## Graphics with Japanese lettering

| Notes | Scope | Final state |
|---|---|---|
| [gfx-pipeline.md](gfx-pipeline.md) | One pipeline for every pre-drawn graphic: fonts, renderer, tiles, build integration, checks | Done 2026-10-10; all five targets are in the full build |
| [gfx-survey.md](gfx-survey.md) | Inventory of every graphic the game loads (`tools/gfx/inventory.py`) | Done: 834 blocks, two more visible targets found (the tags); an unused ending epilogue and an unused prose screen are never shown |
| [gfx-fonts.md](gfx-fonts.md) | The `title16` display font (11 rows, 85 glyphs) | Done 2026-10-09, reviewed |
| [gfx-title-logo.md](gfx-title-logo.md) | Title logo, subtitle and the title screen's warning window | Done, accepted in review |
| [gfx-intro-narration.md](gfx-intro-narration.md) | The 15-line narration crawl of the intro | Done; the owner's review of the wording is open |
| [gfx-chapter-cards.md](gfx-chapter-cards.md) | Story and area title cards, chapters 1 to 20 (40 cards in 36 records) | Done, accepted in review |
| [gfx-labels.md](gfx-labels.md) | The 45 menu labels (64x8) under the icon bars; 44 redrawn, one already in English | Done, accepted in review |
| [gfx-tags.md](gfx-tags.md) | The "deployed" tag on the organize status pane and the paralysis label in battle | Done (FIELDED and STUN), accepted in review |
