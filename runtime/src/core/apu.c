/*
 * Sound subsystem: Z80 sound CPU, T6W28 PSG and the two 8-bit DACs.
 *
 * The Z80 runs at 3.072 MHz (2 master ticks per cycle) and sees:
 *   0x0000-0x0FFF  RAM shared with the TLCS-900 (0x7000-0x7FFF there)
 *   0x4000/0x4001  PSG right/left write ports
 *   0x8000         communication byte (shared latch with TLCS port 0xBC)
 *   0xC000         write: raise TLCS INT5
 *   OUT (0xFF)     acknowledge: drop the Z80 /INT line
 *
 * Its /INT line is driven by TLCS timer flip-flop TO3; NMI by TLCS port 0xBA.
 *
 * Audio is rendered from timestamped register writes: the PSG is clocked at
 * 192 kHz (3.072 MHz / 16) and box-filtered down to 48 kHz.
 */
#include "ngp.h"
#include "state.h"
#include <math.h>
#include "../../../third_party/z80/z80.h"

/* ------------------------------------------------------------------ */
/* T6W28                                                                */
/* ------------------------------------------------------------------ */

typedef struct {
    uint16_t period[3];       /* tone periods, 10 bits */
    uint16_t noise_extra;     /* right-port copy of tone 2 period, used by noise rate 3 */
    uint8_t  noise_ctrl;      /* bits 0-1 rate, bit 2 white noise */
    uint8_t  vol_l[4], vol_r[4];
    uint8_t  latch_l, latch_r;
    uint16_t counter[4];
    uint8_t  out[4];
    uint16_t lfsr;
    uint8_t  enabled;
} Psg;

static Psg      s_psg;
static uint8_t  s_dac_l = 0x80, s_dac_r = 0x80;
static float    s_vol_table[16];

static void psg_reset_state(void)
{
    uint8_t en = s_psg.enabled;
    memset(&s_psg, 0, sizeof(s_psg));
    for (int i = 0; i < 4; i++) { s_psg.vol_l[i] = 15; s_psg.vol_r[i] = 15; }
    s_psg.lfsr = 0x4000;
    s_psg.enabled = en;
}

static void psg_apply_write(int right, uint8_t v)
{
    if (!s_psg.enabled) return;
    if (!right) {
        if (v & 0x80) s_psg.latch_l = v;
        unsigned ch = (s_psg.latch_l >> 5) & 3;
        if (s_psg.latch_l & 0x10) {
            s_psg.vol_l[ch] = v & 15;
        } else if (ch < 3) {
            if (v & 0x80) s_psg.period[ch] = (uint16_t)((s_psg.period[ch] & 0x3F0) | (v & 0x0F));
            else          s_psg.period[ch] = (uint16_t)((s_psg.period[ch] & 0x00F) | ((v & 0x3F) << 4));
        }
    } else {
        if (v & 0x80) s_psg.latch_r = v;
        unsigned ch = (s_psg.latch_r >> 5) & 3;
        if (s_psg.latch_r & 0x10) {
            s_psg.vol_r[ch] = v & 15;
        } else if (ch == 2) {
            if (v & 0x80) s_psg.noise_extra = (uint16_t)((s_psg.noise_extra & 0x3F0) | (v & 0x0F));
            else          s_psg.noise_extra = (uint16_t)((s_psg.noise_extra & 0x00F) | ((v & 0x3F) << 4));
        } else if (ch == 3) {
            s_psg.noise_ctrl = v & 7;
            s_psg.lfsr = 0x4000;
        }
    }
}

/* One 192 kHz step. */
static inline void psg_clock(void)
{
    for (int i = 0; i < 3; i++) {
        uint16_t p = s_psg.period[i];
        if (p <= 1) { s_psg.out[i] = 1; continue; }   /* ultrasonic: DC (PCM via volume) */
        if (s_psg.counter[i] == 0 || --s_psg.counter[i] == 0) {
            s_psg.counter[i] = p;
            s_psg.out[i] ^= 1;
        }
    }
    unsigned rate = s_psg.noise_ctrl & 3;
    uint16_t np = rate == 0 ? 16 : rate == 1 ? 32 : rate == 2 ? 64 : (s_psg.noise_extra ? s_psg.noise_extra : 1);
    if (s_psg.counter[3] == 0 || --s_psg.counter[3] == 0) {
        s_psg.counter[3] = np;
        unsigned fb = (s_psg.noise_ctrl & 4) ? ((s_psg.lfsr ^ (s_psg.lfsr >> 1)) & 1) : (s_psg.lfsr & 1);
        s_psg.lfsr = (uint16_t)((s_psg.lfsr >> 1) | (fb << 14));
        s_psg.out[3] = s_psg.lfsr & 1;
    }
}

/* ------------------------------------------------------------------ */
/* Timestamped event queue                                              */
/* ------------------------------------------------------------------ */

typedef struct { uint64_t tick; uint8_t kind, value; } SndEvent;   /* kind: 0 psgL 1 psgR 2 dacL 3 dacR */
#define EVQ_SIZE 16384
static SndEvent s_evq[EVQ_SIZE];
static unsigned s_ev_head, s_ev_tail;
static uint64_t s_render_tick;    /* audio rendered up to this master tick */
static unsigned s_sub;            /* 192 kHz sub-step counter within an output sample */
static float    s_acc_l, s_acc_r;

static void ev_push(uint64_t tick, uint8_t kind, uint8_t v)
{
    unsigned next = (s_ev_tail + 1) % EVQ_SIZE;
    if (next == s_ev_head) {      /* overflow: apply oldest immediately */
        SndEvent *e = &s_evq[s_ev_head];
        if (e->kind < 2) psg_apply_write(e->kind, e->value);
        else if (e->kind == 2) s_dac_l = e->value; else s_dac_r = e->value;
        s_ev_head = (s_ev_head + 1) % EVQ_SIZE;
    }
    if (tick < s_render_tick) tick = s_render_tick;
    s_evq[s_ev_tail] = (SndEvent){tick, kind, v};
    s_ev_tail = next;
}

void psg_write(int right, uint8_t v, uint64_t tick)
{
    /* TLCS writes only reach the PSG while the Z80 is held in reset. */
    extern int g_apu_running;
    if (g_apu_running) return;
    ev_push(tick, (uint8_t)(right ? 1 : 0), v);
}

static void psg_write_z80(int right, uint8_t v, uint64_t tick) { ev_push(tick, (uint8_t)(right ? 1 : 0), v); }

void dac_write(int right, uint8_t v, uint64_t tick) { ev_push(tick, (uint8_t)(right ? 3 : 2), v); }

void psg_mode(int disable)
{
    /* 0xB8: 0x55 enables the PSG, 0xAA disables (and resets) it. */
    if (disable) { s_psg.enabled = 0; psg_reset_state(); }
    else s_psg.enabled = 1;
}

size_t audio_render(int16_t *out, size_t max_frames, uint64_t until)
{
    size_t n = 0;
    while (s_render_tick + 32 <= until) {
        uint64_t t = s_render_tick + 32;
        while (s_ev_head != s_ev_tail && s_evq[s_ev_head].tick <= t) {
            SndEvent *e = &s_evq[s_ev_head];
            if (e->kind < 2) psg_apply_write(e->kind, e->value);
            else if (e->kind == 2) s_dac_l = e->value;
            else s_dac_r = e->value;
            s_ev_head = (s_ev_head + 1) % EVQ_SIZE;
        }
        psg_clock();
        float l = 0, r = 0;
        for (int i = 0; i < 4; i++) {
            if (s_psg.out[i]) { l += s_vol_table[s_psg.vol_l[i]]; r += s_vol_table[s_psg.vol_r[i]]; }
        }
        l = l * 0.25f * 0.6f + ((int)s_dac_l - 0x80) / 128.0f * 0.4f;
        r = r * 0.25f * 0.6f + ((int)s_dac_r - 0x80) / 128.0f * 0.4f;
        s_acc_l += l;
        s_acc_r += r;
        s_render_tick = t;
        if (++s_sub == 4) {
            s_sub = 0;
            if (n < max_frames && out) {
                float sl = s_acc_l * 0.25f, sr = s_acc_r * 0.25f;
                int il = (int)(sl * 26000.0f), ir = (int)(sr * 26000.0f);
                if (il > 32767) il = 32767; if (il < -32768) il = -32768;
                if (ir > 32767) ir = 32767; if (ir < -32768) ir = -32768;
                out[n * 2] = (int16_t)il;
                out[n * 2 + 1] = (int16_t)ir;
                n++;
            }
            s_acc_l = s_acc_r = 0;
        }
    }
    return n;
}

/* ------------------------------------------------------------------ */
/* Z80                                                                  */
/* ------------------------------------------------------------------ */

static z80      s_z80;
int             g_apu_running;
static uint64_t s_z80_tick;       /* master tick the Z80 has executed up to */
static uint8_t  s_comm;
static bool     s_irq_line;

static uint8_t z80_rd(void *ud, uint16_t a)
{
    (void)ud;
    if (a < 0x1000) return g_lowmem[0x7000 + a];
    if (a == 0x8000) return s_comm;
    return 0;
}

static void z80_wr(void *ud, uint16_t a, uint8_t v)
{
    (void)ud;
    if (a < 0x1000) { g_lowmem[0x7000 + a] = v; return; }
    switch (a) {
    case 0x4000: psg_write_z80(1, v, s_z80_tick); break;
    case 0x4001: psg_write_z80(0, v, s_z80_tick); break;
    case 0x8000: s_comm = v; break;
    case 0xC000: irq_raise(IRQ_INT5); break;
    default: break;
    }
}

static uint8_t z80_in(z80 *z, uint8_t port) { (void)z; (void)port; return 0; }

static void z80_out(z80 *z, uint8_t port, uint8_t v)
{
    (void)z; (void)v;
    if (port == 0xFF) s_irq_line = false;
}

void apu_irq_line(bool level) { if (level) s_irq_line = true; }

void apu_comm_write(uint8_t v) { s_comm = v; }
uint8_t apu_comm_read(void) { return s_comm; }

void apu_nmi(void) { if (g_apu_running) z80_gen_nmi(&s_z80); }

void apu_enable(bool on)
{
    if (on) {
        z80_init(&s_z80);
        s_z80.read_byte = z80_rd;
        s_z80.write_byte = z80_wr;
        s_z80.port_in = z80_in;
        s_z80.port_out = z80_out;
        s_z80_tick = ngp_now();
        s_irq_line = false;
        g_apu_running = 1;
    } else {
        g_apu_running = 0;
    }
}

void apu_run_until(uint64_t tick)
{
    if (!g_apu_running) { s_z80_tick = tick; return; }
    while (s_z80_tick < tick) {
        if (s_irq_line && !s_z80.int_pending) z80_gen_int(&s_z80, 0xFF);
        unsigned long before = s_z80.cyc;
        z80_step(&s_z80);
        unsigned long used = s_z80.cyc - before;
        if (used == 0) used = 4;
        s_z80_tick += (uint64_t)used * 2;
    }
}

void apu_reset(void)
{
    for (int i = 0; i < 15; i++) s_vol_table[i] = powf(10.0f, -2.0f * (float)i / 20.0f);  /* 2 dB steps */
    s_vol_table[15] = 0.0f;
    memset(&s_psg, 0, sizeof(s_psg));
    psg_reset_state();
    s_psg.enabled = 1;
    s_dac_l = s_dac_r = 0x80;
    s_ev_head = s_ev_tail = 0;
    s_render_tick = 0;
    s_sub = 0;
    s_acc_l = s_acc_r = 0;
    g_apu_running = 0;
    s_comm = 0;
    s_irq_line = false;
    s_z80_tick = 0;
    z80_init(&s_z80);
    s_z80.read_byte = z80_rd;
    s_z80.write_byte = z80_wr;
    s_z80.port_in = z80_in;
    s_z80.port_out = z80_out;
}

void apu_state(StateIO *s)
{
    if (!s->loading) audio_render(NULL, 0, ngp_now());   /* apply pending register writes */
    ST(s, s_psg);
    ST(s, s_dac_l); ST(s, s_dac_r);
    ST(s, s_render_tick); ST(s, s_sub); ST(s, s_acc_l); ST(s, s_acc_r);
    z80 saved = s_z80;
    ST(s, s_z80);
    if (s->loading) {   /* keep the host callbacks */
        s_z80.read_byte = saved.read_byte;
        s_z80.write_byte = saved.write_byte;
        s_z80.port_in = saved.port_in;
        s_z80.port_out = saved.port_out;
        s_z80.userdata = saved.userdata;
        s_ev_head = s_ev_tail = 0;
    }
    ST(s, g_apu_running); ST(s, s_z80_tick); ST(s, s_comm); ST(s, s_irq_line);
}
