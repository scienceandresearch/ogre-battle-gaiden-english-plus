/*
 * TMP95C061-style interrupt controller and micro DMA.
 *
 * Each maskable source has a pending latch and a 3-bit priority (0 and 7
 * disable it). The CPU accepts the highest-priority pending source whose
 * level is >= IFF; acceptance pushes PC and SR and sets IFF = level + 1.
 *
 * The NGP BIOS vectors every hardware interrupt to a user handler whose
 * address the game stores in RAM at 0x6FB8 + 4*n. The BIOS stubs are
 * transparent, so we vector directly to the user handler (as NeoPop does).
 *
 * A source whose vector matches a DMAxV register triggers one micro-DMA
 * transfer instead of an interrupt (when IFF <= 6).
 */
#include "ngp.h"
#include "state.h"

typedef struct {
    uint8_t vector;      /* hardware vector number (0x28, 0x2C, ...) */
    int8_t  user_slot;   /* index into 0x6FB8 table, -1 if not routed */
    uint8_t priority;
    uint8_t pending;
} IrqSource;

static IrqSource s_irq[IRQ_COUNT];
static uint8_t   s_dma_vector[4];
volatile int     g_irq_check;

/* Hardware vector numbers and the NGP BIOS user-vector slots. */
static const struct { uint8_t vector; int8_t slot; } k_irq_info[IRQ_COUNT] = {
    [IRQ_INT0]   = {0x28, 4},   /* RTC alarm */
    [IRQ_INT4]   = {0x2C, 5},   /* VBlank */
    [IRQ_INT5]   = {0x30, 6},   /* Z80 */
    [IRQ_INT6]   = {0x34, -1},
    [IRQ_INT7]   = {0x38, -1},
    [IRQ_INTT0]  = {0x40, 7},
    [IRQ_INTT1]  = {0x44, 8},
    [IRQ_INTT2]  = {0x48, 9},
    [IRQ_INTT3]  = {0x4C, 10},
    [IRQ_INTTR4] = {0x50, -1},
    [IRQ_INTTR5] = {0x54, -1},
    [IRQ_INTTR6] = {0x58, -1},
    [IRQ_INTTR7] = {0x5C, -1},
    [IRQ_INTRX0] = {0x60, 12},  /* serial receive */
    [IRQ_INTTX0] = {0x64, 11},  /* serial transmit */
    [IRQ_INTRX1] = {0x68, -1},
    [IRQ_INTTX1] = {0x6C, -1},
    [IRQ_INTAD]  = {0x70, -1},
    [IRQ_INTTC0] = {0x74, 14},  /* micro DMA end 0..3 */
    [IRQ_INTTC1] = {0x78, 15},
    [IRQ_INTTC2] = {0x7C, 16},
    [IRQ_INTTC3] = {0x80, 17},
};

void irq_reset(void)
{
    for (int i = 0; i < IRQ_COUNT; i++) {
        s_irq[i].vector = k_irq_info[i].vector;
        s_irq[i].user_slot = k_irq_info[i].slot;
        s_irq[i].priority = 0;
        s_irq[i].pending = 0;
    }
    memset(s_dma_vector, 0, sizeof(s_dma_vector));
    g_irq_check = 0;
}

static void recheck(void) { g_irq_check = 1; }

void tlcs_irq_mask_changed(void) { recheck(); }

void irq_raise(int src)
{
    s_irq[src].pending = 1;
    recheck();
}

void irq_clear(int src) { s_irq[src].pending = 0; }

bool irq_pending(int src) { return s_irq[src].pending != 0; }

void irq_set_priority(int src, unsigned prio)
{
    s_irq[src].priority = prio & 7;
    recheck();
}

unsigned irq_get_priority(int src) { return s_irq[src].priority; }

void irq_set_dma_vector(int ch, uint8_t vec)
{
    s_dma_vector[ch & 3] = vec;
    recheck();
}

/* One micro-DMA transfer on channel ch. Returns 1 when the count reached 0. */
static int micro_dma(int ch)
{
    uint8_t mode = DMA_MODE(ch);
    unsigned size = (mode & 3) == 0 ? 1 : (mode & 3) == 1 ? 2 : 4;
    uint32_t src = DMA_SRC(ch), dst = DMA_DST(ch);
    unsigned m = (mode >> 2) & 7;

    if (m <= 4) {
        uint32_t v;
        if (size == 1) v = mem_read8(src);
        else if (size == 2) v = mem_read16(src);
        else v = mem_read32(src);
        if (size == 1) mem_write8(dst, (uint8_t)v);
        else if (size == 2) mem_write16(dst, (uint16_t)v);
        else mem_write32(dst, v);
    }
    switch (m) {
    case 0: dst += size; break;
    case 1: dst -= size; break;
    case 2: src += size; break;
    case 3: src -= size; break;
    case 5: src += size; break;   /* counter mode */
    default: break;
    }
    tlcs_set_cr32(0x00 + 4 * ch, src & 0xFFFFFF);
    tlcs_set_cr32(0x10 + 4 * ch, dst & 0xFFFFFF);
    uint16_t count = (uint16_t)(DMA_COUNT(ch) - 1);
    g_cpu.cr[0x20 + 4 * ch] = (uint8_t)count;
    g_cpu.cr[0x21 + 4 * ch] = (uint8_t)(count >> 8);
    g_cpu.cycles += 8;
    return count == 0;
}

/* Called at instruction/block boundaries. Accepts at most one interrupt. */
int irq_service(void)
{
    g_irq_check = 0;
    int best = -1;
    unsigned best_prio = 0;
    for (int i = 0; i < IRQ_COUNT; i++) {
        IrqSource *s = &s_irq[i];
        if (!s->pending) continue;
        unsigned prio = s->priority;
        /* micro DMA trigger: treated as level 6 */
        int dma_ch = -1;
        for (int c = 0; c < 4; c++) {
            if (s_dma_vector[c] && (s_dma_vector[c] << 2) == s->vector) { dma_ch = c; break; }
        }
        if (dma_ch >= 0 && g_cpu.iff <= 6) prio = 6;
        else if (prio == 0 || prio == 7) continue;
        if (prio < g_cpu.iff) continue;
        if (prio > best_prio || (prio == best_prio && best >= 0 && s->vector < s_irq[best].vector)) {
            best = i;
            best_prio = prio;
        }
    }
    if (best < 0) return 0;

    IrqSource *s = &s_irq[best];
    for (int c = 0; c < 4; c++) {
        if (s_dma_vector[c] && (s_dma_vector[c] << 2) == s->vector && g_cpu.iff <= 6) {
            s->pending = 0;
            if (micro_dma(c)) {
                s_dma_vector[c] = 0;
                irq_raise(IRQ_INTTC0 + c);
            }
            g_irq_check = 1;
            return 1;
        }
    }

    s->pending = 0;
    uint32_t handler = 0;
    if (s->user_slot >= 0) {
        handler = mem_read32(0x6FB8 + 4u * (unsigned)s->user_slot) & 0xFFFFFF;
    }
    if (!handler) {
        /* No user vector installed: the BIOS default handler just returns. */
        return 0;
    }
    cpu_interrupt(handler, best_prio);
    g_irq_check = 1;
    return 1;
}

void irq_state(StateIO *s)
{
    st_bytes(s, s_irq, sizeof(s_irq));
    st_bytes(s, s_dma_vector, sizeof(s_dma_vector));
}
