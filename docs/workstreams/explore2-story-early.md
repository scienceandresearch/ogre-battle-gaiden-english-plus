# Explore round 2: early story (stages 2-6)

## Goal

Play the story of stages 2-6 in the English build (deploying units,
recruiting, liberating towns and churches, boss fights, stage clears, chapter
cards, scenario map) and read every dialogue page in context: does it fit,
read naturally and match the scene? Report untranslated text, overflowing or
cut pages, and wording that contradicts the situation.

## State

Done (2026-10-10, round 2). **All 445 messages of the stage 2-6 sections of
`translation/en/script.txt` were shown on screen and checked** (stage 2: 107,
stage 3: 98, stage 4: 40, stage 5: 76, stage 6: 124), plus the stage 0 revisit
between stages 5 and 6 (Banya's letter, 21 messages) and 148 distinct system
messages met in real play. No untranslated text (the localization export over
all text logs, including the 249 `r2-story-early-*` logs, lists 0
untranslated rows), no new pre-drawn Japanese, no crash or hang.

Findings: one real layout bug (a yes/no question whose third line is
overwritten by the Yes/No choice, Open issue 1), the NEXT menu's city list
cutting long town names to 8 letters (Open issue 3), and wording suggestions
(Open issue 4), two of which correct lines that contradict the scene.

## Done

### Method

* **Real play** (earlier part of this round): from the stage 2 start
  (`progress-stage2_gameplay`) the story was played through stages 2, 3, 4, 5,
  the Lichtfloss and Estoa revisits and stage 6, with a driver that runs the
  map in chunks, answers system messages by rule and records every page and
  system message with a screenshot and a text log. Units were deployed from
  the command bar, towns, churches and hidden towns were liberated, Aquarius
  and Goldie recruited, Kazuma, Galan and Jenga fought (testing aid: enemy HP
  set to 1 once a battle starts), every stage cleared to the
  "Congratulation!" screen and the scenario map, and every chapter card
  passed.
* **Every branch** (this part): each event handler of stages 2-6 was run
  through the map's pending-script pointer (testing aid, as in
  `explore2-story-late.md`: script address in `0x61F0` of a calm map state,
  then `10:A:2;60:B:2`), once per branch: first visit, repeat visit (story
  flag set), after the stage is cleared, yes/no answered both ways, in-dialogue
  A/B choices both ways, Chaos Frame high/low, no money, army full, item
  owned or not, character in the current unit or not. 155 runs, page
  screenshots of the dialogue window, coverage from a harness watch on the
  script dispatcher (an opcode fetch at `0x20023D` of the message address).
* **Openings** were captured from the scenario map (A on the stage marker:
  chapter card, then the opening), including the Lichtfloss revisit after
  stage 5 (both answers to the king's request, and the low-Chaos-Frame
  variant without the request) and the Estoa revisit (Banya's letter).
* Hero name "AAAAAAAA" (widest), text speed fastest.

### What was checked

| Area | Result |
|---|---|
| Stage 2 (Satsu): opening, Kazuma (join / refuse-fight / refuse-then-join / traitor return / army full so Aquarius leaves), Aquarius scene, Mugunt, Kaf, Yoshi, Colomban (bronze maiden: both prices, buy, refuse, no money, after), Parna (+ post-game Lancelot), Ijiriko, both churches (Iron Rosary, Netobi request, Aquarius in the unit) | fits; **Open issue 1** (Colomban price question) |
| Stage 3 (Lichtfloss): opening with the king and Nana, Galan (both greetings) and his defeat, every town incl. Satsurama both Chaos Frame branches, both churches (White Cross, the boy-soldier question both answers), all repeat and after-clear lines; revisit after stage 5 (both answers, low Chaos Frame) | fits; wording 0x266E70 |
| Stage 4 (Roden): opening, Brunn (barrier without the ruby, ruby scene with and without Aquarius, after clear), every town, the ruby church (with and without the ruby) | fits |
| Stage 5 (Litt Island Waters): opening (with Aquarius's lines), Jenga (both greetings), Estrada's death (with and without Aquarius), every town incl. the immortality question both answers, the princess/craftsman scene (both variants), both churches (White Cross trade yes/no, again, no cross; Silver Rod purification yes/no) | fits; **Open issue 2** (tight yes/no), wording 0x26876F |
| Stage 6 (Nessa): opening narration (with and without Aquarius), Nanitte elder and the closing discussion, every town and its A/B question both ways, Goldie (yes, no-then-yes, no-no, no money, army full), the Ryuk gift and post-game Gilbert, the donation church (both answers, no money, high Chaos Frame), the other churches | fits |
| Estoa revisit (between stages 5 and 6): villager, Banya's letter, the prince reveal | fits |
| System messages in real play: liberated / discovered (all town types, Roshfol Church, Nanitte without type), finished moving, encounters (enemy, neutral), tarot draw / keep / stock full / stat changes / "From now on, tarot card effects apply to every deployed unit.", buried treasure, found / obtained / spoils items, deploy cost, income window, "Your headquarters has fallen to the enemy..." | all English, all fit; left margin see Open issue 6, spoils indent Open issue 5 |
| Stage clears 2-6: closing scene, clear animation, "Congratulation! ... BONUS MONEY n Goth." (pre-drawn English), scenario map with the next markers and the popup | OK |
| Chapter cards 3-7 (stages 2-6) | pre-drawn Japanese, already tracked by the chapter-card workstream; nothing new |
| NEXT menu (UNIT / CITY lists) | **Open issue 3** (city names cut to 8 letters) |

### Script facts learned (stages 2-6)

* Handlers by town (for later tests): stage 2 Lard/Kazuma `0x265AD1`
  (post-battle `0x265D86`), Mugunt `0x2661AE`, Kaf `0x2662F2`, Yoshi
  `0x2663A2`, Colomban `0x266457`, Parna `0x26663C`, Ijiriko `0x2667FD`,
  churches `0x2668BB` and `0x2669FC`. Stage 3 Fulda/Galan `0x2672BD`
  (post-battle `0x2673C4`), Karkalko `0x267595`, Stomund `0x26764E`, Kamicross
  `0x26772B`, Heide `0x2677A3`, Satsurama `0x26786E`, Linde `0x267977`,
  churches `0x2679CC`, `0x267A5C`; Lichtfloss revisit `0x266FF7` (part of the
  stage 3 script). Stage 4 Brunn `0x267C1F`, Helmut `0x267D2F`, Zigrama
  `0x267DEC`, Porluck `0x267ECF`, Obhelmut `0x267F69`, Isrand `0x267FFF`,
  church `0x2680C5`. Stage 5 Destart/Jenga `0x2682FF` (post-battle
  `0x268456`), Kukrit `0x26875F`, Sarit `0x2687F2`, Urit `0x26887F`,
  Heidecker `0x268963`, churches `0x268AD9` (White Cross), `0x268BE6` (Silver
  Rod). Stage 6 Nanitte `0x268EBC`, Indemura `0x26916C`, Kaldai `0x2691C0`,
  Sattoni `0x269290`, Sakrah `0x26939D`, Kumar `0x26943D`, Ives `0x269576`,
  Dekka `0x269600`, Poai `0x269702`, Kashmiwar `0x269852`, Sagar `0x26991C`,
  Hakatte/Goldie `0x269A2C`, Ryuk `0x269C83`, Gotore `0x269D95`, Spewar
  `0x269E35`, churches `0x269E96` (donation), `0x269F63`, `0x269FD6`,
  `0x26A040`.
* **Lancelot and Gilbert are post-game recruits**: both handlers test
  "stage 12 cleared" (`bflag2 0x0C`). Lancelot joins at Parna (stage 2) with
  Chaos Frame at least 60, hero ALI at least 50, by day and with a free slot;
  Gilbert at Ryuk (stage 6) after stage 6 is cleared, with Yuria's Letter
  (item 161) and a free slot. (The story-late roster aid assumed Lancelot
  joins in stage 3; harmless for its tests.)
* Kazuma's two questions branch on Yes: Yes to the first joins him (he sends
  the unit away; coming back later gives the "traitor" scene and the fight),
  No then Yes ("still reluctant?") fights, No then No joins.
* Galan's greeting needs Kain or Estrada in the current unit, Jenga's needs
  Kain; the other units get a shorter greeting.
* Aquarius joins only with a free army slot (`0x20D288` = 100 - count +
  empty records 1..count); otherwise she leaves (`0x2660FC`). At the end of
  stage 5 Estrada's record is emptied in place (`0x20D356`), so from stage 6
  on the roster has an empty record.
* The Lichtfloss revisit after stage 5 asks the giant request only with Chaos
  Frame 65 or more; accepting opens only the Ein Peninsula (stage 14),
  declining only Estoa (stage 0, Banya's letter), which then opens stage 6.
* The yes/no choice of a question message is always drawn on the window's
  third line, starting about 24 px right of the text start.

## How to test / reproduce

Harness and ROM: `scratchpad\snap2\ngp_harness.exe`, `scratchpad\snap2\ogre_en.ngc`.
Tools (scratch, not committed): `scratchpad\r2-story-early\t\`:
`h.py BASE NAME ADDR [pokes] [--answers A,B] [--pagekeys N:K] [--save-page K NAME] [--save-prompt K NAME]`
(run one handler and capture its pages), `scene.py` (page driver; also used
from scenario-map states with `--first 10:A:2`), `plans.txt` + `runplan.py`
(all 155 handler runs; `FULL` = army full), `cov.py 2 3 4 5 6` (coverage),
`winsheets.py` / `syssheets.py` (window contact sheets), `fit.py ADDR "TEXT"`
(how a candidate English line wraps, with the yes/no rule), `stinfo.py STATE`
(stage masks, flags, Chaos Frame, funds, unit), `poke.py`, `roster.py`. Base
states `t\st\base2..6.state` (copies of the stage map states below). The
real-play driver of the first part is `scratchpad\r2-story-early\play.py`
(+ `r2lib.py`).

States (`build/states/r2-story-early-*.state`, machine-local; `test-` = made with a testing aid):

| State | What it is |
|---|---|
| `s2_four_units_deployed` | stage 2 map, four units out (calm; base for stage 2 runs) |
| `s2_church_liberated`, `s2_ijiriko_discovered`, `s2_parna_discovered` | liberation / hidden town messages |
| `s2_chip_battle_draw_encounter` | encounter that ends in a draw |
| `s2_colomban_statue_prompt` | bronze maiden, 2000 goth question |
| `test-s2_statue_1000goth_prompt_overlap` | **Open issue 1** on screen |
| `s2_kazuma_join_prompt`, `test-s2_kazuma_second_prompt` | Kazuma's two questions |
| `test-s2_aquarius_joined` | "Aquarius joined your army." |
| `s2_join_path_scenario_map`, `s2_cleared_scenario_map` | scenario map after stage 2 |
| `test-s2_lancelot_recruit` | post-game Lancelot at Parna |
| `s3_opening_king` | stage 3 opening (King of Lichtfloss) |
| `s3_all_units_deployed` | stage 3 map (base for stage 3 runs) |
| `s3_linde_discovered`, `s3_satsurama_discovered`, `s3_church_question` | town / church scenes |
| `s3_galan_encounter`, `test-s3_galan_challenge`, `test-s3_galan_defeated` | Galan |
| `s3_next_city_list` | NEXT menu, city list ("Lichtflo"): **Open issue 3** on screen |
| `s3_cleared_scenario_map` | after stage 3 |
| `s4_opening`, `s4_all_units_deployed` | stage 4 opening, map (base for stage 4 runs) |
| `s4_obhelmut_discovered`, `s4_church_ruby_dialogue`, `s4_brunn_ruby_scene`, `test-s4_brunn_barrier` | Brunn and the ruby |
| `s4_undead_battle_at_hq`, `s4_hq_fallen_msg` | battle at the HQ; "Your headquarters has fallen..." |
| `s4_congratulation` | stage 4 bonus screen |
| `test-s5_jenga_encounter`, `test-s5_estrada_death` | Jenga, Estrada's last words |
| `test-s5_whitecross_prompt_tight` | **Open issue 2** on screen |
| `s5_cleared_scenario_map` | after stage 5 |
| `s5after_king_giants_choice`, `s5after_A_scenario_ein_only`, `s5after_B_scenario_estoa_only` | Lichtfloss revisit, both outcomes |
| `s0return_estoa_villager`, `s0return_banya_letter`, `s0return_scenario_stage6_open` | Estoa revisit, Banya's letter, stage 6 opened |
| `s6_opening_narration`, `s6_gameplay` | stage 6 opening ("Three years after Estrada's death..."), map |
| `test-s6_nanitte_elder`, `test-s6_town_choice_money` | Nanitte elder; an A/B town question |
| `test-s6_goldie_prompt`, `test-s6_goldie_joined` | Goldie |
| `test-s6_church_donation_prompt` | donation question |
| `test-s6_gilbert_recruit` | post-game Gilbert at Ryuk |
| `s6_kain_leave_it_to_you`, `s6_congratulation`, `s6_cleared_scenario_map` | stage 6 closing, bonus screen, scenario map |

Text logs: `build/textlogs/r2-story-early-*.txt` (real-play runs `s2a`..`s6o`,
handler runs `p2_*`..`p6_*`, openings `o*`, milestone runs `ms*`). Dialogue
pages are drawn by the VWF typewriter and do not appear in text logs; system
messages and prompts do.

## Open issues

1. **Yes/No choice overwrites a question (bug).** `0x266519` (Colomban, the
   bronze maiden for 1000 goth, Chaos Frame 60 or more) wraps to three lines
   ("... Won't / you buy it?") and the Yes/No choice, always drawn on the third
   line, covers "uy it?". The original question has two lines. Suggested
   text (two lines, 119/120 px): "How about it? It's yours for 1000 goth.
   Won't you buy it?". Test: `test-s2_statue_1000goth_prompt_overlap`, or
   `h.py base2 x 266457 4694=0x50 --answers A`. A scan of all 37 yes/no
   messages found only this one and issue 2; a build check "last page of a
   yes/no message at most 2 lines (or a third line under 22 px)" in
   `tools/text/check.py` would keep it from coming back.
2. **Tight yes/no (polish).** `0x268B20` (stage 5 church, return the White
   Cross) has a 15 px third line "us?" that ends right before the Yes/No
   cursor. Suggested: "I don't know how you came by it, but will you return
   it?" (two lines). Test: `test-s5_whitecross_prompt_tight`.
3. **NEXT menu city list cuts long names to 8 letters.** The CITY tab of the
   NEXT list (composed at `0x204D07`, window map `0x910A`) prints each
   location record's 8-cell name field, which the build fills with the
   English name cut to 8 characters: "Lichtflo", "Kamicros", "Satsuram",
   "Heidecke", "Cassandr", "Kashmiwa" in stages 3-6, 25 names in all (also
   Palmagowa, Sict Prison, Megaholten, Fuchimoni, Doriapolo, Ricantesdo,
   Ixemonica, Spelancas, Queenrock and the free battle area towns). Proposal:
   draw this list with the VWF like the town window (full English names fit
   the 64 px field), or give `locations.txt` an 8-letter short form per long
   name for the record field. Test: `s3_next_city_list` (or from
   `s3_all_units_deployed`: A opens the command bar, A opens NEXT with the
   unit list, A on the NEXT header switches to the city list, Right pages:
   `10:A:2;60:A:2;120:A:2;180:R:2`).
4. **Wording** (English as shown today; all fit one page; widths checked with
   `fit.py`):
   * `0x266E70` "[NAME]: Huh? Who are you?" (the prince saw Nana in the
     throne room a moment earlier and Kain names her next) -> "[NAME]: Huh?
     Aren't you...?"
   * `0x26876F` (Kukrit, shown while Jenga is alive) "Did Jenga mean to make
     himself king or something? What was he going to do with all that
     money?" -> "Does Jenga want to be king or something? What's he going to
     do with all that money?"
   * `0x266469` "You do have good eyes." (praise for their determined look,
     reads as eyesight) -> "Huh, so you're the volunteer army? You've sure
     got a fine look in your eyes."
   * `0x265B12` "You have fine faces." -> "... You have the look of true
     warriors."
   * Lines opening with bare punctuation read oddly in English: `0x266017`
     "Aquarius: ! You want me to fight?" -> "Aquarius: What! You want me to
     fight? ..."; `0x266C28` "Estrada: ! Then ..." -> "Estrada: What! Then
     ..."; `0x266C97` "King of Lichtfloss: ?! I am told ..." -> "... What?! I
     am told ..."; `0x266CEB` "King of Lichtfloss: !! Nana... no, Princess.
     ..." -> "King of Lichtfloss: Nana... no, Princess! Do not say such
     reckless things!"
   * `0x266129` "think about the answer to your words" -> "think about what
     you have said".
   * `0x267D3F` "... For you, I'll tell." -> "You're the volunteer army from
     the south, right? Then I'll tell you a secret."
   * `0x2680AA` "...Now, do plenty of shopping!" -> "...Now, shop to your
     heart's content!"
   * `0x268C98` "This rod sets right wicked powers." -> "This rod purges
     wicked powers."
   * `0x26660F` (said after you bought the statue) "There's only one bronze
     maiden statue. I just found it, but it's rare." -> "That bronze maiden
     statue was one of a kind. I only picked it up, but it's a rare piece."
   * Optional: `0x2679AA` "Buy something, won't you!" -> "won't you?";
     `0x268575` "...Are you there..." -> "...Are you there...?"; `0x26838D`
     "I shall kill you in a way that you do not die" -> "I shall kill you...
     without letting you die"; `0x2669EA` "Thank you for your help." (the
     church hands over the Rainbow Choker for Netobi's mayor) -> "Please see
     that he gets it."; "gentlemen of the volunteer army" (`0x265AE7`,
     `0x266A0C`) addresses an army with women in it -> "friends of the
     volunteer army" / "Ah, so you are the volunteer army."
   * Glossary: "Fix Trishtram" (the prince's true name, `0x263EEA` and later
     stages) and "Key of Glory" (`0x263EA8`) are not in `glossary.md`.
5. **Spoils message indent (polish).** "As spoils of war, you / found "..."."
   (`msg_spoils`, original `0x2096AC`) starts one cell further right than every
   other system message in the same window (seen after battles in stages 4
   and 5): its window setup script sets the text map address `0x96DC`
   (`stv16 0x96DC, var 0x28` at `0x204087`) where the other system-message
   setups use `0x96DA` (e.g. `0x208926`, `0x208EBE`). The original draws it
   the same way; changing the operand would align it, after checking which
   other messages use that setup.
6. Known, confirmed here too: system messages start at the window's inner
   edge while dialogue starts about 8 px further in (story-late Open issue 4).
7. Probably not issues: the bonus money after the real-play clears of stages
   2 and 6 was "0 Goth." (stage 4: 26361, stage 5: 11781; the digits are the
   game's own), most likely because those driven stages took many in-game
   days (formula not checked); the versus-battle items found as spoils are named
   "Forest" and "Deep Sea" (original names, the item descriptions explain
   them).

## Next steps

* Orchestrator: apply 1 (and 2) in `script.txt`, decide on 3 (VWF city list
  or short location forms) and the wording list; add the yes/no line rule to
  the script check.
* After the fixes: re-run `h.py base2 x 266457 4694=0x50 --answers A` and
  `h.py base5 x 268AD9 --answers A` (Yes/No on an empty third line), and the
  CITY list from `s3_all_units_deployed`.
