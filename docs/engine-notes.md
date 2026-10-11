# Engine notes for Densetsu no Ogre Battle Gaiden: Zenobia no Ouji (NGPC)

Reverse-engineering notes for the supported dump
(`5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`). Addresses are CPU addresses
(cartridge ROM is mapped at `0x200000`).

## Hardware / boot

* Header: entry point `0x200040`, catalog `0x0085`, colour mode.
* The game uses the BIOS through a trampoline at `0x366CC9`: `ldf 3`, function
  number in `RW3`, then `call (0xFFFE00 + 4*RW3)`. Functions used: SHUTDOWN (0),
  RTCGET (2, buffer `0x4578`), INTLVSET (4), and the link-cable COM functions
  (0x10-0x19). Interrupt handlers are installed in the BIOS user vector table
  (`0x6FB8 + 4*n`): VBlank at `0x6FCC`, DMA-end handlers at `0x6FF0/0x6FF4`.
* Timer 0 is clocked by HBlank and used with micro-DMA for raster effects.
* The background colour register `0x8118` is written with mode `0b00`; the game
  expects the background colour to be used anyway (only bit 6 disables it).

## Main loop and tasks

* `0x2000CC`: main loop jumps through the state pointer at `0x4002`. A routine
  "yields" by popping its own return address into `0x4002` (`0x2000D9`).
* VBlank handler `0x200127`: copies the sprite buffer `0x442A` to VRAM, runs a
  queue of VRAM transfers at `0x400E` (count `0x400D`), and a continuation at
  `0x4006`.
* Task table at `0x4086`, 0x38 bytes per task. Each task has three script slots
  (+0, +4, +8) holding `(script address << 8) | frames to wait`; a negative
  value (top byte `0xFF`) means inactive. The scheduler is at `0x2001D5`.
  Task fields: +12..14 loop counters, +15 call-stack index, +16.. call stack,
  +32 message buffer pointer, +40 text map address, +42 first text tile,
  +44 blank map entry, +46 message result.

## Script bytecode VM

* Entered with `call 0x20023C` (the return address becomes the script pointer)
  or at `0x20023D` with `XDE` = script pointer. Opcodes are even bytes; the
  handler table is at `0x2007A1` indexed by the signed opcode.
* About 100 opcodes are valid (`0x80`-`0xFE` and `0x00`-`0x4A`); see
  `tools/text/script.py` for operand formats. Notable ones:
  `0x80` yield, `0x82 n` wait, `0x84` stop, `0xDA a24` jump, `0xDC/0xE0`
  call/return, `0xDE/0xE2` call/return on the task stack, `0xD4-0xD8` loops,
  `0xE4-0xEA` jump tables, `0xEE slot a24` spawn task, `0x2E a24` call native,
  `0x30` continue as native code (which re-enters with `call 0x20023C`),
  `0x32 text…term` show a message.
* Native code also re-enters the VM with `ld XDE, script` followed by a jump,
  call or *conditional* jump to `0x20023D` (e.g. the A/B answer branches in
  the tarot scenes: `ld.l XDE, 0x26950C` / `jp NZ, 0x20023D`).
* `st32 <script>, 0x61F0` arms a script that runs later (boss/town events);
  the stored value is a script entry point.
* `stv32 <ptr>, var 0x20` before `pcall 0x202FA1` points at raw window text
  (e.g. the tarot answer lists ` A… ⏎ B… ⏎ C… ⏎⏎`), not bytecode.

## Stages and events

* Stage table at `0x2261D9`: 20 records of 18 bytes. +0 (24-bit) event table,
  +10 (24-bit) map data, +14 (24-bit) stage script.
* The event entries sit just before the stage's location table and are
  read backwards: for location r >= 1 (records and churches alike) the 4
  bytes at (location table - 4r) are `[u8 id][u8 hidden index][u16 handler
  offset]` (`0x2035C1` -> `0x20317D`, `ld.l XWA, (-XIZ:4)`). The handler
  offset is relative to the stage script, 0 = no event. A nonzero hidden
  index n hides the place until a unit finds it (bit n-1 of the bitmap at
  `0x5432`). The ids are global and consecutive, counting down within a
  stage (stage 0: 03-00, stage 1: 0C-04, stage 2: 15-0D, stage 3: 1E-16).
  Location 0, the start, has no entry. Example, stage 0: Balzac (r = 1)
  has handler `0x04F3` (the Balzac bandits), Hind (r = 3) hidden index 1,
  the church (r = 4) handler `0x0C8D`. (These entries were first read one
  entry off, as `[u16 handler][u8 id][u8 town id]` followed by a "main
  event handler" with an unrelated id; that handler is location 1's, and
  the "unrelated id" is the location table's count byte.)
* A location handler typically looks like `bflag2 stage, skip` /
  `bflag flag, skip` / `pcall 0x204033` / `pcall <portrait>` / messages /
  `setflag flag` / `ret`.
* Location table (towns, castles, forts, temples; 207 in all): the stage
  record's byte +3 is its offset from the event table and the word +4 its size
  (`1 + 16*count`); the loader (`0x20321B`) keeps its address at `0x608E`.
  Layout `[count]` then 16-byte records `[type][name, 8 cells padded with 01]
  [flag][u16 population][rating][rating][x][y]` (x/y in 8-pixel tiles; type
  0 = castle/fort, 1-8 index the town-type names at `0x273334`; the flag is
  the stage number on one record per stage). The cursor's map position is at
  `0x60AE`/`0x60B0` (pixels), its screen position at `0x61DE`/`0x61DF`.
* Town window (A on HQ/a town, then the location icon): built at `0x207A66`
  into `0x6000` (flag byte, then text from `0x6001`: name, population, two
  ratings " LOW"/" MID"/"HIGH" from `0x2082D5`, income), frame `0x208002`
  (10x11 cells, 8-cell interior, icons in tiles `0xAA`-`0xAD`) at map `0x908A`,
  text at `0x90CC` from tile `0xC0`. Past the last record it shows the
  Roshfol church window (`0x2081BE`, name `0x208E22`).
* `0x208DE6` writes `<town type><name>` (or the church name) at `XIX`; its
  three callers append "... was liberated" (`0x20887A`, 11 bytes, no terminator),
  "... was discovered" (`0x208E2F`) and
  "... was taken by hostile forces" (`0x20A3CD`)
  and show the result as a system message. The type table is used nowhere else.

## Script inventory (tools/text/extract.py)

* Trusted entry points: every `call 0x20023C` (inline bytecode), the 20 stage
  scripts and everything reachable from them (jumps, calls, tables, task
  spawns, `0x61F0` pointers, native re-entries).
* Expansions, most trusted first: stage location lists (structural), the
  byte after each terminating instruction (chunks are laid out back to back),
  and last a broad search for 24-bit pointers. Speculative code must decode
  cleanly, end properly or merge into verified code, contain natural text
  (bigram model, `tools/text/textscore.py`), and must not overlap verified
  instructions (the walker also refuses overlapping decodes, so the first,
  most trusted decoding of any byte wins).
* Result: 1,570 messages (1,533 `FE`, 37 `FC` yes/no), all in banks
  `0x26`/`0x27` (stage scripts) and `0x29` (opening). Remaining text-like byte
  runs are raw menu/UI strings (no `0x32` prefix).

## Text

* 1-byte encoding; the 8x8 2bpp font is at `0x200C79 + 16*code`
  (strokes colour 1, background colour 2). `tools/text/charmap.py` has the
  table: digits `0x02`, A-Z `0x0C`, hiragana `0x26`, katakana `0x76`,
  punctuation `0xC6`-`0xDC`.
* Controls in message strings: `0x00` new line, `0x01` space, `0xDD` insert the
  hero's name (length-prefixed at `0x46A0`), `0xDE` insert the number at
  `0x65C2`, `0xDF`-`0xFF` terminate (the value is passed to the script in
  task+46/47; `0xFE` is the usual "wait for button").
* Message window: 18 tiles x 3 lines. The opcode parses the string into the
  buffer at `0x6000` (header `[pos][saved word]`, text at `0x6003`) and reveals
  one character per tick (`3*(2-speed)+1` frames, speed at `0x469D`); A/B
  reveals the rest of the line. When done it runs the script at `0x202FB6`
  and returns past the terminator.
* `0x200BAC` draws a window buffer (`00` new line, `00 00` end, `01` space),
  one tile per character from tile `IZ` at map address `IX`. 222 call sites.
* `0x200B72` prints a `00`-terminated string as map entries into a font that
  was preloaded into VRAM (`0x200B45`/`0x200B5A` load it from `0x200C99`).
  114 call sites (HUD labels, menus, yes/no...).
* Name tables are fixed width (e.g. tarot names `0x20F134`, attack names
  `0x20F21A`: 8 characters padded with spaces + `00 00`).

## Where UI text comes from (beyond direct pointers)

* `0x20CC9A`: A = character -> XIY = name, BC = length (hero: the name buffer
  at `0x46A0`; others via the names table). Clobbers XWA, XIY, BC only.
  Callers copy the name into `0x6000` and append a fragment ("<leader> ...").
* Stat changes from tarot cards: composed at `0x208620` (Chaos Frame variant
  `0x2087C9`): subject, stat name from `0x2088EB` (3-byte entries, "HP/MAX"
  first), then the subject particle, a line break and "N points" with the
  digit written over the N, then up/down.
* Item names: `0x215E86` picks the stage's treasure item, `0x215EAC` copies an
  item's name (skipping its data prefix) to XIX.
* Move types: 4-cell names at `0x20EB61` (+ "type" suffix at `0x20EB5D`),
  copied with 32-bit moves at `0x20631A`, `0x206DCF`, `0x20D5A5`, `0x21338D`.
* Popup and scenario map (bank `0x29`, around `0x29C300`): records of a
  10-cell label plus 2 x 14-cell help, padded with the blank glyph; the stage
  names are 10-cell labels at `0x29C562` + 12 * stage. Their pointer tables
  keep flags in the top byte, so lookups must mask it.
* Link battle (bank `0x2E`): setting names at `0x2E1693` + 11 * k (9 cells),
  values printed as `base + index * size` (`0x2E17E3`, `0x2E180E`, `0x2E1833`,
  `0x2E187A`, `0x2E18A2`; overview `0x2E227A`, `0x2E2284`, `0x2E2296`), round
  headers in 16-byte records at `0x2E32EF` (map position, text).
* Battle terrain names: 9-byte entries (7 cells + 00 00) at `0x2C82A9`.
* Finance (income forecast) window labels: `0x20825E`; amounts drawn from RAM.

## Free space and saves

* ROM `0x36746D`-`0x3FFFFF` is unused (`0xFF`) in the original, but
  `0x3B0000`-`0x3EFFFF` is the game's save area: cartridge flash blocks
  0x1B-0x1E hold the suspend data (`0x3B0000`) and save files 1-3
  (`0x3C0000`, `0x3D0000`, `0x3E0000`). The slot table at `0x29A66E` (8-byte
  records: address and block number; used by `0x29A47E`, `0x29A4D7`,
  `0x29A50F`) is the only source of save addresses. Records are appended
  (free-space scan `0x29A436` walks 16-bit record sizes from block start + 6);
  a full block is erased whole.
* The game does not use the BIOS flash calls: the save module copies its own
  routines to RAM `0x6E00` (byte program from `0x366F02`, block erase from
  `0x36711E`) and drives the chip with AMD-style command sequences (unlock
  `AA`->`5555`, `55`->`2AAA`; `A0` + byte; `80 AA 55 30` block erase; `F0`
  reset), then verifies by reading back. The erase routine converts the block
  number to an address with a per-chip-size table (`0x36700E`), indexed by the
  BIOS work byte `0x6C58` (chip size code; 3 = 16 Mbit for this 2 MB
  cartridge).
* Message windows: pcall `0x204033` is the dialogue window setup of every
  location handler (script `0x204072` sets var `0x28` = `0x96DC`, stv16 at
  `0x204087`; do not repoint it, it moves all stage dialogue). System-message
  window setups use `0x96DA` (`0x20854E`, `0x208925`, `0x208B7B`, `0x208EBD`)
  or `0x939A` (`0x203C20`, `0x203FD6`, `0x208492`, `0x2091EE`); so system
  messages start one cell left of dialogue, as in the original. The Yes/No
  choice is drawn at map `0x9764`, on the window's third line: a Yes/No
  question may use at most 2 lines (build rule in `tools/text/insert.py`).
* NEXT menu CITY list: composer `0x204C68` builds 4 lines from the location
  table (`0x608E`): the 8-cell name, then "  S" when record byte +9 is
  nonzero, then `00 01 00`; a mask byte after the `00 00` is read by the
  recolour loop below. Town visibility bits are around `0x5432` (testing:
  `0x5432`-`0x5439` = `0xFF` shows every town). The patch draws the list with
  the VWF and full names (`city_name` in `patch/src/textfix.asm`). The UNIT
  tab's list (composer `0x20D610`, called at `0x204A1F`, drawn at map
  `0x9108`) gets the same VWF marker (hook `0x204A1B`), so both tabs match.
* Original bug, harmless: when the map's NEXT window shows the CITY list, the
  loop at `0x204D10`-`0x204D1B` (`sub.w IX, 0x80` / `sbc.w (XIX), DE`) runs
  with stale upper bits in XIX and writes three words to `0x209208`,
  `0x209188`, `0x209108` (cartridge space) instead of the map cells
  `0x9208`/`0x9188`/`0x9108`. They are not flash command sequences, so the
  chip (and our emulation) ignores them.
* Patch regions: `tools/patch/layout.py` (UI text `0x368000`, code
  `0x370000`, fonts/remap `0x378000`, dialogue `0x380000`, graphics
  `0x3A0000`, tables `0x3F0000`); the build refuses any byte in the save area.

## Translation patch design

* English text uses its own codes (`tools/text/encoding_en.py`) and keeps the
  control codes above.
* Dialogue: the message opcode's per-frame step (`0x2007F8`) and init tail
  (`0x2008E3`) are replaced by a variable-width typewriter
  (`patch/src/textop.asm`, `patch/src/vwf.asm`) that draws only newly
  revealed characters; earlier characters' positions are recomputed from
  glyph widths, so no extra RAM is needed.
* Everything else keeps the original fixed-cell renderers (`0x200BAC`,
  `0x200B72`) with the font pointer redirected to an English 8x8 font, so
  menu layouts and tile budgets are unchanged.
* Each translated message instruction is replaced by `DA <addr24>` jumping to
  English pages in free ROM, which end with `DA <address after the original>`.
  Messages shorter than 4 bytes are rewritten in place.
* Location names (`patch/src/locname.asm`, data from
  `translation/en/locations.txt` via `tools/text/locations.py`): the town
  window's name copy (`0x207AB5`) stores a marker and a pointer to the English
  name instead; `loc_win_draw` (at `0x207B3A`) draws the rest of the window with
  the fixed font and then the name with the VWF (8 cells = 64 px). `0x208DE6`
  jumps to `loc_compose`, which writes the VWF marker, an English type phrase
  ("The trade city of"), a new line and the name; the callers' suffix copies
  are repointed to English endings (`loc_msg_*` in `ui.txt`). The 8-cell name
  field of each record also gets the English name (cut to 8 characters).

## How UI text is translated

How UI text reaches the screen (the renderers are described under "Text"
above):

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

1. In place: English written over the original bytes (must fit; padded).
2. Remap: hooks at `0x200BAC`/`0x200B72` look the source pointer up in a
   sorted table (original address -> English address in free ROM), so any
   string drawn directly from ROM can be longer; window strings can request
   the VWF renderer (packed tiles; must not use more tiles than the original).
3. Repoint: patch the code immediates that load the string (and copy
   lengths) when all references are known.
4. Code: custom patch where Japanese word order is baked into composition.

Packed tables: a table of self-relative 16-bit offsets followed by packed
entries; `0x201B77` returns `XIY` = entry, `BC` = length. Rebuilt whole and
repointed (`translation/en/tables/*.txt`, `@table ADDR [prefix=N]`).

Tools: `python -m tools.text.rawdump ROM LO-HI` (strings with lengths and
reference counts), harness `--text-log FILE` + `python -m tools.text.textlog
FILE` (what the renderers actually draw, with callers).
