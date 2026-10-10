/*
 * TLCS-900/H internal I/O registers (0x00-0xFF) as wired in the Neo Geo Pocket.
 */
#include "ngp.h"
#include "state.h"
#include <time.h>

static uint8_t s_io[0x100];     /* raw latch of written values (for ports/unknowns) */
static uint8_t s_dma_vec[4];
static uint8_t s_clock_gear;
uint8_t g_input_state;

/* Interrupt priority register pairs 0x70-0x7A: {low source, high source} */
static const int8_t k_prio_pairs[11][2] = {
    {IRQ_INT0,   IRQ_INTAD},
    {IRQ_INT4,   IRQ_INT5},
    {IRQ_INT6,   IRQ_INT7},
    {IRQ_INTT0,  IRQ_INTT1},
    {IRQ_INTT2,  IRQ_INTT3},
    {IRQ_INTTR4, IRQ_INTTR5},
    {IRQ_INTTR6, IRQ_INTTR7},
    {IRQ_INTRX0, IRQ_INTTX0},
    {IRQ_INTRX1, IRQ_INTTX1},
    {IRQ_INTTC0, IRQ_INTTC1},
    {IRQ_INTTC2, IRQ_INTTC3},
};

static uint8_t to_bcd(int v) { return (uint8_t)(((v / 10) << 4) | (v % 10)); }

static uint8_t rtc_read(uint8_t a)
{
    time_t now = time(NULL);
    struct tm tmv;
#ifdef _WIN32
    localtime_s(&tmv, &now);
#else
    localtime_r(&now, &tmv);
#endif
    switch (a) {
    case 0x90: return 0x01;   /* RTC running */
    case 0x91: return to_bcd(tmv.tm_year % 100);
    case 0x92: return to_bcd(tmv.tm_mon + 1);
    case 0x93: return to_bcd(tmv.tm_mday);
    case 0x94: return to_bcd(tmv.tm_hour);
    case 0x95: return to_bcd(tmv.tm_min);
    case 0x96: return to_bcd(tmv.tm_sec);
    case 0x97: return (uint8_t)((tmv.tm_wday & 0x0F) | (((tmv.tm_year % 100) & 3) << 4));
    }
    return 0;
}

void io_reset(void)
{
    memset(s_io, 0, sizeof(s_io));
    memset(s_dma_vec, 0, sizeof(s_dma_vec));
    s_clock_gear = 0;
    g_input_state = 0;
}

uint8_t io_read(uint8_t a)
{
    if ((a >= 0x20 && a <= 0x29) || (a >= 0x30 && a < 0x50)) return timers_read(a);
    if (a >= 0x70 && a <= 0x7A) {
        const int8_t *p = k_prio_pairs[a - 0x70];
        return (uint8_t)((irq_pending(p[0]) ? 0x08 : 0) | (irq_pending(p[1]) ? 0x80 : 0));
    }
    if (a >= 0x90 && a <= 0x97) return rtc_read(a);
    switch (a) {
    case 0x7B: return s_io[0x7B] & 0x07;
    case 0x80: return s_clock_gear;
    case 0xB0: return g_input_state;
    case 0xB1: return 0x06;          /* power button released, sub battery ok */
    case 0xB2: return s_io[0xB2] & 1;
    case 0xB3: return s_io[0xB3] & 4;
    case 0xBC: return apu_comm_read();
    case 0x6E: return s_io[0x6E];
    default:   return s_io[a];
    }
}

void io_write(uint8_t a, uint8_t v)
{
    if ((a >= 0x20 && a <= 0x29) || (a >= 0x30 && a < 0x50)) { timers_write(a, v); return; }
    if (a >= 0x70 && a <= 0x7A) {
        const int8_t *p = k_prio_pairs[a - 0x70];
        irq_set_priority(p[0], v & 7);
        if (!(v & 0x08)) irq_clear(p[0]);
        irq_set_priority(p[1], (v >> 4) & 7);
        if (!(v & 0x80)) irq_clear(p[1]);
        return;
    }
    s_io[a] = v;
    switch (a) {
    case 0x7C: case 0x7D: case 0x7E: case 0x7F:
        s_dma_vec[a - 0x7C] = v & 0x1F;
        irq_set_dma_vector(a - 0x7C, v & 0x1F);
        break;
    case 0x80: s_clock_gear = v & 7; break;
    case 0xA0: psg_write(1, v, ngp_now()); break;
    case 0xA1: psg_write(0, v, ngp_now()); break;
    case 0xA2: dac_write(1, v, ngp_now()); break;
    case 0xA3: dac_write(0, v, ngp_now()); break;
    case 0xB8:
        if (v == 0x55) psg_mode(0);
        else if (v == 0xAA) psg_mode(1);
        break;
    case 0xB9:
        if (v == 0x55) apu_enable(true);
        else if (v == 0xAA) apu_enable(false);
        break;
    case 0xBA: apu_nmi(); break;
    case 0xBC: apu_comm_write(v); break;
    default: break;
    }
}

void io_state(StateIO *s)
{
    st_bytes(s, s_io, sizeof(s_io));
    st_bytes(s, s_dma_vec, sizeof(s_dma_vec));
    ST(s, s_clock_gear);
    ST(s, g_input_state);
}
