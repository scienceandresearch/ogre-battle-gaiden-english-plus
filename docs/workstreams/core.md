# Workstream: emulation core (cartridge saves, BIOS, harness)

## Goal

The emulation core (`runtime/src/core/`) behaves like the hardware wherever
the game depends on it, and the same way in the headless harness
(`ngp_harness`, the agents' test tool) and in the player (`zenobia.exe`).
Round 2 task "core-saves": in-game saving works everywhere (the cartridge
flash chip's command interface and the BIOS flash chip size codes), and the
harness can change memory (`--poke`).

## State

Done (2026-10-09). The game saves, loads, suspends and continues in the
harness as in the player, and both give byte-identical pictures and save
files for the same run. Runs that do not save are byte-identical to the
previous harness (281 screenshots and text logs). All player regression
scripts pass on the rebuilt player. New one-command check:
`runtime/src/core/tests/save_test.py` (33 checks, about 11 s).
Independent review (same day): acceptance a-e re-run with the same
results; all 209 states in `build/states` (90 frames with A and B) give the
same screenshots and text logs as the previous harness, the RAM differing
only in the chip size byte (the one state that saves aside). The review
added the `--save` overwrite note to open issue 4 and open issues 5 and 6.

## Done

1. **BIOS flash chip size codes** (`bios.c`). The BIOS records each flash
   chip's size in its work area: `0x6C58` for the chip at `0x200000` (CS0),
   `0x6C59` for a second chip at `0x800000` (CS1); 0 = none, 1 = 4 Mbit
   (512 KB, 11 blocks), 2 = 8 Mbit (1 MB, 19 blocks), 3 = 16 Mbit (2 MB,
   35 blocks). The encoding is the one the game relies on: its flash
   routines index a table of three block-address tables with `code - 1`
   (`0x36700E` -> `0x36701A` / `0x367046` / `0x367092`), which hold the
   start offsets of the 11, 19 and 35 blocks of 4, 8 and 16 Mbit boot-block
   chips. The core used to store 1 (a value copied from older emulators), so
   for this 2 MB cartridge the erase of block 28 (save file 1) read entry 28
   of the 4 Mbit table, i.e. entry 17 of the 8 Mbit table, `0xFA000`, and
   erased block 15 (`0x2F0000`, game data). The code now follows the
   cartridge size: the smallest chip that holds the data (up to 512 KB: 1;
   up to 1 MB: 2; up to 2 MB: 3), and above 2 MB a second chip sized the
   same way from the bytes beyond 2 MB.

   | Cartridge data | `0x6C58` | `0x6C59` |
   |---|---|---|
   | 512 KB or less | 1 | 0 |
   | up to 1 MB | 2 | 0 |
   | up to 2 MB (this game) | 3 | 0 |
   | 3 MB | 3 | 2 |
   | 4 MB (32 Mbit, two 16 Mbit chips) | 3 | 3 |

   The size is `g_rom_data_size` (new in `ngp.h`: the ROM file or patched
   image size; `ngp_load_rom` sets it, the player's `rom_install` too; 0
   means `g_rom_size`). The codes are written at reset (`bios_boot`) and
   again whenever a state is loaded (`bios_state`), because every state made
   before this change holds 1. Only the game's flash routines read these
   bytes: `--watch R:6C58-6C59` over 9000 frames from power-on and 1500
   frames from five states shows no access; the save path reads them at
   `0x366EAD`/`0x366EE5`.
2. **Flash chip command interface in the core** (`flashchip.c`/`.h`,
   moved from `runtime/src/frontend/`). The game does not save through the
   BIOS: it copies its own routines to RAM (program loop from `0x366F02`,
   erase from `0x36711E`) and drives the chip with AMD-style sequences:
   unlock `AA` -> base+`5555`, `55` -> base+`2AAA`; `A0` + data byte
   (program, ANDed into the image); `80`, `AA`, `55`, `30` at a block address
   (block erase; `10` at `5555` = chip erase); `F0` = read mode. Operations
   complete at once, so the game's read-back verify passes. Programs and
   erases go through `flash_write_block`/`flash_erase_block`, which record
   the block for the save file. On by default (`g_flash_commands = true`);
   `false` restores the old behavior (writes logged and ignored, "Could not
   save."). The chip returns to read mode at `ngp_reset` and when a state is
   loaded. Statistics: `flashchip_programs()`, `flashchip_erases()`,
   `flashchip_block_erases(chip, block)`. `g_flash_command_hook` stays as an
   optional override (NULL; nothing uses it now). Block geometry is shared:
   `FLASH_BLOCKS`, `flash_block_range`, `flash_block_of` in `ngp.h`.
3. **Save files** (`flash.c`). Harness and player already wrote the same
   format (below); now they also read it the same way: `flash_load_save`
   checks every record completely before applying it (returns 1 loaded,
   0 no file, -1 damaged/unreadable: the complete records before the damage
   are loaded), like the player's `saves_load_flash_file`. A state load
   replaces the core's record of written blocks with the state's; the new
   `flash_mark_changed_blocks(pristine)` marks every block that differs from
   the unmodified image again, so save data loaded from the file is not
   dropped from it (used by the harness after `--load-state` with `--save`,
   and by the player's `mark_changed_blocks`, which did the same before).
   `flash_store_save` also reports a failed `fclose`.
4. **Harness** (`runtime/src/tools/harness.c`):
   * `--poke ADDR=HEX[,ADDR=HEX...][@FRAME]` (repeatable): bytes in memory
     order (`5490=05`, `6000=30750000`, one digit = one byte, `0x` prefixes
     allowed) written into the 64 KB low memory (`g_lowmem`) before frame
     FRAME; default 0 = right after `--load-state` (also with `--frames 0`).
     Plain stores: right for RAM `0x4000-0x7FFF` and video memory
     `0x8000-0xBFFF`; the I/O registers `0x00-0xFF` are not read from that
     array. Bad specs exit 1; a FRAME beyond `--frames` gives a warning.
     Each poke is printed to stderr when applied.
   * `--no-flash-commands`: the old behavior.
   * `--dump-flash FILE`: the cartridge image as the game sees it after the
     run (same size as the ROM file), to compare with the ROM.
   * `--save FILE`: loaded before `--load-state` (a damaged file is reported:
     `warning: flash save ... is damaged ...`), its blocks kept across the
     state load, written at the end when the game wrote to the flash
     (`flash save written: FILE (blocks 28)`; exit 1 if it cannot be
     written).
   * stderr summary when the flash was used: `flash: 77824 bytes programmed,
     1 blocks erased (chip 0 block 28 at 3C0000: 1)`.
   * The usage comment at the top of `harness.c` lists every option.
5. **Player** (`runtime/src/frontend/`): uses the core's emulation; the
   workaround is gone (`flashchip_install`, `flashchip_set_rom_size`,
   `flashchip_fix_bios_info` and the frontend `flashchip.c/.h` removed;
   `rom_install` sets `g_rom_data_size`). `--no-flash-commands` now works in
   the window mode too (it was selftest only). The `.sav` behavior and the
   44-byte state trailer (with the chip's command state) are unchanged; a
   state load that the core rejects now also restores the chip's command
   state. `CMakeLists.txt`: `flashchip.c` moved from the `zenobia` target to
   `NGP_CORE_SOURCES`.
6. **State files unchanged**: `NGPSTAT1`, the CPU (184 bytes), the 64 KB of
   low memory at byte 192, then the other modules; 66,399 bytes while the
   game has written no flash block, plus each written block (a state saved
   after Data -> Save is 66,399 + 65,536). The chip's command-sequence state
   is not in it (see open issue 1). States from older builds load; their
   chip size byte is corrected on load. Besides `0x6C58`, a new state
   differs from an old harness's state at the same moment only in 20 bytes
   of host pointers inside the Z80 core's struct, which the loader always
   replaces with its own (pre-existing).
7. **Regression script** `runtime/src/core/tests/save_test.py` (below).

## File formats

### Cartridge save file (`zenobia.exe` `saves\*.sav`, harness `--save`)

    "NGPFLSH1"
    then one record per flash block:
      u8  chip      0 = the chip at 0x200000, 1 = the chip at 0x800000
      u8  block     0-34 (16 Mbit layout: 0-30 are 64 KB at block * 0x10000,
                    31 = 32 KB at 0x1F0000, 32 = 8 KB at 0x1F8000,
                    33 = 8 KB at 0x1FA000, 34 = 16 KB at 0x1FC000)
      u16 0
      u32 length    little endian, = the block's size
      the block's bytes as the game left them

A record exists for every block the game has programmed or erased (and,
after a state load, every block that differs from the unmodified ROM). This
game uses blocks 27 (`0x3B0000`, suspend data), 28, 29 and 30 (files 1-3),
so a save file holds only those; the patch keeps them blank (the layout
check in `tools/patch/layout.py`). Both programs write it with
`flash_store_save` (the player through a temporary file and a rename, with a
`.bak` once per session) and check each record before applying it when
reading.

### Save state

Core part as above. The player appends a 44-byte trailer (`ZENOBST1`, core
size, CRC32, ROM SHA-1, flags with the chip's command state); the harness
ignores it, the player accepts states without it.

## How to test

Build: `build.bat` (Visual Studio 2022 C++ tools, CMake, Ninja).

**One command** (harness only; about 11 s):

    python runtime/src/core/tests/save_test.py --harness build/ngp_harness.exe
        --rom build/ogre_en.ngc --states build/states --work NEW_EMPTY_DIR
        [--reference OLD_HARNESS.exe]

33 checks on the 2026-10-09 build (English ROM SHA-1
`272f13aba335d26d566ac9b1e5c79a57b42f8552`, reference = the scratch
snapshot harness): size codes for blank 0.5/1/1.5/2/3/4 MB images and the
game, correction of an old state; Data -> Save ("Save complete.", 4096 bytes,
block 28) and `--no-flash-commands` ("Could not save."); next power-on offers
Load, the file is not rewritten, a truncated file is reported and not applied
half; 19 saves; save-file blocks kept across `--load-state`; `--poke`; the
state format; determinism of power-on and five states. Against the previous
harness it fails 16 of 18 checks (expected).

**By hand** (`H` = `build\ngp_harness.exe`, `ROM` = `build\ogre_en.ngc`,
states from `build\states`):

* Save: `H ROM --load-state data-popup_save_prompt.state --input 10:A:2
  --frames 600 --save S.sav` -> stderr `flash: 4096 bytes programmed, 0
  blocks erased`, `flash save written: S.sav (blocks 28)`, screen "Save
  complete.". The game writes during frames 13-16. With
  `--no-flash-commands`: "Could not save.", no file.
* Load: `H ROM --save S.sav --input "300:A:2;400:A:2;500:A:2" --frames 700`
  -> the title cursor starts on Load (grayed out without the file); add
  `;720:A:2;850:A:2` and `--frames 1000` -> DATA LOAD, then the saved game
  on "The Zenobian Age" map.
* Saving again from the map popup needs three presses (A clears "Save
  complete.", A opens "OK:A NO:B", A saves; no overwrite question). 19 saves
  to file 1: `--input` `10:A:2` plus `c:A:2;c+100:A:2;c+200:A:2` for
  c = 400, 800, ... 7200, `--frames 7700 --save S19.sav --dump-flash
  image.bin` -> `77824 bytes programmed, 1 blocks erased (chip 0 block 28
  at 3C0000: 1)`; the file holds block 28 only (16 KB of records after the
  erase); `image.bin` differs from the ROM in 16,372 bytes, all in
  `0x3C0000-0x3C3FFF`; `0x2F0000-0x2FFFFF` untouched; every save ends on
  "Save complete." in English. The same run with `--poke 6C58=01` (the old
  code) erases block 15 (game data) twice and programs only 61,450 bytes:
  the bug this fixes.
* Suspend and Continue: `H ROM --save S.sav --load-state
  data-cmdbar_suspend.state --input "10:A:2;60:A:2;200:A:2" --frames 600`
  -> 8,960 bytes written to block 27, both notes shown, the file holds
  blocks 27 and 28. Power-on with it: the title cursor starts on Continue;
  `--input "300:A:2;400:A:2;500:A:2;720:A:2"` resumes stage 0, and the game
  then erases block 27.
* Poke: `H ROM --load-state stage0_selected.state --poke 5490=05 --frames
  400 --shot-every 25` -> the chapter 5 card instead of chapter 1
  (`5490=0C`: chapter 12). The byte is read before frame 50: with `@50`
  every frame equals the unpoked run.
* Determinism: 14 cases (power-on 1500 frames, shots every 100; 200 frames
  from organize-items, map-unitwin, battle-inbattle_cmdbar,
  progress-stage2_gameplay, data-popup_monitor, shots every 20; plus runs
  with input: Monitor help, title -> NewGame, stage 0 play, 4200 frames of
  A from power-on, save prompt cancelled, HQ status browsing, stage 0
  opening, finance window), all with `--text-log`: 281 of 281 files
  byte-identical to the previous snapshot harness. No run logged an ignored
  flash write.
* Player and harness: the 19-save run in `zenobia.exe --selftest` (Japanese
  ROM + patch) gives the same `.sav` and the same last picture as the
  harness; the single save and `--no-flash-commands` give the same pictures.
* Player regression scripts on the rebuilt `zenobia.exe` (see
  `player.md`): `release_test.py` 40/40, `bps_test.py` 26/26,
  `state_test.sh` 33/33, `rom_test.sh` 27/27, `gui_test.ps1` 21/21 (renamed
  copy), `gui_save_test.ps1` 12/12, `gui_dialog_test.ps1` 14/14,
  `gui_misc_test.ps1` 9/9.

## Open issues

1. The chip's command-sequence state is not part of the core state format
   (kept fixed for the tools that read states). A harness state saved
   inside a sequence (the game's save loop spans frames 13-16) resumes in
   read mode: that byte's verify fails once and the game retries (it tries
   5 times). The player keeps the state in its trailer.
2. The chip model completes operations at once: no status polling bits
   (DQ7/DQ6 toggle), no autoselect (ID) mode, no erase suspend. The game uses
   none of them.
3. A second chip (CS1, `0x800000`) is supported by the chip model and the
   save format, but the core maps a 4 MB image at `0x200000-0x5FFFFF` and
   does not map `0x800000`, so only the BIOS calls reach chip 1. Irrelevant
   for this 2 MB game.
4. The harness writes its save file in place (no temporary file): a run
   killed while writing leaves a damaged file (reported at the next load).
   It also overwrites a `--save FILE` that exists but is not a save file
   (no `NGPFLSH1` signature, e.g. a mistyped state path; only reported as
   damaged at the start) once the game writes to the flash, and keeps no
   `.bak` as the player does. Now that saving works by default, any run
   that saves can do this: pass a new or a real save file.
5. States with flash blocks are larger: 66,399 bytes plus each block the
   game wrote (131,935 after Data -> Save) or that `--save` loaded.
   `tools/gfx/harness.py` (`poke`, `state_ram`) accepts only 66,399-byte
   states and refuses these ("the state format changed"), although the
   RAM is still at byte 192. Use the harness's `--poke`, or relax that
   check to "at least 66,399 bytes" (owned by the graphics tools).
6. The chip model and the HLE BIOS flash calls use the 16 Mbit block layout
   for every chip. A 4 or 8 Mbit cartridge (size codes 1 and 2) has its
   small boot blocks elsewhere (4 Mbit: 32, 8, 8 and 16 KB from
   `0x70000`), so erasing one of them would erase a whole 64 KB block
   there. Irrelevant for this 2 MB game.
7. Screens now reachable that need translation work elsewhere: the
   title-screen warning shown when Load or NewGame would erase suspend data
   (pre-drawn Japanese window, already a target of
   `gfx-title-logo.md`); the DATA LOAD list with saves; Continue.

## Next steps

* Orchestrator: refresh the scratch snapshot harness (`snap\ngp_harness.exe`)
  from this build so every agent can save, and tick "Core: BIOS chip size
  code, flash command emulation in the harness" in STATUS.md.
* Explore: data: rerun the flows that were blocked (Data -> Save to each
  file, DATA LOAD and Load with saves, "Save complete.", Suspend -> Continue,
  a block filling up) with text logs.
* Use `save_test.py` after any core change that touches memory, flash, BIOS
  or states.
* Small follow-ups found in the review: the harness should refuse (or copy
  to `.bak` first) a `--save FILE` without the `NGPFLSH1` signature instead
  of overwriting it (open issue 4); `tools/gfx/harness.py` should accept
  states longer than 66,399 bytes (open issue 5).
