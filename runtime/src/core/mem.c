/*
 * TLCS-900/H bus: memory map dispatch for accesses outside the fast paths.
 *
 *  0x000000-0x0000FF  internal I/O registers
 *  0x004000-0x006FFF  work RAM (12 KB)
 *  0x007000-0x007FFF  RAM shared with the Z80 (4 KB)
 *  0x008000-0x00BFFF  K2GE registers / VRAM
 *  0x200000-0x3FFFFF  cartridge flash (CS0)
 *  0xFF0000-0xFFFFFF  BIOS (synthetic HLE image)
 */
#include "ngp.h"

uint8_t  g_lowmem[0x10000];
uint8_t *g_rom;
uint32_t g_rom_size;
uint32_t g_rom_data_size;
uint8_t  g_bios[0x10000];

uint8_t mem_read8_slow(uint32_t a)
{
    a &= 0xFFFFFF;
    if (a < 0x100) return io_read((uint8_t)a);
    if (a >= 0x4000 && a < 0x8000) return g_lowmem[a];
    if (a >= 0x8000 && a < 0xC000) return k2ge_read(a);
    if (a >= 0xFF0000) return g_bios[a & 0xFFFF];
    if (a >= NGP_ROM_BASE && a < NGP_ROM_BASE + NGP_ROM_MAX) return flash_read_slow(a);
    return 0xFF;   /* open bus */
}

void mem_write8_slow(uint32_t a, uint8_t v)
{
    a &= 0xFFFFFF;
    if (a < 0x100) { io_write((uint8_t)a, v); return; }
    if (a >= 0x4000 && a < 0x8000) { g_lowmem[a] = v; return; }
    if (a >= 0x8000 && a < 0xC000) { k2ge_write(a, v); return; }
    if (a >= NGP_ROM_BASE && a < NGP_ROM_BASE + NGP_ROM_MAX) { flash_command_write(a, v); return; }
    /* BIOS ROM and unmapped space ignore writes */
}
