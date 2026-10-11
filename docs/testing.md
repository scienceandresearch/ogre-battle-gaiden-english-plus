# Testing

Tests that need the game read your own copy from `rom/baserom.ngc` (SHA-1
`5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`). They write to `build/`, to a
temporary folder, or to a new folder that you name (`--work NEW_DIR` or
`WORKDIR` below). Nothing a test makes from the game belongs in a commit.

## Build

```
build.bat                                    # builds build/ngp_harness.exe and build/zenobia.exe (MSVC + CMake + Ninja)
python -m tools.patch.build rom/baserom.ngc [--no-gfx]  # -> build/ogre_en.ngc, .bps, .sha1, symbols.txt; layout check
```

The patch build is the first test. It checks that every text fits its window
or field (widths, lines, cells, and the rule that the last page of a Yes/No
question has at most two lines), refuses Japanese characters in the `.txt`
files under `translation/en/` and `assets/`, refuses any byte written into
the game's save blocks, and audits the patch: its literal data must not
contain 8 or more bytes in a row from the original game. Each error says what
to fix: a file and line, a message address, or a ROM address.

## Test suites

Build first: `test_bps`, `test_webpatcher` and `test_package` also read the
files in `build/` (without the English ROM, `test_bps` skips 4 of its 11
tests).

```
python -m tools.patch.test_bps rom/baserom.ngc                   # BPS encoder/decoder/audit tests
python -m tools.gfx.test_all rom/baserom.ngc                     # graphics library + build integration tests
python -m tools.text.test_tables rom/baserom.ngc                 # packed tables, copy tables and their database rows
python -m tools.text.check translation/en/script.txt            # English layout check
python -m tools.asm.test_roundtrip rom/baserom.ngc               # assembler self-test: prints ok/failed counts (failed must be 0)
python -m tools.patch.layout build/ogre_en.ngc                   # region usage; refuses bytes in the save blocks
python -m tools.release.test_package --work NEW_DIR              # release packager and each of its refusals
python -m tools.release.test_webpatcher rom/baserom.ngc          # the web patcher page, run in Node.js
```

The web patcher test needs Node.js for its full run and skips those cases
without it.

## Player and emulator core

These run the built programs, so build first. Use a new, empty folder for
`--work` each time.

```
python runtime/src/core/tests/save_test.py --harness build/ngp_harness.exe --rom build/ogre_en.ngc --states build/states --work NEW_DIR
python runtime/src/frontend/tests/release_test.py --exe build/zenobia.exe --patch build/ogre_en.bps --rom rom/baserom.ngc --english build/ogre_en.ngc --harness build/ngp_harness.exe --save-state build/states/data-popup_save_prompt.state --work NEW_DIR
python runtime/src/frontend/tests/zip_test.py --exe build/zenobia.exe --rom rom/baserom.ngc --patch build/ogre_en.bps --english build/ogre_en.ngc --work NEW_DIR
python runtime/src/frontend/tests/extras_test.py --exe build/zenobia.exe --rom rom/baserom.ngc --english build/ogre_en.ngc --harness build/ngp_harness.exe --states build/states --work NEW_DIR
python runtime/src/frontend/tests/bps_test.py build/zenobia.exe WORKDIR [REPO_ROOT]
bash runtime/src/frontend/tests/rom_test.sh ZENOBIA_EXE JAPANESE_ROM PATCH ENGLISH_ROM WORKDIR
bash runtime/src/frontend/tests/state_test.sh ZENOBIA_EXE HARNESS_EXE ENGLISH_ROM JAPANESE_ROM WORKDIR
```

`save_test.py` and `release_test.py` load the states
`data-popup_save_prompt`, `data-cmdbar_suspend` and `stage0_selected` from
`build/states/`. A fresh clone has none of them: "Useful states" below shows
how to reach `stage0_selected`, and
[explore-data.md](workstreams/explore-data.md) gives the inputs for the other
two. `extras_test.py` (console date, continuing where you left off, importing
a saved game, the cheats) also loads `r2-story-early-s6_cleared_scenario_map`
and `battle-gring_fight_banner`.

The PowerShell scripts `gui_*.ps1` in the same folder drive the player's real
window with key presses (window size, full screen, menus, dialogs, saving) and
open real windows for up to a minute. Each one explains its parameters in its
first lines. Run them from a copy of `zenobia.exe` in a scratch folder,
because the player writes saves, states and `zenobia.ini` next to itself.

## Chapter saves

```
python -m tools.release.catalog    # build/catalog/*.sav and catalog.json, from tools/release/catalog.txt
```

The recipe `tools/release/catalog.txt` names one machine-local state per
save. For each, the tool names the hero Tristan, saves through the game's own
menu (scenario map popup: Data > Save > OK), loads the result from the title
screen in a fresh run and compares the army, funds, cleared chapters and
name, and checks that the save holds file 1 only and no run of 16 or more
bytes (with at least 4 different values) from the original game. It writes
nothing unless every save passes. The package takes the saves from
`build/catalog/`.

The saves of chapters 8 to 12 and after the ending come from one playthrough
that went on from `r2-story-early-s6_cleared_scenario_map` to both routes:
the `play-norodom-*` and `play-megaholten-*` states (scenario map with the
popup closed, so their recipe lines press B first). The same playthrough
left `play-norodom-final-before-baldur` (the hero's unit about 70 frames
before it reaches Orma in the Final Chapter; the HQ is under attack, so
move on quickly). Its only aid was enemy HP set to 1 when a battle starts.

## Text and localization tools

```
python -m tools.text.dump rom/baserom.ngc build/script_ja.txt   # local Japanese script (not committed)
python -m tools.text.extract rom/baserom.ngc                     # inventory stats (+ build/strings_missed.txt)
python -m tools.text.l10n export rom/baserom.ngc                 # localization DB + CSV (build/l10n/, local only)
python -m tools.text.l10n import review.csv [--apply]            # apply a reviewer's CSV (docs/localization.md)
python -m tools.gfx.apply IN.ngc OUT.ngc --target NAME           # one graphics target on a copy of a ROM
```

## The test harness

`build\ngp_harness.exe` runs the game without a window: scripted input,
screenshots, save states, text logs and memory traces. It does not create the
`--out` folder, so make it first.

```
build\ngp_harness.exe build\ogre_en.ngc --frames 4200 --shot-every 60 --out <dir> --input "<frame>:<buttons>:<len>;..."
```

`--input` takes `frame:buttons:length` entries separated by semicolons. The
buttons are U D L R A B and O (Option).

To reach the HQ status screen from power-on, accepting the default name
(about 9,000 frames), press A every 40 frames from frame 700 and Option at
frame 900: `--input "700:A:2;740:A:2;...;8980:A:2;900:O:2"`. From there, B
three times (about 200 frames apart) reaches the scenario map with its popup
open on Organize; a fourth B closes the popup. This command prints that list:
`python -c "print(';'.join('%d:A:2' % f for f in range(700, 9000, 40)) + ';900:O:2')"`.

The harness has no help text; these are all of its options (frame lists
are comma-separated, addresses hex):

* Running: `--frames N` (default 600), `--input ...`, `--tps 1|2`,
  `--log N`, `--load-state FILE`, `--save-state F FILE`.
* Pictures and dumps: `--out DIR` (default: the current folder),
  `--shot F,F,...`, `--shot-every N`, `--vram F,F,...` (memory dumps for
  `tools.gfx.vram`), `--dump-ram FILE`, `--ram-usage FILE`.
* Logs and traces: `--text-log FILE` (what the text renderers draw),
  `--vm-log FILE`, `--trace FILE`, `--prof lo-hi`, `--watch R:lo-hi` or
  `--watch W:lo-hi` (up to 16), `--watch-frames A-B`, `--watch-log FILE`.
* Memory and saves: `--poke ADDR=HEX[,ADDR=HEX...][@FRAME]` writes RAM bytes
  after `--load-state`; `--save FILE` keeps the cartridge save in the same
  `.sav` format as the player (saving, Suspend and Continue work);
  `--no-flash-commands`; `--dump-flash FILE`.
* The player's extras: `--cheat NAME[@FRAME]` applies one of the player's
  cheats (`goth`, `heal`, `level`, `rep+`, `rep-`; `runtime/src/core/cheats.h`),
  repeatable; `--date MM-DD` sets the date the BIOS clock reports (the year
  and time of day stay the PC's).

Graphics checks: `python -m tools.gfx.harness run|poke|diff|sheet` and
`python -m tools.gfx.vram render|bytes|map|find|queue`. `tools.gfx.harness
run` creates the `--out` folder and finds the harness through `--exe`, else
the `NGP_HARNESS` environment variable, else
`build\ngp_harness.exe`. `tools.gfx.vram` reads the memory dumps that
`--vram` writes.

In the game, B backs out, Option shows command help, and Right/Left move
between command icons. On the scenario map, B toggles a popup with Organize,
Monitor, Data and Link; Data opens Save and Load.

Useful states (in `build/states/`; recreate them as described):

* `name_entry_grid.state`: the name entry screen.
* `hq_status_screen.state`: the HQ status screen after the tarot (the
  9,000-frame input above).
* `scenario_map_cursor_on_stage0.state`: the "The Zenobian Age" scenario map
  (B from HQ backs out to it). Pressing A at the stage marker does nothing;
  from this state, `--input "10:R:12;27:D:12;54:A:2"` moves to the hotspot
  and selects it, which gives `stage0_selected.state`.
* `stage0_selected.state`: the chapter title card, then the opening scenes of
  stage 0.
* `stage0_gameplay.state`: stage 0 in real-time play (advance the opening with
  A, but answer the "Hear it again?" prompts with B).
* `title_menu.state`: the title menu (NewGame / Load / Continue).
* `command_bar_forecast.state`: the map command bar on "Income forecast"; A
  opens the finance window.
* `scenario_popup_link.state`: the scenario map popup.
* `hq_menu_location_icon.state`: from `stage0_gameplay.state` with
  `--input "46:A:2;80:D:2"` (A on HQ opens a small menu with NEXT, the unit
  and the location; Down selects the location icon). A then opens the town
  window. A on an empty map spot opens the command bar (NEXT / Organize /
  Items / Tarot / Income forecast / Monitor / Suspend).

## Test states

The states in `build/states/` are machine-local (not committed); about 390 of
them cover every stage, ending and system. A state keeps the video memory of
the build it was saved with: for example, `title_menu.state` shows the old
logo until the title screen is loaded again. A state saved in the middle of a
dialogue holds pointers into the dialogue pages of its build, so it can crash
after a rebuild that moves those pages. Record such states again, or relocate
them with `build/handoff/r3/stalescan.py` and `relocate.py` (machine-local
tools of the maintainer).
