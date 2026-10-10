/*
 * Neo Geo Pocket Color system runtime: shared declarations.
 */
#ifndef NGP_NGP_H
#define NGP_NGP_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>

#include "../cpu/tlcs900h.h"

/* ------------------------------------------------------------------ */
/* Timing                                                               */
/* ------------------------------------------------------------------ */

#define NGP_MASTER_HZ      6144000     /* "ticks" */
#define NGP_LINE_TICKS     515
#define NGP_LINES          199         /* lines 0..198 (frame rate register 0xC6) */
#define NGP_HBLANK_TICK    480         /* 160 pixels * 3 ticks */
#define NGP_SCREEN_W       160
#define NGP_SCREEN_H       152
#define NGP_AUDIO_RATE     48000       /* 128 ticks per output sample */

/* CPU instruction timing uses "states". One state lasts this many master
   ticks (MAME/NeoPop model = 1, ares model = 2). */
extern int g_ticks_per_state;

/* Current master tick (absolute since power on). */
extern uint64_t g_tick_base;   /* tick at which g_cpu.cycles == 0 */
uint64_t ngp_now(void);        /* exact current tick, including CPU progress */

/* ------------------------------------------------------------------ */
/* Memory                                                               */
/* ------------------------------------------------------------------ */

#define NGP_ROM_BASE   0x200000u
#define NGP_ROM_MAX    0x400000u   /* up to 4 MB (CS0 + CS1) */

extern uint8_t  g_lowmem[0x10000];   /* 0x0000-0xFFFF backing store (RAM, APU RAM, VRAM) */
extern uint8_t *g_rom;               /* cartridge image (CS0 at 0x200000) */
extern uint32_t g_rom_size;          /* mapped image size: 2 MB, or 4 MB for larger ROMs */
/* Size of the cartridge data (the ROM file or patched image), which decides
   the flash chip sizes the BIOS reports (bios.c). Set by ngp_load_rom(); a
   frontend that fills g_rom itself sets it too (0 = use g_rom_size). */
extern uint32_t g_rom_data_size;
extern uint8_t  g_bios[0x10000];     /* synthetic HLE BIOS image at 0xFF0000 */

uint8_t  mem_read8_slow(uint32_t a);
void     mem_write8_slow(uint32_t a, uint8_t v);

NGP_INLINE uint8_t mem_read8(uint32_t a)
{
    a &= 0xFFFFFF;
    if (a - NGP_ROM_BASE < g_rom_size) return g_rom[a - NGP_ROM_BASE];
    if (a - 0x4000u < 0x4000u) return g_lowmem[a];
    return mem_read8_slow(a);
}

NGP_INLINE void mem_write8(uint32_t a, uint8_t v)
{
    a &= 0xFFFFFF;
    if (a - 0x4000u < 0x4000u) { g_lowmem[a] = v; return; }
    mem_write8_slow(a, v);
}

NGP_INLINE uint16_t mem_read16(uint32_t a)
{
    a &= 0xFFFFFF;
    if (a - NGP_ROM_BASE < g_rom_size - 1) {
        const uint8_t *p = g_rom + (a - NGP_ROM_BASE);
        return (uint16_t)(p[0] | (p[1] << 8));
    }
    if (a - 0x4000u < 0x3FFFu) {
        return (uint16_t)(g_lowmem[a] | (g_lowmem[a + 1] << 8));
    }
    return (uint16_t)(mem_read8_slow(a) | (mem_read8_slow((a + 1) & 0xFFFFFF) << 8));
}

NGP_INLINE uint32_t mem_read32(uint32_t a)
{
    a &= 0xFFFFFF;
    if (a - NGP_ROM_BASE < g_rom_size - 3) {
        const uint8_t *p = g_rom + (a - NGP_ROM_BASE);
        return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
    }
    if (a - 0x4000u < 0x3FFDu) {
        const uint8_t *p = g_lowmem + a;
        return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
    }
    return (uint32_t)mem_read16(a) | ((uint32_t)mem_read16(a + 2) << 16);
}

NGP_INLINE void mem_write16(uint32_t a, uint16_t v)
{
    a &= 0xFFFFFF;
    if (a - 0x4000u < 0x3FFFu) {
        g_lowmem[a] = (uint8_t)v;
        g_lowmem[a + 1] = (uint8_t)(v >> 8);
        return;
    }
    mem_write8_slow(a, (uint8_t)v);
    mem_write8_slow((a + 1) & 0xFFFFFF, (uint8_t)(v >> 8));
}

NGP_INLINE void mem_write32(uint32_t a, uint32_t v)
{
    mem_write16(a, (uint16_t)v);
    mem_write16(a + 2, (uint16_t)(v >> 16));
}

/* Stack helpers (XSP). */
NGP_INLINE void tlcs_push8(uint8_t v)   { R_XSP -= 1; mem_write8(R_XSP, v); }
NGP_INLINE void tlcs_push16(uint16_t v) { R_XSP -= 2; mem_write16(R_XSP, v); }
NGP_INLINE void tlcs_push32(uint32_t v) { R_XSP -= 4; mem_write32(R_XSP, v); }
NGP_INLINE uint8_t  tlcs_pop8(void)  { uint8_t v = mem_read8(R_XSP); R_XSP += 1; return v; }
NGP_INLINE uint16_t tlcs_pop16(void) { uint16_t v = mem_read16(R_XSP); R_XSP += 2; return v; }
NGP_INLINE uint32_t tlcs_pop32(void) { uint32_t v = mem_read32(R_XSP); R_XSP += 4; return v; }

/* ------------------------------------------------------------------ */
/* Subsystems                                                           */
/* ------------------------------------------------------------------ */

/* io.c: TLCS-900 internal registers 0x00-0xFF */
void    io_reset(void);
uint8_t io_read(uint8_t addr);
void    io_write(uint8_t addr, uint8_t v);

/* interrupts.c */
enum {
    IRQ_INT0 = 0, IRQ_INT4, IRQ_INT5, IRQ_INT6, IRQ_INT7,
    IRQ_INTT0, IRQ_INTT1, IRQ_INTT2, IRQ_INTT3,
    IRQ_INTTR4, IRQ_INTTR5, IRQ_INTTR6, IRQ_INTTR7,
    IRQ_INTRX0, IRQ_INTTX0, IRQ_INTRX1, IRQ_INTTX1, IRQ_INTAD,
    IRQ_INTTC0, IRQ_INTTC1, IRQ_INTTC2, IRQ_INTTC3,
    IRQ_COUNT
};
void    irq_reset(void);
void    irq_raise(int src);           /* latch pending (edge) */
void    irq_clear(int src);
bool    irq_pending(int src);
void    irq_set_priority(int src, unsigned prio);
unsigned irq_get_priority(int src);
void    irq_set_dma_vector(int ch, uint8_t vec);
extern volatile int g_irq_check;      /* nonzero when an interrupt may be acceptable */
int     irq_service(void);            /* accept highest pending interrupt; returns 1 if CPU state changed */

/* timers.c */
void    timers_reset(void);
void    timers_advance(uint64_t now_tick);   /* run prescaler up to now */
void    timers_ti0_edge(void);               /* HBlank-driven clock for timer 0 */
uint64_t timers_next_event(uint64_t now_tick);
uint8_t timers_read(uint8_t addr);
void    timers_write(uint8_t addr, uint8_t v);

/* k2ge.c: video */
void    k2ge_reset(void);
uint8_t k2ge_read(uint32_t a);
void    k2ge_write(uint32_t a, uint8_t v);
void    k2ge_render_line(int line);
void    k2ge_line_start(int line);
extern uint32_t g_framebuffer[NGP_SCREEN_W * NGP_SCREEN_H];  /* XRGB8888 */
extern uint16_t g_framebuffer12[NGP_SCREEN_W * NGP_SCREEN_H]; /* raw 12-bit colors */

/* apu.c: Z80 + PSG + DAC */
void    apu_reset(void);
void    apu_run_until(uint64_t tick);
void    apu_enable(bool on);
void    apu_nmi(void);
void    apu_comm_write(uint8_t v);
uint8_t apu_comm_read(void);
void    apu_irq_line(bool level);      /* TO3 -> Z80 /INT */
void    psg_write(int right, uint8_t v, uint64_t tick);
void    dac_write(int right, uint8_t v, uint64_t tick);
void    psg_mode(int dac_mode);
size_t  audio_render(int16_t *out, size_t max_frames, uint64_t until_tick);

/* flash.c: cartridge flash + save data. The chip's command interface (how
   this game saves) is emulated in flashchip.c/h, on by default. */
/* Save file "NGPFLSH1" (format in flash.c). Loading checks each record
   completely before applying it: returns 1 loaded, 0 no such file, -1
   unreadable or damaged (the complete records before the damage are
   loaded). Blocks loaded are recorded for the next store. */
int     flash_load_save(const char *path);
bool    flash_store_save(const char *path);   /* every block written so far */
void    flash_write_block(uint32_t addr, const uint8_t *src, uint32_t len);
void    flash_erase_block(int chip, int block);
uint8_t flash_read_slow(uint32_t a);
void    flash_command_write(uint32_t a, uint8_t v);
extern bool g_flash_dirty;
/* Loading a state replaces the record of written blocks with the state's.
   This marks every block that differs from `pristine` (an unmodified copy
   of the g_rom_size-byte image) again, so save data loaded from a file
   before the state stays in the next flash_store_save(). */
void    flash_mark_changed_blocks(const uint8_t *pristine);
/* Optional override: receives CPU writes to the cartridge range instead of
   the core's chip emulation (NULL by default). */
extern void (*g_flash_command_hook)(uint32_t addr, uint8_t value);

/* 16 Mbit chip layout: blocks 0-30 are 64 KB, then 32 KB, 8 KB, 8 KB, 16 KB. */
#define FLASH_BLOCKS 35
void    flash_block_range(int block, uint32_t *offset, uint32_t *length);
int     flash_block_of(uint32_t offset);      /* offset within the chip */

/* bios.c: BIOS HLE */
void    bios_build_image(void);
void    bios_boot(void);                 /* set up state as if the BIOS just launched the cart */
int     bios_hle_call(uint32_t pc);      /* execute HLE routine at BIOS address; returns 1 if handled */
void    bios_vblank_hook(void);

/* input */
extern uint8_t g_input_state;   /* bit0 up,1 down,2 left,3 right,4 A,5 B,6 option */

/* system.c */
bool    ngp_load_rom(const char *path);
void    ngp_reset(void);
void    ngp_run_frame(void);
extern uint64_t g_frame_count;
extern int g_current_line;

/* cpu execution (dispatch.c) */
void    cpu_run_until(int64_t state_limit);
void    cpu_interrupt(uint32_t vector_addr, unsigned level);

/* logging */
void    ngp_log(const char *fmt, ...);
extern int g_log_level;

#endif
