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
 *
 * A .zip is opened directly (zipread.h): the game file in it is the entry
 * whose name ends in .ngc, .ngp or .npc (if several, the original Japanese
 * ROM by its CRC32, else the largest; if none, the only or the largest
 * file), unpacked in memory and checked against its CRC32. Encrypted
 * entries, ZIP64, split archives and compression methods other than stored
 * and deflate are refused with a message that asks to extract the zip
 * first; .7z, .rar and .gz files are refused as before.
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

/* The game file chosen in a zip archive. */
typedef struct {
    wchar_t *name;              /* its name in the archive (malloc'd), NULL when not from a zip */
    int      by_name;           /* chosen by its .ngc/.ngp/.npc name (else the only or largest file) */
    int      method;            /* compression method (0 stored, 8 deflate) */
    uint32_t packed_size, size, crc32;
} ZipPick;

typedef struct {
    wchar_t *rom_path;          /* full path of the ROM file (or of the .zip holding it) */
    ZipPick  zip;               /* the game file inside the .zip (zip.name NULL for a plain file) */
    wchar_t *shown_path;        /* rom_path for messages, with the file inside the zip */
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
/* 1 when p->image is the English ROM: the original patched in memory, or
   the English ROM itself (CRC32 = the patch's target). */
int  rom_prep_is_english(const RomPrep *p);

/* Puts the image into the core exactly like ngp_load_rom() (2 or 4 MB
   buffer filled with 0xFF) and keeps a pristine copy. Does not reset. */
int  rom_install(const RomPrep *p);
/* SHA-1 of the installed image (identifies save states). */
const uint8_t *rom_image_sha1(void);
/* The installed buffer as it was before any flash writes (g_rom_size bytes). */
const uint8_t *rom_pristine(size_t *size);
/* The installed image itself as it was loaded, before any flash writes
   (*size = the image's size, without the 0xFF padding). */
const uint8_t *rom_image(size_t *size);

/* Writes the image to a file (only for --write-patched). */
int  rom_write_image(const RomPrep *p, const wchar_t *out_path);

/* Unpacks the game file of a zip archive exactly as rom_prepare() chooses
   it (--unzip). Returns ZIP_OK or a ZIP_ERR_* code (zipread.h), or -1 when
   the file cannot be opened or is not a zip archive. pick->name is malloc'd
   (also on most errors, once an entry was chosen); free it. */
int  rom_unzip(const wchar_t *path, size_t max_size, uint8_t **out, size_t *out_size, ZipPick *pick);

const char *rom_kind_name(RomKind k);

#endif
