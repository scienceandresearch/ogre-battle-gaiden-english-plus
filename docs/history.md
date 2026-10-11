# Development history

How the project got to where it is, oldest first. Each entry describes the
state at the time, so the open items in older entries have since been
finished. [STATUS.md](../STATUS.md) has the current state, and the notes in
[workstreams/](workstreams/README.md) have the details of each line of work.

## Sessions

### 2026-10-09, session 1

Built the runtime/harness, decoder, assembler and text toolchain; game boots
and plays to the world map headless; English VWF dialogue working in-game;
opening translated; dialogue extraction at 1,186 verified messages; decoded
stage records and event lists.

### 2026-10-09, session 2

Finished the dialogue inventory (1,570 messages): fixed the stage
location-list parser (one list per stage, global consecutive ids), followed
`0x61F0` event pointers, conditional `jp cc, 0x20023D` re-entries and jumps
during validation, switched the text scorer to an interpolated bigram model,
made the walker reject overlapping decodes (removed fake "suffix" strings from
the pointer search), new grouped `script_ja.txt` dump, in-place short
messages.

### 2026-10-09, session 2 (continued)

Translated all dialogue (stages 0-17), UI remap/table machinery, ~440 UI
strings, 6 rebuilt tables (classes, names, items, item descriptions, tarot,
town types).

### 2026-10-09, session 3

Location names: decoded the stage location tables (207 records), town window
and message composition; English names with VWF in both
(`patch/src/locname.asm`, `translation/en/locations.txt`); town-type phrases
moved from `tables/towntypes.txt` into `locations.txt`. Fixed an assembler
bug: `(REG+)`/`(-REG)` destinations defaulted to a 1-byte step (now the access
size). Found untranslated strings outside the inventory (Suspend prompt).
Localization database for linguist review (`tools/text/l10n.py`,
`docs/localization.md`): export to SQLite/CSV from the ROM +
`translation/en/`, import of reviewed CSVs; the UI scan now also finds script
message pointers outside the walked code. Then: composed messages, move types,
finance window, popup/stage names, link-battle screens, battle terrain;
`ui_lookup` masks the pointer top byte; the export reads runtime text logs
(`build/textlogs/`). All found text is translated (4,619 strings).

### 2026-10-09, session 3 (continued): parallel workflows

Round 1: Windows player `zenobia.exe` + BPS distribution (end-to-end
verified), six play-test areas consolidated into one verified plan (applied:
crashes, VWF width bug, organize-screen wording, lists, Monitor help...),
graphics located/prototyped and one pipeline designed. Found and fixed the
patch writing into the game's save blocks (`tools/patch/layout.py`, layout
check). MIT license, README, third-party notices; glossary without Japanese.
Round 2 launched: graphics wave 1 (library, title16 font, survey), gfx build
integration, core saves (BIOS size code, harness flash), release package,
short names, play-testing round 2.

### 2026-10-10, session 3 (continued): complete build

Copy tables and short names (characters, items, classes) verified in 40
scenarios; play-test round 2 (stages 2-17 in context, endings, every system
and battle screen) and its plan applied (VWF battle names, CITY/recruit/class
lists with full names, Yes/No rule, 36 dialogue fixes); graphics wave 2
accepted after side-by-side reviews (labels, intro, cards, title logo drafted
with Codex, tags) and enabled; final verification (11 agents: 389-state sweep,
golden path, release + every suite) with its fixes applied; graphics text
added to the localization database (`tools/text/gfxtext.py`); player window
icon; dev package `0.1.0-dev+4fe9c5ff`. A usage-limit stop was recovered with
finish scripts (resuming parallel workflows by run id re-ran finished agents).

### 2026-10-10: sharing and ease of use

Private GitHub repository with the pre-release `v0.1.0-dev`; the player opens
the game from its `.zip` and gained a menu bar with File > Save English ROM;
the package gained `Patch your game.html`, an offline web patcher. The
documentation was reorganized: README with a quick start and a block of
instructions for AI agents, CONTRIBUTING.md, docs/testing.md and this file,
with STATUS.md reduced to the current state. Two review agents then checked
the user-facing text for plain wording and every command, path and claim
against the code; their corrections are in. Along the way the localization
database's `limits` for chapter cards and status tags were corrected to what
the build enforces (96 px and one title line; 24 px), and the obsolete
`translation/tests/inplace_smoke.txt` was removed (every message is
relocated now, so the build's `--inplace` test option has nothing left to
replace). Package rebuilt: 457,519 bytes, `release_test.py` 41/41,
`test_package` 33/33.

### 2026-10-10: official series names

A comparison with another English patch of the game (lucdubois/zenobia-en,
public v0.1, fixed-width text) led to a check of our names against the
series' official English releases, using the localization tables of the Ogre
Battle Saga wiki. Three names had no official form behind them and changed:
the prince's true name "Fix Trishtram" is now "Pheryx Tristan" (Tactics Ogre
PSP), "Lancelot" is "Lanselot" (Tactics Ogre PSP; Atlus: "Lans") and "Ryan"
is "Lyon" (Ogre Battle). The glossary now names the source of each series
name. Class names were left as they are: the official releases disagree with
each other, and the wiki rarely gives the Japanese names needed to match them.
The rebuild moved dialogue pages, so 54 test states saved mid-dialogue were
re-pointed; all 389 run without CPU errors. Build `d5234b95`, every suite
passes, dev package rebuilt (457,559 bytes).

### 2026-10-10 to 10-11: English Plus

The project became "Ogre Battle Gaiden English Plus": the translation, plus
extras for players. The repository was renamed to
`scienceandresearch/ogre-battle-gaiden-english-plus` (still private), and
the package to `ogre-battle-gaiden-english-plus-<version>-win64.zip`.

* Player: an Options menu (Console date: the PC's date, 25 December or 6
  June, for the game's two date secrets after the ending; When the player
  starts: ask, continue or title screen), a Cheats menu (100,000 goth, heal
  everyone, level up after the next battle, reputation +10 / -10; the code
  is in the core, `runtime/src/core/cheats.c`, so the harness has it too as
  `--cheat`), File > Import saved game (checks the file, backs up the
  current saves first) and File > Continue where I left off
  (`states/resume.state`, written when the player quits). Tests:
  `extras_test.py` 25/25 and, in the real window, `gui_extras_test.ps1`
  28/28 (the older window scripts updated for the new menu bar and the
  start-up question; all pass).
* Chapter saves: `tools/release/catalog.py` makes cartridge saves from test
  states through the game's own Data > Save, loads each back from the title
  screen to compare it, and audits it for ROM data. The states come from a
  playthrough (the only aid: enemy HP set to 1 when a battle starts) that
  went on to both routes and through an ending: 17 saves, one at the start
  of each chapter, both sides of the king's request, both routes up to the
  Final Chapter, and the Norodom route after the ending. The playthrough
  confirmed the guide's rules where it met them (Gross stays away at Chaos
  Frame 55 or more, no question about Kiros at hero ALI 60 or more, Grant
  only with Yorkleif, the hero a Lord in chapter 12 with both, Orosov gone
  at the start of chapter 11).
* Player's guide: `Player's Guide.html` in the package (Help > Player's
  guide), written from the game's code, data and test runs, with the fan
  wiki used only as leads; an 8-word overlap check against those wiki pages
  found only the game's title. Every fact and its source is in
  `docs/guide-sources.md`. The packager fills in the list of chapter saves
  from `catalog.json`. Writing it corrected a few exploration notes (event
  entry layout, a church index, the battle time-out rule, the game clock at
  each speed) and added the recruit level and Necromancer/Lich recruiting.
* Link-cable play (two-player battles, trading) was considered and left
  out: it needs a second game running and a link protocol, for little gain
  in a one-player game.

Build `d5234b95` unchanged (rebuilt from the sources: same SHA-1). Every
suite passes; `test_package` 46/46 (also without the maintainer's saves,
using a made-up one). Dev package 522,468 bytes with 17 chapter saves. An
audit of every new and changed file found no Japanese, no ROM data and no
personal data.

## Save-safe layout (2026-10-09)

Earlier builds put patch data in the game's save blocks. The game saves to
cartridge flash blocks 0x1B-0x1E = `0x3B0000`-`0x3EFFFF` (suspend, files 1-3;
slot table `0x29A66E`, `explore-data.md`). They put UI text at `0x3C0000` and
tables at `0x3E0000`, so in-game saving (hardware, flash carts, any emulator
with flash emulation, our player) overwrote and eventually erased them. Now
`tools/patch/layout.py` declares the regions and the build refuses any changed
byte in the save blocks or outside a region, printing each region's use:

| Range | Content | Used |
|---|---|---|
| `0x368000`-`0x36FFFF` | UI text and location names | 15.0 KB |
| `0x370000`-`0x377FFF` | patch code (`FREE_CODE`; `textfix.asm` routines at `+0x4000`) | 1.4 KB |
| `0x378000`-`0x37FFFF` | fonts, UI remap table (`FREE_DATA`) | 9.1 KB |
| `0x380000`-`0x39FFFF` | dialogue | 94.6 KB |
| `0x3A0000`-`0x3AFFFF` | replacement graphics (sub-regions in `gfx-pipeline.md` 4.1) | 0 |
| `0x3B0000`-`0x3EFFFF` | the game's save blocks: never written | none |
| `0x3F0000`-`0x3FFFFF` | rebuilt tables | 28.4 KB |

Verified: 16 harness scenarios (finance and town windows, status, organize
items/class change/equipment, unit window, liberation message, item found,
battle commands, Monitor, scenario map, stage 2 play) are pixel-identical
before and after the move; in the player, 19 saves to file 1 erase block 28
once and "Save complete." stays English. Old `.sav` files made with earlier
builds carry stale patch bytes: delete them. English ROM SHA-1 now
`272f13ab...`.

Also fixed (core, round 2): the HLE BIOS stored chip size code 1 at `0x6C58`,
so a full save block made the game erase block 15 (game data); the core now
stores the real codes (3 for this 2 MB cartridge) at reset and on every state
load. The flash-chip command emulation moved from the player into the core, so
the harness saves too (Save, Suspend, Continue; `--no-flash-commands` restores
the old behavior); harness `--poke ADDR=HEX[,...][@FRAME]` and `--dump-flash
FILE` were added. `runtime/src/core/tests/save_test.py`: 33/33.

## Round 1 results (2026-10-09)

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
    `fill=`/`center`) had width 0, so padding and centering never worked
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

## Graphics rule (owner, 2026-10-09)

Every replacement graphic must match the original very closely, with only the
targeted change (Japanese lettering -> English): same position and size, the
original palette colors (no palette writes unless unavoidable), the same
outline/glow/shading treatment and texture, comparable letter weight and
height; everything else stays pixel-identical. Each target is reviewed side by
side with the original (local images only). Codex CLI image generation
(`$imagegen`) may be used for drafts and style references (the title logo
first); final pixels go through `tools/gfx` and are committed as text sources,
never as ROM-derived images.

## Text coverage after round 1 (2026-10-09)

Localization database (`docs/localization.md`), export of 2026-10-09 after the
round-1 fixes: 4,634 strings: dialogue 1,570, UI 598, named strings for code
patches 52, table entries 2,199, locations 207 + 8 town-type phrases; 0
untranslated among everything the scans and the recorded runtime logs find
(the export now also flags hiragana-only strings). The scans do not find
everything (strings behind pointer tables in data that the walker took for
code, values printed by `base + index * size`), so remaining gaps will show up
as more screens are visited: record harness text logs of the English build
into `build/textlogs/` (the export reads them and lists any Japanese that was
actually drawn).

## Earlier in session 3

All verified in the harness unless noted: * Location names: 207 names, town
window (VWF name), liberated / discovered / lost messages
(`patch/src/locname.asm`). * Composed messages (`patch/src/msgcompose.asm`,
`msg_*` in `ui.txt`): "<leader>'s unit has finished moving / to headquarters?
/ encountered ...", found item / treasure / spoils / obtained / gave up / drew
the card (quoted names), revive and deploy costs, shop price, class change,
stat changes from tarot cards (with "point"/"points"), stock label. Checked by
test builds that run the patched code and log the result; the real-game window
position of each is still to be seen in play. * Move types
(`patch/src/movetype.asm`): up to 7 letters on the status screen and unit
window; 5-letter short forms in the deploy list. * Finance window, organize
top bar, quantity prompt, Suspend prompt, item-use and search messages, Jack's
shop line, Data submenu (Save/Load), Link submenu labels, stage names on the
scenario map (VWF, padded with `fill=10`), link-battle settings (labels,
values, overview, terrain and time choices, round headers, results), battle
terrain names (`0x2C82A9`). * Fixes: `ui_lookup` now masks the pointer's top
byte (popup tables keep flags there, so those strings were never remapped);
the assembler gave `(REG+)` destinations a 1-byte step.

## Open at the end of round 1

All of these were finished in round 2.

* Pre-drawn Japanese graphics (need original English art): title logo and
  warning window, intro narration, chapter title cards (36), menu labels
  (45), the "deployed" tag, anything the survey finds.
* Fixed-width fields: character names (8 cells), item names (10/8 cells),
  class names (8-10 cells).
* Deeper play-testing: later stages, endings, shops/churches/recruiting,
  battles in depth.
* Core: BIOS chip size code and flash emulation in the harness; release
  package.

## Round 2 graphics plan

The plan is in `gfx-pipeline.md` section 8. Wave 1 = `gfx-lib` (`tools/gfx/`
library), `gfx-font16`, `gfx-survey` (running since 2026-10-09); `gfx-build`
(target registry, `build/gfx/gfx.asm`, in-place `RomPatch`, `tools.gfx.apply`)
starts once the save-safe layout is in; wave 2 = labels, intro, cards, title
(one agent each, tested with `python -m tools.gfx.apply` on a snapshot ROM);
wave 3 = `gfx-verify` (full build, all recipes).

## Last rounds

Graphics wave 2 and text round 2 were stopped once by a usage limit and
finished with "finish" scripts that start each task at its last finished step
(resuming a parallel workflow by run id re-ran finished agents; see
`build/handoff/finish/`).

## Complete build verification (2026-10-10)

Tests on build `4fe9c5ff`: `release_test.py` 40/40 from the unzipped package;
`save_test.py` 27/27; the package's Python applier reproduces the ROM SHA-1;
`tools.gfx.test_all` 7 modules (105 tests); `test_tables` 18/18; `test_bps`
11/11; `tools.text.check` 1,570 messages, each one page; localization database
5,139 strings, all translated. The final verification round
(`obg-r3-final-verify`, 11 agents) swept every saved state (389) by eye,
played power-on to stage 1 with save/load/suspend/continue in the harness and
the player, and ran every suite: the only in-game defect (the "Save complete."
bar spilling past its frame) is fixed, as are the release README, five A/B
choices that wrapped to a third line, the NEXT window's UNIT tab (now
proportional like CITY) and the packaged applier's `--help`.

Test states: 35 states saved mid-dialogue with older builds crashed on the new
one (their dialogue pointers moved), a test-asset problem, not a build defect.
They were replaced by relocated copies (originals in
`build/states/stale-e63bffd1/`). After any rebuild that moves dialogue pages,
run `build/handoff/r3/stalescan.py` / `relocate.py` (or re-record the states).
States also keep the video memory of the build they were saved with (e.g.
`title_menu.state` still shows the old logo until the title is reloaded).

## Ease of use and sharing (2026-10-10)

No command line needed. The player opens the game as `.ngc` or straight from
the `.zip` it came in (own zip/inflate reader,
`runtime/src/frontend/zipread.c`), and has a menu bar with File > Save English
ROM... (Ctrl+S) for other emulators. The package also holds `Patch your
game.html`: a one-file, offline web patcher (choose the game or its zip, click
"Save the English game"; works on any system; no network access allowed by its
CSP; `tools/release/webpatcher.py`, tested in Node and in Chrome). Both
READMEs start with a three-step quick start. Tests: `release_test.py` 41/41,
`zip_test.py` 59/59, `test_webpatcher` 2/2, `test_package` 33/33.

Private GitHub repository
`https://github.com/scienceandresearch/open-ogre-battle-gaiden-zenobia`
(branch `main`), with the pre-release `v0.1.0-dev` carrying the package zip.
Sharing model: "bring your own game". The repository and the package hold only
original code, translation, fonts and lettering plus the audited BPS patch;
players supply their own cartridge dump. A fresh clone builds the identical
English ROM (`4fe9c5ff...`) and passes every test suite; `build.bat` builds
the player and harness from the clone. Line endings: `.gitattributes` stores
LF; Windows checkouts get CRLF, which every tool accepts. Share access by
inviting collaborators (repository settings) or, later, by making the
repository public after the manual release checks.