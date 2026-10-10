/*
 * K2GE (Neo Geo Pocket Color graphics engine): registers, VRAM and a
 * scanline renderer.
 *
 * VRAM and registers are kept as raw bytes in g_lowmem[0x8000-0xBFFF] so
 * the game reads back exactly what the hardware would return.
 */
#include "ngp.h"
#include "state.h"

uint32_t g_framebuffer[NGP_SCREEN_W * NGP_SCREEN_H];
uint16_t g_framebuffer12[NGP_SCREEN_W * NGP_SCREEN_H];

#define V(a) g_lowmem[(a)]

static uint8_t s_win_x, s_win_y, s_win_w, s_win_h;   /* latched at frame start */
static uint8_t s_vblank_pin;
static int     s_in_vblank;

/* Raster position for 0x8008/0x8009 reads. */
static int raster_line(void) { return g_current_line; }

void k2ge_reset(void)
{
    memset(g_lowmem + 0x8000, 0, 0x4000);
    V(0x8000) = 0xC0;           /* VBlank + HBlank IRQ enabled (BIOS default) */
    V(0x8004) = 0xFF;
    V(0x8005) = 0xFF;
    V(0x8006) = 0xC6;
    V(0x8118) = 0x80;
    V(0x83E0) = 0xFF; V(0x83E1) = 0x0F;   /* default background colour */
    V(0x83F0) = 0xFF; V(0x83F1) = 0x0F;   /* default window colour */
    V(0x8400) = 0xFF;
    V(0x8402) = 0x80;
    V(0x87E2) = 0x00;           /* colour mode */
    s_win_x = 0; s_win_y = 0; s_win_w = 0xFF; s_win_h = 0xFF;
    s_vblank_pin = 0;
    s_in_vblank = 0;
    memset(g_framebuffer, 0, sizeof(g_framebuffer));
}

uint8_t k2ge_read(uint32_t a)
{
    a = 0x8000 | (a & 0x3FFF);
    switch (a) {
    case 0x8008: {
        /* horizontal position in units of 4 ticks */
        uint64_t now = ngp_now();
        unsigned h = (unsigned)(now % NGP_LINE_TICKS);
        return (uint8_t)(h >> 2);
    }
    case 0x8009: return (uint8_t)raster_line();
    case 0x8010: return (uint8_t)((V(0x8010) & 0x80) | (s_in_vblank ? 0x40 : 0));
    case 0x87FE: return 0x3F;
    default: break;
    }
    if (a >= 0x8C40 && a < 0x9000) return 0;
    return V(a);
}

void k2ge_write(uint32_t a, uint8_t v)
{
    a = 0x8000 | (a & 0x3FFF);
    if (a >= 0x9000) { V(a) = v; return; }               /* maps + character RAM */
    if (a >= 0x8800 && a < 0x8900) { V(a) = v; return; } /* sprite attributes */
    if (a >= 0x8C00 && a < 0x8C40) { V(a) = v & 0x0F; return; }
    if (a >= 0x8200 && a < 0x8400) { V(a) = (a & 1) ? (v & 0x0F) : v; return; }
    switch (a) {
    case 0x8000: {
        V(a) = v & 0xC0;
        uint8_t pin = (v & 0x80) ? (uint8_t)s_in_vblank : 0;
        if (pin && !s_vblank_pin) irq_raise(IRQ_INT4);
        s_vblank_pin = pin;
        return;
    }
    case 0x8002: case 0x8003: case 0x8004: case 0x8005:
    case 0x8020: case 0x8021: case 0x8032: case 0x8033: case 0x8034: case 0x8035:
    case 0x8402:
        V(a) = v;
        return;
    case 0x8006: V(a) = v < 152 ? 152 : v; return;
    case 0x8012: V(a) = v & 0x87; return;
    case 0x8030: V(a) = v & 0x80; return;
    case 0x8118: V(a) = v; return;
    case 0x8400: V(a) = (uint8_t)((V(a) & 0x07) | (v & 0xF8)); return;
    case 0x87E0: return;            /* 0x52 = soft reset of K2GE regs (unused) */
    case 0x87E2: return;            /* mode select is BIOS-only */
    default:
        if (a >= 0x8100 && a < 0x8118) { V(a) = v & 7; return; }
        return;
    }
}

/* ------------------------------------------------------------------ */
/* Rendering                                                             */
/* ------------------------------------------------------------------ */

NGP_INLINE uint16_t pal_color(unsigned index)
{
    return (uint16_t)(V(0x8200 + index * 2) | ((V(0x8201 + index * 2) & 0x0F) << 8));
}

NGP_INLINE unsigned tile_pixel(unsigned tile, unsigned row, unsigned col)
{
    const uint8_t *p = &g_lowmem[0xA000 + (tile & 0x1FF) * 16 + row * 2];
    unsigned w = p[0] | (p[1] << 8);
    return (w >> (14 - col * 2)) & 3;
}

/* z-buffer depths (higher = in front) */
enum { Z_SPR1 = 1, Z_BACK = 2, Z_SPR2 = 3, Z_FRONT = 4, Z_SPR3 = 5 };

static void draw_plane(uint16_t *line, uint8_t *zb, int y, unsigned map, unsigned pal_base,
                       uint8_t sx, uint8_t sy, uint8_t depth)
{
    unsigned yy = (unsigned)(y + sy) & 0xFF;
    unsigned row = yy & 7;
    const uint8_t *maprow = &g_lowmem[map + (yy >> 3) * 64];
    for (int x = 0; x < NGP_SCREEN_W; x++) {
        unsigned xx = (unsigned)(x + sx) & 0xFF;
        unsigned e = maprow[(xx >> 3) * 2] | (maprow[(xx >> 3) * 2 + 1] << 8);
        unsigned col = xx & 7, r = row;
        if (e & 0x8000) col ^= 7;
        if (e & 0x4000) r ^= 7;
        unsigned idx = tile_pixel(e & 0x1FF, r, col);
        if (!idx || zb[x] >= depth) continue;
        zb[x] = depth;
        line[x] = pal_color(pal_base + ((e >> 9) & 0xF) * 4 + idx);
    }
}

static void draw_sprites(uint16_t *line, uint8_t *zb, int y)
{
    uint8_t po_h = V(0x8020), po_v = V(0x8021);
    unsigned px = 0, py = 0;
    for (int n = 0; n < 64; n++) {
        const uint8_t *s = &g_lowmem[0x8800 + n * 4];
        unsigned attr = s[1];
        unsigned ox = s[2], oy = s[3];
        if (attr & 0x04) ox = (ox + px) & 0xFF;   /* H chain */
        if (attr & 0x02) oy = (oy + py) & 0xFF;   /* V chain */
        px = ox;
        py = oy;
        unsigned prio = (attr >> 3) & 3;
        if (!prio) continue;
        unsigned sxp = (ox + po_h) & 0xFF;
        unsigned row = (unsigned)(y - (int)((oy + po_v) & 0xFF)) & 0xFF;
        if (row >= 8) continue;
        if (attr & 0x40) row ^= 7;
        unsigned tile = s[0] | ((attr & 1) << 8);
        unsigned code = g_lowmem[0x8C00 + n] & 0x0F;
        uint8_t depth = prio == 1 ? Z_SPR1 : prio == 2 ? Z_SPR2 : Z_SPR3;
        for (unsigned c = 0; c < 8; c++) {
            unsigned x = (sxp + c) & 0xFF;
            if (x >= NGP_SCREEN_W) continue;
            unsigned col = (attr & 0x80) ? 7 - c : c;
            unsigned idx = tile_pixel(tile, row, col);
            if (!idx || zb[x] >= depth) continue;
            zb[x] = depth;
            line[x] = pal_color(code * 4 + idx);
        }
    }
}

void k2ge_line_start(int line)
{
    if (line == 0) {
        s_win_x = V(0x8002); s_win_y = V(0x8003);
        s_win_w = V(0x8004); s_win_h = V(0x8005);
        s_in_vblank = 0;
        s_vblank_pin = 0;
        V(0x8010) &= (uint8_t)~0x80;
    }
    if (line == NGP_SCREEN_H) {
        s_in_vblank = 1;
        uint8_t pin = (V(0x8000) & 0x80) ? 1 : 0;
        if (pin && !s_vblank_pin) irq_raise(IRQ_INT4);
        s_vblank_pin = pin;
    }
}

void k2ge_render_line(int y)
{
    if (y < 0 || y >= NGP_SCREEN_H) return;
    uint16_t *line = &g_framebuffer12[y * NGP_SCREEN_W];
    uint8_t zb[NGP_SCREEN_W];
    memset(zb, 0, sizeof(zb));

    /* Background colour. Only bit 6 of 0x8118 disables it: the manual says
       mode 0b10 enables it, but this game writes 0b00 and expects it used
       (observation documented by ares). */
    uint16_t bg = (V(0x8118) & 0x40) ? 0 : pal_color(0xF0 + (V(0x8118) & 7));
    for (int x = 0; x < NGP_SCREEN_W; x++) line[x] = bg;

    int p2_front = (V(0x8030) & 0x80) != 0;
    draw_sprites(line, zb, y);   /* depth-tests against planes drawn later */
    if (p2_front) {
        draw_plane(line, zb, y, 0x9000, 0x40, V(0x8032), V(0x8033), Z_BACK);
        draw_plane(line, zb, y, 0x9800, 0x80, V(0x8034), V(0x8035), Z_FRONT);
    } else {
        draw_plane(line, zb, y, 0x9800, 0x80, V(0x8034), V(0x8035), Z_BACK);
        draw_plane(line, zb, y, 0x9000, 0x40, V(0x8032), V(0x8033), Z_FRONT);
    }

    /* Window: everything outside the rectangle shows the OOWC colour. */
    uint16_t wc = pal_color(0xF8 + (V(0x8012) & 7));
    int in_y = y >= s_win_y && y < (int)s_win_y + (int)s_win_h;
    for (int x = 0; x < NGP_SCREEN_W; x++) {
        if (!in_y || x < s_win_x || x >= (int)s_win_x + (int)s_win_w)
            line[x] = wc;
    }

    uint32_t *out = &g_framebuffer[y * NGP_SCREEN_W];
    for (int x = 0; x < NGP_SCREEN_W; x++) {
        uint16_t c = line[x];
        unsigned r = c & 0xF, g = (c >> 4) & 0xF, b = (c >> 8) & 0xF;
        out[x] = 0xFF000000u | ((r * 17) << 16) | ((g * 17) << 8) | (b * 17);
    }
}

void k2ge_state(StateIO *s)
{
    ST(s, s_win_x); ST(s, s_win_y); ST(s, s_win_w); ST(s, s_win_h);
    ST(s, s_vblank_pin);
    ST(s, s_in_vblank);
}
