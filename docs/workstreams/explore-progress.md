# Explore: story progression (prologue, chapters, stage clears, endings)

## Goal

Play the English build from the start of stage 0 (prologue, Estoa) through the
stage-clear sequence, results, the next chapter title card, the scenario map
with the next stage and the start of stage 1, and as far beyond as possible;
record every screen's text with harness text logs, report untranslated text,
overflowing English and pre-drawn Japanese graphics, and save a state at every
milestone.

## State

Round 1 done (2026-10-09). Stages 0, 1 and 2 were played to their clears;
stage 3 (Lichtfloss) was started (not cleared: the HQ falls while the hero's
unit crosses the snow, see "Open issues"). With testing aids, every stage's
card and opening (stages 4-19) and all five endings, the staff roll and the
final results screen were reached and checked.

## Done

* **No untranslated text** from the two text renderers on any screen visited
  (188 distinct strings in `build/textlogs/progress-*.txt`): every Japanese
  ROM source in the logs is remapped by `translation/en/ui.txt`, no RAM-composed
  string contains kana codes, and the screenshots show English. The
  localization export over all logs still flags only 3 Monitor help lines
  from another workstream's log.
* No overflowing English seen in the story path. Dialogue checked visually with
  the widest possible hero name ("AAAAAAAA"): the stage 1-3 openings, every
  location event played in stages 0-2, Kazuma, Aquarius joining, the openings
  of stages 4-19, the Baldur scene and all five ending variants. Everything
  fits in 3 lines.
* System messages seen in their real windows (all English, all fit):
  encounter (enemy / neutral), finished moving, liberated (with and without
  town type), "CONGRATULATIONS! You found buried treasure!", treasure / spoils
  / obtained item, tarot draw / keep / stat change, deploy cost, daily
  "Income & Expenses", "Your headquarters has fallen to the enemy...",
  "With its leader lost, the volunteer army has been wiped out...".
* Stage-clear sequence: Estrada-style closing dialogue, clear animation on the
  map, "Congratulation! YOU COMPLETED THIS MAP. BONUS MONEY n Goth."
  (pre-drawn English), then the scenario map with the popup open and the next
  stage's marker; after stage 2 the popup gains the Link icon.
* Game over: "GameOver" (pre-drawn English) on the map, then the game resets
  to the SNK logo and the intro narration (already a graphics workstream).
* Ending: dialogue (five variants), staff roll drawn by the window renderer
  from ROM `0x2A36BC`-`0x2A3874` in the original's Latin letters, SNK logo,
  results screen (tarot card, "CHAOS FRAME n pt.", "CONQUEST n DAYS",
  pre-drawn English), then SNK logo, intro, title. One glitch: see Open
  issues 1.

## Stage walkthroughs (from the stage scripts and play)

Stage scripts were read with a local dump of the stage records
(`0x2261D9 + 18*k`) and event handlers; location coordinates come from the
location tables (`x*8`, `y*8` map pixels).

### Stage 0 (prologue, Estoa, card "Episode 1")

* Church west of Estoa and the hidden town Hind (16,18 tiles) are optional.
* Gring (map pixel 132,272): bandit unit, challenge, battle; winning liberates
  Gring, then villagers, rumour about Balzac, tips 3 (unlocks Balzac).
* Balzac (284,376): before Gring the bandits send the unit away; after it,
  challenge and battle (the starting unit loses without help; the Justice
  tarot card wins it); thanks, "Cure Potion", tips 4, Estrada's speech,
  stage end.

### Stage 1 ("Gross Region", card "Episode 2")

HQ Grolier (728,32). Hero's unit to Dakatsu (168,88). Three bandit forts:
Fort 1 (624,576), Fort 2 (344,704), Fort 3 (40,552); the third fort ends the
stage (Kain's doubts scene, stage clear). Neutral monsters roam; one battle
ends with buried treasure.

### Stage 2 ("Satsu Peninsula", card "Episode 3")

HQ Karkov (720,712). Boss Kazuma at Lard (136,168), reached across shallow
water. **The HQ falls if left empty**: deploy a second unit first (command
bar icon 2). Kazuma asks twice: "Won't you join us?" (No = refuse) and
"Even so, are you still reluctant to join us?" (Yes = refuse -> fight; No =
you join him and are sent to patrol). The polarity matches the original
question. After his defeat: Estrada, Kain, Aquarius scene, "Aquarius joined
your army.", stage clear.

### Stage 3 ("Lichtfloss", card "Episode 4")

HQ Lichtfloss castle (576,656); boss Galan at Fulda (168,72) far north across
snow; buried treasure on the way ("Spike Shield"). Per the stage script,
Galan's defeat ends the stage (not reached in play).

### Later stages

Scenario hotspot table `0x29C4FE` (20 x 5 bytes: x, y, label pointer; index
= stage = bit in the stage masks): 0 Estrada's Manor (29,69), 1 Gross (43,65),
2 Satsu (41,78), 3 Lichtfloss (75,25), 4 Roden (87,28), 5 Litt Eastern Sea
(61,42), 6 Nessa (164,56), 7 Norodom (157,45), 8 Megaholten (139,45),
9 Shagall (117,54), 10 Lego Islands (150,61), 11 Am Sea of Trees (127,52),
12 Laika Lakeside (108,40; final episode, Orma, Baldur, endings),
13 Krono Mountains (72,73), 14 Ein Peninsula (52,24), 15 Wind Dunes (188,123),
16 Freia Isles (157,113), 17-19 Free Battle Areas (103,98), (125,30), (71,113).
The card number is index + 1 (stage 12 shows "Final Episode"; 17-19 show
"Free Battle Area").

Endings (stage 12): Baldur's defeat runs `0x2702C4` (armed through
`0x61F0` by the Orma event). Story flags 0x9A-0x9D choose the variant (none:
the hero goes to Zeteginea and Baldur's voice offers power; 0x9A: leaves with
Kain; 0x9B: brings down the empire, Estrada's words; 0x9C: disappears, Kain
searches; 0x9D: returns to Estoa, Banya's words). All then store an ending id
in `0x45CC` and enter `0x2A2F0C` (staff roll script `0x2A3077`).

## Controls and RAM facts learned

* Map cursor: map position = (`0x60AE` + `0x61DE` - 80, `0x60B0` + `0x61DF` - 76).
  Holding a direction moves ~1 px per frame at first, ~2.8 px later.
* Moving a unit: cursor on the unit (or HQ), A opens the small menu
  (NEXT / units / location); Right once per unit icon, A opens the unit
  window; A on Move gives a flag cursor; steer, then A twice about 50 frames
  apart (the first press after loading a state is ignored).
* Finding a walking unit: A (small menu or command bar), A on NEXT, Down, A:
  the cursor jumps to the unit.
* Deploying (stage 1+): cursor off the HQ, A (command bar), Right, A (UNIT
  list), A, A (Yes to the cost) - `10:U:12;40:A:2;80:R:2;140:A:2;220:A:2;340:A:2`.
* Encounter messages: **A starts the battle; B dismisses the message and
  pauses the game** ("PAUSE" blinks, nothing happens). Other messages: A or B.
* Game clock: 32-bit at `0x6080` (from the explore-map notes); it stops while
  any message, menu or battle is open. (`0x4001` is a free-running counter.)
* Battle: A opens the command bar (Tarot card / Battle command / Run /
  Animation); combatants are 0x30-byte records from `0x5520` (HP word +0x0E,
  side byte +0x12 = 1 for the enemy); the tactic label (caller `0x2C7F9B`) is
  drawn when the battle starts. Result label: `0x20F6C9` = we won,
  `0x20F6D2` = the enemy won.
* Stage masks: `0x546A` (32-bit) open stages, `0x546E` (32-bit) cleared
  stages (new game: 1 and 0; after stage 0: 2 and 1; ...). Story flags: bit
  array at `0x543E` (flag N = bit N%8 of byte `0x543E + N/8`); `bflag2 N`
  tests bit N of `0x546E`.
* Scenario map: cursor mirrored at `0x40BA/0x40BB` (screen) plus horizontal
  scroll `0x5478`; poking `0x40BA` does not move it. Hotspot hit when
  (x + scroll - hx)^2 + (y - hy)^2 < 32 (code `0x29B6F8`).
* Harness: a saved state stores RAM at file offset (address + 0xC0); only the
  last `--save-state` of a run is kept.

## Testing aids (used for this report; not part of the game)

* **Weaken enemies**: in a state taken after the tactic label appeared, set
  the HP of every combatant record with side 1 to 1 (state offset rule
  above). Used for stage 1 Forts 2-3, Kazuma and the stage 3 trip; story
  flags are unaffected.
* **Jump to stage K**: in a scenario-map state set `0x546A` = 1<<K and
  `0x546E` = (1<<K)-1, steer the cursor to hotspot K, A. Skipped stages'
  story flags are not set, so later openings may take default branches.
* **Endings**: in a battle state, set `0x61F0` (32-bit) = `0x002702C4`, weaken
  the enemies and win; set byte `0x5451` bits 2-5 for flags 0x9A-0x9D.
  Directly entering the staff roll: `0x45CC` = ending id, `0x4002` (24-bit) =
  `0x2A2F0C` in any calm map state.
* Session scripts implementing these (scratch area, not committed):
  `progress\steer.py` (map cursor), `sendunit.py` (unit move), `drive.py`
  (runs real-time play, answers system messages by rule, optional enemy
  weakening), `scensteer.py` / `jumpstage.py` (scenario map), `poke.py`
  (state RAM patch), `stagedump.py` (stage records and scripts).

## How to test / reproduce

Harness and ROM: the scratch snapshot (`snap\ngp_harness.exe`,
`snap\ogre_en.ngc`). Text logs: `build/textlogs/progress-*.txt`
(`progress-drive-*.txt` are the long driver runs). States in `build/states/`
(machine-local). The hero is named "AAAAAAAA". States reached with a testing
aid are marked "(aid)"; `progress-test-*` states are artificial.

| State | What it is |
|---|---|
| `progress-gring_bandit_dialogue` | stage 0, Gring: the bandit's challenge |
| `progress-gring_liberated_msg` | "The trade city of Gring has been liberated." |
| `progress-gring_villager_dialogue` | Gring villagers' thanks |
| `progress-gring_cleared_map` | map, unit in Gring, Balzac unlocked |
| `progress-balzac_encounter` | encounter message near Balzac |
| `progress-balzac_battle_start` | Balzac battle just started |
| `progress-balzac_won_villager` | Balzac villager's thanks (won with the Justice card) |
| `progress-stage0_clear_anim` | stage-clear animation on the stage 0 map |
| `progress-stage0_congratulation` | "Congratulation! ... BONUS MONEY" |
| `progress-scenario_after_stage0_popup` | scenario map after stage 0, popup open |
| `progress-scenario_cursor_on_stage1` | cursor on "Gross Region" (A starts stage 1) |
| `progress-stage1_chapter_card` | stage 1 card ("Episode 2") |
| `progress-stage1_opening` | stage 1 opening dialogue |
| `progress-stage1_gameplay` | stage 1 real-time map, hero's unit at HQ Grolier |
| `progress-stage1_neutral_encounter` | neutral monsters on the way to Dakatsu |
| `progress-stage1_buried_treasure` | "CONGRATULATIONS! You found buried treasure!" |
| `progress-stage1_dakatsu_liberated` | unit in Dakatsu after liberation |
| `progress-stage1_fort1_encounter` / `_fort1_won` / `_fort1_liberated` | Fort 1 |
| `progress-stage1_fort2_encounter` / `_fort2_liberated` (aid) | Fort 2 |
| `progress-stage1_fort3_encounter` / `_fort3_won` (aid) | Fort 3 |
| `progress-stage1_kain_scene` | Kain's doubts scene before the clear |
| `progress-stage1_congratulation` | stage 1 bonus screen |
| `progress-scenario_after_stage1_popup` | scenario map after stage 1 |
| `progress-scenario_cursor_on_stage2` | cursor on "Satsu Peninsula" |
| `progress-stage2_chapter_card` | stage 2 card ("Episode 3") |
| `progress-stage2_gameplay` | stage 2 real-time map at HQ Karkov |
| `progress-stage2_estrada_deployed` | Estrada's unit deployed at the HQ as a guard |
| `progress-stage2_hq_fallen_msg` | "Your headquarters has fallen to the enemy..." (game over follows) |
| `progress-stage2_kazuma_dialogue` | Kazuma's welcome at Lard |
| `progress-stage2_kazuma_join_prompt` | "Won't you join us?" |
| `progress-stage2_kazuma_second_prompt` | "Even so, are you still reluctant to join us?" |
| `progress-stage2_kazuma_battle` | boss battle running |
| `progress-stage2_kazuma_defeated` (aid) | Kazuma's last words |
| `progress-stage2_aquarius_joined` | Aquarius scene ending in "Aquarius joined your army." |
| `progress-stage2_congratulation` | stage 2 bonus screen |
| `progress-scenario_after_stage2_popup` | scenario map after stage 2 (popup with Link icon) |
| `progress-scenario_cursor_on_stage3` | cursor on "Lichtfloss" |
| `progress-stage3_chapter_card` | stage 3 card ("Episode 4") |
| `progress-stage3_gameplay` | stage 3 real-time map at HQ Lichtfloss |
| `progress-stage3_estrada_deployed` | guard deployed at the HQ |
| `progress-stage3_leader_lost_msg` | "With its leader lost, the volunteer army has been wiped out..." |
| `progress-test-scenario_all_stages_open` | scenario map with all 20 stages open (aid) |
| `progress-test-scenario_cursor_on_stage12` | cursor on the final stage, only stage 12 open (aid) |
| `progress-test-ending_trigger_battle` | stage 3 battle with the Baldur ending armed (aid) |
| `progress-test-ending_results_screen` | final results screen after the staff roll (aid) |

## Open issues

1. **Staff roll: the copyright sign before the developer credit is blank.** The credits strings at ROM
   `0x2A36BC`-`0x2A3874` (window renderer, caller `0x2A330C`) are the original
   Latin-letter credits and need no translation, but the "QUEST" line has
   code `0xDB` (the original font's copyright sign) at `0x2A3829`. The English 8x8 font has
   no glyph for `0xDB` (`tools/text/encoding_en.py` ALIASES maps the other
   original punctuation codes but not this one), so a blank cell is drawn.
   Fix: give code `0xDB` a copyright-sign glyph in the fixed English font (the VWF marker
   meaning of `0xDB` only applies at the start of window strings), or remap
   that credit line. Test: `progress-test-ending_trigger_battle`, about 5,600
   frames with B presses.
2. Optional (editorial): the staff roll opens with the romanized Japanese
   title; an English release may want an English title line and a
   translation credit there (new strings in the same format).
3. Optional polish: the stage-clear art says "Congratulation!" (original
   English, sic).
4. Pre-drawn Japanese seen on the way, all already tracked by the graphics
   workstreams: chapter cards (story set for stages 0-19, including "Final
   Episode" and "Free Battle Area"), unit window labels (Move / Battle
   command / Recruit / Organize), battle command bar labels (Tarot card /
   Battle command / Run / Animation), map command bar labels, the intro
   narration after a game over, the title logo.
5. Stage 3 was not cleared in the harness: with one guard unit the HQ falls
   (defenders are pushed off the HQ after each battle and the next enemy
   walks in) before the hero's unit reaches Fulda. Needs more units on guard,
   or the weaken aid on the HQ battles as well.

## Next steps

* Clear stage 3 properly (two or more guards, or recall the hero's unit
  between trips) and continue the real story path; check each stage's
  location events (dialogue fits so far) and any new system messages.
* Fix Open issue 1 (font glyph or remap) and re-run the staff roll.
* Consider moving the testing aids (stage jump, enemy weakening, message
  driver) into a repository tool so later sessions can reach late-game
  screens quickly.
