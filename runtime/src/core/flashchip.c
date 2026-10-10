/*
 * Cartridge flash chip command interface. See flashchip.h.
 */
#include "flashchip.h"

#include "ngp.h"

enum {
    FS_READ = 0,      /* read array; waiting for AA at 5555 */
    FS_UNLOCK1,       /* got AA, waiting for 55 at 2AAA */
    FS_UNLOCK2,       /* got 55, waiting for the command at 5555 */
    FS_PROGRAM,       /* next write is the data byte */
    FS_ERASE1,        /* got 80, waiting for AA at 5555 */
    FS_ERASE2,        /* waiting for 55 at 2AAA */
    FS_ERASE3,        /* waiting for 30 at a block address (or 10 at 5555) */
    FS_COUNT
};

bool g_flash_commands = true;

static uint32_t s_state;
static uint64_t s_programs, s_erases;
static uint32_t s_block_erases[2][FLASH_BLOCKS];

static void erase(int chip, int block)
{
    flash_erase_block(chip, block);
    s_erases++;
    s_block_erases[chip][block]++;
    if (g_log_level > 1) ngp_log("flash: erased chip %d block %d\n", chip, block);
}

void flashchip_write(uint32_t addr, uint8_t v)
{
    int chip;
    uint32_t off, base;
    if (addr >= NGP_ROM_BASE && addr < NGP_ROM_BASE + 0x200000u) {
        chip = 0; base = NGP_ROM_BASE;
    } else if (addr >= 0x800000u && addr < 0xA00000u) {
        chip = 1; base = 0x800000u;
    } else {
        return;
    }
    off = addr - base;
    uint32_t cmd = off & 0x7FFF;   /* command addresses decode the low 15 bits */

    if (s_state == FS_PROGRAM) {
        flash_write_block(addr, &v, 1);   /* programming clears bits (AND) */
        s_programs++;
        s_state = FS_READ;
        return;
    }
    if (v == 0xF0) {                      /* reset */
        s_state = FS_READ;
        return;
    }
    switch (s_state) {
    case FS_READ:
        s_state = (cmd == 0x5555 && v == 0xAA) ? FS_UNLOCK1 : FS_READ;
        if (s_state == FS_READ && g_log_level > 1) ngp_log("flash: stray write %06X <- %02X\n", addr, v);
        break;
    case FS_UNLOCK1:
        s_state = (cmd == 0x2AAA && v == 0x55) ? FS_UNLOCK2 : FS_READ;
        break;
    case FS_UNLOCK2:
        if (cmd == 0x5555 && v == 0xA0) s_state = FS_PROGRAM;
        else if (cmd == 0x5555 && v == 0x80) s_state = FS_ERASE1;
        else {
            /* autoselect (90) and other commands are not used by the game */
            if (g_log_level > 0) ngp_log("flash: unsupported command %02X at %06X\n", v, addr);
            s_state = FS_READ;
        }
        break;
    case FS_ERASE1:
        s_state = (cmd == 0x5555 && v == 0xAA) ? FS_ERASE2 : FS_READ;
        break;
    case FS_ERASE2:
        s_state = (cmd == 0x2AAA && v == 0x55) ? FS_ERASE3 : FS_READ;
        break;
    case FS_ERASE3:
        if (v == 0x30) {
            erase(chip, flash_block_of(off));
        } else if (v == 0x10 && cmd == 0x5555) {
            for (int b = 0; b < FLASH_BLOCKS; b++) erase(chip, b);
        }
        s_state = FS_READ;
        break;
    default:
        s_state = FS_READ;
        break;
    }
}

void flashchip_reset(void)
{
    s_state = FS_READ;
}

uint32_t flashchip_state(void)
{
    return s_state;
}

void flashchip_set_state(uint32_t state)
{
    s_state = state < FS_COUNT ? state : FS_READ;
}

uint64_t flashchip_programs(void)
{
    return s_programs;
}

uint64_t flashchip_erases(void)
{
    return s_erases;
}

uint32_t flashchip_block_erases(int chip, int block)
{
    if (chip < 0 || chip > 1 || block < 0 || block >= FLASH_BLOCKS) return 0;
    return s_block_erases[chip][block];
}
