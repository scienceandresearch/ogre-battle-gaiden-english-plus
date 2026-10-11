# Sources of the player's guide

Every factual claim in the player's guide (`tools/release/guide.html`,
packaged as "Player's Guide.html"), grouped by the guide's sections, with
its source. Claims that are only partly backed are marked; things left out
of the guide for lack of proof are listed at the end. When the guide
changes, update the matching row here.

The checks were made in October 2026 while the guide was written. The
scratch helpers named below (`sdis.py`, `flow.py`, `classes.py`,
`stagemap.py`, `churchcount.py`, `allhandlers.py`, `neutrals.py`, `tmap.py`),
the decoded handler listing (`handlers.txt`) and the experiments' logs,
screenshots and states were work files and are not in the repository; each
row gives the addresses, states, pokes and inputs needed to repeat the check
with the harness (`docs/testing.md`).

## How to read the sources

* **Doc**: a project file and section, for example `explore2-systems.md`
  "Class change" (all workstream docs are in `docs/workstreams/`).
* **Tr**: our translation, `file:line` in `translation/en/` (working copy of
  2026-10-10).
* **ROM**: an address in the English ROM used for every check here,
  `build/ogre_en.ngc` (SHA-1 `d5234b95d12096c722c324d23e5e4fb227179eff`,
  the build in STATUS.md), and what the code or data there does. Script
  bytecode was decoded with `tools/text/script.py` through two scratch
  helpers (`sdis.py`, `flow.py`); native code with
  `python -B -m tools.recomp.disasm`; data tables with scratch scripts
  (`classes.py`, `stagemap.py`, `churchcount.py`); the decoded listing of
  every location handler of stages 0-19 is called `handlers.txt` below.
  Script opcodes used below: `bflag n` (branch if story flag n is set),
  `bflag2 k` (branch if stage k is cleared), `bcmp b` (branch if Chaos Frame
  is below b), `b3e w` (branch if character w is not in the current unit),
  `b40 w` (branch if w is not in the army), `b42 i` (branch if item i is not
  owned), `op44 i` (remove item i), `op46 b` (Chaos Frame += signed b, clamped
  0-100, handler `0x20D3FE`), `op48 l` (funds += signed l, clamped 0 to
  99,999,999, handler `0x20D3E4`), `op4a b` (hero's ALI += signed b, clamped
  0-100, handler `0x20D412`), `st16 01xx, 458E` + `pcall 2073DC` (give item
  xx), `0x20D288` (number of free places in the army: 100 minus characters
  plus empty records), `0x20CEEF` / `0x20CCBE` (add a character; A = class
  byte), `0x20D356` (remove a character by name index).
* **Exp**: an experiment with the harness (`ngp_harness.exe` of the same
  build), a test state from `build/states/` (machine-local), RAM pokes
  (`--poke ADDR=HEX`), inputs, and the result.
* **Code (player)**: the player's source in `runtime/src/`.
* **Earlier check**: facts checked before the guide was written and given
  to its writer: the player's menus, options and messages (which the code
  rows show too) and the game's single clock read (RTCGET at `0x204EF2`).

Name indexes used in scripts (from `tables/names.txt`): 0x672 Kain, 0x677
Lord, 0x678 Deneb, 0x679 Lanselot, 0x67A Warren, 0x67B Gilbert, 0x67C
Canopus, 0x67F Ares, 0x681 Estrada, 0x682 Aquarius, 0x683 Birkin, 0x684 Nana,
0x685 Goldie, 0x686 Orosov, 0x687 Grant, 0x68A Yorkleif.

Stage index = chapter number - 1 (stage 12 = Final Chapter; stages 13-16 =
side areas; 17-19 = Free Battle Areas): `explore-progress.md` "Later stages"
and `cards.txt`. `0x5490` holds stage index + 1: Exp (states
`r2-story-late-s9_gameplay` = 10, `r2-story-late-s12_gameplay` = 13,
`stage0_gameplay` = 1).

---

## Intro

| Claim | Source |
|---|---|
| The original manual was in Japanese only. | Earlier check. |

## 1. Getting started with the player

### Opening your game

| Claim | Source |
|---|---|
| Keep `zenobia.exe` and `ogre_en.bps` together; settings, saves and states are stored next to the program; avoid write-protected folders like Program Files. | `player.md` "Steps for the player" 1 and "Files the player creates". |
| File > Open game (Ctrl+O), or drop the file onto the window; `.ngc` or the `.zip` it came in. | `player.md` "Run" and "Steps for the player" 3; Earlier check (menus); Code (player) `gui.c` `k_help`. |
| The game is translated in memory while it loads; your file is never changed; next time the same game opens by itself. | `player.md` "Steps for the player" 3 and "Run". |
| File > Save English ROM (Ctrl+S) writes a separate English `.ngc` and checks it after writing. | `player.md` "Run" (read-back check of SHA-1 and CRC32). |

### Controls

| Claim | Source |
|---|---|
| Key and gamepad table (arrows/D-pad or left stick; Z = A, A or X; X = B, B or Y; Enter or C = Option, Start; Tab / right trigger fast-forward; P or Pause; F5/F9; F6/F7 slots 0-9; F11 or Alt+Enter; F12 reset; Ctrl+O; Ctrl+S; F1; Esc). | Earlier check; Code (player) `gui.c` `k_help` (lines 87-105); `player.md` "Controls". |
| Reset asks first; Esc writes the game's save first. | `player.md` "Controls" table ("Reset (asks first)", "Quit, writing the cartridge save first"); `k_help` ("Esc: quit (the cartridge save is written first)"). |
| Fast-forward is about 5x and muted. | `player.md` "Controls" ("Fast-forward (hold, about 5x, muted)"). |
| Keyboard keys can be changed in `zenobia.ini` except Ctrl+O, Ctrl+S, F1 and Alt+Enter. | `player.md` "Controls"; Code (player) `gui.c` (Alt+Enter is handled as `WM_SYSKEYDOWN` with `VK_RETURN`, not through the key table; the ini's `fullscreen=` key is F11). |
| In the game, A confirms, B goes back; Option pauses the map and shows help for the icon under the cursor. | `docs/testing.md` "The test harness" ("B backs out, Option shows command help"); Tr `script.txt:146-149` (Game System Tips 1: Option stops time); `explore2-systems.md` "Monitor, Option help". |

### The menu bar

| Claim | Source |
|---|---|
| Menus File / Options / Cheats / Help and their items. | Earlier check; Code (player) `gui.c` `create_menu` (lines 975-1018) and `k_cheat_labels`. |
| Mouse only; Alt and F10 do not take keys; hidden in fullscreen. | `player.md` "Run" ("mouse only: Alt and F10 do not open it ... hidden in fullscreen"). |
| Help > Player's guide opens this page. | Code (player) `gui.c` `open_guide` (`GUIDE_FILE` = "Player's Guide.html" next to `zenobia.exe`). |

### Saving

| Claim | Source |
|---|---|
| Scenario map, B, Data, Save; three save files; Load on the title screen. | `docs/testing.md` "In the game, ... B toggles a popup with Organize, Monitor, Data and Link. Data opens Save and Load"; `explore-data.md` "Done" (file list with 3 slots); Tr `ui.txt:2198-2210` (Data submenu). |
| The player writes `saves\<game file name>.sav` about 2 s after the game saves and on exit; previous file kept as `.bak`. | `player.md` "Files the player creates". |
| No Data during a chapter; Suspend saves the game in progress; resume with Continue on the title screen; the suspend data is erased once you resume. | Command bar contents: Exp `cmdbar4` (NEXT, Organize, Items, Tarot cards, Finances, Monitor, Suspend; no save command); Tr `ui.txt:373-374` (Suspend prompt), `ui.txt:223-228` (both notes), `ui.txt:2011-2012` (Suspend help). |
| After suspending the game stays on its last message; F12 or quit. | Exp `susp1`: `data-cmdbar_suspend` + `10:A:2;80:A:2;300:A:2;450:A:2;600:A:2`: both notes shown, "flash: 8960 bytes programmed", the screen stays on the second note to frame 900 despite further A presses. `explore-data.md` saw the same (game "stays on the second one"). |
| F5/F9 at any time; ten slots; F6/F7; title bar shows the slot; `states` folder; a state from another version asks first because it may not work. | `player.md` "Controls" and "Files the player creates"; Code (player) `gui.c` `update_title` ("Slot %d"), `load_state_slot` ("Loading it may crash the game"). |
| Continue where you left off: saved when you quit, asked at the next start, Options > When the player starts, File > Continue where I left off. Default is "ask". | Code (player) `gui.c` `save_resume_state`, `load_resume_state`, `offer_resume`; `config.c:79,232` (`resume=ask`). |
| A save state records the whole machine and may not load correctly with another version; a game save holds only the game's record of army, money and progress. | `docs/testing.md` "Test states" (a state keeps memory of its build and can crash after a rebuild); `release.md` "Chapter saves and the player's guide" ("A save holds only the game's own record of the army, money and progress"). |

## 2. How the game works

### Starting a new game

| Claim | Source |
|---|---|
| Title: NewGame, Load, Continue; Load and Continue only with saved or suspended data; NewGame asks which of three files. | `explore-data.md` "Done" (title menu; "Choose where to save." and the file list). |
| Warren, an astrologer; name the hero (up to 8 letters, default Tristan); six questions; draw a single card. | Tr `script.txt:14-36` (Warren's lines), `ui.txt:181-183` (default name Tristan, 8 characters); `explore-data.md` (name entry asks after the 8th letter; six questions asked depending on timing). |
| The reading decides the hero's starting stats. | Exp/state comparison: `data-scenario_map_new` (opening run with A every 40 frames from 20) has the hero as class 98 with STR..LUK 45/47/40/46/50/45; `hq_status_screen` (power-on run with another input timing) has class 101 with 50/49/42/53/53/47. Both are on the scenario map right after the reading. The class shows as "Fighter" in both (classes 98-102 are all "Fighter", `tables/classes.txt:102-106`). Which part of the reading (questions, answers or card) does it was not isolated. |
| The reading also decides some of the volunteers who join at the start of chapter 2. | ROM `0x264BFF`-`0x264C1E` (chapter 2 opening): two fixed `0x20CCBE` character templates, then `XIZ += (hero class byte - 0xE2) * 0x3F` selects one of five template blocks for three more characters. The hero's class variant (98-102) is the result of the reading (row above). |
| Seven Game System Tips in chapters 1 and 2. | Tr `script.txt` lines 140 (Tips 1), 376 (2), 311 (3), 236 (4), 430 (5), 589 (6), 532 (7); all in the stage 0 and stage 1 sections. |
| The scenario map is titled "The Zenobian Age". | `explore2-story-late.md` ("scenario map 'The Zenobian Age'"); `docs/testing.md` "Useful states". |

### The scenario map and the chapters

| Claim | Source |
|---|---|
| A on an area's marker starts it; title card and opening scenes. | `explore-progress.md` "Controls and RAM facts learned" and state table (`progress-scenario_cursor_on_stage1`: "A starts stage 1", card then opening). |
| B opens the popup Organize, Monitor, Data, Link. | `docs/testing.md`; Exp `scen1` (screenshot of the popup). |
| Monitor: battle animation, music, sound effects on/off; message speed and game speed in three steps; also on the command bar. | Tr `ui.txt:2629-2650` (Monitor help texts); Exp `mon1` (screenshot: three ON/OFF rows and two rows with 1/2/3); Exp `mon3` (`stage0_gameplay`, `10:A:2;60:A:2;110:R:2;150:R:2;190:R:2;230:R:2;270:R:2;320:A:2`: the command bar's Monitor icon opens the same window); Tr `labels.txt` @04. |
| Link: the player behaves as if no cable is connected. | Code `runtime/src/core/bios.c:245` ("Link cable: behave as if no cable is connected."); `explore2-systems.md` "Link battle (one player)" (every icon ends with "Please try again."). |
| Chapter table (area names and title cards). | Tr `cards.txt` (story 1-20, area 1-20); `ui.txt:2233-2355` (scenario labels); stage order from `explore-progress.md` "Later stages". |
| Chapters 8/9 and 11/12 are alternatives. | See section 4 (Routes). |

### Real time, pausing, day and night

| Claim | Source |
|---|---|
| Real time; Option stops and restarts time. | Tr `script.txt:143-149` (Tips 1). |
| Time also stops while a menu, window or the flag cursor is open, and during battles. | `explore-map.md` "Game time" (paused while a menu, window or the flag cursor is open); `explore-progress.md` "Game clock ... stops while any message, menu or battle is open". |
| A day lasts about 7 minutes at game speed 1, a little under 5 at speed 2 (new-game setting), about 2.5 at speed 3. | Clock at `0x6080` (`explore-map.md` "Game time": byte 0 counts 179..0 per game hour, byte 1 the hours). Exp `clk0`: `stage0_gameplay` (Monitor shows game speed 2, Exp `mon3`), no input, 1440 frames: hours 0x10 -> 0x0E, tick unchanged = 720 frames per hour, 17,280 per day. Exp `spd3a`/`spd3b`: same state, Monitor game speed set to 3 (`...;400:D:2;440:D:2;480:D:2;520:D:2;560:R:2;620:B:2;680:B:2;740:B:2`, screenshot shows 3 selected), then 1440 frames: hours 0x0F -> 0x0B = 360 frames per hour. Exp `spd1a`/`spd1b`: speed 1 (`560:L:2`), 2880 frames: (hour 16, tick 3) -> (hour 13, tick 63) = 480 ticks = 1080 frames per hour. At the player's 59.95 Hz (`player.md`): 25,920 / 17,280 / 8,640 frames = about 432 s / 288 s / 144 s. New-game setting 2: `data-popup_monitor` (Exp `mon1`) and `stage0_gameplay` both show speed 2. |
| Each new day the Income & Expenses window appears. | `explore-map.md` "New day". |
| Map colors change through the day. | `explore-map.md` "Game time" ("The map palette changes through the day"). |
| Some events happen only by day or at night. | ROM checks of `0x6088` (0 = day): Parna `0x26675F`, Gawafur `0x26BB90`, Shilda `0x26BCDC`, Estable `0x272142`, Urtomo `0x270B67`, date check `0x204EDF`. |
| Scent of Night / Light's Whisper make it night / day at once. | Tr `tables/items.txt:214-215` (descriptions 16, 17). |

### Units and leaders

| Claim | Source |
|---|---|
| Up to five characters per unit; a large character takes two places. | Tr `ui.txt:308-311` ("The unit is full. 5 members at most; large ones take 2."). |
| Up to 100 characters. | ROM `0x20D288`: free places = 100 (`ld.w WA, 0x64`) minus the character count plus empty records. |
| Up to 25 units. | ROM `0x20D370`-`0x20D399` (loops over 25 unit records of 12 bytes from `0x517E`; the next variable starts at `0x52AA` = `0x517E` + 25 x 12); `explore-organize.md` "Screen map" item 4 (Swap units lists "2." to "25."); Tr `ui.txt:330-332` ("You cannot have any more units."). |
| Characters in no unit wait in the stock. | `explore-organize.md` "Screen map" items 2-3 ("characters in the stock (in no unit)"). |
| The first character of a unit is its leader. | ROM `0x2033E5` (game-over check reads the first member of unit 1); Exp/state `stage0_gameplay` unit 1 = [Estrada, Kain, hero], `progress-stage1_gameplay` unit 1 = [hero, ...]. |
| Leader: OK / No on the status screen. | `explore-organize.md` "Screen map" (status pane ends with "Leader: OK/No"); Tr `ui.txt:2158-2159`; Tr `ui.txt:317-319` ("This character can't lead a unit."). |
| The first unit's leader is Estrada in chapter 1 and the hero from chapter 2; it cannot be changed. | Unit tables of `stage0_gameplay` and `progress-stage1_gameplay` (above); Tr `ui.txt:342-344` ("This unit's leader cannot be changed."); `explore-organize.md` item 6 ("Unit 1 (story leader) answers ..."). |
| Front and back rows; one attack per row; F: and B: show attack and count. | `explore2-battle.md` "Attack names" (class table: front id, front count, back id, back count; row from position); Exp `cc1` screenshot (status pane "F:Slash 2", "B:Slash 1"). |
| Organize screen commands. | `explore-organize.md` "Screen map"; Tr `labels.txt` (labels 02, 08, 09, 0A, 0B, 0C, 0D, 17, 1F, 01). |
| During a chapter, deployed units cannot be changed there; the unit window's Organize offers Formation, Dismiss, Class change, and Change leader when the leader is not a story character. | `explore-organize.md` "Screen map" ("deployed units cannot be changed (A does nothing, no message)"; "Organize submenu: Formation / Dismiss / (Leader change, only when the leader is not a story character) / Class change"). |
| Story characters cannot be dismissed. | `explore-organize.md` "Screen map" (Dismiss: "story characters (class byte bit 7 set) 'cannot be dismissed'"); Tr `ui.txt:204-206`. |

### Headquarters and deploying units

| Claim | Source |
|---|---|
| Single unit in chapter 1. | State `stage0_gameplay` (units = 1). |
| Deploy unit from chapter 2; costs goth; price asked first. | Tr `script.txt:430-433` (Tips 5, chapter 2), `ui.txt:525-526` ("Deploying costs N goth. Is that OK?"); `explore-map.md` "Deploy (stage 1+)". |
| Any unit except the first is asked about recall when it ends its move on the HQ. | `explore-map.md` "Recall to HQ" (`0x20833B`); Tr `ui.txt:486-490`. |
| Return Half sends a unit back to HQ. | Tr `tables/items.txt:207` (item 9 description). |

### Moving units

| Claim | Source |
|---|---|
| A on a unit or the HQ: small menu with NEXT, units, place; unit window commands. | `explore-map.md` "Moving a unit"; `explore-towns.md` "Navigation notes"; Tr `labels.txt` (0E Move, 10 Tactics, 12 Recruit, 13 Buy items, 14 Rite of revival, 07 Organize). |
| Recruit in towns from chapter 2 (one exception, see Recruiting); Buy items only in the shop town; Rite of revival only in churches with a fallen member. | ROM unit-window builder `0x204E66`-`0x204F9E`: churches (location index at or past the record count) set the revival bit 4 only if a member has HP 0 (`0x204E86`-`0x204EA9`); towns (`0x204F2A`) skip recruiting when `0x5490` = 1 (stage 0) and need free army places; the shop bit 3 needs the record's shop byte (`0x204F75`-`0x204F9B`). Help text Tr `ui.txt:2027-2029` ("Only possible while the unit is in a town."). |
| A Necromancer- or Lich-led unit can also recruit in the field (not in towns' or churches' tiles), despite the help text. | ROM `0x204E77`: a tile that is not a location (type != 0x13) goes to `0x204F16`, which allows the recruit path `0x204F2A` only when the leader's class byte is 0x16 (Necromancer) or 0x17 (Lich). Exp `nec0`/`nec1`: `r2-story-late-s9_gameplay`, unit 1 moved to plains tile (79,16) with `6108=80458006`, input `10:A:2;60:A:2;110:A:2;170:D:2;220:A:2;390:A:2;450:R:2;510:A:2`: three icons (Move, Tactics, Organize) normally; four with `46AA=16` (leader made a Necromancer). Exp `nec2`: the extra icon's label is "Recruit" (Option shows the towns-only help). Exp `nec3`: A on it opens the list "Skeleton 180, Ghost 180". |
| Up to three flags; A again on the last flag confirms; a third flag confirms by itself; B removes the last flag. | `explore-map.md` "Moving a unit". |
| Straight lines between flags; mountains crossed slowly; steer around water. | `explore-map.md` ("Units walk in straight lines between flags (through mountains, slowly); use flags to route around water"). |
| Holding B speeds up the cursor. | `explore-map.md` "Cursor coordinates" ("6 px/frame with B held"). |
| Command bar contents; Deploy unit from chapter 2. | Exp `cmdbar4` (stage 0 bar: NEXT, Organize, Items, Tarot cards, Finances, Monitor, Suspend); `explore-map.md` (Deploy label from stage 1); Tr `labels.txt` comment. |
| NEXT lists units and towns and jumps the cursor. | `explore-map.md` ("NEXT ... opens the UNIT / CITY lists ... A on a unit jumps the cursor to it"). |

### Towns, churches and hidden places

| Claim | Source |
|---|---|
| Towns and churches are strongholds; liberation brings information, items or tarot cards; daily reward; money needed to deploy. | Tr `script.txt:314` (Tips 3), `239-245` (Tips 4). |
| Enemy-held places are won in battle first. | `explore-progress.md` "Stage 0" (Gring: bandit challenge and battle; winning liberates Gring). |
| A tarot card is offered on liberation; stat changes shown; keep it for battle. | Tr `ui.txt:279` ("Draw a tarot card?"), `ui.txt:287-288`, `ui.txt:545-586` (stat change messages); `explore2-systems.md` "Tarot cards". |
| Units recover HP in strongholds; new information on later visits. | Tr `script.txt:320-323` (Tips 3). |
| Town window: population, two ratings LOW/MID/HIGH, daily income. | `docs/engine-notes.md` "Stages and events" (town window: name, population, two ratings, income); Exp `hqmenu` (Estoa window: 2120, HIGH, HIGH, 1802). |
| One shop town per area from chapter 2; the table of shop towns and stock; hidden ones. | ROM location records (byte +9 = shop number) and shop lists at `0x21713A + 5 * shop` (decoded with `stagemap.py`); hidden marks from the event entries (below). `explore-towns.md` "How the services work" (one shop town per stage from stage 1; Buy items icon). `explore2-systems.md` "Shops" (all 20 lists displayed). |
| The shop closes after each purchase. | `explore-towns.md` and `explore2-systems.md` "Shops". |
| Trade Ticket calls Jack; his stock. | `explore-towns.md` "Jack's shop"; Tr `tables/items.txt:209`; shop 0 list (ROM `0x21713A`). |
| Recruiting depends on the leader's class. | ROM recruit lists `0x20E7FA` (copied at `0x204F4A`); `explore2-systems.md` "Recruiting". |
| Recruits arrive two levels below the leader (at least level 1). | ROM `0x204E43`-`0x204E4E` (recruit level = leader level - 2, minimum 1, stored at `0x4580`). Exp `cp8recruit`: leader level 12, recruited Curse Priest level 10. |
| The unit needs room and the army needs room. | Tr `ui.txt:308-311`; Exp `cp3` ("The unit is full..." when recruiting into a full unit); ROM `0x204EAE` / `0x204F33` (`call 0x20D288`, no Recruit when the army is full). |
| Rite of revival revives for a fee; Soul Call revives a character. | Tr `script.txt:379-385` (Tips 2), `ui.txt:522-523` ("Reviving costs N goth"), `tables/items.txt:201` (Soul Call). |
| Hidden places appear when a unit walks onto them; Crystal Ball reveals them. | `explore-map.md` "Hidden places" and state table (Hind and Orata discovered by walking); `explore-towns.md` (Crystal Ball reveals Hind); Tr `tables/items.txt:216`. |
| Hints such as an island of the right size or a road ending. | Tr `script.txt:855-858` (Kaf villager). |
| Orata can be reached by a flying unit. | `explore-map.md` ("Orata is on an island in the lake: only a flying unit can reach it"; reached with June's flying unit). |
| List of hidden towns and the count of hidden churches per area. | ROM event entries: for location r >= 1 of a stage, 4 bytes at (location table - 4r) = [id][hidden index][handler offset]; a nonzero hidden index makes the place hidden (check `0x2035C1` -> `0x20317D`, discovered bits at `0x5432`). Decoded for all stages with `allhandlers.py` / `churchcount.py`. Agrees with `explore-map.md` "Hidden places" (stage 0 Hind; stage 1 Kehm, Orata; stage 2 Ijiriko, Parna; stage 3 Linde, Satsurama, Heide; first hidden churches in stage 7 (two), stage 8 (two), stage 10 (three)). |
| Buried treasure; Dowsing Rod; the item is random among weapons, armor and accessories. | `explore-map.md` "Map tile attributes" (treasure tiles); Tr `tables/items.txt:208`; ROM `0x208E82`-`0x208EA0` (treasure script calls `0x215E86`), `0x215E86` (random pick: the n-th item after 25 with bit 3 of its type byte clear, n = 1 to 88), which covers items 26-130 (weapons 26-75, charms and rings 76-99, armor 100-130 in `tables/items.txt`). |

### Money

| Claim | Source |
|---|---|
| Goth; daily Income & Expenses window with Aid, Deployment cost, Carried over, Total funds; Finances shows the forecast. | Tr `ui.txt:259-271`, `ui.txt:2003-2004`; Tr `labels.txt` (03 Finances); `explore-map.md` "New day"; ROM `0x207914`-`0x2079A4` (aid from `0x207B64`, deployment cost summed over deployed units, total = funds - cost + aid). |
| When you cannot pay, you must recall characters from deployed units; choosing a leader recalls the whole unit. | Tr `ui.txt:274-276`; `explore2-systems.md` "Running out of funds at the day change" ("Choosing the leader recalls the whole unit. Is that OK?"). |
| Chapter clear bonus; selling; gifts. | `explore-progress.md` (BONUS MONEY screen); `explore-towns.md` (Sell); Tr `script.txt:350-351` ("You obtained 10000 goth."). |

### Battles

| Claim | Source |
|---|---|
| Battles start when a unit meets an enemy unit or neutrals; they play out by themselves; attacks by class and row. | `explore-battle.md` "How battles start", "Battle screen"; `explore2-battle.md` "Attack choice". |
| Tactics and their effects. | Tr `ui.txt:747-751`, help `ui.txt:2061-2073`. |
| Tactics set in the unit window or in battle; A opens the battle bar and pauses; bar: Tarot cards, Tactics, Retreat, Animation, Persuade (neutrals). | `explore-battle.md` ("In-battle command bar (A during the battle; the battle pauses)"); Exp `cmdbar5`, `cmdbar1`, `cmdbar2` (labels Tarot cards, Tactics, Retreat, Animation, Persuade on screen); Tr `ui.txt:1714-1733`. |
| Defeating the enemy leader wins at once; otherwise the battle runs to a time-out. (The guide no longer says "a battle ends when any leader falls": `explore2-battle.md` "Results" notes that the army leader at 0 HP does not end the battle.) | `explore-battle.md` "Results, defeat, retreat" ("Enemy leader killed: 'WINNERS' at once"); Exp `yl1` and `ct1` (neutral leader HP poked to 1 at frame 110: the battle ends with our WINNERS). |
| Against an enemy unit, on time-out the enemy wins and your unit is pushed back. | `explore-battle.md` ("Enemy leader killed: 'WINNERS' at once"); `explore2-battle.md` "Results" (time-out vs an enemy unit: enemy declared winner while any member stands); ROM `0x2C65F7`-`0x2C6637`. Exp `bt1`: `battle-gring_fight_banner`, HP of all six combatants poked to 999 at frame 130 (`552E,555E,558E,561E,564E,567E = E703`); at the time-out (about frame 2000) the red enemy "WINNERS" label shows and "Estrada's unit has finished moving." follows; `0x45CE` = 1 afterwards. |
| Against neutrals a time-out is decided by how the fight went and can be a draw. | `explore2-battle.md` "Results" (words at `0x5509`/`0x550B` decide; equal = DRAW); ROM `0x2C6613`-`0x2C6631`. |
| Experience up to 100; level up at the end of the battle ("LEVEL UP!"). | Code (player) `runtime/src/core/cheats.h` comment (+16 experience 0-99; level up after the next battle at 99); `explore2-battle.md` "LEVEL UP!" sprites; `explore-battle.md` ("LEVEL UP!" at the end, also after a lost battle); Exp `gb1` (LEVEL UP! sprites at the end of the battle). |
| A fallen leader of another unit turns the unit into a ghost that walks away; the game will not deploy it while its leader cannot fight. | `explore-battle.md` "Results, defeat, retreat" ("the unit turns into a ghost on the map and walks away; no message; it leaves the NEXT list"; "This unit's leader cannot fight, so the unit cannot be deployed."); Tr `ui.txt:528-529`. |
| Neutral monsters: none in Estrada's Manor and the Nessa Region; kind depends on terrain; outside the Free Battle Areas each kind has a fixed level (3 in the Gross Region up to 24 at Laika Lakeside); leader level + 6 in Free Battle Areas. | ROM neutral encounter routine `0x208F70`-`0x209033`: the table before each stage's event table (entries [class][level][terrain], read backwards from event table - 5, ended by a terrain byte with bit 7 set) is matched against the terrain type under the unit (`0x45CE`, from `0x203B9B` = attribute byte +2); an entry with level 0 means "leader level + 6, at most 99" (`0x208FBB`-`0x208FC9`, `0x208FFB`-`0x209000`). All tables dumped with scratch `neutrals.py`: stages 0 and 6 have no entries; stages 1-16 have 3 entries each with fixed levels (stage 1: 3, 3, 3; stage 3: 4-5; stage 8: 15-16; stage 12: 24; side areas 4-20), so levels can differ between kinds of one area; stages 17-19 have 7, 5 and 5 entries, all level 0. Exp: `battle-neutral_battle_start` (stage 1) neutral Dragon level 3 vs leader level 5; Exp `ec2` and `fbmove` (Free Battle Area 1 state) neutral level 13 with leader level 7. |
| The Echo Chime calls one of the area's kinds at random, whatever the terrain. | ROM item-use table at `0x215FBA` (3-byte entries, entry = item id below 132): item 4 (Echo Chime) -> `0x21608C`, which uses `0x209118` (reference at `0x2160A5`); `0x209118`-`0x209190` counts the area's entries, picks entry `floor(count * random / 256)` and builds that neutral, with no terrain test and no special-unit path. Exp `ec2`: in `r2-systems-test-fb17_map` the unit stands on its HQ (tile 101,25, terrain type 19, which no table entry has), yet the Echo Chime called a Cerberus (a terrain-9 entry). |
| Persuade chance depends mainly on leader CHA and LUK against the target's CHA; a persuaded neutral goes to the stock. | `explore2-battle.md` "Commands, tactics, Run, Persuade" (formula at `0x2C79F5`; "the neutral joins the stock silently"). |

### Tarot cards

| Claim | Source |
|---|---|
| 22 cards; from liberation and the Joker Card; up to 14 in stock; asks to discard one when full. | Tr `tables/tarot.txt`; `tables/items.txt:206` (Joker Card); `explore-map.md` "Tarot stock" (14 slots at `0x5406`); Tr `ui.txt:290-292`. |
| World: later card effects apply to every deployed unit. | Tr `ui.txt:281-284`; `explore2-systems.md` "Tarot cards" (shown when World is drawn). |
| Battle effects table. | Tr `ui.txt:1870-1978` (card texts) and `ui.txt:1614-1710` (battle help); `explore2-battle.md` "Tarot cards in battle" (all 22 used in battle). |

### Items

| Claim | Source |
|---|---|
| Item commands; Option shows the description. | Tr `labels.txt` (18-1E); `explore2-systems.md` "Shops" (Option on a list entry shows the description) and "Items". |
| One equipped item per character; no class restriction. | `explore-organize.md` (record +17 equipped item; status ITEM field); `explore2-systems.md` "Class change" ("Equipment has no class restriction."). |
| Stock of 60 entries, up to 99 each. | `explore-towns.md` "RAM" (60 entries [item id][count]); `short-names.md` "Decisions" (stacks up to 99, `cp 0x63` at `0x215C7A`). |
| Hero's Shard (+1 level), stat items. | Tr `tables/items.txt:342-349`; ROM item handlers `0x2164A1` (level up via `0x20CFFA` if below 99), `0x2164C4` (max HP), `0x2164F5`-`0x216586` (stats, CHA/ALI/LUK capped at 100). |
| Chaos Up / Down: +5 / -5. | Tr `tables/items.txt:360-361`; ROM item-use table entries 39/40 (`0x21602F`, `0x216032`) point to `0x216587` / `0x21658C`; each is a script "native" byte (0x30) followed by native `ld.b A, 5` (`0x216588`) or `ld.b A, -5` (`0x21658D`), then `call 0x20D3FE` (`0x21658F`). The dispatcher `0x215F7D` maps items 162/163 to entries 39/40. |
| 7-League Boots, Echo Chime, Joker Card, Crystal Ball, Dowsing Rod. | Tr `tables/items.txt:202-216`; Exp `ec2` (Echo Chime started a neutral battle). |
| "Use in versus battles" items only in link battles. | `explore-battle.md` Open issue 4 (the in-battle Item command does not appear in normal battles even with these items in stock); Tr `tables/items.txt:362-387`. |

### How you lose

| Claim | Source |
|---|---|
| Game over when the first unit's leader falls in battle. | ROM `0x2033E5`-`0x203407`: after a battle, if the HP of unit 1's first member (`0x517E`) is 0, the message `0x203CE9` ("With its leader lost, the volunteer army has been wiped out...") and the game-over script `0x203C1B` run. `explore-battle.md` ("Army leader killed (stage 0, Estrada ...)" -> game over); `explore2-story-late.md` (game over in stage 12 with the hero killed). |
| Game over when the HQ is taken. | ROM `0x203C05`: message `0x20A3C8` ("Your headquarters has fallen to the enemy...") runs the same game-over script `0x203C1B`; `explore-progress.md` state `progress-stage2_hq_fallen_msg` ("game over follows"). |
| In some chapters enemies march on the HQ; a defeated unit is pushed back; an enemy walking into an empty HQ takes it. | `explore-progress.md` "Stage 2" ("The HQ falls if left empty") and Open issue 5 (stage 3: the single guard was pushed off after each battle and the next enemy walked in); `explore-map.md` (stage 1 enemies stayed put: "some chapters"). |
| Losing another town lowers the Chaos Frame by 5. | ROM `0x20A3A4`-`0x20A3B7`: after composing "<town> has fallen to the enemy." (`loc_msg_lost`), `ld.b A, 0xFB` / `call 0x20D3FE`. |

### Clearing a chapter and going back

| Claim | Source |
|---|---|
| A goal per chapter, named in the opening; reaching it ends the chapter; Congratulation screen with bonus money; next area opens. | `explore-progress.md` "Stage walkthroughs" and "Done" (stage-clear sequence); stage main handlers (ROM, `handlers.txt`) end in `jump 207BFC` (stage clear). |
| Cleared areas stay open for a while. | Stage masks (section 4): e.g. after chapter 7 the open mask `0x21C7` includes stages 0, 1, 2 and 6. |
| In a cleared area: no enemy units, no daily aid, no deployment cost, Return to map. | `0x6089` = 1 when the current stage is cleared (stage loader `0x203231`-`0x20324A` stores the cleared bit of stage `0x5490`-1 in H of `0x6088`). Uses: `0x2032D3` (enemy units loaded only if not cleared), `0x206E76` and `0x206EC7` (deploy cost multiplied by 1 - cleared), `0x207937` (daily deployment cost only if not cleared), `0x207B66` (aid only if not cleared), `0x2046CE` (bit 8 of the command mask = Return to map, `explore2-systems.md` "Not reached" names bit 8). Help text Tr `ui.txt:2014-2016`. |

### The Chaos Frame and alignment

| Claim | Source |
|---|---|
| Chaos Frame 0-100; reputation; shows support. | Tr `script.txt:592` (Tips 6); ROM `0x20D3FE` (clamped 0-100); Code (player) `cheats.h` (reputation = Chaos Frame `0x4694`). |
| Final score on the results screen. | `explore-progress.md` "Ending" ("CHAOS FRAME n pt."). |
| Liberating a town changes it by the unit's average ALI against the town and the leader's class against the town; low alignment lowers it. | Tr `script.txt:595` (Tips 6); ROM `0x2083B5`-`0x2083FF`: A = average ALI of the unit's members minus town record byte +12; E = class value (table `0x20DB13` + 16 x leader class) compared with town byte +13 as minus the absolute difference; (A + E) / 20 is added with `0x20D3FE`. Churches (index past the records) skip this (`0x2083A5` branch). |
| Losing a town: -5. | See "How you lose". |
| Conversation choices and some purchases change it. | ROM `op46` in many handlers (`handlers.txt`), e.g. `0x267B3F` (+6), `0x267B78` (-5), `0x2665B2` (Bronze Maiden purchase +2), `0x266587` (refusal -1). |
| Tarot cards when drawn; Chaos Up/Down. | Tr `ui.txt:549-550` ("The Chaos Frame went up/down ..." composed message); `explore-battle.md` ("The Chaos Frame went up by 2 points."). |
| ALI per character, 0-100; class limits; Sun card; conversation choices change the hero's ALI. | ROM `0x20D412` (clamp 0-100); class table (section 3); Tr `ui.txt:1960-1963` (Sun); `op4a` in handlers (e.g. `0x267B41`, `0x2688F2`). |
| Conditions table (king's request 65+, Gross below 55, Kiros below 60, Aquarius leaving below 39 and below 49, Lanselot/Warren 60+ and 50+, priests 80+ / 20-). | See the rows of sections 4, 5 and 7 below. |

## 3. Characters and class changes

| Claim | Source |
|---|---|
| Status screen contents (class, Lv, HP, STR, AGI, INT, CHA, ALI, LUK, cost, next level, F/B attacks, MOVE, ITEM). | `explore-organize.md` "Screen map" (status pane); Exp `cc1` screenshots. |
| Class change from Organize (Character, Class change) or the unit's Organize command; marks OK!, UP OK!, BAD. | `explore-organize.md` "Screen map" and "Class change"; `explore2-systems.md` "Class change"; ROM `0x20D2FD`-`0x20D307` (the "up" flag set when a target has a higher class id, except for class 23). |
| Requirements: minimum level, ALI range, minimum CHA. | ROM `0x20D2A6`-`0x20D2F3`: targets of class c are the c-th zero-terminated list at `0x20E8FE`; each target t needs level >= byte 0, byte 1 <= ALI <= byte 2, CHA >= byte 3 of `0x20E9DD + 4t`. `explore-organize.md` "Class change rules". |
| The table values. | ROM data dumped with `classes.py` (lists and requirements). Exp (class-change boundaries), state `r2-systems-test-cc_fighter_ali50` (Kain = Fighter), input `20:R:2;60:R:2;100:A:2;180:D:2;240:A:2`: Lv 40 ALI 50 CHA 100 -> Knight, Samurai, Beast Tamer, Wizard, Doll Master, Ranger (`cc1`); pokes `46BD=04,46C7=32,46C8=32` (Lv 4, CHA 50, ALI 50) -> Wizard only (`cc2lv4`); Lv 5 -> Knight, Beast Tamer, Wizard, Doll Master (`cc3lv5`); Lv 5 CHA 49 -> BAD (`cc4cha49`); Lv 6 ALI 40 CHA 50 -> Berserker, Ninja, Beast Tamer, Wizard, Doll Master (`cc5ali40`). `explore2-systems.md` "Class change" checked all 56 targets at level 40 and CHA 100. |
| Fighter and Amazon need nothing; every Fighter-line class except the Lich lists Fighter, every Amazon-line class lists Amazon; other back changes need the target's requirements. | ROM requirement records for Fighter (1) and Amazon (25) = (0, 0, 100, 0); lists at `0x20E8FE` (dumped with `classes.py`): classes 2-22 and 24 include Fighter, the Lich (23) lists only Skeleton (68); classes 26-35 include Amazon; the other targets keep their own records. |
| Leaders can only take classes that can lead. | Tr `ui.txt:212-215`; `explore-organize.md` ("A unit leader cannot take a class that cannot lead (`0x202E9D`)"). |
| Story characters with their own classes (hero, Kain) have no class changes in the list. | ROM: classes 98-117 have empty lists at `0x20E8FE`; `explore-organize.md` ("Story characters' unique classes have no targets ('BAD')"). |
| Dragon Tamer, Necromancer, Lich, Revenger, Arch Samurai, Princess and Enigma Hunter come only from items. | ROM: none of them is a target in a list except Dragon Tamer as a change back from Dragon Master (which needs Dragon Tamer first); item pairs below. |
| The monster/other table only moves forward. | ROM lists for classes 36-95: only higher targets. |
| Lich -> Skeleton in the normal list. | ROM list of class 23 = Skeleton (68), requirement (0, 0, 100, 0). |
| Twelve class-change items, their source and target classes. | ROM: item-use dispatch `0x215F7D` maps items 132-161 to entries 19-48; entries for items 132-143 run `0x2165B9`, which requires the character's class byte to equal the first byte of the pair at `0x2165ED + 2 x entry` and sets the second byte (pairs decoded: 15->16, 21->22, 22->23, 2->42, 25->34, 44->45, 7->8, 10->11, 88->89, 90->91, 50->53, 25->35); the Ring of Undeath entry `0x2165A2` adds 10 when used on class 66 (Tiamat), giving 66->67. Item names Tr `tables/items.txt:136-147`; descriptions `items.txt:330-341`. |
| Alignment limits apply, level and CHA do not. | ROM `0x2165E2`-`0x2165FF`: level and ALI range are compared with the target's record; the CHA comparison is broken (`ld.b A, (XDE)` instead of a compare), so CHA is never checked; all item targets have minimum level 0. Target records: Revenger ALI 15-100, Arch Samurai 70-100, Holy 90-100, Exodus 0-10, the others 0-100. Exp `it6`: state `towns-organize_soul`, pokes `538E=8C01` (White Vow), `46CE=58` (Estrada as a non-story Light Priest), `46D9=0A` (CHA 10), `46DA=5F` (ALI 95), Items > Use item on him -> class 89 (Holy) although Holy's CHA minimum is 70. Exp `it7`: same with ALI 89, CHA 100 -> "It can't be used on this character.", class stays 88. |
| They do not work on story characters. | ROM `0x2165D0` compares the whole class byte, including the story bit 7. Exp `it4`: same as `it6` but class byte `D8` (story bit set) -> refused. Dismiss uses the same bit (`explore-organize.md`). |
| The item is used up. | `explore2-systems.md` "Class change by item (Drago Stone on a Beast Master): silent, the item is used up". |
| Ring of Undeath from the Ein Peninsula. | ROM `0x271535`-`0x27153E` (post-battle of Gigant: `st16 0186` = item 134). |
| Waltmood is held by a Talos; defeat it before the Wind Dunes are cleared and the town gives a Blood Spell (Chaos below 40), Archangel Wing (40-69) or Dream Crown (70+). | ROM Waltmood handler `0x2722BF`-`0x272326`: `bflag2 0F` (Wind Dunes cleared) -> only "Now we can come and go as we please."; first arrival arms the post-battle script `0x2722D3` (`setflag BC`); with BC set: "Oho. Defeating that Talos is quite something. Let me give you this as thanks.", `setflag BD` (once), item `0x87` (135 Blood Spell), `bcmp 28` keeps it below 40, else `0x5A` (90 Archangel Wing, Tr `tables/items.txt` line of id 90), `bcmp 46` keeps that below 70, else `0x88` (136 Dream Crown). Waltmood is hidden (event entry hidden index 0x38). The guide does not say whether the gift comes right after the battle or on the next visit: Gring's handler uses the same pattern and `explore-battle.md` saw its villagers right after the liberation, so it is probably the same visit (not tested for Waltmood). (An unused copy of the Talos line at `0x272327` is the orphan noted in `explore2-story-late.md` Open issue 3.) |
| Cat's Tongue from ordinary Firbolg-led neutrals with the leader defeated in a Free Battle Area. | ROM `0x209516`-`0x20952B` (after a won Free Battle fight: encounter type `0x52AA` = 0x65 (ordinary), neutral leader HP `0x4DB6` = 0, then counter = 10 gives Yuria's Letter, else neutral leader class byte `0x4DB2` = 0x32 (Firbolg) gives item 0x8E = Cat's Tongue). Exp `ct1`: `battle-neutral_battle_start` + `5490=12,4698=00`, at frame 110 `561E=0100` (neutral leader HP 1) and `4DB2=32`, A every 80 frames from 900: "As spoils of war, you found "Cat's Tongue"." and "You obtained "Cat's Tongue"." (text log). |
| Of the Free Battle Areas only Area 2 has Firbolgs, met over shallow water or through an Echo Chime; a flying unit can go over water. | Neutral tables (scratch `neutrals.py`): stage 18 has Bahamut (terrain 11), Pixie (6), Skeleton Knight (16), Thrones (1), Firbolg (0); stages 17 and 19 have no Firbolg (stage 5, Litt Island Waters, also has Firbolgs at level 11, but the item needs a Free Battle Area). Terrain 0 is "Shallow" in the battle terrain names `0x2C82A9` (0 Shallow, 1 Ocean, 2 Reef, 3 Plains, 9 Peaks, 15 Road, 19 Fort, ...); `explore2-battle.md` also calls terrain 0 shallow water. The FBA2 map (scratch `tmap.py 18`) has 1,397 shallow tiles (rivers). Echo Chime: row above. Flying units over water: `explore-map.md` "Hidden places" (Orata, on an island ringed by shallow water on the stage 1 map, is reachable only by a flying unit). |
| Others' sources not covered. | Searched: no `st16 01xx` gift of items 132, 133, 137-141 or 143 in any stage handler (`handlers.txt`), and the random treasure pool (`0x215E86`) stops at item 130. |
| Recruit table. | ROM recruit lists at `0x20E7FA` (dumped with `classes.py --recruit`); hero classes 103-107 (Knight) and 108-112 (General) have their own lists, the Lord list (class 96) applies to the hero as Lord (class byte `0xE0`, bit 7 masked at `0x204F47`). `explore2-systems.md` "Recruiting" checked the lists of 11 leader classes. |
| The hero starts as a Fighter, becomes a Knight at the start of chapter 2. | ROM `0x264C66` (chapter 2 opening, after the knighting lines Tr `script.txt:414-418`): `inc.b 5, (0x46AA)` moves the hero from class 98-102 (Fighter) to 103-107 (Knight); `inc.b 1, (0x46BC)` for Kain. States: `stage0_gameplay` hero class 101; `r2-story-early-s3_all_units_deployed` hero class 106. |
| General after the events in Estoa before chapter 7. | ROM `0x263FEB` (Estoa revisit, after Tr `script.txt:214-215`): `add8 05, 46AA`, then `st16 0040, 546A` (opens stage 6). State `r2-story-early-s6_gameplay` hero class 111. |
| Lord at the start of chapter 12 with Yorkleif and Grant. | ROM `0x26E16F`-`0x26E17A`: `b40 068A`, `b40 0687`, then `ld.b (0x46AA), 0xE0`; `explore2-story-late.md` "Script and RAM facts learned". |

## 4. Routes and side areas

| Claim | Source |
|---|---|
| Chapters 1-6 in a fixed order. | ROM stage clears: stage 0 `st8 02, 546A` (`0x26433C`), stage 1 `st8 04` (`0x26537A`), stage 2 `st8 08` (`0x265DAF`), stage 3 `add8 10` (`0x26755B`), stage 4 `add8 20` (`0x267CF4`). |
| After chapter 6 choose Lichtfloss. | State `r2-story-early-s5_cleared_scenario_map`: open stages 3, 4, 5, 13; the Lichtfloss revisit is the stage 3 script's `bflag2 05` branch (`0x266B43` -> `0x266FF7`); `explore2-story-early.md` "Script facts learned". |
| The king asks only with Chaos Frame 65+; Ein Peninsula. | ROM `0x267077` (`bcmp 41`); Tr `script.txt:1104-1115`, `1136`. |
| Accept: Chaos +3, ALI +2, Ein opens; clearing it gives the Ring of Undeath and leads to Estoa; Ein open again after the ending. | ROM `0x2672AA`-`0x2672B0` (`op46 03`, `op4a 02`, `setflag D9`, `st16 4000, 546A`); Ein boss post-battle `0x271539`-`0x271542` (`st16 0186`, `pcall 267B94` = `st16 0001, 546A`, Estoa); ending `0x270B38` (`bflag D9` skips the `add8 C0, 546B` that cancels the +0x40 for Ein). States `r2-story-early-s5after_A_scenario_ein_only` (open = 14 only). |
| Decline: Chaos -5; to Estoa. | ROM `0x26717B` (`op46 FB`), then `pcall 267B94`; state `r2-story-early-s5after_B_scenario_estoa_only` (open = 0 only). |
| Below 65: no request; to Estoa. | ROM `0x267077` branch to `0x2671EC` (no `op46`). |
| Estoa opens chapter 7. | ROM `0x263FF3` (`st16 0040, 546A`); state `r2-story-early-s0return_scenario_stage6_open` (open = 6). |
| After chapter 7 both Norodom and Megaholten are open. | ROM `0x269148` (`st16 21C7, 546A` = stages 0, 1, 2, 6, 7, 8, 13; `add16 FFE0, 546B` removes 13 unless flag CE); state `r2-story-early-s6_cleared_scenario_map` (open 0, 1, 2, 6, 7, 8, 13). |
| Clearing one closes the other for good. | ROM `0x26A427` (stage 7 clear `add8 01, 546B`: with bit 8 set this carries into bit 9, closing Megaholten and opening Shagall); `0x26B381`-`0x26B385` (stage 8 clear `add8 02, 546B` opens Shagall; `add8 80, 546A` flips bit 7, closing Norodom). Exp `r7clear`: `r2-story-late-s7_boss_armed` + poke `546A=C7210000` + `10:A:2;60:B:2` and A every 70 frames -> `0x546A` = `0x22C7` (stages 0, 1, 2, 6, 7, 9, 13). Exp `r8clear`: `r2-story-late-s8_boss_armed`, same -> `0x2347` (0, 1, 2, 6, 8, 9, 13). No later write sets bit 8 or bit 7 again (all writes to `0x546A`-`0x546D` listed in `handlers.txt`; the ending adds `0x000E4038`, which keeps 7 at 1 on the Norodom route and leaves it 0 on the Megaholten route). |
| Norodom route 8, 10, 11, Final; Megaholten route 9, 10, 12, Final. | ROM `0x26C172`-`0x26C17A` (stage 9 clear: `add8 04, 546B` opens 10; without flag 4E a second `add8 04` turns it into 11); flag 4E set by the stage 7 opening (`0x26A190`); stages 10 and 11 clears `add8 10, 546B` (`0x26D4DE`, `0x26E638`) open 12. `explore2-story-late.md` (flag 0x4E set by the stage 7 opening selects Baldur's second question set). |
| Who joins on each route. | See section 5 rows (Orosov, Gross: stage 7 handlers; Yorkleif: stage 8; Grant: needs Yorkleif; Lyon, Ashe: stage 8 hidden towns; Deneb: stage 11 hidden town). Post-ending open stages by route (section 7). |
| Freia Isles from the Lego Islands (Norodom route). | ROM `0x26D60E`-`0x26D626` (Whitey: trade the Thunder Stone, `add8 01, 546C` = stage 16); stage 10 is only on the Norodom route; no other write sets `0x546C` bit 0. |
| Lord on the Megaholten route. | Section 3 row. |
| One question set and three endings per route; five endings in all; one shared. | Section 6 rows. |
| Grant joins only with Yorkleif in the army. | ROM `0x26C981` (`b40 068A` skips Grant's scene). |
| Each route has a character who may leave. | Section 5 spoiler rows (Orosov, Aquarius). |
| Krono Mountains: both Parna and Ijiriko visited before Kazuma is beaten; otherwise never. | ROM `0x265DAF`-`0x265DC7` (Kazuma's post-battle: `st8 08, 546A`; only if flags 1E and 1F are set: `add8 20, 546B` (stage 13) and `setflag CE`); flag 1E set by Parna's first visit (`0x266713`), 1F by Ijiriko's (`0x266894`); both hidden (entries 05, 04). Stage 6 clear keeps 13 only with CE (`0x26914D`). No other write sets bit 13 or flag CE. States: `progress-scenario_after_stage2_popup` (CE 0: open 3 only), `r2-story-early-s2_cleared_scenario_map` (CE 1: open 3, 13). |
| Wind Dunes: Netobi mayor's errand, Rainbow Choker from a Satsu Peninsula church. | ROM `0x26C5F3`-`0x26C6BF` (mayor asks, `setflag DC`); stage 2 church #0 `0x2668C7`-`0x2669F9` (`bflag DC` -> gives item 0xA0 Rainbow Choker); Netobi `0x26C51E`-`0x26C5EE` (with the choker: 30000 goth, item 0x0D Love & Peace, `add8 80, 546B` = stage 15). |
| Freia Isles: Thunder Stone from Kehm traded in Whitey. | ROM Kehm `0x2657C4`-`0x26586C` (gives item 0x9C Thunder Stone; Kehm hidden index 02); Whitey row above. |
| Cleared areas stay open for errands; Gross Region and Satsu Peninsula reopen after chapter 7. | `st16 21C7` row above. |
| Purified Ruby from the Roden church; Brunn barrier. | ROM church `0x2680C5`-`0x2681BF` (gives item 0x9E); Brunn `0x267C2B` (`b42 9E` -> "A barrier has been raised here!" and the unit is sent away); Brunn is the stage 4 main location (clear at `0x267CF4`). |
| Goddess Statue sold in Orata after flag DB (Consana or a Shagall church); prices 50,000 / 30,000 / 20,000 / 10,000 by Chaos Frame below 50 / below 65 / below 80 / 80+. | ROM Orata `0x265652`-`0x2657A9` (`bflag DB`; `st32 C350`, `bcmp 32`, `st32 7530`, `bcmp 41`, `st32 4E20`, `bcmp 50`, `st32 2710`; buy -> item 0x9B); DB set at Consana `0x26ACE9` (Norodom hidden town) and by the Shagall church handler `0x26D049`. Orata hidden index 03. |
| In Gipis one is for sale at 500,000. | ROM `0x26DCCD`-`0x26DD69` (Gipis, hidden index 23, Lego Islands): "A white Goddess Statue. Won't you buy it for 500000 goth?", funds check `0x7A120`, item `0x9B`, `op48 -500000`. The speaker is not named, so the guide does not say "a man". |
| Church of Truth barrier (Norodom route only); Brynhild trade. | ROM Norodom church #0 `0x26AD57` (`b42 9B` -> barrier and push back; hidden index 13; Consana's villager names it the Church of Truth, Tr `script.txt:2248-2257`); Shagall churches (all four share handler `0x26CF12`) `0x26CF12`-`0x26CFB3` (`op44 9B`, gives item 0x19 Brynhild). Norodom route only: after chapter 8 the Megaholten clear flips bit 7 off and no later write sets it again (section 4 rows). |
| Silver Doll from Balzac after the Nessa church mention, with Chaos Frame 70+; sell 50,000 or trade for Mail of Earth at Gawafur (Megaholten route only). | ROM Balzac revisit `0x264344`-`0x2643CD` (`bflag DA`, `bcmp 46` (70), gives item 0x9A); flag DA from Nessa church #3 `0x26A0A1`; Gawafur `0x26B9B1`-`0x26BAD8` (50000 goth via `op48`, or item 0x69 Mail of Earth). Gawafur is a hidden town of stage 8 (Megaholten), which closes for good when Norodom is cleared (`0x26A427`, section 4). |
| White Cross from a Lichtfloss church; return it in chapter 6 at the north-east island church of Litt Island Waters for the Kusanagi Blade. | ROM Lichtfloss church #0 `0x2679CC` (gives item 0x5C); Litt church #0 `0x268AD9` (`bflag2 05` -> only before stage 5 is cleared; trade gives item 0x32); church #0 is location code 7, map tiles x 91-93, y 15-17 (north-east island). Exp `cp1`: `r2-story-early-test-s5_whitecross_prompt_tight`, Yes -> "You obtained 'Kusanagi Blade'". |
| Silver Rod from Heidecker in chapter 6; Holy Rod at the other Litt church in chapter 6. | ROM Heidecker `0x268963` (`bflag2 05` -> gift only before the clear; item 0x48; hidden index 0B); Litt church #1 `0x268BE6` (`bflag2 05`; `op44 48`, item 0x49 Holy Rod). |
| Bronze Maiden: 1,000 with Chaos Frame 60+, else 2,000; buying +2. | ROM Colomban `0x26650E`-`0x2665B4` (`bcmp 3C`, prices `0x3E8`/`0x7D0`, `op46 02` after buying). |

## 5. Story characters and how they join

| Claim | Source |
|---|---|
| Most need a free place; some wait, some are lost. | ROM: free-place checks (`call 0x20D288`) come before the event for Goldie (`0x269A35`), Orosov (`0x26A71E`), Yorkleif (`0x26B53A`), Grant (`0x26C96D`), post-game recruits; after the decisive moment for Aquarius (`0x2660A2`), Gross (`0x26A42C`), Kiros (`0x26C1B1`), Birkin (`0x270CC6`). |
| Kain and Estrada from the start. | State `stage0_gameplay` (records 2 and 3). |
| Aquarius after the Lard boss; needs room; otherwise leaves for good. | ROM `0x2660A2`-`0x266171` (no room -> "I will go alone ..." and stage clear); only join message `0x2660E2` in the script (Tr `script.txt:808`). |
| Nana joins the hero's unit at the start of chapter 4. | ROM `0x266F97`-`0x266FB3` (stage 3 opening: character with class byte 0xA2 = Princess, story flag, created at record 152); states `r2-story-early-s3_all_units_deployed` etc.: unit 1 holds record 152, name index 1668 (Nana). |
| Goldie at hidden Hakatte, chapter 7: yes and 10,000 goth; one conversation; before chapter 7 is cleared. | ROM `0x269A2C`-`0x269C11` (`bflag2 06` -> later only "Good luck out there"; room check; `setflag 47` at the start, so the scene never repeats; second "no" -> leaves; funds check `0x2710` = 10000 -> `op48 -10000`); Hakatte hidden index 0F. |
| Orosov at Haitel, chapter 8, before the clear; Goldie scene. | ROM `0x26A711`-`0x26A99E` (`bflag2 07`, room check, `b3e 0685` chooses the Goldie variant; both end in "Orosov joined your army."). |
| Gross after Sict Prison with Chaos Frame below 55. | ROM `0x26A42C`-`0x26A6CC` (room check, then `bcmp 37` (55) -> Gross joins). |
| Yorkleif at Wanick: with Kain visit twice; otherwise answer yes. | ROM `0x26B531`-`0x26B897` (room check; `b3e 0672`: with Kain, first visit sets flag 5B, next visit joins; without Kain, `bchoice` yes joins). |
| Grant at Estedale needs Yorkleif. | ROM `0x26C964`-`0x26CBDC`. |
| Kiros: hero ALI below 60, spare him; costs 10 and 10. | ROM `0x26C17F` (ALI >= 60 skips the scene), room check `0x26C1B1`, choice `0x26C1E1` (A kills), `0x26C249`-`0x26C254` (`op46 F6`, `op4a F6`, character added); killing: `op4a FB` (`0x26C2AA`). Tr `script.txt:2646-2656`. |
| Birkin: Aquarius in the unit; by day he asks to come back at night; either way you can fight. | ROM `0x270B5A`-`0x270F15` (`cp (0x6088), 0` chooses the day talk with `bchoice`; post-battle `b3e 0682` and room check before he joins). |
| Hayato at Breia: 50,000 before the clear; waits if you cannot pay. | ROM `0x272830`-`0x272A3F` (`bflag2 10`; funds check `0xC350`; "come back when you can afford me"; `op48 -50000`). |
| Lanselot at Parna after the ending: by day, Chaos 60+, hero ALI 50+. | ROM `0x266640` (`bflag2 0C`), `0x26673C`-`0x266764` (flag D2, `bcmp 3C`, ALI `0x32`, room, `0x6088` = 0), class 2. `explore2-story-early.md` "Script facts learned". |
| Gilbert at Ryuk after the ending with Yuria's Letter. | ROM `0x269CBF`-`0x269D92` (`bflag2 0C`, flag D4, `b42 A1`, room). Ryuk hidden index 0E. |
| Lyon at Gawafur after the ending, by day, 100,000. | ROM `0x26BB7B`-`0x26BC4F` (flag D6, room, `0x6088` = 0, funds `0x186A0`, `op48 -100000`). |
| Ashe at Shilda after the ending, by day. | ROM `0x26BCC7`-`0x26BDAF`. |
| Deneb at Tomi after the ending with the Glass Pumpkin; also Free Battle. | ROM `0x26EED7`-`0x26EFBD` (`bflag2 0C`, flag D1, `b42 98`, room; class 0x61); Free Battle row in section 7. Tomi hidden index 29 (stage 11). |
| The Lord at Kaminol after the ending with the Twinkle Star; also Free Battle. | ROM `0x271317`-`0x2713F9` (`bflag2 0C`, flag D0, `b42 99`, room; class 0x60). Kaminol hidden index 35 (stage 13). |
| Warren at Estable: after the Wind Dunes are cleared, after the ending, at night, Chaos 60+, hero ALI 50+. | ROM `0x27209E`-`0x2721EE` (`bflag2 0F` path, flag D3, `bflag2 0C`, `bcmp 3C`, ALI `0x32`, room, `jp Z` on `0x6088` = 0 refuses by day; class 0x14). |
| Canopus and Ares: Free Battle; Canopus needs Gilbert. | Section 7. |
| Light and Curse Priest. | Section 7. |
| Glass Pumpkin and Twinkle Star: no event hands them out. | Searched every stage handler (`handlers.txt`) and native code for gifts of items 0x98/0x99 (`st16 0198/0199`, `ld.b A, 0x98/0x99` with a give, writes to `0x458E`): none. Only `b42` checks at `0x26EEF1` and `0x27134D`. Both items have bit 3 of their type byte set (`0x3F0FD5`, `0x3F0FE6`), which the random item pick skips. Where they really come from is **unconfirmed** (fan wiki says link-battle prizes; not checked). |
| Bosses who never join (Kazuma, Galan, Jenga, Dalam, Malenoa, Bergo, the Baron). | ROM: their handlers (`0x265AD1`, `0x2672BD`, `0x2682FF`, `0x26B1BA`, `0x26D296`, `0x27249C`, `0x271964`) contain no character creation. |
| Joining Kazuma costs 5 Chaos Frame and 5 ALI; you must come back and fight. | ROM Lard handler `0x265AD1`: "Won't you join us?" Yes -> `0x265C36`; No -> "are you still reluctant to join us?", where Yes fights (`0x265D1B`) and No falls through to `0x265C36` too. `0x265C36`-`0x265C9E`: `op46 FB`, `op4a FB`, unit sent away via `0x2093D9`; next visit `0x265CA2` ("You traitors!") arms the battle. `explore2-story-early.md` "Script facts learned" (same branches). |
| Estrada leaves for good at the end of chapter 6. | ROM `0x268721`-`0x268729` (`ld.w WA, 0x681` / `call 0x20D356`), after his dying words (Tr `script.txt` @2685BA-@268646, "...Farewell... Glory... and blessings... upon Zenobia..."); `explore2-story-early.md` ("At the end of stage 5 Estrada's record is emptied"). |
| Orosov leaves at the start of chapter 11 (Norodom route). | ROM `0x26D12E`-`0x26D139` (stage 10 opening: `0x686` removed, `setflag CA`). |
| Aquarius leaves after the battle at Lek (chapter 12) if hero ALI below 39 and Chaos below 49. | ROM Lek handler `0x26E1CB` (Lek = record 1 of stage 11, the chapter's goal: its post-battle script `0x26E29C` ends with the stage clear `add8 10, 546B` / `jump 207BFC`); in that post-battle script `b40 0682`, then `0x26E2A6`-`0x26E2C2` (`cp (0x46B6), 0x27`, `cp (0x4694), 0x31`, `0x20D356` with `0x682`, "Aquarius left, as if fleeing."); `explore2-story-late.md` "What was checked" (stage 11 row). |
| A leaving character's equipped item is lost. | ROM `0x20D356` clears only class/level and unit slots. Exp `est1`: `r2-story-early-test-s5_estrada_death` + poke `46DF=14` (Estrada equips Durandal) + A every 70 frames to 3000: Estrada's record cleared (class 0), the byte +17 still holds 0x14, and the item stock has no item 20. |

## 6. Spoilers: the final battle and the five endings

| Claim | Source |
|---|---|
| Baldur waits at Orma in Laika Lakeside; only the hero's unit; others sent away. | ROM `0x26F37A`-`0x26F38C` (`cp (0x4581), 0` -> `0x26F978`: "...Not you. The one I summoned was..." and `0x2093D9` sends the unit away). |
| Questions choose the ending; the set depends on the route (flag 4E). | ROM `0x26F395` (`bflag 4E`); answers read from bits 4 (A) and 5 (B) of task byte +35 (`0x26F4ED`, `0x26F5DA`, `0x26F7C1`, `0x26F8F1`); flags 9A-9D set at `0x26F5EB`, `0x26F7F6`, `0x26F902`, `0x26F949`, `0x26F94F`. Ending script `0x2702C4`: `bflag 9A` -> `0x270759`, `bflag 9C` -> `0x27096F`, `bflag 9B` -> `0x270599`, `bflag 9D` -> `0x2707DA`, none -> `0x270494`. `explore2-story-late.md` "Script and RAM facts learned" (same mapping, all branches seen on screen). |
| Norodom: A -> 9A (leaves with Kain alone); B, A -> 9D (Estoa, Banya); B, B -> 9C (the hero disappears, friends search). | As above; Tr `script.txt:3649-3672` (choices), `3948-3954`, `3957-3988`, `3990-4029` (ending text). |
| Megaholten: A -> no flag (Zeteginea, Baldur's voice); B, A -> 9B (bring down the empire, Kain, Estrada's words); B, B -> 9A. | As above; Tr `script.txt:3590-3607`, `3882-3903`, `3906-3945`. |
| Staff roll and results screen with Chaos Frame and days. | `explore-progress.md` "Ending" ("CHAOS FRAME n pt.", "CONQUEST n DAYS"). |

## 7. After the ending

| Claim | Source |
|---|---|
| The game saves the finished campaign to the current file after the ending scenes, before the staff roll. | ROM `0x270B21`-`0x270B45` (ending script: masks updated, stage clear `0x207E0B`, then `st32 2A2F0C, 4002`); `0x2A2F1C`-`0x2A2F21` (`ld.l XHL, 0x0E02468E`, `call 0x29A518` = save 0xE02 bytes from `0x468E` to the current file `0x45AF`), before the staff roll script `0x2A3077` is started. Exp `ending`: `r2-story-late-s12_ending_armed` + `10:A:2;60:B:2` and A every 70 frames to 2400: "flash: 4096 bytes programmed", file 1 block (`0x3C0000`) written; the record holds open mask `0x000E5038` and cleared mask `0x000E1FFF` at offset 0xEDC; screenshots show the ending text, then the staff roll title. |
| Returns to the title; Load the file; Free Battle Areas and earlier areas open by route and choices. | `explore2-story-late.md` ("After the results: SNK logo, title"); ending mask update `add32 000E4038, 546A` (stages 3, 4, 5, 14, 17, 18, 19 added), `add16 0E10, 546F` (stage 12 and 17-19 marked cleared), `add8 C0, 546B` unless flag D9. |
| Cleared-area rules apply to cleared areas and Free Battle Areas; neutrals still roam; unplayed side areas play normally. | Cleared-area rows (section 2); Free Battle Areas are marked cleared by `add16 0E10, 546F`; their neutral tables are not empty (stages 17-19). Unplayed side areas: the stage-clear bit is set only by `0x207E0B` when a stage ends. |
| Free Battle Areas have no story events. | ROM stage 17-19 handlers: all `ret` except Free Battle Area 1 church #0 (`handlers.txt`). |
| Their shops sell items found in no other shop, such as Chaos Up and Down. | Shop lists 17-19 against 0-16 (section 2 table). |
| Win counter: increments on each won battle in a Free Battle Area; a fight with neutral monsters that is not won (retreat, loss, draw), in any area, resets it. | ROM `0x2094B0`: after a neutral battle (`0x45D0` = 0x19), unless the neutral was persuaded (`0x61DD` != 0 -> `0x2094C0` adds it and returns), `0x2094DB`-`0x2094F9`: if `0x45CE` (battle result: 0 = won, 1 = lost or retreated, 2 = draw; `0x2C6621`-`0x2C6637`) is not 0, the counter `0x4698` is set to 0, with no stage test; in stages 17-19 (`0x5490` >= 0x12) a win does `inc (0x4698)`. Exp `ret1`: Retreat in `battle-gring_fight_banner` -> `0x45CE` = 1; Exp `win1`: normal win -> 0; Exp `gb1`: win against the Gungnir unit, counter 20 -> 21. (Battles against enemy units take the other branch, `0x20952F`, and do not touch the counter; persuading leaves it unchanged; neither is in the guide.) |
| 10th win against ordinary neutrals with their leader defeated -> Yuria's Letter. | ROM `0x209516`-`0x209521` (`0x52AA` = 0x65 ordinary encounter, neutral leader HP `0x4DB6` = 0, counter = 10 -> item 0xA1). Exp `yl1`: `battle-neutral_battle_start` + pokes `5490=12` (pretend Free Battle Area 1), `4698=09`, neutral HP `561E=0100` at frame 110 -> "As spoils of war, you found 'Yuria's Letter'.", counter 10, item 161 in stock. |
| 20 -> Gungnir unit, 30 -> Trooper, 40 -> the Lord (unless in the army), more than 30 -> Deneb sometimes, any other count -> Canopus and Ares rarely; defeat the leader to recruit; Canopus needs Gilbert. | ROM special-encounter code `0x209040`-`0x2090B1` (counter below 20 or 21-29 -> Canopus/Ares check; exactly 20 -> class 0x5C; exactly 30 -> 0x5E; above 30: exactly 40 -> Lord 0x60, otherwise a random byte >= 0xFB -> Deneb 0x61, else the Canopus/Ares check: random < 2 -> Canopus 0x49, 2-3 -> Ares 0x4A, else ordinary; a named character already in the army (`0x20D337`) gives an ordinary encounter instead); recruit script `0x273068`-`0x27330F` (Lord flag D0, Deneb flag D1, Canopus flag D7 and `b40 067B`, Ares flag D8, Gungnir and Trooper by class). Exp `fbmove`: `r2-systems-test-fb17_map` (stage 17) + poke `4698=14` (20 wins), unit moved with `20:A:2;70:R:2;120:A:2;180:A:2;230:D:120;380:A:2;430:A:2` -> random encounter at about frame 800 with a special leader of class 92 (Gungnir) at `0x5094`, level 13. Exp `gb0`/`gb1`: battle started, leader HP poked to 1 -> "A Gungnir joined your army.", new character class 92 level 13, counter 21. Trooper, Lord, Deneb, Canopus and Ares paths were read in the code only. |
| Special units are met at random while units travel; level = leader + 6; the Echo Chime calls only ordinary monsters. | ROM `0x208F70`-`0x208FDF` (encounter routine: level = leader level + 6 at most 99; specials only in stages 17-19); Exp `fbmove` (special at level 13 with leader level 7). Exp `ec2`: Echo Chime used in the same state with counter 20 -> ordinary neutral (class 55 Cerberus, level 13, `0x52AA` = 0x65, `0x5094` empty). |
| Specials need room in the army; a full army gives an ordinary encounter. | ROM `0x208FD3`-`0x208FDF` (`call 0x20D288`; zero free places skips `0x209040`). |
| Firbolg paragraph (Cat's Tongue, Area 2, shallow water, Echo Chime). | See the section 3 rows "Cat's Tongue ..." and "Of the Free Battle Areas only Area 2 has Firbolgs ...", and the section 2 row on the Echo Chime. |
| Bond to Future at the north-west church of Free Battle Area 1 with the Lord, Lanselot, Warren, Gilbert and Canopus in the unit; link-battle item. | ROM stage 17 church #0 `0x272FFB`-`0x273067` (`b3e` 0677, 0679, 067A, 067B, 067C; `b42 BD`, so only while you do not own one; gives item 189); church #0 = location code 9 at map tiles x 40-42, y 19-21. The map's playable tiles run x 10-109, y 10-104 (a 10-tile margin on the left and top only: `0x203B9B` adds 80 px), so this is the north-west; the other two churches are at x 106-108, y 41-43 (east) and x 10-12, y 88-90 (south-west). Tr `tables/items.txt:387` ("Use in versus battles."). |
| Date secrets: conditions, areas, churches. | ROM `0x204E66`-`0x204F13` (unit-window builder: church branch; free army place; `bit 4, (0x546F)` = stage 12 cleared; Chaos >= 0x50 -> Light Priest (class 0x58), < 0x15 -> Curse Priest (class 0x5A), else nothing; day/night `0x6088` must equal 0 (Light) or 1 (Curse); `0x5490` = 10 with location index 0x10, or 6 with index 6; RTCGET month/day BCD compared with 0x2512 (25 December) or 0x0606 (6 June); then a one-entry recruit list and the Recruit bit). Location index 16 on the stage 9 map = the first church (code 17), map tiles x 83-85, y 15-17, the northernmost of the four churches (the others are at y 48-51 and y 73-75), directly west of Donant (record 1, a castle: location type 0, and Kiros says "This castle has special magic", Tr `script.txt` @26C11D; its 15 tiles are at x 102-106, y 14-16). Index 6 on the stage 5 map = church #0 (code 7), tiles x 91-93, y 15-17, on an island of snow ringed by shallow water in the north-east of the map (scratch `tmap.py 5`); its handler `0x268AD9` takes back the White Cross. Neither church is hidden (event entries). |
| Light Priest experiment. | Exp `lp3`/`lp5list`: `r2-story-late-s9_gameplay` + pokes `6108=804A8006` (unit 1 onto the church), `546F=11` (stage 12 cleared), `4694=50` (80), `6088=00` (day), `--date 12-25`, input `10:A:2;60:A:2;110:A:2;170:D:2;220:A:2;390:A:2;450:R:2;510:A:2` -> unit window with a Recruit icon; Recruit lists "Light Priest 1580". Controls without Recruit: `--date 12-24` (`lp4nodate`), Chaos 79 (`lp6cf79`), night (`lp7night`), another Shagall church (`6108=805E8028`, `lp8church18`). |
| Curse Priest experiment and recruit. | Exp `cp3`: calm stage 5 state made from `r2-story-early-test-s5_whitecross_prompt_tight` (`s5calm`, saved at frame 340), pokes `6108=80528006`, `546F=10`, `4694=14` (20), `6088=01` (night), `--date 06-06` -> Recruit lists "Curse Priest 2820". Controls without Recruit: `--date 06-07` (`cp4date0607`), day (`cp5day`), Chaos 21 (`cp6cf21`), stage 12 not cleared (`cp7notclear`). Exp `cp8recruit`: with a free place in unit 1 (`5186=0000`) the priest joins: funds 245,638 -> 242,818, new record class 90 level 10 (leader level 12). |
| Costs goth, two levels below the leader, room in unit and army. | Experiments above; ROM `0x204E43`-`0x204E4E`. |
| Light Priest -> Holy with White Vow; Curse Priest -> Exodus with Black Vow. | Section 3 item rows. |
| The player can set the date. | Section 8 row. |

## 8. Chapter saves, cheats and the console date

| Claim | Source |
|---|---|
| `Chapter saves` folder next to `zenobia.exe`, one save per chapter start and on each side of the route choices, hero Tristan, file 1. | Earlier check; Code (player) `gui.c:66` (`CATALOG_DIR`), `import_save_dialog`; `release.md` "Chapter saves and the player's guide"; `tools/release/catalog.txt` (the list of saves). |
| Each save holds the army of a test playthrough, whose battles were mostly won with a testing aid. | `tools/release/catalog.txt` header (the only aid: enemy HP set to 1 when a battle starts); `docs/workstreams/release.md` "Chapter saves". |
| The list of saves (file, note, hero's level, characters, goth, Chaos Frame). | Filled in by `tools/release/package.py` from `catalog.json`, which `tools/release/catalog.py` writes from the game's RAM when it makes each save. |
| File > Import saved game; backup first named "... (before import YYYY-MM-DD HH-MM-SS).sav"; game restarts at the title; Load, file 1. | Earlier check; Code (player) `gui.c` `import_backup_path`, `import_save` (messages "It replaces the three saved games and the suspend data ...", "Choose Load on the title screen to play it."). |
| The saves are in the player's own format, which other emulators cannot read. | Code `runtime/src/core/flash.c` (the `NGPFLSH1` record format, shared by the player and the harness's `--save`) and `runtime/src/frontend/saves.c`; `tools/release/catalog_about.txt`. |
| Importing replaces the three saves and the suspend data; import the backup to get them back. | Code (player) `gui.c` `import_save` (whole save file replaced; the backup is a normal save file of this player, accepted by `saves_check_flash_file`). |
| Cheats table, limits, one-shot. | Earlier check; `runtime/src/core/cheats.h` (comment and functions); `gui.c` `k_cheat_labels`, `use_cheat`. |
| Use cheats on the map or in menus, not in battle (untested there). | Earlier check. |
| A game in progress is needed. | Code (player) `gui.c` `use_cheat` ("Start a new game or load a saved game first ..."). |
| The clock is used only for the two date secrets after the ending. | Earlier check (RTCGET called only at `0x204EF2`); `docs/engine-notes.md` "Hardware / boot" (RTCGET buffer `0x4578`); ROM `0x204EB9` (only after stage 12 is cleared). |
| Options > Console date: The PC's date (default), 25 December, 6 June; kept in `zenobia.ini`. | Earlier check; Code (player) `gui.c` `set_console_date`, `config.c:76,227-231,272-277` (`console_date` empty by default = the PC's date; written to the ini). |

## 9. About this guide

| Claim | Source |
|---|---|
| Unofficial fan guide, not affiliated. | Code (player) `gui.c` `show_about` ("Not affiliated with the owners of the game."); Earlier check. |
| Game: Densetsu no Ogre Battle Gaiden: Zenobia no Ouji, Neo Geo Pocket Color, 2000. | Code (player) `gui.c` `show_about` ("(Neo Geo Pocket Color, 2000)"). |
| Names follow the translation and the official English releases where they exist (Warren, Canopus, Lanselot, Gilbert, Lyon, Zenobia, Zeteginea). | Tr `glossary.md` "People" and "Places". |

---

## Left out of the guide, or kept vague, because it could not be confirmed

* Where the Glass Pumpkin and the Twinkle Star come from (fan wiki: link-battle
  prizes). No one-player event gives them (no `st16 0198`/`0199` or other gift
  of items 152/153 in any handler; both have bit 3 of their item type byte set,
  which the random treasure pick skips). The guide says it could not find them.
* Where the Drago Stone, Necro Staff, Rotten Pumpkin, Black Brand, Hard
  Bokken, White Vow, Black Vow and Silver Cross come from. No stage script
  gives them and they are outside the random treasure range; perhaps spoils
  of war or link prizes, unconfirmed. The guide says it does not cover them.
* Exact chances of the rare Free Battle encounters (from the code: Deneb when
  a random byte is 251 or more, Canopus when it is 0-1, Ares when it is 2-3,
  per special-encounter roll). The guide says "rarely" / "now and then",
  since the distribution of that byte was not measured.
* What the town window's two ratings mean in words, and the numbers of the
  liberation formula; the guide gives only the direction (unit alignment
  against the town, leader class).
* The formula of the chapter bonus money (not decoded).
* The stat changes each tarot card gives when drawn, and how long the World
  card's effect lasts (the guide only repeats the game's message).
* Which part of Warren's reading (questions, answers or the drawn card)
  decides the starting stats.
* Day or night effects on battles (fan sources mention stronger monsters at
  night); not checked.
* Whether the game speed setting changes anything besides the clock (for
  example how fast units walk); only the clock was measured.
* Whether the Waltmood gift comes right after the Talos battle or on the
  next visit (see the section 3 row).
* Whether ground units can enter shallow water at all; the guide only says a
  flying unit can go there.
* What the Echo Chime does in the two areas without neutral monsters.
* Persuasion odds in numbers (`explore2-battle.md` has the formula; the
  guide gives only the main factors).
* The Trooper, Lord, Deneb, Canopus and Ares Free Battle paths were read in
  the code but not played; the Gungnir path, the Yuria's Letter and the
  Cat's Tongue rewards were played (the last two with poked values).

Checked but left out to keep the guide short: refusing Goldie costs 1 Chaos
Frame and 1 hero ALI each time (`0x269A92`); refusing the White Cross twice
costs 5 hero ALI (`0x268B91`); Lek in chapter 12 is sealed until Baldur's
envoys in eight towns are beaten (flags 0x80-0x87, `0x26E1D8`; the chapter's
opening says so); persuading neutrals leaves the win counter unchanged, and
battles against enemy units never touch it (`0x2094B0`).

## Corrections to the project docs

Writing the guide turned up a few errors in the exploration notes. They were
fixed on 2026-10-11: the event entries in `docs/engine-notes.md` "Stages and
events" (read one entry off before), the stage 0 church index in
`explore-towns.md`, the time-out rule in `explore-battle.md`, the game clock
at each game speed in `explore-map.md`, and two notes added to
`explore2-systems.md` (the recruit level and recruiting under a Necromancer
or Lich outside towns; the class-change items' missing CHA check).

## Fan wiki discrepancies (used only as leads)

* Lanselot: the wiki asks for hero ALI 55; the code checks 50 (`0x32`,
  `0x26673C`-`0x266764`).
* Warren: the wiki has no time-of-day condition; the code refuses by day
  (`0x27209E`-`0x2721EE`).
* Route names: the wiki calls the Megaholten route the "Lawful Route" and the
  other the "Chaotic Route"; the guide uses the area names, which the game
  shows.
* Free Battle page: "Enemies are scaled to 6 levels above the unit leader"
  for every map revisited after the ending. In the code only the three Free
  Battle Areas' tables use "leader + 6"; revisited story areas keep their
  fixed levels (section 2 row on neutral monsters). The same page's "rate of
  neutral encounters greatly increased" and "liberating towns has no effect"
  were not checked and are not in the guide.
