# Explore 2: game systems (round 2 play-test)

## Goal

Play-test the game systems of the English build with real play (and RAM-patched
test states where real play cannot reach a case): shops in several towns
(buy, sell, prices), churches (Rite of Revival), recruiting (HQ and towns),
class change for every reachable class, items (use / equip / unequip / sell /
discard / sort / tidy up, every item type, the item help and every item
description), the 22 tarot cards (command bar list, drawn messages and
effects, use in battle), persuading neutrals, the Monitor settings, Option
help on every icon and menu, and the link-battle menus as far as one player
can go. Check every message window for fit and wording.

## State

Round 2 done (2026-10-09), on the stable snapshot `snap2` (English ROM SHA-1
`e63bffd1...`, with the round-1 play-test fixes). Every area of the goal was
reached; what one player cannot reach is listed under "Not reached".

Summary: no untranslated text was drawn by the two text renderers in any of
these runs (decoded logs and the localization export agree), no crash, and
the round-1 RAM overruns stay fixed (item lists with long names, long leader
names: the map is intact afterwards). The problems left are fixed-width name
fields (item list, recruit list, class lists, status panes), a handful of
wording issues, and cosmetic font mixing. Two of the field problems have a
one-line fix that was verified in a scratch test ROM (Open issues 2 and 3).

## Done

### Round-1 fixes verified in play

* Items list (map Items and organize Item): no RAM corruption with long
  names (`patch/src/textfix.asm` `item_name10`); names are now cut at 10
  letters (see Open issue 1).
* Status / new-unit top bar: an 11-12 letter leader name no longer overruns
  RAM (`name_top8`); "Rhadamanthys" shows as "Rhadaman" and the stage map is
  intact afterwards.
* Shop list (`0x207447`) and tarot list (`0x208A58`, command bar and the
  "stock full" discard list) are variable-width: every shop list (shops 0-19)
  and every card name fits.
* Organize-screen messages and help (fixed 8x8 cells, printer `0x200B72`
  from `0x213495`) now fit in 18 cells: item command help, organize command
  help, "Pick a character.", "This item can't be / used on the / organize
  screen.", "It can't be used / on this character.", class-change prompt.
* Monitor help (5 rows) is English and fits.

### Shops

* Leckart (stage 1, real play): Buy items icon, Option help, list with
  variable-width names and fixed-cell prices (10 x the item record's price),
  Option on a list entry shows the item description, quantity prompt (Down =
  +1, Up = -1, Left = +10, Right = -10), "8400 goth. / Is that OK?" + Yes/No,
  funds deducted, the shop closes after each purchase (original behavior).
  "You don't have enough funds / to buy this item." and "Your item stock is
  full. / You can't buy any more." fit.
* All 20 shop lists (shop number at `0x61D9` patched in the Leckart unit
  window state; stock lists `0x21713A + 5 * shop`): every name and every
  price (up to "Love & Peace 50000", "Vessel of Fate 21000") fits.
* Jack's shop (Trade Ticket): Jack's line, list, quantity, "30000 goth." OK.
* Funds of 8 digits fit the shop and recruit funds boxes.
* Selling from the map Items command: quantity, "351900 goth. / Is that OK?"
  (6 digits) fits.

### Church (Rite of Revival)

Stage 0 church with a dead member and a patched cost: Option help "Revives
incapacitated / characters.", member selection, "Reviving costs 900 goth. /
Is that OK?" + Yes/No, revival animation (no text, as in the original), and
"You don't have enough funds." with low funds. Soul Call on the dead member
works silently; on a living member: "It can't be used / on this character."

### Recruiting

* Leckart (town) and Karkov (stage 2 HQ): list, funds, placement in the
  formation grid, cost deducted; "The unit is full. / 5 members at most; /
  large ones take 2."; "You don't have enough funds / to add this unit."
  (wording, Open issue 6).
* The recruitable classes come from the unit leader's class (lists of class
  ids at `0x20E7FA`, one zero-terminated list per class, copied to
  `0x4578`, count `0x457F`, at unit-window build time `0x204F4A`). Lists
  checked by patching the leader's class: General, Dragoon, Revenger, Beast
  Master, Lich, Hagal, Enigma Hunter, Holy, Exodus, Lord, Witch (97). Long
  names collide with the cost column (Open issue 2).
* Recruits arrive two levels below the unit's leader, at least level 1
  (`0x204E43`-`0x204E4E`, stored at `0x4580`; a level 12 leader recruited a
  level 10 Curse Priest).
* A unit led by a Necromancer (class 0x16) or a Lich (0x17) also gets
  Recruit outside towns and churches: on a tile that is not a location the
  unit-window builder (`0x204E77` -> `0x204F16`) allows the recruit path
  `0x204F2A` for these two leader classes only. Checked on a plains tile of
  stage 9 with the leader's class poked to Necromancer: the window gained a
  fourth icon, Recruit, listing "Skeleton 180, Ghost 180". The game's help
  text ("Only possible while the unit is in a town.") does not mention it.

### Class change

* Every class that a class change can reach (56 targets) was shown in the
  class list and in its confirmation, on the organize screen (fixed cells)
  and from the stage unit window (variable width): 40 configurations of Kain
  (record `0x46BC`: class, level 40, CHA 100, ALI per config; computed from
  the target lists `0x20E8FE` and requirements `0x20E9DD + 4 * class`),
  71 prompts per path, all matching the expected targets. Every prompt fits:
  "Change class to / Platinum Dragon? / Yes No" (organize: B cancels; unit
  window: B is ignored, move to No).
* The lists overflow for long names (Open issues 3, 4); the status panes too
  (Open issue 5).
* Class change by item (Drago Stone on a Beast Master): silent, the item is
  used up (original behavior). Equipment has no class restriction.
* The class-change items check the target class's level and alignment
  range but never its minimum CHA: at `0x2165FA`-`0x2165FF` the code loads
  (`ld.b A, (XDE)`) where a compare belongs, and the following `jrl C`
  reuses the carry of the alignment compare. A Light Priest with CHA 10 and
  ALI 95 became a Holy (CHA minimum 70) with the White Vow. A quirk of the
  original code; the player's guide says only that level and CHA do not
  matter for these items.

### Items

* All 189 item descriptions (Option on the item list) were displayed and fit
  in 3 lines (`build/textlogs/r2-systems-desc1..4.txt`), including the long
  stat lines (Kiryu Horn, Elder Sign).
* Item command help, map and organize (7 each): English and fit.
* Use, every item type: healing (Cure Potion, Cure Stone, Cure Ankh), Soul
  Call, Echo Chime (calls a neutral: "<leader>'s unit has encountered a
  neutral character." and a battle), Return Half, Joker Card, Dowsing Rod,
  Trade Ticket, 7-League Boots ("Choose a destination."), Crystal Ball,
  Love & Peace ("Choose a unit."), equipment ("Nothing happened."), stat
  items, quest items, Chaos Up/Down, battle items ("Nothing happened.");
  silent ones as in the original (Wonder Egg, Full Moon Stone, All Summons,
  Trojan Horse, Scent of Night, Light's Whisper, Chaos Up/Down).
* Equip / unequip (map and organize), sell, discard ("Is that all right?"),
  sort, tidy up, stock full on a found item ("The stock is full. / Discard
  something?" then "You obtained ..." or "You gave up ...").

### Tarot cards

* Command bar Tarot list with all 22 cards (4 per page, variable width): card
  art and description for each card, all fit.
* Drawn on liberation, all 22 cards: "You drew the card “X”." and the effect
  message of each ("Characters' STR / went up by 1 point.", "Characters' HP
  and max HP / went up by 2 points.", "The Chaos Frame / went down by 2
  points.", World: "From now on, tarot card / effects apply to every /
  deployed unit."; Moon and Sun only change the time of day), "Keep this
  tarot card in stock?", full stock: "Your tarot stock is full. / Discard
  one?", list, "Is that all right?". The card is chosen at `0x208C86`:
  card = ((byte `0x4572` x 22) >> 8) + 1, so the press frame of "Yes" picks
  it (table under How to test).
* Battle: each of the 22 cards used from the in-battle command bar (Option
  help in the 9 x 3 box, card art, effect): all help texts fit; the effects
  draw no text.

### Persuading neutrals

Stage 1 neutral battle: Option help fits; with the hero's CHA, ALI and LUK at
100 (also patched in the battle copies at `0x58C8 + 18 * k`, +7 CHA, +9 LUK)
eight attempts still failed ("miss"). In a scratch test ROM with the check
forced (`0x2C78DF` jr C -> jr T): "Persuasion / succeeded!" fits, the battle
ends at once and the map follows, no further message.

### Monitor, Option help, popup, other flows

* Monitor (scenario popup and command bar): help for all 5 rows. Option
  toggles the help (show / hide); Up/Down only move while it is hidden.
* Option help on: map command bar (stage 0, and stage 1 with Deploy), unit
  window (Move, Battle commands, Recruit, Buy items, Rite of Revival,
  Organize; submenu Formation, Dismiss, Leader change, Class change), Items
  sub-bar (map and organize), organize top icons and Character submenu,
  in-battle command bar and tactics, scenario popup (Organize, Monitor, Data,
  Link) and the Data submenu (Save, Load). All English and fitting.
* Leader change in unit 2's Organize submenu: O/X marks, "Is that all right?".
* Running out of funds at the day change (patched costs): "Income & Expenses"
  with a negative total, "You don't have enough funds. / Choose a character
  from a / deployed unit to recall.", the unit window shows the unit's cost,
  "This character cannot / be recalled.", "Choosing the leader recalls / the
  whole unit. Is that OK?", the window again with the new total. All fit.

### Link battle (one player)

Scenario popup -> Link -> "Will save after / linking. OK?" -> Yes opens link
menu B (icon bar Versus / Send chars / Get chars / Send items / Get items;
labels are the known pre-drawn labels 24-26, 2B, 2C of the labels workstream,
seen in play here for the first time; Option shows nothing). Versus: "Warning!
Check / your characters, / items and tarots." then "You can't receive / when
full."; every icon then tries to connect: "Please wait." -> "Please try
again." -> back to the scenario popup. Link menu A (rules, register, custom),
the settings screens and the battle record need a partner.

### Not reached

* Link menu A and everything after a successful connection (needs a partner).
* Command bar "Return to map" (bit 8 of the command mask comes from `0x6089`,
  set from saved stage data; not set in Free Battle Area 1 entered with the
  stage-jump aid) and its help.
* The unit-window "Transfer" command (entry 9 at `0x205EDD`, help
  `0x2C3E77`, messages `0x206011`, `0x206029`, `0x206044`): no code sets its
  bit in the command mask, so it looks unused.
* A natural persuasion success (see above).

## How to test / reproduce

Harness: `scratch\snap2\ngp_harness.exe` with `scratch\snap2\ogre_en.ngc`.
Helpers in `scratch\r2-systems\` (scratch, not committed):

* `run.py NAME STATE FRAMES INPUT [--every K] [--shots F,..] [--save F NAME]
  [--patch A=HEX|stock=ID:Q,..|funds=N|tarot=N,..] [--ram] [--rom PATH]
  [--ja] [--nolog]`: runs the harness, writes `build/textlogs/
  r2-systems-NAME.txt`, frames and a labeled `sheet.png` in `runs/NAME/`,
  prints the decoded log (remapped ROM strings shown in English).
* `mkstate.py IN OUT patches...` (test states `r2-systems-test-OUT`),
  `view.py RUN F,F x0 y0 x1 y1` (crops), `desc_run.py` (item help),
  `use_run.py` (use items), `ccdata.py` / `cc_run.py org|uw` (class change),
  `tarot_list_run.py`, `btarot_run.py` (battle tarot), `gamedata.py` (item
  records, shop lists), `dbdump.py` (rows of the local database),
  `scensteer.py` (scenario-map cursor, a copy of the progress workstream's
  tool pointed at `snap2`).
* Scratch-only test ROMs (copies of the snapshot ROM with bytes changed, never
  used for the logs in `build/textlogs`): `tmp\persuade_test.ngc`
  (`0x2C78DF` = `0x68`, persuasion always succeeds) and
  `tmp\vwflists_test.ngc` (`0x2057A9` = `1D 2A 40 37 00` and `0x206195` =
  `1D 2A 40 37`: calls to `list_vwf_start` at `0x37402A` of that build).

States (`build/states/`):

| State | What | Use |
|---|---|---|
| `r2-systems-draw_prompt` | "Draw a tarot card?" after the stage 0 church liberation (real play) | `F:A:2`, then A every 100 frames; F picks the card: 10 Strength, 11 Death, 12 Fool, 13 Moon, 14 Tower, 17 Chariot, 18 Emperor, 19 Judgment, 20 Justice, 21 Empress, 23 Temperance, 25 Hierophant, 29 Sun, 33 Magician, 36 Hanged Man, 39 Priestess, 44 Star, 45 Devil, 47 Hermit, 55 Fortune, 73 Lovers, 78 World |
| `r2-systems-test-draw_tarotfull` | same with 14 cards in stock | `10:A:2`, A every 100 |
| `r2-systems-link_menu` | link menu B, cursor on Versus (real play) | A, Right |
| `r2-systems-persuade_battle` | stage 1 neutral battle just started | `20:A:2;80:L:2;160:A:2` = Persuade |
| `r2-systems-test-items_1_60`, `_61_120`, `_121_180`, `_181_189` | map Items sub-bar, those items x1 | `20:A:2`, then Option / A / Down per item, Right per page of 4 |
| `r2-systems-test-cc_fighter_ali50` | organize Character submenu, Kain Fighter Lv 40 | `20:R:2;60:R:2;100:A:2;180:D:2;240:A:2` = class list |
| `r2-systems-test-cc_uw_dragon_ali65` | stage 0 unit window on Organize, Kain Dragon Lv 40 | `20:A:2;100:R:2;140:R:2;220:A:2;300:R:2;340:U:2;400:A:2` = class list |
| `r2-systems-test-btarot_1_14`, `_15_22` | "FIGHT IT OUT!" at Gring with those cards in stock | `100:A:2;160:A:2` = in-battle tarot list |
| `r2-systems-test-shop7_funds` | Leckart unit window, shop 7, funds 99999 | `20:R:2;50:R:2;80:R:2;120:A:2` |
| `r2-systems-test-recruit_dragoon` | Leckart, 4 members, leader a Dragoon | `20:B:2;80:A:2;130:R:2;170:A:2;240:R:2;270:R:2;310:A:2` |
| `r2-systems-test-bankrupt_recall` | negative funds after the day change (patched costs and clock) | `20:A:2;80:A:2;130:D:2;160:D:2;200:A:2;280:A:2;340:R:2;380:A:2` |
| `r2-systems-test-bankrupt_leader` | same, Estrada not a story character | as above with a second Right: leader recall prompt |
| `r2-systems-test-fb17_map` | Free Battle Area 1 start (stage-jump aid) | command bar |

Other inputs: Leckart shop `towns-s1_leckart_unitwin` + `20:R:2;50:R:2;80:R:2;
120:A:2`, other shops with `--patch 61D9=NN`; revival `towns-s0_church_
unitwin_dead` + `20:R:2;60:R:2;100:A:2;180:A:2`; recruit lists
`towns-s1_leckart_unitwin_4members` + `--patch 46AA=<class|0x80>` and the
dragoon input above; Monitor help `data-popup_monitor` + per row `O`, `O`
80 frames later, `D`; link `progress-scenario_after_stage2_popup` +
`20:L:2;80:A:2;160:A:2`. Text logs: `build/textlogs/r2-systems-*.txt`
(grouped runs in `r2-systems-use.txt`, `-shops.txt`, `-recruit-lists.txt`,
`-cc-org.txt`, `-cc-uw.txt`, `-tarot-draw.txt`, `-btarot.txt`, `-link.txt`).

## Open issues

1. **Items list: names cut at 10 letters** (123 of 189 names, e.g. "Cure
   Potio", "Love & Pea", "Sword Symb", "Musashi's "). Every list from the
   composer `0x2157C0` (map Items, drawn by the window renderer from
   `0x207287`; organize Item, uiprint from `0x213DEE`; the stock-full
   discard list). The name and the quantity are one string ("name, pad to 10
   cells, quantity"), so the shop-list fix (variable-width marker) would
   misalign the quantity. Options: draw the quantity separately (as the shop
   does with its prices), add a "move to cell N" control to the
   variable-width renderer and write it instead of the padding, or give each
   item a short list name of at most 10 letters. In the variable-width font
   every item name is at most 72 px (9 cells).
2. **Recruit list: long class names run into the cost** ("Platinum Dr1720",
   "Black Drago1600", "Black Knigh1160", "Skeleton Kni450", "Mad
   Hallowee200"; a Dragoon leader in normal play). Names are drawn by the
   window renderer from `0x6000` (`0x205915`), costs separately by uiprint
   (`0x20594C`), so the shop-list fix applies unchanged; verified in a
   scratch test ROM (all names fit, selection and placement unchanged):
   `.org 0x2057A9` / `call list_vwf_start` / `.db 0` (was `ld.l XIX,
   0x6000`).
3. **Unit-window class-change list: names of 10+ letters run over the right
   frame** (16 targets, e.g. "Samurai Master", "Platinum Dragon", "Red
   Dragon", "Salamander"). Drawn by the window renderer from `0x6000`
   (`0x2061D2`); verified in the same test ROM: `.org 0x206195` / `call
   list_vwf_start` (was `lda XIX, (0x6000)`, 4 bytes). Every class name is
   at most 68 px in the variable-width font.
4. **Organize class-change list: names of 11+ letters put the 11th letter on
   the frame** (12 targets: Black Knight, Samurai Master, Ninja Master, Beast
   Tamer, Beast Master, Dragon Tamer, Dragon Master, Doll Master, Platinum
   Dragon, Black Dragon, Death Bahamut, Silver Knight). Drawn by uiprint
   (`0x213088`, 10 cells from column 9), which has no variable-width mode.
5. **Status panes: class and item names over 8 letters overflow** (known
   field problem, now measured): organize status pane (uiprint `0x213745`;
   ITEM field still "Musashi'" + "s" on the frame) and the map character
   window shown when using or equipping an item (window renderer, `0x2053BC`
   / `0x2053C4`, composer `0x20D42B` shared with the organize pane):
   "Platinum Dra" runs about 4 cells past the frame. 31 class names exceed 8
   letters. With the variable-width font all but Platinum Dragon (68 px),
   Skeleton Knight (67) and Samurai Master (65) fit 64 px.
6. Wording (suggestions are our own English):
   * `0x20588E` (recruiting with low funds): "to add this unit" reads as a
     whole unit; suggest "You don't have enough funds / to recruit this
     character."
   * `0x2E3BC0`: "Will save after / linking. OK?" has no subject; suggest
     "Saves after the / link. All right?" (16 cells per line).
   * `0x2E410B`: "tarots" is not idiomatic; suggest "Warning! Check / your
     characters, / items and cards."
   * `0x2C3D15` (command bar help): "settlement of accounts" is stiff and
     does not match the window title; suggest "Shows the expected / income
     and expenses."
   * `0x20F7A8` (Hierophant battle help): "Puts enemies / to sleep and /
     helpless." is ungrammatical; suggest "Puts enemies / to sleep, so / they
     can't act." (each line at most 72 px).
   * Item 24 description: "Ishtar goddess of war" needs a comma ("Ishtar,
     goddess of war"); item 20: "an ancient sky folk" -> "the ancient sky
     people".
   * Consistency: "Pick a character." (`0x215F3C`, shortened to fit 18 cells)
     next to "Choose a unit." (`0x215F4E`) and "Choose a destination."; e.g.
     "Pick a unit." / "Pick a destination.", or keep.
   * `0x2C3D68` (help of the unreached "Return to map" command): "Quits the
     game" may alarm players; the original means it interrupts the map;
     suggest "Leaves this map and returns / to the map select screen."
   * Item 12 description uses "opinion leader" (series term for the army's
     leader): add it to the glossary or say "the leader".
7. Cosmetic:
   * Tarot card descriptions (`0x21BDB4`-`0x21C0A7`) and the composed
     "drew the card" / "obtained" messages open with a curly quote and close
     with the straight one (the font has no closing curly quote).
   * Quantity prompt: the first "01" is variable width, later values are
     redrawn in fixed cells ("0 2"); shop and sell price prompts stay in
     fixed cells while the other prompts are variable width (by design of
     `msg_price`).
   * In-battle tarot list mixes fixed-cell and variable-width names
     ("Magician" letter-spaced next to "Priestess").
8. Pre-drawn labels: link menu B labels (Versus, Send chars, Get chars, Send
   items, Get items) were seen in play (state `r2-systems-link_menu`) for the
   labels workstream; no other new pre-drawn Japanese graphics were found.

## Next steps

* Apply the two verified hooks (Open issues 2, 3) and decide the item-list
  approach (issue 1); then re-run `cc_run.py uw`, the recruit lists and the
  item lists.
* Decide the status-pane fields (issue 5): variable-width class/name for the
  map window, and either variable width in uiprint or short names for the
  organize pane.
* Try a natural persuasion success again (find which combatant is the
  persuader in `0x2C79F5`) and see whether the neutral joins the army.
* Reach "Return to map" (find what sets `0x6089`) and a link partner (two
  harness instances) for link menu A and the settings screens.
