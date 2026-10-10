# Ogre Battle Gaiden: Prince of Zenobia (English)

An English fan translation of *Densetsu no Ogre Battle Gaiden: Zenobia no Ouji*
(Neo Geo Pocket Color, 2000), with a small Windows player so you can play it on
a PC.

This project contains no game data. To play, you need your own copy of the
original Japanese game as a ROM file, which is the game's data copied from the
cartridge. That is a `.ngc` file (SHA-1
`5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`) or the `.zip` it came in. The
player and the patch page check the file for you.

Version 0.1.0-dev is a complete development build. All of the game's text and
pre-drawn graphics are in English, and every stage and ending has been checked
in play. Before a public release it still needs a few manual checks with other
emulators and patching tools. [STATUS.md](STATUS.md) has the details.

## How to play

Open the newest release on the
[Releases page](https://github.com/scienceandresearch/open-ogre-battle-gaiden-zenobia/releases)
and download the file whose name ends in `-win64.zip` (not the "Source code"
files). On the repository's main page, the Releases link is in the right-hand
column.

### On Windows

1. Extract the zip into a folder of its own (right-click it, then choose
   *Extract All*), and open the `ogre-battle-gaiden-en-...` folder inside.
2. Double-click `zenobia.exe`. The program is not signed, so Windows may show
   "Windows protected your PC". Click *More info*, then *Run anyway*.
3. Choose your game file. It can be the `.ngc` file or the `.zip` it came in.
   The game starts in English.

### On a Mac, Linux, a phone, a flash cart or another emulator

Make an English game file on your computer:

1. Extract the zip (on a Mac, double-click it) and open the
   `ogre-battle-gaiden-en-...` folder inside. Double-click
   `Patch your game.html`. It opens in your web browser.
2. Click the box and choose your game file (a `.zip` works too).
3. Click *Save the English game*. Your browser saves the file like any other
   download, usually in your Downloads folder.

Open that file in a Neo Geo Pocket Color emulator, or copy it to a flash
cart. So far the English file has been tested only with this project's own
player. The page works offline and uploads nothing. On Windows the player can
make the same file: choose *File > Save English ROM...* (Ctrl+S). Neither way
changes your original file.

## Have an AI agent do it for you

If you use an AI agent that can work with files on your computer, such as
Claude Code or Codex, you can paste the text below into it. Replace the part
in angle brackets on the "My game file" line with the location of your game
file, or leave it as it is and the agent will ask you for it.

```text
Set up the English fan translation of the Neo Geo Pocket Color game
"Densetsu no Ogre Battle Gaiden: Zenobia no Ouji" for me.

My game file: <full path to my .ngc file, or the .zip it came in>
Download page: https://github.com/scienceandresearch/open-ogre-battle-gaiden-zenobia/releases

Rules:
- Use only my own game file. If I did not say where it is, ask me.
- Never download, search for or share the game (the ROM) or a patched copy,
  even if my file is missing or does not match.
- Do not change, move or delete my original game file.
- Download only from the download page above.
- Ask me before installing anything.

Steps:
1. From the newest release on the download page (a pre-release counts),
   download the file whose name ends in -win64.zip and extract it into a new
   folder. The files are in the ogre-battle-gaiden-en-... folder inside it;
   work there. If the page asks for a GitHub sign-in, ask me to download the
   zip and tell you where it is.
2. Check my game file. The original is 2,097,152 bytes with SHA-1
   5ac794c0f125bfb97efe9cd06c2aca3afdf549ea. If it is a .zip, check the .ngc
   file inside. If the SHA-1 is different, stop and tell me, because the
   patch only works with this exact file.
3. In that folder, make the English game file with Python 3.7 or
   newer (no extra packages needed; use python3 on macOS and Linux):
     python patch-tools/apply.py "<my game file>" -o "<folder of my game file>/Ogre Battle Gaiden - Prince of Zenobia (English).ngc"
   On Windows without Python, this does the same (zenobia.exe is a windowed
   program, so in PowerShell use Start-Process -Wait, or add | Out-Null, to
   wait until it has finished):
     zenobia.exe "<my game file>" --write-patched "<same output path>"
   Then check that the new file's SHA-1 matches the one in ogre_en.sha1.
4. Tell me where the English file is. It is meant for Neo Geo Pocket Color
   emulators and flash carts (so far it has been tested only with the
   project's own player). On Windows I can also double-click zenobia.exe in
   that folder and choose my original game file; the player translates the
   game as it loads, and F1 shows the controls.
```

To have an agent build the project from source instead, point it to
[Building from source](#building-from-source) and
[CONTRIBUTING.md](CONTRIBUTING.md).

## The Windows player

The player applies the English patch in memory every time it loads the game,
so your game file is never changed. It reopens the last game file you used.
It keeps its files next to `zenobia.exe`: the game's own saves (Save and
Suspend in the game) in `saves\`, save states in `states\`, and settings in
`zenobia.ini`. The player creates the settings file with the default values
and a comment for each setting; delete it to restore the defaults.

These are the default controls. You can change the keyboard keys in
`zenobia.ini`, except Ctrl+O, Ctrl+S, F1 and Alt+Enter; the gamepad buttons
are fixed.

| Neo Geo Pocket | Keyboard | Gamepad (Xbox-style, XInput) |
|---|---|---|
| D-pad | Arrow keys | D-pad / left stick |
| A | Z | A (or X) |
| B | X | B (or Y) |
| Option | Enter (or C) | Start |

| Player command | Keyboard | Gamepad |
|---|---|---|
| Fast forward (hold) | Tab | Right trigger |
| Pause / resume | P or Pause | |
| Save / load state | F5 / F9 | |
| Previous / next state slot (0-9) | F6 / F7 | |
| Full screen | F11 or Alt+Enter | |
| Reset (asks first) | F12 | |
| Open a game file (.ngc or .zip) | Ctrl+O | |
| Save the English ROM | Ctrl+S | |
| Show the controls | F1 | |
| Quit (writes the game save first) | Esc | |

The File menu has Open game, Save English ROM and Exit, and the Help menu
has Controls and About. The menu bar is hidden in full screen. From a command
line, `zenobia.exe GAME.ngc --write-patched ogre_en.ngc` writes the English
ROM (the game can also be a `.zip`), and `zenobia.exe --help` lists the other
options. The player is a windowed program, so a command prompt does not wait
for it: use `start /wait zenobia.exe ...` in cmd, or add `| Out-Null` in
PowerShell.

## Other patching tools

`Patch your game.html` is the easiest way to make the English file. The
release also has the patch as `ogre_en.bps`, for BPS patching tools such as
Floating IPS or ROM Patcher JS in a web browser (not yet tested with them).
With Python:

```
python patch-tools/apply.py your_game.ngc        # in the extracted release folder
python -m tools.patch.apply your_game.ngc build/ogre_en.bps -o ogre_en.ngc   # in this repository
```

Both check your file before patching and check the result afterwards.

## Building from source

You need Windows with Visual Studio 2022 (its C++ build tools include CMake
and Ninja) and Python 3. Put your original game file at `rom/baserom.ngc`
first. The `rom/` and `build/` folders are git-ignored, so nothing from the
game ends up in a commit.

```
build.bat                                     # emulator core, test harness, player
python -m tools.patch.build rom/baserom.ngc   # English ROM and patch (needs your game file)
```

The results go to `build/`: `ogre_en.ngc`, `ogre_en.bps`, `zenobia.exe` and
`ngp_harness.exe`. To make the download package:

```
python -m tools.release.package      # dist/ogre-battle-gaiden-en-<version>-win64.zip
```

The package holds the player, the patch, the web patcher page, a README, the
licenses and a pure-Python patch tool. Before writing it, the script checks
that none of these files carries data from the game.
[CONTRIBUTING.md](CONTRIBUTING.md) lists the tests and the rules for changes.

## What is in this repository

| Path | Contents |
|---|---|
| `translation/en/` | The English text: dialogue, menus, names, places, and the wording of the redrawn graphics |
| `patch/` | Assembly code the patch adds to the game (variable-width text, text hooks) |
| `assets/` | The project's own fonts, title lettering and icon, stored as text files |
| `tools/` | Python tools: patch build, text and graphics pipelines, assembler and disassembler, release packaging |
| `runtime/` | C sources of the emulator core, the Windows player and the headless test harness |
| `third_party/` | The Z80 sound CPU emulator (MIT License, unmodified) |
| `docs/` | Technical notes, the localization workflow, testing and the development history |
| [STATUS.md](STATUS.md) | Where the project stands and what is left |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to report problems and send changes |

## Helping with the translation

The English text is in `translation/en/`. [docs/localization.md](docs/localization.md)
explains how to export every string with its Japanese original into a
spreadsheet for review, and how to bring a reviewer's suggestions back in.
[docs/engine-notes.md](docs/engine-notes.md) describes how the game works
inside. If you find untranslated or cut-off text, please open an issue with a
screenshot and say where in the game it appears.

## License and legal

This is a free, unofficial, non-commercial fan project. It is not affiliated
with, endorsed by or sponsored by the owners of the game or of the Ogre Battle
series. Its code, translation, fonts and art are released under the
[MIT License](LICENSE). The English variable-width font in `assets/font/` is
also dedicated to the public domain (CC0).
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) lists the third-party
components and their licenses.

### Bring your own game

The project distributes no copyrighted game data: no ROM, no BIOS, and no
graphics, text or sound from the game. The repository holds only original
code, an original English translation, original fonts and original English
lettering. The patch (`ogre_en.bps`) holds only the changes, and the build
checks every literal run in it against the original game to make sure it
contains no game data. You need your own copy of the original cartridge,
dumped by yourself. This project does not provide ROM files or say where to
find them. Please do not ask for them, and do not share patched ROMs.

The replacement graphics (menu labels, intro text, chapter cards, title logo
and status tags) are new lettering drawn by this project with its own fonts.
The patch puts them where the Japanese lettering was, and they use the color
palettes that come from your copy of the game. No original artwork is copied
into this repository or the patch.

Ogre Battle, Densetsu no Ogre Battle Gaiden and related names and logos are
trademarks of their respective owners. They are used here only to identify
the game this translation is for. If you are a rights holder and have a
concern, please open an issue and it will be addressed promptly.
