# Glossary for Ogre Battle Gaiden: Prince of Zenobia (English)

Terminology used across the dialogue (`script.txt`), menus (`ui.txt`),
location names (`locations.txt`) and the text drawn into graphics (labels,
intro, chapter cards, title). Names that already have an established English
form in the Ogre Battle series use that form; everything else is our own
choice. Keep this file in sync when a term changes, and search all
translation files for the old term.

The official forms come from the English releases: Ogre Battle: The March of
the Black Queen (SNES 1995, PSX 1997), Tactics Ogre: Let Us Cling Together
(PSX 1998, PSP 2011) and Ogre Battle 64. The Ogre Battle Saga wiki lists them
per release in each article's localization table. Where the releases differ,
the note says which one we follow and what the others use. "Series name"
means every release uses the same form.

The first column gives the Hepburn romanization of the original term. The
repository keeps no Japanese text; the Japanese source of every string is in
the local localization database (`build/l10n/strings.csv`, generated from your
own copy of the game, see `docs/localization.md`).

## People

| Romanized | English | Notes |
|---|---|---|
| Torisutan | Tristan | Prince of Zenobia; default hero name (player can rename) |
| Fikusu Torishutoramu | Pheryx Tristan | the prince's true name, as in Tactics Ogre: Let Us Cling Together (PSP), where he is "Pheryx Tristan Xenobia" (stage 0 reveal; Baldur and Orosov use it, Grant says "Lord Tristan") |
| Wōren | Warren | Astrologer (series name) |
| Esutorāda | Estrada | Leader of the volunteer army, the hero's mentor |
| Kein | Kain | The hero's friend |
| Akueriasu | Aquarius | |
| Nāna | Nana | Princess |
| Bānya | Banya | Hero's foster mother figure (letter in stage 0) |
| Jenga | Jenga | Bandit-backed sorcerer (stage 5 boss) |
| Kazuma | Kazuma | Samurai bandit boss |
| Garan | Galan | Beast tamer |
| Barudoru | Baldur | Main antagonist ("saviour from the dark world") |
| Marenoa | Malenoa | Nixie |
| Gurosu | Gross | Mercenary |
| Daramu | Dalam | |
| Kirosu | Kiros | Weretiger |
| Āresu | Ares | Series name (Ogre Battle) |
| Raian | Lyon | Series name: Lyon the Beast King, a beast tamer in Ogre Battle |
| Berugo | Bergo | |
| Jakku | Jack | Jack-of-all-trades shopkeeper ("Nandemoya Jakku", "Jack's general store") |
| Roki | Loki | Summoned hero (Chariot card) |
| Mārin | Merlin | Summoned sage (Hermit card) |
| Guran (ō) | King Gran | Series name |
| Ransurotto | Lanselot | Tactics Ogre: Let Us Cling Together (PSP), the release that gives "Pheryx Tristan"; the Atlus releases call him Lans (Lans Hamilton) |
| Girubaruto | Gilbert | Atlus releases (wyvern master); the PSP Tactics Ogre calls him Gilbald |
| Kanōpusu | Canopus | Series name |
| Asshu | Ashe | Series name |
| Denebu | Deneb | Series name (witch) |
| Yūria | Yuria | Canopus's younger sister |
| danshaku | the Baron | |
| kodama | Kodama | |
| yami no kishi | the Dark Knight | "D.Knight" in 8-cell name fields (`tables/names.txt`, max 8 letters); dialogue keeps "the Dark Knight" |
| Asumodeusu | Asmodeus | Devil card summon |

## Places

| Romanized | English | Notes |
|---|---|---|
| Zenobia | Zenobia | Ogre Battle and the Atlus releases; the PSP Tactics Ogre spells it Xenobia |
| Zeteginea | Zeteginea | the empire; Atlus releases (the PSP Tactics Ogre: Xytegenia) |
| Esutoa | Estoa | |
| Rihitofurosu | Lichtfloss | |
| Roshuforu kyōkai | Roshfol Church | |
| Rādo | Lard | Bandit town |
| Isurando | Isrand | former trade city (not "Island", to avoid confusion) |
| Fureia shotō | the Freia Isles | |
| Donanto | Donant | |
| Shikuto kangoku | Sict Prison | |
| Ritto-tō kaiiki | Litt Island Waters | the sea around Litt Island (chapter 6 area); not "Eastern Sea" |

## Game terms

| Romanized | English | Notes |
|---|---|---|
| giyūgun | volunteer army / the Volunteers | the hero's army |
| yunitto | unit | |
| kyarakutā / kyara | character | menus may abbreviate to "char" |
| rīdā | leader | |
| gōto | goth | currency (series term), lowercase in running text |
| tarotto kādo | tarot card | |
| hensei | Organize | menu command |
| haken | deploy / dispatch | sending units out; the small tag on a deployed unit's status pane reads FIELDED (the original box has 24 px for the word; DEPLOYED does not fit) |
| mahi | paralysis | battle hit label STUN (16x8-px picture) |
| kikan | recall / return | unit returns to HQ |
| honkyochi | headquarters (HQ) | |
| kyoten | stronghold | map terrain/locations |
| kaihō | liberate | towns, churches |
| kaosu furēmu | Chaos Frame | series term (reputation) |
| araimento | alignment | |
| sōshisan | total funds | |
| shojikin | funds | money on hand |
| enjokin | aid | income line |
| haken kosuto | deployment cost | |
| kurikoshi shisan | carried over | |
| senrihin | spoils | |
| zaihō | treasure | buried treasure |
| aitemu sutokku | item stock | |
| sutokku | stock | tarot/item storage |
| kurasu chenji | class change | |
| fōmēshon | formation | |
| fukkatsu | revive | |
| kōdō funō | incapacitated | |
| tekitai yunitto | enemy unit | |
| chūritsu kyarakutā | neutral character | |
| sōgū | encounter | |
| settoku | persuade | |
| L saizu | large (L-size) | two slots in a unit |
| sakusen | tactics | battle orders |
| gattsu o misero | Show guts! | tactic (balanced); 8-tile label, 64 px ("Show your guts!" is 68 px) |
| barabara ni semero | Spread out! | tactic (targets the characters with the most HP) |
| rīdā o nerae | Get the leader! | tactic; 8-tile label |
| iki no ne o tomero | Finish them! | tactic (targets the characters with the least HP) |
| eikō no kagi | Key of Glory | what the empire's agents seek (stage 0) |
| opinion rīdā | opinion leader | series term for the army's leader (item 12 "All Summons" description) |
| shiroi megami-zō | Goddess Statue | item 155; the dialogue uses the same name ("A white Goddess Statue." once) |
| chikei | terrain | |
| shinkai / umi / sōgen / setsugen / shinrin / arechi / shitchi / yama / yukiyama / kazan / gake / sabaku / kyoten / anshō / jōheki | deep sea / sea / plains / snowfield / forest / wasteland / swamp / mountains / snowy peaks / volcano / cliffs / desert / stronghold / reef / ramparts | terrain names; fixed-width tables may need abbreviations |
| hiru / yoru | day / night | |
| teikoku-reki | Imperial Calendar; dates "Imperial Year N" | intro narration ("Imperial Year 15") |

## Style

* Speaker tags in dialogue are written as `Name: text` (the original puts the
  name before an opening corner bracket); continuation pages drop the tag.
* Keep the tarot reading and Warren formal; Kain casual; bandits rough.
* Menus: short imperative or noun phrases, sentence case ("Select a unit.").
* Fixed-width fields: character names have at most 8 letters (a real shorter
  form of the same name, never a cut-off spelling); items and classes have
  short forms in copy tables (`tables/items_short.txt`,
  `tables/classes_short.txt`) for the 8-10-cell fields only, in the CamelCase
  abbreviation style of the attack names ("CurePotn", "SamuMst"); their file
  headers list the fixed abbreviations. Full names everywhere else.
* Text drawn into graphics (menu labels, chapter cards, intro, title) uses
  the same terms; its sources are `labels.txt`, `cards.txt`, `intro.txt` and
  `title.txt` in this folder once the graphics work lands.
