# Contributing

Reports of untranslated or cut-off text, translation suggestions and code
changes are all welcome.

## Rules for every change

These apply to people and AI agents alike. The first one is what keeps the
project legal to share.

* Never commit data from the game. That means no ROM or part of one, no
  Japanese text from the game (also not in comments, notes or commit
  messages), no graphics taken from the game, no disassembly or code generated
  from the ROM, and no save states. Keep your game file in `rom/` and
  everything generated in `build/`. Both folders are git-ignored.
* Write your own translation. Do not copy from other fan translations.
* Replacement graphics must be original art. Each one should match the
  original graphic closely (position, size, colors, outline and shading) and
  change only the lettering. They are built from text files (fonts and pixel
  art in `assets/`, wording in `translation/en/`), never from images taken
  from the game.
* Write documentation and code comments in English.

The build enforces part of this. It refuses Japanese characters in the
`.txt` files under `translation/en/` and `assets/`, and it refuses a patch
whose literal data contains 8 or more bytes in a row from the original game.
The only Japanese characters in the repository are in the character table in
`tools/text/charmap.py`, which maps the game's byte codes to kana and
punctuation.

## Reporting a problem

Open an issue on GitHub. Include a screenshot, where in the game it happened
(stage, menu or event), and the version from the first lines of `README.txt`
in the download. For a text problem, also type out the English text you saw.
Please do not attach ROM files, patched ROMs or save states, since all of
them contain data from the game.

## Improving the translation

The English text is in `translation/en/`, and the agreed names and terms are
in `translation/en/glossary.md`. [docs/localization.md](docs/localization.md)
explains the files and the review workflow: you can export every string with
its Japanese original into a spreadsheet, and import a reviewer's
suggestions. After changing text, rebuild and look at the result in the
game. The build checks that every line fits its window or field, and when one
does not, it says which entry is too long. Wording choices that are still
open are listed in [STATUS.md](STATUS.md).

## Building

You need Windows with Visual Studio 2022 (its C++ build tools include CMake
and Ninja), Python 3, and your own copy of the game at `rom/baserom.ngc`
(SHA-1 `5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`).

```
build.bat                                     # build/zenobia.exe and build/ngp_harness.exe
python -m tools.patch.build rom/baserom.ngc   # build/ogre_en.ngc, ogre_en.bps and ogre_en.sha1
python -m tools.release.package --no-catalog  # the download package in dist/, without chapter saves
```

The chapter saves come from test states that only the maintainer has, so
leave them out with `--no-catalog` (docs/testing.md, "Chapter saves"). If you
change the player's guide (`tools/release/guide.html`), update the matching
row of [docs/guide-sources.md](docs/guide-sources.md), which records where
each fact in it was checked.

## Testing

Run at least these before you send a change. Each prints a summary and ends
with an error when something fails. `NEW_DIR` is a new, empty folder.

```
python -m tools.gfx.test_all rom/baserom.ngc
python -m tools.text.test_tables rom/baserom.ngc
python -m tools.patch.test_bps rom/baserom.ngc
python -m tools.release.test_webpatcher rom/baserom.ngc
python -m tools.release.test_package --work NEW_DIR
```

[docs/testing.md](docs/testing.md) covers the rest: the player and save
tests, the headless test harness, and how to reach particular screens in it.

## Sending changes

Keep each pull request to one topic and say how you tested it. Do not commit
anything from `build/`, `dist/` or `rom/`. If your change completes a
checklist item or settles an open decision in [STATUS.md](STATUS.md), update
that file and add an entry to [docs/history.md](docs/history.md).
