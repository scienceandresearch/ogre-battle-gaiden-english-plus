# Short names for fixed-width fields

## Goal

Every character, item and class name must fit the fixed-cell fields that show
it, without cut-off spellings and without the RAM overruns that long names
caused (round 1, `explore-organize.md`, `explore-towns.md`): character names
at most 8 letters, short copies of the item and class tables for the narrow
fields, full names everywhere else.

## State

Done 2026-10-09 (round 2). The build accepts all three files (`maxlen` is
checked on every text, inherited copy entries included). Integration check
done the same day on a full build (`c0f4e5dc...`): every fixed field shows a
whole short name inside its frame, every full-name screen is pixel-identical
to the previous build `e63bffd1...` (see "Integration check").

## Done

### Files

| File | Table | Read by | Entries |
|---|---|---|---|
| `translation/en/tables/names.txt` | `0x20FCEA` (main) | name getter `0x20CC9A` (load `20CCAB`) and link `2E3774` | `maxlen=8` (was 12); 107 names replaced (list below) |
| `translation/en/tables/items_short.txt` | copy of `0x2166B8` | `2157F6` Items list (composer `0x2157C0`: map Items command and its stock-full discard list, organize Item icon), `20D5CA` status pane ITEM, `2E55A0` link item getter (versus item list, link overview line, "was received" message) | 157 short forms |
| `translation/en/tables/classes_short.txt` | copy of `0x20E49D` | `20D451` status pane class (also the map character window), `21303C` organize class change list, `2061AA` unit window class list, `2057BC` recruit list, `2C803A` / `2C8103` battle class picker (link/debug), `2E3785` link overview | 32 short forms |

The copy mechanism (`sites=` on an `@table` line) is in `tools/text/tables.py`
(module docstring). A copy starts from the main table's English and lists only
the entries that need a short form; the comment above each entry is the full
name. The localization database shows the copies as rows
`tbl:2166B8:N:items_short` and `tbl:20E49D:N:classes_short`.

Load sites that keep the full names:
* items: shop list `20745F` (VWF), messages `20939D` (spoils), `215D96`,
  `215E96` (found / obtained / gave up), item data `20D077`, `21596A`,
  `215A31`, `215B8B` (type, stat and price bytes only);
* classes: class change confirmations `20624E` (unit window) and `21312F`
  (organize), both VWF, and the link message "<class> was received."
  (`2E4B84`, column 1 of the message area).

### Decisions

* One item copy for both fields (8 letters), not a 10-letter list copy
  plus an 8-letter status copy: both fields then show the same name, and the
  Items list keeps the original layout (name, at least two blank cells, a
  two-digit quantity). Stacks go up to 99 (`cp 0x63` when adding at
  `0x215C7A`, merge cap at `0x2156C3`), so a 10-letter name would run into a
  two-digit quantity. Every entry of the status copy needs 8 letters anyway
  (`maxlen` applies to all its texts), so a second file would only add about
  120 alternative spellings.
* The link screens read the short tables too (integration check). In
  the original every item, class and character name has at most 8 cells,
  and the link screens are fixed fields sized for that: the link overview
  prints the item at column 10 (`0x2E372E`, map `0x9294`) and the
  character's name and class at column 11 (`0x2E376A`, map `0x9396`), so
  only 10 and 9 cells remain to the screen edge; the versus item list
  (`0x2C71C2`) fills the battle window's 8-cell field that otherwise holds
  tarot names. The item getter `0x2E55A0` is shared by these two screens
  and the link message "<item> was received." (`0x2E4D1A`), so that message
  shows the short item name too (a 20-byte buffer would fit the full name;
  see Open issues). The class message `2E4B84` keeps the full name.
* Dark Knight (story character, entry 1654) is `D.Knight` in the name
  fields; dialogue keeps "the Dark Knight".
* Both Lycanthrope classes (39, 41) are `Lycan`; the original gives them the
  same name too.
* Short forms are unique: within each table, two entries share a text only
  when their full English is the same (Lycan, and the names that already
  repeat in the pool, e.g. William). The two Catherines (French and English
  readings) and the two Christines became distinct (Katrine / Kathryn,
  Kristine / Kristin).

### Style guide

**Character names** (no abbreviations: they must read as names). In order of
preference:
1. *variant*: an attested shorter form or spelling of the same name: another
   language's form (Valentin, Frederic, Christof, Costanza, Narciso, Encelado,
   Menesteo), a short or pet form (Bastian, Polly, Berry, Cinders), the root
   name of a patronymic (Christen, Hernando), a surname spelling (Burrows,
   Hampsher, Boville), the name without its particle (Artagnan);
2. *reading*: a shorter spelling of the katakana reading that still reads as
   a name (Barinton, Patrash, Galintis); Greek names in Greek spelling with
   k / t / f (Aigistos, Deimakos, Tessalos, Telkines);
3. *related*: when nothing shorter exists, a close real name: same root
   (Church, Chambers, Little, Livings, Miserere), same person or deity
   (Napoleon, Derceto, Libera), same family or myth (Otrera, Penthesilea's
   mother), or a real name of nearly the same sound (Karamzin, Musolino,
   Cervera, Polydora).

Never a cut-off spelling of the English name. A new name must not repeat
another entry of the table.

**Items and classes** (as the attack names in `ui.txt`: ThndFlar, SncBlade,
PtroBrth):
* Names of 8 letters or fewer are not listed (the copy keeps them).
* Drop the spaces and keep a capital on each word (CamelCase); drop "of",
  "to" and "'s"; "X of Y" becomes "YX" (Ring of Power -> PowerRng, Heart of
  Leo -> LeoHeart, Mail of Nails -> NailMail).
* Shorten as little as needed. Keep the word that identifies the item or class
  whole where possible and shorten the generic one.
* Recurring words always take the same short form:
  * items: Sword Swd, Blade Blde, Spear Spr, Lance Lnc, Staff Stf, Shield
    Shld, Ring Rng, Stone Stn, Charm Chrm, Crown Crwn, Mantle Mntl, Garb Grb,
    Armor Armr, Fang Fng, Pumpkin Pmpk, Thunder Thnd, Dragon (Dragoon) Drgn,
    Death Dth, Devil Dvl, Black (Jet-Black) Blk, White Wht, Silver Slvr (Slv
    before a word kept whole: SlvTiara, SlvCross), Flame Flm, Battle Btl,
    Mystic Myst, Samurai Samu, Down Dn, Light Lite, Night Nite;
  * classes: Master Mst, Tamer Tmr, Knight Knt, Priest Prst, Hunter Hntr,
    Dragon Drgn, Black Blk, Silver Slvr, Death Dth, Stone Stn, Pumpkin Pmpk,
    Samurai Samu, Light Lite, Curse Crse.

  Lite, Nite, Crse, Pmpk, Thnd, Snc and Ptro follow `ui.txt` (Starlite,
  Nitemare, CrseStrk, PmpkDrop, ThndFlar, SncBlade, PtroBrth).
* Other long words lose inner vowels, then doubled letters (Potn, Rtrn, Tkt,
  Sumns, Scnt, Whsp, Scmtr, Enchantr, Salamndr, Hellhnd), or take a natural
  shorter word (Gold, Burn, Pure, Vest, Helm, Maid, Dowse, Mountain, Angl for
  Archangel, Berserk, Necro, Lycan, Skel, Plat, Enig, Zomb).
* Where abbreviating both words would hide the item, its proper name or key
  word stands alone: Musashi, Kusanagi, Mikado, Benkei, Ozrick, Kokuou,
  Iskender, Osafune, Kotodama, Overlord, Martyr, Mirror, Rainbow, Goddess,
  Twinkle, FullMoon, 7-League.
* Spell items reuse the attack names' fixed forms (PtroBrth, Lightnng,
  Nitemare).

### Names replaced (107)

Kind: *variant*, *reading*, *related* as in the style guide.

| Entry | English | Short form | Kind |
|---|---|---|---|
| 61 | Carpenter | Carver | related |
| 80 | Karamazov | Karamzin | related |
| 116 | Christensen | Christen | variant |
| 117 | Christopher | Christof | variant |
| 142 | Gertlinger | Gertling | variant |
| 172 | Schoenberg | Shenberg | reading |
| 180 | Schneider | Snyder | variant |
| 185 | Singleton | Sinton | related |
| 206 | Steinberg | Stenberg | variant |
| 221 | Sebastian | Bastian | variant |
| 225 | Cervantes | Cervera | related |
| 242 | D'Artagnan | Artagnan | variant |
| 243 | Chamberlain | Chambers | related |
| 245 | Churchill | Church | related |
| 254 | Tensberger | Tensberg | variant |
| 320 | Hampshire | Hampsher | variant |
| 327 | Bernstein | Bernsen | related |
| 337 | Barrington | Barinton | reading |
| 338 | Balthazar | Baltazar | variant |
| 339 | Valentine | Valentin | variant |
| 340 | Burroughs | Burrows | variant |
| 350 | Patrasche | Patrash | reading |
| 387 | Frederick | Frederic | variant |
| 393 | Blackburn | Blackett | related |
| 405 | Pleasance | Pleasant | related |
| 407 | Hernandez | Hernando | variant |
| 408 | Hendriksen | Hendriks | variant |
| 422 | Beauville | Boville | variant |
| 429 | Bonaparte | Napoleon | related |
| 442 | McNaughton | McNaught | variant |
| 443 | McPherson | McPhee | related |
| 454 | Malkovich | Malkovic | variant |
| 464 | Mussolini | Musolino | related |
| 486 | Reinhardt | Reinhard | variant |
| 498 | Lancaster | Lansing | related |
| 513 | Littlejohn | Little | related |
| 516 | Livingstone | Livings | related |
| 572 | Amaryllis | Amarilis | variant |
| 616 | Esmeralda | Smeralda | variant |
| 624 | Emmanuelle | Emanuela | variant |
| 632 | Elisabeth | Elisabet | variant |
| 633 | Elizabeth | Lizabeth | variant |
| 661 | Catherine | Katrine | variant |
| 674 | Catherine | Kathryn | variant |
| 690 | Christine | Kristine | variant |
| 691 | Christine | Kristin | variant |
| 712 | Constantia | Costanza | variant |
| 752 | Cinderella | Cinders | variant |
| 775 | Josephine | Josefine | variant |
| 789 | Stephanie | Stefanie | variant |
| 792 | Strawberry | Berry | variant |
| 809 | Chestaria | Chestria | reading |
| 843 | Dominique | Dominika | variant |
| 866 | Barbarella | Barbette | variant |
| 900 | Francoise | Francine | variant |
| 934 | Peppermint | Pepper | variant |
| 946 | Pollyanna | Polly | variant |
| 972 | Margarita | Margita | variant |
| 1020 | Raspberry | Razberry | reading |
| 1109 | Aegisthus | Aigistos | reading |
| 1126 | Automedon | Medon | variant |
| 1130 | Agamemnon | Agamenon | variant |
| 1136 | Ascalabus | Ascalabo | variant |
| 1144 | Apemosyne | Apemosne | reading |
| 1189 | Eupalamus | Eupalamo | variant |
| 1192 | Euphorbus | Euforbo | variant |
| 1212 | Enceladus | Encelado | variant |
| 1228 | Castalian | Castalia | variant |
| 1240 | Galinthias | Galintis | reading |
| 1298 | Staphylus | Stafylos | variant |
| 1299 | Sthenelus | Stenelos | reading |
| 1306 | Semiramis | Semira | related |
| 1331 | Dea Syria | Derceto | related |
| 1340 | Deimachus | Deimakos | reading |
| 1342 | Deucalion | Decalion | reading |
| 1345 | Theophane | Teofane | variant |
| 1349 | Thessalus | Tessalos | reading |
| 1356 | Telchines | Telkines | reading |
| 1363 | Telephassa | Telephe | variant |
| 1368 | Thrasymedes | Thrasius | related |
| 1372 | Nausithous | Nausitos | reading |
| 1377 | Narcissus | Narciso | variant |
| 1407 | Passacaglia | Partita | related |
| 1466 | Proserpina | Libera | related |
| 1482 | Peparethus | Pepareto | variant |
| 1495 | Persephone | Kore | variant |
| 1499 | Berecyntia | Berenice | related |
| 1509 | Penthilus | Pentilos | reading |
| 1510 | Penthesilea | Otrera | related |
| 1521 | Hopladamus | Hopladam | variant |
| 1526 | Polyphony | Harmonia | related |
| 1531 | Polydamna | Polydora | related |
| 1542 | Magna Mater | Matrona | related |
| 1549 | Misericord | Miserere | related |
| 1564 | Musagetes | Musagete | variant |
| 1574 | Metaneira | Metanira | variant |
| 1578 | Menestheus | Menesteo | variant |
| 1579 | Menoetius | Menoitos | reading |
| 1582 | Melanippus | Melanipo | variant |
| 1609 | Rhadamanthys | Radamant | variant |
| 1620 | Licymnius | Licimnio | variant |
| 1621 | Lityerses | Litierse | variant |
| 1625 | Libentina | Libentia | variant |
| 1632 | Lycophron | Licofron | variant |
| 1633 | Lycomedes | Licomede | variant |
| 1641 | Leucippus | Leucipo | variant |
| 1654 | Dark Knight | D.Knight | story character |

The item and class short forms are listed with their full names in
`items_short.txt` and `classes_short.txt`.

## How to test / reproduce

```
python -m tools.patch.build rom/baserom.ngc -o <scratch>/x.ngc   # checks maxlen on every table text
python -m tools.text.tables rom/baserom.ngc 2166B8 20E49D 20FCEA  # load sites and which table each reads
python -m tools.text.test_tables                                  # incl. test_rom_fixed_fields (below)
python -m tools.text.l10n export rom/baserom.ngc                  # copy rows: tbl:ADDR:N:items_short / classes_short
```

A copy entry inherited from the main table that is too long stops the build
with "... give the copy table its own entry N"; a name over 8 letters with
"... is longer than 8 characters". `test_rom_fixed_fields` (in
`tools/text/test_tables.py`) builds the real `translation/en/tables` and
fails if a fixed-cell load site (items `2157F6`, `20D5CA`, `2E55A0`; classes
`20D451`, `21303C`, `2061AA`, `2057BC`, `2C803A`, `2C8103`, `2E3785`; names
`20CCAB`, `2E3774`) reads a text longer than 8 characters, or if a
full-name site (the lists under "Load sites that keep the full names")
stops reading the main table.

### Integration check (2026-10-09)

Build `c0f4e5dc...` (the three files above on top of the round-1 sources)
against the previous build `e63bffd1...`: the two ROMs differ only in the tables
region and the load operands of the copy sites (the tarot table moved inside
the tables region; its entries are unchanged). The ROM layout check passes.
Each scenario ran on both ROMs with the same state and input (harness
`ngp_harness.exe <rom> --load-state build/states/<state>.state --frames N
--input "..."`); text logs of the new build are `build/textlogs/r2short-*.txt`
(local). Patched states: character records at `0x46AA` (18 bytes each:
class id in the low 7 bits of +0, name index in the low 12 bits of +2),
item stock at `0x538E` (pairs of item id and quantity).

| Screen | State and input | New build | Previous build |
|---|---|---|---|
| Items list, all 189 items | `r2-systems-test-items_1_60` (also `_61_120`, `_121_180`, `_181_189`) + `20:A:2`, then `R` every 40 frames | CurePotn ... BondFutr, two blank cells, quantity | "Cure Potio", "Bond to Fu" cut |
| Organize Item list | `towns-organize_items`, stock items 61-120 x 99, + `20:R:2;40:R:2;60:R:2;80:R:2;100:R:2;140:A:2;220:A:2`, then `R` | FlameRod  99 | "Rod of Fla99" |
| Stock-full discard list | `towns-items_rod_full` + `20:A:2;80:A:2;160:A:2;240:A:2;320:A:2;440:A:2` (Yes) | DowseRod / SoulCall | "Dowsing Ro" |
| Status pane ITEM | `organize-test-equip-long` + `10:A:2;220:D:2;290:D:2` | MalacSwd, Musashi, BlkArmor | letter on the frame |
| Status pane class, all 32 long classes | `organize-test-2units` with patched classes + `10:A:2;150:A:2;210:A:2;300:D:2;350:D:2;400:D:2;450:D:2;500:R:2;560:D:2` | Berserk ... SlvrKnt inside the frame | letter on the frame |
| Status pane name and top bar | `organize-test-equip-long`, names 1654 / 1609 | D.Knight, Radamant | "Dark Kni", "Rhadaman" + letter on the frame |
| Organize class change | `organize-test-cc-samurai` + `10:R:2;40:R:2;80:A:2;160:D:2;200:A:2;280:D:2;320:A:2;440:A:2` | list SamuMst; prompt "Samurai Master?"; pane SamuMst | "Samurai Ma" + letter on the frame |
| Unit window class change | `organize-test-uw-samurai` + `10:A:2;60:R:2;100:R:2;150:A:2;260:R:2;300:U:2;340:A:2` | list SamuMst; prompt "Samurai Master?" | "Samurai Master" over the map |
| Recruit list | `r2-systems-test-recruit_dragoon`, leader classes 5, 8, 14, 15, 19, 23, 29, 97 + `20:B:2;80:A:2;130:R:2;170:A:2;240:R:2;270:R:2;310:A:2` | RedDrgn 1400, BlackKnt 1160, SkelKnt 450, MadHalwn 200 | names run into the prices |
| Map character window | `towns-items_equip_long`, character 3 = name 1654, class 60 | D.Knight / PlatDrgn | over the frame |
| Swap units list | `organize-test-2units`, name 1654 + `10:A:2;150:R:2;190:R:2;230:A:2` | 2.D.Knight | over the frame |
| NEXT unit list | `organize-test-s0-2deployed`, names 1654 / 1609 + `20:A:2;100:A:2` | D.Knight, Radamant | over the frame |
| Deploy list | `organize-test-s0-2units`, names 1654 / 1609 + `10:D:12;50:A:2;110:R:2;160:A:2` | 2.Radamant Plain | "RhadamantPlain" over the frame |
| Unit window title | `organize-test-s0-2units`, name 1654 + `20:A:2;80:R:2;130:A:2` | D.Knight | over the frame |
| Leader top bar, map afterwards | `organize-test-s0-longleader` + `10:A:2;60:A:2;160:B:2;220:B:2;320:B:2` | Radamant; map intact | "Rhadaman" (clamp); map intact |
| Stock character | `organize-test-stock2-top` + `10:A:2;60:A:2;160:L:2;230:L:2` | Christen | over the frame |
| Shop lists | `towns-items_ticket` + `20:A:2;80:A:2;150:A:2;200:D:2`; `r2-systems-test-shop7_funds` + `20:R:2;50:R:2;80:R:2;120:A:2` | full names | identical |
| Found / treasure / obtained / gave up | `map-item_found`, `map-treasure1`, `towns-items_rod_full` (A every 80 frames; for "gave up" `400:R:2;440:A:2`) | full names | identical |
| Tarot list, drawn card | `towns-cb_tarot_a`, `towns-cb_tarot_b` + `20:L:2;60:A:2;130:R:2;190:R:2;250:R:2`; `towns-s0_hind_liberated` + A every 90 frames | full names | identical |

Not reachable in the harness: the link screens (they need a partner; checked
in the code, see Decisions) and the battle class picker (`0x2C8017`,
link/debug code). The spoils message (`20939D`) was not reached; it reads
the main table, which is unchanged (same address, same bytes).

## Open issues

* The link message "<item> was received." (`0x2E4D1A`) shows the short
  item name, because it shares the getter `0x2E55A0` with the 8-cell link
  fields. If the full name is wanted there (its 20-byte buffer fits 15
  letters), a code patch can give that one call its own entry point that
  loads the main table (for example `ld.l XIY, (0x215D97)`, the operand of a
  main-table load, then `jp 0x2E55A5`); low priority, link play only.
* Not seen in play (need a link partner or debug code): the link overview
  and versus item list (checked in the code, see Decisions) and the battle
  class picker `2C803A` / `2C8103`. All of them read the short tables.
* The 26 *related* names are judgment calls (no shorter form of the same
  name exists); a reviewer may prefer others. The localization database
  shows the Japanese source of each.
* Harness observation: turning a page of the Items list makes the game write
  to cartridge space `0x2090C8`-`0x209248` (the harness prints "flash command
  write ... (ignored)"). The original Japanese ROM does the same; the writes
  carry no flash command sequence and change nothing.

## Next steps

* Orchestrator: `glossary.md` note that the Dark Knight's name field reads
  `D.Knight`; the STATUS item "Fixed-width fields" is done. The header
  notes of `classes.txt` ("long names may still need shortening") and
  `items.txt` ("names are copied into fixed-cell lists ...; keep them
  short") predate the copy tables: the main tables now feed only VWF
  screens, the link class message and item data.
* When link play can be tested (two harness instances), look at the link
  overview, the versus item list and the "was received" messages.
* Review pass over the short forms with the localization CSV (category
  `table:items_short`, `table:classes_short`, `table:names`).
