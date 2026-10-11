# Localization database and review workflow

Every piece of Japanese text the game shows is tracked next to its English
translation, so that the translation can be reviewed (for example by a
linguist) and updated later without hunting through files.

## Where the text lives

| What | English (committed) | Japanese (from your ROM, never committed) |
|---|---|---|
| Dialogue (1,570 messages) | `translation/en/script.txt` | script walker (`tools/text/extract.py`) |
| Menus, windows, system messages | `translation/en/ui.txt` | original string at each `@ADDR` |
| Names, items, classes, descriptions | `translation/en/tables/*.txt` (copy tables: short forms for narrow fields, see below) | packed tables in the ROM |
| Text drawn into graphics: menu labels, intro, chapter cards, title, tags | `translation/en/{labels,intro,cards,title,tags}.txt` | pre-drawn art: the wording as read from the pictures, in the local file `build/l10n/gfx_source.tsv` |
| Location names, town-type phrases | `translation/en/locations.txt` | stage location tables |
| Scan hits that are not text | `translation/en/not_text.txt` | |
| Review comments | `translation/en/review_notes.txt` (made by the first `import --apply` that carries a comment) | |

The files in `translation/en/` are the source of truth. The database is
generated from them and from your ROM; it is never edited by hand.

## Export

```
python -m tools.text.l10n export rom/baserom.ngc
```

This writes `build/l10n/l10n.sqlite` (table `strings`) and
`build/l10n/strings.csv` (UTF-8; opens in Excel, LibreOffice or Google
Sheets). Both contain the Japanese text from the ROM, so they stay in `build/`
(git-ignored). Share them only with people who own the game.

One row per string:

| Column | Meaning |
|---|---|
| `id` | stable key: `dlg:ADDR`, `ui:ADDR`, `ui:ADDR:inplace`, `sym:NAME`, `tbl:ADDR:N`, `tbl:ADDR:N:NAME` (entry N of copy table NAME), `loc:STAGE:N`, `loctype:N`, `gfx:FILE:KEY` (text drawn as a picture), `raw:ADDR`, `ram:ADDR` (text composed in RAM by the code at ADDR, found in the runtime text logs) |
| `category` | dialogue, ui, symbol, table:&lt;file&gt;, location, location-type, graphic:&lt;file&gt;, composed, unverified |
| `context` | where it appears: stage and speaker, renderer, table, town type... |
| `address` | ROM address of the original text |
| `japanese` | the original text (line breaks kept; `[NAME]`/`[NUM]` are filled in by the game) |
| `english` | the current translation (empty: not translated yet) |
| `displayed` | dialogue only: the English as it wraps on screen (`---` = next page) |
| `limits` | the space the English has to fit (pixels or characters, lines, tiles) |
| `status` | translated, untranslated, or unverified (looks like text, but where the game uses it is unknown) |
| `source` | file and line of the English text |
| `notes` | translator comments from the files and earlier review notes |
| `suggested_english`, `reviewer`, `reviewer_comment` | empty, for the reviewer |

The export also prints a summary by category and status. Rows with status
`untranslated` or `unverified` are the remaining work.

## Text drawn as pictures

Menu labels, the intro narration, the chapter title cards, the title logo with
its warning window, and two status tags are pre-drawn pictures in the
original. Their English lives in `translation/en/labels.txt`, `intro.txt`,
`cards.txt`, `title.txt` and `tags.txt`, and `tools/gfx` draws it into tiles at
build time. Each line is one database row (`gfx:labels:03`, `gfx:intro:13`,
`gfx:cards:story:12:head`, `gfx:title:window:1`, ...; `python -m
tools.text.gfxtext list` lists them). The pictures hold no text bytes, so the
export takes the Japanese wording and its meaning from an optional local file,
`build/l10n/gfx_source.tsv`. It holds Japanese, so it stays in `build/`. The
maintainer makes it from the graphics workstreams' reports:

    python -m tools.text.gfxtext source build/handoff/r1_graphics_result.json build/handoff/r2_gfx_wave1.json

Without that file, the `japanese` column of these rows is empty, and the
reviewer reads the original wording in the game itself.

A suggestion on a `gfx:` row replaces that one line; rebuild to redraw the
picture (the build checks the width). The title logo itself (`gfx:title:kicker`,
`logo`, `subtitle`) is hand-tuned art: its suggestions are listed but applied
by hand (`python -m tools.gfx.title draft`).

## Copy tables: short forms for narrow fields

Some screens print a table entry into a fixed field narrower than the English
(8-cell class and item fields, for example), while other screens show the same
entry in full. A table file can then declare a copy of the table for just
those screens:

    @table 2166B8 prefix=item maxlen=8 sites=2157F6,20D5CA,2E55A0   # Items list (map Items, organize Item), status pane ITEM field, link: versus item list and screens
    ...
    1	CurePotn

(from `translation/en/tables/items_short.txt`, a copy of the item table in
`items.txt`)

* `sites=` lists the code that reads the copy: the address of each instruction
  that loads the table address (its load site). `python -m tools.text.tables
  rom/baserom.ngc 2166B8` lists a table's load sites and the table each one
  reads now. Every other load site keeps reading the main table (the
  `@table 2166B8` line without `sites=`).
* The copy starts from the main table's English and replaces only the entries
  it lists. Its own options (`maxlen`, `vwf`, `wrap`, `width`, `lines`,
  `tiles`) are checked on every resulting text, including the ones it
  inherits, so the build stops at the first main-table entry that is too long
  for the copy and names it. `prefix=` always comes from the main table (a
  copy may repeat it, but not change it).
* `name=WORD` names the copy in the database ids (default: the file name
  without `.txt`). The comment after `#` on the `@table` line should name the
  fields; the database shows it in `context`.

In the database every entry of a copy table has its own row: id
`tbl:ADDR:N:NAME`, category `table:<file>`, `context` = the fields and the load
sites, `notes` = the main table's English. Rows for entries the copy does not
list show the main table's text (`source` is the copy's file without a line
number). A suggestion on a copy row is written into the copy table (as a new
entry if it had none); it never changes the main table. Rows of the main table
say which load sites read the copy instead.

## Review

Give `strings.csv` to the reviewer. They fill in, per row:

* `suggested_english`: a better translation (leave empty to keep the current one);
* `reviewer_comment`: anything worth noting, such as nuance, tone, terminology
  or questions;
* `reviewer`: their name or initials.

Keep `{XX}` codes (raw bytes such as `{00}` = new line), `[NAME]`, `[NUM]`
and leading spaces as they are; if you change one, say why in
`reviewer_comment`. The `limits` column says how long a line may be. Write
comments in English and do not paste Japanese text into them, because the
repository must stay free of text from the game.

## Import

```
python -m tools.text.l10n import review.csv              # dry run: shows every change
python -m tools.text.l10n import review.csv --apply      # writes translation/en/
python -m tools.patch.build rom/baserom.ngc               # checks that everything fits
```

Suggestions replace the English text of existing entries: dialogue, UI
strings, named strings (`sym:` rows), table entries, location names,
town-type phrases and the lines of text drawn as pictures (`gfx:` rows).
Missing table and location entries are added. A suggestion on a copy-table
row (`tbl:ADDR:N:NAME`) goes into that copy table, never into the main table.

The import lists the suggestions it cannot apply as NOT APPLIED: strings that
have no English entry yet (such as `ui:` rows with status untranslated, which
each need a decision on how they are drawn), `raw:` and `ram:` rows, and the
title logo rows. Add or change those by hand. Comments are appended to
`translation/en/review_notes.txt` (`id<TAB>date<TAB>reviewer<TAB>comment`)
and appear in the `notes` column of later exports.

If the build reports that a string no longer fits, shorten it (the error
names the entry) and build again.
