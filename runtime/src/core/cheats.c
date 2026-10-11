/*
 * Cheats for this game. See cheats.h.
 */
#include "cheats.h"
#include "ngp.h"

#include <string.h>

#define FUNDS        0x468Eu
#define FUNDS_MAX    99999999u      /* the game's own cap (code at 0x20D3E4) */
#define CHAR_COUNT   0x4692u
#define REPUTATION   0x4694u       /* Chaos Frame, 0-100 (code at 0x20D3FE) */
#define CHAR_BASE    0x46AAu
#define CHAR_SIZE    18u
#define CHAR_MAX     ((0x517Eu - CHAR_BASE) / CHAR_SIZE)   /* the unit table follows */

static const char *k_names[CHEAT_COUNT] = {"goth", "heal", "level", "rep+", "rep-"};

const char *cheat_name(int id)
{
    return (id >= 0 && id < CHEAT_COUNT) ? k_names[id] : "?";
}

int cheat_lookup(const char *name)
{
    for (int i = 0; i < CHEAT_COUNT; i++)
        if (name && strcmp(name, k_names[i]) == 0) return i;
    return -1;
}

static unsigned rd16(uint32_t a) { return g_lowmem[a] | (g_lowmem[a + 1] << 8); }
static void wr16(uint32_t a, unsigned v) { g_lowmem[a] = (uint8_t)v; g_lowmem[a + 1] = (uint8_t)(v >> 8); }

int cheat_game_ready(void)
{
    unsigned n = g_lowmem[CHAR_COUNT];
    if (n == 0 || n > CHAR_MAX) return 0;
    /* the hero's record: a class, a level and a maximum HP */
    return (g_lowmem[CHAR_BASE] & 0x7F) != 0 && g_lowmem[CHAR_BASE + 1] != 0 && rd16(CHAR_BASE + 6) != 0;
}

int cheat_apply(int id)
{
    if (!cheat_game_ready()) return 0;
    unsigned n = g_lowmem[CHAR_COUNT];
    switch (id) {
    case CHEAT_GOTH: {
        uint32_t v = (uint32_t)g_lowmem[FUNDS] | ((uint32_t)g_lowmem[FUNDS + 1] << 8) |
                     ((uint32_t)g_lowmem[FUNDS + 2] << 16) | ((uint32_t)g_lowmem[FUNDS + 3] << 24);
        if (v > FUNDS_MAX) v = FUNDS_MAX;
        v = (FUNDS_MAX - v < 100000u) ? FUNDS_MAX : v + 100000u;
        for (int i = 0; i < 4; i++) g_lowmem[FUNDS + i] = (uint8_t)(v >> (8 * i));
        return 1;
    }
    case CHEAT_HEAL:
        for (unsigned i = 0; i < n; i++) {
            uint32_t r = CHAR_BASE + i * CHAR_SIZE;
            if (rd16(r + 4) != 0) wr16(r + 4, rd16(r + 6));
        }
        return 1;
    case CHEAT_LEVEL:
        for (unsigned i = 0; i < n; i++) g_lowmem[CHAR_BASE + i * CHAR_SIZE + 16] = 99;
        return 1;
    case CHEAT_REP_UP:
    case CHEAT_REP_DOWN: {
        int v = g_lowmem[REPUTATION];
        v += id == CHEAT_REP_UP ? 10 : -10;
        g_lowmem[REPUTATION] = (uint8_t)(v < 0 ? 0 : v > 100 ? 100 : v);
        return 1;
    }
    default:
        return 0;
    }
}
