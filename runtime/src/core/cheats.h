/*
 * Cheats for this game: one-shot changes to the game's RAM, used by the
 * player's Cheats menu and the harness (--cheat). Each one stays inside the
 * limits the game itself enforces, so the game treats the result like any
 * other value it could reach:
 *
 *   goth    +100,000 goth (funds, 32-bit at 0x468E; the game caps at 99,999,999)
 *   heal    every living character's HP to its maximum (dead ones stay dead)
 *   level   every character's experience to 99, so the game's own level-up
 *           runs after their next battle (stats grow as in normal play)
 *   rep+    reputation (Chaos Frame, 0x4694) +10, at most 100
 *   rep-    reputation -10, at least 0
 *
 * Character records are 18 bytes from 0x46AA (count at 0x4692): +0 class,
 * +1 level, +4 HP, +6 max HP (16-bit), +8 STR AGI INT CHA ALI LUK, +16
 * experience (0-99), +17 equipped item.
 */
#ifndef NGP_CHEATS_H
#define NGP_CHEATS_H

enum { CHEAT_GOTH, CHEAT_HEAL, CHEAT_LEVEL, CHEAT_REP_UP, CHEAT_REP_DOWN, CHEAT_COUNT };

/* Command-line name ("goth", "heal", "level", "rep+", "rep-"); -1 if unknown. */
const char *cheat_name(int id);
int         cheat_lookup(const char *name);
/* The RAM holds a game in progress (a plausible character list). */
int         cheat_game_ready(void);
/* Applies a cheat. Returns 1 if applied, 0 if no game is in progress. */
int         cheat_apply(int id);

#endif
