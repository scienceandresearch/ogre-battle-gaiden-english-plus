# Graphics: pre-drawn menu labels

## Goal

Replace every pre-drawn Japanese menu/command label (graphics, not font
text) with English that looks like the original art: the labels under the
icons of the stage map command bar, the unit window, the item commands, the
organize screen, the in-battle command bar and the link-cable menus. Round 1
found and analyzed them; round 2 (wave 2, task `gfx-labels`) built the
target.

## State

Done (2026-10-09, round 2 wave 2). The target `labels` of the graphics build
(`tools/gfx/labels.py`, source `translation/en/labels.txt`) writes 44 English
labels in place; label 23 (NEXT, English in the original) keeps its art.
`FULL_BUILD = False` until the verify step enables all targets together.

* `python -m tools.gfx.test_labels rom/baserom.ngc`: 12 tests pass (also
  without the ROM, on a synthetic image).
* The six harness recipes of the acceptance list pass on a test ROM made from
  the English snapshot: the VBlank queue copies the expected label, VRAM
  equals the ROM and the built label, and every screenshot equals the
  snapshot's outside x 48-111, y 88-95 (34 dumps).
* All 45 labels were shown in the game and checked the same way: 33 through
  the menus, label 06 with RAM `0x6089` poked, and 0F, 11 and 24-2C by
  pointing the label task at their tables (see "How to test").
* Side-by-side sheets (original against English, 1x and 3x) of every label,
  static and in the game, were reviewed.
* Review round 1 (2026-10-09) passed every faithfulness and functional item
  and asked for one change: the preview colors in `labels.py` were the
  game's sprite palette 0, against `gfx-pipeline.md` 1.1. They are now our
  own (previews only; the ROM output is unchanged, SHA-1 of the test ROM
  identical). `test_labels` now also checks that labels 04 and 20 equal the
  map popup's Monitor and Organize entries. Everything was re-run: 12 tests
  with and without the ROM, `test_all` (7 modules), the six recipes (34 dumps)
  and the extra in-game runs of the other labels (58 dumps), all with 0
  pixels differing outside the strip.

## Done

### One label system for every icon menu (round 1)

* All icon-menu labels are sprites: 8 sprites in a row, 64 x 8 px,
  centered on the screen (sprites at x = 48..111, y = 88). The icons are
  background tiles on scroll plane 1 (2 x 2 tiles each) and contain no
  Japanese (pictograms; a few carry Latin letters: NEXT, ON, OFF, VS, 1, 2,
  P).
* Label graphics: 45 labels, uncompressed, 8 tiles = 128 bytes each, at
  ROM `0x218112 + 128 * n` (n = 0x00..0x2C). The block ends at `0x219791`;
  code follows at `0x219792` (tarot stock routines), so writes must stay
  inside the block.
* Tile format: K2GE 8 x 8, 2 bits per pixel, 16 bytes; each row is a
  little-endian 16-bit word with the leftmost pixel in bits 15-14
  (`tools/common/tiles.py`). Tile k of a label is columns 8k..8k+7.
* Icon graphics: 57 icons, 64 bytes each (tiles TL, TR, BL, BR) at
  `0x2172D2 + 64 * id` (id 0x00..0x38), immediately before the labels.
* Label task: script `0x217268` = `op04`, `anim 0x2172A9`, `pos16 x=0x50
  y=0x58`, then native code `0x217271` that runs every frame (yield and
  `jump 0x217270`):
  * VRAM destination = (task +54 & 0x1FF) * 16 + `0xA000` (the task's
    sprite tile);
  * label number = byte at (task +34, a table pointer) + (task +32, the
    selected index);
  * source = `0x218112 + label * 128` (`ld.l XIY, 0x218112` at `0x217291`);
  * `0x40` words are copied with `0x200B37` (queued for the VBlank copy at
    `0x200178`, or copied at once while the display is off).
  The copy is repeated every frame, and a read watch over the label block
  shows no other reader, so new ROM data shows up without any code change.
* Sprite layout `0x2172A9`: count 8, then 5-byte entries `[u16 added to the
  task's tile/attribute word][dx][dy][palette add]` (here tile +0..+7,
  dx = -32..+24 step 8, dy = 0), expanded every frame by the sprite list
  builder `0x200A8B` (task +52/+53 position, +54 tile word). It is shared
  by every menu.
* Entry scripts set the sprite tile and palette, then jump to `0x217268`:

  | Entry | Sprite tiles (VRAM) | Palette | Used by |
  |---|---|---|---|
  | `0x203FC7` | `0xC0`-`0xC7` (`0xAC00`) | sprite 0 | command bar, unit window, item commands |
  | `0x213471` | `0x160`-`0x167` (`0xB600`) | sprite 0 | organize screen (+ its item commands) |
  | `0x2C7FCA` | `0x001`-`0x008` (`0xA010`) | sprite 13, loaded from `0x2C9EE5` | in-battle command bar |
  | `0x2E4179`, `0x2E4189` | `0x1F8`-`0x1FF` (`0xBF80`) | sprite 0 | link-cable menus (task slot 4) |

  On the map and organize screens the icon tiles start right after the
  label tiles (`0xC8`, `0x168`), the link label ends at the last tile
  (`0x1FF`), and in battle the icons start at `0x06D`, so a label cannot
  simply grow past 8 tiles.
* Icon bar builder `0x21719E` (XWA = descriptor; it installs the VBlank
  continuation `0x2171B4`): descriptor = `[u16 centre map address][u16
  first tile]` then 2-byte entries `[map attribute high byte][icon id]`;
  the word at `0x4592` is the mask of entries shown, the bar is centered on
  their count. A menu's label table has one byte per descriptor entry, same
  index. Command bar mask (`0x2046B0`): base `0x00ED`; index 1 (Deploy
  unit) is added when `(0x61CE) < 7` and `(0x61CE) != (0x4693)`, index 4
  (Tarot cards) when `(0x5406) != 0`, and the high byte comes from
  `(0x6089)` (index 8, Return to map).
* Calls of the builder: `0x2046E8` (command bar), `0x205105`/`0x20643E`
  (unit window), `0x207217` (item commands from the map), `0x2126F0`
  (organize), `0x213DB2` (organize item commands), `0x2C6DCE` etc. (battle,
  several masks), `0x2E136A` / `0x2E3C6C` (link), `0x29BA9E` (scenario map
  popup: icons only, its label is font text, already translated).

### Menus and label tables (round 1)

Label numbers in hex.

| Menu | Descriptor | Label table | Entries (index: label) |
|---|---|---|---|
| Stage map command bar | `0x2047AA` | `0x2047C0` | 0: 23, 1: 00, 2: 20, 3: 01, 4: 05, 5: 03, 6: 04, 7: 22, 8: 06 |
| Unit window | `0x20560F` | `0x205629` | 0: 0E, 1: 10, 2: 12, 3: 13, 4: 14, 5: 07, 6: 0A, 7: 0B, 8: 0D, 9: 11, 10: 0C |
| Item commands (map Items, organize Items) | `0x2073CA`, `0x213E92` | `0x2157AF` (stored at `0x215671`) | 0: 18, 1: 19, 2: 1A, 3: 1B, 4: 1C, 5: 1D, 6: 1E |
| Organize screen | `0x2127DD` | `0x2127F5` | 0: 17, 1: 08, 2: 09, 3: 1F, 4: 0A, 5: 0D, 6: 01, 7: 02, 8: 0B, 9: 0C |
| In-battle command bar | `0x2C7FD9` | `0x2C7FEB` | 0: 05, 1: 10, 2: 15, 3: 21, 4: 16, 5: 01, 6: 05 |
| Link menu A | `0x2E1496` | `0x2E14A2` | 0: 27, 1: 28, 2: 29, 3: 2A |
| Link menu B | `0x2E40F8` | `0x2E4106` | 0: 24, 1: 25, 2: 26, 3: 2B, 4: 2C |

Label 0x0F is in no table (and has no help text): apparently unused. The HQ
small menu (A on HQ: NEXT / unit / location), the scenario map popup and the
Monitor settings panel show no graphic label. The unit window's Organize icon
(07) opens a second bar of the same menu (Formation, Dismiss, Change leader,
Transfer, Class change, as the unit allows).

### The original art (what the English copies)

Measured on the 45 original labels (`decode`, local only):

* Colors: 0 transparent, 1 the strokes (white in every palette seen), 3 the
  outline (near black). Color 2 occurs in 55 pixels of 18 labels (small
  marks inside glyphs) and differs between screens (sprite palette 0 on the
  map, palette 13 in battle), so the English uses colors 1 and 3 only.
* Glyphs: 1-px strokes on rows 1-6 in every label (6 px high); the outline
  takes rows 0-7.
* Outline: 1 px. Every 4-neighbor of the ink is outline (7,393 of 7,394
  pixels), and 86% of the diagonal-only neighbors too (2,638 of 3,070; the
  open ones are hand-trimmed corners, most often on row 7): an 8-neighbor
  outline.
* Placement: centered in the 64-px strip; an odd spare pixel mostly goes to
  the right (x = (64 - width) // 2); the widest labels fill x 0-63.

### The target (round 2)

| File | Content |
|---|---|
| `translation/en/labels.txt` | the English, `@NN text` per label, `@23 keep` |
| `tools/gfx/labels.py` | `build(ctx)`, the style constants, `fit`, `preview`, `decode`, `compare`, `check`, `recipes` |
| `tools/gfx/test_labels.py` | 12 tests |

* **Style** (constants in `labels.py`): `vwf8` glyph shapes (the game's
  English font: capitals on rows 1-6 like the original glyphs, x-height rows
  3-6), ink color 1, a 1-px 8-neighbor outline in color 3, transparent
  background, centered with `x = (64 - width) // 2`, glyph row 0 on strip row
  0. No bold: the original strokes are 1 px, and bold would not fit.
* **Output:** 8 tiles per label, left to right, no deduplication, at
  `0x218112 + 128 * n`; two in-place writes (labels 00-22 and 24-2C,
  5,632 bytes), range `0x218112`-`0x219791`, no hooks, no new ROM.
* **Descenders.** g, j, p, q and y use row 7, so the outline below their
  tails is cut by the strip edge (14 labels). The original never inks row 7.
  Two label variants were drawn and compared at 3x and 6x: compact tails
  inside rows 3-6 (every letter keeps its full outline) and tails raised by
  one row. The compact `g` reads as `a` ("Oraanize", "Reaister"), and the
  raised letters jump above the x-height. The `vwf8` shapes read best and
  were kept; the missing outline pixels under the tails are the only
  difference from the original treatment.
* **Previews** (`build/gfx/labels/`, never committed): `preview.png` (the 45
  labels as built, 4x, numbered), `compare_x1.png` and `compare_x3.png`
  (original | English for every label). Written by every build of the
  target. Their colors are our own (white ink, black outline, color 2 light
  violet, a green background), not the game's palettes: the sheets show the
  shapes, and the harness screenshots show the real colors.

### English wording

Our own wording, sentence case, full words where they fit (owner decisions of
2026-10-09: Finances, Rite of revival, Tactics, Retreat, Persuade, keep the
NEXT art, full words such as Add character and Remove). Widths are measured
with the outline (`python -m tools.gfx.labels fit`); the limit is 64 px.

| n | Meaning of the original | English | px |
|---|---|---|---|
| 00 | Dispatch a unit | Deploy unit | 48 |
| 01 | Items | Items | 25 |
| 02 | Look at status | View status | 51 |
| 03 | Forecast of the settlement of accounts | Finances | 38 |
| 04 | Monitor | Monitor | 32 |
| 05 | Tarot cards | Tarot cards | 52 |
| 06 | Return to the map | Return to map | 61 |
| 07 | Organize | Organize | 38 |
| 08 | Put characters in | Add character | 62 |
| 09 | Take characters out | Remove | 34 |
| 0A | Formation | Formation | 42 |
| 0B | Delete a character | Dismiss | 32 |
| 0C | Class change | Class change | 57 |
| 0D | Leader change | Change leader | 61 |
| 0E | Move | Move | 23 |
| 0F | View the destination (unused) | Destination | 49 |
| 10 | Battle commands | Tactics | 33 |
| 11 | Exchange characters (sends one to another unit) | Transfer | 39 |
| 12 | Replenish characters (recruit in a town) | Recruit | 32 |
| 13 | Buy items | Buy items | 42 |
| 14 | Rite of revival | Rite of revival | 63 |
| 15 | Run away | Retreat | 34 |
| 16 | Persuade | Persuade | 41 |
| 17 | Character (submenu) | Character | 44 |
| 18 | Use an item | Use item | 37 |
| 19 | Equip an item | Equip item | 43 |
| 1A | Take off an item | Remove item | 54 |
| 1B | Sell an item | Sell item | 36 |
| 1C | Throw away an item | Discard item | 53 |
| 1D | Rearrange | Sort | 20 |
| 1E | Organize the items | Tidy up | 32 |
| 1F | Exchange units | Swap units | 47 |
| 20 | Organize screen | Organize | 38 |
| 21 | Animation | Animation | 41 |
| 22 | Suspend | Suspend | 37 |
| 23 | NEXT (English in the original) | original art kept | 24 |
| 24 | Versus | Versus | 31 |
| 25 | Give characters | Send chars | 49 |
| 26 | Receive characters | Get chars | 43 |
| 27 | Type 1 rules | Type 1 rules | 53 |
| 28 | Type 2 rules | Type 2 rules | 54 |
| 29 | Register a player | Register | 37 |
| 2A | Custom | Custom | 32 |
| 2B | Give items | Send items | 47 |
| 2C | Receive items | Get items | 41 |

Full forms that do not fit: "Remove member" 68 px, "Send characters" 72,
"Get characters" 66, "Income forecast" 71, "Battle commands" 72.

Consistency (checked by `test_labels`): the item help texts in `ui.txt`
quote "Use item", "Equip item", "Remove item", "Sell item", "Discard item",
"Sort" and "Tidy up"; `script.txt` quotes "Deploy unit" (Game System Tips 5)
and "Rite of revival" (Tips 2); the map popup (B on the scenario map,
`ui.txt`, font text) names the same commands Monitor and Organize (labels 04
and 20), and its Link submenu Versus, Send chars, Get chars, Register and
Custom. All equal the labels. That submenu's Settings 1 / Settings 2 differ
from Type 1 rules / Type 2 rules in the original too. Tactics, Retreat,
Persuade and Animation match the battle help texts; Finances opens the
window titled "Income & Expenses". Labels 07 (unit window: formation,
dismiss, leader, transfer, class change) and 20 (command bar: the organize
screen) both read "Organize"; the original words them slightly differently
("organize" and "organize screen"), and their help texts tell them apart.

## How to test / reproduce

Repository root; `<scratch>` is the session scratchpad, `H` the snapshot
harness `<scratch>\snap3\ngp_harness.exe`, states in `<scratch>\snap3\states`.

```
python -m tools.gfx.labels fit                                   # widths, margins, descenders
python -m tools.gfx.test_labels rom/baserom.ngc                  # 12 tests (also without the ROM)
python -m tools.gfx.labels compare rom/baserom.ngc               # build/gfx/labels/compare_x1.png, compare_x3.png
copy <scratch>\snap3\ogre_en.ngc in.ngc                          # a fresh copy: applying twice is refused
python -m tools.gfx.apply in.ngc t.ngc --target labels
set NGP_HARNESS=<scratch>\snap3\ngp_harness.exe
python -m tools.gfx.labels recipes t.ngc in.ngc OUTDIR --states <scratch>\snap3\states
```

`recipes` runs the six acceptance runs on both ROMs and checks each with
`check` (exit status 1 on any failure):

| Run | State | Input (frames) | Dumps | VRAM | Labels |
|---|---|---|---|---|---|
| command bar | `command_bar_forecast` | `40:L:2;80:L:2;...;280:L:2` (330) | 30, 70, ..., 310 | `AC00` | 03 05 01 20 23 22 04 03 |
| unit window | `stage0_gameplay` | `46:A:2;100:R:2;150:A:2;200:R:2;240:R:2;280:R:2` (330) | 190, 230, 270, 310 | `AC00` | 0E 10 07 0E |
| item commands | `command_bar_forecast` | `10:L:2;50:L:2;90:A:2;170:R:2;...;370:R:2` (400) | 160, 200, ..., 360, 395 | `AC00` | 18 19 1A 1B 1C 1D 1E |
| organize | `hq_status_screen` | `20:B:2;100:R:2;140:R:2` (200) | 90, 130, 170 | `B600` | 02 0B 0C |
| organize, character | `hq_status_screen` | `20:B:2;60:B:2;140:R:2;...;340:R:2` (400) | 130, 170, ..., 370 | `B600` | 17 09 1F 0A 0D 01 17 |
| battle | `battle-inbattle_cmdbar` | `20:R:2;60:R:2;100:R:2;140:R:2` (200) | 10, 50, 90, 130, 170 | `A010` | 05 10 15 21 05 |

One run by hand: `H t.ngc --load-state STATE --frames N --input ... --shot
F,... --vram F,... --out DIR` (and the same on `in.ngc` into `REF`), then
`python -m tools.gfx.labels check t.ngc DIR --dest AC00 --expect 03,05 --ref
REF`.

The labels that the recipes do not reach (2026-10-09, all checked the same
way, 0 pixels differ outside the strip):

| Labels | State | How |
|---|---|---|
| 00 | `progress-stage1_gameplay` | `10:D:10;40:A:2;100:R:2` (command bar, stage 1 has a unit to deploy), dump 130 |
| 06 | `progress-stage1_gameplay` | `--poke 6089=01@5`, `10:D:10;40:A:2;100:L:2` (index 8 shown), dump 130 |
| 08 | `organize-test-rich-top` | `20:R:2`, dump 50 |
| 0A 0B 0C | `battle-unitwin_gring` | `20:L:2;60:A:2;120:R:2;160:R:2` (the unit window's Organize bar) |
| 12 13 | `towns-s1_leckart_unitwin` | Right every 40 frames (unit in a town) |
| 14 | `towns-s0_church_unitwin_dead` | Right every 40 frames (unit at a church) |
| 16 | `battle-neutral_battle_start` | `10:A:2;80:L:2`, dump 100 |
| 0F 11 24-2C | `command_bar_forecast` | the label task (slot 1, `0x40BE`) pointed at a table: `--poke 40E0=<table, 4 bytes LE>,40DE=<index>@5`, dump 30. Tables: unit window `0x205629` (index 9: 11), link A `0x2E14A2` (27-2A), link B `0x2E4106` (24 25 26 2B 2C), any ROM byte `0x0F` (`0x210356`) |

Evidence (machine-local, contains ROM art; session scratchpad
`r2-gfx2-labels\`): `rec_fix1\` (the six recipes, test and ref, after review
round 1; `rec1\` and `rec2\` before it, identical screenshots),
`fixruns.py` (all the extra runs above, checked with `check_dumps`, and the
in-game sheets) with its output `fix1\` (`allctx_x1.png`, `allctx_x3.png`,
`allctx_part0-2_x3.png`: one in-game crop per label, original | English),
`ctx1\*_x3.png` (per recipe), `cmp\compare_x1.png` / `compare_x3.png`,
`v3_a.png` (descender variants: original | vwf8 | compact | raised),
`orig_ascii.txt` and `analyze_orig.py` (the measurements above).

## Open issues

* Owner review of the descender treatment (see "The target"): the tails of
  g, j, p, q and y end on the strip's last row with no outline below them.
* Owner review of the wording, in particular 09 "Remove" (the organize bar
  shows it next to "Add character"; "Remove member" is 68 px), the
  abbreviation "chars" in 25/26 (as in the Link submenu), and 07 / 20 both
  "Organize" (see "Consistency"; 20 equals the map popup's entry for the
  same screen).
* The link-cable menus were seen only through the RAM poke above (they need
  a link partner).

## Next steps

* `gfx-verify`: remove `FULL_BUILD = False` from `tools/gfx/labels.py` (or
  enable all targets together) and run the recipes on the full build.
* If the owner changes a label that other texts quote (the table under
  "Consistency"), change `ui.txt` / `script.txt` in the same step;
  `test_labels` fails until they agree.
* Glossary candidates for the orchestrator: "Rite of revival" (church
  command), "Finances" (command bar; window "Income & Expenses"), "Retreat"
  (battle bar), and "Tactics" as the label of the battle-commands entry
  (unit window and battle bar).
