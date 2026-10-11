# Graphics: chapter title cards

## Goal

Replace the chapter title cards with English. A card is shown when a stage
starts: an emblem and, in front of it, the chapter number and title (story
set) or the area name (area set), pre-drawn in Japanese. The English cards
must look like the originals, with only the lettering changed (owner's
graphics rule, `STATUS.md`).

## State

Done (2026-10-09, round 2 wave 2, task `gfx-cards`), revised 2026-10-10
after the review (fix round 1). All 40 cards (36 records: chapters 18-20
share one card in each set) show English, drawn from
`translation/en/cards.txt` in `assets/font/title16.txt` with the original
lettering's colors, outline, rows and centering, and inside the original
lettering block (12 x 4 cells at plane-1 column 4, row 8 = screen x 32-127,
y 64-95). The target is `tools/gfx/cards.py` (with `FULL_BUILD = False`; the
verify step enables all targets together), `patch/src/cards.asm` and
`tools/gfx/test_cards.py`.

Fix round 1 (the review's required changes and suggestions):

* Bounds: every line is at most 96 px with its outline (`MAX_LINE = 8 *
  ORIG_BLOCK width`), a card has at most one heading and one title line, and
  every record's map block is the original 12 x 4 block. The 8 story lines
  that were wider are fixed by a 4-px word gap (4 lines) and new wording
  (4 lines, below); chapter 12 has one title line again.
* Word gap: `SPACE_ADVANCE = 3` in the card fonts (title16 has 4): words are
  4 px apart, with 2 px of background between the outlines.
* The checks enforce the bound: `test_bounds` (lettering only in x 32-127,
  y 64-95; records = the original block), and the recipe's second screen
  diff excludes only the original block.
* RAM and VRAM: the hooked loader now repeats what the old loader did (the
  layout copy to RAM `0x6080`, a 0xB40-word tile load), so the main RAM
  equals the original at every sampled frame and the VRAM differs only in
  the card's own tiles and map entries (see "Verification").

* `python -m tools.gfx.test_cards rom/baserom.ngc`: 15 of 15 tests pass
  (12 without the ROM).
* The harness recipe passes for all 40 cards on a copy of the snapshot ROM:
  VRAM tiles and the plane-1 map equal the records; the main RAM, palettes,
  sprites, plane 2, the emblem tiles and the VRAM tiles after the card's own
  equal the snapshot ROM; the screens equal the snapshot ROM outside the
  original lettering block; the sequence check is identical at frames 400,
  600 and 900.
* Cards reached in play without RAM pokes, and 13 skip variants, match too.
* The side-by-side sheets (original | English, 1x and 3x, and full screens)
  were reviewed.

## Done

### How a card is shown (round 1)

* Selecting a stage on the scenario map stores the chapter number
  (hotspot index + 1, 1-20) at RAM `0x5490` (code `0x29B63B`). The scenario
  script then fades out and sets the main-loop state to the card scene
  `0x29EC74` (`st32 0x29EC74, 0x4002` at `0x29B6EC`, its only reference).
  `0x29EC80` sets task 0 to the script at `0x29ECB0`.
* `0x29ECB3` (native code) picks the **set**: bit (chapter - 1) of the long
  at RAM `0x546E` (cleared-stage bits; `0x29A53E` counts them). Clear =
  **story set** (first visit), set = **area set** (a cleared stage again).
  * story: tile sheet `0x29F34A`, layout table `0x29EEA2`
  * area: tile sheet `0x2A09CA`, layout table `0x29EECA`
* It copies the chapter's layout record (`0x31` words) to RAM `0x6080`, then
  copies `0xB40` words (360 tiles) of the sheet to VRAM `0xA440` (tiles
  `0x44`-`0x1AB`) with `0x200B37` (a direct `ldir.w`, or queued for the VBlank
  copy at `0x400E` by `0x200194` when the display is on).
* Palettes: the text palette (4 colors at `0x29EF02`: transparent, white,
  light blue, dark blue) goes to RAM `0x60E2`; the emblem palette `0x29EEF2`
  (gray) or `0x29EEFA` (gold) to RAM `0x60EA`, gold when the byte at
  `0x29EE8D + chapter` is 1 (chapters 14-17).
* Script at `0x29ED39`: plane palettes black, emblem tiles (`gfx2a 0x29EF0A
  -> 0xA000`, tiles 0-0x43), emblem map (`gfxfe 0x2A1E4A -> 0x9800`, 20x19,
  plane 2), display on, emblem fade-in, then at `0x29EDD4` `gfxfe 0x6080,
  0x9208` draws the text layout on plane 1 at column 4, row 8 (plane 1 is
  in front), text fade-in (about 60 frames), final palette (`gfx26 0x60E2 ->
  0x8280` at `0x29EE2A`), hold 180 frames, fade-out. A/B (bit 4 of
  `0x201B37`) skips ahead; every path goes through the one `gfxfe` at
  `0x29EDD4`.
* Timing from `stage0_selected.state`: map fade-out frames 0-25, tiles loaded
  at 29-30, emblem fade-in 34-63, text map drawn at 95, text fade-in 101-159,
  hold until 341, fade-out 341-372.
* `gfxfe` (handler `0x2005C7`, drawing routine `0x2009F1`): `[w][h]` then
  `w*h` map entries, written row by row from the map address, columns
  wrapping at 32; zero entries are written too (tile 0 is the emblem's blank
  tile). `0x2009F1` takes XIY = block, IX = map address and clobbers BC, D,
  WA, XHL, IZ. Plane 1 holds nothing else during the scene, and its scroll is
  0, 0.

### Data layout (original ROM)

| Address | Size | Content |
|---|---|---|
| `0x29EE8E` | 20 | emblem palette flag per chapter (0 gray, 1 gold, 2 free battle) |
| `0x29EEA2` | 40 | story layout table: 20 u16 offsets from the table start |
| `0x29EECA` | 40 | area layout table: 20 u16 offsets |
| `0x29EEF2` | 8 | emblem palette, gray |
| `0x29EEFA` | 8 | emblem palette, gold |
| `0x29EF02` | 8 | text palette |
| `0x29EF0A` | 0x440 | emblem tiles (68 tiles, VRAM 0x00-0x43; no text in it) |
| `0x29F34A` | 0x1680 | story text sheet, 360 tiles (VRAM 0x44-0x1AB) |
| `0x2A09CA` | 0x1480 | area text sheet, 328 tiles (the loader copies 0x1680 bytes; the last 32 tiles are the following data, unused) |
| `0x2A1E4A` | 0x2FA | emblem map, `[20][19]` + entries |
| `0x2A2144` | 18 x 0x62 | story layout records (chapters 18-20 share one) |
| `0x2A2828` | 18 x 0x62 | area layout records (chapters 18-20 share one) |

All of these are used only by the card scene code (`0x29ECB3`-`0x29ED50`).
The data is raw (2bpp tiles, no compression). A layout record is `[w=12][h=4]`
+ 48 map entries (palette 0, no flips): a 96 x 32 block at screen (32, 64).

### The original lettering (measured in round 2)

From `python -m tools.gfx.cards decode` and the 40 harness screenshots
(`test_original_rows` checks the rows on every card):

* **Block.** Every original card is drawn as the same 12 x 4 cell block at
  plane-1 column 4, row 8 (screen x 32-127, y 64-95): a heading band (rows
  8-9) and one title band (rows 10-11). The widest lines fill the block
  (96 px with the outline).
* **Rows.** Each line is an 11-px band of ink inside a 16-px band. The
  heading (screen rows 8-9) has its ink in band rows 2-12 and its outline in
  rows 1-13; a title line (rows 10-11) has its ink in rows 4-14 and its
  outline in rows 3-15. Cards 14-20 and the area cards leave rows 8-9 empty.
* **Colors.** Ink color 1 (white) in 1-px strokes, outline color 3 (dark
  blue), plane-1 palette 0 = the text palette. Color 2 (light blue) marks a
  few stroke joins only: 0-21 pixels per card, mostly in the heading glyphs.
* **Outline.** 1 px. About 95% of the outline pixels touch the ink on one of
  4 sides (a 4-neighbor ring); the rest close the square corners at the ends
  of horizontal strokes. The ring has gaps on the diagonals elsewhere.
* **Numbers.** The chapter numbers in the heading have 2-px strokes (about
  10 px tall); the other heading glyphs and all titles have 1-px strokes.
* **Centering.** Lines are centered in the 96-px block, which is centered on
  the screen; the heading is 44 px (36 px for the final chapter).
* **Punctuation.** None of the original titles ends in an ellipsis glyph;
  chapters 3, 12 and 16 trail off through their grammar (a dangling
  particle or conjunction).

### Card text (meaning)

Story set (first visit). Chapters 1-12 show "Episode N" above the title; 13
shows "Final Episode"; 14-20 show only the title.

| Ch | Area | Heading | Title meaning |
|---|---|---|---|
| 1 | Estrada's Manor | Episode 1 | Quickening / first stirrings (literally fetal movement) |
| 2 | Gross Region | Episode 2 | The starving ones (archaic plural "those who hunger") |
| 3 | Satsu Peninsula | Episode 3 | "Those who believe..." (first half of a saying, trails off) |
| 4 | Lichtfloss | Episode 4 | The northern kingdom |
| 5 | Roden Region | Episode 5 | The dead |
| 6 | Litt Island Waters | Episode 6 | The sorcerer |
| 7 | Nessa Region | Episode 7 | A voice that asks / questions |
| 8 | Norodom Region | Episode 8 | What desire invites / brings about |
| 9 | Megaholten | Episode 9 | Resolve |
| 10 | Shagall Marsh | Episode 10 | The knight of darkness |
| 11 | Lego Islands | Episode 11 | Tears |
| 12 | Am Sea of Trees | Episode 12 | Darkness and silence, and then (trails off) |
| 13 | Laika Lakeside | Final Episode | White night (the midnight sun) |
| 14 | Krono Mountains | - | Deep in the mountains / the mountain recesses (gold emblem) |
| 15 | Ein Peninsula | - | Treasure (gold emblem) |
| 16 | Wind Dunes | - | Blood and flesh, and... (gold emblem) |
| 17 | Freia Isles | - | Samurai (gold emblem) |
| 18-20 | Free Battle Area 1-3 | - | Free Battle Area (one shared card) |

Area set: one line with the area name, the same names as the scenario-map
stage labels (`0x29C562 + 12 * k` in `translation/en/ui.txt`, hotspot table
`0x29C4FE`). The area card for 18-20 has no number.

### English cards

`translation/en/cards.txt` (widths include the outline; the limit is the
original block's 96 px):

| Ch | Story card (heading / title) | px | Area card | px |
|---|---|---|---|---|
| 1 | Chapter 1 / Quickening | 50 / 54 | Estrada's Manor | 83 |
| 2 | Chapter 2 / Those Who Hunger | 52 / 95 | Gross Region | 67 |
| 3 | Chapter 3 / Those Who Believe | 52 / 95 | Satsu Peninsula | 82 |
| 4 | Chapter 4 / Northern Kingdom | 53 / 92 | Lichtfloss | 52 |
| 5 | Chapter 5 / The Dead | 52 / 49 | Roden Region | 68 |
| 6 | Chapter 6 / The Sorcerer | 52 / 70 | Litt Island Waters | 92 |
| 7 | Chapter 7 / A Voice That Asks | 52 / 95 | Nessa Region | 69 |
| 8 | Chapter 8 / What Desire Brings | 52 / 96 | Norodom Region | 82 |
| 9 | Chapter 9 / Resolve | 52 / 41 | Megaholten | 59 |
| 10 | Chapter 10 / The Dark Knight | 57 / 83 | Shagall Marsh | 72 |
| 11 | Chapter 11 / Tears | 55 / 32 | Lego Islands | 65 |
| 12 | Chapter 12 / Silent Darkness… | 57 / 89 | Am Sea of Trees | 86 |
| 13 | Final Chapter / White Night | 68 / 58 | Laika Lakeside | 74 |
| 14 | Mountain Depths | 85 | Krono Mountains | 85 |
| 15 | Treasure | 49 | Ein Peninsula | 66 |
| 16 | Of Blood and Flesh | 95 | Wind Dunes | 57 |
| 17 | Samurai | 41 | Freia Isles | 54 |
| 18-20 | Free Battle Area (shared) | 86 | Free Battle Area (shared) | 86 |

"Chapter N" matches the dialogue ("Once you clear Chapter 3, ...",
`script.txt`). The area names equal the scenario-map labels (including
"Litt Island Waters" and "Ein Peninsula"), "The Dark Knight" is the glossary
term, "The Sorcerer" fits the glossary's Jenga (the chapter 6 boss).

### Wording decisions (provisional, for the owner)

The task fixed the wording of every title. Four of them cannot fit the
original 96-px block in title16 (even with the 4-px word gap), so they were
shortened; the owner may change any of them (one line each in `cards.txt`):

| Ch | Now | px | Spec wording | px | Other options that fit (px) |
|---|---|---|---|---|---|
| 3 | Those Who Believe | 95 | Those Who Believe… | 103 | The Believers… (79) |
| 4 | Northern Kingdom | 92 | The Northern Kingdom | 115 | - |
| 12 | Silent Darkness… | 89 | Darkness and Silence, / and Then… (two lines) | 112 / 56 | Darkness, Silence (91), Dark Silence, and… (96), Dark, Silent, and… (92), Silence and Then… (95), Darkness, then… (86) |
| 14 | Mountain Depths | 85 | Deep in the Mountains | 111 | Deep Mountains (80), In the Mountains (85), Into the Mountains (96) |

Notes: "Those Who Believe" pairs with chapter 2's "Those Who Hunger", and
the original title has no ellipsis either. "Silent Darkness…" keeps the
darkness, the silence and the trailing "and then" (the ellipsis) of the
original in one line, as the original has it; the trailing "and then" leads
into the final chapter's "White Night". "Darkness, Silence" would echo the
chapter's own dialogue ("...a world of death, ruled by darkness and
silence.") more literally, but loses the trailing "and then"; "Darkness,
Silence…" is 99 px (97 with three periods). Restoring a spec wording that
is wider than 96 px, or chapter 12's second line, would break the owner's
bounds rule; it needs the owner's explicit approval and a change of
`MAX_LINE` / `MAX_TITLES` / `BANDS` in `cards.py` (the earlier version
centered such lines over the black background and put a second title line in
rows 12-13).

Typography: the two trailing titles end in the font's ellipsis glyph (three
dots 2 px apart), which stays clearer after outlining than three typed
periods (dots 1 px apart).

### Style (the original's, see above)

Constants in `tools/gfx/cards.py`:

* `STYLE = Style(ink=1, outline=3, outline8=False)`: white ink, 1-px
  dark-blue outline grown to 4 neighbors. An 8-neighbor outline was
  compared on all cards: it fills every diagonal and looks heavier than the
  original, whose ring is 4-neighbor except at horizontal stroke ends.
* `BAND_TOPS = (2, 4)`: glyph row 0 on row 2 of the heading band and on
  row 4 of the title band. The 11-row `title16` glyph box (capitals rows 0-8,
  descenders 9-10) then covers exactly the original ink rows (2-12 and
  4-14), and the outline the original outline rows.
* `BOLD_DIGITS = True`: the heading's digits get 2-px strokes
  (`textart.embolden`), like the original numbers; "Chapter" keeps 1-px
  strokes like the original heading glyphs. A heading that is bold
  throughout was also compared: much heavier than the original.
* `SPACE_ADVANCE = 3`: a 4-px word gap (title16's own SPACE gives 5 px).
  Between the outlines of two words 2 px of background remain, so the word
  breaks stay clear (compared side by side with the 5-px gap); the lines are
  more compact, like the dense original lettering, and 4 lines that were
  1-2 px too wide fit the block.
* Lines are centered on the screen, `x = (160 - width) // 2`, which equals
  the original's left-biased centering in its block. Plane-1 palette 0 (the
  text palette) is not written; color 2 is not used.
* `ORIG_BLOCK = (4, 8, 12, 4)`, `MAX_LINE = 96`, `MAX_TITLES = 1`: the
  lettering stays in the original block.

Result, against the original (`compare_*` sheets of the recipe): same block,
rows, colors, outline and center; the numbers stand out as in the
original. The difference that comes from the English itself: lower-case
letters have a 6-px x-height against the 11-px kana and kanji, so the lines
look lighter.

### Implementation

`patch/src/cards.asm` (hand-written; labels prefixed `card_`):

    .org 0x29ECB4       ; was: ld.b B, (0x5490) / ld.l XWA, (0x546E)
    call card_load      ; (after the scene code's push.l XIY, which 0x29ED34 pops)
    jr   0x29ED02       ; palette setup, unchanged
    .org 0x29EDD4       ; was (script): gfxfe 0x6080, 0x9208
    .db 0x2E / .d24 card_draw / .db 0xCE, 0x20   ; ncall card_draw; cnt0 0x20 (the next op sets the same)
    .org GFX_CARDS
    .include "../../build/gfx/cards/data.asm"     ; card_story (+0), card_area (+0x50), records
    card_sets (24 bytes), card_find / card_load / card_draw (156 bytes)

* `card_sets`: per set, the record table (`card_story` / `card_area`), then
  the original tile sheet and layout table of the set (the addresses the old
  code loads; `test_hook_sites` checks them against the original code).
* `card_find`: XIX = the card's record, XIY = its set in `card_sets`, XHL =
  2 * (chapter - 1), with the original set test (shift the cleared-stage
  bits right `chapter` times; carry = cleared). A chapter outside 1-20 (never
  seen) shows chapter 1's card instead of reading past the tables.
* `card_load` (hook 1) does what the old code did, in the same order: it
  copies the card's original layout record (`0x31` words) to RAM `0x6080`
  (nothing reads it anymore, but the RAM stays as the original leaves it),
  then loads `0xB40` words to VRAM `0xA440` with the game's copy `0x200B37`:
  first the card's own tiles, then the rest of the original sheet. So the
  copy is as long as the old one and every other tile is the original's.
  (`ret ULE` guards the second copy; a card has at most 48 tiles.)
* `card_draw` (hook 2, script `ncall`; keeps XDE and XIY for the script VM):
  IX = the record's map address, XIY = record + 8, `call 0x2009F1`. Every
  record's block is the original 12 x 4 block at `0x9208`, so it writes the
  same 48 map entries as the old `gfxfe 0x6080, 0x9208` (0 for blank cells).
* The skipped old code (`0x29ECBA`-`0x29ED01`) and the old sheets and layouts
  stay in the ROM. `card_load` reads the old layout tables, layout records
  and sheets (`0x29EEA2`-`0x2A2F0B`) at run time, so no other writer may
  change them: `test_apply_to_original` checks that this target leaves them
  alone, and the recipe's RAM and VRAM comparison with REF would show a
  change made by anything else.

`tools/gfx/cards.py` (`build(ctx)`): parses `cards.txt`, renders each card on
a 160 x 32 canvas (screen rows 8-11) with the card fonts (`card_fonts`:
title16 with the 4-px word gap, and for the heading also bold digits),
encodes the original 12 x 4 block of it (columns 4-15; lettering outside the
block is an error), numbers the tiles from `0x44` in order of first use
(identical tiles shared, no flips; blank cells = entry 0), and writes
`build/gfx/cards/data.asm` and the previews (the block's background is
lighter than the rest). Record: `.dl tiles`, `.dw words` (8 per tile), `.dw`
plane-1 map address, `.db w, h`, `w*h` map entries, then the tiles. The
tables sit at fixed offsets of `GFX_CARDS` (+0 and +0x50), so `check` and the
recipe read the records back from any built ROM.

Sizes with the current text: 36 records, 920 tiles (12 to 40 per card),
18,696 bytes of data and 180 bytes of code and `card_sets`:
`0x3A0000`-`0x3A49BB`, 18,876 of the 24,576 bytes of `GFX_CARDS`.

### Verification (round 2, fix round 1)

Test ROM: `python -m tools.gfx.apply <scratch>\snap3\ogre_en.ngc t.ngc
--target cards` on a fresh copy (SHA-1 `d4b80493...`, the same on two
copies): 2 hooks (12 bytes) and `0x3A0000`-`0x3A49BB`; nothing else changes.
A BPS made from the original ROM to this test ROM passes the audit (longest
literal run found in the original: 7 bytes).

* `python -m tools.gfx.cards recipe t.ngc <scratch>\snap3\ogre_en.ngc OUT
  --state <scratch>\snap3\states\stage0_selected.state`: all 40 cards ok.
  Records in ROM = sources; VRAM tiles at `0xA440` and the plane-1 map =
  record, nothing else on plane 1; main RAM, palettes, sprites, plane-2 map,
  emblem tiles and the VRAM tiles after the card's own = the snapshot ROM;
  0 pixels differ outside the original block (and so 0 outside y 64-111);
  sequence (no input, A at 45, 120, 200): identical at 400, 600 and 900.
* RAM through the scene (scratch `ramcmp.py`: 10 variants from
  `stage0_selected.state`: no input, A at 45, 96 or 120, B at 30, and the
  poked story 4, 12, 17 and area 6, 18; a 64 KB dump every 4 frames to frame
  960): the main RAM (`0x4000`-`0x6FFF`), the K2GE registers, palettes and
  sprites are identical at every sampled frame. The plane-1 map differs only
  in the original block while the card is shown; VRAM tiles differ only in
  the card's own tiles until the stage reloads them (frame about 400), and
  are identical after. (Before this round the layout buffer `0x6080`-`0x60E1`
  differed to frame 960 and the tiles after the card's own differed too.)
* In play, without pokes (scratch `natural.py`): the scenario-map states
  with the cursor on stages 0, 1, 2, 3 and 12 (stage 0 with the hotspot input
  in `docs/testing.md`, the others with A at frame 10; stage 12 also with a skip at
  150) show the story cards of chapters 1, 2, 3, 4 and 13: every 4th frame to
  600, the screen is identical outside the original block and the main RAM
  is identical; the lettering differs only while the card is shown (frames
  116-384). The area set cannot be reached in play from the available states
  (cleared stages are not selectable hotspots); the poked recipe runs the
  same set test.
* Skips (scratch `seqcheck.py` runs, compared by `seqfast.py`): no input; A
  at 45, 94, 96, 120, 150, 200, 300, 350; B at 30, 100; three presses; A
  held: every third frame to 960 is identical outside the original block,
  the lettering differs only while the card is shown, and the main RAM at
  frame 960 is identical.
* `test_cards`: 15 of 15 with the ROM (12 without it); `test_all`: 7 modules
  pass.

The sound CPU's work RAM (`0x709A`-`0x70E6`, `0x7105`-`0x715D`,
`0x7632`-`0x76BC`) still differs from the snapshot ROM at some sampled
frames (37-88 of 241, per variant), as before this round. Per-frame dumps
(scratch `z80phase.py`) show 1-4 bytes per differing frame, values off by one
(`0x709A`: `0x56` against `0x57`) or single-frame values, and never the state
of the frame before or after: the sound driver runs the same sequence at a
slightly different phase. The cause is cycle timing: the hooks take a few
hundred CPU cycles more or less than the old code (the copy length is now the
same, so the copy is not the cause). The harness cannot record audio, so
gfx-verify should listen to one card scene in the player.

Scratch evidence (machine-local; it shows the original art), in the session
scratchpad: `r2-gfx2-cards-fix\` (this round: `t.ngc`, `recipe\` with
`compare_story_1x.png`, `compare_story_3x_1.png`, `_3x_2.png`,
`compare_story_full.png` and the same for `area`, `sheet_story.png`,
`sheet_area.png`; `z_bounds.png` (the formerly wide cards at 4x, a red frame
just outside the original block); `natural\`, `seq\`, `new1\` (RAM),
`zp\`; `measure.py` (candidate wordings)); `r2-gfx2-cards\` (round 2:
decoded originals, style variants, `orig.py`).

## How to test / reproduce

    python -m tools.gfx.cards fit                         # widths, tiles, sizes (no ROM)
    python -m tools.gfx.test_cards rom/baserom.ngc        # 15 tests (12 without the ROM)
    python -m tools.gfx.apply <scratch>\snap3\ogre_en.ngc t.ngc --target cards    # on a fresh copy
    python -m tools.gfx.cards recipe t.ngc <scratch>\snap3\ogre_en.ngc OUTDIR --state <scratch>\snap3\states\stage0_selected.state --exe <scratch>\snap3\ngp_harness.exe
    python -m tools.gfx.cards check t.ngc OUTDIR\test     # records in ROM, and VRAM dumps <set>_NN\mem_*.bin
    python -m tools.gfx.cards preview OUTDIR [--rom ROM]  # the English cards only
    python -m tools.gfx.cards decode rom/baserom.ngc OUTDIR   # the original cards (local only)

`recipe` pokes copies of the state (RAM `0x5490` = chapter, `0x546E` = `1 <<
(chapter - 1)` for the area set, 0 for the story set), runs the harness to
frame 201 on both ROMs with a shot and a VRAM dump at 200, checks and
compares them, runs the sequence check, and writes the contact sheets
(`sheet_story.png`, `sheet_area.png`) and the side-by-side sheets
(`compare_<set>_1x.png`, `compare_<set>_3x_1.png`, `_3x_2.png` (screen rows
56-119), `compare_<set>_full.png`: snapshot ROM on the left, test ROM on the
right). It takes about a minute. REF must be the same ROM without the cards.
Keep OUTDIR in `build/` or a scratch folder: it shows the original art.

Changing the text: edit `cards.txt`, run `fit` (every line at most 96 px),
then `test_cards` and the recipe, and review the sheets. Changing the style:
the constants at the top of `cards.py`.

## Open issues

* Wording: the four shortened titles (chapters 3, 4, 12, 14) and "Chapter N"
  / "Final Chapter" / "White Night" are provisional owner decisions (see
  "Wording decisions"); the orchestrator lists them in `STATUS.md`.
* Sound timing: the sound CPU's work RAM differs at some frames (a phase
  difference, see "Verification"); to be confirmed by ear in the player.
* The original's color-2 pixels at a few stroke joins have no English
  counterpart (the font has 1-px strokes without joins to soften); the
  review agreed that none is needed.
* `cards.txt` is not yet in the localization export (`tools/text/l10n.py`).

## Next steps

* `gfx-verify`: enable the target with the others (`FULL_BUILD`), build, and
  run the recipe on `build/ogre_en.ngc` against a `--no-gfx` build; listen
  to one card scene in the player.
* Orchestrator: add `cards.txt` to the localization export; record the card
  wording as provisional owner decisions.
