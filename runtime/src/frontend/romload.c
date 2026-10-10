/*
 * ROM identification, in-memory patching and loading. See romload.h.
 */
#include "romload.h"
#include "sha1.h"
#include "util.h"

#include "core/ngp.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* The original Japanese cartridge (2,097,152 bytes, CRC32 EEEEFD6A). */
static const uint8_t k_japanese_sha1[20] = {
    0x5a, 0xc7, 0x94, 0xc0, 0xf1, 0x25, 0xbf, 0xb9, 0x7e, 0xfe,
    0x9c, 0xd0, 0x6c, 0x2a, 0xca, 0x3a, 0xfd, 0xf5, 0x49, 0xea,
};
#define JAPANESE_SIZE 0x200000u

/* Cartridge header: "COPYRIGHT BY SNK CORPORATION" (or " LICENSED BY SNK
   CORPORATION"), the start address, the software ID (0x20, little endian)
   and a 12-character title (0x24). The patch does not change the header. */
#define HEADER_ID     0x0085u
#define HEADER_TITLE  "OGRE_BATTLE "
/* File offsets 0x170000-0x1700FF (CPU 0x370000, the start of the patch's
   code area) are blank (0xFF) in the original and filled by the patch, so a
   copy of this game with data there has been patched already. */
#define PATCH_AREA_OFFSET 0x170000u
#define PATCH_AREA_SIZE   0x100u

#define PATCH_MAX_SIZE (64u * 1024u * 1024u)

static uint8_t *s_pristine;
static size_t   s_pristine_size;
static uint8_t  s_image_sha1[20];

static const wchar_t k_expected[] =
    L"Expected: Densetsu no Ogre Battle Gaiden: Zenobia no Ouji (Japan) for the "
    L"Neo Geo Pocket Color, 2,097,152 bytes, CRC32 EEEEFD6A, "
    L"SHA-1 5ac794c0f125bfb97efe9cd06c2aca3afdf549ea.\n"
    L"The player translates it while loading, using the English patch "
    L"ogre_en.bps placed next to zenobia.exe (or given with --patch FILE). "
    L"The patch comes with the player release and can also be built from the "
    L"project's source (tools/patch). You need your own copy of the game.";

const char *rom_kind_name(RomKind k)
{
    switch (k) {
    case ROM_JAPANESE: return "original Japanese ROM";
    case ROM_ENGLISH:  return "English ROM";
    default:           return "unrecognised ROM";
    }
}

void rom_prep_free(RomPrep *p)
{
    free(p->rom_path);
    free(p->patch_path);
    free(p->patch_alt_path);
    free(p->file);
    free(p->patched);
    memset(p, 0, sizeof(*p));
}

/* ------------------------------------------------------------------ */
/* Identification helpers                                               */
/* ------------------------------------------------------------------ */

static int is_archive(const uint8_t *d, size_t n)
{
    static const struct { const char *sig; size_t len; } sigs[] = {
        {"PK\x03\x04", 4}, {"PK\x05\x06", 4},            /* .zip */
        {"7z\xBC\xAF\x27\x1C", 6},                         /* .7z */
        {"Rar!\x1A\x07", 6},                               /* .rar */
        {"\x1F\x8B", 2},                                   /* .gz */
    };
    for (size_t i = 0; i < sizeof(sigs) / sizeof(sigs[0]); i++)
        if (n >= sigs[i].len && memcmp(d, sigs[i].sig, sigs[i].len) == 0) return 1;
    return 0;
}

static int has_ngp_header(const uint8_t *d, size_t n)
{
    return n >= 0x40 && (memcmp(d, "COPYRIGHT BY SNK CORPORATION", 28) == 0 ||
                         memcmp(d, " LICENSED BY SNK CORPORATION", 28) == 0);
}

/* What an unrecognised file most likely is (one or two sentences). */
static void diagnose(RomPrep *p, wchar_t *out, size_t cap)
{
    const uint8_t *d = p->file;
    size_t n = p->file_size;
    if (!has_ngp_header(d, n)) {
        swprintf(out, cap, L"It does not look like a Neo Geo Pocket ROM (it has no SNK cartridge header).");
        return;
    }
    unsigned id = (unsigned)d[0x20] | ((unsigned)d[0x21] << 8);
    if (id != HEADER_ID || memcmp(d + 0x24, HEADER_TITLE, 12) != 0) {
        char title[13];
        int len = 0;
        for (int i = 0; i < 12; i++) {
            uint8_t c = d[0x24 + i];
            title[i] = (c >= 0x20 && c < 0x7F) ? (char)c : '?';
            if (title[i] != ' ') len = i + 1;
        }
        title[len] = 0;
        swprintf(out, cap, L"It is another Neo Geo Pocket game (\"%hs\", software ID %04X), not Ogre Battle Gaiden.",
                 title, id);
        return;
    }
    if (n != JAPANESE_SIZE) {
        swprintf(out, cap, L"It has the header of this game but the wrong size (%zu bytes instead of 2,097,152): "
                           L"an incomplete or damaged dump?", n);
        return;
    }
    for (size_t i = 0; i < PATCH_AREA_SIZE; i++) {
        if (d[PATCH_AREA_OFFSET + i] != 0xFF) {
            p->looks_patched = 1;
            if (p->patch_present && !p->patch_error)
                swprintf(out, cap, L"It looks like a copy of this game that has already been patched, but not by "
                                   L"this version of ogre_en.bps (an older English release, or another patch). "
                                   L"For this version, open the original Japanese ROM instead; this copy can "
                                   L"still run as it is.");
            else
                swprintf(out, cap, L"It looks like a copy of this game that has already been patched (an English "
                                   L"ROM?). Without ogre_en.bps its version cannot be checked; it can still run "
                                   L"as it is.");
            return;
        }
    }
    swprintf(out, cap, L"It looks like this game, but its contents differ from the known original dump: "
                       L"a bad dump, another revision or a modified copy?");
}

/* The directory part of a full path, with its trailing separator. */
static wchar_t *dir_of(const wchar_t *path)
{
    const wchar_t *name = zen_path_name(path);
    size_t n = (size_t)(name - path);
    wchar_t *d = (wchar_t *)malloc((n + 1) * sizeof(wchar_t));
    if (!d) return NULL;
    memcpy(d, path, n * sizeof(wchar_t));
    d[n] = 0;
    return d;
}

/* --patch FILE, else ogre_en.bps next to the executable, else next to the
   ROM. When none exists, patch_path is the executable's copy and
   patch_alt_path the place next to the ROM (both named in the message). */
static void find_patch(RomPrep *p, const wchar_t *patch_override)
{
    if (patch_override) {
        p->patch_path = zen_full_path(patch_override);
        return;
    }
    wchar_t *exe_patch = zen_path_join(zen_exe_dir(), ZEN_PATCH_NAME);
    wchar_t *rom_dir = dir_of(p->rom_path);
    wchar_t *rom_patch = rom_dir ? zen_path_join(rom_dir, ZEN_PATCH_NAME) : NULL;
    free(rom_dir);
    if (rom_patch && exe_patch && _wcsicmp(rom_patch, exe_patch) == 0) {
        free(rom_patch);
        rom_patch = NULL;
    }
    if (exe_patch && !zen_file_exists(exe_patch) && rom_patch && zen_file_exists(rom_patch)) {
        p->patch_path = rom_patch;
        free(exe_patch);
        return;
    }
    p->patch_path = exe_patch;
    p->patch_alt_path = rom_patch;
}

/* ------------------------------------------------------------------ */
/* Preparation                                                          */
/* ------------------------------------------------------------------ */

RomPrepStatus rom_prepare(const wchar_t *rom_path, const wchar_t *patch_override, RomPrep *p)
{
    memset(p, 0, sizeof(*p));
    p->kind = ROM_UNKNOWN;
    p->rom_path = zen_full_path(rom_path);
    if (!p->rom_path) return ROMPREP_ERROR;

    int e = zen_read_file(p->rom_path, &p->file, &p->file_size, NGP_ROM_MAX);
    if (e != ZEN_FILE_OK) {
        swprintf(p->message, 2048, L"Cannot open the ROM file:\n%ls\n(%hs)", p->rom_path,
                 e == ZEN_FILE_TOO_BIG ? "too large for a Neo Geo Pocket ROM" : zen_file_error(e));
        return ROMPREP_ERROR;
    }
    if (is_archive(p->file, p->file_size)) {
        swprintf(p->message, 2048,
                 L"This is a compressed archive (.zip, .7z, .rar or .gz), not a ROM:\n%ls\n\n"
                 L"Extract the game file (.ngc) from it first, then open that file.", p->rom_path);
        return ROMPREP_ERROR;
    }
    if (p->file_size <= 0x40) {
        swprintf(p->message, 2048, L"This file is not a Neo Geo Pocket ROM (too small):\n%ls", p->rom_path);
        return ROMPREP_ERROR;
    }
    sha1(p->file, p->file_size, p->file_sha1);
    p->file_crc = bps_crc32(0, p->file, p->file_size);

    find_patch(p, patch_override);
    uint8_t *patch = NULL;
    size_t patch_size = 0;
    if (p->patch_path) {
        e = zen_read_file(p->patch_path, &patch, &patch_size, PATCH_MAX_SIZE);
        if (e == ZEN_FILE_OK) {
            p->patch_present = 1;
            p->patch_error = bps_read_info(patch, patch_size, &p->patch_info);
        } else if (e != ZEN_FILE_MISSING) {
            p->patch_present = 1;
            p->patch_error = BPS_ERR_ARGS;   /* unreadable */
        }
    }

    RomPrepStatus st;
    if (memcmp(p->file_sha1, k_japanese_sha1, 20) == 0) {
        p->kind = ROM_JAPANESE;
        if (p->patch_present && !p->patch_error) {
            p->patch_error = bps_apply(patch, patch_size, p->file, p->file_size,
                                       &p->patched, &p->patched_size, NGP_ROM_MAX, NULL);
        }
        if (p->patched) {
            p->image = p->patched;
            p->image_size = p->patched_size;
            swprintf(p->message, 2048, L"Original Japanese ROM, English patch applied.");
            st = ROMPREP_READY;
        } else {
            if (!p->patch_present && patch_override) {
                swprintf(p->message, 2048,
                         L"This is the original Japanese ROM, but the English patch was not found:\n%ls\n\n"
                         L"Check the file given with --patch.",
                         p->patch_path ? p->patch_path : patch_override);
            } else if (!p->patch_present) {
                swprintf(p->message, 2048,
                         L"This is the original Japanese ROM, but the English patch was not found. "
                         L"The player looks for ogre_en.bps next to zenobia.exe%ls:\n%ls%ls%ls\n\n"
                         L"ogre_en.bps comes with the player release: keep it in the same folder as "
                         L"zenobia.exe. It can also be built from the project's source (tools/patch).",
                         p->patch_alt_path ? L" and next to the ROM" : L"",
                         p->patch_path ? p->patch_path : ZEN_PATCH_NAME,
                         p->patch_alt_path ? L"\n" : L"", p->patch_alt_path ? p->patch_alt_path : L"");
            } else {
                swprintf(p->message, 2048,
                         L"This is the original Japanese ROM, but the English patch could not be used:\n%ls\n(%hs)\n\n"
                         L"Get a fresh copy of ogre_en.bps from the player release.",
                         p->patch_path, p->patch_error == BPS_ERR_ARGS ? "the file cannot be read"
                                                                       : bps_error_string(p->patch_error));
            }
            swprintf(p->question, 160, L"Run the game untranslated (in Japanese)?");
            p->default_yes = 1;
            st = ROMPREP_ASK_UNTRANSLATED;
        }
    } else if (p->patch_present && !p->patch_error && p->file_crc == p->patch_info.target_crc &&
               (uint64_t)p->file_size == p->patch_info.target_size) {
        p->kind = ROM_ENGLISH;
        p->image = p->file;
        p->image_size = p->file_size;
        swprintf(p->message, 2048, L"English ROM (already patched).");
        st = ROMPREP_READY;
    } else {
        char hex[41];
        sha1_hex(p->file_sha1, hex);
        diagnose(p, p->why, sizeof(p->why) / sizeof(p->why[0]));
        swprintf(p->message, 2048,
                 L"This file is not the ROM this player expects:\n%ls\n(%zu bytes, CRC32 %08X, SHA-1 %hs)\n\n"
                 L"%ls\n\n%ls",
                 p->rom_path, p->file_size, (unsigned)p->file_crc, hex, p->why, k_expected);
        swprintf(p->question, 160, p->looks_patched ? L"Run this file as it is?"
                                                    : L"Run this file anyway, as it is (without the patch)?");
        p->default_yes = p->looks_patched;
        st = ROMPREP_ASK_UNKNOWN;
    }
    free(patch);
    return st;
}

void rom_prep_accept_as_is(RomPrep *p)
{
    p->image = p->file;
    p->image_size = p->file_size;
    p->untranslated = p->kind == ROM_JAPANESE;
}

int rom_install(const RomPrep *p)
{
    size_t size = p->image_size;
    if (!p->image || size <= 0x40 || size > NGP_ROM_MAX) return 0;
    /* same layout as ngp_load_rom(): a full 2 MB chip (4 MB for two chips),
       unused space 0xFF, so flash writes past the end of the data are safe */
    uint32_t alloc = size > 0x200000 ? (uint32_t)NGP_ROM_MAX : 0x200000u;
    uint8_t *buf = (uint8_t *)malloc(alloc);
    uint8_t *pristine = (uint8_t *)malloc(alloc);
    if (!buf || !pristine) {
        free(buf);
        free(pristine);
        return 0;
    }
    memset(buf, 0xFF, alloc);
    memcpy(buf, p->image, size);
    memcpy(pristine, buf, alloc);
    free(g_rom);
    g_rom = buf;
    g_rom_size = alloc;
    free(s_pristine);
    s_pristine = pristine;
    s_pristine_size = alloc;
    sha1(p->image, size, s_image_sha1);
    g_rom_data_size = (uint32_t)size;   /* the BIOS reports the flash chip size from it */
    return 1;
}

const uint8_t *rom_image_sha1(void)
{
    return s_image_sha1;
}

const uint8_t *rom_pristine(size_t *size)
{
    if (size) *size = s_pristine_size;
    return s_pristine;
}

int rom_write_image(const RomPrep *p, const wchar_t *out_path)
{
    if (!p->image) return 0;
    return zen_write_file_atomic(out_path, p->image, p->image_size) == ZEN_FILE_OK;
}
