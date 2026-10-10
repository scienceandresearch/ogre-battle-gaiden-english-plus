/*
 * System: ROM loading, reset and the per-scanline frame scheduler.
 */
#include "ngp.h"
#include "flashchip.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>

int      g_ticks_per_state = 1;
uint64_t g_tick_base;
uint64_t g_frame_count;
int      g_current_line;
int      g_log_level = 1;

static int s_shutdown_requested;

void ngp_log(const char *fmt, ...)
{
    if (g_log_level <= 0) return;
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
}

void ngp_request_shutdown(void) { s_shutdown_requested = 1; }
int  ngp_shutdown_requested(void) { return s_shutdown_requested; }

uint64_t ngp_now(void)
{
    return g_tick_base + (uint64_t)g_cpu.cycles * (uint64_t)g_ticks_per_state;
}

static int64_t states_at(uint64_t tick)
{
    if (tick <= g_tick_base) return 0;
    return (int64_t)((tick - g_tick_base + (uint64_t)g_ticks_per_state - 1) / (uint64_t)g_ticks_per_state);
}

bool ngp_load_rom(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f) return false;
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (size <= 0x40 || size > (long)NGP_ROM_MAX) { fclose(f); return false; }
    free(g_rom);
    /* Always allocate a full 2 MB chip so flash writes past the end are safe. */
    uint32_t alloc = size > 0x200000 ? (uint32_t)NGP_ROM_MAX : 0x200000u;
    g_rom = (uint8_t *)malloc(alloc);
    if (!g_rom) { fclose(f); return false; }
    memset(g_rom, 0xFF, alloc);
    size_t got = fread(g_rom, 1, (size_t)size, f);
    fclose(f);
    if (got != (size_t)size) return false;
    g_rom_size = alloc;
    g_rom_data_size = (uint32_t)size;
    return true;
}

void ngp_reset(void)
{
    memset(&g_cpu, 0, sizeof(g_cpu));
    memset(g_lowmem, 0, sizeof(g_lowmem));
    g_tick_base = 0;
    g_frame_count = 0;
    g_current_line = 0;
    s_shutdown_requested = 0;
    irq_reset();
    io_reset();
    timers_reset();
    k2ge_reset();
    apu_reset();
    flashchip_reset();   /* the cartridge's contents survive a reset */
    bios_build_image();
    bios_boot();
}

/* Run the CPU (and timers) up to an absolute tick. */
static void run_to(uint64_t tick)
{
    for (;;) {
        uint64_t now = ngp_now();
        if (now >= tick) break;
        uint64_t next = timers_next_event(now);
        if (next > tick) next = tick;
        if (next <= now) next = now + 1;
        cpu_run_until(states_at(next));
        timers_advance(ngp_now());
    }
}

void ngp_run_frame(void)
{
    int lines = g_lowmem[0x8006] + 1;
    if (lines < NGP_SCREEN_H + 1) lines = NGP_SCREEN_H + 1;
    uint64_t frame_start = ngp_now();

    for (int line = 0; line < lines; line++) {
        uint64_t line_start = frame_start + (uint64_t)line * NGP_LINE_TICKS;
        g_current_line = line;

        /* HBlank signal (TI0) pulses at the start of lines 0..150 and the
           last line, when HBlank interrupts are enabled in 0x8000. */
        if ((line < 151 || line == lines - 1) && (g_lowmem[0x8000] & 0x40)) timers_ti0_edge();
        if (line == NGP_SCREEN_H) bios_vblank_hook();
        k2ge_line_start(line);

        run_to(line_start + NGP_HBLANK_TICK);
        if (line < NGP_SCREEN_H) k2ge_render_line(line);
        run_to(line_start + NGP_LINE_TICKS);
        apu_run_until(line_start + NGP_LINE_TICKS);
    }
    g_frame_count++;
}
