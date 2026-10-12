# Project status

_Last updated: 2026-10-11_

This file tracks Ogre Battle Gaiden English Plus: the English version of
*Densetsu no Ogre Battle Gaiden: Zenobia no Ouji* (Neo Geo Pocket Color),
plus a Windows player with extras. It records where the project stands, what
is left, and which decisions are still open. The development log is in
[docs/history.md](docs/history.md).

## Where the project stands

Version 1.0.0, the first public release, was published on 2026-10-11: the
repository is public and the release `v1.0.0` carries the zip and its
`README.txt` as separate downloads. The development pre-release `v0.1.0-dev`
and its tag were removed.

* Everything the game shows is in English: all 1,570 dialogue messages, every
  menu and system message, all names and places, and every pre-drawn graphic
  with Japanese lettering (the title logo, the warning window on the title
  screen, the intro narration, the 40 chapter title cards, 44 menu labels and
  two status tags). The localization database counts 5,139 strings, all
  translated.
* The final verification looked at 389 saved states across every stage,
  ending and system, played the game from power-on through stage 1 with
  saving, loading, suspending and continuing, and ran every test suite.
  Everything it found is fixed.
* Players need no command line. The Windows player opens the game file or
  the zip it came in, and `Patch your game.html` in the package makes the
  English file in any web browser, offline.
* The "plus": the package has a player's guide (`Player's Guide.html`, also
  under Help in the player), ready-made chapter saves to import (one at the
  start of each chapter and on each side of the route choices, from a test
  playthrough), a Cheats menu (goth, healing, levels, reputation), a console
  date setting for the game's two date secrets, and "continue where you left
  off".
* The repository and the package contain no data from the game. Players bring
  their own copy. The patch holds only the changes and is audited against the
  original.

The current build turns the original (SHA-1
`5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`) into the English ROM with SHA-1
`d5234b95d12096c722c324d23e5e4fb227179eff`. The patch `ogre_en.bps` is
133,249 bytes, and the release package
`ogre-battle-gaiden-english-plus-1.0.0-win64.zip` is 522,001 bytes with 17
chapter saves (SHA-256
`9db5bdf657ea8b0d334ee6ee505c4fc2c20a7fde6455775ea94aad1ed8f18621`). Test
results on this build: `release_test.py` 41/41 on the files extracted from
the zip, `zip_test.py` 59/59, `save_test.py` 27/27, `extras_test.py` 25/25,
`bps_test.py` 26/26, `tools.gfx.test_all` 7 modules (105 tests),
`test_tables` 18/18, `test_bps` 11/11, `test_webpatcher` 2/2, `test_package`
46/46, the assembler round trip (28,948 instructions, none failed), the six
real-window scripts `gui_*.ps1` (121 checks, among them 28 for the new
menus; run on the 0.1.0 player, whose code 1.0.0 shares), and
`tools.text.check` confirms that each of the 1,570 dialogue messages fits on
one page. All 389 test states run on this build without CPU errors (54 of
them were re-pointed to its dialogue pages).

Checks outside the project's own emulator (2026-10-11, on this patch):
Floating IPS v198 (`flips --apply`) and ROM Patcher JS v3.2.1 (its patching
library, which the web page uses, run in Node.js) both make the English ROM
with the right SHA-1. Floating IPS refuses the English ROM and a changed
original; ROM Patcher JS shows "Source ROM checksum mismatch" for them but
by default still writes a (broken) file, and the readmes say so. In the
libretro cores Beetle NeoPop (Mednafen) and RACE, run off-screen with
`tools/release/lrhost.py`, the English ROM plays the opening, the name
entry and the tarot reading; in Beetle NeoPop also chapter 1 with its
dialogue, the church event and the battle at Gring; in both, a save made in
the game loads after the emulator restarts. Beetle NeoPop gives the same
frames with the console language set to Japanese or English.

The names of characters who appear in the series' official English releases
follow those releases (see "Open decisions").

The readmes say how the translation was made: the English text, the player
and the tools were written with Claude (Anthropic's AI model), directed by
the project lead (scienceandresearch), and no human translator has reviewed
the translation yet.

## What is left

1. Announcing it: the Romhacking.net entry was submitted on 2026-10-11 and
   waits for the site's approval. Romhack Plaza and the Freeplay Tech forum
   follow (texts in `build/handoff/outreach/submissions.md`, machine-local),
   then the Romhacking.net news post and the news tips once the entry is
   live. Romhack.ing blocks downloads of machine-translated patches, so ask
   there first.
2. One manual check that cannot be done here: run the package on a clean
   Windows 10 or 11 PC (step 7 of the checklist in
   [docs/workstreams/release.md](docs/workstreams/release.md)). The player
   imports only DLLs that ship with Windows.
3. The open decisions below.
4. Optional work: a review of the translation by a human translator through
   the localization database ([docs/localization.md](docs/localization.md)),
   which the patch sites and players will value most; the compact form of
   the menu labels' descenders; a harness check that refuses save states made
   with another ROM, as the player already does; a check of the class names
   against the official releases (several classes have different English
   names in Ogre Battle, Tactics Ogre and Ogre Battle 64, and matching them
   needs a reliable list of the Japanese names).

## Open decisions

These choices are provisional. Each one is already built and takes a one-line
change in a text file to revise.

* Title: every element of the original logo is translated. A small "THE
  LEGEND OF" (the original logo has it), "OGRE BATTLE" in fire lettering,
  "GAIDEN" in white (rather than "SIDE STORY"), and the subtitle "PRINCE OF
  ZENOBIA".
* Intro: set in the 11-row `title16` font. Line 6 reads "is indeed a 'true
  king'..." to avoid "truly a true".
* Chapter cards: the headings are "Chapter N" and "Final Chapter", chapter 13
  is "White Night", and the titles of chapters 3, 4, 12 and 14 are shortened
  to fit.
* Menu labels, as in `translation/en/labels.txt`: 03 is "Finances" (the
  window it opens is titled "Income & Expenses"), 07 and 20 are both
  "Organize", 09 is "Remove", 25 and 26 are "Send chars" and "Get chars", and
  the church label 14 is "Rite of revival" (Game System Tips quotes it the same
  way). The letters on row 7 keep their descender tails; a compact form
  exists.
* Status tags: FIELDED for a deployed unit (DEPLOYED does not fit the original
  box) and STUN for paralysis.
* Fixed-width fields show character names of up to 8 letters, which changes
  one story name ("Dark Knight" becomes "D.Knight"), and short item and class
  names. Full names appear everywhere else.
* The staff roll opens with the English title instead of the original's
  romanized one.
* Series names: characters who appear in the official English releases keep
  those names (`translation/en/glossary.md` gives the source of each). Where
  the releases differ, the prince's true name is "Pheryx Tristan" and
  Ransurotto is "Lanselot", as in Tactics Ogre: Let Us Cling Together (PSP);
  the Atlus releases call him "Lans". The Beast King is "Lyon", as in Ogre
  Battle. Zenobia, Zeteginea and Gilbert follow the Atlus releases (the PSP
  release has Xenobia, Xytegenia and Gilbald).
* English that was already in the original art stays as it is:
  "Congratulation!", "NewGame", the "TAROT" frame header and "M-SHILD".

Still to decide:

* The license of the new `title16` font: CC0 like the variable-width font, or
  MIT only (MIT for now).
* Whether to restore the unused ending epilogue, 87 lines that the shipped
  game never shows. This is not planned.
* Where to keep the original ROM archive `Densetsu no Ogre Battle (Japan).zip`.
  It sits in the root of the working folder (git-ignored, never committed);
  moving it into `rom/` or out of the folder would be safer.

## Goal and approach

The goal is an English version of the game that is easy to play on a PC, open
source, and requires the player's own copy of the game. No data from the game
(Japanese text, graphics, generated code) is ever committed.

1. Translation patch (phase 1, done): `tools/patch/build.py` makes the English
   ROM from the original. It is meant for existing emulators and flash
   carts; besides the project's own player it has been tested in Beetle
   NeoPop and RACE (flash carts not tested).
2. Standalone player (phase 2, done for Windows): the project's own emulator
   core in `runtime/`, which is also the test harness, with a Win32 player
   that applies the patch when it loads the game. An SDL port for other
   platforms is optional.
3. Static recompilation (`tools/recomp/`) is optional and neither phase needs
   it.

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
      cartridge saves with flash emulation, save states, patch applied at load,
      opens the game's .zip, File menu with Save English ROM)
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
- [x] All UI, menu and table text (the localization database holds 5,139
      strings, dialogue and graphics included, all translated)

### Graphics with Japanese text (`docs/workstreams/gfx-pipeline.md`)
- [x] Located, decoded and prototyped: title package, intro crawl, chapter
      cards, menu labels (round 1)
- [x] Pipeline design: text-only sources, build-time tiles, graphics region
- [x] `tools/gfx` library, `title16` display font (round 2 wave 1)
- [x] Build integration `gfx-build` (registry, in-place RomPatch, apply tool)
- [x] "Deployed" tag and the paralysis label (survey targets): FIELDED, STUN
- [x] Menu labels in English (44 redrawn; label 23, NEXT, was already English)
- [x] Intro narration in English
- [x] Chapter title cards in English (40 cards in 36 records)
- [x] Title logo and warning window: original English art (faithful match)
- [x] Survey of all other screens for baked-in Japanese (`gfx-survey.md`)

### Extras (the "plus")
- [x] Player menus: Options (console date, what happens at start), Cheats,
      Help > Player's guide; File > Import saved game (with a backup first)
      and Continue where I left off (`docs/workstreams/player.md`)
- [x] Cheats in the core (`runtime/src/core/cheats.c`), also in the harness
      (`--cheat`); console date override (`--date`) in both
- [x] Chapter saves from a test playthrough (`tools/release/catalog.py`,
      recipe `catalog.txt`), each loaded back and audited for ROM data
- [x] Player's guide (`tools/release/guide.html`; every fact and its source in
      `docs/guide-sources.md`); the save list is filled in by the packager
- [ ] Link-cable features (two-player battles, trading): not planned; the
      player behaves as if no cable is connected

### Testing / release
- [x] Playthrough checkpoints (389 saved states across every stage, ending and
      system) + screenshot sweep reviewed by eye (final verification)
- [x] Untranslated-text detection: harness text logs + l10n export rows;
      layout checks in the build (widths, lines, cells, Yes/No rule)
- [x] Verify the patched ROM in established emulators: Beetle NeoPop and RACE
      through `tools/release/lrhost.py` (2026-10-11)
- [x] Apply the patch with Floating IPS v198 and ROM Patcher JS v3.2.1
      (2026-10-11)
- [ ] Run the package on a clean Windows PC (manual; owner)
- [x] README, CONTRIBUTING, MIT license, third-party notices
- [x] Offline web patcher `Patch your game.html` (`tools/release/webpatcher.py`)
- [x] Release packaging (zip with zenobia.exe, ogre_en.bps, the web patcher,
      the player's guide, the chapter saves and a README):
      `python -m tools.release.package`; the 1.0.0 package was made with
      `--release` and passed checklist steps 1 to 6 and 8 in
      `docs/workstreams/release.md`

## Resuming work

For maintainers and AI agents who pick the work up:

1. Read this file, then the notes for the area you work on
   ([docs/workstreams/README.md](docs/workstreams/README.md) lists them).
2. Follow the rules in [CONTRIBUTING.md](CONTRIBUTING.md). Nothing from the
   game may be committed.
3. Build and test as described in [docs/testing.md](docs/testing.md). The
   build needs your own copy of the game at `rom/baserom.ngc`.
4. At each milestone, update this file (the summary, the checklist and the
   open items) and add an entry to [docs/history.md](docs/history.md).

The repository is
`https://github.com/scienceandresearch/ogre-battle-gaiden-english-plus`
(public, branch `main`); the release `v1.0.0` carries the package zip and
its `README.txt`. Never rebuild a published version: raise `VERSION` for the
next one. `.gitattributes` stores text files with LF line endings, Windows
checkouts get CRLF, and every tool accepts both. A fresh clone builds the
identical English ROM and passes every test suite. The save, release and
extras tests and the chapter saves also need the machine-local test states
(see "Test states" in [docs/testing.md](docs/testing.md)); without them,
package with `--no-catalog`.

Machine-local material on the maintainer's PC, never committed:

* `build/states/`: about 400 test states, among them the `play-*` states of
  the playthrough behind the chapter saves of chapters 8 to 12 and after the
  ending. "Test states" in [docs/testing.md](docs/testing.md) explains what
  to do with states from older builds. For the `d5234b95` build, 54 states
  were re-pointed with `build/handoff/r3/relocate.py` and `relocate_inner.py`
  (the second one handles states paused at a prompt); the originals are in
  `build/states_before_d5234b95/`.
* `build/handoff/`: the agents' briefing (`briefing.md`), every round's raw
  results (`r1_*_result.json`, `r2_*.json`, `r3_final.json`), the Codex title
  drafts and prompts (`codex-title/`), the play-test plan tools (`tplan/`),
  the finish and final-verification scripts (`finish/`), the stale-state tools
  (`r3/`) and all workflow scripts (`workflow-scripts/`).
* The scratch folder of the Claude Code session that built the project
  (written `<scratch>` in the notes) holds the agents' work folders and
  snapshots. It may be cleaned.

Resuming a parallel workflow by its run id re-runs agents that had already
finished. To continue an interrupted round, start each task at its last
finished step instead, as the scripts in `build/handoff/finish/` do.

## Engine and ROM facts

Details are in [docs/engine-notes.md](docs/engine-notes.md).

* Free ROM `0x36746D`-`0x3FFFFF` except the game's save blocks
  `0x3B0000`-`0x3EFFFF`; patch regions in `tools/patch/layout.py` (table
  below).
* Message buffer `0x6000` (header `[pos][saved word]`, text at `0x6003`), ~120 bytes usable.
* Dialogue window: 18 tiles x 3 lines; English lines wrap at 136 px in stage
  dialogue and at 144 px in the opening and prologue (bank `0x29`).
* Main text hooks: `0x2007F8` (typewriter step), `0x2008E3` (init tail),
  `0x200BEC` / `0x200B50` / `0x200B67` (English 8x8 font). The other hooks
  are in `patch/main.asm` and `patch/src/*.asm`.
* Stage table `0x2261D9` (20 x 18 bytes: +0 event table, +10 map, +14 script);
  the event entries sit before each location table, one per location r >= 1
  at (table - 4r): `[u8 id][u8 hidden index][u16 handler offset]`.
* Tarot answers are raw window text pointed to by `stv32 <ptr>, var 0x20`.

Patch regions of the current build (`python -m tools.patch.layout
build/ogre_en.ngc`; "used" is the extent from the start of the region):

| Range | Content | Used |
|---|---|---|
| `0x368000`-`0x36FFFF` | UI text and location names | 15.5 of 32 KB |
| `0x370000`-`0x377FFF` | patch code (`FREE_CODE`; `textfix.asm` routines at `+0x4000`) | 16.1 of 32 KB |
| `0x378000`-`0x37FFFF` | fonts, UI remap table (`FREE_DATA`) | 19.6 of 32 KB |
| `0x380000`-`0x39FFFF` | dialogue | 94.5 of 128 KB |
| `0x3A0000`-`0x3AFFFF` | replacement graphics (sub-regions in `gfx-pipeline.md` 4.1) | 18.4 of 64 KB |
| `0x3B0000`-`0x3EFFFF` | the game's save blocks: never written | none |
| `0x3F0000`-`0x3FFFFF` | rebuilt tables | 32.0 of 64 KB |

## Known issues and risks

* RAM free space is not proven; avoid new RAM use (current design needs none).
* The fixed-cell renderer leaves the map cell of a `01` space untouched; in
  windows that are not cleared first this shows stale glyphs. Use `solid`
  entries (spaces become the blank glyph `0xDC`) there.
* Emulator timing model: CPU states vs master ticks (`--tps`) unresolved
  (MAME/NeoPop = 1, ares = 2); default 1.
* `ld XHL, imm`-style task-slot seeds in native code are not exhaustively scanned.
