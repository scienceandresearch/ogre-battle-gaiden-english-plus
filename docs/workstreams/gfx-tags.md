# Graphics: small status tags ("deployed" tag, paralysis label)

## Goal

Replace the two small pre-drawn Japanese tags that the graphics survey found
(`gfx-survey.md`, targets 1 and 2) with English that looks like the original
art, changing only the lettering:

* the "deployed" tag on the organize status pane of a unit that is deployed
  on the stage map (seen in every stage);
* the paralysis label that a battle shows over each combatant hit by a
  paralyzing attack.

Both are replaced in place: no hooks, no new ROM, no palette writes. Round 2
wave 2, task `gfx2-tags`.

## State

Done (2026-10-10, round 2 wave 2, after review fix round 1). The target
`tags` of the graphics build (`tools/gfx/tags.py`, sources
`translation/en/tags.txt` and `assets/gfx/tags/caps6.txt`) writes
FIELDED (both copies of the deployed tag) and STUN in place.
`FULL_BUILD = False` until the verify step enables all targets together;
`python -m tools.gfx.apply IN OUT --target tags` runs it.

Fix round 1 (review of 2026-10-09): the first build wrote DEPLOYED, 30 px of
ink, which covered the blue margins that the original keeps on both sides
of its lettering. The English lettering now stays inside the original
lettering's area (ink at strip x 8-31, last shadow at x 32), the build
refuses wider words, and the build-time check also covers the margins.

* `python -m tools.gfx.test_tags rom/baserom.ngc`: 16 tests pass (13 without
  the ROM, on a synthetic image); `test_build` still passes.
* Harness, on a test ROM made from the English snapshot (`snap3`): in every
  frame that shows a tag, VRAM holds the built tiles and the sprites form the
  whole tag. Deployed: 49 frames over three recipes, and in each of them
  `harness diff ref.png t.png 16 55 40 60` (the original lettering's box)
  gives 0; the whole-screen difference is 88 pixels inside it. Paralysis: 54
  frames over five battles, no difference outside the label rectangles.
  Palettes are identical everywhere; only the tag tiles differ in VRAM.
* Sweep: all 222 saved states, 120 frames each, idle and with two kinds of A
  presses (shots at frames 30, 60, 90 and 119), on the snapshot and on the
  final test ROM: 2,664 screenshot pairs, none differs. Nothing else on
  screen uses the changed tiles.
* All five targets present today (labels, intro, cards, title, tags) apply
  together on one snapshot copy without a clash.
* Side-by-side sheets (original against English, 1x and 3x) of every
  instance, the wording candidates, and the written ranges were reviewed
  (machine-local, see "Review").

## Done

### The originals (described; no ROM data here)

**Deployed tag.** 5 sprite tiles, 40 x 8 px, 80 bytes at `0x214A00` (tiles
`0x5B`-`0x5F` of the organize sheet `0x214450`; VRAM tiles `0x13B`-`0x13F`),
and an identical copy at `0x2E736A` (the link-battle copy of the sheet,
`0x2E6DBA`). Shown as sprites at x 8-47, y 54 of the status pane, sprite
palette 8 (color 1 white, color 2 blue, color 3 near black). The art:

* columns 0-3 and 36-39 transparent;
* a box at x 4-35, rows 0-7: a 1-px border in color 3, a fill in color 2
  (the same blue as the pane, so the box reads as a dark frame);
* four glyphs in color 1 with 1-px strokes, on rows 1-6 (the whole interior
  height), ink at x 8-31;
* every ink pixel has a 1-px shadow on its right in color 3 (checked:
  every dark interior pixel is right of an ink pixel and nothing else);
  there is no shadow below or to the left; the last shadow is at x 32;
* so the lettering's area is x 8-32, rows 1-6, and the blue fill shows on
  both sides of it: 3 columns at x 5-7 and 2 at x 33-34.

**Paralysis label.** 2 sprite tiles, 16 x 8 px, 32 bytes at `0x2FE5ED`, VRAM
tiles `0x2D`-`0x2E`, sprite palette 15 (palette data `0x2FE325`: color 1
light gray, color 2 orange, color 3 near black). The art uses colors 1
and 3 only: two glyphs and an exclamation mark in color 1, mostly 2-px
strokes, ink on rows 1-6 and x 1-14 (41 pixels), with a 1-px outline over the
8 neighbors in color 3 (two more outline pixels at the bottom right),
transparent background.

### Wording

Each tag was drawn with several English candidates in the final font and
style, composited into real harness VRAM dumps, and compared side by side
with the original at 1x, 3x and 6x (`fix1\candidates_deployed.png`; the
paralysis candidates in `final\tags_wording_candidates.png`).

Deployed tag: the word must fit the original lettering's area, 24 px of ink
(x 8-31). Interior balance is ink / blue / dark pixels of the 30 x 6
interior; the original's is 61 / 77 / 42, with blue margins of 3 and 2 px.

| Candidate | Ink | Balance | Notes |
|---|---|---|---|
| **FIELDED** | 24 px, x 8-31 | 68 / 62 / 50 | chosen: exactly the original lettering's area and margins (3 and 2 px); every letter unambiguous; the tutorial's "send a waiting unit into the field" (the unit is in the field) |
| ON MAP | 23 px, x 8-30 | 59 / 69 / 52 | fits, but the 3-px arch N reads as "On" or a Greek pi at 1x and 3x |
| IN FIELD | 24 px, x 8-31 | 63 / 66 / 51 | fits; same N problem, and two words in 24 px look crowded |
| AFIELD | 20 px, x 10-29 | 57 / 79 / 44 | fits with wider margins; a rare word |
| SORTIE | 21 px, x 9-29 | 55 / 81 / 44 | fits; a term the game uses nowhere else |
| DEPLOY | 22 px, x 9-30 | 58 / 74 / 48 | fits; a verb (a command), not a state |
| OUT | 11 px | 31 / 122 / 27 | fits; too vague, and leaves the box mostly empty |
| DEPLOYED | 30 px, x 5-34 | 81 / 39 / 60 | the glossary's "deploy", but 6 px wider than the original lettering: it covers both blue margins (first build; rejected in review) |
| Deployed (unboxed, `vwf8`) | 37 px | | the survey's first proposal; drops the box; rejected |

Paralysis label (16 px):

| Candidate | Ink | Notes |
|---|---|---|
| **STUN** | 15 px | chosen: the usual short word for the status ("paralysis" does not fit), and one the game's attack list already uses (Stun Cloud; whether that attack is what paralyses is not confirmed in play); capitals like the game's own English battle labels (MISS, WAKE, DEF UP!) |
| ZAP! | 13 px | reads as an electric hit |
| HALT | 14 px | not paralysis |
| bolt and "!" pictogram | | matches the stroke weight, but reads as lightning damage (the game has Lightning and Thunder Flare) |

No 4-letter word fits with 2-px strokes, and the survey's "four 3-px
capitals with outline columns" needs 17 px, not 16 (see the style below).

The wording is one line each in `translation/en/tags.txt`; any capitals up
to 24 px (deployed) or 16 px (paralysis) of ink fit (`fit` reports widths).
The game's text says "deploy" (glossary `haken`), the help text calls the
status "paralysis"; the tags use FIELDED and STUN because those fit.

### Font `assets/gfx/tags/caps6.txt`

Compact capitals, our own design (MIT; the owner may dedicate it to CC0 like
`vwf8.txt`), in the `vwf8.txt` syntax, loaded with `tools.gfx.font`:

* 6 rows (the original glyphs' height on both tags), 1-px strokes, no
  descenders; 31 glyphs: A-Z, `! ? - .` and `SPACE` (1 px, advance 2, so
  the word gap is 3 px against 1 px between letters);
* widths: most letters 3 px, I 1 px, L 2 px (so that FIELDED is exactly
  24 px, the deployed tag's lettering width), M and W 5 px;
* N is an arch (top row `##.`): a 3-px N with its diagonal in the middle
  column looks like a 3-px M ("ON MAP" read as "OM MAP", "STUN" as "STUM");
  a 4-px N reads best but would make STUN 16 px and cut both outline columns
  of the paralysis label;
* the advance is width + 1: the gap column takes the deployed tag's right
  shadow, or the outline between two letters of the paralysis label.

It lives in `assets/gfx/tags/` because it serves only this target; it can
move to `assets/font/` if another target needs it.

### Style (constants in `tools/gfx/tags.py`)

* **Deployed:** the box is generated (border color 3, fill color 2, x 4-35,
  rows 0-7; transparent outside). The word's ink (color 1) goes on rows 1-6
  inside the original lettering's area, ink at x 8-31 (`LETTER_X0`,
  `LETTER_X1`; at most 24 px, `FitError` above), centered there with
  `x = 8 + (24 - width) // 2`; then each ink pixel whose right neighbor is
  not ink gets color 3 there, so the last shadow is at x 32 at most
  (`SHADOW_X`). The blue columns x 5-7 and 33-34 stay as in the original.
  FIELDED (24 px) lands exactly where the original's lettering is.
* **Paralysis:** `textart.render` with `Style(ink=1, outline=3,
  outline8=True)`; glyph row 0 on row 1 (rings on rows 0 and 7); the ink is
  centered in 16 px with left bias, `x = (16 - width) // 2`; rings outside the
  16 px are cut. STUN (15 px) starts at x 0, so the outline column left of
  the S is cut: 2 ink pixels of the S (its left edge) touch the background;
  everything else is outlined as in the original.
* **Build-time check:** `build(ctx)` decodes the ROM's tag at both addresses
  and refuses to build unless every pixel outside the lettering area (x 8-32,
  rows 1-6) equals ours: the box, the blue margins x 5-7 and 33-34 and the
  transparent columns. So only the lettering can change, and the build fails
  on a wrong address or box constant.
* Writes: `0x214A00` (80 bytes), `0x2E736A` (the same 80 bytes), `0x2FE5ED`
  (32 bytes); 97 bytes differ from the original. Ranges are declared in
  `Result.allow`; no asm, no sub-region (`TARGETS['tags'] = None`).

### Files

| File | Content |
|---|---|
| `translation/en/tags.txt` | `@deployed FIELDED`, `@paralysis STUN` (`keep` keeps the original art) |
| `assets/gfx/tags/caps6.txt` | the 6-row capitals |
| `tools/gfx/tags.py` | the target: `build(ctx)`, rendering, the frame check, `fit` / `preview` / `decode` / `check` |
| `tools/gfx/test_tags.py` | 13 tests, plus 3 with the ROM |
| `tools/gfx/build.py` | one registry line: `'tags': None` |

## How to test / reproduce

Shorthand: `S` = the session scratchpad, `H` = `S\snap3\ngp_harness.exe`,
`ST` = `S\snap3\states`, `t.ngc` = a test ROM.

    python -m tools.gfx.tags fit                         # widths: FIELDED 24 of 24, STUN 15 of 16
    python -m tools.gfx.tags preview OUTDIR              # our tags, 1x and 8x
    python -m tools.gfx.tags decode rom/baserom.ngc DIR  # the originals as PNG (local only)
    python -m tools.gfx.test_tags rom/baserom.ngc        # 16 tests
    python -m tools.gfx.apply S\snap3\ogre_en.ngc t.ngc --target tags   # a fresh copy each time
    python -m tools.gfx.tags check t.ngc DUMPDIR ...     # ROM and VRAM hold the built tags

`check` prints, per dump, which tag is shown, whether VRAM holds the built
tiles, and the sprite rows; it fails on the unmodified snapshot. The game
wipes the paralysis label's tiles after about 40 frames; `check` reports
that as "blank or partly wiped" and accepts it for that label only.

Harness recipes (set `NGP_HARNESS=H` for `tools.gfx.harness`):

| Tag | State and input | Frames |
|---|---|---|
| deployed, stage 0 unit 1 | `ST\command_bar_forecast.state`, `10:L:2;40:L:2;70:L:2;110:A:2;200:A:2;260:A:2`, 400 frames | tag from 270 (sprites 13-17) |
| deployed, two units | `ST\organize-test-s0-2deployed.state`, `10:D:10;40:A:2;90:R:2;130:A:2;230:A:2;290:A:2;370:R:2`, 460 frames | unit 1 at 300-370 (sprites 13-17), unit 2 from 380 (sprites 9-13) |
| deployed, stage 3 | `ST\progress-stage3_estrada_deployed.state`, `10:R:16;40:A:2;80:R:2;110:R:2;150:A:2;240:A:2;300:A:2`, 480 frames | tag from 310 (sprites 21-25); R moves the map cursor off the unit, A opens the command bar on NEXT, two R reach the organize icon, then A three times |
| paralysis | `python -m tools.gfx.harness poke ST\battle-inbattle_cmdbar.state st.state 412E=0194BE2C 4166=0194BE2C 419E=0194BE2C 4246=0194BE2C 427E=0194BE2C 42B6=0194BE2C`, then `10:B:2`, 120 frames | labels on screen at 20-60 above five combatants (sprites 0-9); VRAM `0xA2D0` holds them at 20-55, is partly wiped in the dump of frame 60, and the screen shows nothing from 61 (the sprites stay until 65) |
| paralysis, more battles | the same poke and input on `battle-boss_battle_start`, `battle-neutral_battle_start`, `progress-stage2_kazuma_battle`, `progress-balzac_battle_start`, 80 frames | labels at 20-65 (4 to 6 on screen; the neutral and Kazuma battles show one over light terrain at x 36, y 20) |

Acceptance on each frame with a tag: `harness diff ref.png t.png 16 55 40
60` (deployed tag at sprite x 8, y 54: the original lettering's box, strip x
8-32, rows 1-6) or with the label rectangles (from the dump's sprites) gives
0. The deployed tag's whole-screen difference is 88 pixels in x 17-40, y
55-60; the paralysis labels' about 45 pixels per label.

### Review (machine-local, under `S\r2-gfx2-tags\fix1\`)

* `review.py TEST.ngc OUTDIR` runs the eight recipes above on the snapshot
  and the test ROM (every 5 or 10 frames), checks the dumps, diffs outside
  the original lettering areas, palettes and VRAM tiles, and writes
  `sheet_<recipe>.png` (every frame with a tag, original against English,
  1x and 3x) and whole-screen sheets. Latest run: `rev\` (`problems: 0`).
* `final_sheet.py rev tags_review.png`: every distinct instance in one sheet.
* `cands.py candidates_deployed.png`: the deployed wording candidates with
  their measurements.
* `static_sheet.py TEST.ngc tags_static.png`: the three written ranges (both
  deployed copies, including the link-battle one, and the label) in the
  game's palettes, original against English, with the lettering area marked.
* `sweep.py TEST.ngc OUTDIR`: the all-states sweep (about 12 minutes).
* The first round's studies (box words, N shapes, pictogram) are in
  `S\r2-gfx2-tags\` (`cand.py`, `cand2.py`, `nvar.py`, `nvar2.py`).

## Open issues

* **Paralysis stroke weight.** The original's verticals are mostly 2 px
  wide; four English letters in 16 px only allow 1-px strokes. The ink count
  is the same (41 pixels) and the outline is a full ring (85 dark pixels
  against 74), so the label weighs the same at 1x and 2x, but STUN looks
  lighter at 3x and above. Accepted as inherent.
* **STUN's outline is open at the S's left edge** (2 pixels): STUN needs 17
  px with a full outline. It shows over light terrain (the labels at x 36,
  y 20 in the neutral and Kazuma battles). Only 14-px words (HALT, ZAP!)
  close the outline, and they read worse, so the gap stays.
* **Wording.** FIELDED fits the original lettering exactly but is not the
  game's "deploy"; ON MAP (23 px) is the other candidate that keeps the
  margins. The owner may pick either (one line in `tags.txt`).
* **Link-battle copy** (`0x2E736A`): the link screens need a partner, so only
  the static check covers it (both copies hold the same built bytes; `check`
  verifies the ROM; the build-time frame check covers both addresses).
* **Natural paralysis trigger** not seen yet (the survey's open issue); the
  poke recipe shows the label meanwhile.

## Next steps

* `gfx-verify`: drop `FULL_BUILD = False` with the other targets and run the
  recipes above on the full build.
* Owner: confirm FIELDED (or ON MAP) and STUN.
* Glossary: the status term (paralysis; battle label STUN) and the tag's
  FIELDED next to "deploy".
* Localization export (`tools/text/l10n.py`): include `translation/en/tags.txt`
  with the other graphics text files.
