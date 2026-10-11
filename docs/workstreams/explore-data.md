# Explore: data and system flows

## Goal

Play-test the English build through the data and system flows (title menu, Load
screen with and without saves, saving from the scenario map popup, Suspend and
Continue, Monitor settings, notice screens, game over, first-run name entry and
tarot questions) and report every piece of text that is still Japanese, does not
fit, overlaps a frame or leaves stale characters behind.

## State

Paused (2026-10-09, round 1). Blocked: the runtime does not emulate the flash
commands this game uses, so nothing can be saved (Load with saves, the overwrite
prompt, "Save complete." and Continue are unreachable). Some planned runs were
also stopped by the session's tool permission checks (see Next steps).

## Done

Checked in the harness (English build, text logs in `build/textlogs/data-*.txt`):
* Power-on: SNK logo, intro narration (pre-drawn, covered by gfx-intro-narration),
  title menu (NewGame / Load / Continue are pre-drawn English; Load and Continue
  are grayed out and cannot be selected while there is no save or suspend data).
* NewGame: "Choose where to save." and the file list (3 x "NOTHING"); B goes back
  to "PRESS A BUTTON". Choosing a file starts Warren's opening.
* Name entry: all three grid pages (ABC, abc, 123), END, the confirmation with an
  8-letter name, "No" (grid redrawn correctly) and "Yes". Everything fits.
* Tarot reading: 7 of the 20 answer lists seen in play (`0x299B98`, `0x2997C9`,
  `0x299A1A`, `0x299768`, `0x299839`, `0x299E76`, `0x299EDD`) plus their questions,
  the "Lastly, draw a single tarot card..." step and the closing prayer. All fit
  the 18 x 3 window; nothing is cut off. The pre-drawn card names (PRIESTESS,
  STRENGTH, MAGICIAN, ...) are English in the original.
* Scenario map popup: Data -> Save ("OK:A  NO:B" fits; then "Saving data..." and
  "Could not save."), Data -> Load (DATA LOAD screen, no saves), Monitor panel and
  its five help texts (untranslated, see Open issues).
* Stage map command bar -> Suspend: prompt, both Continue notes.
* 12,000 frames of idling on stage 0: no enemy reaches the HQ; the day change
  opens the finance window ("Income & Expenses", English, fits).

## Critical findings (for the orchestrator)

1. **The patch puts data in the game's save blocks.** The game keeps its saves
   in cartridge flash blocks 27-30. A slot table at `0x29A66E` (8-byte records,
   used by `0x29A47E`, `0x29A4D7` and `0x29A50F`) gives the address and block
   number of each slot: file 1 = `0x3C0000` (block 0x1C), file 2 = `0x3D0000`
   (0x1D), file 3 = `0x3E0000` (0x1E), slot 3 (suspend data, written by the
   Suspend command) = `0x3B0000` (0x1B). `tools/patch/build.py` puts the
   remapped UI text at `0x3C0000`-`0x3DFFFF` and the rebuilt tables at
   `0x3E0000`-`0x3EFFFF` (it assumed the save area is the last 64 KB). In the
   current English ROM `0x3C0000`-`0x3C3BDB` and `0x3E0000`-`0x3E717B` hold
   patch data. On hardware, flash carts and any emulator that emulates flash:
   saving to file 1 or 3 writes save records into the patch area (the free-space
   scan `0x29A436` walks 16-bit record sizes from block start + 6 and reads patch
   bytes as sizes; in the harness the first write of file 1 went to
   `0x3C7700`), and when the block is full the game erases the whole block
   (`0x29A576` -> erase wrapper `0x366F75`), wiping the English UI text or
   tables. Fix: keep all patch data out of `0x3B0000`-`0x3EFFFF`; free space
   remains below `0x3B0000` and in `0x3F0000`-`0x3FFFFF`, which no slot uses.
   The flash routines are only copied to RAM by the save module (`0x366ED5`,
   `0x366FB3`; a byte match at `0x2DC483` is graphics data), whose callers
   (`0x29A4FC`, `0x29A576`, `0x29A5CC`) all take the block from that slot
   table, so no other flash block is written.
2. **Saves do not work in our runtime.** The game does not use the BIOS flash
   calls: it copies its own flash routines to RAM `0x6E00` (byte-program loop
   from `0x366F02`, erase from `0x36711E`; wrappers `0x366E94` write and
   `0x366F75` erase, chip base in XIX: `0x200000` or `0x800000`) and drives the
   chip with command sequences: `AA` -> base+`0x5555`, `55` -> base+`0x2AAA`,
   then `A0` and the data byte written to the target address (byte program),
   or `F0` (reset); the erase routine presumably uses `80`, `AA`, `55`, `30`
   (sector erase). It verifies by reading the byte back and polling bit 5, and
   gives up after 5 tries. `runtime/src/core/flash.c` (`flash_command_write`)
   ignores these writes, so every save fails ("Could not save."). The Player
   needs an AMD-style command state machine (program = AND the byte into the
   image, sector erase = fill the block with `FF`, mark the block touched so the
   save file keeps it).

## How to test / reproduce

Harness: the stable snapshot `scratchpad\snap\ngp_harness.exe` with
`scratchpad\snap\ogre_en.ngc` (see the briefing). Text logs go to
`build/textlogs/data-*.txt`, new states to `build/states/data-*.state`.
Note: `--save FILE` is loaded before `--load-state`; a state only carries the
flash blocks the game wrote, so a flash file survives loading older states.

States (all in `build/states/`, English build) and how to go on from them:
* `title_menu` (shared): A at frame 60 = NewGame ("Choose where to save."), A at
  200 = file list.
* `data-newgame_file_list`: NewGame file list. Down moves, B returns to the
  title, A on a file starts the opening.
* `data-opening_start`: Warren's first line, right after choosing file 1.
  From `data-newgame_file_list`: `20:A:2` then A every 40 frames from 160 reaches
  the name entry at frame 522.
* `data-name_entry_fresh`: name entry, default name, nothing typed. Option
  jumps to END; Up/Down move in the mode column (ABC / abc / 123 / END); A on a
  mode switches the grid page; the game asks "Is this name OK?" by itself after
  the 8th letter. `10:O:2;50:A:2;120:A:2` = END, Yes.
* `data-tarot_reading_start`: just after confirming the name. A every 40
  frames from frame 20 reaches the scenario map at about frame 4980. Which 6
  questions are asked depends on input timing (not on the clock): A every 40
  frames from 20 gives `0x2997C9`, `0x299A1A`, `0x299768`, `0x299839`,
  `0x299E76`, `0x299EDD`.
* `data-scenario_map_new`: scenario map just after the opening, popup open on
  Organize. `20:R:2;50:R:2;90:A:2` = Data; then `150:A:2` = Save ("OK:A NO:B"),
  or `150:R:2;200:A:2` = Load (DATA LOAD screen; B returns). `20:R:2;80:A:2` =
  Monitor panel.
* `data-popup_save_prompt`: the "OK:A  NO:B" bar of Data -> Save. A tries to
  save (fails in our runtime; watch with `--watch W:205555-205555 --watch
  W:3C0000-3CFFFF --watch-log FILE`).
* `data-popup_monitor`: Monitor panel, cursor on the first row. Option shows
  the row's help in the bottom bar, B closes it, Down moves to the next row.
* `data-cmdbar_suspend`: stage 0 command bar with the cursor on Suspend
  (from `stage0_gameplay`: `10:L:5;21:D:15;46:A:2` then Right six times, 30
  frames apart). A = prompt, A = Yes; the game then shows both notes and stays
  on the second one (the suspend write to `0x3B0000` failed).

## Open issues

1. Patch data inside the save blocks (Critical findings 1).
2. Runtime: no flash command emulation, so saving fails (Critical findings 2).
   Load with saves, "Overwrite this file?", "Save complete." and Continue from
   the title cannot be reached until the runtime emulates the commands.
3. **Monitor (screen settings) help texts are untranslated.** Option on each
   row of the Monitor panel shows a 2-line help in the bottom bar (window
   renderer, caller `0x29BF92`, map `0x9446`, first tile `0x1E0`; 14 cells x
   2 lines, padded with the blank glyph `0xDC`). None is in `ui.txt`:
   * `0x29BF9A` (row 1, animation): fixed "ON: Animations" / "OFF: Skip them",
     or VWF "ON: Play animations" / "OFF: Skip animations".
   * `0x29BFB9` (row 2, music): "ON: Play music" / "OFF: No music".
   * `0x29BFD8` (row 3, sound effects): "ON: Play SFX" / "OFF: No SFX", or VWF
     "ON: Play sound effects" / "OFF: No sound effects".
   * `0x29BFF7` (row 4, message speed, 3 levels): "Sets message" /
     "speed (1-3).", or VWF "Set how fast messages" / "appear (3 speeds)."
   * `0x29C016` (row 5, game speed, 3 levels): "Sets game" / "speed (1-3).",
     or VWF "Set the game speed" / "(3 speeds)."
   `python -m tools.text.l10n export` flags only three of them (`0x29BF9A`,
   `0x29BFF7`, `0x29C016`); `0x29BFB9` and `0x29BFD8` are missing from the
   database although they were logged (`data-monitor2.txt`).
4. **Suspend prompt overlaps the Yes/No choice.** `0x204888` is translated on 3
   lines, but the Yes/No prompt (`0x2030F5`, map `0x940C`, row 16 from column 6)
   is drawn on the third line of the window (the original prompt had 2 lines),
   so the screen reads "Is that [cursor]Yes  No". Suggest 2 lines: "Save the game
   in progress" / "and turn off the power?". Any other 3-line `sysmsg` entry
   that is followed by a Yes/No prompt collides the same way.
5. "Could not save." (`0x29BCF1`, VWF) in the scenario map message bar is
   followed by about 3 cells of a checkered pattern: the bar's tiles start out
   checkered and the VWF text does not cover all 12 cells of the original
   string. "Saving data..." (`0x29BCFF`, 12 cells) and "Save complete."
   (`0x29BD0D`, 10 cells) are in the same bar. Suggest padding these VWF
   entries to the original cell count (like the `fill=` of the stage names).
6. NewGame file list: the separator after the slot number is byte `0xCF` (the
   original middle dot), drawn by the English font as a small `*` ("1*   NOTHING").
   Suggest drawing `0xCF` as a middle dot or period (it is an alias in
   `tools/text/encoding_en.py`), or composing "1:". List composed in RAM
   `0x60B6`, drawn through `0x202FB0`. The DATA LOAD screen uses "1 :Lv-" and
   is fine.
7. DATA LOAD screen (no saves): multicolored sprite fragments under the header
   and under each "n :Lv- NOTHING" bar. Not compared with the original ROM yet;
   may be the original's behavior with empty slots.
8. Not reachable here: the monochrome-system notice (`0x28C7C3`, shown only on a
   black-and-white Neo Geo Pocket; check near `0x28C7A0`), game over (stage 0
   enemies never reached the HQ in 12,000 frames; losing the hero needs a battle
   state from explore-battle).

## Next steps

* Fix the patch layout (Critical 1) and add flash command emulation to the
  runtime (Critical 2); then rerun: Data -> Save to each file, the NewGame file
  list and DATA LOAD with saves (file details, "Lv" field, sprites), Load
  (confirmation, loading messages), saving over an existing file ("Overwrite
  this file?"), "Save complete.", Suspend -> power off -> title Continue (and its
  messages), and a block filling up (the erase path).
* Translate the five Monitor help texts; shorten the Suspend prompt to 2 lines;
  pad the save-bar VWF strings; decide on the `0xCF` glyph.
* Remaining tarot answer lists (13 of 20 not yet seen in play): rerun from
  `data-tarot_reading_start` with other A timings (e.g. A every 37 frames from
  33) and contact sheets of the frames just before each A.
* Compare the DATA LOAD sprites and the save bar with the original ROM.
* Game over: from a battle state of explore-battle, let the hero's unit lose;
  also check "Your headquarters has fallen to the enemy..." (`0x20A3C8`).
* Not done this round because the session's tool permission checks refused
  them: a private harness build with flash emulation (scratch only), further
  original-ROM comparison runs, more tarot runs and the idle-to-game-over run
  beyond 12,000 frames.
