# Explore: map (stage map play)

## Goal

Play-test the English build on the stage map (stage 0 first) and find text that
is still Japanese or does not fit: unit window and movement, liberating towns
(message + tarot card draw), hidden town / hidden church, buried treasure, "unit
has finished moving", recalling a unit to headquarters, day/night changes, the
Monitor and Income forecast commands, encounters with enemy units. Record how to
reach each screen so later sessions can repeat it.

## State

In progress (2026-10-09, round 1). Stage 0 played through to the stage clear
(own branch: church, Hind, both treasures, Gring, Balzac boss won after
healing and "Get leader!" tactics), plus stage 1 (from the progress
workstream's states): deploying a second unit and recalling it to the HQ,
and the hidden island town Orata with a flying unit.
All map messages seen are English and fit. **Found: untranslated Monitor
help lines (5 strings); overflowing move type in the deploy list.** Not
reached: "has fallen to the enemy" (no enemy ever left its stronghold in
40,000 idle frames of stage 1) and a hidden church (first hidden churches are
in stage 7, see below).

## Done

### How the stage map works (findings)

* **Moving a unit:** A on the unit (or HQ) opens a small menu (NEXT icon,
  one icon per unit standing there, location icon); Right selects the first
  unit, A opens the unit window (icons Move / Battle command / [Recruit,
  stage 1+] / Organize), A on Move closes the window and shows a flag cursor.
  In flag mode **A places a waypoint flag (numbered 1, 2, ...); pressing A
  again on the same spot confirms the route** (at most 3 flags: placing the
  third one confirms the route automatically). B removes the last flag; with no
  flag placed, B puts the cursor back on the unit and a second B leaves flag
  mode (`0x61DB` back to 0). Code: map loop `0x2036DB` (input mask A/B/Option via `0x203198`),
  flag handler `0x2039E4` (flag count in the low nibble of `0x61DB`, flags at
  `0x61E0 + 4*n`, compares with the previous flag to detect the double press).
  Earlier attempts pressed A only once, which leaves the game waiting for more
  flags.
* Units walk in straight lines between flags (through mountains, slowly);
  use flags to route around water (e.g. Gring -> Balzac over the bridge).
* After "has finished moving" the cursor stays at the destination; to get
  back to a unit use the command bar: A on empty ground -> A on NEXT ->
  Down (cursor on "1.<leader>") -> A jumps the map cursor to the unit.
  (`scratchpad\map\toflag.py STATE OUT [N]` automates dismiss -> NEXT ->
  unit N -> unit window -> Move; with two units on one spot the small menu has
  two unit icons, Right once = first, twice = second.)
* "NEXT" in the small menu opens the command bar; the command bar's NEXT
  opens the UNIT / CITY lists (A or Left/Right switch tabs; Down then A on a
  unit jumps the cursor to it).
* **Game time:** runs only in the normal map mode. It is paused while a
  menu, window or the flag cursor is open, and by Option (blinking "PAUSE"
  sprite, English art; Option again resumes). Clock: 32-bit value at
  `0x6080` updated by `0x2036B2`: byte 0 counts 179..0, byte 1 counts the
  hours down (23..0), byte 2 the days. At game speed 2 (the new-game
  setting) a tick takes 4 frames, so one game hour = 180 ticks = 720 frames
  and a day is 17,280 frames; at speed 1 a game hour takes 1,080 frames, at
  speed 3 360 (measured with the Monitor setting changed). The map palette changes through
  the day (normal, dusk, night, bright morning, orange evening); no text.
* **New day:** when the hour counter wraps (frame ~11622 idling from
  `stage0_gameplay`) the "Income & Expenses" window (Aid / Deployment cost /
  Carried over / Total funds) is shown and waits for A or B. Same window as
  the Income forecast command. English, fits.
* **Healing:** units standing in a liberated town recover fully within
  ~6000 frames (Estrada 17 -> 120 HP at Gring). Character records: 18 bytes
  from `0x469C`, +0 HP, +2 max HP, +4.. STR AGI INT CHA ALI LUK.
* **Cursor coordinates:** map pixel = camera (`0x60AE`/`0x60B0`) + screen
  cursor (`0x61DE`/`0x61DF`) - (80, 76). Location records give x/y in 8-px
  tiles of the same space (HQ tile (25,9) = cursor (204,72)). Holding a
  direction moves 0,1,2,4,6 px for 1..5 frames and 3 px/frame after that
  (6 px/frame with B held; in flag mode a new B press cancels, so hold B
  from before the directions).
* **Map tile attributes:** stage record (`0x2261D9` + 18*n) +10 map data,
  +13 width - 10, +17 height - 10; map array (stage 0: `0x22CB2B`, 70 x 67
  tiles including a 10-tile margin), attribute table right after the
  location table (4 bytes per tile kind: [?, ?, type, code]); `0x203B9B`
  returns the code under a unit. Type `0x13` = location (code = record
  index + 1; codes past the last record = churches); type `0x0F` = road,
  `0x09` = mountain, `0x05` forest, `0x03` plains, `0x00`-`0x02` water; any
  other tile with a non-zero code = buried treasure (flag bitfield `0x543A`,
  message `0x208DC2`). `scratchpad\map\stagescan.py` lists them per stage.
* **Hidden places:** `0x2035C1` checks a "discovered" bit (`0x5432`
  bitfield) whose index comes from the 4-byte stage event entries just
  before the location table. The indexes run on consecutively across stages:
  stage 0 Hind; stage 1 Kehm, Orata (Orata is on an island in the lake: only
  a flying unit can reach it); stage 2 Ijiriko, Parna; stage 3 Linde,
  Satsurama, Heide; ...; the **first hidden churches are in stage 7** (two),
  then stage 8 (two) and stage 10 (three). Stage 0 has no hidden church.
* **Item on liberation:** the arrival code (`0x20840B`) rolls `0x4575`
  (random) against the leader's LUK (thresholds at `0x208462`, signed
  compare); on success "You found an item: "X"." and "You obtained "X"."
  follow the tarot sequence (`0x2086E4`).
* **Recall to HQ** (`0x20833B`): when a unit other than the first unit
  ends its route on the HQ the game asks "Recall <leader>'s unit to
  headquarters?" (default No); Yes removes the unit silently.
* **Deploy** (stage 1+, when units are waiting): command bar icon 2
  (pre-drawn Japanese label "deploy unit") opens the UNIT list (number,
  leader, move type); A asks "Deploying costs N goth. Is that OK?", Yes puts
  the unit on the HQ. At most seven player units are on the map at once:
  the deploy routine `0x206F8D` takes the first free 8-byte map slot from
  `0x6106`, and player units use the seven slots below `0x613E` (added
  2026-10-11; a playthrough with seven units out had no Deploy icon).
* **Tarot stock:** sorted card numbers at `0x5406` (14 slots, `0x5413` != 0
  means full). Keep = No: no message. Full stock (test state): "Your tarot
  stock is full. Discard one?" -> TAROT list -> "Is that all right?" ->
  the card is replaced silently.

### Screens checked (all English unless noted)

| Screen | Result |
|---|---|
| Unit window (number, leader name, HP bars) | OK. The command labels under the icons are **pre-drawn Japanese** (Move / Battle command / Recruit / Organize): `scratchpad\map\uw1\labels.png`, `scratchpad\map\uw4\grid.png` |
| Small unit/HQ menu (NEXT, unit, location icons) | "NEXT" icon is English art; no text |
| Command bar (NEXT / [Deploy] / Organize / Items / Tarot / Forecast / Monitor / Suspend) | labels pre-drawn Japanese (the Deploy label appears from stage 1, `scratchpad\map\dp1\sheet.png`); Option help for every icon English and fits |
| NEXT window ("UNIT" / "CITY" tabs, unit and town lists) | OK |
| Battle command (tactics) window: Show guts! / Spread out! / Get leader! / Finish them! + Option help | OK (header art reads "TAROT") |
| **Monitor** (icons only) | **Option help lines untranslated** (Open issue 1) |
| Income forecast / daily "Income & Expenses" | OK |
| **Deploy list** (stage 1) | **move type overflows into the right border** (Open issue 2); "Deploying costs 1023 goth. / Is that OK?" OK |
| "Recall Estrada's unit / to headquarters?" + Yes/No | OK |
| "<leader>'s unit / has finished moving." | OK (VWF, 2 lines) |
| "<leader>'s unit has / encountered an enemy unit." | OK |
| "Roshfol Church / has been liberated.", "The trade city of / Gring / has been liberated." | OK |
| "LIBERATION" / "FIND OUT!" / "FIGHT IT OUT!" banners, "Boo!Boo!" / "THANK YOU!" bubbles, tarot card art, "PAUSE", "Congratulation! YOU COMPLETED THIS MAP. BONUS MONEY" | English in the original art |
| "Draw a tarot card?" + Yes/No; "You drew the card / "Hanged Man"." ("Tower", "Hermit") | OK (opening and closing quote glyphs differ slightly: cosmetic) |
| "Characters' STR / went down by 1 point." (ALI down 2, INT up 2) | OK |
| "Keep this tarot card / in stock?"; "Your tarot stock is full. / Discard one?"; TAROT list; "Is that all right?" | OK (full stock = test state) |
| "You found an item: / "Oath Vestment"." / "You obtained / ..." | OK |
| "The fortress city of / Hind / has been discovered." / "... liberated." | OK (3 lines, full window) |
| Stage 1 hidden town on the lake island, reached with June's flying unit: "The self-governing city of / Orata / has been discovered." / "... liberated.", "LUCKY!!" bubble, "The Chaos Frame / went up by 2 points.", Orata dialogue | OK (the longest type phrase, 112 px) |
| "CONGRATULATIONS! / You found buried treasure!"; "The treasure you found / was "Conqueror Blade"." ("Thunder Spear"); "You obtained ..." | OK |
| Town window (Gring), enemy-held castle window (Balzac, red), church window ("Roshfol Church") | OK |
| Event dialogue (church, Hind, Gring, Balzac, Estrada) | OK (dialogue workstream) |
| Battle (seen in passing): tactic label, "Lightnng" / "Tornado" attack names, "WINNERS" | battle workstream; "Lightnng" is the 8-letter cut of "Lightning" |

Pixel widths (VWF, 144 px per line) of the longest map message lines: type
phrases 67-112 px ("The self-governing city of" 112), endings 80-101 px
("has fallen to the enemy." 101), "encountered an enemy unit." 116,
"You found buried treasure!" 114. All fit; the build checks the location
messages (`tools/text/locations.py`).

## How to test / reproduce

Harness: `scratchpad\snap\ngp_harness.exe` with `scratchpad\snap\ogre_en.ngc`
(stable snapshot of the English ROM). Tools in `scratchpad\map\`:
`run.py NAME STATE FRAMES INPUT [--every K] [--save F NAME] [--ram]`
(screenshots in `scratchpad\map\NAME\`, text log in
`build\textlogs\map-NAME.txt`, states saved as `build\states\map-NAME.state`);
`steer.py STATE PREFIX START X Y` (input that moves the map/flag cursor to
map pixel (X, Y)); `toflag.py STATE OUT [N]` (flag mode for unit N);
`stitch.py STATE OUT.png W H` (whole-map image, e.g.
`scratchpad\map\stage0_map.png`); `stagescan.py [STAGE]` (locations and
treasure tiles per stage); `patchstate.py IN OUT ADDR=HEX` (test states with
patched RAM; RAM address A is at file offset 192 + A).

Dialogue: A advances; B also advances and answers "No" on yes/no prompts
("Hear it again?"); press only after the prompt is drawn (the text log shows
the Yes/No string `0x2030F5` when it appears).

Saved states (`build\states\`), with how they were made:

| State | Reached from | Input / note |
|---|---|---|
| `map-unitwin` | `stage0_gameplay` | `46:A:2;90:R:2;130:A:2` (unit window, Move selected) |
| `map-flagcursor` | `map-unitwin` | `20:A:2` (flag cursor at HQ) |
| `map-income_daily` | `stage0_gameplay` | idle 11640 frames (Income & Expenses window) |
| `map-church_liberated` | `map-flagcursor` | `10:L:27;41:D:24;69:D:2;90:A:2;120:A:2`, save at 790 |
| `map-item_found` | `map-flagcursor` | same with the second A at 128 (item roll succeeds), A every 80 from 800, save at 1395 ("You found an item") |
| `map-church_dialogue`, `map-church_tips2`, `map-church_done` | church | tarot draw (keep = Yes), church dialogue, "finished moving" |
| `map-church_flag` | `map-church_done` | `20:A:2;60:A:2;100:R:2;140:A:2;180:A:2` (flag mode at the church) |
| `map-hind_discovered` | `map-church_flag` | `10:R:83;97:D:13;114:D:3;140:A:2;170:A:2`, save at 2965 |
| `map-hind_dialogue`, `map-hind_done`, `map-hind_flag` | Hind | A every 120 frames; flag mode at Hind |
| `map-treasure1`, `map-treasure1_done` | `map-hind_flag` | `10:R:9;23:R:3;30:U:47;100:A:2;130:A:2`, save at 1095 |
| `map-gring_encounter` | `map-church_flag` | `10:D:49;63:D:3;90:A:2;120:A:2`, save at 785 (enemy met) |
| `map-gring_fight_banner` | `map-gring_encounter` | A at 20,140,...,620 ("FIGHT IT OUT!", battle starts next) |
| `map-gring_liberated`, `map-gring_dialogue`, `map-gring_done` | after the Gring battle | liberated message / town dialogue / "finished moving" |
| `map-cmdbar` | `map-gring_done` | `20:A:2;60:R:30;130:A:2` (command bar open on empty ground) |
| `map-gring_flag` | `map-gring_done` | flag mode at Gring |
| `map-treasure2`, `map-treasure2_done` | `map-gring_flag` | `10:L:21;35:L:3;42:D:35;100:A:2;130:A:2`, save at 875 |
| `map-balzac_encounter` | `map-gring_flag` | flags via the bridge: `10:R:24;38:R:2;44:D:24;72:D:2;90:A:2;110:D:10;124:D:3;140:A:2;160:R:29;193:R:3;200:D:2;220:A:2;250:A:2`, save at 1200 |
| `map-balzac_prebattle` | `map-balzac_encounter` | boss dialogue up to Estrada's last line (A, A starts the battle) |
| `map-balzac_after1..3`, `map-balzac_encounter2..4`, `map-balzac_flag2..4` | repeated attacks | fights 1-3 do not kill the boss |
| `map-heal_gring`, `map-healed_gring`, `map-healed_flag` | `map-balzac_flag4` | back to Gring, B every 300 frames for 6000 frames (full HP), tactics "Get leader!", flag mode |
| `map-balzac_won` | `map-balzac_encounter4` | fight 4 won (boss dead), Balzac villager dialogue next |
| `map-stage0_clear`, `map-scenario_after0` | `map-balzac_won` | A every 120, B at 760 ("Hear it again?" = No); "Congratulation!" screen; scenario map with popup |
| `map-orgscreen` | `stage0_gameplay` | organize screen top level |
| `map-s1_unit2_deployed` | `progress-stage1_gameplay` | `10:U:12;40:A:2;80:R:2;140:A:2;220:A:2;340:A:2` (unit 2 Estrada deployed at the HQ) |
| `map-s1_u2_flag`, `map-s1_u2_moved`, `map-s1_u2_flag2` | stage 1 | unit 2 moved 56 px south and back |
| `map-s1_recall_prompt` | `map-s1_u2_flag2` | `10:U:21;35:U:3;80:A:2;110:A:2`, save at 555 (recall prompt) |
| `map-s1_june_deployed`, `map-s1_june_flag` | `progress-stage1_gameplay` | unit 5 (June, flying) deployed: `10:U:12;40:A:2;80:R:2;140:A:2;200:D:2;240:D:2;280:D:2;330:A:2;450:A:2`; flag mode (small menu: Right twice for the second unit) |
| `map-s1_orata_discovered` | `map-s1_june_flag` | `10:L:160;174:L:2;180:D:123;307:D:3;340:A:2;370:A:2`, save at 2885 (Orata discovered) |
| `map-test-tarotfull` | `map-church_liberated` | **test state**: tarot stock filled (`5406` = 14 cards) |
| `map-test-luck` | `map-flagcursor` | **test state**: Estrada's LUK = 100 |
| `map-test-enemymove` | `progress-stage1_dakatsu_liberated` | **test state**: stage 1 enemy behavior bytes `65C9`/`65D1`/`65D9` = 0x7F |

## Open issues

1. **Untranslated: Monitor help lines** (Option in the Monitor window; window
   renderer `0x200BAC`, caller `0x29BF92`, map `0x9446`; 14 cells x 2 lines,
   fixed 8x8 cells, padded with the blank glyph `0xDC`, so English needs
   `solid` padding). Not in `ui.txt`. Strings at `0x29BF9A` (battle animation
   on/off), `0x29BFB9` (BGM on/off), `0x29BFD8` (sound effects on/off),
   `0x29BFF7` (message speed in 3 steps), `0x29C016` (game speed in 3 steps).
   Text starts at column 3; the window is not cleared between the five
   texts, so every line must be padded to 14 cells. Suggested English (each
   line at most 14): "ON: Animations" / "OFF: Skip them"; "ON: Play music" /
   "OFF: No music"; "ON: Sound FX" / "OFF: Silent"; "Message speed" /
   "in 3 steps"; "Game speed" / "in 3 steps".
   Screenshot: `scratchpad\map\mon2\help.png`.
2. **Overflow: move type in the deploy list** (stage 1+, command bar
   "deploy unit"): `patch/src/movetype.asm` `mt_copy_d` (called from
   `0x206DCF`, list drawn by `0x200BAC` from `0x206E08` at map `0x955C`,
   column 14) copies the full English name, but only columns 14-18 are inside
   the window: "Plains" puts its "s" on the right border (also "Forest",
   "Shallow"). Fix: 5-letter move type names (e.g. Plain, Woods, Shoal) or a
   5-cell cut / shifted column for this list. Screenshot:
   `scratchpad\map\dp3\m.png`.
3. Overflow already reported by the organize workstream: Organize-screen
   command help is drawn by the fixed-cell printer `0x200B72` (caller
   `0x213495`), lines over 18 letters run over the border (seen here too:
   `scratchpad\map\org2\help.png`).
4. Pre-drawn Japanese labels (graphics workstream): unit window labels
   (Move / Battle command / Recruit / Organize), command bar labels including
   "deploy unit" (stage 1+).
5. Cosmetic: in composed messages the opening and closing quote glyphs look
   different ("Hanged Man", "Conqueror Blade").
6. Original-game quirk, not a translation bug: the NEXT window's CITY list
   writes three map words through `XIX` with a stale upper half
   (`0x204D17`, "flash command write 209208" in the harness log); same with
   the original ROM from the same state.
7. Tool gap: `tools/text/l10n.py` `runtime_rows` flags a drawn ROM string
   only if it contains a byte 0x56-0xC5, so Japanese made only of the first
   48 hiragana (codes 0x26-0x55, which double as English letters) is missed:
   the export lists 3 of the 5 Monitor help strings and not `0x29BFB9` /
   `0x29BFD8`. Suggestion: also flag any drawn ROM source below the free
   space that has no remap entry (all such sources in the current logs are
   either the Monitor lines or original English like "WINNERS").
8. Deploy list: leader names longer than 9 letters would run into the move
   type column (name from column 4, move type at column 14); part of the
   organize workstream's long-name finding.
9. The leader's HP line in the unit window starts with a small mark that
   looks like a katakana; the original ROM shows the same tile (leader
   marker), so not a translation issue (`scratchpad\map\hq1\leader.png`,
   original `scratchpad\map\orig_uw\leader.png`).

## Next steps

* "has fallen to the enemy": needs an enemy unit that leaves its stronghold
  (later stages) or a test state that moves one onto a liberated town.
* Hidden churches: stage 7 or later (two hidden churches there). Every
  church uses the one name string `0x208E22`, so the message will be
  "Roshfol Church" / "has been discovered." (both parts already seen on
  screen; 65 + 90 px). Stage progress: the script op bflag2 tests bits at
  `0x546E` (bit 0 set after stage 0), `0x546A` went 1 -> 2 after stage 0
  (stage progress of some kind), bflag/setflag use `0x543E`; a cleared stage
  cannot be replayed from the scenario map. Patching `0x546A` = 8 or 14 and
  `0x546E` = 0x7F in `map-scenario_after0` only brought up markers labeled
  "Gross Region", "Satsu Peninsula" and "Lichtfloss" (labels 1, 2, 4), so the
  scenario progression is not a simple stage counter; reaching stage 7 needs
  real play (progress workstream) or a better understanding of these
  variables.
* Enemy movement: enemy behavior records (8 bytes) are at
  `0x65C8`-`0x6607`; in stage 1 all three have behavior byte +1 = 0
  (stationary). The step routine `0x209A11` changes a record's state at
  random when +1 is non-zero; the map loop goes to `0x20A358` ("has fallen
  to the enemy") when it reports a capture. Setting +1 = 0x7F on the stage 1
  records (test state `map-test-enemymove`) changed their state but caused no
  capture in 30,000 frames; the unit positions themselves live elsewhere.
