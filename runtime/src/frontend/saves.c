/*
 * Cartridge saves and save states. See saves.h.
 */
#include "saves.h"
#include "bps.h"
#include "romload.h"
#include "util.h"

#include "core/flashchip.h"
#include "core/ngp.h"
#include "core/state.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------------ */
/* Flash blocks                                                         */
/* ------------------------------------------------------------------ */

/* Makes sure every flash block whose contents differ from the pristine ROM
   is included in the next flash_store_save(). After loading a state the
   core only knows the blocks recorded in that state; without this, save
   data loaded from the save file (or written later) in other blocks could
   be left out of the file. Does not change g_flash_dirty. */
static void mark_changed_blocks(void)
{
    size_t psize;
    const uint8_t *pristine = rom_pristine(&psize);
    if (pristine && g_rom && psize == g_rom_size) flash_mark_changed_blocks(pristine);
}

/* ------------------------------------------------------------------ */
/* Flash save                                                           */
/* ------------------------------------------------------------------ */

#define FLASH_QUIET_SECONDS 2.0
#define FLASH_MAX_DELAY     10.0
#define FLASH_RETRY_SECONDS 5.0
#define SAVE_MAGIC          "NGPFLSH1"
#define SAVE_MAX_SIZE       (16u * 1024u * 1024u)

static uint32_t rd32le(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

int saves_load_flash_file(const wchar_t *path)
{
    uint8_t *data = NULL;
    size_t size = 0;
    int e = zen_read_file(path, &data, &size, SAVE_MAX_SIZE);
    if (e == ZEN_FILE_MISSING) return 0;
    if (e != ZEN_FILE_OK) return -1;

    static const uint8_t ff = 0xFF;
    bool dirty = g_flash_dirty;
    int result = (size >= 8 && memcmp(data, SAVE_MAGIC, 8) == 0) ? 1 : -1;
    size_t pos = 8;
    while (result == 1 && pos < size) {
        /* check the whole record before touching the image */
        if (size - pos < 8) { result = -1; break; }
        const uint8_t *h = data + pos;
        int chip = h[0], block = h[1];
        uint32_t len = rd32le(h + 4), off, blen;
        if (chip > 1 || block >= FLASH_BLOCKS) { result = -1; break; }
        flash_block_range(block, &off, &blen);
        uint32_t abs = (uint32_t)chip * 0x200000u + off;
        if (len != blen || !g_rom || abs + len > g_rom_size || size - pos - 8 < len) { result = -1; break; }
        memcpy(g_rom + abs, h + 8, len);
        flash_write_block((chip ? 0x800000u : NGP_ROM_BASE) + off, &ff, 1);   /* records the block */
        pos += 8 + (size_t)len;
    }
    g_flash_dirty = dirty;
    free(data);
    return result;
}

#define SAVE_FIRST_BLOCK 0x1B      /* the game's save blocks: 0x1B-0x1E (0x1B0000-0x1EFFFF) */
#define SAVE_LAST_BLOCK  0x1E

int saves_check_flash_file(const wchar_t *path)
{
    uint8_t *data = NULL;
    size_t size = 0;
    int e = zen_read_file(path, &data, &size, SAVE_MAX_SIZE);
    if (e == ZEN_FILE_MISSING) return 0;
    if (e != ZEN_FILE_OK) return -1;
    int result = (size >= 8 && memcmp(data, SAVE_MAGIC, 8) == 0) ? 1 : -1;
    size_t pos = 8;
    int records = 0;
    while (result == 1 && pos < size) {
        if (size - pos < 8) { result = -1; break; }
        const uint8_t *h = data + pos;
        int chip = h[0], block = h[1];
        uint32_t len = rd32le(h + 4), off, blen;
        if (chip != 0 || block < SAVE_FIRST_BLOCK || block > SAVE_LAST_BLOCK) { result = -1; break; }
        flash_block_range(block, &off, &blen);
        if (len != blen || !g_rom || off + len > g_rom_size || size - pos - 8 < len) { result = -1; break; }
        pos += 8 + (size_t)len;
        records++;
    }
    if (result == 1 && records == 0) result = -1;
    free(data);
    return result;
}

static wchar_t *s_save_path;
static int      s_pending;
static double   s_first_write, s_last_write, s_retry_at;
static int      s_backup_done;
static int      s_failed;

static wchar_t *with_suffix(const wchar_t *path, const wchar_t *suffix)
{
    size_t a = wcslen(path), b = wcslen(suffix);
    wchar_t *d = (wchar_t *)malloc((a + b + 1) * sizeof(wchar_t));
    if (!d) return NULL;
    memcpy(d, path, a * sizeof(wchar_t));
    memcpy(d + a, suffix, (b + 1) * sizeof(wchar_t));
    return d;
}

static void make_parent_dir(const wchar_t *path)
{
    wchar_t *dir = zen_wcsdup(path);
    if (!dir) return;
    wchar_t *name = (wchar_t *)zen_path_name(dir);
    if (name > dir) {
        name[-1] = 0;
        zen_make_dir(dir);
    }
    free(dir);
}

int saves_flash_attach(const wchar_t *save_path)
{
    free(s_save_path);
    s_save_path = save_path ? zen_wcsdup(save_path) : NULL;
    s_pending = 0;
    s_backup_done = 0;
    s_failed = 0;
    s_retry_at = 0;
    if (!s_save_path || !zen_file_exists(s_save_path)) return 0;
    int r = saves_load_flash_file(s_save_path);
    g_flash_dirty = false;
    return r;
}

static int flash_write_now(void)
{
    if (!s_save_path) return 1;
    make_parent_dir(s_save_path);
    if (!s_backup_done && zen_file_exists(s_save_path)) {
        wchar_t *bak = with_suffix(s_save_path, L".bak");
        if (bak) CopyFileW(s_save_path, bak, FALSE);
        free(bak);
        s_backup_done = 1;
    }
    wchar_t *tmp = with_suffix(s_save_path, L".tmp");
    char *cp = tmp ? zen_core_path(tmp) : NULL;
    int ok = cp && flash_store_save(cp);
    if (ok) ok = zen_replace_file(tmp, s_save_path);
    if (!ok && tmp) DeleteFileW(tmp);
    free(cp);
    free(tmp);
    if (ok) {
        s_pending = 0;
        s_failed = 0;
        g_flash_dirty = false;
    } else {
        s_failed = 1;
        s_pending = 1;
        s_retry_at = zen_seconds() + FLASH_RETRY_SECONDS;
    }
    return ok;
}

int saves_flash_poll(void)
{
    if (!s_save_path) return 0;
    double now = zen_seconds();
    if (g_flash_dirty) {
        g_flash_dirty = false;
        if (!s_pending) s_first_write = now;
        s_pending = 1;
        s_last_write = now;
    }
    if (s_pending && now >= s_retry_at &&
        (now - s_last_write >= FLASH_QUIET_SECONDS || now - s_first_write >= FLASH_MAX_DELAY))
        return flash_write_now() ? 1 : -1;
    return 0;
}

int saves_flash_flush(void)
{
    if (!s_save_path) return 1;
    if (g_flash_dirty) s_pending = 1;
    if (!s_pending) return 1;
    return flash_write_now();
}

int saves_flash_failed(void)
{
    return s_failed;
}

const wchar_t *saves_flash_path(void)
{
    return s_save_path;
}

/* ------------------------------------------------------------------ */
/* Save states                                                          */
/* ------------------------------------------------------------------ */

#define STATE_MAGIC    "NGPSTAT1"
#define TRAILER_MAGIC  "ZENOBST1"
#define TRAILER_SIZE   44
#define STATE_MAX_SIZE (64u * 1024u * 1024u)
#define FLAG_FLASHCMD  0x100u     /* trailer flags: bits 0-7 hold the flash command state */

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}

static uint32_t get32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

const char *state_result_string(int r)
{
    switch (r) {
    case STATE_OK:            return "ok";
    case STATE_ERR_MISSING:   return "the slot is empty";
    case STATE_ERR_IO:        return "the file could not be read or written";
    case STATE_ERR_INVALID:   return "the file is not a valid save state (damaged?); nothing was changed";
    case STATE_ERR_OTHER_ROM: return "the state was saved with a different version of the game";
    case STATE_ERR_BACKUP:    return "no backup of the running game could be made; nothing was changed";
    case STATE_ERR_RESTORED:  return "the state could not be loaded; the game continues unchanged";
    case STATE_ERR_FATAL:     return "the state could not be loaded and the game had to be reset";
    default:                  return "unknown error";
    }
}

int state_save(const wchar_t *path, const uint8_t rom_sha1[20])
{
    make_parent_dir(path);
    wchar_t *core_tmp = with_suffix(path, L".core");
    char *cp = core_tmp ? zen_core_path(core_tmp) : NULL;
    int ok = cp && ngp_state_save(cp);
    free(cp);
    uint8_t *data = NULL;
    size_t size = 0;
    if (ok) ok = zen_read_file(core_tmp, &data, &size, STATE_MAX_SIZE) == ZEN_FILE_OK && size >= 8;
    if (core_tmp) DeleteFileW(core_tmp);
    free(core_tmp);
    if (!ok) { free(data); return STATE_ERR_IO; }

    uint8_t *full = (uint8_t *)malloc(size + TRAILER_SIZE);
    if (!full) { free(data); return STATE_ERR_IO; }
    memcpy(full, data, size);
    uint8_t *t = full + size;
    memset(t, 0, TRAILER_SIZE);
    memcpy(t, TRAILER_MAGIC, 8);
    put32(t + 8, (uint32_t)size);
    put32(t + 12, bps_crc32(0, data, size));
    memcpy(t + 16, rom_sha1, 20);
    put32(t + 36, FLAG_FLASHCMD | (flashchip_state() & 0xFF));
    free(data);
    ok = zen_write_file_atomic(path, full, size + TRAILER_SIZE) == ZEN_FILE_OK;
    free(full);
    return ok ? STATE_OK : STATE_ERR_IO;
}

int state_matches_rom(const wchar_t *path, const uint8_t rom_sha1[20])
{
    uint8_t *data = NULL;
    size_t size = 0;
    if (!rom_sha1 || zen_read_file(path, &data, &size, STATE_MAX_SIZE) != ZEN_FILE_OK) return 0;
    int ok = size >= 8 + TRAILER_SIZE && memcmp(data, STATE_MAGIC, 8) == 0 &&
             memcmp(data + size - TRAILER_SIZE, TRAILER_MAGIC, 8) == 0 &&
             memcmp(data + size - TRAILER_SIZE + 16, rom_sha1, 20) == 0;
    free(data);
    return ok;
}

int state_load(const wchar_t *path, const uint8_t rom_sha1[20], int allow_other_rom)
{
    uint8_t *data = NULL;
    size_t size = 0;
    int e = zen_read_file(path, &data, &size, STATE_MAX_SIZE);
    if (e == ZEN_FILE_MISSING) return STATE_ERR_MISSING;
    if (e != ZEN_FILE_OK) return STATE_ERR_IO;

    /* 1. validate before touching the running game */
    size_t core_size = size;
    uint32_t flags = 0;
    int result = STATE_OK;
    if (size < 8 || memcmp(data, STATE_MAGIC, 8) != 0) result = STATE_ERR_INVALID;
    if (result == STATE_OK && size >= 8 + TRAILER_SIZE &&
        memcmp(data + size - TRAILER_SIZE, TRAILER_MAGIC, 8) == 0) {
        const uint8_t *t = data + size - TRAILER_SIZE;
        core_size = size - TRAILER_SIZE;
        flags = get32(t + 36);
        if (get32(t + 8) != (uint32_t)core_size || get32(t + 12) != bps_crc32(0, data, core_size))
            result = STATE_ERR_INVALID;
        else if (!allow_other_rom && rom_sha1 && memcmp(t + 16, rom_sha1, 20) != 0)
            result = STATE_ERR_OTHER_ROM;
    }
    /* the fixed part alone (signature, CPU, 64 KB of memory) needs this much */
    if (result == STATE_OK && core_size < 8 + sizeof(g_cpu) + sizeof(g_lowmem)) result = STATE_ERR_INVALID;
    free(data);
    if (result != STATE_OK) return result;

    /* 2. back up the running game: its state, and the ROM/flash image */
    uint8_t *rom_backup = (uint8_t *)malloc(g_rom_size ? g_rom_size : 1);
    wchar_t tmpdir[MAX_PATH + 1], backup[MAX_PATH + 1];
    char *backup_cp = NULL;
    int have_backup = 0;
    if (rom_backup && GetTempPathW(MAX_PATH + 1, tmpdir) && GetTempFileNameW(tmpdir, L"zen", 0, backup)) {
        backup_cp = zen_core_path(backup);
        have_backup = backup_cp && ngp_state_save(backup_cp);
        if (!have_backup) DeleteFileW(backup);
    }
    if (!have_backup) {
        free(rom_backup);
        free(backup_cp);
        return STATE_ERR_BACKUP;
    }
    memcpy(rom_backup, g_rom, g_rom_size);
    bool dirty = g_flash_dirty;
    uint32_t chip_state = flashchip_state();

    /* 3. load; on failure put everything back. The core sets the BIOS
       flash chip sizes from the loaded cartridge (states made before that
       fix hold a wrong value) and puts the chip in read mode. */
    char *cp = zen_core_path(path);
    int ok = cp && ngp_state_load(cp);
    free(cp);
    if (ok) {
        g_flash_dirty = dirty;
        mark_changed_blocks();
        /* states from other tools carry no flash command state: read mode */
        flashchip_set_state((flags & FLAG_FLASHCMD) ? (flags & 0xFF) : 0);
        result = STATE_OK;
    } else {
        memcpy(g_rom, rom_backup, g_rom_size);
        if (ngp_state_load(backup_cp)) {
            g_flash_dirty = dirty;
            flashchip_set_state(chip_state);
            result = STATE_ERR_RESTORED;
        } else {
            ngp_reset();
            mark_changed_blocks();
            result = STATE_ERR_FATAL;
        }
    }
    DeleteFileW(backup);
    free(backup_cp);
    free(rom_backup);
    return result;
}
