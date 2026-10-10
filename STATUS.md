# Project status — Ogre Battle Gaiden: Prince of Zenobia (English)

_Last updated: 2026-10-10 (session 3: complete build, verified)_

This is the common status document. **To resume in a new session:** read this
file top to bottom, then the notes of the workstream you continue in
`docs/workstreams/`. Update the "Workstreams" table, "Where we left off" and the
checklists at every milestone. Parallel agents each keep their own
`docs/workstreams/<track>.md`; the orchestrator merges their results here after
each round.

## RESUME HERE (2026-10-10: complete build done)

**The English version is complete and verified.** No workflow is running.

* **Build:** `build/ogre_en.ngc` SHA-1 `4fe9c5ff...` (all text, all play-test
  fixes, short names, all replacement graphics; save-safe layout),
  `build/ogre_en.bps` (133,251 bytes, audit OK) + `.sha1`, `build/zenobia.exe`
  (Windows player: icon, version, flash saves) and `build/ngp_harness.exe`.
  From scratch: `build.bat`, then `python -m tools.patch.build rom/baserom.ngc`.
* **Package:** `dist/ogre-battle-gaiden-en-0.1.0-dev+4fe9c5ff-win64.zip`
  (313,994 bytes; SHA-256 `b5c184d9...`): `zenobia.exe`, `ogre_en.bps`,
  `ogre_en.sha1`, `README.txt`, `LICENSE.txt`, `THIRD_PARTY_NOTICES.txt` and a
  pure-Python `patch-tools/apply.py`. Rebuild: `python -m tools.release.package`.
* **Verified on this build:** `release_test.py` 40/40 from the unzipped
  package; `save_test.py` 27/27; the package's Python applier reproduces the
  ROM SHA-1; `tools.gfx.test_all` 7 modules (105 tests); `test_tables` 18/18;
  `test_bps` 11/11; `tools.text.check` 1,570 messages, each one page;
  localization database 5,139 strings, all translated. The final verification
  round (`obg-r3-final-verify`, 11 agents) swept every saved state (389) by
  eye, played power-on to stage 1 with save/load/suspend/continue in the
  harness and the player, and ran every suite: the only in-game defect (the
  "Save complete." bar spilling past its frame) is fixed, as are the release
  README, five A/B choices that wrapped to a third line, the NEXT window's UNIT
  tab (now proportional like CITY) and the packaged applier's `--help`.
* **Test states:** 35 states saved mid-dialogue with older builds crashed on
  the new one (their dialogue pointers moved), a test-asset problem, not a
  build defect. They were replaced by relocated copies (originals in
  `build/states/stale-e63bffd1/`). After any rebuild that moves dialogue
  pages, run `build/handoff/r3/stalescan.py` / `relocate.py` (or re-record the
  states). States also keep the video memory of the build they were saved
  with (e.g. `title_menu.state` still shows the old logo until the title is
  reloaded).

**What is left (owner):**
1. Manual release checks that cannot be automated here
   (`docs/workstreams/release.md`, checklist steps 6-8): apply `ogre_en.bps`
   with Floating IPS and ROM Patcher JS, run the package on a clean Windows
   10/11 PC, play the patched ROM in an established emulator. Then
   `python -m tools.release.package --release` for a public 0.1.0.
2. Decisions (provisional choices are built, each a one-line change): see
   "Provisional wording decisions" and "Open owner decisions" below.
3. Optional: a linguist review through the localization database
   (`docs/localization.md`); the label descender option; a harness check that
   refuses states from another ROM (ROM SHA-1 in `.state`, like the player's).
4. Housekeeping: the original ROM archive `Densetsu no Ogre Battle (Japan).zip`
   sits in the working folder's root (git-ignored by `*.zip`, never
   committed); moving it into `rom/` or out of the folder is safer.

**Ease of use (2026-10-10):** no command line needed. The player opens the
game as `.ngc` or straight from the `.zip` it came in (own zip/inflate reader,
`runtime/src/frontend/zipread.c`), and has a menu bar with File > Save English
ROM... (Ctrl+S) for other emulators. The package also holds `Patch your
game.html`: a one-file, offline web patcher (choose the game or its zip, click
"Save the English game"; works on any system; no network access allowed by
its CSP; `tools/release/webpatcher.py`, tested in Node and in Chrome). Both
READMEs start with a three-step quick start. Tests: `release_test.py` 41/41,
`zip_test.py` 59/59, `test_webpatcher` 2/2, `test_package` 33/33.

**Repository and sharing (2026-10-10):** private GitHub repository
`https://github.com/scienceandresearch/open-ogre-battle-gaiden-zenobia`
(branch `main`), with the pre-release `v0.1.0-dev` carrying the package zip.
Sharing model: "bring your own game" — the repository and the package hold
only original code, translation, fonts and lettering plus the audited BPS
patch; players supply their own cartridge dump. A fresh clone builds the
identical English ROM (`4fe9c5ff...`) and passes every test suite; `build.bat`
builds the player and harness from the clone. Line endings: `.gitattributes`
stores LF; Windows checkouts get CRLF, which every tool accepts. Share access
by inviting collaborators (repository settings) or, later, by making the
repository public after the manual release checks.

**Handoff artifacts** (machine-local, never committed): `build/handoff/` holds
the agents' briefing (`briefing.md`), every round's raw results
(`r1_*_result.json`, `r2_*.json`, `r3_final.json`), the Codex title drafts and
prompts (`codex-title/`), the play-test plan tools (`tplan/`), the finish and
final-verification workflow scripts (`finish/`), the stale-state tools
(`r3/`) and all workflow scripts (`workflow-scripts/`). The session scratchpad
of the session that built it (a Claude Code temporary folder on the
maintainer's machine, written `<scratch>` in the notes) holds all agent work
folders and snapshots; it is machine-local and may be cleaned.

**Open owner decisions** (provisional choices are built): title kicker "THE
LEGEND OF" (adopted because the original logo has it) and GAIDEN rather than
SIDE STORY; intro line 6 "is indeed a 'true king'..." (avoids "truly a true");
CC0 for the new `title16` font (MIT for now); whether to restore the unused
ending epilogue (87 lines the shipped game never shows; not planned);
labels: descender tails on row 7 (a compact option exists), 07 and 20 both
"Organize", 09 "Remove", 25/26 "chars"; cards: "Chapter N" / "Final
Chapter" / "White Night", shortened titles of chapters 3, 4, 12, 14; tags:
FIELDED vs ON MAP; original English art left as it is ("Congratulation!",
"NewGame", the "TAROT" frame header, "M-SHILD").

**History of the last rounds** (details in the session log and
`docs/workstreams/`): graphics wave 2 and text round 2 were stopped once by a
usage limit and finished with "finish" scripts that start each task at its
last finished step (resuming a parallel workflow by run id re-ran finished
agents; see `build/handoff/finish/`).

## Workstreams

Goal of the current rounds (started 2026-10-09): make the game easy to play on
a PC, fully in English. Workflows run in parallel; each workstream keeps its
notes file, and this table is updated when a workflow finishes.

| Workstream | Scope | Notes | State |
|---|---|---|---|
| Player | Windows standalone player: window, keyboard/gamepad, audio, saves, states, patch applied at load | `docs/workstreams/player.md` | round 1 done, end-to-end verified (`release_test.py` 40/40) |
| Patch distribution | BPS patch creation/apply with no ROM data inside; release checks | `docs/workstreams/patch-distribution.md` | round 1 done (audit OK, 113 KB) |
| Save safety | Keep patch data out of the game's save blocks | `tools/patch/layout.py`, this file | done 2026-10-09 (layout check in the build) |
| Core saves | BIOS chip size code, flash command emulation in the core/harness, harness `--poke` | `docs/workstreams/core.md` | done 2026-10-09 (reviewed; `save_test.py` 33/33) |
| Release package | `VERSION`, icon + version resource, `python -m tools.release.package` zip | `docs/workstreams/release.md` | done (review re-running): dev package `dist/ogre-battle-gaiden-en-0.1.0-dev+e63bffd1-win64.zip`; window icon still the stock one (3-line `gui.c` fix in release.md notes) |
| Graphics: build integration | `gfx-build`: target registry, `build/gfx/gfx.asm`, in-place RomPatch, `tools.gfx.apply`, VRAM/harness check tools | `docs/workstreams/gfx-pipeline.md` ("Build integration (as built)") | done 2026-10-09 (reviewed) |
| Explore: organize | HQ/organize screens: units, characters, status, class change, equipment | `docs/workstreams/explore-organize.md` | round 1 done, fixes applied |
| Explore: map | Stage map play: moving units, liberating towns, hidden places, treasure, encounters | `docs/workstreams/explore-map.md` | round 1 done, fixes applied |
| Explore: battle | Battles: battle screens, tactics, results, level-ups | `docs/workstreams/explore-battle.md` | round 1 done, fixes applied |
| Explore: towns | Shops, churches, Items and Tarot commands, stock prompts | `docs/workstreams/explore-towns.md` | round 1 done, fixes applied |
| Explore: data | Save/load/continue/suspend, Monitor settings, title, game over | `docs/workstreams/explore-data.md` | round 1 done, fixes applied (saving still untested in the harness) |
| Explore: progress | Story progression: stages 0-2 cleared, every chapter card reached | `docs/workstreams/explore-progress.md` | round 1 done |
| Short names | Copy tables (`sites=`) for fixed fields; 8-letter character names, short item and class names | `docs/workstreams/short-names.md` | done 2026-10-10 (verified in 40 scenarios) |
| Explore round 2 | Story stages 2-6; stages 7-17, endings, staff roll, game over; systems (shops, churches, recruiting, class change, items, tarot, persuade, link menus); battles in depth; then one verified plan | `docs/workstreams/explore2-*.md` | done 2026-10-10; plan applied |
| Graphics: pipeline | One pipeline for all pre-drawn Japanese: fonts, renderer, tiles, build integration, checks | `docs/workstreams/gfx-pipeline.md` | done 2026-10-10: all five targets enabled in the full build (gfx-verify) |
| Graphics: title logo | Main title, subtitle and the title-screen warning window (Codex drafts as style reference) | `docs/workstreams/gfx-title-logo.md` | done (accepted after 2 reviews) |
| Graphics: intro narration | Pre-rendered 15-line narration crawl | `docs/workstreams/gfx-intro-narration.md` | done (accepted) |
| Graphics: chapter cards | Story and area title cards, chapters 1-20 | `docs/workstreams/gfx-chapter-cards.md` | done (accepted after 2 reviews) |
| Graphics: labels | 45 pre-drawn 64x8 menu labels under icon bars | `docs/workstreams/gfx-labels.md` | done (accepted after 2 reviews) |
| Graphics: tags | "Deployed" tag (organize status pane) and "paralysed" battle label | `docs/workstreams/gfx-tags.md` | done (FIELDED, STUN; accepted after 2 reviews) |
| Graphics: fonts | `assets/font/title16.txt` (11-row display font, 85 glyphs) | `docs/workstreams/gfx-fonts.md` | done 2026-10-09 (reviewed) |
| Graphics: survey | Static inventory of every graphic the game loads (`tools/gfx/inventory.py`) | `docs/workstreams/gfx-survey.md` | done: 834 blocks; only 2 new visible Japanese targets (tags); unused ending epilogue (87 lines) and an unused prose screen not shown by the game |

Round 2 graphics plan (`gfx-pipeline.md` section 8): wave 1 = `gfx-lib`
(`tools/gfx/` library), `gfx-font16`, `gfx-survey` (running since
2026-10-09); `gfx-build` (target registry, `build/gfx/gfx.asm`, in-place
`RomPatch`, `tools.gfx.apply`) starts once the save-safe layout is in; wave 2
= labels, intro, cards, title (one agent each, tested with `python -m
tools.gfx.apply` on a snapshot ROM); wave 3 = `gfx-verify` (full build, all
recipes).

## Goal and approach

* English version of *Densetsu no Ogre Battle Gaiden: Zenobia no Ouji*
  (Neo Geo Pocket Color, 2000), playable on modern PCs, open source, requiring
  the user's own ROM. No ROM-derived data (Japanese text, graphics, generated
  code) is ever committed.
* **Phase 1 (current): translation patch.** `tools/patch/build.py` produces an
  English ROM from the original; works in existing emulators and on hardware.
* **Phase 2: standalone build.** Our own runtime (`runtime/`, already used as
  the test harness) gets a Windows player (Win32, no external dependencies;
  SDL for other platforms later) that applies the patch at load time.
* Static recompilation (`tools/recomp/`) is optional and off the critical path.

## Where we left off

**Fixed 2026-10-09: patch data in the game's save blocks.** The game saves to
cartridge flash blocks 0x1B-0x1E = `0x3B0000`-`0x3EFFFF` (suspend, files 1-3;
slot table `0x29A66E`, `explore-data.md`). Earlier builds put UI text at
`0x3C0000` and tables at `0x3E0000`, so in-game saving (hardware, flash carts,
any emulator with flash emulation, our player) overwrote and eventually erased
them. Now `tools/patch/layout.py` declares the regions and the build refuses
any changed byte in the save blocks or outside a region, printing each
region's use:

| Range | Content | Used |
|---|---|---|
| `0x368000`-`0x36FFFF` | UI text and location names | 15.0 KB |
| `0x370000`-`0x377FFF` | patch code (`FREE_CODE`; `textfix.asm` routines at `+0x4000`) | 1.4 KB |
| `0x378000`-`0x37FFFF` | fonts, UI remap table (`FREE_DATA`) | 9.1 KB |
| `0x380000`-`0x39FFFF` | dialogue | 94.6 KB |
| `0x3A0000`-`0x3AFFFF` | replacement graphics (sub-regions in `gfx-pipeline.md` 4.1) | 0 |
| `0x3B0000`-`0x3EFFFF` | the game's save blocks: never written | — |
| `0x3F0000`-`0x3FFFFF` | rebuilt tables | 28.4 KB |

Verified: 16 harness scenarios (finance and town windows, status, organize
items/class change/equipment, unit window, liberation message, item found,
battle commands, Monitor, scenario map, stage 2 play) are pixel-identical
before and after the move; in the player, 19 saves to file 1 erase block 28
once and "Save complete." stays English. Old `.sav` files made with earlier
builds carry stale patch bytes: delete them. English ROM SHA-1 now
`272f13ab...`.

Also fixed (core, round 2): the HLE BIOS stored chip size code 1 at
`0x6C58`, so a full save block made the game erase block 15 (game data); the
core now stores the real codes (3 for this 2 MB cartridge) at reset and on
every state load. The flash-chip command emulation moved from the player into
the core, so the harness saves too (Save, Suspend, Continue; `--no-flash-commands`
restores the old behaviour); harness `--poke ADDR=HEX[,...][@FRAME]` and
`--dump-flash FILE` were added. `runtime/src/core/tests/save_test.py`: 33/33.

**Round 1 results (2026-10-09):**
* Engineering: `build\zenobia.exe` (Win32 player: GDI, waveOut, keyboard +
  XInput, `zenobia.ini`, 10 state slots, cartridge saves with flash-chip
  emulation, BPS applied in memory, `--selftest`, `--write-patched`) and
  `build/ogre_en.bps` + `.sha1` from every build (`tools/patch/bps.py`, audit:
  no literal of 8+ bytes found in the original; 113 KB). End-to-end check
  still running.
* Graphics: all four known targets located, decoded and prototyped in scratch
  ROMs with original placeholder art (title package in bank 0x28, uncompressed;
  15-line intro crawl; 36 chapter cards; 45 menu labels). One design for all:
  `docs/workstreams/gfx-pipeline.md` (text-only sources: fonts, English text
  files, optional text-art images; tiles generated at build time; 64 KB
  graphics region). New target found: the title-screen warning window
  ("suspend data will be erased"); the "deployed" tag on the stage organize
  panel goes to the survey.
* Play-testing (six areas, 200 new states in `build/states/`, text logs in
  `build/textlogs/`): consolidated into one verified plan, applied
  2026-10-09 (build `e63bffd1...`), checked again on the real build:
  * untranslated: Monitor help (5), link-battle day/night and order prompt,
    staff-roll title and (C) line;
  * crashes fixed: leader names of 11+ letters and item names of 10+ letters
    overran RAM from `0x6000` through 8-bit pad loops (white map, false
    "buried treasure"); clamps `name_top8` / `item_name10` in
    `patch/src/textfix.asm`;
  * VWF width lookup used a signed index: codes `0x80`+ (the blank glyph of
    `fill=`/`center`) had width 0, so padding and centring never worked
    (stage names, save bar); fixed in `patch/src/vwf.asm`;
  * the organize screen prints system messages and help with the fixed-cell
    printer (18 cells x 3 lines): 39 entries reworded, new `cells=N` check
    in `tools/text/uitext.py`; the printer now skips a leading VWF marker
    (class-change confirmation);
  * tarot and shop lists drawn variable-width (VWF marker at the start of the
    composed list); deploy list uses short move types (Shoal/Woods/Plain);
    stock bar back to the original lengths; save list separator "1.";
    Suspend prompt on 2 lines; save bar fully redrawn; "Unit: 1";
    link-battle items described as versus-battle items; l10n export now flags
    hiragana-only Japanese drawn from ROM;
  * still open, in round 2: names in 8-cell fields (107 long character names,
    32 class names, 157 item names; copy tables with `sites=`).
* Repository hygiene: `translation/en/glossary.md` now uses romanized source
  terms (no Japanese anywhere in the repository except the character table
  in `tools/text/charmap.py`); chapter 6's area is "Litt Island Waters"
  everywhere.

**Graphics rule (owner, 2026-10-09):** every replacement graphic must match
the original very closely, with only the targeted change (Japanese lettering
-> English): same position and size, the original palette colours (no palette
writes unless unavoidable), the same outline/glow/shading treatment and
texture, comparable letter weight and height; everything else stays
pixel-identical. Each target is reviewed side by side with the original
(local images only). Codex CLI image generation (`$imagegen`) may be used for
drafts and style references (the title logo first); final pixels go through
`tools/gfx` and are committed as text sources, never as ROM-derived images.

Provisional wording decisions (the owner may change them; each is one line
in a text file): intro in the 11-row `title16` font; title with every element
of the original translated: small "THE LEGEND OF", "OGRE BATTLE" (fire),
"GAIDEN" (white), subtitle "PRINCE OF ZENOBIA"; card headings "Chapter N" /
"Final Chapter", chapter 13 "White Night"; label 0x03 "Finances" (the window
is "Income & Expenses"); the church icon label 0x14 "Rite of revival" (the
Game System Tips line quotes it the same way); the staff roll opens with the
English title instead of the original's romanized one; status tags FIELDED (deployed unit; DEPLOYED
does not fit the original box) and STUN (paralysis); menu labels as in
`translation/en/labels.txt` (07 and 20 both "Organize"); fixed fields get
8-letter character names (only story name affected: "Dark Knight") and short
item/class names, full names everywhere else.


**Text coverage (localization database, `docs/localization.md`; export of
2026-10-09 after the round-1 fixes):** 4,634 strings: dialogue 1,570, UI 598,
named strings for code patches 52, table entries 2,199, locations 207 + 8
town-type phrases; **0 untranslated** among everything the scans and the
recorded runtime logs find (the export now also flags hiragana-only strings). The scans do not
find everything (strings behind pointer tables in data that the walker took
for code, values printed by `base + index * size`), so remaining gaps will
show up as more screens are visited: record harness text logs of the English
build into `build/textlogs/` (the export reads them and lists any Japanese
that was actually drawn).

Done earlier in session 3 (all verified in the harness unless noted):
* Location names: 207 names, town window (VWF name), liberated / discovered /
  lost messages (`patch/src/locname.asm`).
* Composed messages (`patch/src/msgcompose.asm`, `msg_*` in `ui.txt`):
  "<leader>'s unit has finished moving / to headquarters? / encountered ...",
  found item / treasure / spoils / obtained / gave up / drew the card (quoted
  names), revive and deploy costs, shop price, class change, stat changes from
  tarot cards (with "point"/"points"), stock label. Checked by test builds
  that run the patched code and log the result; the real-game window
  position of each is still to be seen in play.
* Move types (`patch/src/movetype.asm`): up to 7 letters on the status
  screen and unit window; 5-letter short forms in the deploy list.
* Finance window, organize top bar, quantity prompt, Suspend prompt, item-use
  and search messages, Jack's shop line, Data submenu (Save/Load), Link
  submenu labels, stage names on the scenario map (VWF, padded with `fill=10`),
  link-battle settings (labels, values, overview, terrain and time choices,
  round headers, results), battle terrain names (`0x2C82A9`).
* Fixes: `ui_lookup` now masks the pointer's top byte (popup tables keep flags
  there, so those strings were never remapped); the assembler gave `(REG+)`
  destinations a 1-byte step.

Open (each has a running round-2 workstream, see the table at the top):
* Pre-drawn Japanese graphics (need original English art): title logo and
  warning window, intro narration, chapter title cards (36), menu labels
  (45), the "deployed" tag, anything the survey finds.
* Fixed-width fields: character names (8 cells), item names (10/8 cells),
  class names (8-10 cells).
* Deeper play-testing: later stages, endings, shops/churches/recruiting,
  battles in depth.
* Core: BIOS chip size code and flash emulation in the harness; release
  package.

## UI text plan (in progress)

How UI text reaches the screen (details in `docs/engine-notes.md`):
* `0x200BAC` window renderer and `0x200B72` tile-mapped printer, both with the
  string pointer in `XIY` (`00` new line, `00 00` end, `01` space).
* System messages: code stores a string pointer in task field +32 (script
  var `0x20`) and calls `0x203FEF`/`0x202FA1`, which draws it straight from
  ROM with `0x200BAC` (yes/no prompt from `0x2030F5`).
* Many screens compose text in the RAM buffer `0x6000` with bespoke code,
  often copying fragments with fixed lengths (e.g. `ld XIY, 0x208864` /
  `ld BC, 0x16`), and fixed-width name tables (`0x20F0E7`, `0x20F134`,
  `0x20F21A`, terrain `0x2C82B2`, ...). Help texts use a 16-bit offset table
  (`0x2C3C8C`).

Insertion modes, per string:
1. **in-place**: English written over the original bytes (must fit; padded).
2. **remap**: hooks at `0x200BAC`/`0x200B72` look the source pointer up in a
   sorted table (original address -> English address in free ROM), so any
   string drawn directly from ROM can be longer; window strings can request
   the VWF renderer (packed tiles; must not use more tiles than the original).
3. **repoint**: patch the code immediates that load the string (and copy
   lengths) when all references are known.
4. **code**: custom patch where Japanese word order is baked into composition.

Packed tables: a table of self-relative 16-bit offsets followed by packed
entries; `0x201B77` returns `XIY` = entry, `BC` = length. Rebuilt whole and
repointed (`translation/en/tables/*.txt`, `@table ADDR [prefix=N]`).

Tools: `python -m tools.text.rawdump ROM LO-HI` (strings with lengths and
reference counts), harness `--text-log FILE` + `python -m tools.text.textlog
FILE` (what the renderers actually draw, with callers).

## How to build and test

```
build.bat                                    # builds build/ngp_harness.exe and build/zenobia.exe (MSVC + CMake + Ninja)
python -m tools.patch.build rom/baserom.ngc [--no-gfx]  # -> build/ogre_en.ngc, .bps, .sha1, symbols.txt; layout check
python -m tools.patch.layout build/ogre_en.ngc                   # region usage; refuses bytes in the save blocks
python -m tools.patch.test_bps rom/baserom.ngc                   # BPS encoder/decoder/audit tests
python -m tools.gfx.test_all rom/baserom.ngc                     # graphics library + build integration tests
python -m tools.gfx.apply IN.ngc OUT.ngc --target NAME           # one graphics target on a copy of a ROM
python runtime/src/core/tests/save_test.py --harness build/ngp_harness.exe --rom build/ogre_en.ngc --states build/states --work NEW_DIR
python runtime/src/frontend/tests/release_test.py ...            # player end-to-end check (see player.md)
python -m tools.text.dump rom/baserom.ngc build/script_ja.txt   # local Japanese script (not committed)
python -m tools.text.extract rom/baserom.ngc                     # inventory stats (+ build/strings_missed.txt)
python -m tools.text.check translation/en/script.txt            # English layout check
python -m tools.asm.test_roundtrip rom/baserom.ngc               # assembler self-test (28,948 insns)
python -m tools.text.l10n export rom/baserom.ngc                 # localization DB + CSV (build/l10n/, local only)
python -m tools.text.l10n import review.csv [--apply]            # apply a reviewer's CSV (docs/localization.md)
build\ngp_harness.exe build\ogre_en.ngc --frames 4200 --shot-every 60 --out <dir> --input "<frame>:<buttons>:<len>;..."
```

Reaching the world map from power-on (accepts the default name; ~9000 frames):
`--input` = `"700:A:2;740:A:2;...;8960:A:2;900:O:2"` (A every 40 frames from
700, Option at 900), e.g. generated with
`python -c "print(';'.join('%d:A:2' % f for f in range(700, 9000, 40)) + ';900:O:2')"`.

Saved states (English build; `build/states/`, not committed, recreate as below):
* `name_entry_grid.state` — name entry; `hq_status_screen.state` — HQ
  status screen after the tarot (9000-frame A spam above).
* `scenario_map_cursor_on_stage0.state` — "The Zenobian Age" scenario map
  (B from HQ backs out to it; B there toggles the Organize/Monitor/Data/Link
  popup). A at the stage marker does nothing: the hotspot is at
  `--input "10:R:12;27:D:12;54:A:2"` from this state ->
  `stage0_selected.state` (chapter title card, then stage 0 opening scenes).
* `stage0_gameplay.state` — stage 0 in real-time play (advance the opening with
  A, but answer the "Hear it again?" prompts with B).
* `title_menu.state` (title menu: NewGame / Load / Continue, pre-drawn),
  `command_bar_forecast.state` (map command bar on "Income forecast"; A opens
  the finance window), `scenario_popup_link.state` (scenario map popup).
* `hq_menu_location_icon.state` — from `stage0_gameplay.state` with
  `--input "46:A:2;80:D:2"` (A on HQ opens a small menu: NEXT, the unit, the
  location; Down selects the location icon). A then opens the town window.
  A on an empty map spot opens the command bar (NEXT / Organize / Items /
  Tarot / Income forecast / Monitor / Suspend; labels are pre-drawn
  Japanese graphics).

Harness extras: `--text-log FILE`, `--save-state F FILE`, `--load-state FILE`, `--watch R:lo-hi`,
`--watch W:lo-hi`, `--watch-log`, `--vm-log FILE`, `--prof lo-hi`,
`--ram-usage FILE`, `--vram F`, `--trace FILE`, `--tps 1|2`,
`--poke ADDR=HEX[,ADDR=HEX...][@FRAME]` (RAM bytes after `--load-state`),
`--save FILE` (cartridge save, same `.sav` format as the player; saving,
Suspend and Continue work), `--no-flash-commands`, `--dump-flash FILE`.
Graphics checks: `python -m tools.gfx.harness run|poke|diff|sheet`,
`python -m tools.gfx.vram render|bytes|map|find|queue` (harness via `--exe`,
else `NGP_HARNESS`, else `build\ngp_harness.exe`).
Buttons: U D L R A B O (Option). Put the ROM at `rom/baserom.ngc`
(SHA-1 `5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`).

Menu navigation found so far (from the HQ/organize screens): B backs out,
Option shows command help, Right/Left move between command icons. The world
map command popup has Organize / Monitor / Data (Data -> Save/Load).

## Checklist

### Infrastructure
- [x] TLCS-900/H decoder (`tools/recomp/tlcs900.py`), MAME-derived timings
- [x] C runtime: CPU interpreter, memory map, I/O, interrupts + micro-DMA, timers,
      K2GE renderer, Z80 + T6W28 + DAC audio, flash saves, BIOS HLE
- [x] Headless harness: scripted input, PNG screenshots, memory/VM tracing,
      profiling, RAM usage maps, deterministic save states
- [x] TLCS-900/H assembler (`tools/asm/tlcs900asm.py`), verified by round trip
- [x] Patch build pipeline with hook/free-space safety checks
- [x] BPS patch output for distribution (`build/ogre_en.bps`, audited: no ROM data)
- [x] Windows standalone player `zenobia.exe` (window, keyboard/gamepad, audio,
      cartridge saves with flash emulation, save states, patch applied at load)
- [x] Save-safe ROM layout (patch data out of `0x3B0000`-`0x3EFFFF`) + layout check
- [x] Core: BIOS chip size code, flash command emulation in the harness
- [ ] SDL port of the player for other platforms (optional)

### Text engine
- [x] Character table, control codes, message window format (`docs/engine-notes.md`)
- [x] Script VM decoded (~100 opcodes) and script walker
- [x] Stage records (20) and stage event lists decoded
- [x] English variable-width font (`assets/font/vwf8.txt`, original design)
- [x] VWF renderer for dialogue with incremental typewriter (cheap per frame)
- [x] Fixed-cell windows/UI switched to an English 8x8 font (layouts kept)
- [x] Dialogue relocation: original message -> jump to English pages in free ROM
- [x] Dialogue inventory: 1,570 messages verified (stage location lists,
      `0x61F0` event pointers, conditional native re-entries, overlap-free walk)
- [x] In-place replacement for messages shorter than the 4-byte jump
- [x] Inventory UI strings and window strings (scans + runtime text logs of every screen)
- [x] Name/data tables (classes, attacks, items, tarot names, tactics, units, places),
      with short copies for fixed-width fields (`sites=` copy tables)
- [x] Tarot question answers (20 lists) and the 4 missing tarot questions
- [x] Help texts (Option button), save/load messages
- [x] Insertion tools for fixed-width tables and UI strings
- [x] UI remap hooks on both renderers (+ VWF for window strings), named strings
      for code patches, in-place mode, fit checks (`tools/text/uitext.py`)
- [x] Name entry screen: English alphabet pages, relabel mode buttons

### Translation (`translation/en/`)
- [x] Opening tarot sequence (31 messages) translated and verified in-game
- [x] All dialogue: 1,570 / 1,570 messages (opening + stages 0-17, every
      message fits one page like the original); in-game pass done (every
      message of stages 2-17 the game can show was seen in context)
- [x] Glossary of names/terms (`translation/en/glossary.md`, romanized sources)
- [x] Location names (207) with VWF in the town window and location messages
- [x] Localization database + review import (`docs/localization.md`)
- [x] All UI/menu/table text (5,139 strings in the database, all translated)

### Graphics with Japanese text (`docs/workstreams/gfx-pipeline.md`)
- [x] Located, decoded and prototyped: title package, intro crawl, chapter
      cards, menu labels (round 1)
- [x] Pipeline design: text-only sources, build-time tiles, graphics region
- [x] `tools/gfx` library, `title16` display font (round 2 wave 1)
- [x] Build integration `gfx-build` (registry, in-place RomPatch, apply tool)
- [x] "Deployed" tag and "paralysed" label (survey targets): FIELDED, STUN
- [x] Menu labels (45) in English
- [x] Intro narration in English
- [x] Chapter title cards (36) in English
- [x] Title logo and warning window: original English art (faithful match)
- [x] Survey of all other screens for baked-in Japanese (`gfx-survey.md`)

### Testing / release
- [x] Playthrough checkpoints (389 saved states across every stage, ending and
      system) + screenshot sweep reviewed by eye (final verification)
- [x] Untranslated-text detection: harness text logs + l10n export rows;
      layout checks in the build (widths, lines, cells, Yes/No rule)
- [ ] Verify the patched ROM in an established emulator (manual; owner)
- [x] README, MIT license, third-party notices
- [x] Release packaging (zip with zenobia.exe, ogre_en.bps, README):
      `python -m tools.release.package` (dev package works; a public release
      still needs the manual checks in `docs/workstreams/release.md`)

## Key facts (details in `docs/engine-notes.md`)

* Free ROM `0x36746D`-`0x3FFFFF` except the game's save blocks
  `0x3B0000`-`0x3EFFFF`; patch regions in `tools/patch/layout.py` (table in
  "Where we left off").
* Message buffer `0x6000` (header `[pos][saved word]`, text at `0x6003`), ~120 bytes usable.
* Dialogue window: 18 tiles x 3 lines; English lines wrap at 144 px.
* Hooks so far: `0x2007F8` (typewriter step), `0x2008E3` (init tail),
  `0x200BEC` / `0x200B50` / `0x200B67` (English 8x8 font).
* Stage table `0x2261D9` (20 x 18 bytes: +0 event table, +10 map, +14 script);
  each event table has one location list `[u16 offset][u8 loc id][u8 town]`.
* Tarot answers are raw window text pointed to by `stv32 <ptr>, var 0x20`.

## Known issues / risks

* RAM free space is not proven; avoid new RAM use (current design needs none).
* The fixed-cell renderer leaves the map cell of a `01` space untouched; in
  windows that are not cleared first this shows stale glyphs. Use `solid`
  entries (spaces become the blank glyph `0xDC`) there.
* Emulator timing model: CPU states vs master ticks (`--tps`) unresolved
  (MAME/NeoPop = 1, ares = 2); default 1.
* `ld XHL, imm`-style task-slot seeds in native code are not exhaustively scanned.

## Session log

* **2026-10-09, session 1** — Built the runtime/harness, decoder, assembler and
  text toolchain; game boots and plays to the world map headless; English VWF
  dialogue working in-game; opening translated; dialogue extraction at 1,186
  verified messages; decoded stage records and event lists.
* **2026-10-09, session 2 (cont.)** — Translated all dialogue (stages 0-17),
  UI remap/table machinery, ~440 UI strings, 6 rebuilt tables (classes, names,
  items, item descriptions, tarot, town types).
* **2026-10-09, session 3** — Location names: decoded the stage location
  tables (207 records), town window and message composition; English names
  with VWF in both (`patch/src/locname.asm`, `translation/en/locations.txt`);
  town-type phrases moved from `tables/towntypes.txt` into `locations.txt`.
  Fixed an assembler bug: `(REG+)`/`(-REG)` destinations defaulted to a
  1-byte step (now the access size). Found untranslated strings outside the
  inventory (Suspend prompt). Localization database for linguist review
  (`tools/text/l10n.py`, `docs/localization.md`): export to SQLite/CSV from
  the ROM + `translation/en/`, import of reviewed CSVs; the UI scan now also
  finds script message pointers outside the walked code. Then: composed
  messages, move types, finance window, popup/stage names, link-battle
  screens, battle terrain; `ui_lookup` masks the pointer top byte; the
  export reads runtime text logs (`build/textlogs/`). All found text is
  translated (4,619 strings).
* **2026-10-10, session 3 (cont.)** — Complete build. Copy tables and short
  names (characters, items, classes) verified in 40 scenarios; play-test round
  2 (stages 2-17 in context, endings, every system and battle screen) and its
  plan applied (VWF battle names, CITY/recruit/class lists with full names,
  Yes/No rule, 36 dialogue fixes); graphics wave 2 accepted after side-by-side
  reviews (labels, intro, cards, title logo drafted with Codex, tags) and
  enabled; final verification (11 agents: 389-state sweep, golden path,
  release + every suite) with its fixes applied; graphics text added to the
  localization database (`tools/text/gfxtext.py`); player window icon; dev
  package `0.1.0-dev+4fe9c5ff`. A usage-limit stop was recovered with finish
  scripts (resuming parallel workflows by run id re-ran finished agents).
* **2026-10-09, session 3 (cont.)** — Parallel workflows (ultracode). Round 1:
  Windows player `zenobia.exe` + BPS distribution (end-to-end verified),
  six play-test areas consolidated into one verified plan (applied: crashes,
  VWF width bug, organize-screen wording, lists, Monitor help...), graphics
  located/prototyped and one pipeline designed. Found and fixed the patch
  writing into the game's save blocks (`tools/patch/layout.py`, layout check).
  MIT licence, README, third-party notices; glossary without Japanese. Round
  2 launched: graphics wave 1 (library, title16 font, survey), gfx build
  integration, core saves (BIOS size code, harness flash), release package,
  short names, play-testing round 2.
* **2026-10-09, session 2** — Finished the dialogue inventory (1,570 messages):
  fixed the stage location-list parser (one list per stage, global consecutive
  ids), followed `0x61F0` event pointers, conditional `jp cc, 0x20023D`
  re-entries and jumps during validation, switched the text scorer to an
  interpolated bigram model, made the walker reject overlapping decodes
  (removed fake "suffix" strings from the pointer search), new grouped
  `script_ja.txt` dump, in-place short messages.
