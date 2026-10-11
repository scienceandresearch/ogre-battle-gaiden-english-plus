# Explore: battle

## Goal

Play-test the English build through battles and find text that is still
Japanese or does not fit: battle start, attack names, the tactics menu
(Battle commands), HP/damage numbers, results (win/loss, experience, level
up, items or spoils), unit defeat/retreat, leader defeat, and the unit
window's "Battle commands" entry outside battle. Record how to reach each
screen (saved states + input sequences).

## State

In progress (2026-10-09, round 1). Covered: stage 0 battles (Gring won,
Balzac boss lost on time and won with a tarot card, level-ups), the army
leader killed (game over), a stage 1 unit losing its leader (retreat as a
ghost, "cannot be deployed"), Run, animation off, tactics, tarot cards, a
neutral battle with Persuade (failure; success only in a test ROM), the unit
window's Battle commands outside battle.

Every string drawn by the text renderers in normal battles is English and
fits. Found: two untranslated link-battle strings (by code inspection, not
reachable in the harness), pre-drawn Japanese labels, one overflow (deploy
list), cosmetic spacing, one wording question. Not reached: a draw, spoils
of war in my runs (seen by explore-progress), the battle Item command
(link battles only).

## Done

### How battles start
* A unit stops when it comes near an enemy: "<leader>'s unit has encountered
  an enemy unit." (A), then the enemy's pre-battle lines and a "FIGHT IT
  OUT!" banner (English art in the original), then the battle screen.
* Stage 0: the Balzac castle bandits only say "Go home before you get hurt"
  and the unit "has finished moving" without a fight until Gring has been
  liberated (story logic, same in the original ROM). The Gring bandits fight
  at once; after Gring the Balzac bandits challenge the unit (two lines +
  Estrada's reply); a second attempt on the same enemy starts without talk.
* Neutral characters (stage 1): "<hero>'s unit has encountered a neutral
  character." then "FIGHT IT OUT!".

### Battle screen (compared with the original ROM from the same states)
* Ally panel top right (blue), enemy panel bottom left (red): HP numbers and
  bars, leader marked with a cross; damage numbers, "miss" and "LEVEL UP!"
  are sprites (English in the original).
* Window at the bottom right: the unit's tactic at the start ("Show guts!",
  "Get leader!", VWF), each attack or spell name (blue window for our side,
  red for the enemy): Lightning, Thunder Flare, Ice Storm, Fire Breath
  (VWF); Tornado, Slash, Stab, Strike, Healing (fixed cells). All fit.
* "WINNERS" (0x20F6C9 / 0x20F6D2, English in the original) on the winner's
  side: blue window bottom right for us, red window top left for the enemy.
* In-battle command bar (A during the battle; the battle pauses): Tarot card
  / Battle command / Run / Animation, plus Persuade against neutrals. Labels
  are pre-drawn Japanese sprites (Open issues). Option on an icon shows a
  9 x 3 help box, all English and fitting: "Use a tarot card.", "Change your
  battle tactics.", "Retreat from the battle.", "Turn battle animations on
  or off.", "Persuade a neutral to join your side.".
* Battle command: 4-line tactics window (0x20F10F, VWF) "Show guts! / Spread
  out! / Get leader! / Finish them!", help per line (Option); same layout as
  the original. A picks one and returns to the bar; B resumes the battle.
* Tarot card: "TAROT" list of owned cards (header English in the original),
  7 per page, Left/Right switch pages (tested with all 14 slots filled:
  page 2 "Death, Devil, Tower, Moon, Sun, Judgment, Fool"; "Hierophant" and
  "Hanged Man" use the VWF and fit), help per card, A shows the card art
  (English caption in the original art), A again uses it (e.g. Magician:
  fire damage on all enemies; no text).
* Run: our characters run off, back to the map, unit pushed back, "<leader>'s
  unit has finished moving." (also works against the Balzac boss; no
  "cannot escape" message exists in these battles).
* Pre-battle questions: the stage 1 Fort 3 bandit asks "How about it? Want
  to join us?" with Yes/No in the message window (fits); Yes gets "You
  idiot! If you're going to lie, at least do it better!!", then the battle.
* Animation: "Anim OFF" / "Anim ON" (VWF, fits); with animations off the
  attacks play on the field and their names are still shown.
* Persuade: a failure shows only "miss" over the neutral (61 timings tried,
  all failed; the chance depends on stats, check at `0x2C79F5`). A test copy
  of the ROM with the check forced (`scratchpad\battle\test_persuade.ngc`,
  byte `0x2C78DF` 67 -> 68) shows "Persuasion succeeded!" in the help box
  (fits).

### Results, defeat, retreat
* Battles end when the enemy leader dies or when time runs out (the army
  leader at 0 HP does not end a battle: `explore2-battle.md` "Results").
  On time-out against an enemy unit the enemy wins while any of its members
  stands; against neutral monsters the side that did better wins, or it is
  a draw (corrected later; first noted here as "the side that did better
  wins" for both). The loser is pushed back on the map ("<leader>'s unit
  has finished moving."). No experience numbers are shown; "LEVEL UP!"
  sprites appear at the end (also after a lost battle).
* Enemy leader killed: "WINNERS" at once. Town: "The trade city of Gring has
  been liberated.", "LIBERATION" banner, "Draw a tarot card?" Yes/No, "You
  drew the card "Temperance".", "THANK YOU" / "LUCKY!!" banners, "The Chaos
  Frame went up by 2 points." / "Characters' CHA went up by 2 points.",
  "Keep this tarot card in stock?", the villagers. Boss: "You obtained "Cure
  Potion".", "Congratulation! YOU COMPLETED THIS MAP. BONUS MONEY 6588 Goth."
  (English art in the original), scenario map. All English and fitting.
* Army leader killed (stage 0, Estrada at 1 HP in a patched state): enemy
  "WINNERS", then "With its leader lost, the volunteer army has been wiped
  out..." (fits) and the "Game Over" art (English in the original).
* Other unit's leader killed (stage 1, Estrada's deployed unit, leader at
  1 HP): enemy "WINNERS", the unit turns into a ghost on the map and walks
  away; no message; it leaves the NEXT list. Deploying it again: "This unit's
  leader cannot fight, so the unit cannot be deployed." (fits).
* Spoils of war: not in my runs; explore-progress logged "As spoils of war,
  you found "Snowy Peaks"." (`build\textlogs\progress-f3c.txt`).

### Outside battle (unit window)
* Labels under the unit window icons ("Move", "Battle commands",
  "Organize") are pre-drawn Japanese sprites.
* Option help: "Moves the unit." / "Sets the tactics the unit uses in
  battle." / "Change the formation or dismiss characters." (fit).
* "Battle commands" opens a window headed "TAROT" (English in the original;
  Left/Right do nothing) with the four tactics (VWF, fit); Option shows the
  help of each tactic in the message window (all four fit); A picks one and
  returns to the unit window.

### Static check of indexed text (base + index * size)
`scratchpad\battle\idxscan.py` lists every 24-bit ROM constant added shortly
before a call to `0x200BAC` / `0x200B72` and whether `translation/en/ui.txt`
covers it. Besides pointer tables whose entries are covered and English
originals ("YOU WIN!" / "YOU LOSE" / "YOU DRAWN", "ON", "CPU"), it found the
two untranslated link-battle strings below and the Monitor help at
`0x29BF95` (explore-data's area).

## How to test / reproduce

Harness and ROM: the stable snapshot `snap\ngp_harness.exe` +
`snap\ogre_en.ngc` in the session scratchpad (see the orchestrator's
briefing). States are in `build\states\` (local, not committed). Helper:
`scratchpad\battle\run.py NAME STATE FRAMES INPUT [--every K] [--shots ..]
[--save F NAME] [--ram]` runs the harness, writes
`build\textlogs\battle-NAME.txt`, a contact sheet and prints the decoded log.

    ngp_harness.exe ogre_en.ngc --load-state STATE --frames N --out DIR \
        --input "FRAME:BUTTONS:LEN;..." --shot-every 30 \
        --text-log build\textlogs\battle-<step>.txt
    python -m tools.text.textlog build\textlogs\battle-<step>.txt --en

Map cursor: true map position = camera + screen = `word(0x60AE) +
byte(0x61DE)`, `word(0x60B0) + byte(0x61DF)` (the word alone is the camera).
Location record tiles (x, y) are at about (8x + 84, 8y + 76) in these units.
`scratchpad\battle\steer.py STATE PREFIX START X Y` finds the hold lengths.
To select a unit: A on empty ground (command bar), A on NEXT, Down (more
Downs for later units), A (cursor jumps to the unit), A on it, Right (once per
unit icon), A = unit window; A on Move, steer the flag, A sets the
destination, A again (about 50 frames later) confirms.

Testing defeat: character records are 18 bytes from `0x46AA` (hero), HP at
+4 (stage 0: hero `0x46AE`, Kain `0x46C0`, Estrada `0x46D2`). Item stock
`0x538E` ([id][count] x 60). `scratchpad\battle\patch_state.py IN OUT
ADDR=HEX ...` writes RAM bytes into a state copy (RAM is at file offset 192
+ address). Patched states stay in the scratchpad.

States (`build\states\battle-*.state`):
| State | What | From |
|---|---|---|
| `battle-unitwin_move` | stage 0 unit window on Move | `stage0_gameplay` + `46:A:2;80:R:2;110:A:2` |
| `battle-bcmd_window` | Battle commands window outside battle | `battle-unitwin_move` + `10:R:2;50:A:2` |
| `battle-marching` | flag planted on Balzac | `battle-unitwin_move` + `10:A:2;40:R:29;77:D:102;200:A:2`; `10:A:2` confirms |
| `battle-encounter3` | encounter near Balzac before Gring (talk, no battle) | marching, two Move orders later |
| `battle-after_talk3` | near Balzac, messages closed | encounter3 + `10:A:2;830:A:2;890:A:2` |
| `battle-unitwin_bank2` | unit window there | after_talk3 + NEXT selection |
| `battle-gring_encounter` | encounter at Gring | unitwin_bank2 + `10:A:2;40:L:59;107:U:18;140:A:2;190:A:2`, frame 1950 |
| `battle-gring_talk` | Gring bandit's line | gring_encounter + `10:A:2` |
| `battle-gring_fight_banner` | "FIGHT IT OUT!", battle starts ~40 frames later, won at ~1300 | gring_talk + `10:A:2;300:A:2` |
| `battle-inbattle_cmdbar` | in-battle command bar (Tarot icon) | banner + `100:A:2` |
| `battle-tarot_card_shown` | Magician card shown (A uses it) | cmdbar + `10:A:2;60:A:2` |
| `battle-gring_liberated` | "Gring has been liberated." | banner + 1790 frames |
| `battle-gring_done` | map after the Gring scenes | liberated + B every 100 frames, then A |
| `battle-unitwin_gring` | unit window at Gring | gring_done + `10:A:2;50:R:2;90:A:2` |
| `battle-boss_encounter` / `-boss_talk_end` | Balzac boss encounter / end of its talk | unitwin_gring + `10:A:2;40:R:54;102:D:36;160:A:2;210:A:2` |
| `battle-boss_battle_start` | boss battle (lost on time at ~1940) | boss_talk_end + `10:A:2` |
| `battle-boss_lost1` | map after the loss | |
| `battle-boss_encounter2` / `-boss2_battle_start` | second attempt, battle at once | |
| `battle-boss_defeated` | boss beaten with Magician: `10:A:2;110:A:2;200:A:2;300:A:2` from boss2_battle_start | |
| `battle-stage0_cleared_scenario` | scenario map after stage 0 | boss_defeated + B every 100 frames |
| `battle-neutral_battle_start` | stage 1 neutral battle (Persuade: `10:A:2;80:L:2;260:A:2`) | `progress-stage1_neutral_encounter` + `10:A:2` |
| `battle-s1_estrada_deployed` | stage 1, Estrada's unit deployed at HQ | `progress-stage1_gameplay` + `10:D:20;50:A:2;100:R:2;220:A:2;260:A:2;380:A:2` |
| `battle-s1_estrada_unitwin` / `-s1_estrada_encounter` | its unit window / encounter at Fort 1 | `10:A:2;40:L:41;89:D:180;290:A:2;340:A:2`, frame 3750 |
| `battle-s1_estrada_dead_ghost` / `-s1_after_ghost` | after the lost battle with Estrada at 1 HP | patched encounter + `10:A:2;400:A:2;700:A:2` |

Comparing with the original: the states load into `rom\baserom.ngc` as well
(same RAM layout), e.g. `snap\ngp_harness.exe rom\baserom.ngc --load-state
build\states\battle-gring_fight_banner.state ...`.

Text logs: `build\textlogs\battle-*.txt`. Label screenshots for the graphics
workstream: `scratchpad\battle\gfx\*.png`.

## Open issues

1. **Untranslated (link battles, found by code inspection):**
   * `0x2C835D` (Japanese for "daytime") and `0x2C8361` ("night"), 4-byte
     entries (2 cells + 00 00): time of day drawn with `0x200BAC` from
     `0x2C81E4` (`0x2C835D + 4 *
     (0x45D2)`) into the top-left battle window (map `0x9084`, first tile 9,
     8 cells), next to the terrain name (bottom right, already English). The
     loop at `0x2C8169` (A/B change, Option confirms) only runs when
     `0x45D9` = 1, which only the link code sets (`0x2C5A34`, from
     `0x2E3007`). Suggested: "Day" / "Night" (remap entries; in place there
     are only 2 cells).
   * `0x2E47AA` (2 lines, Japanese for "choose your own battle order"):
     uiprint (`0x200B72`) at map `0x9002`, pointer table `0x2E479E`
     (entries `0x2E47AA`, `0x2E47AA`, `0x2E47BF`), code `0x2E4716`. Its pair
     `0x2E47BF` ("Pick the foe's battle order.") is translated. Suggested:
     "Pick your" / "battle order." (14 cells x 2 lines).
2. **Overflow: deploy list move type** (command bar Deploy, stage 1): the
   move-type column has 5 cells (cols 14-18, map `0x955C`, composed at RAM
   `0x602B` by `0x206E08`); "Plains" puts its "s" on the right frame
   (`scratchpad\battle\out\s1redep\frame_00300.png`); 6-7 letter types
   (Shallow, Forest, Plains) overflow. The original uses 4 cells. Needs
   5-letter names for this list (or the VWF). Area: map/organize.
3. **Pre-drawn Japanese labels** (graphics workstream), screenshots in
   `scratchpad\battle\gfx\`: unit window "Move", "Battle commands",
   "Organize"; in-battle bar "Tarot card", "Battle command", "Run",
   "Animation", "Persuade".
4. **Wording to review:** battle item descriptions 164-188
   (`translation/en/tables/items.txt`, table `0x2C4124`) start "Use during
   battle." The original says "use during a versus match"; the in-battle
   Item command does not appear in normal battles even with these items in
   stock (tested), so they look link-battle only. Suggest "Use in link
   battles." or similar.
5. **Cosmetic:** fixed-cell and VWF entries are mixed in the same window:
   the in-battle tarot list shows "Magician", "Empress", "Emperor",
   "Justice", "Star" letter-spaced next to "Priestess", "Temperance" in the
   VWF; attack names alternate between "T o r n a d o" and "Lightning";
   "WINNERS" is letter-spaced. Drawing every entry of these windows with the
   VWF would look consistent. The unit window help for Organize ("Change
   the formation...") is imperative while the others are descriptive
   ("Moves the unit."). "Congratulation!" and "YOU DRAWN" are the original's
   English art/text (optional fixes).

## Next steps

* A draw ("DRAW", 0x20F6DB), spoils of war in a battle of my own, bosses of
  later stages (special pre-battle talk), battles at night (palette only?).
* Link battles cannot be tested in the single-instance harness (forcing
  `0x45D9` = 1 in a state does not work: normal battle setup clears it at
  `0x2C5EE2`); the two link strings above need a code-level check after
  they are added, or a two-instance link emulation.
* Main text logs: `battle-gbat1` (whole Gring battle), `battle-bcmdR` /
  `battle-bhelp` (command bar + help), `battle-btac` (tactics), `battle-btarot`
  (tarot list), `battle-banimoff`, `battle-brun`, `battle-boss3` (boss lost),
  `battle-boss6` (boss won, level-up), `battle-lead1` (game over),
  `battle-neu3` (Persuade), `battle-s1edef` / `battle-s1redep` (unit leader
  lost, redeploy refused, deploy list overflow), `battle-uwhelp` /
  `battle-tachelp` (unit window help).
