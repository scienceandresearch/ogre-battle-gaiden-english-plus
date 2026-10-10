# Workstream: standalone Windows player

## Goal

`zenobia.exe`: a Windows player for the English game, built on our own emulation
core (`ngp_core`). Win32 window (GDI), waveOut audio, keyboard and XInput gamepad,
cartridge saves, save states, and the English BPS patch applied in memory at load
time. Win32 API only, C11, MSVC, no third-party libraries. A headless `--selftest`
mode lets agents and CI check it without a window.

## State

Round 1 done and integrated end to end with the BPS patch (2026-10-09,
integration pass). A folder holding only `zenobia.exe` and `ogre_en.bps` plays
the user's original ROM from anywhere on disk: the picture equals the harness
running `build/ogre_en.ngc`, in-game saves are written and loaded on the next
start, the window, sound and keyboard work, and the executable runs without
the Visual C++ Redistributable. Wrong ROMs, missing or damaged patches and
archives get clear messages. `runtime/src/frontend/tests/release_test.py`
repeats all of this in one command (40 checks, all pass).

Saving is release-ready since round 2 (2026-10-09): the patch keeps the
game's save blocks blank (`tools/patch/layout.py`; former open issue 1) and
the emulation core itself now emulates the flash chip and reports the right
chip size to the game (`core.md`; former open issues 2 and 3). 19 saves to
file 1 erase block 28 once, as on hardware, and the English text stays.

## Release package

### What a player needs

Exactly three files; nothing else is needed to play:

| File | Source | Notes |
|---|---|---|
| `zenobia.exe` | `build\zenobia.exe` from `build.bat` | x64, Windows 10/11. Self-contained: imports only Windows system DLLs (user32, gdi32, winmm, comdlg32, shell32, ole32, kernel32); the C runtime is linked in. About 360 KB. |
| `ogre_en.bps` | `build\ogre_en.bps` from `python -m tools.patch.build rom/baserom.ngc` | Must come from the same build as the `ogre_en.sha1` quoted in the release. Holds no ROM data (audited). |
| the player's ROM | the player's own dump | The original Japanese cartridge, 2,097,152 bytes, SHA-1 `5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`. Never shipped. Any file name and extension, any folder; not inside a .zip. |

The release zip also carries, for reading only: `README.txt` (the player steps
below and the controls), `LICENSE.txt`, `THIRD_PARTY_NOTICES.txt` (required:
`zenobia.exe` contains the Z80 core from `third_party/z80`, MIT, and the
MAME-derived TLCS-900/H timing table, BSD-3-Clause; their notices must ship
with the binary) and `ogre_en.sha1` (for people who patch with other tools;
see `patch-distribution.md`).

Never in the package: a ROM or patched ROM (`.ngc`, `.ngp`, `.npc`, any
2,097,152-byte file), save files (`.sav`), save states (`.state`),
`zenobia.ini`, `zenobia.pdb` (debug symbols with local paths), screenshots.

### Making the package (maintainer)

1. Clean build: `build.bat`, then `python -m tools.patch.build rom/baserom.ngc`.
   The build must print `patch audit: OK` and the layout report line `save
   blocks 3B0000-3EFFFF untouched` (the build refuses any patch byte there;
   check a finished ROM with `python -m tools.patch.layout build/ogre_en.ngc`).
2. Tests: `python -m tools.patch.test_bps rom/baserom.ngc` (11 tests) and
   `python runtime/src/frontend/tests/release_test.py ...` (40 checks, see
   "How to test"); optionally the GUI scripts.
3. Make a folder `ogre-battle-gaiden-en-vX.Y` with `zenobia.exe`,
   `ogre_en.bps`, `ogre_en.sha1` (all three from `build\`), `README.txt`,
   `LICENSE.txt`, `THIRD_PARTY_NOTICES.txt`; zip it.
4. Check the zip's file list against the list above (no other files).
5. In the release notes: version, date, the English ROM's SHA-1 (contents of
   `ogre_en.sha1`), known issues.

### Steps for the player (README text)

1. Download the zip and **extract all files** into a folder of your own, for
   example `Documents\Zenobia`. Do not start `zenobia.exe` from inside the zip
   (Windows would copy it alone to a temporary folder, without `ogre_en.bps`,
   and your saves would be lost) and do not use a write-protected folder such
   as `Program Files` (settings, saves and states are stored next to the
   program).
2. Start `zenobia.exe`. The program is not signed, so Windows SmartScreen may
   say "Windows protected your PC": click "More info", then "Run anyway".
3. Choose your Ogre Battle Gaiden ROM in the window that opens (or drop the
   file onto the player, or run `zenobia.exe "path\to\game.ngc"`). The game is
   translated while it loads; your ROM file is never changed. Next time the
   same ROM opens by itself.
4. Play (controls below; F1 shows them). The game's own saves go to `saves\`,
   save states (F5 / F9) to `states\`. To move to another PC, copy the whole
   folder.

If something is wrong, the player says what and how to fix it:
* "the English patch was not found": `ogre_en.bps` must be next to
  `zenobia.exe` (or next to the ROM).
* "the English patch could not be used ... damaged": download the release again.
* "This file is not the ROM this player expects", with the reason (a bad or
  modified dump, another game, the wrong size, a copy that was patched
  already) and the checksums of the right ROM.
* "This is a compressed archive": extract the `.ngc` file from the `.zip` first.

## User guide

### Build

`build.bat` (Visual Studio 2022 C++ tools, CMake, Ninja) builds
`build\zenobia.exe` next to `build\ngp_harness.exe`. The player is linked
against its own copy of the core compiled with the static C runtime
(`ngp_core_static`, `/MT`); `ngp_core` and `ngp_harness` keep the DLL runtime
and are unchanged.

### Run

* Start `zenobia.exe` and choose your ROM, drop the ROM file onto the window, or
  pass it on the command line: `zenobia.exe "path\to\game.ngc"`. The last ROM
  is remembered.
* The original Japanese cartridge (2,097,152 bytes, SHA-1
  `5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`) is translated while it loads with
  `ogre_en.bps`: `--patch FILE`, else the one next to `zenobia.exe`, else the
  one next to the ROM. Nothing is written to disk. An already patched English
  ROM (CRC32 = the patch's target) runs as is.
* Without a usable patch the player offers to run the game untranslated
  (default Yes). Any other file gets an explanation of what it most likely is
  and the question "Run this file anyway?" (default No), or, for a copy of this
  game that was already patched (the patch's code area at file offset
  0x170000 is not blank), "Run this file as it is?" (default Yes). Archives
  (.zip, .7z, .rar, .gz) are refused with "extract the ROM first".
* `zenobia.exe ROM --write-patched OUT.ngc` writes the patched ROM (for other
  emulators or flash carts) and exits; it refuses (exit 3, with the reason)
  anything but the original ROM with a usable patch or the English ROM itself.

### Controls (change them in `zenobia.ini`)

| Action | Keyboard | Gamepad (XInput) |
|---|---|---|
| D-pad | arrow keys | D-pad or left stick |
| A | Z | A or X |
| B | X | B or Y |
| Option | Enter or C | Start |
| Fast-forward (hold, about 5x, muted) | Tab | right trigger |
| Pause / resume | P or Pause | |
| Save / load state (current slot) | F5 / F9 | |
| Previous / next slot (0-9, shown in the title bar) | F6 / F7 | |
| Fullscreen (borderless) | F11 or Alt+Enter | |
| Reset (asks first) | F12 | |
| Open a ROM | Ctrl+O | |
| Show the controls | F1 | |
| Quit (writes the cartridge save first) | Esc | |

### Files the player creates (all next to `zenobia.exe`)

* `zenobia.ini`: settings, created with commented defaults when missing:
  `[video] scale` (window size, 1-12, default 4), `fullscreen`,
  `integer_scaling` (whole-number zoom when resized, default 1);
  `[audio] volume` (0-100); `[input]` one line per action with key names
  (`A`-`Z`, `0`-`9`, `F1`-`F24`, `Up`, `Enter`, `Space`, `Tab`, `Escape`,
  `Shift`, `LCtrl`, `Numpad0`, `Comma`...) or virtual-key codes (`65`, `0x41`),
  several per action separated by commas, empty = disabled; `[rom] last`;
  `[general] pause_when_inactive` (default 0). Delete it to restore defaults.
* `saves\<ROM file name>.sav`: the cartridge save (the game's own Save and
  Suspend), written about 2 s after the game saves and on exit. The previous
  file is kept as `.sav.bak` once per session. A damaged file is reported,
  only its complete records are loaded, and it is copied to `.bak` before the
  game saves again.
* `states\slot0.state` ... `slot9.state`: save states (shared by all ROMs; a
  state from a different ROM or patch version asks before loading). Note: when
  run from `build\`, these land in `build\states\` next to the agents' harness
  states (different names).

### Command line

```
zenobia [ROM] [--patch FILE] [--untranslated] [--console] [--log N]
        [--exit-after SECONDS] [--png FILE] [--png-scale N] [--no-flash-commands]
zenobia ROM --write-patched OUT [--patch FILE]
zenobia --selftest ROM [--patch FILE] [--frames N] [--input "F:BUTTONS:LEN;..."]
        [--png OUT.png] [--png-scale N] [--save FLASHFILE] [--untranslated]
        [--load-state FILE] [--load-state-at F FILE] [--save-state F FILE]
        [--no-flash-commands] [--write-patched OUT] [--log N]
zenobia --bps-apply SOURCE PATCH OUT
```

`--no-flash-commands` (window and selftest) makes the core ignore the game's
flash chip commands, the old behaviour: in-game saving then fails ("Could not
save."). `--console` shows core log messages (attaches to the calling console or opens
one; Ctrl+C or closing that console quits normally, saving first). Without it
a window start never attaches to a console. `--exit-after` runs the real
window and audio for that many seconds, then quits cleanly (flushes the save,
writes `--png`, prints statistics to stderr; no dialogs: questions get their
default answer, except that an unrecognised ROM runs as is with a warning, as
in `--selftest`). Exit codes: 0 ok, 1 usage, 2 ROM unreadable, 3 ROM refused
(or patch unusable), 4 a state operation failed, 5 write failed, 6 PNG
failed, 7 cartridge save failed, 10+n BPS error n.

Test hook: the environment variable `ZENOBIA_XINPUT="name.dll[,name.dll]"`
replaces the XInput DLL names tried (still from System32 only); a name that
does not exist simulates a PC without XInput (keyboard only).

`zenobia.exe` is a Windows-subsystem program: Git Bash waits for it and
captures its output; from PowerShell pipe it (`| Out-Host`) or use
`Start-Process -Wait`; from cmd use `start /wait` (batch files wait anyway).

## Done

* `runtime/src/frontend/` (CMake target `zenobia`, WIN32 subsystem, links
  `ngp_core_static` + user32 gdi32 winmm comdlg32 shell32 ole32; XInput loaded
  at run time):
  * `main.c` command line, ROM decision policy (`app_prepare_rom`),
    `--write-patched`, `--bps-apply`. `app.h` options and exit codes.
  * `gui.c` window, frame loop identical to the harness (set `g_input_state`,
    `ngp_run_frame`, drain `audio_render`, show `g_framebuffer`), pacing with
    QPC and a high-resolution waitable timer at the emulated rate (from the
    K2GE line count: 59.95 Hz) corrected by at most 0.3 % from the audio
    buffer level, hotkeys, borderless fullscreen, drag and drop, Open dialog,
    per-monitor DPI (keeps whole-number zoom across DPI changes), keeps running
    while the window is dragged, keeps the display awake while playing,
    pause when inactive, status messages in the title bar.
  * `video.c` GDI `StretchDIBits` (COLORONCOLOR = nearest neighbour),
    whole-number zoom or aspect fit, black borders, hint screen without ROM.
  * `audio.c` waveOut on its own thread: 4 x 10 ms device buffers, ring buffer
    (playback starts at 40 ms, trimmed above 100 ms, empty ring padded with a
    short fade), DC blocker, volume; muted while paused / fast-forwarding.
  * `input.c` key bindings (left/right modifiers), XInput 1.4 / 9.1.0 / 1.3
    from System32 only, empty pad slots polled every 2 s, opposite directions
    cancelled; `ZENOBIA_XINPUT` test hook.
  * `config.c` `zenobia.ini` (UTF-16 with BOM, Win32 profile API so comments
    survive), key-name parser.
  * `romload.c` SHA-1/CRC32 identification, patch search (`--patch`, next to
    the exe, next to the ROM), in-memory patching, diagnosis of unrecognised
    files (archive, no SNK header, another game by header title/ID, wrong
    size, already patched, other dump), loads the image exactly like
    `ngp_load_rom` (2 MB buffer, 0xFF fill), keeps a pristine copy.
  * `bps.c` BPS applier: SourceRead/TargetRead/SourceCopy/TargetCopy with signed
    relative offsets, every bound checked, source/target/patch CRC32 verified,
    numbers limited to 8 bytes, targets above 256 MiB refused (also when the
    caller passes no limit). `sha1.c`.
  * `saves.c` flash save (debounced: 2 s after the last flash write, at most
    10 s; temp file + rename; `.bak`), validated loading of the save file
    (`saves_load_flash_file`: every record checked before it is applied; used
    by the window and by `--selftest --save`), and save states: the core
    format plus a 44-byte trailer (`ZENOBST1`, core size, CRC32, ROM SHA-1,
    flash command state). Loading validates first (signature, size, trailer
    CRC, ROM identity), then backs up the running game (state in a temp file +
    ROM/flash image) and restores it if the core rejects the file. After a
    load, every flash block that differs from the pristine image is marked for
    the save file, so loading an old state never drops save data from it.
  * (round 1: `flashchip.c`, the flash chip's command interface and the
    BIOS chip-size fix-up; moved into the core in round 2, see below.)
  * `selftest.c` headless mode (same frame loop and input syntax as
    `ngp_harness`).
  * `zenobia.manifest` UTF-8 process code page (the core opens files with
    `fopen`: paths with any characters work), per-monitor DPI v2, Common
    Controls 6.
  * `tests/` regression scripts (below).
* `CMakeLists.txt`: the core's sources in `NGP_CORE_SOURCES`; with MSVC a
  second static library `ngp_core_static` (same sources, `/MT`) for the
  player, and `/INCREMENTAL:NO /OPT:REF /OPT:ICF` for it outside Debug.
* Flash chip emulation (round 1 in the player, round 2 in the core). The game
  never uses the BIOS flash calls. It copies its own routines to RAM
  (`0x366F02` program, `0x36711E` erase) and drives the chip with AMD-style
  sequences (unlock `AA`->5555, `55`->2AAA; `A0` + data byte;
  `80`,`AA`,`55`,`30` block erase; `F0` reset), then verifies by reading back.
  The core used to ignore these writes, so in-game saving always failed
  ("Could not save."). Round 1 emulated them in the player
  (`frontend/flashchip.c` on a core hook); since round 2 the core does it for
  every frontend (`runtime/src/core/flashchip.c`, on by default, see
  `core.md`) and the player only uses it: programs AND into the image and
  erases fill a block with FF, both through `flash_write_block` /
  `flash_erase_block`, so the blocks reach the save file. Verified: Data ->
  Save shows "Save complete.", the save file holds block 28, and after a
  restart the title menu offers Load (greyed out without the file).
* BIOS chip size (round 1: a player fix-up; round 2: the core). The HLE BIOS
  stored chip size code 1 (4 Mbit) at `0x6C58`. The game's erase routine
  picks the block address from a per-size table (`0x36700E`: 11, 19 or 35
  blocks) with it, so when a save block filled up it erased block 15
  (`0x2F0000`, game data) instead of block 28. The player used to write 3
  after every reset and state load; now the core's `bios.c` stores the
  cartridge's real codes (3 and 0 for this 2 MB game) at reset and corrects
  them whenever a state is loaded (older states hold 1), and the player's
  fix-up is gone. Only the game's flash routines read these bytes.
* Round 2 changes in the frontend (2026-10-09, task core-saves): the
  frontend `flashchip.c/.h` removed; `gui.c`, `selftest.c`, `saves.c`,
  `romload.c` use the core (`g_flash_commands`, `flashchip_state` for the
  state trailer, `g_rom_data_size`, `flash_mark_changed_blocks`);
  `--no-flash-commands` also in the window mode; a state load the core
  rejects also restores the chip's command state. Behaviour otherwise
  unchanged (all regression scripts below pass; the player and the harness
  give byte-identical pictures and save files for the same run).
* Integration pass (2026-10-09), fixes found by the end-to-end test:
  * The executable needed `VCRUNTIME140.dll` (Visual C++ Redistributable, not
    part of a clean Windows): now linked with the static C runtime.
  * A truncated or damaged save file was loaded partially (the core's
    `flash_load_save` returns success after a short read) with no warning:
    now checked record by record, reported, and never applied half.
  * Messages for unrecognised files said only "not the ROM this player
    expects"; they now say what the file most likely is. `--write-patched`
    with a wrong ROM printed "running it as is" before refusing; it now
    prints the reason and "nothing written".
  * `ogre_en.bps` next to the ROM is used when there is none next to the exe.
  * `.zip`/`.7z`/`.rar`/`.gz` files are recognised and refused with
    "extract the ROM first".
  * `bps_apply` with `max_target = 0` could try to allocate the size a
    damaged header declares: now limited to 256 MiB.

## How to test / reproduce

Build: `build.bat`; patch: `python -m tools.patch.build rom/baserom.ngc`.

**Release end-to-end test** (one command, about 20 s, opens a window twice):

    python runtime/src/frontend/tests/release_test.py --exe build/zenobia.exe
        --patch build/ogre_en.bps --rom rom/baserom.ngc --english build/ogre_en.ngc
        --harness build/ngp_harness.exe
        --save-state build/states/data-popup_save_prompt.state --work NEW_EMPTY_DIR

It copies `zenobia.exe` and `ogre_en.bps` into an otherwise empty folder and
checks (40 checks, all pass on the 2026-10-09 integration build and again on
the round 2 core-saves build with English ROM SHA-1 `272f13ab...`): only system
DLLs imported; the original ROM patched in memory gives the image SHA-1 of
`build/ogre_en.ngc` and frame 1499 byte-identical to `ngp_harness` on
`build/ogre_en.ngc`; the English ROM runs as is with the same picture;
`--write-patched` = `build/ogre_en.ngc`; `--bps-apply` and
`tools/patch/bps.py` give the same bytes; one byte changed / wrong size /
another game / not a ROM (headless: warned with the reason and run as is;
`--write-patched`: refused with the reason); `.zip` refused; missing patch
(names both places looked at); English ROM without the patch (recognised as
patched); patch next to the ROM used; damaged and truncated patch refused;
in-game save from `data-popup_save_prompt` (4096 bytes programmed, file holds
block 28); next start with that file: title menu offers Load, Load -> file 1
reaches the saved game ("The Zenobian Age" map; checked by eye: DATA LOAD
lists "1: Lv-1 Tristan", the HQ shows Unit 1, Char 3, Funds 30000); a
truncated save is reported and not applied; window mode 5 s twice (normal
and `ZENOBIA_XINPUT=xinput_missing_test.dll`): exit 0, waveOut 48 kHz, 300
frames in 5.01 s, 0 underruns, XInput 1.4 / "not available". Afterwards the
release folder holds only `zenobia.exe`, `ogre_en.bps` and `zenobia.ini`.

Other regression scripts (`runtime/src/frontend/tests`), all rerun on the
integration build and on the round 2 core-saves build (same results; the
core's own save checks are `runtime/src/core/tests/save_test.py`, see
`core.md`):

* `python runtime/src/frontend/tests/bps_test.py build/zenobia.exe WORK .`:
  26 cases (all four actions, overlapping and backward copies, multi-byte
  numbers, empty source/target, 17 malformed patches with the expected error,
  4 patches from `tools/patch/bps.py`): 26/26.
* `bash runtime/src/frontend/tests/state_test.sh build/zenobia.exe
  build/ngp_harness.exe EN_ROM JP_ROM NEW_DIR`: resumed runs equal the
  uninterrupted run (picture and state file), states move both ways between
  player and harness, 7 kinds of bad file leave the game byte-identical, a
  state from another ROM is detected: 33/33.
* `bash runtime/src/frontend/tests/rom_test.sh build/zenobia.exe JP_ROM_COPY
  build/ogre_en.bps build/ogre_en.ngc NEW_DIR`: patch policy, damaged/missing
  patch, unknown ROM, `--write-patched`, Greek and Cyrillic paths, `--help`:
  27/27.
* The BPS test vectors (`python -m tools.patch.test_bps --vectors DIR`) through
  `zenobia.exe --bps-apply`: 28/28 give the expected result (10 targets
  byte-identical, 18 rejected with the matching error class).
* GUI scripts (`tests/gui_*.ps1`, real window, keys posted to it; run them on a
  copy of `zenobia.exe` + `ogre_en.bps` in a scratch folder):
  `gui_save_test.ps1` 12/12, `gui_dialog_test.ps1` 14/14 (new message texts
  shown in the real dialogs), `gui_misc_test.ps1` 9/9, `gui_test.ps1` 21/21
  when run on a renamed copy (`zen_final_check.exe`). Run on a copy named
  `zenobia.exe` it gives 20/21: PersistentWindows (running on this machine)
  restores the last size it saw for `zenobia.exe` windows (1000x700, from the
  misc test), while a fresh name opens at 640x608 every time. The script now
  prints that hint. `gui_save_test.ps1` is timing-sensitive: its second run
  presses A about 0.3 s after F9 and quits 0.6 s later; once (round 2) the
  window ran only 92 frames in 1.94 s instead of about 116, the game did not
  save before Esc (0 bytes programmed) and the run gave 10/12 ("Esc wrote the
  pending save", ".bak"); the pre-change player passed on the same ROM and
  the two reruns gave 12/12. In the review it also gave 10/12 twice when
  the new window was not activated: the script sets `pause_when_inactive=1`,
  so the game stayed "Paused (inactive)" and did not save in time ("save
  file written after the quiet period", "title reports the write"); the
  pre-change player failed the same way there, and a third run gave 12/12.
  `gui_misc_test.ps1`'s fast-forward checks need a machine that is not
  busy (once 497 frames in 6 s instead of over 600; the rerun 1088).
* In-game save headless: `zenobia.exe --selftest ROM --load-state
  build\states\data-popup_save_prompt.state --input "10:A:2" --frames 600 --png
  S.png --save S.sav` shows "Save complete." and writes the flash file;
  `--no-flash-commands` reproduces the old behaviour ("Could not save."). The
  harness gives the same pictures in both modes.
* Repeated saves: `--load-state build\states\data-popup_save_prompt.state
  --input` `10:A:2` plus `c:A:2;c+100:A:2;c+200:A:2` for c = 400, 800, ...
  7200, `--frames 7700 --save S.sav` (19 saves to file 1): "77824 bytes
  programmed, 1 blocks erased" (block 28; the harness names it), the last
  screen reads "Save complete.", and the save file holds block 28 only, byte
  for byte the harness's file for the same run. (With the round 1 layout,
  12 saves erased the UI text kept in block 28.)

## Open issues

1. Resolved (round 2): patch data inside the game's save blocks. The game
   saves to flash blocks 27-30 (`0x3B0000` suspend, `0x3C0000` file 1,
   `0x3D0000` file 2, `0x3E0000` file 3); round 1 builds kept UI text in
   block 28 and tables in block 30, and about 12 saves to file 1 erased the
   UI text. The save-safe layout (`tools/patch/layout.py`: UI text
   `0x368000`, tables `0x3F0000`, a build check that refuses any byte in
   `0x3B0000-0x3EFFFF`) fixed it; verified with 19 saves on English ROM
   `272f13ab...` ("How to test"). Save files made with round 1 builds carry
   the old UI text in block 28/30 and should be deleted.
2. Resolved (round 2): HLE BIOS chip size. `runtime/src/core/bios.c` stores
   the cartridge's real codes (3 and 0 for this 2 MB game) and corrects them
   when a state is loaded (`core.md`).
3. Resolved (round 2): the harness emulates the game's flash commands (the
   core does, by default).
4. Untranslated and translated runs of the same ROM file share
   `saves\<name>.sav`. With the save-safe layout both images keep blocks
   27-30 blank, so the file holds only the game's own records in either case.
5. Not covered by automated tests: drag and drop (the handler is plain
   `WM_DROPFILES` code), a real gamepad (none connected; XInput loads, and the
   no-XInput path is tested with `ZENOBIA_XINPUT`), moving the window to a
   monitor with a different DPI, a PC without an audio device (the code runs
   silent with a title-bar note; not exercised).
6. `gui_test.ps1`'s window-size check fails while PersistentWindows runs (see
   "How to test"); run it on a renamed copy of the exe on such machines.
7. Flash emulation (now in the core) completes operations at once and has no
   autoselect (ID) mode; the game does not use it. Other core limits:
   `core.md` "Open issues".
8. The executable is unsigned (SmartScreen asks once). (Its icon and
   version resource were added in round 2, `release.md`.)

## Next steps

* Release: write `README.txt` from "Steps for the player" and the controls,
  then package as in "Making the package". A packaging script that builds and
  checks the zip would make this repeatable.
* Optional: an icon and version resource, code signing, SDL port for other
  platforms.
