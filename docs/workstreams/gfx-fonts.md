# Graphics: display fonts

## Goal

Deliver the shared 11-row display font `assets/font/title16.txt`: white
lettering with an outline, like the original card and narration lettering. It
is used by the chapter title cards, the intro narration and the title
subtitle. The font is an original design of this project. It ports the
round-1 chapter-cards prototype and adds the missing punctuation and symbols.

The dialogue font `assets/font/vwf8.txt` (8 rows, CC0) is unchanged. The logo
font `logo19.txt` belongs to the `gfx-title` task.

## State

Done (2026-10-09, round 2, task `gfx-font16`). `assets/font/title16.txt` has
85 glyphs, the same character set as `vwf8.txt`. Every acceptance check
passed:

* Every glyph has 11 rows of equal width. Three parsers read the file and
  agree on every glyph:
  * `tools/gfx/font.py` (`load_font`);
  * a copy of the parsing rules of `tools/text/fontc.py`, set to 11 rows
    (`fontc` itself only reads 8-row fonts);
  * a strict scratch checker.
* The 15 draft intro lines measure at most 143 px (limit 144). All card lines
  measure at most 117 px (limit 158). PRINCE OF ZENOBIA measures 107 px
  (limit 140). The scratch checker and `tools/gfx/textart.py` agree on every
  width.
* Preview sheets and sample lines were reviewed on the card palette and on
  the intro palette, against harness backgrounds.
* The intro crawl, rebuilt in place with this font in a scratch ROM, is
  legible in the harness. Every line stays inside its 144-px box.

## Done

### The font file

* Path: `assets/font/title16.txt`. It is UTF-8, pure ASCII, with LF line
  endings, in the `vwf8.txt` syntax.
* The header states the origin: an original design for this project. The
  letters and digits come from the round-1 cards prototype; the punctuation
  and symbols were added in round 2. Nothing is traced or copied from the
  game's art or from another font.
* Licence: MIT (the project licence). The owner may also dedicate the font to
  CC0, like `vwf8.txt`.
* The glyphs are grouped in sections (capitals, lower case, digits,
  punctuation), each introduced by a comment line.

### Metrics

| Item | Rows | Notes |
|---|---|---|
| Glyph height | 0-10 (11 rows) | every glyph |
| Capitals and digits | 0-8 | cap height 9 px, baseline = row 8; the tail of Q stays inside row 8 |
| x-height | 3-8 | a c e m n o r s u v w x z (6 px) |
| Ascenders | from row 0 | b d f h k l; t starts at row 1; the dots of i and j are on row 1 |
| Descenders | 9-10 | g j p q y |
| Stroke | 1 px | the renderer adds the 1-px outline |
| Outlined line | 13 px | inside a 16-px band |

Placement in the targets (from the round-1 prototypes):

* Cards put glyph row 0 on band row 2: outline rows 1-13 of each 16-px band.
* The intro puts glyph row 0 on row 3 of its 144 x 16 line: outline rows
  2-14.
* The title subtitle has its capitals at y 91-99.

### Character set (85 glyphs, the `vwf8.txt` set)

* Letters `A`-`Z`, `a`-`z`, digits `0`-`9`.
* `SPACE` is 3 px blank with advance 4, so the gap between words is 5 px
  against 1 px between letters.
* Punctuation: `. , ! ? ' " : ; - ( ) / &`, `ELLIPSIS` (the ellipsis
  character) and `LQUOTE` (the opening double quote).
* Symbols: `% + = * ~ [ ]`.

Text characters map to glyph names through `tools/gfx/font.py`:

| Character | Glyph |
|---|---|
| space | `SPACE` |
| ellipsis (U+2026) | `ELLIPSIS` |
| opening double quote (U+201C) | `LQUOTE` |
| closing double quote (U+201D) and plain `"` | `"` |
| left and right single quotes (U+2018, U+2019) and plain `'` | `'` |

Widths (the advance is width + 1 for every glyph except `SPACE`):

| Width | Glyphs |
|---|---|
| 1 | `i . ! ' :` |
| 2 | `j l , ;` |
| 3 | `I 1 " ( ) [ ]`, `LQUOTE` (and the blank `SPACE`, advance 4) |
| 4 | `f r t -` |
| 5 | `E F J L`, `a b c d e g h k n o p q s u v x y z`, `0 2 3 5 6 7 8 9`, `? / + = *` |
| 6 | `A B C D G H K O P Q R S U X Z`, `4 & ~` |
| 7 | `M N T V W Y`, `m w`, `% ELLIPSIS` |

### Design notes

* **Letters (ported unchanged from the prototype).** The style is a 1-px
  sans with chamfered round corners.
  * `I` has serifs, and `J` has a top bar.
  * `1` has a flag and a base, so `I`, `l` and `1` stay distinct.
  * `l` has a small foot to the right.
  * `a` is double-storey and `g` single-storey.
  * The review found no letter or digit that reads poorly with either
    outline, so none was changed.
* **Dots.** `.` and the dots of `: ; ! ?` are single pixels.
  * The colon's dots sit on rows 3 and 8: the x-height top and the baseline.
  * `!` and `?` have a 1-row gap above the baseline dot.
  * The tails of `,` and `;` go down and to the left, into row 9.
* **Quotes.**
  * `'` is one 2-px tick in rows 0-1. It serves as the apostrophe and as
    both single quotes.
  * `LQUOTE` and `"` are two straight ticks in rows 0-1, so the opening and
    closing quotes look the same. A slanted pair needs a 2-px gap, because
    the ticks would otherwise touch diagonally; that makes the glyph 5 px
    wide and does not read better.
* **Ellipsis.** Three dots on the baseline, 2 px apart (`#..#..#`, 7 px).
  The gaps stay visible after outlining: two outline pixels separate each
  dot. Three typed periods (`...`) give `#.#.#` (5 px). The ellipsis lines of
  the intro have a lot of room.
* **Hyphen and maths.** The hyphen is 4 px on row 5. `+` and `=` are centred
  on row 5, and `~` sits on rows 4-5.
* **Brackets and slash.** `( ) [ ]` span all 11 rows. `/` is a regular
  2-rows-per-column staircase over rows 0-9.
* **`&` and `%`.**
  * `&` has the classic loop-and-tail shape. It was chosen over two other
    drafts in a zoom comparison.
  * `%` uses two 3x3 square rings and a long diagonal. It replaced a first
    version with diamond rings, which looked cluttered after outlining.

### Widths of the target texts

Widths include the 1-px outline on both sides: the ink bounding box + 2.
Every text below starts with a glyph whose ink touches its left edge, so the
pen measure of the prototypes (rightmost ink + 2) gives the same numbers.
Texts: the draft intro lines (scratch `gfx-intro\narr_en_v3.txt`) and the
card proposal (scratch `gfx-chapter-cards\cards_en.txt`). The final wording
lives in `translation/en/intro.txt` and `cards.txt` once the target tasks
land; re-measure then.

Intro (limit 144 px):

| n | Line | px |
|---|---|---|
| 0 | To take all the suffering | 130 |
| 1 | of the people upon oneself, | 143 |
| 2 | and to bear one's own | 115 |
| 3 | suffering alone… | 87 |
| 4 | Whoever can do this | 105 |
| 5 | is truly a “true king”… | 114 |
| 6 | But… | 27 |
| 7 | can such a way of life | 116 |
| 8 | be called happiness? | 107 |
| 9 | And to force such a life | 125 |
| 10 | upon others… | 71 |
| 11 | is that truly right? | 98 |
| 12 | Imperial Year 15. Our story | 140 |
| 13 | begins in Estoa, a village | 127 |
| 14 | on a small peninsula… | 112 |

Cards (limit 158 px per line):

| Card | Heading | px | Title line(s) | px |
|---|---|---|---|---|
| story 1 | Chapter 1 | 50 | Quickening | 54 |
| story 2 | Chapter 2 | 52 | Those Who Hunger | 97 |
| story 3 | Chapter 3 | 52 | Those Who Believe... | 103 |
| story 4 | Chapter 4 | 53 | The Northern Kingdom | 117 |
| story 5 | Chapter 5 | 52 | The Dead | 50 |
| story 6 | Chapter 6 | 52 | The Sorcerer | 71 |
| story 7 | Chapter 7 | 52 | A Voice That Asks | 98 |
| story 8 | Chapter 8 | 52 | What Desire Brings | 98 |
| story 9 | Chapter 9 | 52 | Resolve | 41 |
| story 10 | Chapter 10 | 56 | The Dark Knight | 85 |
| story 11 | Chapter 11 | 54 | Tears | 32 |
| story 12 | Chapter 12 | 56 | Darkness and Silence, / and Then... | 114 / 55 |
| story 13 | Final Chapter | 69 | White Night | 59 |
| story 14 | | | Deep in the Mountains | 114 |
| story 15 | | | Treasure | 49 |
| story 16 | | | Of Blood and Flesh | 98 |
| story 17 | | | Samurai | 41 |
| story 18 (also 19, 20) | | | Free Battle Area | 88 |
| area 1 | | | Estrada's Manor | 84 |
| area 2 | | | Gross Region | 68 |
| area 3 | | | Satsu Peninsula | 83 |
| area 4 | | | Lichtfloss | 52 |
| area 5 | | | Roden Region | 69 |
| area 6 | | | Litt Island Waters | 94 |
| area 7 | | | Nessa Region | 70 |
| area 8 | | | Norodom Region | 83 |
| area 9 | | | Megaholten | 59 |
| area 10 | | | Shagall Marsh | 73 |
| area 11 | | | Lego Islands | 66 |
| area 12 | | | Am Sea of Trees | 89 |
| area 13 | | | Laika Lakeside | 75 |
| area 14 | | | Krono Mountains | 86 |
| area 15 | | | Ein Peninsula | 67 |
| area 16 | | | Wind Dunes | 58 |
| area 17 | | | Freia Isles | 55 |
| area 18 (also 19, 20) | | | Free Battle Area | 88 |

Title words:

| Text | px | Limit |
|---|---|---|
| PRINCE OF ZENOBIA | 107 | 140 |
| Prince of Zenobia | 91 | |
| THE LEGEND OF | 83 | |
| OGRE BATTLE GAIDEN | 117 | |

Compared with the round-1 width test (scratch `gfx-pipeline\title16_draft.txt`),
ten intro lines measure the same, including the widest (143 px). The five
lines that end in an ellipsis are 2 px wider, because the ellipsis now has
2-px gaps (7 px instead of 5). They remain far below the limit.

### Review

The previews are machine-local, under the scratch folder `r2-gfx-font16\`.
Previews of the original screens stay there; they are never committed.

* **Glyph sheets** (`final\`):
  * `sheet_raw.png` shows the bare glyphs with the metric bands;
  * `sheet_card4.png`, `sheet_card8.png` and `sheet_card8s.png` use the card
    palette: white ink and a dark-blue outline. The `8s` sheet draws the
    diagonal-only outline pixels in light blue;
  * `sheet_intro8.png` uses the intro palette: white with a blue outline.
* **Sample lines** (`final\`):
  * `intro_mock.png`: the 15 lines in their boxes over the cloud background;
  * `cards_mock_4.png`, `cards_mock_8.png` and `cards_mock_8s.png`: the 36
    distinct cards over the emblem;
  * `subtitle_mock.png`: the subtitle;
  * `pangrams.png`: pangram lines;
  * the `v1\` and `v2\` zoom images: the punctuation, the letters at 10x,
    and the `&` and `%` variants.
* **Harness run.** `in16_final\` holds the four frames of acceptance item 4.
  `in16_vram\` holds the VRAM dumps and a contact sheet of the whole crawl,
  one frame every 300.

Findings:

* The letters read well in all three outline styles over the emblem and
  over bright clouds.
* `%` was redrawn after the review.
* The ellipsis spacing was settled at 2 px.

## How to test / reproduce

Load the font with the shared library (repository root):

    python -c "from tools.gfx.font import load_font; f = load_font('assets/font/title16.txt'); print(f, f.height)"

Expected: `<Font title16: 85 glyphs, 11 rows> 11`.

Measure a text with the shared renderer. The width includes the outline, so
this line gives 143:

    python -c "from tools.gfx.font import load_font; from tools.gfx.textart import Style, measure; f = load_font('assets/font/title16.txt'); print(measure(f, 'of the people upon oneself,', Style(ink=1, outline=3, outline8=True)))"

Cross-checks, run when `tools/gfx/textart.py` had just landed:

* `textart.measure` gives the widths of the tables above for the 64 intro and
  card lines and for the subtitle, with both outline modes. There are no
  differences from the scratch checker.
* `render_box` places every text in its real box without a `FitError`:
  * the intro in 144 x 16 with `top=3`;
  * the cards in 160 x 16 with `top=2`;
  * the subtitle in 140 px.
* The 15 intro bitmaps from `render_box` (8-neighbour outline, centred) are
  byte-identical to those of the scratch ROM used in the harness check.

`tools/gfx/font.py` has no command line, so `python -m tools.gfx.font` does
not measure anything.

Scratch tools (machine-local, `r2-gfx-font16\` in the session scratchpad):

    python t16.py check   FONT          # 11 rows, equal widths, names, required set, metrics per glyph
    python t16.py measure FONT          # intro / card / title widths against the limits (exit 1 on failure)
    python t16.py sheet   FONT OUTDIR   # glyph sheets: raw with metric bands, card and intro palettes
    python t16.py samples FONT OUTDIR   # intro, card and subtitle mock-ups on harness backgrounds
    python t16.py zoom    FONT OUT.png [--8|--8s] TEXT ...   # 10x zoom with a pixel grid
    python intro16.py FONT IN.ngc OUT.ngc                     # intro lines in place (8-neighbour outline)

Here `FONT` is `assets/font/title16.txt`. The backgrounds come from harness
frames: `stage0_selected` at frame 90 shows the emblem before the card text
appears, and power-on frame 300 shows the clouds before the first line.

Intro check (acceptance item 4):

    python intro16.py <repo>\assets\font\title16.txt <scratch>\snap\ogre_en.ngc intro16.ngc
    <scratch>\snap\ngp_harness.exe intro16.ngc --frames 6500 --shot 1200,2400,3600,4800

Results:

* All 15 lines are legible, and the widest line (143 px) sits inside the box.
* The VRAM check (`gfx-pipeline\introcheck.py` on `--vram
  1200,2400,3600,4800` dumps) finds the expected slots: `0 1 2 3 -`,
  `5 6 2 3 4`, `10 11 7 8 9` and `10 11 12 13 14`.
* The crawl ends on the title screen (frame 6450).

### How to add a glyph

1. **Pick the name.**
   * Use the character itself, or one of the word names (`SPACE`,
     `ELLIPSIS`, `LQUOTE`).
   * A new word name also needs an entry in `ALIASES` in
     `tools/gfx/font.py` (owned by `gfx-lib`).
   * Keep the set equal to `vwf8.txt`: a character that graphics text may
     use belongs in both fonts.
2. **Draw it** in the right section of `assets/font/title16.txt`:
   * write `@NAME`, then exactly 11 rows of `#` and `.`, all the same width;
   * keep to the metrics above: capitals rows 0-8, x-height rows 3-8,
     descenders rows 9-10;
   * use 1-px strokes;
   * leave no blank column at the left or right edge, because the advance
     adds the 1-px gap;
   * give `advance=N` only for spacing glyphs;
   * draw it yourself: never trace the game's art or another font.
3. **Comments** start with `# `. A comment line must never consist of `#`
   and `.` only: the parsers would read it as a glyph row.
4. **Check the file.**
   * `load_font` must load it, and `t16.py check` must pass.
   * Run `t16.py measure`, or `textart.measure`, on every text that uses the
     glyph.
   * Look at the glyph in a zoom (`t16.py zoom`) in the 4- and 8-neighbour
     styles, next to its usual neighbours. The outlines of neighbouring
     glyphs merge, so 1-px counters and gaps turn into outline colour.
5. **Rebuild** the affected targets and review their previews.

## Open issues

* **Intro margin.** The widest draft line is 143 of 144 px, and the 1-px
  margin comes from the prototype letters. A rewording may need room. The
  options, none applied because each costs legibility and the text fits:
  * a 3-px `f` saves 1 px per f (2 px on that line);
  * an `l` without its foot saves 1 px per l;
  * a `SPACE` advance of 3 saves 1 px per space (word gap 4 px);
  * the intro's relocated mode allows a re-split.
* **Outline style per target.** The font is drawn for any of three styles:
  * 4-neighbour outline, like the original card art;
  * 8-neighbour outline: bolder, and the better choice for the intro over
    bright clouds (the scratch `intro16.py` uses it);
  * 8-neighbour with the diagonal-only pixels in colour 2 (light blue on the
    card palette): a softer edge.

  The choice is a style constant of `gfx-cards`, `gfx-intro` and
  `gfx-title`. The previews of all three are in the scratch folder.
* **Quotes.** The opening and closing double quotes look the same.
* **No kerning.** Wide capitals such as `T`, `V`, `W` and `Y` leave a
  visible gap before lower case, as in "To". This is acceptable for display
  type.

## Next steps

* `gfx-intro`, `gfx-cards` and `gfx-title` load `assets/font/title16.txt`
  through `tools.gfx.font.load_font`. Their `fit` commands re-check the final
  texts against the limits above with `textart.measure`.
* `gfx-lib` may add a library test: `title16` loads with height 11 and has
  the `vwf8` character set.
* Owner: decide whether to dedicate `title16.txt` to CC0, like `vwf8.txt`.
  If so, update its header, `README.md` and `THIRD_PARTY_NOTICES.md`.
