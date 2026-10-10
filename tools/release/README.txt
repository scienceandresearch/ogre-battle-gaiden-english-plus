Ogre Battle Gaiden: Prince of Zenobia - English
===============================================

Version @VERSION@ (@DATE@)

An unofficial English fan translation of "Densetsu no Ogre Battle Gaiden:
Zenobia no Ouji" (Neo Geo Pocket Color, 2000), with a small Windows player
that runs it on a PC.

This download contains no game data. The English patch and the player need
your own copy of the original Japanese game.


Quick start
-----------
You need your own copy of the original Japanese game: a .ngc file, or a .zip
that contains it (see "What you need" below).

To play on Windows:
  1. Extract this zip into a folder (right-click it, then "Extract All").
  2. Double-click zenobia.exe. If Windows says "Windows protected your PC",
     click "More info", then "Run anyway".
  3. Choose your game file (the .ngc, or the .zip it came in). The game
     starts in English.

To get the English game file instead (for another emulator, a Mac, Linux, a
phone or a flash cart), either use File > Save English ROM in the player, or:
  1. Double-click "Patch your game.html". It opens in your web browser.
  2. Click the box and choose your game file (a .zip works too).
  3. Click "Save the English game". The English file appears in your
     Downloads folder.
Nothing is uploaded: the page works offline, on your own computer.


Contents
--------
  zenobia.exe               the Windows player (64-bit Windows 10 or 11)
  Patch your game.html      makes the English game file in your web browser
  ogre_en.bps               the English patch (BPS format), for patching tools
  ogre_en.sha1              SHA-1 of the English ROM that the patch makes
  README.txt                this file
  LICENSE.txt               the licence of this project (MIT)
  THIRD_PARTY_NOTICES.txt   the licences of parts made by others
  patch-tools               a Python tool that applies the patch (optional)


What you need
-------------
Your own copy of the original cartridge's data (a "ROM" file) of

  Densetsu no Ogre Battle Gaiden: Zenobia no Ouji (Japan)
  Neo Geo Pocket Color
  Size:   @ORIGINAL_SIZE@ bytes
  CRC32:  @ORIGINAL_CRC32@
  MD5:    @ORIGINAL_MD5@
  SHA-1:  @ORIGINAL_SHA1@

The file name and extension (.ngc, .ngp) do not matter, and a .zip that
contains the file works too. Other dumps, other revisions and files that
were patched already are refused. This project does not provide the game.


Playing with the included player
--------------------------------
1. Extract ALL files of the zip into a folder of your own, for example
   Documents\Zenobia. Do not start zenobia.exe from inside the zip: Windows
   would run it alone from a temporary folder, without ogre_en.bps, and your
   saves would be lost. Do not use a write-protected folder such as
   Program Files either: settings, saves and save states are stored next to
   the player.
2. Start zenobia.exe. The program is not signed, so Windows SmartScreen may
   say "Windows protected your PC": click "More info", then "Run anyway".
3. Choose your game file in the window that opens (or drop it onto the
   player's window). You don't need to unzip it: pick the .zip your game
   came in and the player finds the .ngc file inside. The game is
   translated in memory while it loads; your file is never changed. Next
   time the same file opens by itself (File > Open game, or Ctrl+O, opens
   another one).
4. Play. F1 (or Help > Controls) shows the controls.

To play the English version elsewhere (another emulator, a flash cart),
choose File > Save English ROM... (Ctrl+S) while your game is open. The
Save dialog opens in your game's folder with the name "Ogre Battle Gaiden -
Prince of Zenobia (English).ngc"; click Save. The player checks the file it
wrote and shows its checksums. Your original file is not changed.

If something is wrong, the player says what and how to fix it, for example:
  - "the English patch was not found": ogre_en.bps must be next to
    zenobia.exe (or next to your game file).
  - "the English patch could not be used ... damaged": download this
    release again.
  - "This file is not the ROM this player expects", with the reason (a bad
    or modified dump, another game, the wrong size, a copy that was patched
    already) and the checksums of the right file.
  - "Please extract the zip first": the .zip is password-protected or in a
    format the player cannot read. Right-click it in File Explorer, choose
    "Extract All...", and open the extracted .ngc file instead.
  - "This is a compressed archive": .7z, .rar and .gz files must be
    extracted first (a .zip opens directly).


Controls
--------
  Neo Geo Pocket    Keyboard             Gamepad (XInput)
  D-pad             arrow keys           D-pad or left stick
  A                 Z                    A or X
  B                 X                    B or Y
  Option            Enter or C           Start

  Player                                      Keyboard
  Fast forward (hold; about 5x, no sound)     Tab (gamepad: right trigger)
  Pause / resume                              P or Pause
  Save state / load state (current slot)      F5 / F9
  Previous / next state slot (0-9)            F6 / F7
  Full screen                                 F11 or Alt+Enter
  Reset (asks first)                          F12
  Open a game file (.ngc or .zip)             Ctrl+O
  Save the English ROM                        Ctrl+S
  Show the controls                           F1
  Quit (writes the game's save first)         Esc

The File and Help menus have the same commands; the menu bar is hidden in
full screen. The keys can be changed in zenobia.ini (see below).


Saves, save states and settings
-------------------------------
Everything is stored next to zenobia.exe:

  saves\<game file name>.sav
      The game's own saves (Save and Suspend in the game), written about
      2 seconds after the game saves and when you quit. The previous file
      is kept as .sav.bak.
  states\slot0.state ... states\slot9.state
      Save states (F5 / F9): a snapshot of the whole machine. A state made
      with a different version of the game or the patch asks before it is
      loaded.
  zenobia.ini
      Settings, created with commented defaults: window size ([video]
      scale, 1-12), full screen, whole-number zoom, volume ([audio] volume,
      0-100), the keys ([input]), the last game file, pausing while the
      window is in the background. Delete it to restore the defaults.

To move to another PC or to a new version of this release, copy the saves
and states folders (and zenobia.ini, if you changed it) into the new folder.
The game's saves carry over to new versions; save states may not.


Command line
------------
  zenobia.exe [GAME] [--patch FILE]     play; the patch is the ogre_en.bps
                                        next to zenobia.exe, else the one
                                        next to the game file
  zenobia.exe GAME --write-patched OUT  write the English ROM to OUT, for
                                        other emulators or flash carts
  zenobia.exe --help                    all options


Using the patch with other emulators
------------------------------------
The easiest way is "Patch your game.html" (see Quick start): it works in
any modern web browser on Windows, macOS and Linux, accepts the game as a
.ngc file or inside a .zip, checks that it is the right game, and saves
"Ogre Battle Gaiden - Prince of Zenobia (English).ngc".

ogre_en.bps is the same patch for patching tools. All of these tools check
the original first and refuse a different file; never force them to apply
the patch anyway.

Floating IPS (Flips), Windows and Linux:
  Start Flips, click "Apply Patch", choose ogre_en.bps, then your original
  game file, then where to save the English ROM (for example ogre_en.ngc).
  Command line: flips --apply ogre_en.bps "original.ngc" ogre_en.ngc
  Do not use its option to ignore checksums.

ROM Patcher JS (any web browser; the files stay on your computer):
  Choose your original game file as "ROM file" (a .zip works too), check
  that the CRC32 and SHA-1 it shows are the ones in "What you need", choose
  ogre_en.bps as "Patch file" and click "Apply patch". The browser saves the
  English ROM.

Python (Windows, Linux or macOS; Python 3.7 or newer, nothing to install),
in this folder:
  python patch-tools/apply.py "original.ngc"
  (python3 instead of python on Linux and macOS). This uses the ogre_en.bps
  of this folder and writes ogre_en.ngc next to the original (-o OUT.ngc
  chooses another name). It checks the original's SHA-1 before patching and
  the result afterwards.

The player: File > Save English ROM... (Ctrl+S), or from a command line
  zenobia.exe "original.ngc" --write-patched ogre_en.ngc
  (the original may also be the .zip it came in).

Check the result (optional): the English ROM has SHA-1
@ENGLISH_SHA1@ (the contents of ogre_en.sha1) and
CRC32 @ENGLISH_CRC32@. For example:
  certutil -hashfile ogre_en.ngc SHA1          (Windows command prompt)
  Get-FileHash ogre_en.ngc -Algorithm SHA1     (PowerShell)
  sha1sum ogre_en.ngc                          (Linux)
  shasum ogre_en.ngc                           (macOS)

Then open the English ROM in a Neo Geo Pocket Color emulator. For the
game's own saves the emulator must support Neo Geo Pocket cartridge saves.
The player's .sav files are in its own format and do not work in other
emulators.


Known issues
------------
  - Where the game has room for only 8 or 10 letters (item, class and
    character names in some lists and status fields), long names are
    shortened; the full names appear in shops, messages and confirmations.
  - The later stages and the endings have been played less than the first
    stages. Please report untranslated or cut-off text.
  - So far the English ROM has been tested only with this project's own
    player.
  - zenobia.exe is not signed, so SmartScreen asks before the first start.


Licence and credits
-------------------
This is a free, unofficial fan project, not connected with the owners of
Ogre Battle. Its code, translation, fonts and art are released under the
MIT License (LICENSE.txt). zenobia.exe also contains work by others under
their own licences: the Z80 emulator by Nicolas Allemand (MIT) and
instruction timings derived from MAME by Wilbert Pol (BSD-3-Clause); see
THIRD_PARTY_NOTICES.txt.

Ogre Battle and the original game, its program, text, graphics and sound
are the property of their respective owners. This release contains none of
them: the patch holds only the new English text, code, fonts and art, and
takes everything else from your own copy of the game. Please do not ask for
or share ROM files, and do not distribute patched ROMs: share this package
instead.

Translation, player and tools: the open-ogre-battle-gaiden-zenobia
contributors. Thanks to the creators of the original game.
