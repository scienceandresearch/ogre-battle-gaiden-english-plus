# Explore 2: battle (play-test round 2)

## Goal

Play-test battles in depth with the current English build (round-1 fixes
included): many unit/class combinations (RAM-patched test states), every attack
name, the tactics window, every tarot card in battle, Run, Persuade, the
animation switch, level-ups, results (win, loss, draw, time-out), defeated
members, a unit leader and the army leader killed, boss battles with their
dialogue, and the battle help (Option). Check whether attack and tarot names
are drawn consistently (fixed cells versus the variable-width font, VWF).

## State

Round 2 done (2026-10-09). **No untranslated text in battles**: every string
the two text renderers drew in 2,249 logged draws (291 distinct) is English
(own scan of `build/textlogs/r2-battle-*.txt` plus the localization export:
no row from these logs). Everything fits. The main finding is cosmetic but
very visible: **attack and tarot names mix letter-spaced fixed cells with the
VWF in the same windows** (finding 1). A few wording suggestions, original
quirks and two static risks for link-battle screens follow.

Coverage: 89 distinct attack ids seen in their real window (every name
the game can produce; the rest of the table is unreachable or placeholders),
all 117 classes in battle (each at least once, every front and back attack
of the class table), all 22 tarot cards used and
their help shown, both tactics windows with help, Run, Persuade (failure and a
forced success), animation on/off, level-up, enemy WINNERS / our WINNERS /
DRAW / time-out win, members and the army leader at 0 HP, a unit leader lost
(ghost), and the post-battle event of every stage boss (36 scripts).

## Done

### Attack names (window bottom right, map `0x9414`, tiles `0x65`-`0x6C`)

* 164 call sites (one per attack animation script, banks `0x2C`-`0x35`) draw
  `0x20F21A + 10 * id` with the window renderer; the id is at combatant
  pointer + 22 (the pointer in task var `0x20` is record + 2, records 0x30
  bytes from `0x5520`). The frame is script `gfxfe 0x2C8C83` (blue, our side)
  or `0x2C8CC1` (red, enemy) at `0x93D2`.
* When a name is shown: ids flagged in the byte table `0x2DF1A7` (spells,
  breaths, summons...) always; plain physical attacks only when battle
  animations are off (`0x5508` = 1; 0 = on, copied from the Monitor setting
  `0x469A` at battle start; "Anim ON" is shown when it becomes 0).
* Attack choice (`0x2CAF92`): class table `0x20EE47`, 4 bytes per class
  (front id, front count, back id, back count); row = bit 0 of
  `0x2C6089[5 * position]` (ours: positions 1-5 back, 6-10 front; enemies
  11-15 front, 16-19 back); per-id routine from the 3-byte table `0x2CAFD9`.
  Placeholder ids "Magic" (84, 85, 87-90, 92-94, 101-106, 112, 113, 115,
  117) and "Ninjutsu" (86) are always replaced: by the target's weakest element
  (argmin of bytes 11-15 of the per-battle character copy `0x58C8 + 18 k`;
  tables such as `0x2CB252`, `0x2CB2CC`, `0x2CB2FC`, `0x2E00A0`), by the
  terrain (`0x45CE`; Kraken: Maelstrom on the water terrains 0-2, shallow,
  ocean and reef) or at random
  (`0x45DC`; ids 101 and 112).
* Seen in their window (montage of every one:
  `scratchpad\r2-battle\names_all.png`): all English, all fit. Never drawn
  because no class or routine produces them: Acid Cloud (9; same name as 10),
  Death Cloud (11), Cleave (24), Acid Breath (26; same as 27), Ninjutsu (47),
  Magic (51), Petro Flash (81; same as 116), Healing (108; same as 107).
* Class names are **not shown** in normal battles (no button opens a unit
  view). The only battle code that draws class names (`0x2C8016`-`0x2C8299`,
  8-cell windows at `0x9414`/`0x9084`) is a leftover developer "battle test"
  setup (pick both classes, terrain, day/night, then a fixed tarot stock)
  that nothing calls: no pointer to `0x2C7FF2`/`0x2C7FF3` exists. The
  terrain names `0x2C82A9` and the Day/Night labels `0x2C835D`/`0x2C8361`
  are referenced only from that code (round 1 thought link battles used
  them), so their translations are harmless but never visible.

### Tarot cards in battle

* The TAROT list (`0x2C71AB`) draws each owned card's name straight from the
  fixed-width table `0x20F134 + 10 * card` (rows at map `0x90C6 + 0x40 k`,
  8 tiles per row), 7 per page; the cursor keeps its row when Left/Right
  switch pages; the list is cleared on a page switch (no stale cells). With
  an empty stock the Tarot icon is simply missing from the command bar.
* All 22 cards used (stock patched, two runs of 14): card art with English
  captions, effects with English sprites only (DEF UP!, DEF DOWN, AGI UP!,
  R-AGAIN, M-SHILD, WAKE UP!, zzz, ???, miss, LEVEL UP!). Chariot, Tower and
  Sun won the Gring battle outright; Fortune missed in the one attempt.
* Option on every card: the help box (9 x 3, `0x2C9911`, table `0x20F6E4`)
  matches each card and fits.

### Commands, tactics, Run, Persuade, animation

* Command bar help (`0x2C9959`, table `0x20F941`): Tarot card, Battle
  command, Run, Animation, Persuade, all fit (labels under the icons are the
  known pre-drawn graphics).
* Tactics window in battle (`0x20F10F`, VWF) and its help (`0x2C99DA`, table
  `0x20F9F2`) fit; choosing a tactic shows no new label (as in the original).
  The battle-start label (`0x2C7F9B`) was checked for all four tactics (unit
  byte +10 = tactic): Show guts! / Spread out! / Get leader! / Finish them!.
  The unit-window version (Battle commands) and its help in the message
  window also fit.
* Run: help, retreat, "<leader>'s unit has finished moving." Animation:
  "Anim OFF" / "Anim ON" (VWF, fit). Persuade: failure shows "miss";
  forced success shows "Persuasion succeeded!" (fits), the battle ends after
  A and the neutral joins the stock silently (no message in the original
  either; checked with `rom\baserom.ngc` from the same state).
* Persuasion check (`0x2C79F5`): H = leader CHA - target CHA + leader LUK / 2
  - |class byte 15 difference| from the per-battle copies (+7 CHA, +9 LUK);
  H 33-78 always succeeds, lower values roll `0x45DC` against 0x78 ... 0x20.
  In `battle-neutral_battle_start` H = 18 (94 %), but the roll at the usual
  timing is 0x79 and fails; the test state lowers the neutral's CHA byte
  (`0x593B`) so that it always succeeds.

### Results, level-up, defeat

* Result codes (`0x2C9448`): 1 = our "WINNERS" (`0x20F6C9`, blue, bottom
  right), 2 = enemy "WINNERS" (`0x20F6D2`, red, top left), 3 = "DRAW"
  (`0x20F6DB`, bottom right). Time-out (`0x2C65F7`): against an enemy unit
  (`0x45D1` = 1, set by the encounter code at `0x2092AC`) the enemy is
  declared the winner while any of its members stands; against neutrals
  (`0x45D1` = 0) the words at `0x5509` and `0x550B` decide (the smaller
  `0x5509` wins for us, equal = DRAW). Draw and time-out win were reached
  with patched end-of-battle states; all three labels are original English
  in fixed cells.
* "LEVEL UP!" sprites over each character that levelled (EXP is byte +16 of
  the character record; 0x60 + a won battle levels up), then the town
  message.
* Members at 1 HP: the HP panel's right column sits at the screen edge
  (original layout). The army leader at 0 HP does **not** end the battle; it
  runs to the time-out, then "With its leader lost, the volunteer army has
  been wiped out..." (same in the original ROM). Stage 1 unit leader lost:
  pre-battle talk, enemy WINNERS, the unit turns into a ghost, no message.

### Boss battles and their dialogue

* 36 of the 37 post-battle events (`st32 script, 0x61F0` in the stage
  scripts; the ending one, `0x2702C4`, was covered by explore-progress) were
  run as a testing aid: arm `0x61F0` in a battle state, win with the Tower
  card, A every 90 frames, message speed fast (`0x469D` = 2). Dialogue shown
  for stages 0, 1, 2, 3, 5, 7, 8, 9, 10, 11 (all 9 scripts), 13, 14, 15
  (first script) and 16, with the composed messages "You obtained "Cure
  Potion" / "Archangel Wing" / "Ring of Undeath"", "Aquarius joined your
  army.", the tips prompts and the stage clear screen. Every page fits (3
  lines) with the 8-letter hero name. `0x26444F`, `0x26510F`, 10 of the 11
  stage 15 scripts and `0x20412C` showed nothing in this context (story
  conditions). Pre-battle boss talk was seen for the stage 1 Fort 1 bandit;
  the others were covered in round 1 and by explore-progress.

## How to test / reproduce

Harness: `snap2\ngp_harness.exe` + `snap2\ogre_en.ngc` in the session
scratchpad. Scripts in `scratchpad\r2-battle\` (machine-local):

* `run.py NAME STATE FRAMES INPUT [--every K] [--shots ..] [--save F NAME]
  [--rom PATH]`: runs the harness, writes `build\textlogs\r2-battle-NAME.txt`
  and a contact sheet, prints the decoded log with ui.txt English.
* `bconf.py NAME "CLASS@POS,..." "CLASS@POS,..." [--anim on|off] [--elem E]
  [--late ADDR=HEX]`: test battle from `battle-gring_fight_banner` with our
  unit (characters 3, 2, 1, 4, 5) and the Gring bandits (characters
  `0x6B`-`0x6F`, unit `0x52C2`) set to any classes; screenshots of every name
  draw. `plan.py` prints the 20 battles that cover every class and every
  class-table attack; `cover.py` lists the ids drawn; `montage.py` builds the
  name montage.
* `tarotrun.py STOCK IDX NAME`, `tarothelp.py STOCK NAME`: use / show help of
  a tarot card (stock written to `0x5406`).
* `bossrun.py SCRIPT NAME`: post-battle event test; `dlgsheet.py` collects
  the frames with a message window.
* `pst.py IN OUT [ADDR=HEX] [cN:class=C,lv=L,hp=H] [show]`: state RAM patch
  (state offset = RAM address + 0xC0).

States (`build\states\`, local):

| State | What |
|---|---|
| `r2-battle-tactics_window` | in-battle tactics window open |
| `r2-battle-cmdbar_animation` / `_run` / `_persuade` | command bar on that icon (Persuade: stage 1 neutral) |
| `r2-battle-test-tarot_list_cards1to14` / `_cards9to22` | TAROT list open with 14 cards |
| `r2-battle-test-no_tarot` | empty stock (no Tarot icon) |
| `r2-battle-test-persuade_ok` | neutral battle, target CHA lowered: Persuade with `10:A:2;80:L:2;260:A:2` succeeds |
| `r2-battle-test-draw_pending` / `_timeout_win_pending` | 60 frames before the time-out, result words patched |
| `r2-battle-test-levelup_pending` | EXP 0x60, only the Tower card: `100:A:2;160:A:4;230:A:4;300:A:4` |
| `r2-battle-test-army_leader_1hp` / `_members_1hp` | Estrada / Kain and the hero at 1 HP (stage 0) |
| `r2-battle-test-s1_unit_leader_1hp` | stage 1 Fort 1 encounter, Estrada at 1 HP: `10:A:2;400:A:2;700:A:2` |
| `r2-battle-test-cls-s01`..`s11`, `l01`..`l09`, `b1` | class battles at the fight banner (animations off; just let them run; configurations in `scratchpad\r2-battle\plan1.txt`) |
| `r2-battle-test-cls-x1` | Princess and Kraken, battle frame 60, terrain index 0 (shallow water): Starlight, Maelstrom |
| `r2-battle-test-elem-e1x0`..`e1x4` | magic classes with the target element forced (battle frame 60) |
| `r2-battle-test-boss-<name>` | post-battle event armed, only the Tower card (input as in `bossrun.py`; names in `scratchpad\r2-battle\boss_list.txt`, plus `bs03` = Galan) |

Key logs: `r2-battle-s01`..`s11`, `l01`..`l09`, `e*`, `x1` (attack names),
`tu01`..`tu22` (tarot use), `th1`/`th2` (tarot help), `tac1`, `anim1`,
`run1`, `neu1`..`neu3`, `draw1`, `towin1`, `lvl2`, `lead3`, `ghost1`,
`bs*` (boss events).

## Open issues

1. **Fixed and VWF names mixed** (cosmetic, highly visible). Names that fit
   in 8 cells only have their in-place entry, so they are drawn letter-spaced
   ("S l a s h", "F i r e   A r t") next to VWF names ("Lightning") in the
   same attack window, and in the TAROT list ("M a g i c i a n" above
   "Priestess"). Proposed fix in `translation/en/ui.txt`: add a
   `vwf width=8 tiles=8` entry with the same text for every name that has
   only an in-place entry. Attack names displayable in battle (37):
   `20F224 20F22E 20F238 20F242 20F29C 20F2A6 20F2C4 20F378 20F382 20F3D2
   20F3E6 20F3FA 20F404 20F40E 20F422 20F436 20F44A 20F45E 20F472 20F490
   20F49A 20F4D6 20F4E0 20F4F4 20F4FE 20F508 20F512 20F526 20F54E 20F5A8
   20F5D0 20F5DA 20F5EE 20F602 20F648 20F68E 20F6B6` (the never-drawn
   `20F30A`, `20F3F0`, `20F652` and the "Magic"/`20F576` placeholders can get
   one too, harmless). Tarot names (18): `20F13E 20F152 20F15C 20F170 20F17A
   20F184 20F18E 20F198 20F1A2 20F1B6 20F1CA 20F1D4 20F1DE 20F1E8 20F1F2
   20F1FC 20F206 20F210`. The in-place entries stay (the status screen copies
   the bytes). Both windows are redrawn before each name, so no stale tiles.
   Optional: "WINNERS"/"DRAW" (`20F6C9`, `20F6D2`, `20F6DB`, original English
   in fixed cells) as VWF too.
2. **Static risk, link battles only** (cannot be run in the harness):
   * `0x2E3720` prints a tarot name from `0x20F134` with the tile-mapped
     printer at map `0x91D4` (column 10); that printer ignores the VWF flag,
     so the remapped "Priestess" (9) and "Hierophant", "Hanged Man",
     "Temperance" (10) take 9-10 fixed cells there, up to the screen's last
     column (and finding 1 would not change that).
   * `0x2E3770` composes "<name>" new line "<class>" and prints it at map
     `0x9396` (column 11, 9 cells to the screen edge): English names of
     10-12 letters and 32 class names over 9 letters run off screen.
     `0x2E4B78` copies the class name into a 20-byte stack buffer (the
     longest English class, 15 letters, still fits).
3. **Wording** (suggestions, all checked for fit):
   * `20F7A8` Hierophant help "Puts enemies / to sleep and / helpless." is
     ungrammatical: "Puts enemies / to sleep so / they can't act." (56/47/62
     px of 72, 21 tiles of 26).
   * `20FC48` "Turns the field / into snowy / mountains.": the terrain and
     the item are "Snowy Peaks" (glossary): "into snowy / peaks.".
   * Tactics: the glossary has "Show your guts!" and "Target the leader!",
     the game "Show guts!" and "Get leader!". "Show your guts!" (68 px) does
     not fit 8 tiles; "Target leader!" (60 px) does. Align one with the
     other. "Spread out!" (second tactic) does not describe its effect
     (targets the characters with the most HP); e.g. "Hit the strong!"
     (62 px) if the owner prefers.
   * Optional: "Anim ON"/"Anim OFF" (`2C8402`, `2C842D`) could read
     "Animation ON"/"Animation OFF" (55/59 px) with `tiles=8` (same window
     and tiles as the attack names).
   * Dialogue seen in boss events: `2673CC` Galan "...forgive me... not
     undeath..." reads oddly: "...M-Master Jenga... have mercy... not
     undead... anything but that..." (fits one page); `267439` Estrada "An
     unsettling thing to leave behind..." could be "What an eerie thing to
     say at the end... Something about becoming undead..." (fits);
     `26A5CE` Kain "Huh, that was graceful." means "gracious" (giving up
     with good grace): "Huh, you're a good sport.".
4. **Original quirks** (optional art polish, not translation errors): the
   tactics window opened from the unit window has the pre-drawn English
   header "TAROT" (window frame reused, same in the original); effect sprites
   "M-SHILD" (sic, World) and "R-AGAIN" (Temperance).
5. **For the core / player**: drawing the CITY list of the map's NEXT window
   (`0x204D10`-`0x204D1B`, `sbc.w (XIX), DE` with stale upper bits of XIX)
   writes three words into cartridge space (`0x209208`, `0x209188`,
   `0x209108`) every time; the original ROM does the same. Harmless on
   hardware; flash emulation must keep ignoring writes that are not command
   sequences (the harness prints "flash command write ... (ignored)").

## Next steps

* Apply finding 1 (the orchestrator owns `ui.txt`) and re-run
  `montage.py` and `tarothelp.py` on the new build.
* Link-battle screens (finding 2) need a two-instance link setup or a
  code-level check.
* The paralysis hit label (gfx-survey target 2) was seen in play after Stun
  Cloud (`r2-battle-test-cls-s04`, around frame 300); use that state to
  check the replacement art.
