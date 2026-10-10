# Explore: organize (HQ / Organize screens)

## Goal

Play-test the English build through every HQ / Organize screen (unit list, character
list, View status, formation and placement, moving characters between units, equipping
items, class change, dismissing, leader settings, Option-button help on every icon, and
the map's "Organize screen" command and unit-window Organize command in stage 0) and
report text that is still Japanese or does not fit, so the text and graphics workstreams
can fix it.

## State

Round 1 done (2026-10-09). Every Organize screen and sub-screen was visited, with the
real stage-0 party and with test states (RAM patched: generic characters, a second
unit, items, long names). **No untranslated font text** was drawn on these screens (all
text logs are clean; the localization export flags nothing from them). The problems are
(1) two code-level RAM overruns with long English names, (2) messages and help that do
not fit the fixed-cell organize window, (3) fixed 8-cell name / class / item fields,
(4) a one-cell error in the Stock top bar, (5) pre-drawn Japanese labels. Not reached:
the unit-window "Transfer" icon and the "unit entry" prompt (see Open issues).

## Done

### Screen map

The scenario-map Organize (B on the scenario map, A on "Organize") and the stage
command bar's "Organize screen" (A on empty ground, 2nd icon, A) open the same screens.

* Top bar: "Unit / Char / Funds" = number of units, of characters, funds.
* Top-level icon menu (Left/Right wrap, Option = help, A = enter, B = back):
  1. Character -> submenu View status / Dismiss / Class change.
  2. Add character -- only when characters are in the stock (in no unit); the menu is
     built when the screen opens. Choose a unit (Left/Right: units and the stock),
     or a stock character who can lead to form a new unit, then the characters to add
     and their places; a full unit asks "This unit will be formed. Is that all right?".
  3. Remove character (to the stock; removing a leader disbands the unit, Yes/No).
  4. Swap units: list "2." ... "25." with the leaders' names (4 per page, Right = next
     page); A on one unit, A on another swaps their numbers. Silent.
  5. Formation: status screen, A on a member opens the placement grid; B asks
     "Is that all right?" + Yes/No.
  6. Leader change: members who cannot lead are marked with an X; choosing a member
     who can lead asks "Is that all right?". Unit 1 (story leader) answers "This
     unit's leader cannot be changed."
  7. Item -> submenu Use / Equip / Remove / Sell / Discard / Sort / Tidy up. Use:
     "Choose a character." or "Choose a unit.", then the status screen; Equip: item
     list, then the character (no message); Remove: the character (silent; "stock is
     full" prompt when the stock is full); Sell / Discard: "Choose a quantity.", then
     "N goth. Is that OK?" / "Is that all right?"; Sort swaps two entries; Tidy up is
     silent.
* Status screen ("View status", also the base of Add / Remove / Formation / Leader /
  Dismiss / Class change / item targets): top bar "Unit. N", leader name, cost "GOTH",
  move type (or "Stock N" for characters in no unit); Left/Right = next unit / stock,
  Up/Down = member. Pane: portrait with size badge (S / L), name, class, Lv, HP, the six
  stats, COST, NEXTLv/EXP, F:/B: attacks, MOVE, ITEM, "Leader: OK/No". Field labels are
  pre-drawn English graphics. During a stage the left pane of a deployed unit has a
  pre-drawn Japanese label meaning "dispatched", and deployed units cannot be changed
  (A does nothing, no message).
* Class change: the left pane marks each member "OK!", "UP OK!" or "BAD" (pre-drawn
  English); A on an OK member lists the classes it can change to; choosing one asks
  "Change class to <class>. Is that OK?" + Yes/No.
* Dismiss: story characters (class byte bit 7 set) "cannot be dismissed", a unit
  leader neither; others ask "You will lose this character. Is that all right?".
* Stage unit window (A on HQ, Right, A; or A on a unit): Move / Battle commands /
  Organize. Organize submenu: Formation / Dismiss / (Leader change, only when the
  leader is not a story character) / Class change. These screens use the window
  renderer, so their VWF messages and help fit.

### Class change rules (from the code; numbers left in the ROM)

* Checked at `0x20D2A6` for character n (record `0x4698 + 18 n`). The possible targets
  of class c are the c-th zero-terminated list at `0x20E8FE`; each target class t
  has 4 requirement bytes at `0x20E9DD + 4 t`: minimum level, minimum and maximum
  alignment (ALI), minimum charisma (CHA). Changing back to the base class (Fighter,
  Amazon) has no requirement. Class 23 has an extra rule.
* A unit leader cannot take a class that cannot lead (`0x202E9D`). Story characters'
  unique classes have no targets ("BAD"). Some items mention class changes ("Use it on
  a ...?"); not tested. Observed: a Fighter (Lv 10, all stats 90) can become Knight,
  Samurai or Ranger; a Knight Lv 20 General, Paladin, Dragoon (or Fighter); a Samurai
  Lv 20 Samurai Master.

### Findings

1. **RAM overrun: leader names of 11+ letters** (critical). The top-bar composer pads
   the leader name to 11 cells: `0x21337D ld.b A, 0xB / sub.b A, C / ldir.b /
   ld.b (XIX+), 1 / djnz A`. With 11 or 12 letters the 8-bit count wraps and about 256
   spaces are written from `0x6000` (up to about `0x6118`). Seen on the status screen
   (caller `0x2136D8`) and on the new-unit top bar (caller `0x212BCC`). In stage 0
   (Organize screen from the command bar) this wipes the map data in `0x6080`-`0x6110`:
   back on the map the screen is white and "You found buried treasure!" pops up at
   once. 10 names in `tables/names.txt` have 11-12 letters. Same family as the
   item-list overrun at `0x215816` found by the towns workstream (item names of 10+
   letters; also on the Organize Item lists).
2. **Organize-screen messages are drawn in fixed 8x8 cells** (high). The organize
   screen shows messages and Option help through the script routine `0x21347A`
   (pointer in task var 0x20) which prints with `0x200B72` (caller `0x213495`) at map
   `0x9382`: 18 cells x 3 lines; with a Yes/No prompt only 2 lines are free. The remap
   hook for `0x200B72` ignores the VWF flag, so `sysmsg` lines over 18 letters run over
   the right frame and off screen, often losing the key word ("A large character / be
   added to this un..."). The same strings are shown by the window renderer elsewhere
   (unit window, map), so 18 fixed cells per line works for both. List and suggested
   English in "Open issues".
3. **Class-change confirmation on the Organize screen** (composed in `0x6000`, drawn via
   `0x213152` -> `0x21347A`): the VWF marker `0xDB` is drawn as a blank cell and the
   second line "<class>. Is that OK?" is cut ("Samurai Master. Is").
4. **Fixed name / class / item fields** (high): status pane name, class and ITEM fields
   8 cells (columns 11-18); top-bar leader name 8 cells; Swap-units list 8 cells; unit
   window title 9 cells; class-change list 10 cells (Organize, from column 9) and
   9 cells (unit window, from column 6); NEXT unit list 11 cells. Longer English runs
   over the frames (screenshots in the evidence folder, see below). 107 names, 32 class
   entries and 157 item names are longer than 8 letters.
5. **Stock top bar one cell too long** (`msg_stock_label`; the patch at `0x213644`
   copies 6 bytes "Stock " where the original copies 5): the two blank glyphs land on
   columns 18-19, so the left half of the GOTH graphic ("GO") stays at column 17 and
   the top-right frame border is erased.
6. **Pre-drawn Japanese labels**: the 7 + 3 + 7 organize icon labels and the unit
   window labels are covered by the gfx-labels workstream. New: the "dispatched" label
   above a deployed unit's formation on the stage status screen: 5 sprite tiles
   (`0x13B`-`0x13F`, palette 8, x 8-47, y 54), uncompressed 2bpp at ROM `0x214A00`
   (80 bytes; a copy at `0x2E736A`); the text part is 3 tiles between two bracket
   tiles.
7. Deploy list (stage command bar "Deploy", map workstream): the move type field is 5
   cells (from column 14), so "Plains" puts its "s" on the right border.
8. Style: "Unit. 1" copies the original's period (5-byte label `0x2133A3`).

## How to test / reproduce

Harness: the stable snapshot in the session scratch area (`snap\ngp_harness.exe`,
`snap\ogre_en.ngc`). Text logs: `build/textlogs/organize-*.txt`. States:
`build/states/organize-*.state`. The original game runs from the same states
(`rom/baserom.ngc`); leave Organize and re-enter it first so the original font loads.

States from real play (story start: Estrada, Kain, the hero in unit 1; 30000 goth):

| State | Screen | Made from |
|---|---|---|
| `organize-top` | scenario-map Organize, top menu, cursor on Character | `hq_status_screen` + `40:B:2;100:B:2`, frame 170 |
| `organize-charsub` | Character submenu | `organize-top` + `10:A:2`, frame 55 |
| `organize-items` | Item submenu (stock empty) | `organize-top` + `10:L:2;50:A:2`, frame 140 |
| `organize-dismiss-prompt` | "cannot be dismissed" on Kain | `organize-charsub` + `10:R:2;50:A:2;110:D:2;150:A:2`, frame 280 |
| `organize-s0-top` | stage 0, Organize screen from the command bar | `command_bar_forecast` + `10:L:2;40:L:2;70:L:2;110:A:2`, frame 250 |
| `organize-uw-organize` | stage 0 unit window, cursor on Organize | `stage0_gameplay` + `46:A:2;90:R:2;130:A:2;200:R:2;240:R:2`, frame 275 |

Test states (RAM patched with `scratchpad\organize\statepatch.py`; not reachable this
early in real play):

| State | Content |
|---|---|
| `organize-test-stock2-top` | 2 story-flagged stock characters with long names (Christensen, Penthesilea); menu has Add |
| `organize-test-rich-top` | top menu with Add; stock: Abel (Knight), Adam (Amazon), Axe (Golem, large), Allen (Cleric), all generic; items Cure Ankh x2, Soul Call, Chaos Up, Gauge Up, Durandal, Plains |
| `organize-test-rich-dismiss-prompt` | "You will lose this character..." on Adam |
| `organize-test-2units` | scenario map, popup on Organize: unit 1 (5 members), unit 2 (Allen, Axe) |
| `organize-test-unit1-full`, `organize-test-unit1-four` | top menu; unit 1 with 5 / 4 members, rest in the stock |
| `organize-test-cc-samurai` | Character submenu; Kain = Samurai Lv 20 (class list shows Samurai Master) |
| `organize-test-uw-samurai` | stage 0 unit window on Organize; Kain = Samurai Lv 20 |
| `organize-test-items-short` | Item submenu; Durandal, Soul Call x2, Cure Ankh, Lava Axe, Dark Axe (names under 10 letters) |
| `organize-test-stockfull` | Item submenu; 60 stock entries, Estrada holds Durandal (Remove -> "stock is full") |
| `organize-test-equip-long` | Character submenu; equipped items with 15-letter names |
| `organize-test-longleader` | Character submenu; Estrada renamed Rhadamanthys: View status overruns RAM |
| `organize-test-s0-longleader` | stage 0 Organize; same name: View status, then back to the map breaks it |
| `organize-test-s0-2units` | stage 0; unit 2 (Abel, Adam) at HQ, not deployed (command bar shows Deploy) |
| `organize-test-s0-2deployed` | stage 0; unit 2 deployed at HQ |

RAM used for the patches (state file offset = 192 + address): character count `0x4692`,
unit count `0x4693`, funds `0x468E`; character records 18 bytes from `0x46AA` (hero
first): +0 class (bit 7 = story character), +1 level, +2 name index (12 bits), +4 HP,
+6 max HP, +8 STR AGI INT CHA ALI LUK, +17 equipped item; units 12 bytes from `0x517E`:
5 x (character number, position), then 0, 7 (unit 1 = `0x517E`, unit 2 = `0x518A`);
item stock 60 x (item, count) from `0x538E`.

Inputs: Right/Left between icons (40 frames apart is safe), Option = help (A closes),
A = enter, B = back. All top-level help: `10:O:2;110:A:2;160:R:2` every 200 frames
from `organize-top`. Scripts: `scratchpad\organize\run.py NAME STATE FRAMES INPUT`
(text log + coverage verdict per string + contact sheet), `annotate.py`, `statepatch.py`,
`labels.py`; screenshots of every finding in `scratchpad\organize\evidence\`.

## Open issues

Suggested English (our own wording) for the fixed-cell organize window, at most 18
letters per line, 3 lines (2 when Yes/No follows):

| Address | Use | Suggestion |
|---|---|---|
| `2C3F1D` | help Character | Dismiss characters / or change their / class. |
| `2C3F3B` | help Add | Add characters to / a unit, or form a / new unit. |
| `2C3F5F` | help Remove | Removes a member. / Removing a leader / disbands the unit. |
| `2C3F87` | help Swap units | Swaps the numbers / of two units. |
| `2C3FB4` | help Leader | Changes the / unit's leader. |
| `2C3FC9` | help Item | Use or equip the / items you carry. |
| `2C3FE6` | help View status | Shows the status / of a character. |
| `2C4004` | help Dismiss | Dismisses a / character. |
| `2C4015` | help Class change | Changes a / character's class. |
| `2C403B` | help Use item | "Use item" / Uses an item you / are carrying. |
| `2C405E` | help Equip item | "Equip item" / Equips a weapon, / armor and so on. |
| `2C408C` | help Remove item | "Remove item" / Takes off an / equipped item. |
| `2C40AC` | help Sell item | "Sell item" / Sells an item you / are carrying. |
| `2C40CC` | help Discard item | "Discard item" / Throws an item / away. |
| `2C40E3` | help Sort | "Sort" / Changes the order / of your items. |
| `2C40FB` | help Tidy up | "Tidy up" / Packs scattered / items together. |
| `202E46` | dismiss (Yes/No) | You will lose this / character. OK? |
| `202E67` | dismiss refused | You cannot dismiss / this character. |
| `202E82` | dismiss refused | You cannot dismiss / a unit leader. |
| `202E9D` | class change refused | A leader can't / change to a class / that cannot lead. |
| `20CDD6` | add refused (not seen live; code `0x212859`) | To add a character / here, change this / unit's formation. |
| `20CE75` | add refused | The unit is full. / Max. 5 members; a / large one takes 2. |
| `212B21` | add | Choose a character / to add. |
| `212B3D` | form refused | This character / can't lead a unit. |
| `212B58` | form (Yes/No) | This unit will be / formed. All right? |
| `212B72` | add refused | A large character / can't be added to / this unit. |
| `212CD9` | remove refused | This character / can't be removed. |
| `212CF8` | remove leader (Yes/No) | Removing a leader / disbands the unit. |
| `214279` | unit entry (Yes/No; not seen) | End unit entry. / Is that all right? |
| `215F11` | stock full (Yes/No) | Stock is full. / Discard something? |
| `215F3C` | item target | Choose a character (or: Pick a character.) |
| `215F5E` | item refused | This item can't be / used on the / organize screen. |
| `216122`, `21664D`, `21666F` | item refused | Can't be used on / the stock. (this unit. / this character.) |

Fit already: `2C3F9B`, `202E5D`, `212B96`, `212FE4`, `215EBF`, `215F2E`, `215F4E`, the
sell price prompt and Yes/No. Alternative to rewording: let the `0x200B72` hook draw
remapped strings with the VWF when called from `0x213495` (window of 18 x 3 cells,
tiles from map `0x9382`), which would also fix the class-change line.

Other open points:
* Class-change confirmation (finding 3): e.g. `msg_classchange` "?" so that the second
  line is "<class>?" (16 cells at most), and skip a leading `0xDB` in the `0x200B72`
  hook for RAM strings.
* Names / classes / items (findings 1, 4): either cap list names (8 letters for the
  status, top-bar and swap fields, 10 at most to avoid the overrun) or clamp the copies
  in code (`0x21337D` like the towns workstream's item-list fix) and use the VWF where
  a field is drawn by the window renderer.
* Stock top bar (finding 5): restore the 5-byte head ("Stock") at `0x213644`, or drop
  one space from the tail.
* Not reached: the unit-window "Transfer" icon (did not appear with two units at or
  next to HQ; its help `2C3E77` fits in the window) and `214279` "End the unit entry"
  (called at `0x21418E`; probably link-battle unit registration).

## Next steps

* Re-test with the next patch build: the organize help/messages, the class-change line,
  the Stock top bar, and the long-name states (`organize-test-longleader`,
  `organize-test-s0-longleader`) must no longer corrupt RAM.
* Reach "Transfer" (two units side by side away from HQ) and the link-battle unit entry.
* Class changes by item ("Use it on a ...?") and the Lich special case.
