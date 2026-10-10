/*
 * Cartridge flash memory and save persistence.
 *
 * NGP games save by reprogramming blocks of their own cartridge flash, via
 * BIOS calls or by driving the chip's command interface (flashchip.c). We
 * apply those writes to the in-memory ROM image and persist every block
 * ever erased/written to a save file, so the original ROM file is never
 * modified.
 *
 * 16 Mbit chip layout: blocks 0-30 are 64 KB, then 32 KB, 8 KB, 8 KB, 16 KB.
 */
#include "ngp.h"
#include "flashchip.h"
#include "state.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

bool g_flash_dirty;
static uint8_t s_touched[2][FLASH_BLOCKS];

void flash_block_range(int b, uint32_t *off, uint32_t *len)
{
    if (b < 31) { *off = (uint32_t)b * 0x10000u; *len = 0x10000u; return; }
    switch (b) {
    case 31: *off = 0x1F0000; *len = 0x8000; return;
    case 32: *off = 0x1F8000; *len = 0x2000; return;
    case 33: *off = 0x1FA000; *len = 0x2000; return;
    default: *off = 0x1FC000; *len = 0x4000; return;
    }
}

int flash_block_of(uint32_t off)
{
    off &= 0x1FFFFF;
    if (off < 0x1F0000) return (int)(off >> 16);
    if (off < 0x1F8000) return 31;
    if (off < 0x1FA000) return 32;
    if (off < 0x1FC000) return 33;
    return 34;
}

static uint8_t *chip_ptr(int chip, uint32_t off)
{
    uint32_t abs = (uint32_t)chip * 0x200000u + off;
    if (abs >= g_rom_size) return NULL;
    return g_rom + abs;
}

void flash_write_block(uint32_t addr, const uint8_t *src, uint32_t len)
{
    int chip = addr >= 0x800000 ? 1 : 0;
    uint32_t off = (addr - (chip ? 0x800000u : NGP_ROM_BASE)) & 0x1FFFFF;
    for (uint32_t i = 0; i < len; i++) {
        uint8_t *p = chip_ptr(chip, (off + i) & 0x1FFFFF);
        if (!p) continue;
        *p &= src[i];   /* flash programming can only clear bits */
        s_touched[chip][flash_block_of((off + i) & 0x1FFFFF)] = 1;
    }
    g_flash_dirty = true;
}

void flash_erase_block(int chip, int block)
{
    if (chip < 0 || chip > 1 || block < 0 || block >= FLASH_BLOCKS) return;
    uint32_t off, len;
    flash_block_range(block, &off, &len);
    for (uint32_t i = 0; i < len; i++) {
        uint8_t *p = chip_ptr(chip, off + i);
        if (p) *p = 0xFF;
    }
    s_touched[chip][block] = 1;
    g_flash_dirty = true;
}

uint8_t flash_read_slow(uint32_t a)
{
    (void)a;
    return 0xFF;
}

/* Optional override for CPU writes to the cartridge range (tools may trace
   them). NULL (default): the core's chip emulation, or log-and-ignore when
   g_flash_commands is false. */
void (*g_flash_command_hook)(uint32_t addr, uint8_t value);

void flash_command_write(uint32_t a, uint8_t v)
{
    if (g_flash_command_hook) {
        g_flash_command_hook(a, v);
        return;
    }
    if (g_flash_commands) {
        flashchip_write(a, v);
        return;
    }
    /* Old behaviour: the chip's command interface is not emulated; log the
       writes so we notice. */
    if (g_log_level > 0) ngp_log("flash command write %06X <- %02X (ignored)\n", a, v);
}

void flash_mark_changed_blocks(const uint8_t *pristine)
{
    if (!pristine || !g_rom) return;
    for (int chip = 0; chip < 2; chip++) {
        uint32_t base = (uint32_t)chip * 0x200000u;
        if (base >= g_rom_size) break;
        for (int b = 0; b < FLASH_BLOCKS; b++) {
            uint32_t off, len;
            flash_block_range(b, &off, &len);
            if (base + off + len > g_rom_size) continue;
            if (memcmp(g_rom + base + off, pristine + base + off, len) != 0) s_touched[chip][b] = 1;
        }
    }
}

/* Save file: "NGPFLSH1" then records {u8 chip, u8 block, u16 0, u32 len
   (little endian, = the block's size), block data}; the same format the
   player writes (runtime/src/frontend/saves.c). */
bool flash_store_save(const char *path)
{
    FILE *f = fopen(path, "wb");
    if (!f) return false;
    fwrite("NGPFLSH1", 1, 8, f);
    for (int c = 0; c < 2; c++) {
        for (int b = 0; b < FLASH_BLOCKS; b++) {
            if (!s_touched[c][b]) continue;
            uint32_t off, len;
            flash_block_range(b, &off, &len);
            uint8_t *p = chip_ptr(c, off);
            if (!p) continue;
            uint8_t hdr[8] = {(uint8_t)c, (uint8_t)b, 0, 0,
                              (uint8_t)len, (uint8_t)(len >> 8), (uint8_t)(len >> 16), (uint8_t)(len >> 24)};
            fwrite(hdr, 1, 8, f);
            fwrite(p, 1, len, f);
        }
    }
    bool ok = ferror(f) == 0;
    if (fclose(f) != 0) ok = false;
    if (ok) g_flash_dirty = false;
    return ok;
}

int flash_load_save(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f) return errno == ENOENT ? 0 : -1;
    char magic[8];
    if (fread(magic, 1, 8, f) != 8 || memcmp(magic, "NGPFLSH1", 8) != 0) { fclose(f); return -1; }
    uint8_t *buf = (uint8_t *)malloc(0x10000);
    if (!buf) { fclose(f); return -1; }
    int result = 1;
    uint8_t hdr[8];
    size_t got;
    while ((got = fread(hdr, 1, 8, f)) != 0) {
        /* check the whole record before touching the image */
        if (got != 8) { result = -1; break; }
        int c = hdr[0], b = hdr[1];
        uint32_t len = hdr[4] | (hdr[5] << 8) | (hdr[6] << 16) | ((uint32_t)hdr[7] << 24);
        uint32_t off, blen;
        if (c > 1 || b >= FLASH_BLOCKS) { result = -1; break; }
        flash_block_range(b, &off, &blen);
        uint8_t *p = chip_ptr(c, off);
        if (len != blen || !p || (uint32_t)c * 0x200000u + off + len > g_rom_size) { result = -1; break; }
        if (fread(buf, 1, len, f) != len) { result = -1; break; }
        memcpy(p, buf, len);
        s_touched[c][b] = 1;
    }
    free(buf);
    fclose(f);
    return result;
}

void flash_state(StateIO *s)
{
    /* contents of every block the game has written so far */
    st_bytes(s, s_touched, sizeof(s_touched));
    for (int c = 0; c < 2; c++) {
        for (int b = 0; b < FLASH_BLOCKS; b++) {
            if (!s_touched[c][b]) continue;
            uint32_t off, len;
            flash_block_range(b, &off, &len);
            uint8_t *p = chip_ptr(c, off);
            if (p) st_bytes(s, p, len);
        }
    }
    /* the chip's command sequence is not in the format: a loaded state
       starts in read mode (frontends may restore a sequence themselves) */
    if (s->loading) flashchip_reset();
}
