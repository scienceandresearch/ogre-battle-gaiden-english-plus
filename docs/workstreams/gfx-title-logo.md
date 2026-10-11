# Graphics: title logo

## Goal

Find the pre-drawn Japanese graphics on the title screen (the large game title and
its subtitle above "PRESS A BUTTON" / "NewGame Load Continue") and on every boot
screen before it (publisher logo, notices), work out where they are stored and how
they are loaded, and replace them with English drawn as original pixel art (our own
lettering) that matches the original very closely: same place and size, the
original palettes, the same outline, glow, shading and texture, and everything else
on the screen unchanged. Round 1 analyzed the screen and planned the replacement;
round 2 (wave 2, task `gfx-title`) built the target, then revised it after review.

## State

Done (2026-10-10, round 2 wave 2, revised the same day after review). The target
`title` of the graphics build (`tools/gfx/title.py`) writes the English logo and
the English warning window in place: no hooks, no new ROM, no palette writes.
`FULL_BUILD = False` until the verify step enables all targets together; `python
-m tools.gfx.apply IN OUT --target title` runs it.

* `python -m tools.gfx.test_title rom/baserom.ngc`: 18 tests pass (14 without the
  ROM). `python -m tools.gfx.test_all rom/baserom.ngc`: 7 modules pass.
* Test ROM from a fresh copy of the English snapshot (`snap3`, SHA-1
  `e63bffd1...`): 2,988 bytes change, all below `0x36746D` in the declared ranges;
  logo 177 of 201 tiles (70 front cells, 108 back cells), window 29 of 29.
  Applying it a second time is refused.
* Every harness recipe of the acceptance list passes (113 screenshot comparisons,
  details in "How to test"): each screenshot equals the snapshot's outside the
  logo band y 56-103 (and the window interior when the window is open), VRAM tiles
  and both plane maps equal the ROM package, the window map equals its ROM block.
  The warning window was reached for real (suspend data in the cartridge save,
  then NewGame) as well as with the test bypass; No, B, Continue and Yes behave
  and look as before outside the replaced text.
* The BPS audit passes (no literal of 8+ bytes from the original); the patch
  grows by 2.9 KB (116,695 bytes against the snapshot's 113,807).
* Side-by-side sheets of every replaced instance (original against English, 1x
  and 3x) were reviewed: title still, PRESS A BUTTON on and off, both fade-ins,
  the menu, the window (cursor on No, on Yes, fade-out after Yes), plus detail
  sheets of the band at 4x, the rows under the title, the fist, the kicker and the
  subtitle (original, round 1 and the revision).

## Done

### Review fixes (round 2, after review)

The review asked for one change and suggested others; all are in:

1. **The glow under the main title (required).** It ran one row lower and heavier
   than the original's and touched the subtitle. The main title now sits in the
   original's rows (fill y 65-83, black outline 84) and the glow ends at y 86:
   under the letters one row of blue mixed with cyan (85) and a few blue pixels
   (86); row 87 stays empty above the subtitle's outline (88), as in the original.
   The kicker moved to y 57-61, so its black top outline is on y 56, the band's
   first row (this also removes the flat blue line that its glow drew there).
   `test_treatment` checks the rows (no glow at y 87 or below, the blue share of
   row 85, only a few blue pixels on row 86).
2. **The glow by side.** Measured on the original by ring (distance from the
   fill) and by the side of the lettering, the draft now follows it: above the
   letters ring 2 is cyan (69% cyan, 6% blue, 23% black corners; the original
   69 / 2 / 28) and ring 3 mostly blue (53% blue, 16% cyan; the original 49 / 24);
   under them ring 2 is half blue (46% blue, 44% cyan; the original 44 / 40) and
   ring 3 sparse (18% blue); between letters and in counters ring 3 is a third each
   of cyan, blue and empty (34 / 37 / 29; the original 32 / 32 / 35); a few ring-4
   pixels. Ring 2 over all: 64% cyan, 24% blue, 11% black (the original 63 / 21 /
   10). The rules are `OUTER_GLOW`, `ENCLOSED_RING3`, `RING4` and `outer_side` in
   `title.py`.
3. **The fist's thumb.** The thumb of the fist (sprites in front of the logo, x
   107-113, y 64-71) is an outline with see-through holes that show the dark
   background in the original, whose letters keep clear of it. In round 1 the G
   of GAIDEN passed under it (15 fill pixels hidden) and the white G showed
   through the holes, so the thumb merged with the letter. Now the letters stop at
   the thumb: no fill and no glow in that box, only the black outline of the G
   (`THUMB`, 24 fill pixels left out). The thumb looks as in the original and the
   G reads with its top arm behind the thumb.
4. **The kicker at 1x.** Its fire fill is brighter (yellow, orange-red, dark red
   25 / 45 / 30% instead of the main title's 13 / 39 / 48%, without the darker
   edges), so the 2-px strokes of THE LEGEND OF read at native size; still the fire
   palette.
5. **Subtitle letters.** In `italic9.txt` the A's left leg is continuous (it jumped
   2 px, so the brown outline broke the stroke) and the N's diagonal now joins the
   right stem (it read as a vertical middle stroke).
6. **Horizontal reach.** The glow reaches x 2-157 (the original x 3-156) and the
   fill x 5-155 (the original 6-154): 1 px further out on each side, for the
   longer English line.
7. **warn-test guard.** The test-only bypass decodes the instruction at
   `0x28CDA4` (`jr Z, 0x28CDD0`) with `tools.recomp.tlcs900` instead of comparing
   stored bytes.

### The English title (round 2, as built)

Wording (`translation/en/title.txt`; the owner's rule: translate every element of
the original logo, nothing else):

| Element | Original (meaning) | English | Where (screen px) | Treatment (as the original) |
|---|---|---|---|---|
| Kicker | "Legend of", the first part of the big title | THE LEGEND OF | fill x 5-72, y 57-61 (map row 7, left of the arm); outline from y 56 | fire fill (brighter shares), black outline, glow (none above: the band's top) |
| Main title, fire part | "Ogre Battle" | OGRE BATTLE | fill x 5-99, y 65-83; outline 84, glow 85-86 | mottled fire fill (plane-1 palette 0), black outline and cyan/blue glow (plane-2 palette 0) |
| Main title, white part | "side story" | GAIDEN | fill x 104-155, y 65-83 (from a cell boundary) | white/gray fill (plane-1 palette 1), same outline and glow; only the G's outline under the thumb |
| Subtitle | "Prince of Zenobia" | PRINCE OF ZENOBIA | letters x 22-137, y 89-97; outline x 21-138, y 88-98; row 87 empty | thin italic amber letters with a brown outline (plane-2 palette 5) |
| Warning window | "The suspend data will be erased. Is that all right?" + yes/no | The suspend data will be erased. / Is that OK? / Yes / No | interior rows 1-3, Yes at column 6, No at column 12 | the window's own colors (plane-1 palette 3), vwf8 |

All palettes are `keep`: the art uses the original colors by index (color 1-3 of
the palettes above), and nothing is written to the palettes. The main title's fill
is in the original's rows (65-83, the outline on 84, the glow on 85-86, row 87
empty), the subtitle letters in exactly the original's rows 89-97. The English
line is 1 px further out on each side than the original (fill x 5-155 against
6-154, glow x 2-157 against 3-156). The subtitle is wider than the original's (x
37-124), because the English text has 15 letters against 7 characters; it stays
centered.

Files (all text, all ours):

| File | Content |
|---|---|
| `translation/en/title.txt` | the wording (`@kicker`, `@logo FIRE|WHITE`, `@subtitle`, `@window` x2, `@yes`, `@no`) |
| `assets/font/logo19.txt` | main title font: 26 capitals, 19 rows, 3-px stems, rounded bowls, a slanted counter in O and Q, tapered bar ends on E, F and T, pointed A; letters 1 px apart, words 4 px |
| `assets/gfx/title/kicker5.txt` | kicker font: 26 capitals, 5 rows, 2-px stems |
| `assets/gfx/title/italic9.txt` | subtitle font: 26 capitals, 9 rows, 1-px strokes on a 5x9 grid, slanted 1 px every 3 rows, letters 3 px apart |
| `assets/gfx/title/logo_front.txt` | plane 1, 160x48 text-art (fill), drawn by `draft` |
| `assets/gfx/title/logo_back.txt` | plane 2, 160x48 text-art (outline, glow, subtitle), drawn by `draft` |
| `tools/gfx/title.py` | the target: draft (style rules), encoder, checks, previews, harness-dump check, warn-test |
| `tools/gfx/test_title.py` | 18 tests |

The build reads the two committed layers. `python -m tools.gfx.title draft` draws
them from `title.txt` and the three fonts; the layers' headers name the wording
they show and the build stops when `title.txt` says something else. The test
checks that the committed layers are exactly the draft.

How the style rules reproduce the original treatment (measured on the original
package in a scratch analysis; the rules are constants in `title.py`):

* **Outline.** Every 4-neighbor of the fill is black (the original: 865 of 871).
  The original also fills about a quarter of the outer diagonal corners and most
  pixels between two diagonal fill pixels (a step of a slanted edge: 28 of 36)
  with black; the draft fills all steps and a quarter of the corners (chosen by a
  hash of the position).
* **Glow.** By the side of the lettering a pixel is on (`outer_side`: the fill
  straight above, below, left or right within 6 px, or diagonally next to it;
  "enclosed" when in more than one direction). On the outer edges ring 2 and ring 3
  take the measured shares of `OUTER_GLOW` (see "Review fixes" for the numbers);
  enclosed places (counters, gaps between letters, the row between the kicker and
  the main title) glow cyan in ring 2 and a third each of cyan, blue and empty in
  ring 3, with a few ring-4 pixels. Strength is smooth value noise, so blue and
  cyan come in patches as in the original. Glow only in map rows 7-10 above y 87,
  never in reserved cells, nothing but the outline under the fist's thumb.
* **Fire fill.** Smooth value noise with colors by share: dark red 48%,
  orange-red 39%, yellow 13% (the original: 48 / 40 / 12), a little brighter
  inside the strokes, darker on the edges (right and bottom more) and on the first
  and last rows, as the original. Neighbor correlation 0.49 (the original 0.43).
  The kicker uses the same palette with brighter shares (25 / 45 / 30) and no
  darker edges, so that its 5-px letters read at 1x.
* **White fill.** Gray 42%, white 36%, light gray 22% (the original 44 / 34 / 22),
  grayer toward the right and bottom edges, whiter toward the left and top,
  mixed as in the original rather than a hard bevel.
* **Subtitle.** 1-px amber strokes (the original's strokes are 1 px) with a brown
  outline on the 4 neighbors and on diagonal steps and some outer corners (the
  original: 281 of 283 4-neighbors brown, 6 of 6 steps, about a quarter of the
  outer corners), italic like the original's lettering, 9 rows tall like its amber
  rows.
* **Cells.** One palette per 8x8 cell and plane: the fire/white split falls on the
  cell boundary x 104; the glow (rows 7-10) and the subtitle (rows 11-12) never
  share a cell. The two old fill sprites are dropped (flag list count 50 -> 48).
* **Stroke weight and size.** Stems 3 px (the original's strokes are 2-4 px), cap
  height 19 px (the original's characters 19-20 px).
* **Sprites in front of the logo.** The original's letters avoid the arm, fist
  and pole sprites. The English letters keep clear of the thumb (above); two
  places remain where an opaque sprite covers a letter corner: the lower tip of
  the pole hides the top-left corner of the I (6 px, x 124-126, y 65-67) and two
  dark fist pixels lie on the top-left corner of BATTLE's E (x 94-95, y 65). The
  line cannot move: GAIDEN starts on the cell boundary x 104 and ends at x 155.

Codex drafts: the orchestrator's two Codex image drafts (`codex-title/` in the
session scratch; prompts there) were the style reference for the English layout
(kicker top left, letter weight, 1-px letter spacing, white GAIDEN). Their pixels
are not used: at the native grid they are noisy and inconsistent (repeated letters
differ), so the letters were drawn as fonts and the treatment generated by the
rules above, which keeps repeated letters identical and the treatment close to the
original's. No new Codex generation was needed; nothing from Codex is committed.

Encoding (unchanged from round 1's prototype, now in `title.py`): tiles from the
230-tile pool (the old window tiles first, then the old logo tiles, then the tiles
nothing references), one `TileBank` with flips shared by the window and both
layers; map entries for rows 7-12 of both planes (reserved cells left out) and
window rows 1-3; the flag sprite count. Budget: logo 177 of 201 tiles (70 front
cells, 108 back cells), window 29 of 29.

### Boot screens before the title (round 1, all checked)

| Screen | When | Japanese? |
|---|---|---|
| Notice "for color hardware only" | only on a monochrome system: boot code at `0x28C695` compares the BIOS system-type byte `0x6F91` with `0x10` and runs `0x28C76A` instead of the logo | font text drawn by the window renderer from `0x28C7C3`; already in `ui.txt` (`@28C7C3`), checked on screen in English with a scratch ROM that forces the branch |
| Publisher logo on white | frames 0-150 from power-on (`0x28C7E8`) | no: word mark, registered sign and web address in Latin letters |
| Black | frames 150-300 | nothing drawn |
| Cloud intro with narration | from frame 300 | yes, pre-drawn: workstream "intro narration" |
| Title | A at frame 700 skips the intro; the title fades in at frame 740 | yes: the logo and a warning window (below) |

Idling on the title for about a minute returns to the publisher logo and the intro
(attract loop). There is no demo or other screen. No code reads the BIOS language
byte. "PRESS A BUTTON", "NewGame", "Load", "Continue", "SNK" and the copyright
line are pre-drawn in English already.

### What shows Japanese on the title screen (round 1)

1. **Main title** (the Japanese title, literally "Legend of Ogre Battle, side
   story"). It spans the full width at map rows 7-10 (pixels x 3-156, y 61-86).
   It has two layers:
   * outline layer on scroll plane 2 (behind): black outline with a cyan and blue
     glow, plane-2 palette 0, tiles `0x001`-`0x04B`;
   * fill layer on scroll plane 1 (in front): mottled fire colors (yellow,
     orange-red, dark red; plane-1 palette 0) for the series name, and white-gray
     (plane-1 palette 1) for the last two characters ("side story"). Tiles
     `0x076`-`0x0B1`, rows 8-10. Two sprites (tiles `0x0B2`/`0x0B3`, sprite
     palette 2, the last two records of the flag sprite list) add fire pixels
     where a fire letter reaches into a white-palette cell.
2. **Subtitle** ("Prince of Zenobia"): thin italic amber letters with a brown
   outline. It uses one layer: plane 2, palette 5, tiles `0x04C`-`0x061`, rows
   11-12 (pixels x 37-124, y 88-98).
3. **Warning window**: a 20x5-cell framed window with a pre-drawn sentence ("The
   suspend data will be erased. Is that all right?") and yes/no answers. It is
   drawn on plane 1 at rows 13-17 when NewGame or Load is chosen while suspend data
   exists (`0x29A4BB` reads the suspend slot's status byte; erased flash means no
   suspend data). The glyphs are copies of the game's 8x8 font baked into tiles
   `0x062`-`0x075` and `0x12F`-`0x131`. The window uses plane-1 palette 3 (white
   ink on dark blue), frame tiles `0x133`-`0x139`, and blank filler `0x132`.
   Answer cursor: sprite tile `0x13A` at y 128, x = 40 + 48 * choice (0 = yes at x
   40, 1 = no at x 88; the constants are at `0x28CE4C`/`0x28CE4F`). The cursor
   starts on "no", Left/Right toggles, A confirms, B cancels.

The flag, arm and fist artwork (plane-2 palette 4, one solid tile in plane-2
palette 5, plane-1 palette 2, and the first 48 sprites of the flag list) has
no text and stays as it is.

### Title screen data: one uncompressed package in bank 0x28 (round 1)

All addresses are CPU addresses. Everything is stored raw (no compression), so a
same-size replacement can be written in place.

| Address | Size | Content |
|---|---|---|
| `0x28CBC6` | 2 | background color (dark blue) |
| `0x28D277` | 56 | plane-2 palettes 0-6 (4 colors each) |
| `0x28D2AF` | 32 | plane-1 palettes 0-3 |
| `0x28D2CF` | 56 | sprite palettes 0-6 |
| `0x28D307` | 0x2000 | 512 tiles (all of character RAM), tile N at `0x28D307 + 16*N`; tile 0 is blank |
| `0x28F307` | 251 | flag artwork sprite list (count 50, 5-byte records: 48 art sprites, then the 2 logo fill sprites) |
| `0x28F402` | 126 | 6 metasprites of 4 sprites (spinning card cursor, tiles `0x100`-`0x117`) |
| `0x28F480` | 61 | "PRESS A BUTTON" sprite row (12 sprites, tiles `0x1E0`-`0x1EB`) |
| `0x28F4BD` | 6 | yes/no cursor (one sprite, tile `0x13A`) |
| `0x28F4C3` | 2 + 760 | plane-1 map: header (width 20, height 19), then 20x19 entries |
| `0x28F7BD` | 2 + 200 | warning window map, 20x5, copied to `0x9340` (plane 1, row 13) |
| `0x28F887` | 2 + 760 | plane-2 map, 20x19 |
| `0x28CECF`, `0x28CF15`, `0x28CF5B` | 70 each | menu label maps (17x2), one per selected item, drawn at `0x9B44` |

Formats:
* Tiles: K2GE 8x8, 2 bits per pixel, 16 bytes; each row is a little-endian word,
  leftmost pixel in bits 15-14 (as in `tools/common/tiles.py`).
* Map entries: 16-bit little endian; bits 0-8 tile, bits 9-12 palette, bit 14
  vertical flip, bit 15 horizontal flip. A map block starts with one byte width
  and one byte height and is copied row by row into the 32-entry-wide plane.
* Sprite records: `[tile bits 0-7][attributes: bit 0 = tile bit 8, bit 7/6 =
  horizontal/vertical flip][x][y][palette]` after a count byte. The loader adds
  the origin set by the script (`pos16`: low byte x, high byte y) and ORs the
  priority bits `0x18`. Lower-numbered sprites win where sprites overlap.
* Palettes: 12-bit colors `0x0BGR`, 4 per palette, color 0 transparent.

Loader (every reference to the package is in the title code in bank 0x28):
* Script at `0x28CBC8` (entered at `0x28C8DA` with the screen off):
  `gfx26 src, count-1, dst` copies the palettes, `gfx2a 0x28D307, 0xA000, 0x1000`
  copies all tiles (0x1000 words), `gfxfe 0x28F4C3, 0x9000` and
  `gfxfe 0x28F887, 0x9800` copy the maps, and `pos16 0x0050` + `anim 0x28F307`
  place the flag sprites (origin x = 80). Plane 1 is in front of plane 2
  (`0x8030` = 0); sprites have priority 3 (in front of both).
* Fade-in: `0x28CC17` and `0x28CC8B` interpolate sprite palette 2 and plane-1
  palettes 0-1 (the logo fill) from black (`0x295642`) to white (`0x2955A2`)
  and then to their ROM values (`0x28D2DF`, `0x28D2AF`) with `0x295EB9`. The
  title lettering flashes white before it settles. `0x28C8EE` then sets sprite
  palette 2 and plane-1 palettes 0-2 from ROM. Plane-2 palettes are not faded.
  The English fill uses the same palettes, so it fades the same way.
* "PRESS A BUTTON": sub-script `0x28D00F`, origin `pos16 0x6A18` (x 24, y 106),
  shown 50 frames, hidden 30. Its sprite palette 2 is shared with the two old logo
  fill sprites.
* Menu: `0x28CD1D` onwards; the cursor skips disabled items. A on NewGame or Load
  calls `0x29A4BB`; if suspend data exists it spawns `0x28CDD8`
  (`gfxfe 0x28F7BD, 0x9340`, cursor sub-script `0x28CE3E`). Closing clears the
  window with `0x2009CC`.
* Nothing else writes tiles while the title is up: the harness write watch shows
  the one block copy at frames 736-737, then only menu label redraws.

### Space, colors and tile budget (round 1)

Canvas: the full width, map rows 7-12 (x 0-159, y 56-103), as two layers. The
menu begins at row 13 (y 104), and "PRESS A BUTTON" is at y 106-113.
* Front layer (plane 1, in front): each 8x8 cell uses one palette. Palette 0
  (fire: yellow, orange-red, dark red) or palette 1 (white, light gray, gray).
  Palettes 2-3 belong to the flag highlights and the warning window.
* Back layer (plane 2, behind): each cell uses one of palette 0 (blue, cyan,
  black: the outline and glow), palette 5 (brown, amber, near-black: the
  subtitle), or palettes 1 and 6 (loaded but unused on this screen). Palette 5's
  color 3 also colors one solid square of the flag (tile `0x148`).
* Reserved cells (keep the original entries): row 7 (y 56-63), columns 11 and
  13-15 (x 88-95 and 104-127), in both planes. They hold arm artwork.
* The arm and fist sprites are drawn in front of everything. They cover about
  x 85-140 for y 56-63, and thin parts of the fist reach y 71 between x 88 and
  127. Letters may pass under them, but those pixels are hidden; the thumb (x
  107-113, y 64-71) has see-through holes, so the letters keep clear of it (round
  2 revision).
* Row 7 is unobstructed at x 0-84 and x 141-159. The flag's lower tip reaches
  about y 52 near x 49-60 (row 6), so the kicker stays within row 7.
* Tiles available in place: 158 tiles of the old logo plus 49 tiles that nothing
  on this screen references (`0x00B`, `0x0B4`-`0x0BF`, `0x0F4`-`0x0FF`,
  `0x11E`-`0x11F`, `0x12C`-`0x12E`, `0x13B`-`0x13F`, `0x1DE`-`0x1DF`,
  `0x1EC`-`0x1F7`), plus the 23 old window glyph tiles: 230 in all. The window
  text takes 29, which leaves 201 for the logo.

### Technical path: in place, no code changes, no free ROM

* Tiles: the new tiles go over pool slots (`0x28D307 + 16*N`).
* Maps: the entries of rows 7-12 in the plane-1 map (`0x28F4C5 + 2*(20*row +
  col)`) and the plane-2 map (`0x28F889 + ...`), and window rows 1-3
  (`0x28F7BF + ...`). Reserved cells are not written.
* Palettes: none written (all `keep`). The ranges for plane-2 palettes 0, 1, 5
  (colors 1-2) and 6 and plane-1 palettes 0-1 are declared, so own colors remain
  possible; plane-2 palette 5 color 3 is never writable (the flag uses it).
* Sprites: the count byte at `0x28F307` goes from 50 to 48 (drops the two old fill
  sprites).
* No new ROM: `0x3B0000`-`0x3EFFFF` holds the game's save blocks. The fallback (a
  repointed package in `GFX_TITLE`) is not needed.

## How to test / reproduce

```
python -m tools.gfx.test_title rom/baserom.ngc     # 18 tests (14 without the ROM)
python -m tools.gfx.title fit                      # widths, cells, palettes, tile budget
python -m tools.gfx.title draft [OUTDIR]           # redraw the layers (default build/gfx/title/draft)
python -m tools.gfx.title preview OUTDIR --rom rom/baserom.ngc   # local only (shows the original art)
python -m tools.gfx.title decode ROM OUTDIR        # local only
python -m tools.gfx.apply SNAP_COPY.ngc t.ngc --target title    # on a fresh copy (a second apply is refused)
python -m tools.gfx.title warn-test t.ngc tw.ngc   # test ROM only: NewGame always opens the window
python -m tools.gfx.title check t.ngc DUMPDIR [--window]        # harness --vram dumps against the package
```

Harness recipes (snapshot harness `snap3\ngp_harness.exe`, which emulates the
flash chip; reference = the same run on the snapshot ROM; "equal" = `python -m
tools.gfx.harness diff` reports 0 pixels outside the given rectangles):

| Recipe | Input | Result (2026-10-10, revision) |
|---|---|---|
| title | `--frames 1100 --input 700:A:2 --shot 736,738,...,764,800,1010,1040 --vram 800` | equal outside y 56-103 at all 18 frames; VRAM `0xA000`-`0xBFFF` = ROM `0x28D307`; both 20x19 maps = ROM |
| natural fade-in | no input, `--frames 6500`, shots 6300-6496 every 4 | equal outside y 56-103 (50 frames) |
| menu | `700:A:2;900:A:2`, shot 950 | equal outside y 56-103 |
| NewGame | `700:A:2;900:A:2;980:A:2`, shots 1100-1390 | identical (4 frames) |
| window, bypass | `warn-test` ROM, `700:A:2;900:A:2;980:A:2;1060:R:2`, shots 990-1110 every 10, 1040, 1100 | equal outside y 56-103 and x 8-151, y 112-135 (15 frames); window map at `0x9340` = ROM `0x28F7BF` |
| window, real | `--save` with suspend data (Suspend in stage 0), `700:A:2;900:A:2;960:L:2;1020:A:2;1120:R:2` | the window opens on NewGame; equal outside the band and the window interior (6 frames); maps and tiles = ROM |
| window: B, Continue | same save, `...;1020:A:2;1100:B:2;1160:R:2;1200:A:2;1280:A:2` | equal outside the band and the window interior (7 frames); the resumed game identical |
| window: Yes | same save, `...;1020:A:2;1080:R:2;1120:A:2` | the fade-out equal outside the band and window (4 frames); the new game's screens identical (8 frames) |

The suspend save comes from `H ogre_en.ngc --load-state
data-cmdbar_suspend.state --frames 600 --input "10:A:2;60:A:2" --save
suspend.sav` (Suspend on the stage 0 command bar, Yes; the flash log says 8960
bytes programmed in block 27). Use a copy per run: the game erases the suspend
data when it resumes. Scratch scripts (machine-local; they show the original
art): `r2-gfx2-title\v4\final.py` (all recipes, checks and the BPS audit),
`sheets.py` (comparison sheets), `edges.py` and `sides.py` (glow statistics by
row, ring and side), `fist.py` and `sprmask.py` (which sprites cover which
pixels), `proto.py` and `newdraft.py` (variants into a ROM with sheets).

Round-1 notes still valid: the monochrome notice is reached by changing the `jr C`
at `0x28C69A` to `jr T` in a scratch copy; idling on the title restarts the attract
loop after about a minute.

## Open issues

* Owner decisions (provisional choices in place): the kicker THE LEGEND OF (kept
  because the original's big title has it; `@kicker` empty removes it, the main
  title stays in place); GAIDEN (alternative SIDE STORY: `@logo OGRE
  BATTLE|SIDE STORY` does not fit in one line).
* Two opaque sprites still cover letter corners (the pole's tip over the I's
  top-left corner, 6 px; two dark fist pixels on BATTLE's E, 2 px), where the
  original's letters avoid them; the line has no room to move.
* The English line is 1 px further out on each side than the original (fill x
  5-155 against 6-154, glow x 2-157 against 3-156); the subtitle is wider (x
  22-137 against 37-124).
* The subtitle follows the original's treatment (thin italic amber strokes with a
  brown outline), not the Codex drafts' bold strokes with a drop shadow. A bolder
  subtitle would be a change of `assets/gfx/title/italic9.txt` only.
* Outside this target (`translation/en/ui.txt`, owner: orchestrator): the staff
  roll opens with the title in two 20-cell lines (`@2A36BC`, `@2A36D2`). The
  original's two lines are the romanized "legend of" and "Ogre Battle Gaiden", so
  `THE LEGEND OF` / `OGRE BATTLE GAIDEN` would match both the original and the
  logo (today: OGRE BATTLE GAIDEN / PRINCE OF ZENOBIA).
* Optional polish: the menu label "NewGame" has no space. The labels are
  pre-drawn English maps of 17x2 cells (tiles `0x0C0`-`0x0F3`) and could be
  redrawn as "New Game" with the same tools.

## Next steps

1. Verify step: enable the target in the full build together with the other
   graphics targets (`FULL_BUILD`), rerun the recipes on `build/ogre_en.ngc`.
2. Show the comparison sheets to the owner.
