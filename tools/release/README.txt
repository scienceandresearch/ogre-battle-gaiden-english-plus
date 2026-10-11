Ogre Battle Gaiden: Prince of Zenobia, English Plus
===================================================

Version @VERSION@ (@DATE@)

An unofficial English fan translation of "Densetsu no Ogre Battle Gaiden:
Zenobia no Ouji" (Neo Geo Pocket Color, 2000), with a small Windows player
that runs it on a PC, a player's guide, and saved games that start you at
any chapter.

This download contains none of the game itself: no text, graphics, sound or
program code. The English patch and the player need your own copy of the
original Japanese game.


Quick start
-----------
You need your own copy of the original Japanese game: a .ngc file, or a .zip
that contains it (see "What you need" below).

To play on Windows:
  1. Extract this zip into a folder (right-click it, then "Extract All"),
     and open the ogre-battle-gaiden-english-plus-... folder inside.
  2. Double-click zenobia.exe. If Windows says "Windows protected your PC",
     click "More info", then "Run anyway".
  3. Choose your game file (the .ngc, or the .zip it came in). The game
     starts in English. Next time it opens by itself.
  4. New to the game? Help > Player's guide (or double-click "Player's
     Guide.html"). To start at a later chapter, use File > Import saved
     game and pick a file from the Chapter saves folder.

To get the English game file instead (for another emulator, a Mac, Linux, a
phone or a flash cart):
  1. Extract this zip, then double-click "Patch your game.html". It opens in
     your web browser.
  2. Click the box and choose your game file (a .zip works too).
  3. Click "Save the English game". The English file appears in your
     Downloads folder.
The page works offline and uploads nothing. On Windows, File > Save English
ROM in the player does the same.


Contents
--------
  zenobia.exe               the Windows player (64-bit Windows 10 or 11)
  Player's Guide.html       how to play, the chapters, secrets and cheats
                            (opens in your web browser)
  Chapter saves             saved games that start you at a chapter (see
                            "Chapter saves" below)
  Patch your game.html      makes the English game file in your web browser
  ogre_en.bps               the English patch (BPS format), for patching tools
  ogre_en.sha1              SHA-1 of the English ROM that the patch makes
  README.txt                this file
  LICENSE.txt               the license of this project (MIT)
  THIRD_PARTY_NOTICES.txt   the licenses of parts made by others
  patch-tools               a Python tool that applies the patch (optional)


What you need
-------------
Your own copy of this game, as a "ROM" file dumped from the original
cartridge:

  Densetsu no Ogre Battle Gaiden: Zenobia no Ouji (Japan)
  Neo Geo Pocket Color
  Size:   @ORIGINAL_SIZE@ bytes
  CRC32:  @ORIGINAL_CRC32@
  MD5:    @ORIGINAL_MD5@
  SHA-1:  @ORIGINAL_SHA1@

The file name and extension (.ngc, .ngp) do not matter, and a .zip that
contains the file works too. The patching tools refuse other dumps, other
revisions and files that were already patched; the player asks before it runs
such a file as it is. This project does not provide the game.


Playing with the included player
--------------------------------
1. Extract all files of the zip into a folder of your own, for example
   Documents\Zenobia. Do not start zenobia.exe from inside the zip. Windows
   would run it alone from a temporary folder without ogre_en.bps, and your
   saves would be lost. Avoid write-protected folders such as Program Files
   too, because the player keeps its settings, saves and save states next to
   itself.
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
  Neo Geo Pocket    Keyboard             Gamepad (Xbox-style, XInput)
  D-pad             arrow keys           D-pad or left stick
  A                 Z                    A or X
  B                 X                    B or Y
  Option            Enter or C           Start

  Player command                              Keyboard
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

The menu bar has the same commands and a few more. File: Open game, Save
English ROM, Import saved game, Continue where I left off, Exit. Options:
Console date, When the player starts. Cheats (see below). Help: Controls,
Player's guide, About. The menu bar is hidden in full screen. You can change
the keyboard keys in zenobia.ini (see below), except Ctrl+O, Ctrl+S, F1 and
Alt+Enter. The gamepad buttons are fixed.


Chapter saves
-------------
The Chapter saves folder holds saved games made at the start of each
chapter, and on both sides of a choice that changes the route, so you can
jump back to a point you remember. In each one the hero is named Tristan
and the game is in file 1. The guide lists them, with what comes next.

To use one, open your game in the player, choose File > Import saved
game..., and pick a file from the Chapter saves folder. The player copies
your own saved games to a backup file first (in the saves folder, named
"... (before import <date and time>).sav"), then restarts the game at the
title screen. Choose Load there, then file 1.

The saves come from a real play of the game. The only help used was that
battles ended quickly, so the army's levels may be a little lower than in
a careful play. They hold only the game's progress (the army, money and
chapters cleared), saved by the game itself.


Cheats
------
The Cheats menu changes the game being played:
  Add 100,000 goth                  money (the game's limit is 99,999,999)
  Heal every character              full HP for everyone still alive
  Level up after the next battle    each character gains a level after
                                    their next battle, as in normal play
  Reputation +10 / Reputation -10   the Chaos Frame, from 0 to 100
Use them on the map or in a menu, not during a battle. An in-game save
afterwards keeps the change.


Continue where you left off, and the console date
-------------------------------------------------
When you quit, the player remembers where you were. The next time it starts
with the same game, it asks whether to continue from there (File > Continue
where I left off does the same later). Options > When the player starts
changes the question to always continue or always start at the title
screen. This is separate from the game's own saves, which stay as they are.

The game checks the console's date for two secrets after the ending (see
the guide). Options > Console date sets the date the game sees: the PC's
date, 25 December or 6 June.


Saves, save states and settings
-------------------------------
The player keeps these files next to zenobia.exe:

  saves\<game file name>.sav
      The game's own saves (Save and Suspend in the game), written about
      2 seconds after the game saves and when you quit. The previous file
      is kept as .sav.bak.
  saves\<game file name> (before import <date and time>).sav
      Your saves as they were before File > Import saved game replaced them.
  states\slot0.state ... states\slot9.state
      Save states (F5 / F9): a snapshot of the whole machine. A state made
      with a different version of the game or the patch asks before it is
      loaded.
  states\resume.state
      Where you were when you last quit (Continue where I left off).
  zenobia.ini
      Settings. The player creates this file with the default values and a
      comment for each setting: window size ([video] scale, 1-12), full
      screen, whole-number zoom, volume ([audio] volume, 0-100), the keys
      ([input]), the last game file, pausing while the window is in the
      background, the console date and what happens when the player starts
      ([general]). Delete it to restore the defaults.

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

zenobia.exe is a windowed program, so a command prompt does not wait for it:
use "start /wait zenobia.exe ..." in the Windows command prompt, or add
"| Out-Null" in PowerShell.


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
  game file (extracted; Flips cannot open a .zip), then where to save the
  English ROM (for example ogre_en.ngc).
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
  - Every stage and ending has been checked, but a game this long can still
    hide untranslated or cut-off text. Please report any you find at
    https://github.com/scienceandresearch/ogre-battle-gaiden-english-plus/issues
    with a screenshot and where in the game it appears.
  - So far the English ROM has been tested only with this project's own
    player.
  - zenobia.exe is not signed, so SmartScreen asks before the first start.


License and credits
-------------------
This is a free, unofficial fan project, not connected with the owners of
Ogre Battle. Its code, translation, fonts and art are released under the
MIT License (LICENSE.txt). zenobia.exe also contains work by others under
their own licenses: the Z80 emulator by Nicolas Allemand (MIT) and
instruction timings derived from MAME by Wilbert Pol (BSD-3-Clause); see
THIRD_PARTY_NOTICES.txt.

Ogre Battle and the original game, its program, text, graphics and sound
are the property of their respective owners. This release contains none of
them: the patch holds only the new English text, code, fonts and art, and
takes everything else from your own copy of the game. The chapter saves
hold only saved progress. Please do not ask for or share ROM files, and do
not distribute patched ROMs: share this package instead.

Translation, player and tools: the ogre-battle-gaiden-english-plus
contributors. Thanks to the creators of the original game.
