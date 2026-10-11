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

Saving has been release-ready since round 2 (2026-10-09): the patch keeps the
game's save blocks blank (`tools/patch/layout.py`; former open issue 1) and
the emulation core itself now emulates the flash chip and reports the right
chip size to the game (`core.md`; former open issues 2 and 3). 19 saves to
file 1 erase block 28 once, as on hardware, and the English text stays.

Ease of use (2026-10-10, task player-zip): the game can be opened straight
from the `.zip` it usually comes in, everywhere a game file is accepted
(Open dialog, drag and drop, command line, `--selftest`, `--write-patched`,
the remembered last game), with the project's own zip reader and inflate
decoder (`zipread.c`, no third-party code). A menu bar (File: Open game,
Save English ROM, Exit; Help: Controls, About) makes the English ROM easy to
save for other emulators or a flash cart without the command line. The
client area is unchanged at every scale and the menu bar is hidden in
fullscreen; Alt and F10 still do not take keys from the game. Tests:
`zip_test.py` 59/59, `gui_menu_test.ps1` 37/37, and every earlier script
passes unchanged except `release_test.py`, whose ".zip refused" check now
checks that the zip opens (41/41 with a new `.7z` refusal check).

## Release package

### What a player needs

Exactly three files; nothing else is needed to play:

| File | Source | Notes |
|---|---|---|
| `zenobia.exe` | `build\zenobia.exe` from `build.bat` | x64, Windows 10/11. Self-contained: imports only Windows system DLLs (user32, gdi32, winmm, comdlg32, shell32, ole32, kernel32); the C runtime is linked in. About 410 KB. |
| `ogre_en.bps` | `build\ogre_en.bps` from `python -m tools.patch.build rom/baserom.ngc` | Must come from the same build as the `ogre_en.sha1` quoted in the release. Holds no ROM data (audited). |
| the player's ROM | the player's own dump | The original Japanese cartridge, 2,097,152 bytes, SHA-1 `5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`. Never shipped. Any file name and extension, any folder; also inside the `.zip` it came in (stored or deflate; not `.7z`/`.rar`/`.gz`). |

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
3. Choose your Ogre Battle Gaiden game file in the window that opens: the
   `.ngc` file, or the `.zip` it came in (no need to extract it). You can
   also drop the file onto the player, or run `zenobia.exe "path\to\game.zip"`.
   The game is translated while it loads; your file is never changed. Next
   time the same game opens by itself.
4. Play (controls below; F1 or Help > Controls shows them). The game's own
   saves go to `saves\`, save states (F5 / F9) to `states\`. To move to
   another PC, copy the whole folder.
5. To play the English version elsewhere (another emulator, a flash cart):
   File > Save English ROM (Ctrl+S). The Save dialog opens in your game
   file's folder with the name "Ogre Battle Gaiden - Prince of Zenobia
   (English).ngc"; the player checks the written file and confirms.

If something is wrong, the player says what and how to fix it:
* "the English patch was not found": `ogre_en.bps` must be next to
  `zenobia.exe` (or next to the ROM).
* "the English patch could not be used ... damaged": download the release again.
* "This file is not the ROM this player expects", with the reason (a bad or
  modified dump, another game, the wrong size, a copy that was patched
  already) and the checksums of the right ROM.
* A zip the player cannot read (password-protected, ZIP64, a compression
  method other than deflate): "Please extract the zip first: right-click it,
  choose Extract All, then open the extracted game file (.ngc)." A damaged or
  incomplete zip: "Copy or download it again."
* "This is a compressed archive (.7z, .rar or .gz)": extract the `.ngc` file
  first.

## User guide

### Build

`build.bat` (Visual Studio 2022 C++ tools, CMake, Ninja) builds
`build\zenobia.exe` next to `build\ngp_harness.exe`. The player is linked
against its own copy of the core compiled with the static C runtime
(`ngp_core_static`, `/MT`); `ngp_core` and `ngp_harness` keep the DLL runtime
and are unchanged.

### Run

* Start `zenobia.exe` and choose your ROM (File > Open game, Ctrl+O), drop
  the ROM file onto the window, or pass it on the command line:
  `zenobia.exe "path\to\game.ngc"`. Each of these also takes the `.zip`
  holding the ROM. The last ROM (or zip) is remembered.
* Zip files (`zipread.c`): the game file is the entry whose name ends in
  `.ngc`, `.ngp` or `.npc` (any case; when there are several, the one with
  the original ROM's CRC32 and size, else the largest), else the only or the
  largest file; directories are skipped. Stored (0) and deflate (8) entries
  are unpacked in memory (at most 4 MB, the largest Neo Geo Pocket ROM;
  `--unzip` allows 8 MB) and checked against their CRC32; the result goes
  through the same identification as a plain file. Encrypted entries
  (flag bits 0, 6, 13 or method 99), other methods (LZMA, BZIP2, Deflate64,
  ...), ZIP64 and split archives are refused with "Please extract the zip
  first: right-click it, choose Extract All, ..."; damaged zips (CRC32,
  invalid or truncated data, no end record) with "Copy or download it
  again". Names are UTF-8 (flag bit 11) or code page 437. An archive comment,
  data in front of the archive and data descriptors are fine. A file named
  `.zip` that holds no zip is identified like any other file. Messages name
  the zip and the file inside it; the cartridge save is named after the file
  inside (`saves\<its name>.sav`), so it stays the same when the zip is
  extracted.
* The original Japanese cartridge (2,097,152 bytes, SHA-1
  `5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`) is translated while it loads with
  `ogre_en.bps`: `--patch FILE`, else the one next to `zenobia.exe`, else the
  one next to the ROM. Nothing is written to disk. An already patched English
  ROM (CRC32 = the patch's target) runs as is.
* Without a usable patch the player offers to run the game untranslated
  (default Yes). Any other file gets an explanation of what it most likely is
  and the question "Run this file anyway?" (default No), or, for a copy of this
  game that was already patched (the patch's code area at file offset
  0x170000 is not blank), "Run this file as it is?" (default Yes). Other
  archives (.7z, .rar, .gz) are refused with "extract the ROM first".
* Menu bar (mouse only: Alt and F10 do not open it, so no key is taken from
  the game; hidden in fullscreen): File > Open game... (Ctrl+O), Save English
  ROM... (Ctrl+S), Exit (the quit key, Esc); Help > Controls (F1), About
  (version from the version resource, the game file and whether it runs in
  English, the folder of the settings and saves). The game waits while a
  menu is open (sound muted, keys released). The window is sized with
  `AdjustWindowRectExForDpi(..., bMenu)`, and grown further if the menu bar
  wraps onto two lines, so the client area is exactly what it was before
  the menu bar at every scale (checked against the previous build at scales
  1-12 on a 3840x2160 150 % monitor: identical).
* File > Save English ROM writes the image as it was loaded (the pristine
  copy, without in-game saves, which stay in `saves\`), the same bytes as
  `--write-patched`. The Save dialog (the common item dialog, so the folder
  can be set: `GetSaveFileName` ignores the folder of the proposed name and
  opens where Windows last saved for the program) opens in the game file's
  folder with the name "Ogre Battle Gaiden - Prince of Zenobia
  (English).ngc"; Windows asks before replacing a file. The player refuses
  to write over the game file (or zip) it is running, writes through a
  temporary file, reads the file back and checks its SHA-1 against the
  running image and its CRC32 against the patch's target, then confirms
  (path, size, CRC32, SHA-1); a file that does not read back the same is
  deleted. With no game loaded, an untranslated game or another ROM run as
  is, it explains why there is no English ROM to save instead.
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
| Open a game file, .ngc or .zip (File > Open game) | Ctrl+O | |
| Save the English ROM (File > Save English ROM) | Ctrl+S | |
| Show the controls (Help > Controls) | F1 | |
| Quit, writing the cartridge save first (File > Exit) | Esc | |

Ctrl+O, Ctrl+S, F1 and Alt+Enter are fixed; the other keys can be changed in
`zenobia.ini` (the fullscreen key there is F11).
The File > Exit item shows the first key bound to `quit`.

Menus: File (Open game, Save English ROM, Import saved game, Continue where I
left off, Exit), Options (Console date: the PC's date, 25 December, 6 June;
When the player starts: ask to continue, continue, start at the title
screen), Cheats (`runtime/src/core/cheats.h`: +100,000 goth, heal every
character, level up after the next battle, reputation +10 / -10), Help
(Controls, Player's guide, About).

* Import saved game: picks a `.sav` (the dialog opens in `Chapter saves`
  next to `zenobia.exe` when it exists), checks it (`saves_check_flash_file`:
  "NGPFLSH1", complete records, flash blocks 0x1B-0x1E only), flushes the
  current save, copies the current save file to
  `saves\<name> (before import YYYY-MM-DD HH-MM-SS).sav`, writes the imported
  file in its place and reloads the game (title screen; Load, file 1).
* Continue where I left off: quitting writes `states\resume.state` (the
  normal state format with the ROM's SHA-1); the next start with the same
  ROM asks to continue (`[general] resume=ask`), continues (`yes`) or does
  nothing (`no`). Runs without a window user (`--exit-after`, tests) neither
  write nor load it unless `--resume` is given.
* Console date: `g_rtc_month` / `g_rtc_day` in the core replace the date the
  BIOS RTCGET call reports (year and time of day stay the PC's). The game
  reads the clock only for two post-game recruits (code at `0x204EA9`: 25
  December and 6 June).
* Player's guide: opens `Player's Guide.html` next to `zenobia.exe` in the
  default browser.
* Cheats need a game in progress (`cheat_game_ready`: a plausible character
  list); they change RAM once, inside the game's own limits.

### Files the player creates (all next to `zenobia.exe`)

* `zenobia.ini`: settings, created with commented defaults when missing:
  `[video] scale` (window size, 1-12, default 4), `fullscreen`,
  `integer_scaling` (whole-number zoom when resized, default 1);
  `[audio] volume` (0-100); `[input]` one line per action with key names
  (`A`-`Z`, `0`-`9`, `F1`-`F24`, `Up`, `Enter`, `Space`, `Tab`, `Escape`,
  `Shift`, `LCtrl`, `Numpad0`, `Comma`...) or virtual-key codes (`65`, `0x41`),
  several per action separated by commas, empty = disabled; `[rom] last`;
  `[general] pause_when_inactive` (default 0), `console_date` (`MM-DD`, empty
  = the PC's date), `resume` (`ask`, `yes`, `no`; default `ask`). Delete it to
  restore defaults.
* `saves\<ROM file name>.sav`: the cartridge save (the game's own Save and
  Suspend), written about 2 s after the game saves and on exit. For a zip,
  the name of the game file inside it (folders in the zip and characters
  Windows does not allow in file names left out). The previous
  file is kept as `.sav.bak` once per session. A damaged file is reported,
  only its complete records are loaded, and it is copied to `.bak` before the
  game saves again.
* `saves\<ROM file name> (before import YYYY-MM-DD HH-MM-SS).sav`: the save
  as it was before File > Import saved game replaced it.
* `states\slot0.state` ... `slot9.state`: save states (shared by all ROMs; a
  state from a different ROM or patch version asks before loading). Note: when
  run from `build\`, these land in `build\states\` next to the agents' harness
  states (different names).
* `states\resume.state`: the session at the last quit (Continue where I left
  off).

### Command line

```
zenobia [ROM] [--patch FILE] [--untranslated] [--console] [--log N]
        [--exit-after SECONDS] [--png FILE] [--png-scale N] [--no-flash-commands]
        [--date MM-DD] [--resume ask|yes|no] [--import-save FILE]
zenobia ROM --write-patched OUT [--patch FILE]
zenobia --selftest ROM [--patch FILE] [--frames N] [--input "F:BUTTONS:LEN;..."]
        [--png OUT.png] [--png-scale N] [--save FLASHFILE] [--untranslated]
        [--load-state FILE] [--load-state-at F FILE] [--save-state F FILE]
        [--no-flash-commands] [--write-patched OUT] [--log N]
zenobia --bps-apply SOURCE PATCH OUT
zenobia --unzip ZIP OUT
```

ROM may be a `.zip` holding the game file in every form above.
`--unzip` writes the file the player would take from ZIP (chosen and
checked the same way, limit 8 MB) and prints which one; exit 30 + the zip
error code of `zipread.h` (31 read error, 32 damaged/incomplete, 33 split,
34 ZIP64, 35 no files, 36 encrypted, 37 other method, 38 too large, 39
damaged data, 40 CRC32 mismatch, 41 out of memory), 2 when the file cannot
be opened or is not a zip; it is also the test hook for the zip reader.

`--no-flash-commands` (window and selftest) makes the core ignore the game's
flash chip commands, the old behavior: in-game saving then fails ("Could not
save."). `--console` shows core log messages (attaches to the calling console or opens
one; Ctrl+C or closing that console quits normally, saving first). Without it
a window start never attaches to a console. `--exit-after` runs the real
window and audio for that many seconds, then quits cleanly (flushes the save,
writes `--png`, prints statistics to stderr; no dialogs: questions get their
default answer, except that an unrecognized ROM runs as is with a warning, as
in `--selftest`). Exit codes: 0 ok, 1 usage, 2 ROM unreadable (also a zip
that cannot be used), 3 ROM refused (or patch unusable), 4 a state operation
failed, 5 write failed, 6 PNG failed, 7 cartridge save failed, 10+n BPS
error n, 30+n zip error n (`--unzip`).

`--date MM-DD` sets the console date for this run (window and selftest),
`--resume` the start behavior for this run (also without a window), and
`--import-save FILE` imports a saved game before playing (no questions; exit
7 if the file is refused). `runtime/src/frontend/tests/extras_test.py` covers
the three, and the cheats through the harness.

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
  * `video.c` GDI `StretchDIBits` (COLORONCOLOR = nearest neighbor),
    whole-number zoom or aspect fit, black borders, hint screen without ROM.
  * `audio.c` waveOut on its own thread: 4 x 10 ms device buffers, ring buffer
    (playback starts at 40 ms, trimmed above 100 ms, empty ring padded with a
    short fade), DC blocker, volume; muted while paused / fast-forwarding.
  * `input.c` key bindings (left/right modifiers), XInput 1.4 / 9.1.0 / 1.3
    from System32 only, empty pad slots polled every 2 s, opposite directions
    canceled; `ZENOBIA_XINPUT` test hook.
  * `config.c` `zenobia.ini` (UTF-16 with BOM, Win32 profile API so comments
    survive), key-name parser.
  * `romload.c` SHA-1/CRC32 identification, patch search (`--patch`, next to
    the exe, next to the ROM), in-memory patching, diagnosis of unrecognized
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
  restart the title menu offers Load (grayed out without the file).
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
  rejects also restores the chip's command state. Behavior otherwise
  unchanged (all regression scripts below pass; the player and the harness
  give byte-identical pictures and save files for the same run).
* Zip files and the menu bar (2026-10-10, task player-zip):
  * `zipread.c/.h` (new, original code, MIT): end record search (the last
    record whose comment ends at the end of the file first, then any;
    data in front of the archive handled by the offset shift), central
    directory (at most 16 MB), entry choice, local header, stored and
    deflate entries, CRC32 (`bps_crc32`), clear error classes. The inflate
    decoder (RFC 1951): stored, fixed and dynamic blocks, a 9-bit lookup
    table plus a short list for longer codes, every length, distance and
    table bound checked, incomplete codes accepted only where encoders
    produce them (no code, or one 1-bit code), exactly like zlib. The
    archive is read through a callback, so only the end, the directory and
    the chosen entry are read, whatever the zip's size.
  * `romload.c`: `unzip_game` (Win32 file reader for `zipread`), zip
    messages, messages naming the zip and the file inside (`shown_path`),
    `ZipPick` in `RomPrep`, `rom_prep_is_english`, `rom_image`, `rom_unzip`;
    the archive message now lists only .7z, .rar and .gz.
  * `gui.c`: menu bar, `WM_COMMAND`/`WM_ENTERMENULOOP`/`WM_EXITMENULOOP`,
    Ctrl+S, Save English ROM (`IFileSaveDialog` with `SetFolder`, classic
    dialog as fallback; read-back check), About (version read from the
    version resource), menu-aware window sizing and fullscreen, save file
    named after the file in the zip, Open dialog filter with `*.zip`, new
    hint and controls texts. `input.c`: `input_key_down` (Ctrl seen by the
    window, so posted test keys work like real ones). `main.c`: `--unzip`,
    usage text. `selftest.c`: prints `zip entry NAME (method, packed size)`.
  * Verified beyond the scripts (scratch, not committed): the inflate
    decoder against zlib on 25,255 streams (zlib at every level, strategy,
    window size and flush mode; an independent encoder's stored, fixed and
    dynamic blocks; 3 mutated copies of each), with identical verdict and
    output in every case, built with AddressSanitizer; the archive layer on
    64,800 valid and mutated zips under AddressSanitizer, no fault; the
    owner's own zip of the game (a `.url` file next to the `.ngc`) opens and
    gives the English image.
* Integration pass (2026-10-09), fixes found by the end-to-end test:
  * The executable needed `VCRUNTIME140.dll` (Visual C++ Redistributable, not
    part of a clean Windows): now linked with the static C runtime.
  * A truncated or damaged save file was loaded partially (the core's
    `flash_load_save` returns success after a short read) with no warning:
    now checked record by record, reported, and never applied half.
  * Messages for unrecognized files said only "not the ROM this player
    expects"; they now say what the file most likely is. `--write-patched`
    with a wrong ROM printed "running it as is" before refusing; it now
    prints the reason and "nothing written".
  * `ogre_en.bps` next to the ROM is used when there is none next to the exe.
  * `.zip`/`.7z`/`.rar`/`.gz` files are recognized and refused with
    "extract the ROM first" (`.zip` files are opened since 2026-10-10).
  * `bps_apply` with `max_target = 0` could try to allocate the size a
    damaged header declares: now limited to 256 MiB.

## How to test / reproduce

Build: `build.bat`; patch: `python -m tools.patch.build rom/baserom.ngc`.

The release end-to-end test is one command (about 20 s; it opens a window
twice):

    python runtime/src/frontend/tests/release_test.py --exe build/zenobia.exe
        --patch build/ogre_en.bps --rom rom/baserom.ngc --english build/ogre_en.ngc
        --harness build/ngp_harness.exe
        --save-state build/states/data-popup_save_prompt.state --work NEW_EMPTY_DIR

It copies `zenobia.exe` and `ogre_en.bps` into an otherwise empty folder and
checks (40 checks, all pass on the 2026-10-09 integration build and again on
the round 2 core-saves build with English ROM SHA-1 `272f13ab...`; 41 since
the zip support, 41/41 on English ROM `4fe9c5ff...`): only system
DLLs imported; the original ROM patched in memory gives the image SHA-1 of
`build/ogre_en.ngc` and frame 1499 byte-identical to `ngp_harness` on
`build/ogre_en.ngc`; the English ROM runs as is with the same picture;
`--write-patched` = `build/ogre_en.ngc`; `--bps-apply` and
`tools/patch/bps.py` give the same bytes; one byte changed / wrong size /
another game / not a ROM (headless: warned with the reason and run as is;
`--write-patched`: refused with the reason); a `.zip` of the ROM opens and
gives the English image, a `.7z` is refused; missing patch
(names both places looked at); English ROM without the patch (recognized as
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
* `python runtime/src/frontend/tests/zip_test.py --exe build/zenobia.exe
  --rom rom/baserom.ngc --patch build/ogre_en.bps --english build/ogre_en.ngc
  --work NEW_DIR` (about 5 s; every zip is made at test time from the ROM in
  WORK): 17 zips that must give the English image with `--selftest`
  (zipfile stored and deflate; raw deflate at levels 0/1/9 and the fixed,
  Huffman-only, run-length and filtered strategies; a `.url` next to the
  game; the game in a folder as `.NGC`; no ROM name; two ROM names, the
  original chosen by CRC32; comment and data in front; data descriptor;
  UTF-8 and code page 437 names), `--write-patched` and `--unzip` from zips,
  Greek and Cyrillic paths; 9 payloads from an independent deflate encoder
  in the script (single one-bit distance code, distance 32768 with length
  258 as code 284, empty blocks, stored data over 65,535 bytes, long codes,
  fixed codes only) through `--unzip`; refusals with message and exit code:
  bad CRC32, damaged deflate data, truncated file, encrypted flag, LZMA,
  BZIP2, ZIP64 archive and entry, split archive, empty zip, folder only, a
  5 MB file (too large for a ROM), the 8 MB `--unzip` limit (8 MB passes, one
  byte more is refused), an encrypted zip with `--write-patched` (nothing
  written), a zip in the zip, a non-zip named `.zip`, `.7z`: 59/59.
* `gui_menu_test.ps1 -AppDir DIR -ExeName NEW_NAME.exe -Rom JP_ROM -English
  EN_ROM -Out DIR` (real windows, about 35 s; makes its zip with .NET's zip
  writer): the Open dialog takes the zip and it runs; it is remembered and
  opens by itself on the next start; the menu texts and shortcuts; client
  480x456 at scale 3; Alt and F10 enter no menu mode (Down + Enter after
  them open no menu item and no dialog), F5/F9 still work; F1
  and Help > Controls; About; Save English ROM proposes the English name in
  the zip's folder, writes the English ROM (SHA-1 checked) and confirms;
  Ctrl+S opens it, Cancel writes nothing; saving over the zip: Windows asks,
  then the player refuses and the zip stays unchanged; F11 hides the menu bar
  and fills the monitor, F11 again restores menu, window and client area;
  File > Exit quits with exit 0; the explanations with no game and
  untranslated; client 176x152 (scale 1, Windows' minimum window width, as
  before the menu), 320x304 and 640x608 at scales 2 and 4, each started
  under a new exe name: 37/37. Use a new exe name: PersistentWindows
  otherwise restores the size of the first window for later starts.
* `gui_save_test.ps1` with `-Rom` a zip whose game file has the zip's name
  (`Ogre Zip Test.zip` holding `Ogre Zip Test.ngc`): 12/12, so in-game
  saving works when playing from a zip (`saves\Ogre Zip Test.sav`); with
  `mygame.zip` holding `roms/Ogre (J).ngc` the file is `saves\Ogre (J).sav`.
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
  With the menu bar (2026-10-10) all four pass unchanged: `gui_test.ps1`
  21/21 on a renamed copy (client 640x608, F11 / Alt+Enter restore the same
  window), `gui_dialog_test.ps1` 14/14, `gui_misc_test.ps1` 9/9 (1084
  frames in 6 s), `gui_save_test.ps1` 12/12.
* With the extras (2026-10-11): `gui_extras_test.ps1 -AppDir DIR -ExeName
  NEW_NAME.exe -Rom JP_ROM -State GAME_STATE -Save CHAPTER_SAVE -Out DIR`
  (new, real windows, about 40 s): the menu bar File, Options, Cheats, Help
  and the Options and Cheats items; the check marks and `zenobia.ini`
  values of Console date and When the player starts; without a game in
  progress the cheats, Continue where I left off and (with no guide next to
  the exe) Help > Player's guide explain themselves; a game in progress
  loaded with F9 and paused takes each cheat (title messages, then a state
  saved with F5 holds +100,000 goth, the same reputation after +10 and -10,
  and experience 99); quitting writes `states\resume.state`; the next start
  asks and Yes continues; File > Continue asks first; File > Import saved
  game opens in `Chapter saves`, asks, replaces the save, keeps the old one
  as "(before import ...)" and restarts: 28/28. `gui_menu_test.ps1` now
  expects the new menu bar and `gui_dialog_test.ps1` writes `resume=no`
  first (their restarts must not meet the question): 37/37 and 14/14;
  `gui_misc_test.ps1` 9/9, `gui_save_test.ps1` 12/12, `gui_test.ps1` 21/21
  on a renamed copy.
* In-game save headless: `zenobia.exe --selftest ROM --load-state
  build\states\data-popup_save_prompt.state --input "10:A:2" --frames 600 --png
  S.png --save S.sav` shows "Save complete." and writes the flash file;
  `--no-flash-commands` reproduces the old behavior ("Could not save."). The
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
   `WM_DROPFILES` code calling the same `load_rom` as the Open dialog, which
   is tested with a zip), a real gamepad (none connected; XInput loads, and the
   no-XInput path is tested with `ZENOBIA_XINPUT`), moving the window to a
   monitor with a different DPI, a PC without an audio device (the code runs
   silent with a title-bar note; not exercised), the menu bar wrapping onto
   two lines (very large text on a narrow window: `size_window` adds the
   difference; not seen at 150 %, where even scale 1 keeps one line), the
   classic Save dialog fallback (used only if the common item dialog cannot
   be created).
6. `gui_test.ps1`'s window-size check fails while PersistentWindows runs (see
   "How to test"); run it on a renamed copy of the exe on such machines.
7. Flash emulation (now in the core) completes operations at once and has no
   autoselect (ID) mode; the game does not use it. Other core limits:
   `core.md` "Open issues".
8. The executable is unsigned (SmartScreen asks once). (Its icon and
   version resource were added in round 2, `release.md`.)
9. Zip limits by design: no ZIP64, encryption, split archives or methods
   other than stored and deflate (each refused with "Please extract the zip
   first"); the game file must be at most 4 MB unpacked. `.7z`, `.rar` and
   `.gz` are still refused. A zip of the player release itself (no `.ngc`
   inside) is identified as "not a Neo Geo Pocket ROM ... this is the largest
   file in it".

## Next steps

* Release: write `README.txt` from "Steps for the player" and the controls,
  then package as in "Making the package". A packaging script that builds and
  checks the zip would make this repeatable.
* Optional: an icon and version resource, code signing, SDL port for other
  platforms.
