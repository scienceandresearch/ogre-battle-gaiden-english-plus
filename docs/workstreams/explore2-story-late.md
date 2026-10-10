# Explore round 2: late story (stages 7-17, endings, staff roll, game over)

## Goal

Read every late-story dialogue page in context in the English build (fit,
natural English, matching the scene): stages 7-17 (openings, every location
event and its branches, boss scenes before and after the battle, recruits),
the Baldur conversation and all endings, the staff roll and results screen,
and the game over. Report untranslated text, layout problems and wording.

## State

Done (2026-10-09, round 2). **910 of the 911 messages** of the stage 7-17
sections of `translation/en/script.txt` were shown on screen and checked
(page screenshots, every branch); the last one (`0x27232F`) is unreachable in
the original (see Open issues 3). No untranslated text, no overflowing or
clipped page, no garbled glyph. Findings are layout polish (1 item) and
wording/terminology suggestions (Open issues 1-2). The export
(`python -m tools.text.l10n export rom/baserom.ngc`) lists 0 untranslated rows
over all text logs, including the 350 `r2-story-late-*` logs.

## Done

### Method (testing aids, not part of the game)

* **Stage start**: from `progress-scenario_after_stage2_popup` the open/cleared
  stage masks (`0x546A`/`0x546E`) are set for stage K, the scenario cursor is
  steered to the hotspot and A starts the stage (card, opening).
* **Realistic roster and flags**: because stages 3..K-1 are skipped, the army
  records of generic soldiers get the name index of the story characters who
  would have joined (Lancelot, Goldie, Gilbert, Orosov, Gross, Yorkleif, Ashe,
  Ryan, Grant, Deneb, Birkin, the Lord, Warren, Hayato, by stage), and the
  cross-stage story flags are set (0xD9, 0x3D, 0x4E, 0xCA, 0xD1, 0xD0). The
  script's character tests only compare the name index, so this is enough.
* **Running any event script**: in a calm stage-map state, store the script
  address in `0x61F0` (32-bit) and open and close a menu (input
  `10:A:2;60:B:2`). The map loop runs the pending script when it re-enters map
  mode (`0x2034E3` -> `0x204026`, task 2) and returns to the map after its
  final `ret`. Boss handlers arm their post-battle script in `0x61F0`, so with
  this aid the post-battle scene follows the pre-battle dialogue immediately
  (in the game the battle comes in between).
* **Branches**: flags, characters, items, Chaos Frame, alignment, charisma,
  funds, day/night and the current unit were poked per run (RAM facts below);
  yes/no prompts were answered both ways; in-dialogue A/B choices (Kiros,
  stage 11 sword, Baldur) were taken both ways.
* **Page capture**: the harness runs in 24-frame chunks; when a task waits at
  the end-of-message script (task script slot at `0x203062`) the frame is saved
  and A pressed; text speed `0x469D` = 2; hero name "AAAAAAAA" (widest).
* **Coverage**: harness `--watch R:260000-280000 --watch-log F`: an opcode
  fetch at `0x20023D` reading `DA` at a message address means the translated
  message was entered. Union over all runs: stages 7-17 = 910/911.

### What was checked

| Area | Result |
|---|---|
| Openings 7-12 (13-17 have none), all branches (with/without Aquarius, Orosov, Yorkleif; stage 7 played or not) | OK, all fit |
| Stage 7 (Sict Prison, Gross; Church of Truth; Orosov/Goldie) incl. Gross recruit (Chaos Frame below 55) and both alignment texts of the Church of Truth | OK |
| Stage 8 (Dalam, Yorkleif in every variant, Silver Doll sale/trade/refusal, post-game Ryan and Ashe) | OK |
| Stage 9 (Kiros: kill / spare / high alignment; Baldur's first appearance; Rainbow Choker; Peridot Sword sale; Brynhild) | OK |
| Stage 10 (Malenoa, with/without Aquarius; Orosov's disappearance; Thunder Stone trade; Ogre Shield / White Goddess Statue sales) | OK |
| Stage 11 (barrier, envoys, Kodama, Aquarius leaving (alignment below 39 and Chaos Frame below 49) or the resolve speech; Deneb) | OK |
| Stage 12 (all towns; Baldur, both question sets, all answers; "Not you" when another unit arrives; all five endings, with/without Orosov scene and Aquarius) | OK |
| Stage 13 (Birkin by day and night, both answers, joins only with Aquarius in the unit; the Lord) | OK |
| Stages 14-16 (Firbolg, the Baron and the black robe with Aquarius/Birkin/Kain lines, golem towns, Warren, Bergo with Hayato/Aquarius/Goldie lines, Hayato hire incl. no money / no room) | OK |
| Stage 17 free battle area (Bond to Future gift, recruit scenes: the Lord, Deneb, Canopus + Gilbert, Ares, Gungnir, Trooper) | OK |
| System messages in event context ("You obtained ...", "You received N goth.", "X joined your army.", yes/no prompts) | fit; left margin see Open issues 4 |
| Real map flow in stage 7: walk to Rorom, "The trade city of / Rorom / has been liberated.", tarot draw | OK |
| Stage clear (stage 11): "Congratulation! ... BONUS MONEY 9600 Goth.", scenario map "The Zenobian Age" with the next marker | OK (pre-drawn English) |
| Staff roll | title lines now "OGRE BATTLE GAIDEN / PRINCE OF ZENOBIA", copyright line "(C) QUEST" (round-1 issue fixed); original layout |
| Results screen ("CHAOS FRAME n pt.", "CONQUEST n DAYS", tarot card) | OK (pre-drawn English) |
| After the results: SNK logo, title (pre-drawn, tracked), NewGame -> "Choose where to save." | OK |
| Game over in stage 12 (leader killed in battle): "WINNERS", "With its leader lost, / the volunteer army / has been wiped out...", "GameOver" art, SNK logo, intro crawl | OK |

No new pre-drawn Japanese graphics: the ones seen (chapter cards, organize
icon labels, title logo, intro narration) are already tracked.

### Script and RAM facts learned

* Branch opcodes: `bflag n` branches if story flag n is set; `bflag2 k` if
  stage k is cleared (`0x546E`); `b3e w` if character w (name index, low 11
  bits of record +2) is NOT in the current unit (`0x4581`, unit table
  `0x517E`, 12 bytes per unit); `b40 w` if w is NOT in the army; `b42 i` if
  item i is NOT owned (stock `0x538E`, 60 x [item, count], or equipped in the
  current unit); `bcmp b` if the Chaos Frame (`0x4694`, shown on the results
  screen) is below b.
* Character records: `0x4698 + 0x12*k` (k = 1 .. count at `0x4692`): +0 class
  (0 = empty), +2 name index (| flags), +4 HP, +6 max HP, +8 STR, AGI, INT,
  CHA, ALI, LUK. Hero: CHA `0x46B5`, ALI `0x46B6`. `0x20D288` returns the free
  army slots (100 - count + empty records).
* `0x6088` = 0 by day (Birkin, Warren and Ryan/Ashe checks). Funds `0x468E`.
* Unit map positions: player units `0x6108 + 8*k` (x*32, y*32 words), enemy
  units `0x65D0 + 8*k` (+0 state, +4 x*32, +6 y*32). Writing a position moves
  the unit but does not trigger the location under it.
* Stage 11 opening: with Yorkleif and Grant in the army the hero's class
  becomes Lord (class byte `0xE0`), silently.
* Endings: the Orma handler `0x26F37A` (hero's unit only) asks Baldur's
  questions; flag 0x4E (set by the stage 7 opening) selects the second set,
  flag 0xCA (stage 10, Orosov left) adds the Orosov scene. Answers set flags
  0x9A-0x9D; `0x2702C4` (after Baldur's defeat) picks the ending. Set 2 (normal
  play): A -> 0x9A (leaves with Kain), B then A -> 0x9D (back to Estoa,
  Banya), B then B -> 0x9C (the prince disappears, Kain searches; Aquarius's
  lines only if she is in the army). Set 1: A -> no flag (Zeteginea, Baldur's
  voice), B then A -> 0x9B (fight the empire, Estrada's words), B then B ->
  0x9A. The ending id goes to `0x45CC`, then the staff roll `0x2A2F0C`.
* Free battle area recruits: after a battle, the code at `0x2094F9` arms
  `0x273068` when the word at `0x5098` is 0 (and `0x52AA` is not 0x65); the
  script checks the defeated leader (`0x5096`: the Lord, Deneb, Canopus (needs
  Gilbert), Ares) or class (`0x5094`: Gungnir 0x5C, Trooper 0x5E). The
  messages were checked by running `0x273068` with these values poked.

## How to test / reproduce

Harness and ROM: `scratchpad\snap2\ngp_harness.exe`, `scratchpad\snap2\ogre_en.ngc`.
Tools (scratch, not committed): `scratchpad\r2-story-late\`:
`startstage.py K --pokes ...` (stage start + opening pages),
`realistic.py K` (roster/flag pokes for stage K), `h.py BASE NAME ADDR [pokes]
[--answers A,B] [--pagekeys N:B]` (run a script via `0x61F0` and capture
pages), `plan.py planK.txt` (all runs of a stage; `plan7.txt`..`plan17.txt`
list every run with its pokes), `scene.py` (page driver), `cov.py` (coverage),
`stagesheet.py` / `pagesheet.py` (contact sheets), `sfull.py K` / `outline.py
K` (stage script listings), `poke.py` (state RAM patch: `ADDR=VAL[:w|:l]`,
`flag+N`, `stage+K`, `item+I`, `charK=INDEX`), `roster.py STATE`.

States (`build/states/`, machine-local; "aid" = made with a testing aid):

| State | What it is |
|---|---|
| `r2-story-late-s7_gameplay` .. `s17_gameplay` | real-time map after each stage's card and opening (aid: stage jump + realistic roster/flags) |
| `r2-story-late-sK_boss_armed` (K = 7-11, 13-16) | gameplay with the boss handler armed; input `10:A:2;60:B:2` plays the boss scene (aid) |
| `r2-story-late-s12_baldur_armed`, `_path1` | Baldur at Orma armed (question set 2 / set 1) (aid) |
| `r2-story-late-s12_baldur_q3`, `_q1` | first Baldur choice page of set 2 / set 1 (press A or B) (aid) |
| `r2-story-late-s12_ending_armed` | post-Baldur ending script armed (ending by flags 0x9A-0x9D) (aid) |
| `r2-story-late-staffroll_start` | staff roll start (title lines), about 7,000 frames to the results |
| `r2-story-late-results_screen` | results screen; A goes to the SNK logo and title |
| `r2-story-late-s12_battle_leader_weak` | stage 12 battle, hero at 1 HP (aid) |
| `r2-story-late-s12_leader_lost_msg`, `_gameover_art` | game over message and "GameOver" art |
| `r2-story-late-s12_encounter_near_orma` | encounter message near Orma (real walk, teleported start) |

Text logs: `build/textlogs/r2-story-late-*.txt` (one per run; the dialogue
itself is drawn by the VWF typewriter and does not appear in text logs).

## Open issues

1. **Wording suggestions** (English as shown; all fit today):
   * `0x26A0F8` "That's the prince of Zenobia... That's our leader!" reads
     as pointing at someone; the line praises his decision: "Spoken like the
     prince of Zenobia... like our leader!"
   * `0x26B0C6` "Nana: Spoken like the blood of King Gran Zenobia." ->
     "Nana: Truly worthy of King Gran Zenobia's blood."
   * `0x26A5CE` "Kain: Huh, that was graceful." (Gross gives up) -> "Kain:
     Huh. You give up gracefully."
   * `0x26A87C` "Orosov: He?" -> "Orosov: 'He'?"
   * `0x26ADC7` "...Can only you hear it...?" -> "...Are you the only one who
     can hear it...?"
   * `0x26EC3C` "...Take this... It's no use to a coward..." can be read as
     calling the hero a coward; the speaker means himself: "...Take this... A
     coward like me has no use for it..."; also "won't you." -> "won't you?"
   * `0x272CCF` "You put it to good use." reads as past tense -> "You folks
     put it to good use."
   * `0x270C8C` "Birkin: Oh. Is that so? Come again at night, okay?" (the
     player agreed to come back) -> "Birkin: Oh, good. Come back at night,
     okay?"
   * `0x271E19` "Surely there isn't nothing inside just because it's dark?"
     -> "Surely it isn't empty in there just because it's dark?"
   * `0x270989` "Kain: Hey! Has anyone seen [NAME]... [NAME]?" (name twice at
     the end) -> "Kain: Hey! [NAME]...! Has anyone seen [NAME]?"
   * `0x270494` "Let's go to Zeteginea. I want to bring down Zeteginea." ->
     "... I want to bring the empire down."
   * Punctuation: `0x26AD23` "buy something, won't you." -> "will you?";
     `0x26BBEC` "haven't you. I know" -> "haven't you? I know".
2. **Terminology**: the dialogue says "White Goddess Statue" (`0x26ACC7`,
   `0x26ACEC`, `0x26CF22`, `0x26CFF6`, `0x26DCD9`, `0x26DD81`) but the item is
   "Goddess Statue" (item 155, 15-letter limit; the source item name includes
   "white"), so "You obtained "Goddess Statue"." follows "A White Goddess
   Statue" on screen. Suggest item "White Goddess" (13) or dialogue "the
   Goddess Statue". "The Lord joined your army." (`0x2713D6`) may read as a
   religious phrase; "Lord" is the character's name and class, the speaker tag
   is "Lord:". The hero's true name "Fix Trishtram" (`0x26B666`, `0x26C98F`,
   stage 12) is not in `glossary.md`.
3. `0x27232F` (stage 15, "Defeating that Talos is quite something.") is never
   shown: no event entry or pointer references `0x272327` (orphan in the
   original). Nothing to fix.
4. **Layout (polish)**: system messages drawn by the window renderer at map
   `0x96DA`/`0x939A` ("You obtained ...", "Draw a tarot card?", liberation,
   "With its leader lost...") start at the window's inner edge (about 2 px from
   the frame) while VWF dialogue pages start about 9 px in; in event scenes the
   two alternate in the same window, so the text jumps left. Same column as the
   original (whose dialogue lines started with an opening bracket there).
   Option: an 8 px left indent for VWF system messages (their longest lines,
   116 px, still fit 136 px). Screenshot:
   `scratchpad\r2-story-late\out\p8_loc4E_trade\page_004.png`.
5. Not reached: "Your headquarters has fallen to the enemy..." in a late stage
   (needs an enemy unit that walks onto the HQ; moving an enemy record onto
   the HQ does not trigger the capture). Same code and message as stage 2
   (round 1).

## Next steps

* Apply or reject the wording suggestions (orchestrator owns `script.txt`,
  `glossary.md`, `tables/items.txt`).
* Consider moving the aids (`0x61F0` script runner, page driver with
  coverage, roster pokes) into `tools/` so later sessions can replay any scene.
* HQ-fallen game over in a late stage: find the enemy route fields so an
  enemy can be sent to the HQ.
