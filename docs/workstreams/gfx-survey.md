# Graphics survey: remaining pre-drawn Japanese

## Goal

Find every pre-drawn Japanese graphic beyond the four round-1 targets (title
package, intro narration, chapter cards, menu labels), with a static inventory of
every graphic that scripts and native code load, and plan each new target the way
the round-1 reports did: storage, loader, space, English wording, replacement path,
and a harness state that shows it. Round-2 task `gfx-survey` of
`gfx-pipeline.md` (section 8, task 4).

## State

Survey done (2026-10-09, round 2). `tools/gfx/inventory.py` lists, filters,
renders and classifies every tile block the game loads: 834 distinct blocks, all
classified (723 no text, 79 English, 20 round-1 targets, 12 Japanese). The 12
Japanese blocks are four new targets:

| # | Target | Players see it? | Size | Path | Priority |
|---|---|---|---|---|---|
| 1 | "Deployed" tag on the organize status pane | yes, every stage | 5 tiles, 40x8 px | in place, 2 x 80 bytes, no hooks | high |
| 2 | "Paralysed!" hit-reaction label in battle | yes, when a paralysing attack hits | 2 tiles, 16x8 px | in place, 32 bytes, no hooks | medium |
| 3 | Ending epilogue text, 5 endings, 87 lines | no: its display code has no reference | 87 x 32 tiles | in place, only if restored | low (owner decision) |
| 4 | Text screen in the boot bank | no: its loader has no reference | 144 tiles | none | none |

No compressed graphics exist: every loader copies raw 2bpp tiles, raw map
entries or raw colour words.

## Done

### Method (`tools/gfx/inventory.py`)

1. **Scripts.** The text walker (`tools.text.extract.build_walker`) plus 77 script
   entries that it misses. Those are started by native code that the walker never
   visits:
   * task slots, `ld.l R, (script << 8) | n` then `ld.l (0x4086 + 0x38 * task +
     0/4/8), R`. One example is the organize screen setup at `0x21260B`, which loads
     the sheet of target 1 and is started at `0x212684`;
   * `ld.l XDE, script` followed by a jump or call to `0x20023D`;
   * `calr 0x20023C`.
2. **Script ops.** `gfx2a`, `gfx2c` (tiles), `gfxfe` (maps), `gfx26`, `gfx28`
   (palettes) and `anim` (sprite lists).
3. **Native loaders.** Every call or jump to `0x200B37` or `0x200194` (tiles),
   `0x200B33` (palettes) and `0x2009F1` or `0x2009F4` (maps). XIY, IX and BC come
   from a backward search over the local control-flow graph, so a loader with two
   branches yields both sources.
4. **Table-driven loaders.** The source of these loaders is computed at run time.
   Each table was found by reading its loader, and its entries are enumerated:
   * menu icons `0x2172D2` and menu labels `0x218112`;
   * map unit icons `0x201FC6 + 64 * id`;
   * the result banners at `0x2086AB`;
   * intro lines (table `0x28D1EA`) and card sheets (`0x29ECFE`);
   * tarot cards (records `0x219918`);
   * ending text (table `0x2A3058`);
   * battle backgrounds (pointer tables `0x2CDDCC` and `0x2CDE6C`, 80 records of
     two layers);
   * scenario popup icons (lists `0x29C083` and `0x29C121`).
5. **Filters** (as specified):
   * tiles: dest `0xA000`-`0xBFFF`, source in ROM below `0x36746D`, 1 to
     `0x1000` words;
   * maps: dest `0x9000`-`0x9FFF`, header 1-32 x 1-32;
   * palettes: dest `0x8200`-`0x83FF`;
   * anim: 1-64 sprites.

   A native or table load whose dest comes from a task's tile field passes when
   its source and size pass ("dest set at run time"). RAM sources are counted
   separately as dynamic.
6. **Renders** (local only, `build/gfx/inventory/`):
   * a grey sheet per block;
   * map blocks drawn with the tiles and palettes of their script run, else of the
     loads stored nearest in ROM (a guess, checked in the harness where it
     mattered);
   * sprite lists that have a `tile` base (for example the game-over art);
   * 27 labelled contact sheets.
7. **Classes.** The `CLASSES` table in the module holds the verdict per block
   (address and English description). A block missing from it prints as
   `unclassified`.

### Counts (`rom/baserom.ngc`)

Scripts: 5,807 entries and 20,411 instructions from the text walker. The 1,848
extra seeds add 77 entries, for 5,899 entries and 20,858 instructions in all.

| Kind | Op | Before | After | Of which dest set at run time | RAM source |
|---|---|---|---|---|---|
| tiles | `gfx2a` | 1,081 | 1,075 | 0 | 2 |
| tiles | `gfx2c` | 14 | 12 | 0 | 0 |
| tiles | native `0x200B37` (132 call sites; one op per source found) | 242 | 228 | 222 | 0 |
| tiles | native `0x200194` (13 call sites) | 13 | 0 | 0 | 5 |
| tiles | table loads (10 tables, 237 entries) | 237 | 237 | 55 | 0 |
| map | `gfxfe` | 861 | 855 | 0 | 5 |
| map | native `0x2009F1` (88 sites) / `0x2009F4` (3 sites) | 92 / 3 | 76 / 0 | 4 / 0 | 2 / 0 |
| map | battle-background table | 160 | 160 | 0 | 0 |
| palette | `gfx26` / `gfx28` | 389 / 17 | 347 / 0 | 0 | 40 / 0 |
| palette | native `0x200B33` (26 sites) | 26 | 12 | 7 | 4 |
| palette | battle-background table | 160 | 160 | 0 | 0 |
| anim | `anim` | 1,542 | 1,520 | 0 | 8 |

* With the text walker alone the walk finds 1,064 `gfx2a` uses and 621 distinct
  `gfx2a`/`gfx2c` sources before filtering, the same as the first scratch scan.
  With the extra seeds there are 631 distinct sources, 623 after filtering.
* The walk also decodes some data as script; the filters remove it:
  * all 17 `gfx28` (dests such as `0x3C1D` and `0x2828`);
  * 10 `anim` whose "lists" hold 158-235 sprites. These are native sprite
    callbacks: the sprite builder jumps to the list address when the task
    palette byte is `0x7x`;
  * 4 `anim` whose source is not ROM data (for example `0x514000`). The other 8
    filtered `anim` have RAM sources.
* Distinct tile blocks after filtering: 834, 518,240 bytes (32,390 tiles).

### What the blocks are (by screen)

The tool's `CLASSES` table has the full list. In summary:

* **No text (723 blocks).** This covers:
  * character portraits (`0x2797CC`-`0x28C6FF`) and event landscapes
    (`0x274F5D`-`0x2797CB`);
  * battle animation frames and spell effects (`0x2E8000`-`0x35BFFF`, about 500
    blocks) and small unit sprites (`0x35C697`-`0x35E617`);
  * battle backgrounds (`0x2CF390`-`0x2DCB2F`) and map terrain tiles
    (`0x273870`);
  * map unit icons (`0x202006`), menu icons (`0x2172D2`) and popup icons
    (`0x29E7CE`);
  * scenario map art (`0x29D402`), the tarot reading scene (`0x297651`-
    `0x299470`), intro clouds (`0x29312D`, `0x29376D`) and the card emblem
    (`0x29EF0A`);
  * digits, frames and link-battle icons.
* **English originals (79 blocks), kept as they are.** None of these needs new art.
  * Map HUD sheet `0x20A588`: PAUSE, NEXT Lv, stat names, COST, GOTH, EXP, ITEM,
    TAROT, UNIT, CITY, OK!, BAD, UP.
  * Stat-up sprites `0x201ECB`-`0x201FCB`, unit window field labels `0x206C9B`.
  * Stage clear screen `0x20B5CB` ("Congratulation!" (sic), YOU COMPLETED THIS
    MAP., BONUS MONEY, Goth.).
  * Game over art `0x20BE14` (sprite lists `0x20BCDB` "Game", `0x20BD77` "Over").
  * Banners: FIND OUT! `0x20C25E`, FIGHT IT OUT! `0x20C418`, LIBERATION
    `0x20C62A`, LUCKY!! `0x20C7CA`, THANK YOU `0x20C93A`, Boo!Boo! `0x20CAAA`.
  * Labels: BOSS! `0x20CC1A`, READY `0x20CC5A`, NEXT `0x217F52`.
  * Tarot card art (44 blocks from `0x21C0F9`): roman numerals and English
    captions.
  * Publisher logo screen `0x28FBB1`, data load screen `0x29A849` (stained glass
    and "Lv-"; DATA LOAD and NOTHING are font text), scenario banner `0x29C9A4`.
  * Ending results screen `0x2AFF4E` (CHAOS FRAME, PT., CONQUEST, DAYS) and the
    staff roll, which is font text in Latin letters (`0x2A36BC`, window renderer).
  * Battle: MISS and digits `0x2C9AFD`, WAKE / LEVEL UP! `0x2CC784`, zzz
    `0x2F99A2`, M-SHILD (sic) `0x2F9E6F`, AGI UP! `0x2FB123`, R-AGAIN
    `0x2FB269`, DEF DOWN `0x2FB39D`, DEF UP! `0x2FB4BC`.
* **Round-1 targets (20 blocks), excluded and cross-referenced:**
  * menu labels `0x218112` (`gfx-labels.md`);
  * title package `0x28D307` (`gfx-title-logo.md`);
  * 15 intro lines `0x290F5D + 0x240 * n` (`gfx-intro-narration.md`);
  * card sheets `0x29F34A`, `0x2A09CA` and the emblem `0x29EF0A`
    (`gfx-chapter-cards.md`).
* **Japanese (12 blocks):** the four new targets below.

Screens in the task's priority list:

| Screen | Result |
|---|---|
| Game over | English art |
| Ending and staff roll | English: font staff roll and results art. The epilogue text (Japanese) is unused |
| Stage clear and liberation | English art |
| Battle results | English: "WINNERS" is font text; LEVEL UP!, MISS and digits are art |
| Organize and status panels | English field labels; the "deployed" tag is Japanese (target 1) |

### Classification of every block, by address range

Each row matches the blocks whose start address lies in the range. This is the
`CLASSES` table of the tool, with the block count and size from the run.

| Range (block starts) | Blocks | Bytes | Class | What |
|---|---|---|---|---|
| `0x200C99` | 1 | 160 | none | digits 0-9 for the tile-mapped printer |
| `0x201C03`-`0x201ECA` | 3 | 352 | none | small map effect sprites |
| `0x201ECB`-`0x201FEA` | 9 | 288 | english | stat-up sprites STR AGI INT CHA ALI LUK H.P. L.V. UP! |
| `0x202006`-`0x202D85` | 1 | 3,456 | none | map unit icons (54 x 4 tiles, table 0x201FC6) |
| `0x202D86`-`0x202E85` | 2 | 128 | none | map icons |
| `0x206C9B`-`0x206D0A` | 1 | 112 | english | unit window field labels F: B: MOVE ITEM |
| `0x20A588`-`0x20ADD7` | 1 | 2,128 | english | map HUD sheet: PAUSE, NEXT Lv, stat names, COST, GOTH, EXP, ITEM, TAROT, UNIT, CITY, OK!, BAD, UP |
| `0x20AFF5`-`0x20B134` | 1 | 320 | none | window frame pieces and digits |
| `0x20B5CB`-`0x20BCDA` | 1 | 1,808 | english | stage clear screen: Congratulation!, YOU COMPLETED THIS MAP., BONUS MONEY, Goth., digits |
| `0x20BE14`-`0x20C1E3` | 1 | 976 | english | game over art "Game" / "Over" (sprite lists 0x20BCDB, 0x20BD77) |
| `0x20C25E`-`0x20C3CD` | 1 | 368 | english | banner FIND OUT! |
| `0x20C418`-`0x20C5E7` | 1 | 464 | english | banner FIGHT IT OUT! |
| `0x20C62A`-`0x20C7C9` | 1 | 416 | english | banner LIBERATION |
| `0x20C7CA`-`0x20C939` | 1 | 368 | english | banner LUCKY!! |
| `0x20C93A`-`0x20CAA9` | 1 | 368 | english | banner THANK YOU |
| `0x20CAAA`-`0x20CC19` | 1 | 368 | english | banner Boo!Boo! |
| `0x20CC1A`-`0x20CC59` | 1 | 64 | english | label BOSS! |
| `0x20CC5A`-`0x20CC99` | 1 | 64 | english | label READY |
| `0x214450` | 1 | 2,048 | japanese | organize sheet: English field labels and frames, plus the "deployed" tag (tiles 0x5B-0x5F = ROM 0x214A00, 80 bytes) |
| `0x2148A0`-`0x21495F` | 1 | 192 | none | item icons (inside the organize sheet; another loader) |
| `0x2172D2` | 1 | 3,648 | none | menu icons (57 x 4 tiles; pictograms, one reads NEXT) |
| `0x217F52`-`0x217F91` | 1 | 64 | english | label NEXT |
| `0x218112`-`0x219791` | 1 | 5,760 | known | round-1 target: menu labels (gfx-labels.md) |
| `0x21C0F9`-`0x225FFF` | 44 | 41,184 | english | tarot card art: roman numeral and English caption (table 0x219918) |
| `0x273870`-`0x273EDF` | 1 | 1,648 | none | stage map terrain tiles |
| `0x274F5D`-`0x2797CB` | 10 | 14,992 | none | event background landscapes |
| `0x2797CC`-`0x28C6FF` | 49 | 54,112 | none | character portraits |
| `0x28D307`-`0x28F306` | 1 | 8,192 | known | round-1 target: title package (gfx-title-logo.md) |
| `0x28FBB1`-`0x2900B0` | 1 | 1,280 | english | publisher logo screen (word mark, web address) |
| `0x2904CB`-`0x290DCA` | 1 | 2,304 | japanese | unused text screen (target 4) |
| `0x290F5D`-`0x29311C` | 15 | 8,640 | known | round-1 target: intro narration lines (gfx-intro-narration.md) |
| `0x29312D`-`0x293DDC` | 2 | 3,248 | none | intro cloud tiles (two copies) |
| `0x297651`-`0x299470` | 3 | 7,712 | none | tarot reading scene art and sparkles |
| `0x29A849`-`0x29B048` | 1 | 2,048 | english | data load screen: stained glass, frames, Lv- (DATA LOAD and NOTHING are font text) |
| `0x29C9A4`-`0x29D1A3` | 1 | 1,536 | english | scenario map frame and the banner The Zenobian Age |
| `0x29D402`-`0x29E3F9` | 1 | 3,968 | none | scenario map art |
| `0x29E3FA`-`0x29E5F9` | 1 | 512 | none | scenario map symbols |
| `0x29E7CE`-`0x29EA4D` | 1 | 640 | none | scenario popup icons |
| `0x29EF0A`-`0x29F349` | 1 | 1,088 | known | round-1 target: chapter card emblem (no text; gfx-chapter-cards.md) |
| `0x29F34A`-`0x2A1E49` | 2 | 11,520 | known | round-1 target: chapter card sheets (gfx-chapter-cards.md) |
| `0x2A4E54`-`0x2AFC53` | 8 | 44,544 | japanese | ending epilogue text (target 3; listed in chunks of up to 16 lines) |
| `0x2AFF4E`-`0x2B054D` | 1 | 1,536 | english | ending results screen: CHAOS FRAME, PT., CONQUEST, DAYS, digits |
| `0x2B0850`-`0x2B088F` | 1 | 64 | english | SNK word mark (staff roll) |
| `0x2C9AFD`-`0x2C9BBC` | 1 | 192 | english | battle numbers: MISS and digits |
| `0x2C9D1D`-`0x2C9E1C` | 1 | 256 | none | battle icons |
| `0x2CC784`-`0x2CC7E3` | 1 | 96 | english | battle labels WAKE, LEVEL UP! |
| `0x2CCC3D`-`0x2CD60C` | 8 | 2,512 | none | battle effect sprites |
| `0x2CF390`-`0x2DCB2F` | 22 | 43,168 | none | battle backgrounds (tables 0x2CDDCC, 0x2CDE6C) |
| `0x2DEF17`-`0x2DEFA6` | 1 | 144 | none | link battle art |
| `0x2E3BDE`-`0x2E3BED` | 1 | 16 | none | cursor |
| `0x2E62AA`-`0x2E6B29` | 1 | 2,176 | none | link menu icons |
| `0x2E6C4A`-`0x2E6CB9` | 1 | 112 | none | digits 1-7 |
| `0x2E6CBA`-`0x2E6DB9` | 1 | 256 | none | window frame pieces |
| `0x2E6DBA` | 1 | 1,664 | japanese | link copy of the organize sheet, with the "deployed" tag copy (tiles 0x5B-0x5F = ROM 0x2E736A) |
| `0x2F99A2`-`0x2F9A91` | 1 | 240 | english | battle effect with sleep marks zzz |
| `0x2F9E6F`-`0x2F9EAE` | 1 | 64 | english | battle label M-SHILD (sic) |
| `0x2FB123`-`0x2FB162` | 1 | 64 | english | battle label AGI UP! |
| `0x2FB269`-`0x2FB2A8` | 1 | 64 | english | battle label R-AGAIN |
| `0x2FB39D`-`0x2FB3DC` | 1 | 64 | english | battle label DEF DOWN |
| `0x2FB4BC`-`0x2FB4FB` | 1 | 64 | english | battle label DEF UP! |
| `0x2FE5ED`-`0x2FE60C` | 1 | 32 | japanese | battle hit-reaction label meaning "paralysed!" (target 2) |
| `0x3206A9`-`0x3206C8` | 1 | 32 | none | battle hit-reaction marks !? |
| `0x2E8000`-`0x35BFFF` (other blocks) | 497 | 224,464 | none | battle animation frames and spell effects |
| `0x35C000`-`0x35E6FF` | 111 | 7,872 | none | small unit sprites (4-6 tiles each) |

Total: 834 blocks; no block is `unclear`.

### Target 1: the "deployed" tag (organize status pane)

* **Meaning:** "dispatched / deployed".
* **Where it shows:** on the status pane (View status) of a unit that is deployed
  on the stage map. It sits above the formation grid at x 8-47, y 54 and is drawn
  as five sprites. Their numbers depend on the unit: sprites 13-17 for unit 1 in
  the first recipe below, 9-13 for unit 2 in the two-unit recipe.
* **Storage:** ROM `0x214A00`-`0x214A4F`, 80 bytes. These are 5 uncompressed 2bpp
  tiles: tiles `0x5B`-`0x5F` of the organize sheet `0x214450` (2,048 bytes, 128
  tiles).
  * An identical copy lies at `0x2E736A`, in the link-battle copy of the sheet
    (`0x2E6DBA`, 104 tiles).
  * The harness confirms that VRAM tiles `0x13B`-`0x13F` equal both copies.
* **Loader:**
  * the organize setup script `0x21260B` runs `gfx2a 0x214450, 0xAE00, 0x400`
    (VRAM tiles `0xE0`-`0x15F`). Native code at `0x212684` starts it in task 0's
    slot when the organize screen opens;
  * the link screens load the same sheet (`0x2E3AD1`, `0x2E46D9`) or the copy
    (`0x2E28F3`, `0x2E31D1`, `0x2E3516`).
* **Display:**
  * an inline sprite script at `0x213AEE`: `pos16 0x3608`, `anim 0x213AFE`
    (5 sprites, tiles +0..+4 at dx 0..32 step 8), `tile 0x13B`, `pal 8`,
    `attr 0x10`;
  * native code at `0x213AD9`-`0x213AE9` decides when it runs.
* **Colours:** sprite palette 8 on this screen holds colour 1 white, colour 2
  blue and colour 3 near black.
* **Original layout:** a 32x8 box at x 4-35 of the 40-px strip, with a 1-px
  near-black border and a blue fill. Inside are four white glyphs with a dark
  outline. Strip columns 0-3 and 36-39 are transparent.
* **Space:** 40x8 px (5 tiles), in place. Nothing next to the strip is free, and
  nothing more is needed.
* **English (proposal):** **Deployed**, 37 px in `vwf8`, 39 px with a 1-px
  8-neighbour outline.
  * Draw it like the menu labels: colour 1 ink and colour 3 outline on a
    transparent background, centred in 40x8. The pane behind it is blue, so it
    reads well without a box.
  * The descenders of p and y use row 7, as in the menu labels.
  * Alternative with a box: a 40x8 box (border on columns 0 and 39, 38-px
    interior) with capitals in rows 1-6: SORTIE (32 px) or ON MAP (32 px).
    "Deployed" itself does not fit a box, because its descenders would cut the
    bottom border.
* **Replacement path:**
  * in place, no hooks, no new ROM: write the same 80 bytes at `0x214A00` and at
    `0x2E736A` (so that both sheets stay identical);
  * nothing else reads those bytes; they only arrive through the sheet loads;
  * `GFX_SPARE` is not used.
* **Harness:**
  * `S\command_bar_forecast.state` with
    `--input "10:L:2;40:L:2;70:L:2;110:A:2;200:A:2;260:A:2" --frames 400 --shot 360
    --vram 380`. This opens Organize screen, then Character, then View status of
    unit 1 in stage 0.
    * Check: VRAM `0xB3B0`-`0xB3FF` equals the 80 built bytes, and sprites 13-17
      are tiles `0x13B`-`0x13F`, palette 8, at x 8..40, y 54.
    * The screen must be identical to the unmodified build outside x 8-47,
      y 54-61.
  * Two deployed units: `B\organize-test-s0-2deployed.state` with
    `--input "10:D:10;40:A:2;90:R:2;130:A:2;230:A:2;290:A:2;370:R:2" --frames 460`
    (unit 1 from frame 300, unit 2 from frame 380).

### Target 2: the "paralysed!" hit-reaction label (battle)

* **Meaning:** "paralysis!": two characters and an exclamation mark.
* **Where it shows:** above every combatant that a paralysing effect hits. Sprite
  list `0x2FE0D0` has 2 records: tiles `0x2D`/`0x2E` at dx -8/0, dy -28,
  palette 15. Native code `0x2CB91D` (sprite callback `0x2CB959`) places them.
* **Storage:** ROM `0x2FE5ED`-`0x2FE60C`, 32 bytes: 2 uncompressed tiles. The
  palette is at `0x2FE325` (4 words). On screen the label uses only colours 1
  (light grey) and 3 (near black), on a transparent background. Its strokes are
  2 px wide.
* **Loader:**
  * script `0x2CBE94`: `gfx26 0x2FE325, 3, 0x8278` (sprite palette 15) at
    `0x2CBEB0`, then `gfx2a 0x2FE5ED, 0xA2D0, 0x10` (VRAM tiles `0x2D`-`0x2E`)
    at `0x2CBEB8`;
  * the same pair at `0x2CBF65`/`0x2CBF6D` (inline after `0x2CBF61`).
* **Trigger:**
  * Hit-reaction list 1 (`0x2CA340`, reached through pointer table `0x2CA338`)
    holds task-slot values. Entries 6 and 9 start `0x2CBE94`. Entry 17 starts
    `0x2CBF2C`, which waits until the byte at RAM `0x43EE` is negative and then
    runs the same pair at `0x2CBF65`/`0x2CBF6D`.
  * The battle effect handlers `0x2CA2AB` (effect type 12) and `0x2CA301`
    (effect type 17) apply the list. Both come from dispatcher `0x2C9F17`
    (handler table `0x2C9F42`), for each target whose reaction index (combatant
    record +44) is 6, 9 or 17.
  * None of the 22 tarot cards uses effect types 12 or 17. This was probed in
    `B\battle-inbattle_cmdbar.state` with the battle copy of the tarot stock (RAM
    `0x5772`) poked. Most likely a monster's or class's attack from a later stage
    triggers it; it has not been seen in play yet.
* **Space:** 16x8 px (2 tiles), in place.
  * A normal battle writes VRAM tiles `0x2F`-`0x30` with other graphics (write
    watch, Gring battle), so the label cannot simply grow.
  * A 24-px label would need a free tile, a relocated 3-record sprite list and
    four operand hooks. That is not recommended.
* **English (proposal):** **STUN**, as 16x8 pixel art: a 1-px outline column,
  then four 3-px capitals separated by 1-px outline columns. Text 5 rows high
  (rows 1-5) with an outline above and below, colours 1 and 3, transparent
  background.
  * No English word fits in `vwf8`: Zap! is 19 px and Stun! 23 px with the
    outline.
  * Alternative: a pictogram (a small zig-zag bolt and "!"), which needs no
    words.
* **Replacement path:**
  * in place, no hooks: write 32 bytes at `0x2FE5ED`;
  * the source is a hand-made text-art image (`gfx-pipeline.md` 1.4), because
    the shape does not come from a font;
  * the palette stays as it is.
* **Harness** (a RAM poke; the trigger has not been met in play):
  * Each living combatant's task slot gets the task-slot value `0x2CBE9401`
    (bytes `01 94 BE 2C`). The slots are RAM `0x412E`, `0x4166`, `0x419E`,
    `0x4246`, `0x427E` and `0x42B6`: the pointers at +4 of the combatant records
    `0x5522 + 0x30 * k` and `0x5612 + 0x30 * k`.

        python -m tools.gfx.harness poke build\states\battle-inbattle_cmdbar.state st.state 412E=0194BE2C 4166=0194BE2C 419E=0194BE2C 4246=0194BE2C 427E=0194BE2C 42B6=0194BE2C
        H ROM --load-state st.state --input "10:B:2" --frames 120 --shot 40 --vram 40

  * At frame 40, sprites 0-9 are tiles `0x2D`/`0x2E`, palette 15, above five
    combatants, and VRAM `0xA2D0`-`0xA2EF` equals the 32 bytes. Check at frames
    20-50: the game clears the tiles again by frame 60. This was checked on the
    snapshot.

### Target 3: ending epilogue text (unused in the shipped game)

* **Content:** five endings, our summary:

  | Ending | Lines | Content |
  |---|---|---|
  | 1 | 11 | You became a dweller of the world of darkness. In a silent world you live as if forgetting everything; there is no more need to think of Zenobia, or even of your many friends. |
  | 2 | 24 | Your life in the world of darkness begins. Some of the humans brought there start to resist (they hate the dark, nothing ever changes). You have a few executed as an example, to keep the law of the world of darkness. |
  | 3 | 20 | You gained two new friends. Busy learning from them, you never noticed that many old friends had left you. But fighting the Empire takes more money and blood. |
  | 4 | 10 | The party that defeated the Dark Knight and his army spends its days gathering strength for a greater battle to come. |
  | 5 | 22 | One story ends. There were many meetings and partings; new days begin for everyone. Does this young man know that he must face a greater hardship? But that is another story. |

* **Storage:** `0x2A4E54`-`0x2AFC53`, 87 lines of 512 bytes. A line is 32 tiles
  (128x16 px): 16 top-row tiles, then 16 bottom-row tiles. Text is white on
  blue.
  * Table `0x2A3058` holds 5 x `[u8 lines][u24 first line]`: (11, `0x2A4E54`),
    (24, `0x2A6454`), (20, `0x2A9454`), (10, `0x2ABC54`), (22, `0x2AD054`).
  * The palette is `0x2A4E4C`.
  * The line map is the 20x19 block `0x2AFC54`. Routine `0x200A49` draws rows 4,
    7, 10 and 13, columns 2-17 (16x2 cells per line).
  * The line slots are VRAM `0xB400 + 0x200 * (k & 3)`, 4 lines per page.
* **Code:**
  * `0x2A30CB` picks the ending from RAM `0x45CC`;
  * script `0x2A344C`-`0x2A3527` copies 0x100 words per line through `0x2A34A0`
    and fades each line in.
  * No absolute, relative, script-branch or task-slot reference reaches
    `0x2A30CB` or `0x2A344C`.
* **What the shipped game does instead:**
  * the script of stage 12 (chapter 13, the last story chapter; dialogue
    `0x27050A`-`0x270AF8`) tells the five endings in dialogue (already in
    `script.txt`);
  * it sets `0x45CC` (`st8` at `0x270591`, `0x270751`, `0x2707D2`, `0x270967`,
    `0x270B1D`), then `st32 0x2A2F0C, 0x4002` at `0x270B45`;
  * the ending main state `0x2A2F0C` shows only the staff roll and the results
    screen, then returns to the boot sequence.
  * The ending illustrations of the same bank are also unreferenced: tiles
    `0x2A392A`, maps `0x2B0890`, `0x2B0B8A`, scene scripts behind table
    `0x2A303A`. They contain no text.
* **Plan (only if the owner wants to restore it):** text in a new
  `translation/en/epilogue.txt`, rendered per 128x16 line slot. In place, 87
  slots and 44,544 bytes, with the same line counts:
  * either two rows of `vwf8` per slot (about 52 characters);
  * or one row of `title16` (about 20 characters).

  Restoring also needs a hook in the ending task script `0x2A3077` that calls
  `0x2A30CB` and runs the epilogue before the staff roll, plus a decision on the
  epilogue's own exit (`st32 0x2A2F57, 0x4002`). This is not planned for now.
* **Harness (test ROM only, never in the build):**
  * In a copy of the snapshot ROM, write `2E CB 30 2A DA 4C 34 2A 80` (`ncall
    0x2A30CB`, `jump 0x2A344C`, `yield`) over the 9 bytes at `0x2A3077`.
  * For endings 2-5, also replace `ld.b A, (0x45CC)` at `0x2A30CD` with `21 0n
    00 00` (`ld.b A, n` and two `nop`, where n is the ending index 1-4, for
    example `21 01 00 00` for ending 2). The ending entry rewrites RAM `0x45CC`,
    so poking it does not work.
  * Then load a copy of `S\title_menu.state` with the main state set to the
    ending entry, `python -m tools.gfx.harness poke S\title_menu.state end.state
    4002=0C2F2A00`, and run 3,000-5,200 frames.
  * The same state on the unmodified ROM shows the real ending: the staff roll
    from about frame 100 (shot 300), the results screen from frame 7,416 (shot
    7,500). This is the only way to reach the ending screens today.

### Target 4: text screen in the boot bank (unused)

* **Storage:**
  * `0x2904CB`, 2,304 bytes: 144 uncompressed tiles of prose in 8-px glyphs,
    9 rows of 16;
  * palette fade target `0x2903CB`.
* **Code:**
  * loader script `0x28CB82` (`gfx2a 0x2904CB, 0xA000, 0x480`);
  * raster scripts `0x28CA37`-`0x28CACE`.
* **Reach:** none. None of these addresses is referenced, and a 7,000-frame
  power-on run never reads the block.
* **Plan:** none.

### Other VRAM writers

A harness sweep ran 205 states with A presses and a write watch on
`0xA000`-`0xBFFF`. Besides the two copy routines (`0x200178` for the VBlank
queue, `0x200B42` for direct copies) it found these tile writers:

* `0x200B6F`: the whole fixed-cell font of the tile-mapped printer (`0x6D8`
  words from `0x200C99`, loaded by `0x200B5A`; the patch already points this
  load, and the 10-digit load at `0x200B45`, at its English font);
* `0x200C0A`-`0x200C1B`: the window renderer's glyphs;
* `0x203EDD`: map unit icons from `0x201FC6`;
* `0x20D678`-`0x20D720`: two-digit numbers built from half-width digits at
  `0x20D914` and `0x20D964`;
* `0x217206`: menu icons;
* `0x2CB876`: a battle mask (AND);
* `0x3700C8`-`0x37010D`: the patch's VWF renderer.

None of them is a decompressor. No codec is needed.

## How to test / reproduce

Shorthand as in `gfx-pipeline.md` section 5:

* `H` = `scratchpad\snap\ngp_harness.exe`;
* `ROM` = `scratchpad\snap\ogre_en.ngc`;
* `S` = `scratchpad\snap\states`;
* `B` = `build\states`.

    python -m tools.gfx.inventory rom/baserom.ngc build/gfx/inventory            # about 12 s
    python -m tools.gfx.inventory rom/baserom.ngc build/gfx/inventory --no-png   # about 4 s

* The run prints the counts table above and the classes line `{'english': 79,
  'japanese': 12, 'known': 20, 'none': 723}`. It then lists the round-1 blocks
  (excluded) and the Japanese blocks: `214450 2904CB 2A4E54 2A6454 2A8454
  2A9454 2AB454 2ABC54 2AD054 2AF054 2E6DBA 2FE5ED`.
* Files (local only, never committed):
  * `inventory.txt`: every op with its verdict;
  * `blocks.txt`: block, size, users, class;
  * `tiles/`, `maps/`, `sprites/` and `contact/sheet_00.png`-`sheet_26.png`.
* A block reported as `unclassified` means the walk changed. Review it and add it
  to `CLASSES`.
* Harness recipes are given under each target.

Scratch evidence (machine-local, contains ROM graphics), all in the session
scratchpad under `r2-gfx-survey\`:

* `sweep\writers.txt` (VRAM writers);
* `dep3\` (the tag on the snapshot) and `tagcheck.py`;
* `para14\` (the paralysis label via the poke recipe; frame 40);
* `tarotprobe.py` (all tarot cards, battle copy of the stock);
* `epi_e0\`, `epi_f1\`-`epi_f4\` and `pages_*.png` (the five epilogues);
* `endpoke.py` (the ending main state);
* `boot\` (the 7,000-frame read watch).

## Open issues

* **Coverage limits of a static inventory.**
  * Scripts reached only through computed pointers may still be missed.
  * Known misses, found in the round-2 review by a VRAM content check (every
    non-blank tile of VRAM dumps from all saved states looked up in the base
    ROM). None of these blocks shows text, so the four targets are unchanged:
    * Scripts started by task-slot values that are held in data as a u32
      `(script << 8) | 1` (for example `0x2DCE57`, from `0x2C8676`, `0x2C86DE`
      and `0x2DEFBF`) or computed in code (`lda`, shift by 8, `ld L, 1` at
      `0x365A15`, which starts `0x2C7F21` in task 13). Seeding the data values
      (validated by decoding) adds 13 scripts and 11 tile blocks: full-screen
      battle effects `0x2DDAAD`, `0x2DDFC7`, `0x2DE61F`, `0x2DEA9F` and effect
      frames `0x2FC9B9`, `0x2FCB19`, `0x2FD141`, `0x301632`, `0x30822A`,
      `0x3213B6`, `0x321936`. Script `0x2C7F21` adds `0x2C9BBD` (12 tiles: frame
      pieces and the English captions ITEM and TAROT), `0x2C9C7D` and
      `0x2C9E55`.
    * Native loads with computed sources: the map HUD day/night dial
      `0x20AE44` (25 tiles, indexed by the table `0x20AE12` and copied one tile
      at a time at `0x203F1B`), the map unit icon at `0x202DC6` (4 tiles, icon
      slot `0x201FC6 + 64 * 56`; no class record uses id 56, so
      `table:map-unit-icons` does not list it; seen in the state
      `battle-s1_estrada_dead_ghost`; loader not traced), and 4 tiles at
      `0x204286` (seen in `towns-items_crystal`; loader not traced).
    * Review scratch (local only): `r2-review-gfx-survey\coverage.py` and
      `slotseeds.py`.
  * Native loaders with computed sources are covered only through the 10 tables
    listed.
  * The stage-specific map tiles copied from the RAM pointer `0x6092` (24 tiles
    per stage, terrain) are not enumerated.
  * The harness sweep covers the saved states of stages 0-3 only.
  * Later stages, link battles and the real ending have not been seen in play.
* **Paralysis trigger.** Which attack applies effect type 12 or 17 is not known.
  Note it when explore-battle meets it. The poke recipe tests the art meanwhile.
* **Epilogue.** The static analysis says it is unused. A play-through of the real
  ending (later stages) would confirm this.
* **Wording to review:** Deployed (or SORTIE / ON MAP in a box); STUN (or a
  pictogram).

## Next steps

1. Orchestrator: add a small target "tags" to the graphics pipeline (wave 2,
   after `gfx-lib` and `gfx-build`):
   * `tools/gfx/tags.py` and `test_tags.py`, with `translation/en/tags.txt`
     (`@deployed Deployed`) and `assets/gfx/tags/paralysis.txt` (16x8 text-art);
   * in-place writes `0x214A00` (80 bytes), `0x2E736A` (80 bytes) and
     `0x2FE5ED` (32 bytes), no hooks, no new ROM;
   * acceptance: the two harness recipes above, and identical screens outside
     the tag rectangles.
2. Owner decision: restore the epilogue (target 3) or leave it unused.
3. Re-run the inventory whenever the walker or the tables change. Any new block
   shows up as `unclassified`.
