/*
 * ROM identification and loading.
 *
 * The original Japanese ROM (SHA-1 5ac794c0f125bfb97efe9cd06c2aca3afdf549ea)
 * is patched in memory with the English patch: --patch FILE, else
 * ogre_en.bps next to the executable, else ogre_en.bps next to the ROM. A ROM
 * whose CRC32 is the patch's target CRC32 is already English and runs as is.
 * Anything else needs the user's consent; the message then says what the
 * file most likely is (an archive, another game, a wrong size, a copy that
 * was patched already, another dump). No patched ROM is ever written unless
 * explicitly requested.
 */
#ifndef ZEN_ROMLOAD_H
#define ZEN_ROMLOAD_H

#include <stddef.h>
#include <stdint.h>
#include <wchar.h>

#include "bps.h"

#define ZEN_PATCH_NAME L"ogre_en.bps"

typedef enum { ROM_JAPANESE, ROM_ENGLISH, ROM_UNKNOWN } RomKind;

typedef enum {
    ROMPREP_READY = 0,          /* image ready to run */
    ROMPREP_ERROR,              /* file unusable (message says why) */
    ROMPREP_ASK_UNTRANSLATED,   /* Japanese ROM without a usable patch */
    ROMPREP_ASK_UNKNOWN,        /* not the expected ROM */
} RomPrepStatus;

typedef struct {
    wchar_t *rom_path;          /* full path of the ROM file */
    wchar_t *patch_path;        /* patch used, or where it was looked for first */
    wchar_t *patch_alt_path;    /* second place looked at (next to the ROM), or NULL */
    uint8_t *file;
    size_t   file_size;
    uint8_t  file_sha1[20];
    uint32_t file_crc;
    RomKind  kind;
    int      patch_present;     /* the patch file exists */
    int      patch_error;       /* BPS error code, 0 = none */
    BpsInfo  patch_info;
    uint8_t *patched;           /* patched image (malloc'd) or NULL */
    size_t   patched_size;
    const uint8_t *image;       /* what runs: patched or file */
    size_t   image_size;
    int      untranslated;      /* Japanese ROM accepted without the patch */
    int      looks_patched;     /* ROM_UNKNOWN: this game, already patched (another patch version?) */
    wchar_t  why[512];          /* ROM_UNKNOWN: what the file most likely is */
    wchar_t  message[2048];     /* explanation for the user */
    wchar_t  question[160];     /* ROMPREP_ASK_*: the yes/no question to append */
    int      default_yes;       /* ROMPREP_ASK_*: the safe default answer is Yes */
} RomPrep;

RomPrepStatus rom_prepare(const wchar_t *rom_path, const wchar_t *patch_override, RomPrep *p);
/* The user agreed to run the file without the patch. */
void rom_prep_accept_as_is(RomPrep *p);
void rom_prep_free(RomPrep *p);

/* Puts the image into the core exactly like ngp_load_rom() (2 or 4 MB
   buffer filled with 0xFF) and keeps a pristine copy. Does not reset. */
int  rom_install(const RomPrep *p);
/* SHA-1 of the installed image (identifies save states). */
const uint8_t *rom_image_sha1(void);
/* The installed buffer as it was before any flash writes (g_rom_size bytes). */
const uint8_t *rom_pristine(size_t *size);

/* Writes the image to a file (only for --write-patched). */
int  rom_write_image(const RomPrep *p, const wchar_t *out_path);

const char *rom_kind_name(RomKind k);

#endif
