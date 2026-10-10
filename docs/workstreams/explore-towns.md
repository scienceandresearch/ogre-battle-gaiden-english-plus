# Explore: towns and services

## Goal

Play-test the English build in the areas "towns and services" and list every
string that is still Japanese or does not fit: shops (buying, selling, price
and quantity prompts, stock full), churches (reviving, cost prompt), visiting
towns with a unit (town events and dialogue), the map command bar "Items"
(use / equip; targets unit, character or stock) and "Tarot cards" (use /
stock). Record how to reach each screen so later sessions can go straight
there.

## State

Round 1 done (2026-10-09). Every service in the area was reached and checked:
Jack's shop and a town shop (stage 1, Leckart), all Items sub-commands, the
Tarot cards list, church liberation and the Rite of Revival, recruiting, and
the town events of the church, Hind and Leckart. No text drawn by the two
renderers is still Japanese in this area; the problems are one critical
crash bug, fixed-width fields that are too narrow for the English names, and
pre-drawn Japanese labels (see Open issues).

## Done

### How the services work (from the code)

* **Shops.** One shop town per stage from stage 1 on: the location record's
  byte +9 holds the shop number (= stage number): stage 1 Leckart (tile
  (7,39)), stage 2 Colomban, stage 3 Linde, stage 4 Isrand, ... Stage 0 has
  no shop. A unit standing in that town gets a "Buy items" icon in its unit
  window (code at `0x204F6F` sets `0x61D9` = shop number and enables entry 3
  of the unit command table at `0x2050A5`; the HQ does not qualify); the shop
  routine is `0x207407`. Stock lists: 5 item numbers per shop at
  `0x21713A + 5 * shop`. The shop closes after each purchase.
* **Jack's shop** = shop 0, reached by using the item "Trade Ticket"
  (item 11): the item-use dispatcher `0x215F99` (jump table at `0x215FBD`,
  one script per item) shows Jack's line, sets `0x61D9 = 0` and jumps to the
  same shop routine. Jack sells Sword Symbol, Magus Paper, Speed Gear, Life
  Source, Vessel of Fate; the ticket is used up.
* **Churches** ("Roshfol Church" for every church) are location indexes past
  the last record (stage 0: index 5, tile (16,17), south-west of Estoa).
  Liberating one draws a tarot card. A unit standing in a church with a dead
  member gets the unit-window icon "Rite of Revival" (pre-drawn label; table
  entry 4, `0x2059F9`); the cost is 3 x the character's cost field (word at
  `0x46A6 + 18 * n`), so the stage 0 characters revive for 0 goth.
* **Recruiting** ("Recruit characters" icon in some towns, entry 2,
  `0x205798`): list of class + cost, then the position in the unit; no
  confirmation text.
* **RAM**: item stock = 60 entries `[item id][count]` at `0x538E` (count 0 =
  empty); tarot stock = 14 bytes at `0x5406`-`0x5413`; funds = 32-bit at
  `0x468E`; characters = 18-byte records, HP at `0x469C + 18 * n`, max HP at
  `+2`, cost at `+10`; units = 12-byte records at `0x517E + 12 * u` (5 x
  `[character][position]`).

### Screens checked (English and fitting unless listed under Open issues)

* Command bar "Items" sub-bar: use, equip, unequip, sell, discard, sort
  (swap two entries), tidy up (silent).
* Use item: "Choose a character." / "Choose a unit." / "Choose a
  destination." / "Nothing happened." / "It can't be used on this unit.";
  target picking via the NEXT list (UNIT / CITY tabs); Joker Card ("You drew
  the card “Lovers”." + "Keep this tarot card in stock?"), Dowsing Rod
  ("CONGRATULATIONS! You found buried treasure!", "The treasure you found was
  “Overlord Crown”.", "You obtained ..."), Crystal Ball ("The fortress city of
  / Hind / has been discovered."), stat items (STR UP sprite, no text), stock
  full ("Your item stock is full. Discard something?" -> list -> "Is that all
  right?", or No -> "You gave up “Overlord Crown”."). Silent in the original
  too: Wonder Egg, Full Moon Stone, All Summons, Trojan Horse, Scent of
  Night, Light's Whisper, Chaos Up.
* Equip / unequip: map target, unit, character, status preview (no message,
  as in the original).
* Sell: "Choose a quantity." + "01", "200 goth. / Is that OK?" + Yes/No.
  Discard: quantity, "Is that all right?" + Yes/No.
* Jack's shop: Jack's line, shop list with prices and "Funds", quantity
  prompt, "15000 goth. / Is that OK?", "You don't have enough funds to buy
  this item.", "Your item stock is full. You can't buy any more."
* Town shop (Leckart): same list and prompts, no greeting.
* Tarot cards (command bar): list, page flip, card art and descriptions; the
  command only shows the stock (cards are used in battle). Tarot stock full
  on a draw: "Your tarot stock is full. Discard one?" -> list -> "Is that all
  right?" (cursor starts on No).
* Church: town window "Roshfol Church"; liberation: "Roshfol Church has been
  liberated.", LIBERATION / THANK YOU! / Boo!Boo! graphics (English
  originals), "Draw a tarot card?", "You drew the card “Fool”.", "Characters'
  LUK went up by 1 point." / "The Chaos Frame went up (down) by 2 points.",
  "Keep this tarot card in stock?", priest dialogue with the A/B answer, Game
  System Tips 2 (names the icon "Rite of Revival"), the hint about Hind.
* Revival: "Reviving costs 0 goth. / Is that OK?", with a patched cost
  "Reviving costs 30000 goth.", with low funds "You don't have enough funds."
* Hind (hidden town, tile (47,21)): "... has been discovered.", "... has been
  liberated.", tarot draw, the town's request (Yes: gift, "You obtained 10000
  goth."; No: "...I see... What a pity..."), town window "Hind" with
  population, ratings and income.
* Leckart: liberation, Game System Tips 6, "There's a shop in this town, you
  know...", unit window with Recruit / Buy items.
* Recruit: "Fighter 140" list, "Funds", "The unit is full. A unit holds up
  to 5 members; a large character counts as two."

## How to test / reproduce

Harness: the stable snapshot `scratchpad\snap\ngp_harness.exe` with
`scratchpad\snap\ogre_en.ngc` (see the agent briefing). Text logs go to
`build/textlogs/towns-<step>.txt` (decode with
`python -m tools.text.textlog FILE --en`); states made here are
`build/states/towns-*.state`. Helpers (scratch, `scratchpad\towns\`):
`run.py STEP STATE FRAMES INPUT [--every K] [--save F NAME] [--rom
padfix|ja|PATH] [--ja]`, `patchstate.py IN OUT stock=ID:QTY,... funds=N
ADDR=HEX` (state file offset = 192 + RAM address), `curpos.py` (cursor
position), `locprobe.py` (finds selectable map locations by pressing A on a
grid), `useall.py` (uses each item in turn), `padfix.py` (see below).

Comparing with the original: the same states load in the Japanese ROM
(`--rom ja`; its text logs go to the scratch folder, never to
`build/textlogs/`), which shows what the original draws on the same screen.

Test-only ROM: `scratchpad\towns\ogre_en_padfix.ngc` = the snapshot ROM plus
a fix for Open issue 1 (names clamped to 10 cells), used only to explore the
screens behind the Items list without RAM corruption (logs `towns-pf-*`,
states `towns-pf_*`).

Saved states (all from the English snapshot unless marked pf):

| State | Where | How it was made |
|---|---|---|
| `towns-items_subbar` | command bar -> Items sub-bar, cursor on "use" | `command_bar_forecast` + `20:L:2;60:L:2;100:A:2`, frame 150 |
| `towns-items_stocked` | same, 33 test items in stock | `towns-items_subbar` + stock patch |
| `towns-items_short` | same, Soul Call, Cure Ankh, Durandal only | stock patch |
| `towns-items_ticket` | same, one Trade Ticket | stock `11:1`; `20:A:2;80:A:2;150:A:2` -> Jack's shop list |
| `towns-items_ticket_poor` / `_full` | ticket with funds 1000 / with a full stock | patches |
| `towns-items_equip`, `towns-items_equip_long` | equipment only | stock patch |
| `towns-items_rod_full` | Dowsing Rod x2 + 59 items | stock patch |
| `towns-items_crystal` | Crystal Ball only | stock patch |
| `towns-jack_shop_list` | Jack's shop list on screen | `towns-items_ticket` + `20:A:2;80:A:2;150:A:2;200:D:2`, frame 225 |
| `towns-organize_top` | organize screen top icons | `command_bar_forecast` + `20:L:2;50:L:2;80:L:2;120:A:2`, frame 175 |
| `towns-organize_items`, `towns-organize_soul` | same with test items | stock patch |
| `towns-tarot_list` | Tarot cards list | `command_bar_forecast` + `20:L:2;60:A:2`, frame 110 |
| `towns-cb_tarot_a`, `towns-cb_tarot_b` | command bar with cards 1-14 / 15-22 in the tarot stock | patch `5406=...`; then `20:L:2;60:A:2` |
| `towns-s0_move_flag` | Move chosen, flag cursor on HQ | `stage0_gameplay` + `46:A:2;80:R:2;110:A:2;170:A:2`, frame 215 |
| `towns-s0_walk_church` | unit walking to the church | `towns-s0_move_flag` + `10:L:27;47:D:26;90:A:2;140:A:2`, frame 200 |
| `towns-s0_church_liberated` | "Roshfol Church has been liberated." | same input, frame 790 |
| `towns-s0_church_priest_end` | priest dialogue, last line | + A every 100 frames, frame 1790 |
| `towns-s0_church_done` | priest's hint about Hind | + A x10, B at 1200 and 1350, frame 1700 |
| `towns-s0_church_dead` | same, character 2 dead | patch `46C0=0000` |
| `towns-s0_church_unitwin_dead` | unit window with Rite of Revival | + `20:A:2;150:A:2;240:A:2;290:R:2;330:A:2`, frame 410 |
| `towns-s0_church_unitwin_dead_poor` | same, cost 30000, funds 100 | patch `46CA=1027`, `funds=100` |
| `towns-s0_hind_discovered` | "... Hind has been discovered." | `towns-s0_move_flag` + `10:R:62;82:D:36;140:A:2;190:A:2`, frame 2190 |
| `towns-s0_hind_liberated` | "... Hind has been liberated." | + `20:A:2`, frame 190 |
| `towns-s0_hind_question` | "Would you take us under your protection?" | + A every 130 frames, frame 1250 |
| `towns-s0_hind_done` | after the gift | + A every 130 frames, frame 1090 |
| `towns-s0_hind_tarotfull` | Hind liberated with 14 tarot cards in stock | patch `5406=...` |
| `towns-s1_walk_leckart` | stage 1, hero's unit walking to Leckart | `progress-stage1_gameplay` + `40:A:2;100:R:2;140:A:2;200:A:2;260:L:227;500:D:98;640:A:2;700:A:2`, frame 760 |
| `towns-s1_leckart_liberated` | "The trade city of Leckart has been liberated." | + 5390 frames |
| `towns-s1_leckart_tips_end` / `_shop_hint` | tips 6 / the shop hint | A every 130 frames; then A, B, B |
| `towns-s1_leckart_unitwin` | unit window at Leckart (Recruit, Buy items) | + `20:A:2;150:A:2;250:A:2;300:R:2;340:A:2`, frame 390 |
| `towns-s1_leckart_unitwin_4members` | same, one member removed | patch `5186=0000` |
| `towns-s1_leckart_bought_potion` | after buying a Cure Potion | + `20:R:2;50:R:2;80:R:2;120:A:2;200:A:2;280:A:2;360:A:2`, frame 440 |
| `towns-pf_*` (pf) | states made with the test ROM | see the scratch logs |

Navigation notes:
* Command bar (A on empty map ground): NEXT, (stage 1+: Deploy unit),
  Organize, Items, Tarot cards, Income forecast, Monitor, Suspend;
  Left/Right moves (wraps), A selects, B backs out. NEXT opens a jump list:
  A on the "NEXT" header switches the UNIT / CITY tab, Down enters the list,
  A jumps the cursor there.
* Moving a unit: A on the unit -> Right (unit icon) -> A -> A (Move) -> steer
  the flag -> A (place) -> **A again** (confirm). Holding a direction moves
  the cursor 0,1,2,4,6,9,12... px for 1,2,3,4,5,6,7... frames (3 px per frame
  after a ramp); the cursor's map position is camera (`0x60AE`/`0x60B0`) +
  screen (`0x61DE`/`0x61DF`) - (80, 76).
* Stage 0 locations (tile x, y): Estoa (25,9) HQ, church (16,17), Gring
  (16,34), Balzac (35,47), Hind (47,21, hidden until found).
* System messages wait for A; a press during the typewriter only completes
  the line, so leave about 80 frames between presses; "Hear it again?"
  prompts take B (No) once they are fully drawn.

## Open issues

1. **Critical: the Items list corrupts RAM with English names of 10+
   letters, and the game breaks.** The list composer at `0x2157C0` copies
   each name and pads it with `10 - length` spaces using an 8-bit `djnz`
   (`0x215816`: `ld A,10; sub A,C; ldir; ... djnz A`). For a name of 10 or
   more letters the count wraps (10 letters -> 256 spaces, 11 -> 255, ...),
   so each such line writes about 256 bytes into the `0x6000` buffer and the
   four lines run over RAM `0x6000`-`0x6400` (location table pointer
   `0x608E`, camera `0x60AE`, timer `0x6080`, shop number `0x61D9`, cursor
   `0x61DE`, event script `0x61F0` all become `01 01 ...`). The list still
   looks almost right (the map row wraps every 32 cells), but after closing
   it the stage map is gone (all green / white, cursor lost, spurious events
   such as "You found buried treasure!"). Every list built by this composer
   is affected: use, equip, unequip, sell, discard, sort, the stock-full
   discard list, and the organize screen's Item icon (drawn by `0x213DEE`).
   It happens in normal play: stage 1 starts with 5 Cure Potions, so
   `progress-stage1_gameplay` +
   `40:D:12;80:A:2;140:R:2;180:R:2;220:R:2;260:A:2;330:A:2;420:B:2;480:B:2;540:B:2`
   breaks the map (the Japanese ROM and the test fix ROM do not). Other
   repros: `towns-items_stocked` + `20:A:2;100:B:2;160:B:2;220:B:2;300:A:2`
   (versus `towns-items_short`, normal). 146 of the 189 English item names
   have 10 or more letters. Fix in code (clamp the copy to the field and skip
   the pad loop when the count is 0; `scratchpad\towns\padfix.py` is a 26-byte
   test version at `0x3FF000`, outside the patch area) and/or keep list names
   within 9 letters.
2. **Item names overflow their fixed fields** (Japanese names have at most 9
   letters):
   * Items list: 10-cell name field (cols 5-14), quantity in cols 15-16: the
     quantity overwrites the 11th letter and longer names run over the right
     frame ("Full Moon S1one", "one" outside the window).
   * Shop list (`0x207464`, no padding, no crash): name from col 3, the price
     right-aligned in cols 13-17: names of 10+ letters run into the price
     ("Return Half2000", "All Summons3000", "Speed Gear17000") and longer
     ones are cut by it ("Sword Symb15000", "Life Sourc20000", "Vessel of
     21000"). "Cure Potion 400" only looks right because the price is short.
   * Organize status pane "ITEM:" field: 8 cells; "Musashi's Blade" shows
     "Musashi'" with the "s" on the frame and the rest cut off (equip it with
     `towns-items_equip_long`, then Organize -> Character).
   Options: variable-width font for these name fields (80 px holds most
   15-letter names) or a short list name of at most 8-9 letters per item.
3. **Tarot cards list: 10-letter card names overflow** onto the right
   frame: "Hierophant", "Hanged Man", "Temperance" (states `towns-cb_tarot_a`
   + `20:L:2;60:A:2;130:R:2;190:R:2;250:R:2`). The list (composed in `0x6000`,
   drawn from `0x208A91`, names from the packed table `0x21BCEB`, also used
   for the tarot-stock-full discard list) has 9 cells after the cursor.
   Shorten to 9 letters or draw with the VWF.
4. **Organize screen: item messages drawn in fixed cells.** When the Items
   command is used from the organize screen, the item code's messages are
   shown by `0x213495` with the fixed-cell printer (`0x200B72`, 18 cells per
   line, 2 lines, from map `0x9382`), so the `sysmsg` (VWF) layouts do not
   apply. Seen: `@215F5E` "This item cannot be used / on the organize
   screen." runs off the screen (suggest "This item can't be" / "used
   here."); `@215F3C` "Choose a character." (19) puts the period on the right
   frame (suggest "Pick a character."); `@21666F` "It can't be used on / this
   character." (19 on line 1; suggest "Can't be used on" / "this
   character."). Same risk for `@21664D`, `@216122` ("It can't be used on",
   19) and `@215F11` ("Your item stock is full.", 24). "Choose a quantity."
   (18), "Nothing happened.", "200 goth. / Is that OK?" fit. Either keep these
   strings within 18 fixed cells per line or let the uiprint hook use the VWF
   when called from `0x213495`. Repro: `towns-organize_items` +
   `20:R:2;40:R:2;60:R:2;80:R:2;100:R:2;140:A:2;220:A:2` (cannot be used),
   `towns-organize_soul` + same + `300:A:2;380:A:2;460:A:2` (this
   character).
5. Cosmetic: the quantity prompt (`@215EBF`) draws the first "01" with the
   VWF; the game then redraws the digits in fixed cells ("0 1", 8 px apart).
   The shared Yes/No prompt (`@2030F5`) puts the "No" cursor right after
   "Yes" ("Yes▶No"), by design of the cell layout.
6. Recruit list (`0x2057B7`, no padding): class names start at col 3 and the
   cost is right-aligned to col 17, so names of about 12 letters or more
   would touch a 3-4 digit cost. Only "Fighter" was offered at Leckart.
7. Pre-drawn Japanese labels (for the graphics workstreams; screenshots in
   the scratch folder): Items sub-bar labels (use, equip, unequip, sell,
   discard, sort, tidy up) `towns\items1\sheet.png`; command bar (7, plus
   "Deploy unit" from stage 1) `towns\cb0\sheet.png`,
   `towns\s1corrupt0\sheet.png`; organize top icons (6)
   `towns\org1\sheet.png`; unit window labels Move / Battle commands / Rite
   of Revival / Organize `towns\revive1\sheet.png` and Recruit characters /
   Buy items `towns\labels\sheet.png` (the church tip calls the icon "Rite of
   Revival", so the art should use that name); organize unit panel tag
   "deployed" `towns\pf-orgsoul\crop_label.png`.

## Next steps

* After a code fix for issue 1, re-check the Items and organize lists on the
  real build (all sub-commands and the stock-full discard list).
* Decide the item-name strategy for issues 2 and 3 (VWF fields or short list
  names) and re-check the shop list, the Items list, the status ITEM field
  and the tarot list.
* Later shops (stages 2-19) only change the stock; check a few lists for
  5-digit prices with long names once those stages are reachable.
