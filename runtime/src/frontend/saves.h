/*
 * Cartridge saves and save states.
 *
 * Flash save: the core applies the game's flash writes to the ROM image in
 * memory; this module stores them (flash_store_save format) when the game
 * has been quiet for 2 s (at most 10 s after the first write) and on exit.
 * The previous file is copied to "<save>.bak" once per session before it is
 * first replaced. Files are written to a temporary name and renamed.
 *
 * Save states: the core's format (loadable by ngp_harness too) followed by a
 * 44-byte trailer: "ZENOBST1", u32 core size, u32 CRC32 of the core part,
 * the SHA-1 of the ROM image, u32 flags (0x100 | flash command state, see
 * flashchip.h), u32 reserved; little endian. Loading validates the
 * file first (signature, trailer checksum, ROM identity), keeps a backup of
 * the running game (state + ROM/flash image) and restores it if the core
 * rejects the file, so a bad file never leaves the game half-loaded.
 */
#ifndef ZEN_SAVES_H
#define ZEN_SAVES_H

#include <stdint.h>
#include <wchar.h>

/* ---- cartridge flash save ---- */
/* Loads a save file (the core's flash_store_save format: "NGPFLSH1", then
   records {u8 chip, u8 block, u16 0, u32 length, block data}) into the ROM
   image and records its blocks for the next store. Each record is checked
   completely (chip and block exist in this image, the length is the
   block's, all data present) before it is applied, so a damaged file never
   leaves a block half overwritten. Returns 1 loaded, 0 no file, -1 damaged
   or unreadable (the complete records before the damage are loaded). Does
   not change g_flash_dirty. */
int  saves_load_flash_file(const wchar_t *path);
/* Selects the save file for the loaded ROM (NULL = no persistence) and loads
   it into the core; call after ngp_reset(). Returns 1 loaded, 0 no file,
   -1 present but damaged (kept on disk, backed up before replacement). */
int  saves_flash_attach(const wchar_t *save_path);
/* Once per emulated frame: notices flash writes and stores when due.
   Returns 1 if the file was just written, -1 if a write just failed
   (retried later), 0 otherwise. */
int  saves_flash_poll(void);
/* Stores now if anything is unsaved. Returns 1 on success or nothing to do. */
int  saves_flash_flush(void);
int  saves_flash_failed(void);           /* the last write attempt failed */
const wchar_t *saves_flash_path(void);

/* ---- save states ---- */
typedef enum {
    STATE_OK = 0,
    STATE_ERR_MISSING,     /* no such file */
    STATE_ERR_IO,          /* cannot read or write the file */
    STATE_ERR_INVALID,     /* not a state file, or damaged: nothing changed */
    STATE_ERR_OTHER_ROM,   /* saved with another ROM image: not loaded */
    STATE_ERR_BACKUP,      /* no backup of the running game possible: not loaded */
    STATE_ERR_RESTORED,    /* the core rejected the file; the game was restored */
    STATE_ERR_FATAL,       /* rejected and the restore failed: the game was reset */
} StateResult;

int  state_save(const wchar_t *path, const uint8_t rom_sha1[20]);
int  state_load(const wchar_t *path, const uint8_t rom_sha1[20], int allow_other_rom);
const char *state_result_string(int r);

#endif
