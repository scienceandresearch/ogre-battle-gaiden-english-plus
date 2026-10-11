# Patch distribution (BPS)

## Goal

Distribute the translation as a standard BPS patch (beat format, "BPS1") that
users apply to their own ROM with common tools (Floating IPS, ROM Patcher JS),
with our own Python applier, or inside the Windows player. The patch must not
carry ROM data: bytes that exist in the original ROM are referenced by copy
actions, and only new bytes (English text, our code, our font and art) are
stored as literals. The build checks this every time.

## State

Done for round 1 and integrated end to end with the player (2026-10-09,
integration pass). Every build writes `build/ogre_en.bps` and
`build/ogre_en.sha1` (40 hex digits and a line feed); the audit passes; all
tests pass. The player's real `zenobia.exe` (not a scratch copy) applies the
real patch and all 28 test vectors exactly like `tools/patch/bps.py`, and a
release folder with only `zenobia.exe` + `ogre_en.bps` plays the original ROM
(`player.md`, "Release package"; `runtime/src/frontend/tests/release_test.py`).

Not releasable yet: the English ROM keeps data in the game's save blocks
(open issue 1). The BPS step now reports this on every build with a `WARNING:
the patch puts data in the game's save blocks` line. Also not done: a
packaging script and a manual check with Flips / ROM Patcher JS (see Next
steps).

Current numbers (build of 2026-10-09 19:50; the translation keeps changing,
so these change with it):

| | |
|---|---|
| Patch `build/ogre_en.bps` | 113,450 bytes (zipped with `zenobia.exe`: 280 KB) |
| SourceRead (same offset) | 1,945 actions, 1,905,810 bytes |
| SourceCopy (from anywhere in the original) | 114 actions, 4,288 bytes |
| TargetCopy (repeats inside the English ROM) | 11,181 actions, 123,770 bytes |
| TargetRead (literals) | 8,131 runs, 63,284 bytes |
| Audit | OK: longest literal run found in the original ROM is 7 bytes (limit 8) |
| English ROM SHA-1 | `e40d4ae69c360a0113064ae0fd66a226f45aff24` (changes with every build that changes the ROM) |
| Patch file SHA-1 | `a2f64510573589ebb104d2ab58fbd703c27b6e79` (the encoder is deterministic: same ROMs, same patch) |
| Save-area check | WARNING: `0x3C0000-0x3C3BDA` (15,323 bytes) and `0x3E0000-0x3E717B` (29,052 bytes) are inside blocks 27-30 |
| Time | patch step about 0.6 s of a 0.9 s build |

## Done

### `tools/patch/bps.py`: encoder, decoder, audit (standard library only)

* Format exactly as specified by beat: `"BPS1"`, source size, target size,
  metadata size + metadata, actions `((length - 1) << 2) | kind` with kinds
  SourceRead 0 / TargetRead 1 / SourceCopy 2 / TargetCopy 3, copy moves encoded
  as `(|delta| << 1) | negative` relative to a cursor per copy kind, then the
  CRC32 of the source, the target and the patch (all bytes before that field),
  little endian. Numbers use beat's variable-length encoding (7 bits per byte,
  last byte has bit 7 set, each continuation adds one). The patch's metadata is
  empty (best compatibility).
* Encoder (`encode`, `encode_actions`): finds the changed spans quickly (XOR of
  the two files as big integers, then a regex over the non-zero bytes);
  unchanged runs of 32+ bytes become SourceRead at once. In and just before a
  changed span, each position gets the action that saves the most patch bytes
  among: SourceRead (same offset), SourceCopy (every 8-byte window that the
  encoder may look up is indexed in the original ROM; for each window up to 16
  places, plus the longest run of a repeated byte, are extended to the full
  match), TargetCopy (6-byte windows of earlier literal/copied target data,
  8 most recent places, overlapping copies allowed for runs). When the 8 bytes
  starting at a position occur anywhere in the original, a copy is forced, so a
  literal can never contain 8 bytes found in the original. Deterministic
  output (no hash-order dependence).
* `create(source, target)`: encode, apply the new patch and compare with the
  target, then `audit`; raises `AuditError` if the audit fails.
* `audit(source, patch)`: independent check of the finished patch: every
  8-byte piece of every TargetRead run is looked up against all 8-byte pieces
  of the original (one pass over the ROM); reports the literal bytes, runs,
  the longest literal run that also occurs in the original (exact, found by
  trying 7, 6, ... bytes) and every offender (target offset, length, original
  offset). Cross-checked with a brute-force script (full set of the original's
  8- and 7-byte windows): same result (0 eight-byte matches, 25 seven-byte ones).
  Mutation check: with the encoder's SourceCopy search switched off, the audit
  flags 18 literal runs of 8 to 19 bytes (original instructions at 0x200829
  that the hook code at 0x37021F repeats, parts of the in-place text area near
  0x299471, a few font bytes), the build step stops and no `.bps`/`.sha1` is
  left behind. With the search on, the patch copies these bytes from the
  player's original ROM instead of storing them.
* Decoder (`parse`, `apply`): validates the signature, patch CRC, every number
  (truncation, values above 64 bits), sizes (limit 256 MiB), metadata bounds,
  every action's bounds (SourceRead within the source, TargetRead within the
  patch, copies within the source / within the target written so far, output
  never past the target size and exactly filled), then the source size and
  CRC (`SourceMismatch`, with `already_patched` set when the input is the
  target) and the result's CRC (`TargetMismatch`). Errors: `PatchFormatError`
  (damaged/malformed patch), `SourceMismatch`, `TargetMismatch`, `AuditError`,
  all subclasses of `BpsError`.
* Command line: `python -m tools.patch.bps create SRC TGT OUT.bps
  [--metadata TEXT]`, `apply SRC PATCH OUT`, `audit SRC PATCH` (exit 1 on
  failure, lists offenders), `info PATCH` (sizes, CRCs, action counts).
* Tuning was swept on the real ROM (target window 4/5/6/8, more candidates):
  all variants are 110-122 KB; the defaults are a balance of size and speed.

### `tools/patch/build.py`: final step

After `build/ogre_en.ngc` (and `symbols.txt`) the build calls
`write_distribution_patch`: removes any old `.bps`/`.sha1` next to the output
ROM (so a failed step never leaves a patch for an older ROM), creates the
patch with `bps.create` (round trip + audit), writes `build/ogre_en.bps` and
`build/ogre_en.sha1` (40 hex digits + newline, nothing else), and prints:

    patch: ...\build\ogre_en.bps, 113,452 bytes
    patch audit: OK: 63,297 literal bytes in 8,129 runs; longest literal run found in the source: 7 bytes (limit 8)
    patched ROM SHA-1: 0c31dc6a0def4d375730d1d45779467f471e57b2 (...\build\ogre_en.sha1)

If the audit fails the build stops with `BPS patch audit failed ...` and lists
the offending literals (ROM addresses). With `-o OUT.ngc` the files are named
`OUT.bps` / `OUT.sha1`. All earlier build output is unchanged.

Save-area check (`save_area_changes`, added in the integration pass): the
game saves to cartridge flash blocks 27-30 (`SAVE_AREA = 0x3B0000-0x3EFFFF`:
suspend data, files 1-3; slot table at `0x29A66E`, see `explore-data.md`).
The step lists every range the patch changes there and prints

    WARNING: the patch puts data in the game's save blocks 27-30 (0x3B0000-0x3EFFFF): 0x3C0000-0x3C3BDA (15,323 bytes), 0x3E0000-0x3E717B (29,052 bytes). In-game saves overwrite and erase it; not releasable until it moves out (docs/workstreams/patch-distribution.md, release checks).

It is a warning, not an error, so the build keeps working for everyone until
the layout is fixed; a release build must not print it.

### `tools/patch/apply.py`: user-facing applier

`python -m tools.patch.apply ORIGINAL [PATCH.bps] [-o OUT.ngc]`

* ORIGINAL may also be a `.zip` that contains the ROM (the member with the
  right SHA-1 is used). If the patch is given first (Flips order) the
  arguments are swapped with a note.
* PATCH defaults to `build/ogre_en.bps`, else `ogre_en.bps` in the repository
  root, next to ORIGINAL, or in the current folder. OUT defaults to
  `ogre_en.ngc` next to ORIGINAL; the original is never overwritten.
* Checks: the patch (signature, checksums, structure) first; then the
  original's SHA-1 (`5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`); the patch's
  source CRC; after patching the result's CRC32 (in the patch) and SHA-1
  (from `PATCH.sha1` when present, first word of the file).
* Messages (exit code 1): "is already patched: it is the English ROM that this
  patch makes" (input = patch target); "is not the ROM this patch is for"
  with both SHA-1s plus a hint: wrong size / looks patched already (the
  original's blank space at file offset 0x170000 is filled) / other dump or
  revision; "the patch ... cannot be used (patch checksum mismatch: the file
  is damaged or incomplete). Download it again."; "was not made for this
  ROM"; "the patch and that file do not belong together" (SHA-1 file
  mismatch).
* Imports only the standard library, `tools/patch/bps.py` and
  `tools/recomp/rom.py`.

### `tools/patch/test_bps.py`

`python -m tools.patch.test_bps rom/baserom.ngc` (11 tests, about 2 s; without
the ROM only the 7 synthetic tests run):

* numbers: known encodings (0 -> `80`, 127 -> `FF`, 128 -> `00 80`, 16511 ->
  `7F FF`, 16512 -> `00 00 80`, ...), round trips up to 2^64-1 (10 bytes),
  uniqueness, truncated and over-64-bit numbers rejected;
* a hand-assembled patch with every action, SourceCopy and TargetCopy moving
  backwards, overlapping TargetCopy (runs of period 1 and 2) and metadata,
  checked against spelled-out expected bytes; "negative zero" moves;
* encoder round trips: empty/empty, empty source, empty target, identical
  files, a case using all four actions (with a negative SourceCopy move and an
  overlapping TargetCopy), target longer / shorter than the source, runs,
  large numbers (4-byte action header, 3-byte TargetRead header, 4-byte copy
  move on a 1.1 MB file); 400 random edit cases with small alphabets. Every
  case goes through `create` (round trip + audit), a byte-by-byte reference
  decoder written from the specification, and a determinism check;
* 18 malformed patches (flipped byte, truncated, too short, bad signature,
  SourceRead/SourceCopy/TargetRead/TargetCopy out of bounds, writes past or
  short of the target size, bad metadata size, truncated and oversized
  numbers, 1 TiB target, wrong target CRC, wrong source CRC) and wrong
  sources (changed byte, shorter, longer, already patched);
* the audit: 8, 9 and 20 bytes of the original inside a literal are reported
  with the right offsets; 7 bytes pass with "longest 7";
* real ROM: `create(original, build/ogre_en.ngc)`, apply, reference decoder,
  numbers at most 8 bytes long (the C applier's limit); damaged patch, changed
  ROM and English ROM rejected; `build/ogre_en.bps` reproduces
  `build/ogre_en.ngc` and matches `build/ogre_en.sha1`; the apply command in a
  temporary folder (success, default output, .zip input, swapped arguments,
  already patched, wrong ROM, wrong size, missing file, refusing to overwrite
  the original, damaged patch, wrong .sha1).

`--vectors DIR` writes the synthetic cases as files (`NAME.source`,
`NAME.bps`, `NAME.target`) with a `MANIFEST.txt` of expected results (`ok`,
`error-patch`, `error-source`, `error-target`) for testing other BPS
implementations.

A heavier fuzz run (9,000 random cases with sizes up to 6 KB, alphabets of 1
to 256 values, block copies, repeats and runs) passed as well; 535 cases had a
longest literal-in-source run of exactly 7 bytes, so the 8-byte limit is
exercised at its edge.

### Interoperability with the player's C applier

`runtime/src/frontend/bps.c`, through the real player
(`zenobia.exe --bps-apply SOURCE PATCH OUT`, integration pass): all 10 valid
vectors from `--vectors` give the expected target byte for byte, all 18
malformed vectors are rejected with the matching error class (exit 12-16 or
19-21 damaged patch, 18 wrong source, 22 wrong result; the 1 TiB target is
refused as an invalid header, not by running out of memory), and
`build/ogre_en.bps` gives `build/ogre_en.ngc` exactly; `tools/patch/bps.py
apply` and `tools/patch/apply.py` give the same file (all three SHA-1s equal
`build/ogre_en.sha1`). The player also applies the patch in memory when it
loads the original ROM; that image's SHA-1 equals `build/ogre_en.sha1` and its
picture equals the harness on `build/ogre_en.ngc`.

## Applying the patch (instructions for users)

You need your own copy of the original game:

| | |
|---|---|
| Game | Densetsu no Ogre Battle Gaiden - Zenobia no Ouji (Japan), Neo Geo Pocket Color |
| Size | 2,097,152 bytes |
| CRC32 | `EEEEFD6A` |
| MD5 | `26d0557d8a465aa8f430d5e4d94c679a` |
| SHA-1 | `5ac794c0f125bfb97efe9cd06c2aca3afdf549ea` |

The file name and extension (`.ngc`, `.ngp`) do not matter. The patch stores
the CRC32 of the original and of the result, so all tools below refuse a
different ROM; never force them to apply it anyway.

**Floating IPS (Flips), Windows/Linux.** GUI: start Flips, click
"Apply Patch", choose `ogre_en.bps`, then the original ROM, then where to save
the English ROM (for example `ogre_en.ngc`). Command line:

    flips --apply ogre_en.bps "original.ngc" ogre_en.ngc

Do not use its option to ignore checksums.

**ROM Patcher JS (any browser).** Open ROM Patcher JS (marcrobledo.com,
RomPatcher.js), choose the original ROM as "ROM file" (a .zip works too), check
that the CRC32 / SHA-1 it shows match the table above, choose `ogre_en.bps` as
"Patch file" and click "Apply patch"; the browser saves the English ROM. The
files are processed locally in the browser.

**Python (this repository, or the release zip if it includes the `tools`
folder; Python 3.7+, no extra packages).**

    python -m tools.patch.apply "original.ngc" ogre_en.bps -o ogre_en.ngc

It checks the original's SHA-1 before patching and the result's CRC32 and
SHA-1 afterwards (with `ogre_en.sha1` next to the patch).

**The Windows player** (player workstream) applies the same patch at load
time; see `player.md`.

**Check the result** (optional): its SHA-1 must equal the contents of
`ogre_en.sha1`, e.g. `certutil -hashfile ogre_en.ngc SHA1` (Windows command
prompt), `Get-FileHash ogre_en.ngc -Algorithm SHA1` (PowerShell),
`sha1sum ogre_en.ngc` (Linux) or `shasum ogre_en.ngc` (macOS).

## Release package

The player release (what most people download) is defined in `player.md`,
"Release package": `zenobia.exe`, `ogre_en.bps` and the player's own ROM are
all that is needed to play; the zip adds `ogre_en.sha1`, `README.txt`,
`LICENSE.txt` and `THIRD_PARTY_NOTICES.txt`. The same `ogre_en.bps` and
`ogre_en.sha1` serve people who use other emulators; for them the README
carries the instructions of "Applying the patch" above.

Contents (one zip named with the version, e.g. `ogre-battle-gaiden-en-v0.1.zip`):

* `ogre_en.bps`: the patch from a clean build (audit OK and no save-area
  warning in the build log).
* `ogre_en.sha1`: SHA-1 of the patched ROM (also quoted in the README).
* `zenobia.exe`: the Windows player (self-contained, see `player.md`).
* `README.txt`: what the project is; the required ROM and its checksums (table
  above); how to play with the player (`player.md`, "Steps for the player")
  and how to apply the patch for other emulators (the instructions above);
  the patched ROM's SHA-1; emulators known to work; known issues; credits;
  version and date.
* `LICENSE.txt` and `THIRD_PARTY_NOTICES.txt` (the player contains the Z80
  core, MIT, and MAME-derived timing tables, BSD-3-Clause).
* Optional: the Python applier, as these files at the top of the zip next to
  `ogre_en.bps`: `tools/__init__.py`, `tools/patch/__init__.py`,
  `tools/patch/apply.py`, `tools/patch/bps.py`, `tools/recomp/__init__.py`,
  `tools/recomp/rom.py`. Run `python -m tools.patch.apply original.ngc` in
  that folder; it finds `ogre_en.bps` and `ogre_en.sha1` there (the folder
  that contains `tools`).
* Never: the original ROM, a patched ROM, archives containing either, save
  states, save files, `zenobia.ini`, `zenobia.pdb`, screenshots or any other
  file with game data.

Release checks:

1. Clean build from the original ROM: `python -m tools.patch.build
   rom/baserom.ngc` prints `patch audit: OK` and no `WARNING: the patch puts
   data in the game's save blocks` line (fails today: open issue 1).
2. `python -m tools.patch.test_bps rom/baserom.ngc`: all tests pass (this
   includes the shipped `build/ogre_en.bps` and `build/ogre_en.sha1`).
3. `python -m tools.patch.bps audit rom/baserom.ngc build/ogre_en.bps`
   (exit code 0), and `python -m tools.patch.bps info build/ogre_en.bps`
   (metadata empty, sizes 2,097,152 -> 2,097,152).
4. `python runtime/src/frontend/tests/release_test.py ...` (`player.md`): all
   checks pass, including the player's in-memory patching, `--bps-apply` and
   `tools/patch/bps.py` giving the English ROM.
5. Apply `ogre_en.bps` with Flips and ROM Patcher JS: the SHA-1 of each result
   equals `ogre_en.sha1`.
6. Play test the patched ROM in an established emulator (STATUS checklist).
7. Check the zip's file list against the contents above.

## How to test / reproduce

    python -m tools.patch.build rom/baserom.ngc            # writes build/ogre_en.{ngc,bps,sha1}
    python -m tools.patch.test_bps rom/baserom.ngc         # all tests
    python -m tools.patch.test_bps --vectors <folder>      # synthetic vectors + MANIFEST.txt
    python -m tools.patch.bps info build/ogre_en.bps
    python -m tools.patch.bps audit rom/baserom.ngc build/ogre_en.bps
    python -m tools.patch.apply rom/baserom.ngc -o <folder>/ogre_en.ngc
    build\zenobia.exe --bps-apply rom\baserom.ngc build\ogre_en.bps <folder>\c.ngc

Results of the integration pass (2026-10-09): `test_bps` 11 tests, 0 failed
(2.1 s); the vectors through `zenobia.exe --bps-apply` 28/28 as expected;
the C applier, `bps.py apply`, `apply.py` and the build give the same English
ROM; `release_test.py` 40/40 (`player.md`). The build at 19:35 reproduced
the previous build (18:58) byte for byte; the build at 19:50 picked up a
translation change made by another agent meanwhile (UI text one byte
shorter), hence the new numbers in "State".

`build/` is git-ignored, so the patch is a build artifact, not a repository
file.

## Open issues

1. **Patch data in the game's save blocks: release blocker** (owner: patch
   build layout, `FREE_END` / `TEXT_START` / `UI_TEXT_START` / `TABLES_START`
   in `tools/patch/build.py`; details and a proposal in `player.md`, open
   issue 1). Not a BPS problem, but it decides what the patch may ship: once
   players have save files, those files contain whole 64 KB blocks, and with
   the current layout blocks 28 and 30 hold patch text and tables, so old
   saves would put old patch data back into a newer version. Fix it before
   the first public release; the build warns until then.
2. Flips and ROM Patcher JS were not run here (no third-party downloads in
   this project). The patch uses only plain BPS: empty metadata, numbers of at
   most 4 bytes, TargetCopy that may overlap the bytes it writes (both tools
   copy byte by byte, as the specification requires). Check by hand before a
   release (release check 5).
3. The patched ROM's SHA-1 changes whenever the translation changes; a release
   must quote the SHA-1 of the build it ships.
4. Resolved in the integration pass: `bps_apply` with `max_target = 0` now
   uses a 256 MiB limit (`BPS_DEFAULT_MAX_TARGET`), so the "1 TiB target"
   vector is refused as an invalid header in every caller.

## Next steps

* "Save safety" workstream (STATUS.md): move the data out of
  `0x3B0000-0x3EFFFF` (issue 1) with the agreed layout and its build-time
  check (`tools/patch/layout.py`). The BPS step's save-area warning
  (`SAVE_AREA`, `save_area_changes` in `build.py`) then stops firing; it can
  be removed, or use `layout.py`'s `SAVE_START`/`SAVE_END`, once that check
  refuses such builds. Then rerun `release_test.py` and the repeated-save
  scenario in `player.md`.
* A packaging script (for example `tools/patch/package.py`) that builds the
  release zip from a clean build (contents and checks as in "Release
  package"; README with the checksums filled in) and refuses any file that
  looks like a ROM. The license is decided (MIT); the README text for the
  release still has to be written (`player.md` has the player steps).
* Manual check with Flips and ROM Patcher JS.
* Optionally put a version string in the patch metadata (kept empty for now).
