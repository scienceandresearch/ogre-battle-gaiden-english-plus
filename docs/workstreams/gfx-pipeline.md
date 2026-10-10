# Graphics pipeline: English replacement graphics

## Goal

One pipeline for every pre-drawn graphic that shows Japanese. Our own fonts,
art and English text are committed as text sources. The patch build converts
them into NGPC tiles, maps and palettes, then writes them either in place or
into a graphics region of free ROM. Harness checks prove every screen. The
round-1 targets are the menu labels, the intro narration, the chapter title
cards, and the title logo with its warning window. A survey for any remaining
targets is part of round 2.

This file holds the design (round 1). From round 2 on it is also the notes
file of the framework tasks (`gfx-lib`, `gfx-build`, `gfx-verify`).

## State

**Done (2026-10-10).** Round 2 built `tools/gfx/` (library, build
integration, five targets: labels, intro, cards, title, tags), every target
passed an independent side-by-side faithful-match review, and gfx-verify
enabled all five in the full build (see "Build integration (as built)",
"Library (as built)" and "Verification" at the end of this file; per-target
notes in `gfx-*.md`). The sections below are the round-1 design, kept as the
contract; where the build differs, the as-built sections and the target notes
win (for example, the intro uses `title16` with a 4-neighbour outline, like
the original lettering).

Design done (2026-10-09, round 1). It is based on the four investigations
(`gfx-title-logo.md`, `gfx-intro-narration.md`, `gfx-chapter-cards.md`,
`gfx-labels.md`) and on the checks listed below.

Checked for this design (scratch folder `gfx-pipeline\`, stable harness
snapshot, round-1 prototype ROMs):

* **The acceptance checks in section 5 work.**
  * Labels: the 128 bytes of label sprite tiles in VRAM equal the ROM label
    named by the VBlank queue, on the command bar, unit window, item commands,
    organize screen (both bars) and in-battle bar. Every pixel outside the
    label strip matches the unmodified build.
  * Title: the 512 tiles and both 20x19 plane maps in VRAM equal the ROM
    package. Title, menu and NewGame screens match the unmodified build
    outside map rows 7-12. The warning-window map in VRAM equals the ROM
    block.
  * Intro: each of the 5 VRAM line slots holds the expected line at frames
    1200, 2400, 3600 and 4800.
  * Cards: with RAM poked to story chapter 4 and area chapter 6, the screens
    differ from the unmodified build only in rows 8-13.
* **The larger display font fits the intro in place.** The 11-row font of
  the cards prototype, with draft punctuation added, fits all 15 intro lines
  in place: the widest is 143 of 144 px with the outline. A scratch ROM runs
  the whole crawl correctly with it. So the bigger font does not force the
  relocated layout that the intro notes expected.
* **The save blocks.** The save slot table at `0x29A66E` uses flash blocks
  0x1B-0x1E, which are `0x3B0000`-`0x3EFFFF` (see `explore-data.md`). The
  region suggested for graphics, `0x3E8000`-`0x3EFFFF`, lies inside the block
  of save file 3. Graphics therefore go elsewhere (section 4.1).
* **No compressed formats in the targets.** The script VM's graphics opcodes
  copy raw data. The handlers are `gfx26`/`gfx28` (palettes, through
  `0x200B33`), `gfx2a`/`gfx2c` (tiles, through `0x200B37`) and `gfxfe` (maps,
  through `0x2009F1`).
* **Free space in the current English build.** Patch code `0x370000` (1.4 KB),
  font `0x378000` (6.2 KB), remap table `0x37C000` (3.0 KB), dialogue
  `0x380000`-`0x397A37` (94.6 KB), UI text and locations `0x3C0000` (15.0 KB),
  tables `0x3E0000` (28.4 KB). The last two are in save blocks.

## Summary

| Target | Source we commit | Font | Written to | Hooks | New ROM |
|---|---|---|---|---|---|
| Menu labels | `translation/en/labels.txt` | `vwf8` | in place: 45 x 128 bytes at `0x218112` | none | none |
| Intro narration | `translation/en/intro.txt` | `title16` (as built: 4-neighbour outline) | in place: 15 x 576 bytes at `0x290F5D` | none; relocated mode: 3 operands | none; relocated mode: up to 16 KB |
| Chapter cards | `translation/en/cards.txt` | `title16` | one record per card (map + tiles) | 2 hooks, 3 routines | about 18 KB (24 KB reserved) |
| Title logo, warning window | `translation/en/title.txt`, `assets/font/logo19.txt` (optional `assets/gfx/title/*.txt`) | `logo19`, `title16`, `vwf8` | in place: pool tiles, maps rows 7-12, window rows 1-3, palettes, one sprite count | none | none (16 KB reserved for a fallback) |

## Done (the design)

### 1. Asset formats (what we commit)

#### 1.1 Rules

* Original work only: our own fonts, lettering and wording. Do not trace or
  copy the original art, fan translations or other people's fonts.
* Text sources only, as UTF-8 `.txt`: fonts, text-art images, English text,
  and style constants in the target's Python module. No binary art goes in the
  repository. PNG is only an import and preview format.
* The colours are ours. Source palettes hold RGB values that we choose. Where
  a palette entry is shared with original art that stays on screen, the source
  says `keep`, and the build uses the ROM value at build time. No colour
  values are copied from the ROM into the repository.
* Anything that is decoded from the ROM or drawn over ROM art stays in
  `build/` or a scratch folder. That covers decoded originals, design
  templates, previews that show the original flag or emblem, screenshots and
  VRAM dumps.
* The build's Japanese-text check covers `translation/en/` (already) and
  `assets/` (new in round 2).
* Hook sites are documented as in `patch/main.asm`, by the original
  instruction in a comment. The repository holds no copies of original bytes.
  The build already verifies the SHA-1 of the whole base ROM.

#### 1.2 Fonts (`assets/font/*.txt`)

All fonts use the existing `vwf8.txt` syntax:

* `@NAME [advance=N]` starts a glyph, followed by rows of `#` (ink) and `.`
  (blank).
* All glyphs in one file have the same number of rows. The advance defaults
  to width + 1.
* A line that starts with `#` is a comment, unless it holds only `#` and `.`
  (then it is a glyph row).
* New fonts are original designs for this project, under the project licence
  (MIT). The owner may also dedicate them to CC0, like `vwf8.txt`.
* Glyph names are single characters, plus `SPACE`, `ELLIPSIS` (the ellipsis
  character) and `LQUOTE` (opening double quote). `"` is the closing double
  quote, and `'` covers both the apostrophe and the right single quote, as in
  `vwf8.txt`.
* The renderer stops with an error that names any missing character.

| Font | Rows | Metrics | Used by | State |
|---|---|---|---|---|
| `vwf8.txt` | 8 | capitals rows 1-6, x-height rows 3-6, descenders row 7 | dialogue (VWF), menu labels, title warning window, optional small kicker | exists (CC0) |
| `title16.txt` | 11 | capitals rows 0-8 (9 px), x-height rows 3-8, descenders rows 9-10. With the 1-px outline the text is 13 px tall, drawn in a 16-px band like the original card and narration lettering | chapter cards, intro narration, title subtitle | prototype in scratch (`gfx-chapter-cards\title16.txt`); round 2 task `gfx-font16` |
| `logo19.txt` | 19 | capitals only, condensed (about 7 px wide; I is 3 px), 2-3 px strokes so that a fill pattern shows | main title lettering | round 2 task `gfx-title` |

* `title16.txt` must add `? : ; ( ) / &`, `ELLIPSIS`, `LQUOTE`, `"` and a
  quote mark for `'`.
* `logo19.txt` needs at least the letters of OGRE BATTLE GAIDEN and SIDE
  STORY (A B D E G I L N O R S T Y). A-Z is recommended, so that the wording
  can still change.

No separate label font is needed. The 8-px label strip holds `vwf8`'s 6-px
capitals plus a 1-px outline. Only the five descender letters lose the outline
below their last row, and the prototype reads fine. If review asks for a label
font later, `label8.txt` (8 rows, baseline one row higher) can replace `vwf8`
by changing one constant in `tools/gfx/labels.py`.

#### 1.3 English text that appears in graphics (`translation/en/`)

There is one file per target, so parallel tasks never share a file. The build's
Japanese check already covers these files. Formats:

* `labels.txt`: `@NN text` per label (NN = 00-2C in hex). `@23 keep` keeps the
  original "NEXT" art. Comment lines start with `#`.
* `intro.txt`: one bitmap line per text line. A blank line separates
  paragraphs, and `#` starts a comment. Three paragraphs of 6, 6 and 3 lines
  keep the original layout (in place). Any other structure selects the
  relocated layout.
* `cards.txt`: the format of the prototype `cards_en.txt`. `[story N]` and
  `[area N]` (N = 1-20) start a card, `^text` is the heading band, and the
  other lines are title bands (1 or 2). `same N` reuses card N of the same
  set.
* `title.txt`: one `@key text` per line. The keys are `@logo` (fire part `|`
  white part, e.g. `OGRE BATTLE|GAIDEN`), `@subtitle`, `@kicker` (empty means
  none), `@window` (twice: lines 1 and 2), `@yes` and `@no`.

#### 1.4 Images (`assets/gfx/<target>/*.txt`): text-art indexed images

Text-art images are for art that cannot be generated from text by a font and
a style, for example a hand-tuned logo layer. Round 2 needs them only if the
title task chooses hand-made layers. Format:

    # comment
    @size 160 48
    @palette fire  plane1 0  #FFE040 #FF6020 #A01000
    @palette sub   plane2 5  #C08030 #FFD060 keep
    @chars . = 0   Y = fire.1   O = fire.2   R = fire.3   B = sub.1   A = sub.2   K = sub.3
    @data
    ....YYYY....   (one line per pixel row: 48 lines of 160 characters here)

In memory, a pixel is 0 (transparent) or `4 * slot + colour`, where slot is
the palette's position in the file and colour is 1-3. `python -m
tools.gfx.image import IN.png OUT.txt --like SPEC.txt` converts an indexed or
RGB PNG that uses exactly the declared colours. `export` writes a preview PNG.

#### 1.5 Style and colours (in code)

Each target module keeps its style as constants:

* font, outline (4 or 8 neighbours), bold, colour indices, alignment;
* for the title, its palettes (our RGB values, or `keep`).

Changing the look is a code change in the target module and needs no new
asset format.

### 2. Conversion at build time

#### 2.1 K2GE formats (reference)

* **Tile:** 8x8 pixels, 2 bits per pixel, 16 bytes. Each row is a
  little-endian word with the leftmost pixel in bits 15-14
  (`tools/common/tiles.py`). Colour 0 is transparent on planes and sprites.
  There are 512 tiles at VRAM `0xA000`.
* **Plane maps:** 32x32 entries, plane 1 at `0x9000` and plane 2 at
  `0x9800`. An entry is 16 bits little endian: bits 0-8 tile, bits 9-12
  palette, bit 14 vertical flip, bit 15 horizontal flip.
* **Map block** (script op `gfxfe`, routine `0x2009F1`): `[w][h]`, then `w*h`
  entries, copied row by row into the 32-wide plane.
* **Palettes:** 16 palettes x 4 colours per layer. Sprites start at `0x8200`,
  plane 1 at `0x8280`, plane 2 at `0x8300`; the background colour is at
  `0x83E0`. A colour is a 12-bit word `0x0BGR`. We convert from RGB with
  round(v * 15 / 255) per channel; previews use v4 * 17.
* **Sprite list** (`anim`): a count byte, then 5-byte records `[tile bits
  0-7][bit 0 = tile bit 8, bit 7 = H flip, bit 6 = V flip][x][y][palette]`.

#### 2.2 Steps (shared by every target)

1. **Text to ink.** Look up each character's glyph, advance the pen (plus
   optional extra spacing), and build the ink mask.
2. **Style.** Colour the ink with one index, a per-glyph-row list (a vertical
   gradient) or a repeating pattern. Then apply the options: bold (1 px wider
   to the right; dots and quote marks doubled but kept apart), a 1-px outline
   ring (4 or 8 neighbours), and extra glow rings. The renderer can return
   only the ink or only the rings, for two-layer art.
3. **Box.** Place the result in a fixed box (left, centre or right). If it
   does not fit, raise `FitError` with the text and its width.
4. **Layer bitmap.** Each pixel is 0 or `4 * slot + colour`.
5. **Cells.** Cut the bitmap on the target's cell grid.
   * The non-zero pixels of a cell must share one slot; otherwise raise
     `PaletteError` naming the cell.
   * Reserved cells must be empty.
6. **Tiles.** Encode each cell as 2bpp and deduplicate in a `TileBank`, either
   exact matches or also H/V/HV flips where the layout allows them. Tile
   numbers come from the target's pool, and the budget is checked.
7. **Output.** Map entries (`tile | palette << 9 | flips`), fixed-order tile
   blobs, card records, and palette words (`keep` entries untouched).
8. **Write.** In-place writes go through `RomPatch` (section 3.2). New data
   goes into generated assembly that is assembled with `main.asm` into the
   graphics region.
9. **Preview.** Previews go to `build/gfx/<target>/`.

| Target | Tile order | Dedupe | Flips |
|---|---|---|---|
| labels | 8 consecutive tiles per label (the shared sprite layout uses tile +0..+7) | no | no |
| intro | 36 tiles per line: top row of 18, then bottom row of 18 (the slot copy) | no | no |
| cards | per card, numbered from `0x44`; blank cells use tile 0 | identical tiles | optional |
| title | 207 free tile numbers (pool); the window goes first | yes | yes |

### 3. Tools (`tools/gfx/`)

#### 3.1 Library (task `gfx-lib`)

    font.py     load_font(path) -> Font            # any uniform glyph height; cached
                Font.height, Font.glyph(ch) -> Glyph(rows, advance), Font.missing(text) -> set
    textart.py  Style(ink=1, outline=3, outline8=True, bold=False, glow=(), rows=None,
                      pattern=None, spacing=0)
                measure(font, text, style) -> int   # px, outline included
                render(font, text, style, part='all'|'ink'|'rings') -> Bitmap (tight box)
                render_box(font, text, style, w, h, align='center', top=0) -> Bitmap
                FitError
    image.py    Bitmap(w, h, px); crop/paste/blit; load_textart(path) -> (Bitmap, [PaletteBinding]);
                save_textart(); save_png(path, bitmap, rgb, scale); import_png(); rgb_to_ngp(), ngp_to_rgb()
    tiles.py    cells(bitmap, cols, rows) ; cell_slot(cell) (PaletteError) ; encode_cell(cell) -> 16 bytes
                TileBank(pool, flips) .add(cell) -> (tile, hflip, vflip) ; .tiles ; .used
                map_entry(tile, pal, hflip, vflip) ; gfxfe_block(w, h, entries) -> bytes
                tiles_rowmajor(bitmap) -> bytes ; tiles_lines(bitmap, rows) -> bytes

#### 3.2 Build integration (task `gfx-build`)

`target.py` defines the interface types:

    Context(root, base, rom, work, region, font(name), log)
    Result(writes=[(addr, bytes)], allow=[(lo, hi)], asm=path|None, previews=[...], stats={})

`build.py` drives the targets:

    TARGETS = ('labels', 'intro', 'cards', 'title')
    SUBREGIONS = {'GFX_CARDS': (0x3A0000, 0x3A6000), 'GFX_INTRO': (0x3A6000, 0x3AA000),
                  'GFX_TITLE': (0x3AA000, 0x3AE000), 'GFX_SPARE': (0x3AE000, 0x3B0000)}
    prepare(root, base, rom) -> GfxBuild
    GfxBuild.check_chunks(chunks)
    GfxBuild.apply_inplace() -> report

* `prepare` is phase 1. It runs each target's `build(ctx)` and writes
  `build/gfx/gfx.asm` (the sub-region constants plus an include of each
  target's asm entry).
* `check_chunks` checks that every assembled chunk of a target lies in its
  sub-region or is a hook.
* `apply_inplace` is phase 2.
* A target whose module file does not exist yet is skipped with a note. Errors
  inside an existing module are not hidden.

`romio.py` provides `RomPatch(base, rom)`:

* `allow(lo, hi, owner)`;
* `write(addr, data, owner)`, which refuses writes outside the owner's ranges
  and overlaps with other queued writes;
* `commit()`, which first checks that `rom == base` on every queued range (no
  other writer touched it), then writes;
* `log`, for the report.

`apply.py` is the standalone test path (section 4.4):

    python -m tools.gfx.apply IN.ngc OUT.ngc --target NAME [--target ...]
        [--base rom/baserom.ngc] [--work DIR]

It assembles only the selected targets' asm, with a wrapper in the work
folder. Chunks must land on `0xFF` bytes of IN, and IN is never modified.

`test_all.py` is the test runner: `python -m tools.gfx.test_all
[rom/baserom.ngc]` runs every `tools/gfx/test_*.py`.

The build must keep working while target modules are still missing (wave 1):
the registry then simply has nothing to run.

Changes to `tools/patch/build.py`, `patch/main.asm` and the region table are
covered in section 4.

#### 3.3 Target modules (one per target, one task each)

Each target module provides:

* `labels.py`, `intro.py`, `cards.py`, `title.py`, each with `build(ctx) ->
  Result`;
* `python -m tools.gfx.<target> fit` for widths and budgets, without the ROM;
* `preview OUTDIR`;
* `decode ROM OUTDIR` to view the originals locally, never committed;
* `check ROM DUMPDIR` for the acceptance checks of section 5 on harness
  dumps;
* `test_<target>.py`.

Hand-written assembly (cards) lives in `patch/src/<target>.asm`. Generated
assembly and data go to `build/gfx/<target>/`. Target asm must be
self-contained: it may use ROM addresses and its own labels only, so that the
standalone path can assemble it without `main.asm`.

#### 3.4 Analysis and verification tools

* `vram.py` (`gfx-build`) consolidates the four scratch viewers.
  * `render MEM.bin PREFIX` prints the registers and palettes and writes
    plane 1, plane 2, sprites, the composite and a tile sheet from a harness
    `--vram` dump.
  * `bytes MEM.bin ROM VADDR ROMADDR LEN` and `map MEM.bin ROM PLANEADDR
    ROMADDR W H` compare VRAM with ROM data.
* `harness.py` (`gfx-build`):
  * `run(...)`, a wrapper for `ngp_harness.exe`; the path comes from `--exe`
    or `NGP_HARNESS`, default `build\ngp_harness.exe`;
  * `poke SRC DST ADDR=HEX ...` copies a state file with RAM changed. The file
    is `NGPSTAT1` followed by the CPU state, with the 64 KB low-memory image
    at byte 192. The tool checks the magic and the file size (66,399 today)
    and fails if the format changed;
  * `sheet` makes contact sheets;
  * `diff A.png B.png [X0 Y0 X1 Y1 ...]` counts differing pixels outside the
    given rectangles (160x152 screen coordinates).
* `inventory.py` (`gfx-survey`) is the static survey of graphics loaders
  (section 8, task 4).

#### 3.5 Encoders and compression

None are needed. All four targets are raw 2bpp data, and every script graphics
opcode copies raw data. If the survey finds a compressed format, add
`tools/gfx/codec_<name>.py` with a decoder, an encoder and round-trip tests:

* decode gives the VRAM contents seen in the harness;
* `encode(decode(x)) == x`, or the size is no larger than the original when
  written in place.

#### 3.6 Tests

* Library tests:
  * fonts: `vwf8` loads; its widths match the advances that `tools/text/fontc`
    compiles;
  * outline rings (4 and 8 neighbours) and bold on synthetic glyphs; box
    alignment and `FitError`;
  * text-art errors: unknown character, palette `keep`, wrong size;
  * `TileBank` deduplication with flips; map-entry bits; `gfxfe_block`.
* Build tests:
  * `RomPatch` refusals (outside range, overlap, bytes already changed);
  * a dummy target with one in-place write and one asm chunk;
  * no targets gives an identical ROM;
  * a write in `0x3B0000`-`0x3EFFFF` fails the layout check.
* Target tests:
  * all texts fit; sizes and addresses are right; output is deterministic
    (two builds are identical);
  * writes stay in the declared ranges;
  * with `rom/baserom.ngc`: decoding the original works, and applying the
    target to the base ROM changes only the expected ranges.
* Tests that need the ROM write only to `build/` or a temporary folder.

### 4. Insertion into the patch

#### 4.1 ROM layout and the graphics region

The game saves into flash blocks 0x1B-0x1E (`0x3B0000`-`0x3EFFFF`: suspend
data, then files 1, 2 and 3). When a block is full it is erased whole. Today
the patch keeps UI text at `0x3C0000` (file 1) and tables at `0x3E0000`
(file 3). Saving on hardware, on flash carts, and in our player (which now
emulates the flash commands, see `player.md`) destroys them. Graphics
therefore cannot use `0x3E8000`-`0x3EFFFF`, and the existing data must move.
No save slot uses the top 64 KB (`0x3F0000`-`0x3FFFFF`). Proposed layout
(task `gfx-build`):

| Range | Size | Content | Used today |
|---|---|---|---|
| `0x368000`-`0x36FFFF` | 32 KB | UI text and location names (moved from `0x3C0000`) | 15.0 KB |
| `0x370000`-`0x377FFF` | 32 KB | patch code | 1.4 KB |
| `0x378000`-`0x37FFFF` | 32 KB | fonts, UI remap table | 9.1 KB |
| `0x380000`-`0x39FFFF` | 128 KB | dialogue (allocator capped at `0x3A0000`) | 94.6 KB |
| `0x3A0000`-`0x3AFFFF` | 64 KB | **graphics** (new) | 0 |
| `0x3B0000`-`0x3EFFFF` | 256 KB | the game's save blocks: never written | none |
| `0x3F0000`-`0x3FFFFF` | 64 KB | rebuilt tables (moved from `0x3E0000`) | 28.4 KB |

Why `0x3A0000` for graphics:

* It is free and safe in today's build, so the graphics tasks need not wait
  for the move.
* It is 2.5 times the planned need: cards about 18 KB, plus the intro if it
  uses the relocated layout.
* It sits next to the other patch data.

Fixed sub-regions keep the parallel tasks independent, and they make the
standalone test ROMs use the same addresses as the full build:

| Sub-region | Range | For |
|---|---|---|
| `GFX_CARDS` | `0x3A0000`-`0x3A5FFF` (24 KB) | card routines, tables, records, tiles |
| `GFX_INTRO` | `0x3A6000`-`0x3A9FFF` (16 KB) | relocated intro: line table, map, extra lines (only if used) |
| `GFX_TITLE` | `0x3AA000`-`0x3ADFFF` (16 KB) | fallback title package (only if the in-place budget is exceeded) |
| `GFX_SPARE` | `0x3AE000`-`0x3AFFFF` (8 KB) | targets found by the survey |

Build rules (`gfx-build`):

* After all writers have run, a layout check compares the ROM with the base.
  Every changed byte at or above `0x36746D` must lie in a declared region, and
  none may lie in `0x3B0000`-`0x3EFFFF`. The check prints the usage of each
  region.
* `apply_chunks` refuses chunks in the save blocks.
* Graphics chunks must stay inside their sub-region.

#### 4.2 Build steps (new order in `tools/patch/build.py`)

1. Verify the ROM. Check for Japanese in `translation/en` and `assets`. Build
   the fonts.
2. UI text, then locations (new region).
3. **Graphics phase 1:** `tools.gfx.build.prepare` runs the targets and writes
   `build/gfx/gfx.asm`.
4. Assemble `patch/main.asm`. Its one new line, near the end, is:

        ; Graphics (tools/gfx): sub-regions, and each target's hooks, code and data
                .include "../build/gfx/gfx.asm"

   Then apply the chunks, check the graphics chunks against their
   sub-regions, and print the hook report as today.
5. Dialogue (`0x380000`-`0x3A0000`), tables (new region), and in-place text
   (`--inplace`).
6. **Graphics phase 2:** in-place writes through `RomPatch`. They run after
   every other writer and check that their bytes are untouched. The report
   lists each target's ranges and byte counts.
7. Layout check, then the ROM, symbols and BPS as today.

The BPS audit needs no change. The encoder references every 8-byte run that
the original ROM has, so the new tiles' literals never carry ROM data. The
title prototype passed the audit.

#### 4.3 What each target writes, and its hooks

**Menu labels:** in place, no hooks.

* 45 x 128 bytes at `0x218112 + 128 * n`, range `0x218112`-`0x219791`. Code
  starts at `0x219792`.
* The label task copies the selected label from ROM to its sprite tiles every
  frame (`0x217271`, VBlank copy), so new data shows up with no code change.

**Intro narration:** in place by default, no hooks.

* Line n is written at `0x290F5D + 0x240 * n` (n = 0-14), range
  `0x290F5D`-`0x29311C`. The palette at `0x290F55` is kept.
* The relocated mode is chosen automatically when the text structure is not 6,
  6 and 3 lines. It generates `build/gfx/intro/intro.asm`, with the line
  table, the map and the bitmaps of lines 15 and up placed in `GFX_INTRO`, and
  these operand hooks:

        .org 0x28D0A3                   ; script stv32 operand: line table (was 0x28D1EA)
        .dl     intro_table
        .org 0x28D0B7                   ; cp.w WA, end position (was 0x228 = 552)
        .dw     INTRO_END
        .org 0x28D0E2                   ; ld.l XIY, narration map (was 0x293DDD)
        .dl     intro_map

* Layout rules:
  * triggers are multiples of 8;
  * line pitch 24, paragraph gap 64, end = last trigger + 136;
  * with 5 VRAM slots, a line must be at least 120 px below the line five
    places before it.
* The generator reproduces the original table and map exactly from the
  original structure. That is a local golden test, with the ROM present.

**Chapter cards:** new data and two hooks, all in `patch/src/cards.asm`
(hand-written; data from `build/gfx/cards/data.asm`):

    ; Chapter title cards (data: translation/en/cards.txt via tools/gfx/cards.py)
            .org 0x29ECB4                   ; was: ld.b B,(0x5490) / set test, layout copy, sheet load
            call    card_load               ; load this card's tiles to VRAM tile 0x44 onward
            jr      0x29ED02                ; palette setup continues unchanged
            .org 0x29EDD4                   ; script, was: gfxfe 0x6080, 0x9208
            .db     0x2E                    ; ncall card_draw
            .d24    card_draw
            .db     0xCE, 0x20              ; cnt0 0x20 (the next op sets the same value)
            .org GFX_CARDS
    ; card_find / card_load / card_draw (87 bytes, from the scratch prototype)
            .include "../../build/gfx/cards/data.asm"

* A record is `.dl tiles`, `.dw words` (8 per tile), `.dw plane-1 map
  address`, `.db w, h`, then `w*h` map words (tiles from `0x44`; 0 = blank),
  then the tiles. The tables `card_story` and `card_area` hold 20 `.dl` each.
* Limits: at most 360 tiles per card (VRAM `0x44`-`0x1AB`), lines up to 158
  px, one heading line and up to two title lines.
* The old sheets stay in place, unused.

**Title logo and warning window:** in place, no hooks. Writes:

* **Palettes:** plane 2 at `0x28D277 + 8p` (p = 0, 1, 5, 6; colour 3 of
  palette 5 is `keep` because flag tile `0x148` uses it), and plane 1 at
  `0x28D2AF + 8p` (p = 0, 1). The fade-in reads the plane-1 values from ROM,
  so it follows our colours.
* **Tiles** at `0x28D307 + 16N`, only for the 207 pool tiles:
  * the old logo tiles `0x001`-`0x04B` except `0x00B`, `0x04C`-`0x061`,
    `0x076`-`0x0B3`;
  * the unreferenced tiles `0x00B`, `0x0B4`-`0x0BF`, `0x0F4`-`0x0FF`,
    `0x11E`-`0x11F`, `0x12C`-`0x12E`, `0x13B`-`0x13F`, `0x1DE`-`0x1DF`,
    `0x1EC`-`0x1F7`;
  * the window glyph tiles `0x062`-`0x075` and `0x12F`-`0x131`, used by the
    window first.
* **Maps:** plane-1 rows 7-12 at `0x28F4C5 + 2 * (20 * row + col)`, plane-2
  rows 7-12 at `0x28F889 + ...`, and window rows 1-3 at `0x28F7BF + ...`.
* **Sprites:** the flag sprite list's count byte at `0x28F307` goes from 50 to
  48, which drops the old fill sprites (the last two records).
* **Reserved cells:** row 7, columns 11 and 13-15, on both planes (arm art).
  They must be empty in our art.
* **Test only:** `python -m tools.gfx.title warn-test IN OUT` replaces the
  conditional jump at `0x28CDA4` with two NOPs, so that NewGame always opens
  the warning window. It is never used in the build.
* **Fallback** (more than 207 tiles or more palettes needed): a relocated
  package in `GFX_TITLE`. It repoints:
  * the script operands at `0x28CBC9`-`0x28CC0E`;
  * the fade-target loads at `0x28CCC5` and `0x28CCDF`;
  * the palette restore at `0x28C8EE` and `0x28C8F5`;
  * the window map operand at `0x28CDD9`.

#### 4.4 Testing without the full build

Parallel agents must not run `python -m tools.patch.build`, because it
rewrites `build/ogre_en.ngc`. Each target task tests through `python -m
tools.gfx.apply` on a copy of the stable snapshot ROM (`scratchpad\snap\ogre_en.ngc`)
and runs the harness on the copy. The snapshot's graphics region is free
(dialogue ends at `0x397A37`). Only `gfx-build` (its own before/after
comparison, written with `-o` to scratch) and `gfx-verify` run the full
build.

## How to test / reproduce

### 5. Acceptance recipes

Shorthand:

* `H` = `scratchpad\snap\ngp_harness.exe`;
* `S` = `scratchpad\snap\states`;
* `B` = `build\states`;
* `t.ngc` = the test ROM from `python -m tools.gfx.apply`;
* `ref` = the same command on the unmodified snapshot ROM.

"Identical outside R" means `python -m tools.gfx.harness diff` reports 0
pixels outside rectangle R, in 160x152 coordinates.

These recipes were run on the round-1 prototype ROMs during the design, and
gave the stated results: labels, intro (including the skip), title (including
the warning window and NewGame), and the card sequence. The per-card check was
run on two cards (story 4, area 6); the cards workstream checked all 40 in
round 1. The layout-move recipe is for round 2.

**Labels.** Label VRAM is `0xAC00` (map), `0xB600` (organize) or `0xA010`
(battle). Each dump must meet two checks:

* the VBlank queue (count at `0x400D`, 8-byte entries `[u16 words][u16
  dest][u32 src]` from `0x400E`) holds `src = 0x218112 + 128n` with that
  destination;
* the 128 bytes there equal the built label n.

Screens must be identical to `ref` outside x 48-111, y 88-95.

| State | Input | Shots and dumps | Expected labels |
|---|---|---|---|
| `S\command_bar_forecast` | `40:L:2;80:L:2;120:L:2;160:L:2;200:L:2;240:L:2;280:L:2` (`--frames 330`) | 30, 70, ..., 310 | 03 05 01 20 23 22 04 03 |
| `S\stage0_gameplay` | `46:A:2;100:R:2;150:A:2;200:R:2;240:R:2;280:R:2` (330) | 190, 230, 270, 310 | 0E 10 07 0E |
| `S\command_bar_forecast` | `10:L:2;50:L:2;90:A:2;170:R:2;210:R:2;250:R:2;290:R:2;330:R:2;370:R:2` (400) | 160, 200, 240, 280, 320, 360, 395 | 18 19 1A 1B 1C 1D 1E |
| `S\hq_status_screen` | `20:B:2;100:R:2;140:R:2` (200) | 90, 130, 170 | 02 0B 0C |
| `S\hq_status_screen` | `20:B:2;60:B:2;140:R:2;180:R:2;220:R:2;260:R:2;300:R:2;340:R:2` (400) | 130, 170, ..., 370 | 17 09 1F 0A 0D 01 17 |
| `B\battle-inbattle_cmdbar` | `20:R:2;60:R:2;100:R:2;140:R:2` (200) | 10, 50, 90, 130, 170 | 05 10 15 21 05 |

These runs do not reach labels 00, 06, 08, 0F, 11-14, 16 and 24-2C. The ROM
byte test and the preview sheet cover them.

**Intro.** Run `H t.ngc --frames 6500 --shot-every 300 --shot 6450 --vram
1200,2400,3600,4800`.

* The 5 slots (`0xA010`, `0xA250`, `0xA490`, `0xA6D0`, `0xA910`, 576 bytes
  each) must hold these lines:

  | Frame | Slot contents |
  |---|---|
  | 1200 | 0 1 2 3 (fifth slot not loaded yet) |
  | 2400 | 5 6 2 3 4 |
  | 3600 | 10 11 7 8 9 |
  | 4800 | 10 11 12 13 14 |

  In relocated mode, the expected slots come from the generated table.
* At frame 6450 the title screen is shown.
* Skip: with `--frames 1100 --input "1000:A:2" --shot 1080`, the screen is
  identical to `ref`.
* Review the contact sheet for legibility and centring.

**Cards.** For each chapter 1-20 and both sets, run `python -m
tools.gfx.harness poke S\stage0_selected.state st.state 5490=<ch>
546E=<bits>`, where bits is `00000000` for the story set and `1 << (ch-1)` as
4 little-endian bytes for the area set. Then run `H t.ngc --load-state
st.state --frames 201 --shot 200 --vram 200`.

* The VRAM tiles from `0xA440` equal the card's tiles.
* The plane-1 map at the record's map address equals its entries.
* The screen is identical to `ref` outside y 64-111.
* Review the story and area contact sheets.
* Sequence: from `S\stage0_selected` with no input, and with A at frame 45,
  120 or 200, shots at 400, 600 and 900 are identical to `ref`.

**Title.**

* Run `H t.ngc --frames 1100 --input "700:A:2" --shot 740,750,760,800,1010,1040
  --vram 800`.
  * VRAM `0xA000`-`0xBFFF` equals ROM `0x28D307` (0x2000 bytes).
  * The plane-1 map (`0x9000`) and plane-2 map (`0x9800`) 20x19 blocks equal
    the ROM maps.
  * Frames 800, 1010 (PRESS A BUTTON on) and 1040 (off) are identical to `ref`
    outside y 56-103.
  * Review the fade frames 740-760.
* Menu: with `--frames 960 --input "700:A:2;900:A:2" --shot 950`, the screen
  is identical outside y 56-103.
* Warning window: run `title warn-test`, then `--frames 1120 --input
  "700:A:2;900:A:2;980:A:2;1060:R:2" --shot 1040,1100 --vram 1100`.
  * The window map at `0x9340` (20x5) equals the ROM block.
  * Review: the text is inside the frame, and Yes and No sit under the cursor
    positions (x 40 and 88).
* NewGame: with `--frames 1400 --input "700:A:2;900:A:2;980:A:2" --shot
  1100,1200,1300,1390`, every frame is identical to `ref`.

**Layout move (`gfx-build`).** Build twice from the same sources, before and
after the change, with `-o` into scratch. Shots of both ROMs must be
identical:

* `S\command_bar_forecast` with `10:A:2`, shot 60 (finance window);
* `S\hq_status_screen`, shot 10;
* `S\scenario_popup_link`, shot 10;
* `S\hq_menu_location_icon` with `10:A:2`, shot 60 (town window);
* `S\name_entry_grid`, shot 10.

The layout report must show nothing in `0x3B0000`-`0x3EFFFF`.

### Evidence (scratch, machine-local, contains ROM graphics)

All under `scratchpad\gfx-pipeline\`:

* Check scripts:
  * `labelcheck.py`, `introcheck.py`, `vcheck.py` (`bytes` / `map` /
    `shots`) and `poke.py` are the prototypes of the acceptance checks;
  * `checks.py` checks the slot table and hook sites;
  * `freemap.py` measures free-space usage.
* Fonts and text:
  * `measure.py` measures text widths;
  * `intro16.py` with `title16_draft.txt` builds the intro test with the
    11-row font (`intro16.ngc`);
  * `intro_vwf8bold_vs_title16_f1200.png` and `_f2400.png` show the two
    styles side by side.
* Survey: `gfxops.py` scopes the survey. Its walk finds 1,064 `gfx2a` uses and
  621 distinct tile blocks before filtering, so some of the walk is data.
* Run outputs: `lab_*` (labels), `ti_*` (title, menu, warning window,
  NewGame), `in_en` and `in16` (intro), `sk_*` (intro skip), `cd_*` (two
  cards), `sq_*` (card sequence).

## Open issues

### 6. Risks

* **Tile budget (title).** The logo has 201 tiles, against 232 usable
  cell-layers; the placeholder used 153.
  * Detailed fire texture defeats tile sharing.
  * Keep the texture constant per glyph row, align letters to cells where
    possible, and let the tool report the budget.
  * The fallback is the relocated package (16 KB reserved).
* **Palettes (title).** Each 8x8 cell can use one palette per plane.
  * Front: fire or white, 3 colours each.
  * Back: palettes 0, 1, 6 and 5 (colour 3 kept), 3 colours each.
  * The fire/white split must fall between cells. GAIDEN starts on a cell
    boundary, so no fill sprites are needed.
  * The front palettes flash white during the fade-in; the back palettes do
    not fade.
* **Palettes (labels).** Colour 2 differs between screens (sprite palette 0
  against 13 in battle), so labels use colours 1 and 3 only.
* **Width limits.**
  * Labels: 64 px with outline. The widest proposals are 61-63 px.
  * Intro lines: 144 px. With `title16` the widest is 143 px, a 1-px margin.
    A wording change can force a re-split, and the relocated mode handles
    that.
  * Card lines: 158 px. Chapter 12 already needs two title lines.
  * Warning window line 1: 144 px; it is 138 px today.
* **Timing.**
  * Labels, intro lines and the title package keep their copy sizes.
  * Cards load fewer tiles than before (at most 62 against 360).
  * The relocated intro is longer: about 4.3 s more for each extra line,
    because the speed is fixed. The skip still works.
* **Data size.**
  * New ROM: about 18 KB for the cards, plus at most 16 KB for the intro
    (relocated) and 16 KB for the title (fallback).
  * The BPS grows by about 40 KB: labels 5.6 KB, intro 8.4 KB, title about
    4 KB, cards 18 KB.
  * No compression is involved.
* **Save blocks (urgent).** Until `gfx-build` lands, the UI text and tables
  sit in save blocks.
  * The player now emulates flash commands, and there saving already corrupts
    the English UI text once file 1's block fills up and is erased (about the
    8th save, `player.md`).
  * Test saves made with the old layout carry patch bytes in blocks 0x1C and
    0x1E.
  * The cards prototype also used `0x3B0000` (the suspend block).
  * The new layout check stops all of these.
* **Shared files.** Only `gfx-build` edits `tools/patch/build.py` and
  `patch/main.asm`. Target tasks plug in through the registry and generated
  include, so they never touch shared files. If another workflow also fixes
  the save-block layout, it must be serialised with `gfx-build`.
* **Reachability.**
  * The link-cable menus need a partner; static checks only.
  * In the harness, which ignores flash commands, the warning window needs
    the test bypass. The player's `--selftest` emulates flash commands, so an
    optional extra check is possible there: suspend in stage 0 with `--save`,
    then power on with that save and choose NewGame.
  * The area cards need RAM pokes.
  * `poke` depends on the state-file layout; it checks the size.
* **In-place overlaps.** Graphics phase 2 runs last and refuses ranges that
  any other writer changed. A future hook inside a graphics range would show
  up as a build error, not as silent corruption.
* **Survey.** Unknown Japanese graphics remain, for example the "deployed" tag
  on the stage organize panel (`explore-organize.md`, `explore-towns.md`) and
  possibly the ending or game over. Some of these may be native-loaded or
  compressed.

### 7. Decisions for the owner

Resolved in round 2 (provisional choices, built; see STATUS.md): intro in
`title16` with a 4-neighbour outline like the original; title Layout B ("THE
LEGEND OF" kicker, because the original logo has that phrase) with GAIDEN;
labels "Finances", "Tactics", "Rite of revival" (the tips line quotes it the
same way), "Add character" / "Remove", NEXT art kept; chapter 6 area "Litt
Island Waters" everywhere, "White Night". All follow-ups in item 5 are done
(glossary entry, graphics text in the localization database via
`tools/text/gfxtext.py`, harness `--poke`, flash emulation in the core). The
original round-1 questions follow for reference.

1. **Intro style.** Choose `title16` with an 8-neighbour outline (the
   recommendation: closer to the original size, matches the cards, in place)
   or bold `vwf8` (heavier, smaller). Comparison:
   `scratchpad\gfx-pipeline\intro_vwf8bold_vs_title16_f1200.png`.
2. **Title wording.** OGRE BATTLE GAIDEN alone (Layout A, recommended, matches
   the project title), or with a THE LEGEND OF kicker (Layout B). Also GAIDEN
   or SIDE STORY.
3. **Label wording.** Choices: Forecast or Finances (the window is titled
   "Income & Expenses"); Tactics; Revive or Rite of revival (the church tip
   says "Rite of Revival"); Add chars / Remove chars; keep or redraw NEXT.
4. **Card wording.** Chapter 6's area: "Litt Island Waters" here, but
   `ui.txt` says "Litt Eastern Sea" (the `ui.txt` owner should align them).
   Also White Night or Midnight Sun.
5. **Follow-ups outside graphics:**
   * a glossary entry for "Imperial Calendar" / "Imperial Year N";
   * add the four graphics text files to the localization export
     (`tools/text/l10n.py`) for linguist review;
   * a harness `--poke ADDR=HEX` option;
   * flash command emulation in the harness (the player already has it), so
     that the warning window can be reached without the bypass.

## Next steps

### 8. Round 2 tasks (one agent each, in this order)

| # | Task | Wave | Depends on |
|---|---|---|---|
| 1 | `gfx-lib` | 1 | none |
| 2 | `gfx-build` | 1 | none |
| 3 | `gfx-font16` | 1 | none |
| 4 | `gfx-survey` | 1 | none (uses `gfx-lib` when available) |
| 5 | `gfx-labels` | 2 | 1, 2 |
| 6 | `gfx-intro` | 2 | 1, 2, 3 |
| 7 | `gfx-cards` | 2 | 1, 2, 3 |
| 8 | `gfx-title` | 2 | 1, 2, 3 |
| 9 | `gfx-verify` | 3 | 5, 6, 7, 8 |

Scratch paths below are relative to the session scratchpad. The scratch files
are machine-local, and some contain ROM data, so read them but never copy
their ROM-derived parts into the repository.

1. **`gfx-lib`: graphics library.**
   * Owns `tools/gfx/font.py`, `textart.py`, `image.py`, `tiles.py` and
     `test_gfx.py`.
   * Inputs: sections 1-3; `tools/common/png.py`, `tools/common/tiles.py` and
     `tools/text/fontc.py`; scratch `gfxlabels\labelgen.py`,
     `gfx-intro\narrlib.py`, `gfx-chapter-cards\cards.py` and
     `gfx-title-logo\proto_logo.py`.
   * Implements section 3.1 and the library part of 3.6.
   * Its output must match the scratch prototypes byte for byte with the same
     parameters: `labelgen.py` (labels), `narrlib.py` (intro, bold `vwf8`,
     8-neighbour outline) and `cards.py` (cards).
   * Art: none.
2. **`gfx-build`: integration and save-safe layout.**
   * Owns `tools/gfx/__init__.py`, `target.py`, `build.py`, `romio.py`,
     `apply.py`, `vram.py`, `harness.py`, `test_build.py`, `test_all.py`, plus
     `tools/patch/build.py`, `patch/main.asm` and this file.
   * Inputs: sections 3.2, 3.4 and 4; `explore-data.md` (save slots) and
     `player.md` (saving corrupts the UI text today); scratch
     `gfx-pipeline\` (`vcheck.py`, `labelcheck.py`, `introcheck.py`,
     `poke.py`, `freemap.py`), the scratch VRAM viewers
     (`gfx-title-logo\vramview.py`, `gfx-intro\vinfo.py`,
     `gfx-chapter-cards\vram.py`, `gfxlabels\vram.py`), and
     `gfx-chapter-cards\buildtest.py`.
   * Implements sections 3.2, 3.4 and 4.1-4.4, including the layout move and
     the layout check.
   * Acceptance:
     * the "layout move" recipe;
     * `test_build` passes;
     * `apply` with no target gives an identical ROM, and the full build
       works with no target modules present;
     * `tools.gfx.vram` and `tools.gfx.harness`, run on the round-1 prototype
       ROMs, give the same results as the scratch checks in `gfx-pipeline\`.
3. **`gfx-font16`: display font.**
   * Owns `assets/font/title16.txt` and `docs/workstreams/gfx-fonts.md`.
   * Inputs: scratch `gfx-chapter-cards\title16.txt` (the prototype font, our
     own design), `assets/font/vwf8.txt` (style reference), scratch
     `gfx-chapter-cards\cards_en.txt` and `gfx-intro\narr_en_v3.txt` (texts
     to measure), scratch `gfx-pipeline\measure.py` and `intro16.py`.
   * Port the cards prototype font and add the punctuation listed in 1.2. The
     drafts in scratch `gfx-pipeline\title16_draft.txt` were only for the
     width test.
   * Acceptance:
     * every glyph has 11 rows of equal width;
     * the required character set is present;
     * all 15 draft intro lines are at most 144 px and all card lines at most
       158 px (outline included);
     * PRINCE OF ZENOBIA is at most 140 px;
     * the preview sheets have been reviewed;
     * `intro16.py`, rerun with the new font, shows a legible crawl.
   * Art: about 90 glyphs of 11 rows.
4. **`gfx-survey`: remaining pre-drawn Japanese.**
   * Owns `tools/gfx/inventory.py` and `docs/workstreams/gfx-survey.md`.
   * Inputs: `tools/text/extract.py` (`build_walker`), `tools/text/script.py`
     (opcode table), scratch `gfx-pipeline\gfxops.py` (first scan), the
     "pre-drawn" findings in `explore-organize.md`, `explore-towns.md` and
     `explore-battle.md`, and the states in `build\states\`.
   * Collect the graphics ops of every walked script (`gfx2a`, `gfx2c`,
     `gfxfe`, `gfx26`, `gfx28`, `anim`). Keep only VRAM destinations
     `0xA000`-`0xBFFF`, sources below `0x36746D` and at most `0x1000` words.
   * Collect native loaders too: `ld XIY, imm` before calls to `0x200B37` or
     `0x200194`.
   * Render each block to `build/gfx/inventory/` and classify it (no text /
     English / Japanese). Plan each Japanese target as the round-1 reports
     did, starting with the "deployed" tag.
   * Acceptance: the inventory with counts; every block classified; the
     "deployed" tag decoded, with a harness state and a replacement plan.
5. **`gfx-labels`.**
   * Owns `translation/en/labels.txt`, `tools/gfx/labels.py`,
     `tools/gfx/test_labels.py` and `gfx-labels.md`.
   * Inputs: `gfx-labels.md` (format, label tables, wording), scratch
     `gfxlabels\labelgen.py`, and `gfx-pipeline\labelcheck.py` (check
     prototype).
   * Art: 45 labels of 8 tiles each (64x8 px), colours 1 and 3, with the
     wording table of `gfx-labels.md` and the decisions in section 7.
   * Acceptance: the label recipes; `test_labels` passes; the preview sheet
     has been reviewed.
6. **`gfx-intro`.**
   * Owns `translation/en/intro.txt`, `tools/gfx/intro.py`,
     `tools/gfx/test_intro.py` and `gfx-intro-narration.md`.
   * Inputs: `gfx-intro-narration.md`; scratch `gfx-intro\narrlib.py`,
     `narr_render.py`, `build_extended.py`, `sim_crawl.py` and
     `narr_en_v3.txt`; `gfx-pipeline\introcheck.py` and `intro16.py`.
   * Art: 15 lines of 36 tiles each (144x16 px), colours 1 and 3, with the
     text of `gfx-intro-narration.md`.
   * Provide both modes.
   * Acceptance:
     * the intro recipe;
     * the golden layout test (with the ROM present);
     * a relocated-mode run with a 17-line test text (like the scratch
       `build_extended.py`): it ends on the title.
7. **`gfx-cards`.**
   * Owns `translation/en/cards.txt`, `tools/gfx/cards.py`,
     `patch/src/cards.asm`, `tools/gfx/test_cards.py` and
     `gfx-chapter-cards.md`.
   * Inputs: `gfx-chapter-cards.md`; scratch `gfx-chapter-cards\cards.py`,
     `cards_test.asm`, `cards_en.txt`, `allcards.py`, `decode_cards.py` and
     `buildtest.py`; `gfx-pipeline\poke.py`.
   * Art: 36 distinct cards, each at most 20x6 cells (screen rows 8-13), with
     the heading band in rows 8-9 and title bands in rows 10-13. The largest
     card is about 62 tiles. Colours 1 and 3. Text as in
     `gfx-chapter-cards.md`.
   * Acceptance: the cards recipe for all 40 combinations; `test_cards`
     passes; data fits `GFX_CARDS`.
8. **`gfx-title`.**
   * Owns `translation/en/title.txt`, `assets/font/logo19.txt`,
     `assets/gfx/title/`, `tools/gfx/title.py`, `tools/gfx/test_title.py`
     and `gfx-title-logo.md`.
   * Inputs: `gfx-title-logo.md`; scratch `gfx-title-logo\proto_logo.py`,
     `mock_art.py`, `geometry.py`, `tileuse.py` and `decode_title.py` (the
     template and decoder go to `build/` only).
   * Art:
     * front layer 20x6 cells (160x48 px at screen rows 7-12): OGRE BATTLE in
       fire (letter bodies about 7x19 px at y 66-84, from x 2) and GAIDEN in
       white (from x 104, on a cell boundary);
     * back layer 20x6 cells: a 3-px outline and glow around the main title,
       plus PRINCE OF ZENOBIA in `title16` capitals (palette 5, centred, y
       91-99);
     * at most 201 tiles for both layers;
     * window: "The suspend data will be erased." / "Is that OK?" / "Yes" at
       column 6 and "No" at column 12, in the 18x3-cell interior, 29 tiles.
   * Acceptance: the title recipes; `test_title` passes (budget, palettes,
     reserved cells, only pool tiles changed).
9. **`gfx-verify`: integration.**
   * Owns this file in wave 3 and adds a "Verification" section. It may run
     `python -m tools.patch.build rom/baserom.ngc`.
   * Inputs: the outputs of tasks 1-8 and section 5.
   * Run `python -m tools.gfx.test_all rom/baserom.ngc` and every recipe of
     section 5 on `build/ogre_en.ngc`.
   * Report the BPS audit, the patch size and the per-region layout usage.
     Nothing may be written in `0x3B0000`-`0x3EFFFF`.

## Build integration (as built)

_Task `gfx-build`, round 2 wave 1, 2026-10-09._ Sections 3.2, 3.4 and 4.2-4.4
are implemented as described here. The layout move and
`tools/patch/layout.py` were done by the orchestrator first. Where this
section differs from the design above, this section is right.

### Files

| File | Content |
|---|---|
| `tools/gfx/target.py` | `Context`, `Result`, `GfxError`, `TargetError`, `write_if_changed` |
| `tools/gfx/romio.py` | `RomPatch`: in-place writes with owners |
| `tools/gfx/build.py` | registry (`TARGETS`, `SUBREGIONS`), `prepare` and `GfxBuild` (phase 1, chunk check, phase 2); `python -m tools.gfx.build` lists the registry |
| `tools/gfx/apply.py` | the standalone test path |
| `tools/gfx/vram.py`, `tools/gfx/harness.py` | analysis and acceptance tools |
| `tools/gfx/test_build.py`, `tools/gfx/test_all.py` | tests and the test runner |
| `tools/patch/build.py` | the two graphics phases, the chunk check, `--no-gfx` |
| `patch/main.asm` | its last two lines: `.include "../build/gfx/gfx.asm"` |

### Build order (`tools/patch/build.py`)

1. Verify the ROM, check for Japanese (`translation/en`, `assets`), build the
   fonts.
2. UI text, then locations.
3. Graphics phase 1: `gfx = prepare(ROOT, base, rom)` runs every registered
   target whose module exists, queues its in-place writes and writes
   `build/gfx/gfx.asm`. That file holds `GFX_START`, `GFX_END`, `NAME` and
   `NAME_END` for each sub-region, then one `.include` per target asm entry,
   each followed by a marker comment. With no targets it holds only the
   constants, and it assembles to nothing.
4. Assemble `patch/main.asm`, then `gfx.check_chunks(chunks, asm.lines)`
   (before the chunks are applied), then `apply_chunks` as before.
5. Dialogue, tables, `--inplace` (unchanged).
6. Graphics phase 2: `gfx.apply_inplace()`.
7. Layout check, then the ROM, symbols and BPS (unchanged).

`--no-gfx` is `prepare(..., targets=())`: no target runs, `gfx.asm` holds only
the constants, and the report says `graphics: left out (--no-gfx)`.

### Rules the build enforces

In-place writes (`Result.allow`, `Result.writes`, `RomPatch`):

* A target declares the ranges it may write (end exclusive). In the original
  program they may be anywhere; in the free area (`0x36746D` and up) only
  inside the target's sub-region; never in the save blocks. The ranges of
  two targets may not overlap.
* Every write lies inside one of its target's ranges (adjacent ranges count
  as one) and overlaps no other write.
* Phase 2 runs after every other writer. It refuses the whole commit if any
  written range no longer equals the original ROM (a hook, in-place UI text,
  a dialogue jump...). Nothing is written then.

Assembly (a target's asm entry and the files it includes):

* It must start with an `.org`. A label or data before it would land in the
  section before the include.
* New data must lie in the target's sub-region (`.org GFX_CARDS`...). A
  target registered without a sub-region may only hook.
* A hook (a chunk below `0x36746D`) must land on bytes that no earlier writer
  changed (UI text, locations; in the standalone path, the input ROM). It
  must not overlap another chunk (`apply_chunks`). Phase 2 checks that no
  later writer (dialogue, tables) overwrote it.
* A target's symbols may not be defined anywhere else (`main.asm`, the
  generated symbol files, other targets) or twice. All labels share one
  namespace, so prefix them with the target name.
* No chunk from outside the targets may use `0x3A0000`-`0x3AFFFF`.
* The assembly must hold the `gfx.asm` that phase 1 wrote, included once,
  and every target's asm entry. Every full build rewrites
  `build/gfx/gfx.asm`, even with `-o`. So if `main.asm` lost the include, or
  a build running at the same time with other targets (for example a
  `--no-gfx` comparison) rewrote the file in between, the build stops.
  Without this check, a target's chunks would be dropped silently.

A chunk belongs to the file of the `.org` that started it, found from the
assembler's line list. The lines of a target's entry file, and of the files
it includes, belong to that target until the next line of `gfx.asm`.

Errors: `TargetError` and the library's own `ValueError`s (`FitError`,
`PaletteError`, `BudgetError`, `MissingGlyphError`...) become one message,
`graphics: target NAME: ...`. Any other exception in a target is a bug and
keeps its traceback. A registered target whose module file does not exist is
skipped with a note (`graphics: no targets (no module yet: labels, intro,
cards, title)`); an import error inside an existing module propagates.

### API (as built)

```
Context    root, name, base (bytes), rom (bytes: the ROM at phase 1), work (build/gfx/<name>/),
           subregion ('GFX_CARDS' or None), region ((lo, hi) or None),
           log(text), path(*parts), translation(file), font(name), read(addr, n) (original ROM),
           write_file(name, str or bytes) -> path   (atomic; only when the content changed)
Result(writes=[(addr, bytes)], allow=[(lo, hi)], asm=path or None, previews=[...], stats={...})
RomPatch(base, rom): allow(lo, hi, owner), write(addr, data, owner), commit() -> lines, log, stats()
build.TARGETS = {'labels': None, 'intro': 'GFX_INTRO', 'cards': 'GFX_CARDS', 'title': 'GFX_TITLE'}
build.SUBREGIONS = {'GFX_CARDS': (0x3A0000, 0x3A6000), 'GFX_INTRO': (0x3A6000, 0x3AA000),
                    'GFX_TITLE': (0x3AA000, 0x3AE000), 'GFX_SPARE': (0x3AE000, 0x3B0000)}
build.Target(name, build_function, subregion=None)        (tests make their own)
build.select_targets(None or [names or Target objects]) -> (targets, notes)
build.prepare(root, base, rom, targets=None, gfx_dir=None, asm_path=None, log=print) -> GfxBuild
GfxBuild.report(), .check_chunks(chunks, asm.lines) -> lines, .apply_inplace() -> lines
apply.apply_targets(base, rom_in, targets=None, work=None, gfx_dir=None) -> (bytes, lines)
```

Changes from section 3.2:

* `TARGETS` is a dict (name -> sub-region).
* `check_chunks` also takes the assembler's `lines`.
* `Context` has `name`, `subregion` and the helpers above.
* A module may set `FULL_BUILD = False` (see below).
* Phase 2 also checks the targets' chunks.
* The phase-2 report lists the use of each sub-region. The layout report
  measures the graphics region from its start, so 6 bytes in `GFX_SPARE`
  show there as 56 KB "used".

### How to add a target

1. Add one line to `TARGETS` in `tools/gfx/build.py`: the name and its
   sub-region, or `None` for in place only. The names of the library and tool
   modules are reserved.
2. Write `tools/gfx/<name>.py`:

   ```python
   from .target import Result, TargetError

   def build(ctx):
       font = ctx.font('vwf8')
       ...                                     # read ctx.translation('<name>.txt'), render, encode
       asm = ctx.write_file('<name>.asm', text)    # only for code or new data
       return Result(writes=[(addr, data)], allow=[(lo, hi)], asm=asm,
                     previews=[...], stats={'lines': 15})
   ```

   Generated files and previews go to `ctx.work`, which is
   `build/gfx/<name>/` in the full build and in `tools.gfx.apply` alike. So a
   hand-written `patch/src/<name>.asm` can include its generated data as
   `"../../build/gfx/<name>/data.asm"`; `Result.asm` then names
   `patch/src/<name>.asm`.
3. While drafting, `FULL_BUILD = False` in the module keeps it out of the
   full build, and out of `apply` without `--target`. `python -m
   tools.gfx.apply IN OUT --target <name>` still runs it. Once the module
   exists without that flag, every full build includes it.
4. Write `tools/gfx/test_<name>.py`, runnable as `python -m
   tools.gfx.test_<name> [ROM]`, with exit status 0 when it passes and a
   summary as its last line. `test_all` picks it up.

Two targets may share a sub-region (for example survey targets in
`GFX_SPARE`) if they use different addresses; overlaps are build errors.

### How to test

```
python -m tools.gfx.test_build [rom/baserom.ngc]      # 14 tests; a synthetic ROM without the argument
python -m tools.gfx.test_all rom/baserom.ngc          # every tools/gfx/test_*.py
python -m tools.gfx.build                             # registry, sub-regions, modules present
python -m tools.gfx.apply <scratch>\snap\ogre_en.ngc t.ngc --target NAME   # test ROM; IN is never modified
python -m tools.patch.build rom/baserom.ngc -o <scratch>\a.ngc [--no-gfx]  # comparison builds
```

With `NGP_HARNESS` set (for example to the snapshot harness), `test_build`
also runs the harness for 40 frames and checks that the composite drawn by
`vram` equals the screenshot.

`tools.gfx.apply` writes its wrapper to `--work` (default
`build/gfx/apply/apply-<targets>.asm`, with the symbols in `.sym`). Apply a
target once, to a clean copy: applying it again is refused, because its
hooks and ranges are no longer original. A `--target` whose module does not
exist is an error. Without `--target` and with no target module present,
OUT is a copy of IN.

### Analysis tools and the section 5 recipes

The commands are `python -m tools.gfx.vram ...` and `python -m
tools.gfx.harness ...`. Addresses and byte lengths are hex, counts decimal; a
folder stands for its `mem_*.bin` dumps. `harness diff` counts screen pixels,
with inclusive rectangles (the scratch `vcheck.py shots` counted 2x-scaled
pixels, 4 per screen pixel). `harness diff`, `vram bytes` and `vram map` exit
with status 1 when something differs.

| Recipe | Commands |
|---|---|
| any run | `harness run [--exe H] t.ngc --frames N --load-state S --input ... --shot ... --vram ... --out DIR` (the harness is `--exe`, else `NGP_HARNESS`, else `build\ngp_harness.exe`) |
| title | `vram bytes DIR\mem_00800.bin t.ngc A000 28D307 2000`; `vram map ... 9000 28F4C5 20 19`; `vram map ... 9800 28F889 20 19`; `harness diff t\frame_00800.png ref\frame_00800.png 0 56 159 103` |
| labels | `vram queue DIR --rom t.ngc --dest AC00 --index 218112 80`: the label number from the queue's source address, and VRAM checked against it. `vram find DIR t.ngc AC00 80 218112 45 --hex` lists the matching ROM labels; two labels with the same art show as `07/20` |
| intro | `vram find DIR t.ngc A010,A250,A490,A6D0,A910 240 290F5D 15` (in-place layout) |
| cards | `harness poke S\stage0_selected.state st.state 5490=04 546E=00000000`, then a run, `harness diff ... 0 64 159 111` and `vram bytes ... A440 ...` |
| review | `harness sheet DIR [START STOP STEP]`; `vram render MEM.bin PREFIX [--maps] [--sprites]` (planes, sprites, composite, tile sheet) |

### Verification (this task)

On the round-1 prototype ROMs, with the snapshot harness and states unless
noted:

* `test_build`: 13 of 13 pass with the ROM, without it, and with
  `NGP_HARNESS`. `test_all`: `test_build` and `test_gfx` pass.
* Full build with no target modules: the default and `--no-gfx` builds, run
  back to back, are byte-identical, and identical to the build before this
  change. The layout report shows `gfx` with 0 bytes.
* `tools.gfx.apply` on the snapshot ROM with no target gives an identical ROM.
* Title (`gfx-title-logo\test_logo.ngc`): 0 of 8192 tile bytes differ, 0 of
  380 map entries differ on each plane, and there are 0 differing pixels
  outside y 56-103 at frames 800, 1010 and 1040. The composite that `vram
  render` draws from the frame-800 dump equals the screenshot.
* Labels (`gfxlabels\test_labels.ngc`, command bar): 03 05 01 20 23 22 04 03
  (queue source, VRAM verified). Every shot is identical to the snapshot
  outside x 48-111, y 88-95. `labelcheck.py` printed 07 for the fourth shot,
  because the prototype's labels 07 and 20 have the same art.
* Intro (`gfx-pipeline\intro16.ngc`): slots 0 1 2 3 - / 5 6 2 3 4 / 10 11 7 8
  9 / 10 11 12 13 14, as `introcheck.py` shows.
* Cards (`gfx-chapter-cards\test_cards.ngc`): the `poke` output is identical
  to that of `poke.py` and to the round-1 states. Story 4 and area 6 are
  identical to the snapshot outside y 64-111.
* A dummy target through the real full build, on an isolated copy of the
  sources in scratch: only its 16 bytes changed, and the BPS audit passed.
  These were refused with clear messages: a hook on a `main.asm` hook, an
  in-place write over a `main.asm` hook, a hook that the dialogue writer
  later overwrites, and an in-place write over a dialogue site.

Scratch evidence: `r2-gfx-build\` (`fullbuild_dummy.py` and the run outputs).

Review (round 2): all of the above reproduced. The review added the check
that the assembly holds the generated `gfx.asm` and every target's asm entry
(see "Rules the build enforces"), with its test (`test_build` now has 14
tests). Before the check, a `main.asm` without the include, or a `gfx.asm`
rewritten by a concurrent `--no-gfx` build, dropped a target's chunks without
an error. Evidence: `r2-review-gfx-build\`.

## Library (as built, round 2)

Files: `tools/gfx/font.py`, `textart.py`, `image.py`, `tiles.py`, and the tests in `tools/gfx/test_gfx.py`.

* The library is pure Python. It uses only `tools.common.png` and `tools.common.tiles` (no PIL).
* To test: `python -m tools.gfx.test_gfx [ROM]`. It runs 18 tests, needs no ROM (a ROM argument is ignored), takes about 0.2 s and exits 1 on failure.

**font.py**

* `load_font(path) -> Font`
  * Cached per path, and reloaded when the file changes.
  * Reads UTF-8 with or without a byte-order mark.
* `Font` provides:
  * `.height`, `.name`, `.glyphs` (name -> Glyph), `.glyph(ch)`, `.glyph_name(ch)`, `.missing(text) -> set`, and `ch in font`;
  * `Font.from_text(text, source)`, for fonts held in code (tests).
* `Glyph(rows, advance)`: rows is a tuple of '#'/'.' strings. It also has `.width`, `.height` and `.ink()`.
* Syntax:
  * That of vwf8.txt. Rows before the first glyph are ignored, as in fontc.
  * Stricter than fontc: any other stray line, an unknown header option, a duplicate glyph, ragged rows or a height mismatch is a `FontError` with file:line.
* Character mapping:
  * As specified: ' ' -> SPACE, U+2026 -> ELLIPSIS, U+201C -> LQUOTE, U+201D -> `"`, U+2019 -> `'`.
  * Deviation (a superset): U+2018 -> `'` as well, as `tools/text/encoding_en.py` does.
  * A glyph named by the character itself wins over the alias.
* `MissingGlyphError` (a ValueError) names the missing characters, the text and the font.

**textart.py**

* `Style(ink=1, outline=3, outline8=True, bold=False, glow=(), rows=None, pattern=None, spacing=0)`
  * An immutable namedtuple. `_replace()` normalises like the constructor. `Style.rings` gives the ring colours.
  * `outline`: None or 0 means no ring. `glow` gives rings 2..k. Glow without an outline makes ring 1 an empty, transparent gap.
  * `rows`: exactly `font.height` colours (ValueError otherwise).
  * `pattern`: rows of colours repeated over the ink. A flat list of numbers means one colour per pixel row. It is anchored at the pen origin of the first glyph and at glyph row 0, so it does not depend on where the text is placed. `rows` and `pattern` exclude each other.
  * `bold`: every glyph with ink gets 1 px wider (each ink pixel also inks its right neighbour; advance + 1). The marks in `BOLD_MARKS` (ELLIPSIS, LQUOTE, `"`) instead double each ink pixel and keep the gaps (advance = new width + 1). This is exactly narrlib's rule. Glyphs without ink (SPACE) are unchanged.
  * Rings grow from the whole line with 4 or 8 neighbours, and each ring grows from the previous one. Ink always wins over a neighbour's ring.
* `measure(font, text, style=None) -> int`: the rendered width, rings included. It is 0 for text without ink.
* `render(font, text, style=None, part='all'|'ink'|'rings') -> Bitmap`
  * Horizontally tight: from the leftmost to the rightmost ink, plus the rings.
  * Vertically: the full font height plus the rings, so glyph row 0 is at y = number of rings.
  * All three parts share the same box.
* `render_box(font, text, style, w, h, align='center', top=0, part='all') -> Bitmap(w, h)`
  * `align`: 'left', 'center' (x = (w - width) // 2, the prototypes' left bias) or 'right'.
  * `top`: the box row of glyph row 0; the rings extend above it.
  * `FitError(text, width, limit)` (a ValueError) when the width is more than w, and also when ink rows fall outside the box. Rings may be clipped, at the top and bottom only.
  * Extensions to the design: the `part` keyword, and `top=None`, which centres the text box vertically.
* Deviation, horizontal origin:
  * labelgen.py and cards.py measured from the pen origin; the library measures from the leftmost ink, as narrlib.py does.
  * The two agree for every vwf8 glyph and every prototype title16 glyph, since all of them except SPACE have ink in column 0.
  * Leading and trailing spaces do not count.

**image.py**

* `Bitmap(w, h, px)`
  * Pixels are a flat row-major list; a list of rows is also accepted. Each pixel is 0 or 4 * slot + colour.
  * Methods: `get`, `set`, `row`, `rows`, `copy`, `crop`, `paste` (every pixel, clipped), `blit` (non-zero pixels only), `bbox`, `values`, and equality.
* Text-art loading and saving:
  * `load_textart(path) -> (Bitmap, [PaletteBinding])`.
  * `parse_textart(text) -> TextArt(bitmap, palettes, chars)`.
  * `format_textart` and `save_textart(path, bitmap, palettes, chars=None, comments=())`. Output is deterministic, with LF line ends. Default characters are '.' for 0, then 1-9, A-Z and a-z by pixel value.
* `PaletteBinding(name, plane, number, colors)`
  * `colors` holds 3 entries, each (r, g, b), or None for keep.
  * `.words()` gives the colour words (None for keep).
  * The slot is the binding's position in the list.
* Format: that of section 1.4, plus:
  * several @chars lines;
  * plain pixel numbers in @chars (e.g. `o = 3`), for art without palettes;
  * the plane is plane1, plane2 or sprite;
  * each hardware palette may be declared only once per file;
  * data rows are taken literally (no comments inside; trailing spaces are ignored).
* `TextArtError` reports file:line for:
  * an unknown character (with x and y);
  * a wrong size (row length, too few rows, too many rows);
  * a bad colour, or an unknown palette or colour in @chars;
  * duplicates, and a missing @size or @data.
* Previews:
  * `save_png(path, bitmap, rgb=None, scale=1)`.
  * `preview_rgb(palettes, transparent=#FF00FF, keep=None)` builds the rgb table.
  * Keep entries use the override in `keep` ({'NAME.K': rgb}) if there is one. Otherwise they use `keep_placeholder(v)` = (0, 255, 255 - v), which is distinct for each pixel value, so a preview can be imported again.
* `import_png(path, palettes, transparent=#FF00FF, keep=None, cell=8)`
  * Exact colours only; the error names the colour and the pixel.
  * Alpha 0 is transparent, and a partly transparent pixel is an error.
  * A colour shared by several palettes is resolved per 8x8 cell, counted from the image origin: the cell takes the lowest slot that has all of its colours, then that slot's lowest colour index. This is the rule of proto_logo.py's convert_layer. A cell whose colours share no palette is an error. `cell=None` resolves per pixel.
  * Reads indexed and truecolour PNGs. A truecolour PNG may carry a PLTE chunk; it is handled correctly.
* Colours: `rgb_to_ngp(rgb or '#RRGGBB')`, `ngp_to_rgb(word)`, `parse_rgb`, `format_rgb`.
* Command line:
  * `python -m tools.gfx.image import IN.png OUT.txt --like SPEC.txt [--keep NAME.K=#RRGGBB] [--transparent #RRGGBB] [--cell N]` (N = 0 resolves per pixel);
  * `python -m tools.gfx.image export IN.txt OUT.png [--scale N] [--keep ...]`.

**tiles.py**

* `cells(bitmap, cols=None, rows=None)` returns a flat row-major list of `Cell`. A Cell is a tuple of 8 tuples with `.col` and `.row`. The bitmap must be exactly cols x rows cells.
* `cell_slot(cell)` returns the slot, or None for an empty cell. `PaletteError` names the cell (col, row) for mixed slots, or for a pixel whose colour bits are 0 (such as 4).
* `encode_cell(cell)` returns 16 bytes through `encode_tile_2bpp` (colour = pixel & 3). `flip_cell(cell, h, v)` mirrors a cell.
* `TileBank(pool, flips=False)`
  * `.add(cell) -> (tile, hflip, vflip)` looks for an exact match, then H, V and HV, the title prototype's order. A new tile takes the next pool number.
  * `.tiles` (16-byte tiles) and `.used` (their numbers) are in allocation order. Also `.remaining`, `.blob()` and `len()`.
  * The same colours in different slots share one tile.
  * `BudgetError` names the pool size and the cell.
  * Blank cells are not special: the target maps them to entry 0 or a blank tile before calling `add`.
* `map_entry(tile, pal=0, hflip=False, vflip=False)`.
* `gfxfe_block(w, h, entries)`: 1-32 x 1-32, with w*h 16-bit entries.
* Tile orders:
  * `tiles_rowmajor(bitmap)`.
  * `tiles_lines(bitmap, rows=2)`: row-major within each line of `rows` cell rows. This equals `tiles_rowmajor`; it also checks that the height is a whole number of lines.
  * Both check the palette slot of every cell.

**Recipes that reproduce the round-1 prototypes byte for byte**

* Labels: `tiles_rowmajor(render_box(vwf8, text, Style(), 64, 8))` gives 128 bytes.
* Intro in bold vwf8: `tiles_lines(render_box(vwf8, text, Style(bold=True), 144, 16, 'center', 4), 2)` gives 576 bytes. With the 11-row font (as in intro16.py), use top=3.
* Cards:
  * per band, `render_box(title16, text, Style(outline8=False), 160, 16, 'center', 2)`, blitted at y = 16 * band onto a 160x48 canvas;
  * then `cells(canvas)`, crop to the non-blank cells, `TileBank(range(0x44, 0x1AC))`, and entry 0 for blank cells.
* Title:
  * build the layers with `import_png` or `render(..., part=...)`, then `cells(layer, 20, 6)`, and map `cell_slot` to the palette;
  * use one `TileBank(pool, flips=True)` per pool, window first; the logo pool appends the window bank's `.remaining`;
  * map entries are `map_entry(tile, number, h, v)`; write the tiles with `zip(bank.used, bank.tiles)`.
* Warning window text:
  * the number of cells comes from the sum of the glyph advances;
  * on a background bitmap of colour 2, blit `render_box(vwf8, text, Style(outline=None), n * 8, 8, 'left', 0)`.

**Cross-check results** (a machine-local scratch script that reads the round-1 prototypes and, for the title, the base ROM)

* Labels: 45 of 45 labels identical (45 x 128 bytes).
* Intro:
  * narr_en_v3.txt: 15 of 15 lines identical (15 x 576 bytes) for every bold/outline combination;
  * narr_ext_test.txt: 17 of 17;
  * the old drafts v1 and v2 each have one bold line wider than 144 px, which narrlib clipped silently and the library refuses with FitError.
* Cards: 36 of 36 canvases identical, with both outline modes, and the card encoder output identical for all 36.
* intro16.py: 15 of 15 lines identical.
* Title: proto_logo.py's whole test ROM rebuilt with 0 differing bytes (window 29 tiles, logo 153, 48 pool tiles left, 3 entries with H flips).

## Verification (gfx-verify, round 2 wave 3)

_2026-10-10._ All five targets are enabled (`FULL_BUILD = True` in `labels.py`,
`intro.py`, `cards.py`, `title.py` and `tags.py`) and built into
`build/ogre_en.ngc`. Every check below used the snapshot harness
(`snap3\ngp_harness.exe`, states `snap3\states`) against two references:

* the snapshot ROM `snap3\ogre_en.ngc` (`e63bffd1...`, original graphics), as
  section 5 specifies;
* the same sources built with `--no-gfx` (`517c5359...`, the previous
  `build/ogre_en.ngc`). The text changed after the snapshot, so this build
  isolates the graphics.

Both references gave the same results. The evidence is machine-local and shows
the original art: the session scratchpad's `r2-gfx2-verify\`.

### Build

| Check | Result |
|---|---|
| `python -m tools.patch.build rom/baserom.ngc`, first with `-o` into scratch | passes; SHA-1 `3b1184f5ab5bcf893842057f89f8929b5f8f962f` both times |
| in-place writes (phase 2 report) | labels 5,632 bytes in 2 writes, 4,396 of them differing from the original: `0x218112`-`0x219291` and `0x219312`-`0x219791` (label 23 kept); intro 8,640 bytes in 15 writes (4,780): `0x290F5D`-`0x29311C`; title 3,869 bytes in 226 writes (2,988) in 13 ranges `0x28D317`-`0x28FA90` (tiles, the sprite count at `0x28F307`, plane maps, window map); tags 192 bytes in 3 writes (97): `0x214A00`-`0x214A4F`, `0x2E736A`-`0x2E73B9`, `0x2FE5ED`-`0x2FE60C` |
| cards | 2 hooks (`0x29ECB4`, `0x29EDD4`, 12 bytes) and `0x3A0000`-`0x3A49BB` in `GFX_CARDS` (18,876 of 24,576 bytes); `GFX_INTRO`, `GFX_TITLE` and `GFX_SPARE` stay empty |
| layout (also `python -m tools.patch.layout build/ogre_en.ngc`) | ui 15.5 of 32 KB, code 16.1 of 32 KB, data 19.6 of 32 KB, dialogue 94.6 of 128 KB, gfx 18.4 of 64 KB (18,678 bytes changed), tables 32.0 of 64 KB; save blocks `0x3B0000`-`0x3EFFFF` untouched |
| BPS | 133,226 bytes (116,435 without the graphics: +16,791). Audit OK: 74,254 literal bytes in 9,394 runs; the longest literal run found in the original is 7 bytes (limit 8). `python -m tools.patch.test_bps rom/baserom.ngc`: 11 tests pass |
| same bytes as reviewed | the full build equals `tools.gfx.apply` of all five targets on the `--no-gfx` build. The 30,951 bytes where the two differ are exactly the bytes that the targets' accepted test ROMs changed (labels `c668efab`, intro `3325e859`, cards `d4b80493`, title `553d6533`, tags `a461c8d9`), with the same values and no overlap. The card sources read at run time (`0x29EEA2`-`0x2A2F0B`) and the intro palette are unchanged |
| Japanese check | the build's check of `translation/en` and `assets` passes; in the repository's text files, Japanese appears only in `tools/text/charmap.py` (the character table) |
| localization export | `python -m tools.text.l10n export rom/baserom.ngc`: 5,139 strings, all translated, 117 of them from the graphics text files (labels 44, intro 15, cards 49, title 7, tags 2) |
| player | `zenobia --selftest rom/baserom.ngc --patch build/ogre_en.bps` gives the image `3b1184f5...`, and its title frame equals the harness frame |

### Tests

`python -m tools.gfx.test_all rom/baserom.ngc`: `test_build` (14), `test_cards`
(15), `test_gfx` (18), `test_intro` (12) and `test_labels` (12) pass.
`test_tags` passes 15 of 16 and `test_title` 17 of 18. Both failures are in
`test_registry`, which pins the drafting state:

* `test_tags.py` lines 344-347 assert `T.FULL_BUILD is False` and that the
  default selection leaves `tags` out;
* `test_title.py` line 382 asserts `T.FULL_BUILD is False`.

With these assertions set to the enabled state, both modules pass: 16 of 16 and
18 of 18. The check was scratch `registry_tests.py`, which runs patched copies
and leaves the files unchanged. **Follow-up:** the owners of the two test files
change these lines.

### Harness recipes on the full build

| Target | Runs | Result |
|---|---|---|
| labels | the six recipes of section 5 (34 dumps), plus the extra runs of `gfx-labels.md` (58 dumps; RAM pokes for 06, 0F, 11 and 24-2C) | every dump: the VBlank queue copies the expected label, and VRAM holds the built label. All 45 labels are seen in the game. Every screen has 0 px differing outside x 48-111, y 88-95 |
| intro | the recipe (`--frames 6500 --shot-every 300`, dumps at the shots); a dense run with a shot and a dump every 25 frames (250-6475); the skip | slots `0 1 2 3 -`, `5 6 2 3 4`, `10 11 7 8 9` and `10 11 12 13 14` at 1200, 2400, 3600 and 4800, and every dump agrees with the table. Every crawl frame has 0 px differing outside the line boxes, and the logo frames 0 px. The title frames (6300-6475, and 1040-1080 after the skip) differ only inside y 56-103: that is the title target's logo. `intro check` compares those frames whole and reports them, as expected in the full build |
| cards | `cards recipe`: 40 cards and the sequence | all 40 ok: records, VRAM tiles and map equal the record; main RAM, palettes, sprites and plane 2 equal the reference; 0 px differ outside the original block. The sequence is identical at 400, 600 and 900. `cards check`: ok |
| title | 113 screenshot pairs: title, menu, NewGame, the natural fade-in, the window with `warn-test`, and the real window from a suspend save (cursor No; B, then Continue; Yes) | 0 px differ outside y 56-103 (and outside the window interior while it is open). NewGame and the new game after Yes are identical on the whole screen. VRAM equals the ROM package: 0 of 8,192 tile bytes, 0 of 380 entries in each plane map and 0 of 100 in the window map differ. The cartridge saves after the runs are the same for both ROMs |
| tags | the eight recipes of `gfx-tags.md`: 168 frames, 103 with a tag | the same tag instances on both ROMs, and `check_dump` passes. 0 px differ outside the original lettering areas, and outside the label strip where the labels target changed the label tiles. Palettes are identical. `tags check` finds the built tiles at all three ROM addresses, including the link-battle copy at `0x2E736A` |

### Integration checks

* **Every saved state.** Scratch `sweep.py` ran all 222 states for 120 frames,
  in 4 variants (idle, A twice, A three times, Right three times), with shots
  and dumps at 30, 60, 90 and 119, on the full build and on the `--no-gfx`
  build. Of the 3,552 screenshot pairs, 568 differ:
  * labels 528, cards 22 and title 14. The card scenes are reached in play
    from the scenario map (stages 1, 2, 3 and 12) and from `stage0_selected`.
    Title: the title state, and the return to the title after the ending
    results.
  * In every pair, 0 px differ outside the area of a target on screen. Each
    area counts only when the dump shows evidence for it: changed label tiles,
    a tag sprite, the title package in VRAM, or a changed card block.
  * Palettes are identical in all pairs.
  * Main RAM is identical except in two cases, both understood:
    * At the title, the sprite engine's buffers differ (`0x4400`-`0x45FF` and
      the list end pointer `0x6BF6`). Cause: the title target's flag sprite
      list has 48 records instead of 50.
    * Frame 30 of `stage0_selected` shows 8 stale stack bytes
      (`0x6BE8`-`0x6BEF`), which hold the card routine's return address
      `0x3A4987`. The game overwrites them in the next frame.
  * A state keeps the VRAM it was saved with. So `title_menu.state`, which
    was saved with an earlier build, shows the original logo in the full
    build. The two fill sprites over that logo are also gone (21 px), because
    the shorter flag sprite list comes from the new ROM. Graphics that a
    screen loads only once show up after a reload (power-on, a new scene);
    reviews of such screens need states made with the new build.
* **Power-on to the HQ:** 9,500 frames, pressing A every 40 frames from frame
  700 (the opening, the name entry and the tarot), sampled every 250 frames
  from frame 1,000.
  * The screens equal the `--no-gfx` build's, except the label strip on the
    organize screen.
  * From NewGame on, main RAM differs in 6 bytes of the sprite engine
    (`0x455A`-`0x455F`, `0x4566`-`0x4567`), caused by the shorter flag sprite
    list. They are gone by frame 6,750, and the screen never differs.
* **Saves:** Suspend on the stage-0 command bar writes the same cartridge save
  (SHA-1 `4f1a8d4f...`) on the full build, the `--no-gfx` build and the
  snapshot.
* **Card scene sound** (open issue of `gfx-chapter-cards.md`): a scratch copy of
  the harness writes the audio it already renders to a WAV file
  (`wav\harness_wav.c`, built against `build\ngp_core.lib`). It recorded
  `stage0_selected` for 960 frames, with no input and with A at frame 120.
  * Main RAM is identical at all 240 sampled frames.
  * The audio differs in 0.18 % of the samples (0.02 % with A), from frame 406
    on, in bursts of 1-9 samples (at most 0.19 ms).
  * In every 100-ms window the best alignment is at lag 0. So the music is the
    same, and single sound-register writes only take effect a few samples
    earlier or later.
  * This should not be audible. The owner can compare `wav\nogfx-idle.wav` and
    `wav\en-idle.wav`.

### Contact sheets for the owner

These are in `build/gfx/verify/` (local only: they show the original art). Each
puts the snapshot ROM (original) on the left and the full build (English) on
the right:

* `labels.png`: all 45 labels in the game, 3x;
* `intro.png`: the 15 line boxes, cut from the same crawl frames, 3x;
* `cards.png`: all 40 cards (story and area sets), screen rows 56-119, 2x;
* `title.png`: the title, PRESS A BUTTON, the fade-in (white flash and colours),
  the menu, the warning window (No, Yes, and the fade-out after Yes), plus the
  logo band at 3x;
* `tags.png`: the deployed tag in three contexts and the paralysis labels in
  five battles, as whole screens at 2x and as each tag at 4x.

### Result

No regressions were found, and every target behaves in the full build as it did
in its accepted test ROM. Still open:

* the `test_registry` follow-up above;
* the owner decisions listed in each target's notes:
  * labels: descenders, and the wording of 09, 25/26 and 07/20;
  * cards: the shortened titles of chapters 3, 4, 12 and 14;
  * title: the kicker, GAIDEN against SIDE STORY, two sprite-covered corners,
    and bounds 1 px wider;
  * tags: FIELDED or ON MAP, and STUN's weight;
  * intro: the wording.
* What no saved state reaches, checked only with RAM pokes or statically:
  * the link-cable labels 24-2C and the link-battle copy of the deployed tag;
  * the natural paralysis trigger;
  * the area cards.
