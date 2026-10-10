# Workstream: release package

## Goal

A download that a player can use: one zip with the Windows player, the
English patch and the documents, built and checked by one command from what
the build folder holds. The player carries a version and an icon. Nothing in
the zip may contain data from the game.

## State

Current package (2026-10-10, complete build: every text and every pre-drawn
graphic in English; with the web patcher and the reworded READMEs):
`dist\ogre-battle-gaiden-en-0.1.0-dev+4fe9c5ff-win64.zip`, 457,519 bytes,
19 entries, SHA-256
`25dcba326a9c2c2aab50f9ea5601d1daf4337c500d0cd72e97912ae3d1c70297`, English
ROM SHA-1 `4fe9c5ffe335e028397a8503ee5d3a625607dc16`, patch 133,251 bytes.
Unzipped, it passes `release_test.py` 41/41, and its `patch-tools/apply.py`
reproduces `ogre_en.sha1`; `test_package` 33/33, `test_webpatcher` 2/2. It is
the asset of the GitHub pre-release `v0.1.0-dev`. Older packages were
deleted. Still not a public release: the manual checklist steps 6-8 (Flips,
ROM Patcher JS, a clean PC, another emulator) remain for the owner.

Earlier package of the same build (before the web patcher): 313,994 bytes,
18 entries, SHA-256
`b5c184d90acb9b78228f9641ddfce787852884af330cf96de96a073010098f41`;
`release_test.py` 40/40, `save_test.py` 27/27.

Done 2026-10-09 (round 2, task release-package). First package:
`dist\ogre-battle-gaiden-en-0.1.0-dev+e63bffd1-win64.zip`, 296,941 bytes,
18 entries, SHA-256 `475f0e68198f3cecf183af4a5d7cb70c7b23e3981a14989af773e0e7b6544c97`,
English ROM SHA-1 `e63bffd10b2211da02cd80c699a11ecdce221a0c`. A second run
gives the same bytes. Unzipped, it passes `release_test.py` 40/40 and the
other player scripts (bps 26/26, rom 27/27, state 33/33); its Python applier
reproduces `ogre_en.sha1` with Python 3.14 and 3.12. All refusal cases work
(`tools/release/test_package.py`, 33 checks). Not a public release yet: the
checklist below has manual steps that were not done (Flips, ROM Patcher JS,
another emulator), and the pre-drawn Japanese graphics are still in the game.

## Done

### VERSION

`VERSION` (repository root) holds `MAJOR.MINOR.PATCH`, now `0.1.0`. It goes
into the version resource of `zenobia.exe` (CMake reads it; a change
reconfigures and relinks) and into the package name. Packages are dev builds
unless made with `--release`: their version gets `-dev+` and the first 8
hex digits of the English ROM's SHA-1, e.g. `0.1.0-dev+e63bffd1`.

### Version resource and icon of zenobia.exe

* `runtime/src/frontend/zenobia.rc`: `VS_VERSION_INFO` (FILEVERSION and
  PRODUCTVERSION `0.1.0.0`; FileVersion/ProductVersion "0.1.0";
  FileDescription "Ogre Battle Gaiden: Prince of Zenobia (English)", the
  window title; ProductName "... - English fan translation"; CompanyName and
  LegalCopyright "The open-ogre-battle-gaiden-zenobia contributors", MIT;
  OriginalFilename `zenobia.exe`; Comments: unofficial fan project, needs
  your own game). The version numbers come from CMake
  (`ZEN_VERSION_MAJOR/MINOR/PATCH`); without them the file stops with
  `#error`. The icon line is compiled only with `ZEN_HAVE_ICON`. No manifest
  here (the linker embeds `zenobia.manifest`).
* `runtime/src/frontend/resource.h`: `IDI_ZENOBIA` = 1, the lowest icon ID,
  so Explorer shows it for the file.
* `CMakeLists.txt` (one block after the `zenobia` target, inside
  `if(WIN32)`): reads `VERSION` (configure error if it is not
  MAJOR.MINOR.PATCH; `CMAKE_CONFIGURE_DEPENDS`), `find_package(Python3
  COMPONENTS Interpreter QUIET)`; with Python a custom command runs
  `tools/release/mkicon.py assets/icon/zenobia.txt build/zenobia.ico`, the
  icon is a source of the target and an `OBJECT_DEPENDS` of the .rc; the .rc
  gets the definitions and `build/` as its include path. Without Python:
  `-- Python 3 not found: zenobia.exe is built without its icon`, and the
  player builds with the version resource only.
* Checked in a scratch copy of the CMake setup and in the real build: no
  change, no work; icon source changed: icon, .res and link rebuilt; VERSION
  changed: CMake reruns, the exe says the new version; VERSION `0.2`:
  configure error; `-DCMAKE_DISABLE_FIND_PACKAGE_Python3=TRUE`: builds,
  version present, no icon (`LoadIcon` fails). The real `build\zenobia.exe`
  grew from 362,496 to 381,440 bytes.
* The window itself still uses the stock application icon: `gui.c` registers
  its class with `IDI_APPLICATION` (owner: player; see Open issues).

### The icon (`assets/icon/zenobia.txt`, `tools/release/mkicon.py`)

Original pixel art: a tarot card in a gold frame with a crown and an
upright sword on a night-blue face (and a few stars at 32/48 px). Hand-drawn
at 16, 32 and 48 px in a text-art file like the images of
`gfx-pipeline.md` 1.4, one character per pixel: `@chars C = #RRGGBB`
(or `#RRGGBBAA`, `none`), `@size W H` + `@data` + rows, `@scale FROM to TO`.
The file also asks for 64 (32 x2), 96 (48 x2) and 256 (32 x8) px, enlarged
without smoothing so that high-DPI screens show sharp pixels.

`mkicon.py` (standard library only; `python tools/release/mkicon.py SRC
OUT.ico [--preview PNG]` or `python -m tools.release.mkicon ...`) checks the
source (row lengths, unknown characters, colours, square sizes, whole
multiples; errors name file and line, exit 1, no .ico written) and writes
the 16/32/48 images as 32-bit BGRA bitmaps with an AND mask and the larger
ones as PNG, through a temporary file. Output: 17,443 bytes, deterministic.
All six sizes load through the Windows icon loader (`LoadImage`,
`PrivateExtractIcons`) with transparent corners; the .NET Framework's
managed `System.Drawing.Icon` cannot decode PNG frames (a .NET limit, not
the file).

### `python -m tools.release.package [--out dist] [--build build] [--rom rom/baserom.ngc] [--release]`

Builds `OUT/ogre-battle-gaiden-en-<version>-win64.zip` from the build folder;
it never builds anything itself. The zip holds one folder,
`ogre-battle-gaiden-en-<version>/`:

| Entry | Source | Bytes (0.1.0-dev+e63bffd1) |
|---|---|---|
| `README.txt` | `tools/release/README.txt`, fields filled, CRLF | 8,856 |
| `zenobia.exe` | `build\zenobia.exe` | 381,440 |
| `ogre_en.bps` | `build\ogre_en.bps` | 113,807 |
| `ogre_en.sha1` | `build\ogre_en.sha1` (unchanged) | 41 |
| `LICENSE.txt` | `LICENSE`, CRLF | 1,126 |
| `THIRD_PARTY_NOTICES.txt` | `THIRD_PARTY_NOTICES.md`, CRLF | 3,697 |
| `patch-tools/apply.py` | `tools/release/patch_tools_apply.py` | 1,506 |
| `patch-tools/tools/...` | `tools/__init__.py`, `tools/patch/{__init__,apply,bps}.py`, `tools/recomp/{__init__,rom}.py`, unchanged (found by following the imports of `tools/patch/apply.py`) | 37,970 |

Checks (all run; any problem refuses, exit 1, nothing written):

| Check | Refuses when |
|---|---|
| version | `VERSION` is not MAJOR.MINOR.PATCH |
| inputs | `zenobia.exe`, `ogre_en.ngc/.bps/.sha1` or the ROM is missing |
| rom | the ROM is not the original (SHA-1 `5ac794c0...`) |
| sha1 | `ogre_en.sha1` does not match `ogre_en.ngc` |
| layout | `python -m tools.patch.layout build/ogre_en.ngc ROM` fails (save blocks, regions) |
| audit | `python -m tools.patch.bps audit ROM build/ogre_en.bps` fails |
| patch | `ogre_en.bps` applied to the ROM does not give `ogre_en.ngc` |
| exe | `zenobia.exe` is older than its sources: Ninja dry run (`ninja -C BUILD -n zenobia`, the Ninja recorded in `CMakeCache.txt`) when the build folder has `build.ninja`, else file times of its 53 sources (the C/RC files CMakeLists.txt lists for it and the core, the headers they include, the manifest, `VERSION`, the icon source, `mkicon.py`); also when its version resource is not `VERSION` or it imports the Visual C++ runtime DLLs. A missing icon is only a note. |
| contents | a file looks like game data or local settings (`.ngc .ngp .npc .sav .state .ini .pdb .zip .7z .rar .gz`, a 2,097,152-byte file), a text file is not UTF-8 or holds Japanese, `README.txt` has an unfilled `@FIELD@` or does not name every packaged item |
| rom-data | ROM data in a packaged file (below) |
| zip | the zip read back differs from the staged files; the extracted `patch-tools/apply.py` (run with `python -I`) does not make the English ROM or leaves files behind; with `--release`, a different zip of the same version exists |

ROM-data scan (every packaged file except `ogre_en.bps`, which the audit
covers): every 8-byte window of a file that also occurs in the ROM is a hit
(windows of one repeated byte are fill and not counted); overlapping hits
form a region. A region is allowed when, as a whole, it is data that any
binary holds, or occurs in the ROM only in the cartridge header; otherwise
it is cut into the longest pieces that occur in the ROM as they are, and
each piece must pass the same test. The allowed kinds:

* padding: all but at most 4 bytes have one value (zero fill with small
  numbers, e.g. PE structures);
* runs: at most 3 stretches of one repeated byte;
* counting: the bytes, or the 16- or 32-bit units, step by a constant
  amount, with at most 2 breaks (needs 4 units or more), e.g. "UVWXYZ" then
  zeros, or a table of 32-bit indexes;
* header: occurs in the ROM only in 0x00-0x3F. `zenobia.exe` holds the
  cartridge licence string and the 12-character header title
  (`romload.c` compares them to recognise the game), and `LICENSE` /
  `THIRD_PARTY_NOTICES` contain the English word "COPYRIGHT ", which the
  header starts with.

Current package: 12 files, 0 problems; allowed 1,927 padding, 112 runs, 73
counting, 7 header. Measured on the game's own data, a copied block is let
through only when it is itself almost empty or a counting/run pattern:
random 16-, 32- and 64-byte blocks of the game's data are found 86%, 94% and
96% of the time. (A first, per-window version of the rule let 34% of the
game's windows through one by one and missed 5.75% of random 64-byte
blocks, including low-colour graphics; the test suite now has such a block.)

Deterministic: fixed entry order, MS-DOS attributes (0x20 files, 0x10
folders), every entry dated with the newest input file's time in UTC, or
`SOURCE_DATE_EPOCH`; deflate level 9 only where it makes the file smaller.
The bytes depend on the Python build's zlib: Python 3.14 (zlib-ng) and 3.12
(zlib 1.3.1) give different, each reproducible, zips; the output names the
zlib used. The zip is written to `NAME.zip.tmp`, verified, then renamed; the
output ends with the listing, the SHA-256 and SHA-1 of the zip and a release
notes line. About 2 s.

### `tools/release/README.txt` (README.txt in the zip)

For players, ASCII, 76 columns: what it is; contents; the required original
(name, size, CRC32, MD5, SHA-1, filled in from the ROM itself); playing with
the player (extract all files, SmartScreen, choosing the game file, the
player's error messages); controls; saves, save states and `zenobia.ini`;
moving to another PC or version; command line; the patch with other
emulators (Floating IPS, ROM Patcher JS, `python patch-tools/apply.py`,
`--write-patched`), checking the English ROM's SHA-1/CRC32; known issues;
licence and credits. Fields: `@VERSION@ @DATE@ @ORIGINAL_SIZE@
@ORIGINAL_CRC32@ @ORIGINAL_MD5@ @ORIGINAL_SHA1@ @ENGLISH_SHA1@
@ENGLISH_CRC32@`.

### `patch-tools` and `tools/release/patch_tools_apply.py`

`python patch-tools/apply.py ORIGINAL [PATCH] [-o OUT]` from the release
folder (or `python apply.py ...` inside `patch-tools`). The launcher puts
its folder on `sys.path` (works with `python -I`), writes no bytecode, and
makes the release folder the place where `tools/patch/apply.py` looks for
`ogre_en.bps` first; everything else is the project's own applier,
unchanged. Checked from the unzipped package: default patch and output,
the form `python patch-tools/apply.py ORIGINAL ogre_en.bps -o ogre_en.ngc`
with Python 3.12 `-I`, from inside `patch-tools`, a ROM path with spaces:
all write `e63bffd1...` ("matches ogre_en.sha1"); the English ROM given as
the original is refused ("already patched"), nothing written.

### "Patch your game.html": the one-file web patcher (2026-10-10)

For people who want the English game file without any command line, on any
system: double-click the page (it opens in the browser, offline), click the
box and choose the game file (`.ngc`/`.ngp`, or a `.zip` that contains it),
click "Save the English game". The page reads stored and deflate zips
(`DecompressionStream`), accepts an over-dump (the game plus `0xFF` fill),
checks the original's SHA-1, applies the built-in BPS patch with its own
applier (CRC32 of source, target and patch), checks the result's SHA-1, and
saves `Ogre Battle Gaiden - Prince of Zenobia (English).ngc`; an English ROM
is recognised, anything else gets a plain explanation. Its
Content-Security-Policy (`default-src 'none'`) forbids every network access.

* Template `tools/release/patcher.html` (all code ours, ASCII);
  `tools/release/webpatcher.py` fills in the patch (base64), the checksums
  and the version: `python -m tools.release.webpatcher [--out FILE]`.
  `package.py` adds the page to the zip (`Patch your game.html`; it is
  covered by the Japanese scan and the ROM-data scan like every file).
* `python -m tools.release.test_webpatcher [rom/baserom.ngc]` runs the
  page's own script in Node (same browser APIs): the plain ROM, a stored
  and a deflate zip and an over-dump all give the English ROM's SHA-1; an
  English ROM is recognised; a changed ROM, a damaged zip, a
  password-protected zip and a `.7z` are refused with their messages; plus
  static checks (no URLs, CSP present, every field filled). Checked by hand
  in Chrome too (zip chosen, "This is the right game", Save enabled).
* Later, when the repository is public, the same page can be served from
  GitHub Pages for a true "click here" link.

### Other files

* `tools/release/pe.py`: reads a PE file's resources (version information,
  icon groups) and imports; `python -m tools.release.pe FILE.exe`.
* `tools/release/test_package.py`: the regression test below.

## How to test / reproduce

    build.bat                                         # zenobia.exe with version + icon
    python -m tools.release.package                   # dist\ogre-battle-gaiden-en-<v>-win64.zip
    python -m tools.release.test_package --work NEW_EMPTY_DIR
    python -m tools.release.pe build\zenobia.exe      # version, icon sizes, imports
    python tools\release\mkicon.py assets\icon\zenobia.txt X.ico --preview X.png

`test_package.py` (33 checks, about 20 s) copies the build outputs into the
work folder (the build folder is never changed) and checks: packaging, a
byte-identical second run, "unchanged" on a third, the `--release` name;
each refusal on its own with nothing written (sha1 file changed; a patch
that writes English text at 0x3C0000, the save blocks: layout; a patch with
16 ROM bytes as a literal at 0x37FF00: audit; `zenobia.exe` dated 2020:
exe; 64 ROM bytes appended to `zenobia.exe`: rom-data; `ogre_en.bps`
missing: inputs; `--release` over a different zip: zip); the match
classification (padding, runs, 8/16/32-bit counting, text, the header, a
24-byte and a 32-byte low-information ROM block inside a file); the icon
(six sizes, BMP/PNG, deterministic, five malformed sources refused); and that
this workstream's files are plain ASCII.

The Ninja path of the exe check was tried on the scratch CMake build: stale
configuration ("Re-running CMake..."), up to date ("no work to do"), a
touched C file (compile + link): refused, accepted, refused; a dry run
changes no build file.

Acceptance runs of 2026-10-09 (all on the final zip, extracted with
PowerShell `Expand-Archive`; Explorer's shell extraction and `tar -xf` give
the same 18 entries byte for byte):

    python runtime/src/frontend/tests/release_test.py --exe X\zenobia.exe
        --patch X\ogre_en.bps --rom rom/baserom.ngc --english build/ogre_en.ngc
        --harness build/ngp_harness.exe
        --save-state build/states/data-popup_save_prompt.state --work NEW_DIR
                                                       -> passed 40, failed 0
    python runtime/src/frontend/tests/bps_test.py X\zenobia.exe NEW_DIR .  -> 26/26
    bash runtime/src/frontend/tests/rom_test.sh X\zenobia.exe JP_COPY X\ogre_en.bps build/ogre_en.ngc NEW_DIR -> 27/27
    bash runtime/src/frontend/tests/state_test.sh X\zenobia.exe build/ngp_harness.exe build/ogre_en.ngc rom/baserom.ngc NEW_DIR -> 33/33
    (Get-Item X\zenobia.exe).VersionInfo   -> FileVersion 0.1.0, ProductVersion 0.1.0, ...
    python -m tools.release.pe X\zenobia.exe   -> icon group 1: 16, 32, 48, 64, 96, 256

## Release checklist

1. Clean build: `build.bat`, then `python -m tools.patch.build
   rom/baserom.ngc` (prints `patch audit: OK` and the layout report with
   `save blocks 3B0000-3EFFFF untouched`).
2. Automated tests: `python -m tools.patch.test_bps rom/baserom.ngc`,
   `python runtime/src/core/tests/save_test.py ...` (`core.md`),
   `python -m tools.release.test_package --work NEW_DIR`.
3. Review `tools/release/README.txt`, above all "Known issues". Raise
   `VERSION` if this version was released before, then `build.bat` again (the
   exe carries the version).
4. `python -m tools.release.package --release` (no `-dev` suffix; refuses
   to replace a different zip of the same version). Keep its output: the
   zip's SHA-256 and the release notes line.
5. Extract the zip with Explorer ("Extract All") into a new folder; run
   `release_test.py` on the extracted `zenobia.exe` and `ogre_en.bps` (as in
   "How to test", 40 checks) and `python patch-tools/apply.py ORIGINAL` in
   it ("matches ogre_en.sha1").
6. By hand, not automated here (no third-party downloads in this project):
   apply `ogre_en.bps` to a copy of the original with Floating IPS (GUI and
   `flips --apply`) and with ROM Patcher JS in a browser; the SHA-1 of each
   result (`certutil -hashfile FILE SHA1`) must equal `ogre_en.sha1`, and
   both tools must refuse the English ROM and a changed copy of the
   original.
7. By hand on a clean Windows 10/11 PC or account: Explorer shows the icon
   and, under Properties > Details, file version 0.1.0.0 / product version
   0.1.0; SmartScreen asks once ("More info", "Run anyway"); choose the ROM,
   play a few minutes, save in the game, quit, start again, load.
8. Play the English ROM in an established emulator (STATUS checklist).
9. Publish the zip with its SHA-256 and release notes: version, date, the
   English ROM's SHA-1, known issues. Never rebuild a published version.

## Open issues

1. Resolved (round 2): `gui.c` registers its window class with
   `IDI_ZENOBIA` (`LoadIconW` and `LoadImageW` for the small icon), falling
   back to `IDI_APPLICATION` when the exe has no icon (a build without
   Python), so the window and the taskbar show the program icon.
2. The executable is not signed (SmartScreen asks before the first start).
3. Only 16/32/48 px are drawn; Windows makes 20, 24 and 40 px (125% and
   150% scaling) by shrinking the next size, which softens the pixel art.
   Hand-drawn 24 and 40 px images can be added to the same source file.
4. The zip is reproducible for one Python build (its zlib): 3.12 and 3.14
   give different bytes with the same contents.
5. The README's date is the UTC date of the newest input file, which can be
   the next day in local time (the first package says 2026-10-10).
6. Resolved (round 3): `tools/patch/apply.main` takes a `prog` parameter
   and the packaged launcher passes `python patch-tools/apply.py`, so its
   `--help` and its "give the original ROM first" error name the command a
   player types.
7. The ROM-data rule may one day flag a coincidence in a rebuilt
   `zenobia.exe` (small numbers with 5 or more different values that also
   happen to be in the ROM). The refusal lists file offset, length and ROM
   offset; check the bytes, and if they are such a coincidence, adjust
   `trivial` in `package.py` with a test case instead of skipping the check.
8. Without a Ninja build folder the exe check uses file times and cannot see
   changes to `CMakeLists.txt`.
9. "Known issues" in the README is written by hand for each release.

## Next steps

* Player owner: the window icon (open issue 1).
* Orchestrator: STATUS.md (release package done; checklist item "Release
  packaging"), `player.md` "Release package" and `patch-distribution.md`
  "Release checks" can point to `python -m tools.release.package` and this
  checklist; README.md "Building from source" can add the package command;
  `.gitignore` could list `dist/` (only zips land there, which `*.zip`
  already ignores).
* Before the first public release: checklist steps 6-8, the graphics work,
  then `--release`.
