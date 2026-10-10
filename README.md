# Ogre Battle Gaiden: Prince of Zenobia — English

An English version of *Densetsu no Ogre Battle Gaiden: Zenobia no Ouji*
(Neo Geo Pocket Color, 2000) that you can play on a PC.

This project contains **no game data**. It is a translation patch plus a small
player, and both need your own copy of the original Japanese game
(`.ngc` file, SHA-1 `5ac794c0f125bfb97efe9cd06c2aca3afdf549ea`).

> Status: complete development build (version 0.1.0-dev): every text and every
> pre-drawn graphic is in English, verified in play. A public release still
> needs a few manual checks. See [STATUS.md](STATUS.md) for details.

## Playing

Download the latest zip from the **Releases** page (on the right of the
repository page). You also need your own copy of the original Japanese game:
a `.ngc` file, or a `.zip` that contains it.

**Play on Windows (easiest):**
1. Extract the downloaded zip into a folder (right-click it, *Extract All*).
2. Double-click `zenobia.exe`. If Windows says *"Windows protected your PC"*,
   click *More info*, then *Run anyway* (the program is not signed).
3. Choose your game file: the `.ngc`, or the `.zip` it came in (no need to
   unzip it). The game starts in English.

**Get the English game file** (for another emulator, a Mac, Linux, a phone or
a flash cart): in the player choose *File > Save English ROM...* (Ctrl+S), or,
on any system:
1. Double-click `Patch your game.html` from the zip. It opens in your browser.
2. Click the box and choose your game file (a `.zip` works too).
3. Click *Save the English game*. The file appears in your Downloads folder.

Nothing is uploaded: the page works offline. Your original file is never
changed by either method.

### More about the Windows player

The player applies the English patch in memory each time and remembers the
last game file. The game's own saves (Save and Suspend) go to `saves\` next to
the player, save states to `states\`, settings to `zenobia.ini` (created with
commented defaults; delete it to restore them).

Default controls (changeable in `zenobia.ini`):

| Neo Geo Pocket | Keyboard | Gamepad (XInput) |
|---|---|---|
| D-pad | Arrow keys | D-pad / left stick |
| A | Z | A (or X) |
| B | X | B (or Y) |
| Option | Enter (or C) | Start |

| Player | Keyboard | Gamepad |
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

The File and Help menus have the same commands (the menu bar is hidden in
full screen). From a command line, `zenobia.exe GAME.ngc --write-patched
ogre_en.ngc` writes the English ROM (the game may be a `.zip`);
`zenobia.exe --help` lists the other options.

### With another emulator

The easiest way is `Patch your game.html` (above). `ogre_en.bps` is the same
patch for any BPS patching tool (for example Floating IPS, or ROM Patcher JS
in a web browser); or, with Python:

```
python patch-tools/apply.py your_game.ngc        # in the extracted release folder
python -m tools.patch.apply your_game.ngc build/ogre_en.bps -o ogre_en.ngc   # in this repository
```

Then open the patched file in a Neo Geo Pocket Color emulator.

## Building from source

Requirements: Windows with Visual Studio 2022 (C++ build tools, which include
CMake and Ninja) and Python 3.

```
build.bat                                     # emulator core, test harness, player
python -m tools.patch.build rom/baserom.ngc   # English ROM and patch (needs your game file)
```

Put your original game file at `rom/baserom.ngc` first. Outputs go to `build/`
(`ogre_en.ngc`, `ogre_en.bps`, `zenobia.exe`, `ngp_harness.exe`).

```
python -m tools.release.package      # dist/ogre-battle-gaiden-en-<version>-win64.zip
```

builds the download package (player, patch, README, licences, and a
pure-Python patch tool) after checking that it carries no data from the game.

## Translation

The English text lives in `translation/en/` (dialogue, menus, names, places).
`docs/localization.md` explains the localization database: an export of every
Japanese string next to its translation for review, and the import of a
reviewer's suggestions. Technical notes on the game are in
`docs/engine-notes.md`.

## License and legal

This is a free, unofficial, non-commercial fan project. It is not affiliated
with, endorsed or sponsored by the owners of the game or of the Ogre Battle
series. Its code, translation, fonts and art are released under the
[MIT License](LICENSE) (the English variable-width font in `assets/font/` is
additionally dedicated to the public domain, CC0). Third-party components and
their licenses are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

**Bring your own game.** The project distributes no copyrighted game data: no
ROM, no BIOS, no graphics, text or sound from the game. The repository holds
only original code, an original English translation, original fonts and
original English lettering; the patch (`ogre_en.bps`) holds only the changes,
and the build audits it to contain no data from the game (every literal run is
checked against the original). You need your own copy of the original
cartridge, dumped by yourself. This project does not provide ROM files or tell
you where to find them; please do not ask for them or share patched ROMs.

The replacement graphics (menu labels, intro text, chapter cards, title logo,
status tags) are new lettering drawn by this project with its own fonts, placed
where the Japanese lettering was and using the game's own colours at run time;
no original artwork is copied into this repository or the patch.

Ogre Battle, Densetsu no Ogre Battle Gaiden and related names and logos are
trademarks of their respective owners, used here only to identify the game
this translation is for. If you are a rights holder and have a concern, please
open an issue and it will be addressed promptly.
