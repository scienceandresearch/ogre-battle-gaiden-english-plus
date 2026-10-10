/*
 * 8-bit timers 0-3 of the TMP95C061 (16-bit timers 4/5 are register-only).
 *
 * Prescaler taps (in 6.144 MHz master ticks): T1 = 128, T4 = 512,
 * T16 = 2048, T256 = 32768 (matches ares/MAME; this rate makes NGP music
 * play at the correct tempo).
 *
 * Timer 0 can be clocked by TI0, which the K2GE drives once per HBlank.
 * Flip-flop FF3 (TO3) drives the Z80 interrupt line: every rising edge
 * raises the Z80 IRQ.
 */
#include "ngp.h"
#include "state.h"

typedef struct {
    uint8_t counter;
    uint8_t compare;
    uint8_t clk;      /* clock select from TxxMOD */
    uint8_t run;
} Timer8;

static Timer8   t[4];
static uint8_t  trun, t01mod, t23mod, tffcr, trdc;
static uint8_t  ff1, ff3;
static uint8_t  buf_treg0, buf_treg2;
static uint8_t  t16regs[0x20];   /* 0x30-0x4F: 16-bit timers, stored only */
static uint64_t s_last_tick;     /* prescaler position (absolute tick) */

#define TAP_T1   128u
#define TAP_T4   512u
#define TAP_T16  2048u
#define TAP_T256 32768u

static void ff3_set(uint8_t v)
{
    v &= 1;
    if (v && !ff3) apu_irq_line(true);
    ff3 = v;
}

static void ff1_set(uint8_t v) { ff1 = v & 1; }

static void match_t1(void);
static void match_t3(void);

static void clock_t1(void)
{
    if (!t[1].run) return;
    if ((t01mod >> 6) == 0 || (t01mod >> 6) == 3) {
        if (++t[1].counter == t[1].compare) match_t1();
    }
}

static void match_t1(void)
{
    t[1].counter = 0;
    irq_raise(IRQ_INTT1);
    if ((tffcr & 0x01) && (tffcr & 0x02)) ff1_set(!ff1);   /* FF1 source = T1, invert enabled */
}

static void clock_t0(void)
{
    if (!t[0].run) return;
    unsigned mode = t01mod >> 6;
    if (mode == 0) {
        if (++t[0].counter == t[0].compare) {
            t[0].counter = 0;
            irq_raise(IRQ_INTT0);
            if (!(tffcr & 0x01) && (tffcr & 0x02)) ff1_set(!ff1);
            if (((t01mod >> 2) & 3) == 0) clock_t1();   /* cascade */
        }
    } else if (mode == 1) {   /* 16-bit: T0 low, T1 high */
        if (++t[0].counter == 0) t[1].counter++;
        if (t[0].counter == t[0].compare && t[1].counter == t[1].compare) {
            irq_raise(IRQ_INTT1);
            t[0].counter = 0;
            t[1].counter = 0;
            if (tffcr & 0x02) ff1_set(!ff1);
        }
    } else if (mode == 2) {   /* PPG */
        ++t[0].counter;
        int m0 = t[0].counter == t[0].compare, m1 = t[0].counter == t[1].compare;
        if ((m0 || m1) && (tffcr & 0x02)) ff1_set(!ff1);
        if (m0) irq_raise(IRQ_INTT0);
        if (m1) {
            irq_raise(IRQ_INTT1);
            t[0].counter = 0;
            if (trdc & 1) t[0].compare = buf_treg0;
        }
    } else {                  /* PWM */
        ++t[0].counter;
        unsigned pwm = (t01mod >> 4) & 3;
        if (pwm == 1) t[0].counter &= 0x3F;
        else if (pwm == 2) t[0].counter &= 0x7F;
        if (t[0].counter == t[0].compare || t[0].counter == 0) {
            irq_raise(IRQ_INTT0);
            if (trdc & 1) t[0].compare = buf_treg0;
            if (tffcr & 0x02) ff1_set(!ff1);
        }
    }
}

static void clock_t3(void)
{
    if (!t[3].run) return;
    if ((t23mod >> 6) == 0 || (t23mod >> 6) == 3) {
        if (++t[3].counter == t[3].compare) match_t3();
    }
}

static void match_t3(void)
{
    t[3].counter = 0;
    irq_raise(IRQ_INTT3);
    if ((tffcr & 0x10) && (tffcr & 0x20)) ff3_set(!ff3);   /* FF3 source = T3, invert enabled */
}

static void clock_t2(void)
{
    if (!t[2].run) return;
    unsigned mode = t23mod >> 6;
    if (mode == 0) {
        if (++t[2].counter == t[2].compare) {
            t[2].counter = 0;
            irq_raise(IRQ_INTT2);
            if (!(tffcr & 0x10) && (tffcr & 0x20)) ff3_set(!ff3);
            if (((t23mod >> 2) & 3) == 0) clock_t3();
        }
    } else if (mode == 1) {
        if (++t[2].counter == 0) t[3].counter++;
        if (t[2].counter == t[2].compare && t[3].counter == t[3].compare) {
            irq_raise(IRQ_INTT3);
            t[2].counter = 0;
            t[3].counter = 0;
            if (tffcr & 0x20) ff3_set(!ff3);
        }
    } else if (mode == 2) {
        ++t[2].counter;
        int m2 = t[2].counter == t[2].compare, m3 = t[2].counter == t[3].compare;
        if ((m2 || m3) && (tffcr & 0x20)) ff3_set(!ff3);
        if (m2) irq_raise(IRQ_INTT2);
        if (m3) {
            irq_raise(IRQ_INTT3);
            t[2].counter = 0;
            if (trdc & 2) t[2].compare = buf_treg2;
        }
    } else {
        ++t[2].counter;
        unsigned pwm = (t23mod >> 4) & 3;
        if (pwm == 1) t[2].counter &= 0x3F;
        else if (pwm == 2) t[2].counter &= 0x7F;
        if (t[2].counter == t[2].compare || t[2].counter == 0) {
            irq_raise(IRQ_INTT2);
            if (trdc & 2) t[2].compare = buf_treg2;
            if (tffcr & 0x20) ff3_set(!ff3);
        }
    }
}

/* Clock selects: T0: 0=TI0 1=T1 2=T4 3=T16; T1: 0=cascade 1=T1 2=T16 3=T256
                  T2: 0=none 1=T1 2=T4 3=T16; T3: 0=cascade 1=T1 2=T16 3=T256 */
static void prescaler_tap(uint64_t tick)
{
    unsigned c0 = t01mod & 3, c1 = (t01mod >> 2) & 3;
    unsigned c2 = t23mod & 3, c3 = (t23mod >> 2) & 3;
    /* T1 tap */
    if (c0 == 1) clock_t0();
    if (c1 == 1) clock_t1();
    if (c2 == 1) clock_t2();
    if (c3 == 1) clock_t3();
    if (tick % TAP_T4) return;
    if (c0 == 2) clock_t0();
    if (c2 == 2) clock_t2();
    if (tick % TAP_T16) return;
    if (c0 == 3) clock_t0();
    if (c1 == 2) clock_t1();
    if (c2 == 3) clock_t2();
    if (c3 == 2) clock_t3();
    if (tick % TAP_T256) return;
    if (c1 == 3) clock_t1();
    if (c3 == 3) clock_t3();
}

void timers_advance(uint64_t now)
{
    if (!(trun & 0x80)) { s_last_tick = now; return; }
    /* process every T1 boundary in (s_last_tick, now] */
    uint64_t next = (s_last_tick / TAP_T1 + 1) * TAP_T1;
    while (next <= now) {
        prescaler_tap(next);
        next += TAP_T1;
    }
    s_last_tick = now;
}

uint64_t timers_next_event(uint64_t now)
{
    if (!(trun & 0x80) || !(trun & 0x0F)) return UINT64_MAX;
    /* Conservative: the next T1 boundary when any prescaled timer runs. */
    unsigned c0 = t01mod & 3, c1 = (t01mod >> 2) & 3, c2 = t23mod & 3, c3 = (t23mod >> 2) & 3;
    int any = (t[0].run && c0) || (t[1].run && c1) || (t[2].run && c2) || (t[3].run && c3);
    if (!any) return UINT64_MAX;
    /* Find the earliest matching boundary by simulating counters (cheap upper bound:
       wake every T1 tap only when a match is within the next tap). */
    uint64_t best = UINT64_MAX;
    for (int i = 0; i < 4; i++) {
        unsigned c = i == 0 ? c0 : i == 1 ? c1 : i == 2 ? c2 : c3;
        if (!t[i].run || c == 0) continue;   /* cascade/TI0 driven: handled by source */
        unsigned period = (i & 1) ? (c == 1 ? TAP_T1 : c == 2 ? TAP_T16 : TAP_T256)
                                  : (c == 1 ? TAP_T1 : c == 2 ? TAP_T4 : TAP_T16);
        unsigned remaining = (uint8_t)(t[i].compare - t[i].counter);
        if (remaining == 0) remaining = 256;
        uint64_t first = (now / period + 1) * period;
        uint64_t when = first + (uint64_t)(remaining - 1) * period;
        if (when < best) best = when;
    }
    return best;
}

void timers_ti0_edge(void)
{
    if ((t01mod & 3) == 0) clock_t0();
}

void timers_reset(void)
{
    memset(t, 0, sizeof(t));
    trun = t01mod = t23mod = tffcr = trdc = 0;
    ff1 = ff3 = 0;
    buf_treg0 = buf_treg2 = 0;
    memset(t16regs, 0, sizeof(t16regs));
    s_last_tick = 0;
}

uint8_t timers_read(uint8_t a)
{
    switch (a) {
    case 0x20: return trun;
    case 0x24: return t01mod;
    case 0x25: return (uint8_t)((tffcr & 0x33) | 0xCC);
    case 0x28: return t23mod;
    case 0x29: return trdc;
    default:
        if (a >= 0x30 && a < 0x50) return t16regs[a - 0x30];
        return 0;   /* TREGx are write-only */
    }
}

void timers_write(uint8_t a, uint8_t v)
{
    timers_advance(ngp_now());
    switch (a) {
    case 0x20:
        for (int i = 0; i < 4; i++) {
            int on = (v >> i) & 1;
            if (t[i].run && !on) t[i].counter = 0;
            t[i].run = (uint8_t)on;
        }
        trun = v;
        break;
    case 0x22: buf_treg0 = v; if (!(trdc & 1)) t[0].compare = v; break;
    case 0x23: t[1].compare = v; break;
    case 0x24: t01mod = v; break;
    case 0x25: {
        tffcr = v;
        unsigned f1 = (v >> 2) & 3, f3 = (v >> 6) & 3;
        if (f1 == 0) ff1_set(!ff1); else if (f1 == 1) ff1_set(1); else if (f1 == 2) ff1_set(0);
        if (f3 == 0) ff3_set(!ff3); else if (f3 == 1) ff3_set(1); else if (f3 == 2) ff3_set(0);
        break;
    }
    case 0x26: buf_treg2 = v; if (!(trdc & 2)) t[2].compare = v; break;
    case 0x27: t[3].compare = v; break;
    case 0x28: t23mod = v; break;
    case 0x29: trdc = v & 3; break;
    default:
        if (a >= 0x30 && a < 0x50) t16regs[a - 0x30] = v;
        break;
    }
}

void timers_state(StateIO *s)
{
    st_bytes(s, t, sizeof(t));
    ST(s, trun); ST(s, t01mod); ST(s, t23mod); ST(s, tffcr); ST(s, trdc);
    ST(s, ff1); ST(s, ff3); ST(s, buf_treg0); ST(s, buf_treg2);
    st_bytes(s, t16regs, sizeof(t16regs));
    ST(s, s_last_tick);
}
