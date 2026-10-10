/*
 * ROM identification, in-memory patching and loading. See romload.h.
 */
#include "romload.h"
#include "sha1.h"
#include "util.h"
#include "zipread.h"

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
#define JAPANESE_CRC  0xEEEEFD6Au

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
static size_t   s_image_size;
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
    free(p->zip.name);
    free(p->shown_path);
    free(p->patch_path);
    free(p->patch_alt_path);
    free(p->file);
    free(p->patched);
    memset(p, 0, sizeof(*p));
}

int rom_prep_is_english(const RomPrep *p)
{
    if (!p->image) return 0;
    if (p->patched && p->image == p->patched) return 1;
    return p->kind == ROM_ENGLISH && p->image == p->file;
}

/* The ROM path for messages: for a zip, with the file inside it. */
static const wchar_t *shown(const RomPrep *p)
{
    return p->shown_path ? p->shown_path : p->rom_path;
}

static int ends_with_ci(const wchar_t *s, const wchar_t *suffix)
{
    size_t a = wcslen(s), b = wcslen(suffix);
    return a >= b && _wcsicmp(s + a - b, suffix) == 0;
}

/* ------------------------------------------------------------------ */
/* Zip archives                                                         */
/* ------------------------------------------------------------------ */

/* ZipSource reader on a Win32 file handle (reads at an offset). */
static int file_read_at(void *ctx, uint64_t offset, void *buf, size_t len)
{
    HANDLE h = (HANDLE)ctx;
    uint8_t *dst = (uint8_t *)buf;
    while (len > 0) {
        OVERLAPPED ov;
        memset(&ov, 0, sizeof(ov));
        ov.Offset = (DWORD)offset;
        ov.OffsetHigh = (DWORD)(offset >> 32);
        DWORD chunk = len > (1u << 30) ? (1u << 30) : (DWORD)len, got = 0;
        if (!ReadFile(h, dst, chunk, &got, &ov) || got == 0) return 0;
        dst += got;
        offset += got;
        len -= got;
    }
    return 1;
}

/* An entry's name as text: UTF-8 when the entry says so, else code page 437
   (what zip programs used before UTF-8). Control characters become '?'. */
static wchar_t *entry_name(const ZipEntry *e)
{
    int len = (int)e->name_len;
    UINT cp = e->utf8 ? CP_UTF8 : 437;
    int n = len ? MultiByteToWideChar(cp, 0, e->name, len, NULL, 0) : 0;
    wchar_t *w = (wchar_t *)malloc(((size_t)(n > 0 ? n : len) + 1) * sizeof(wchar_t));
    if (!w) return NULL;
    if (n > 0) {
        MultiByteToWideChar(cp, 0, e->name, len, w, n);
    } else {
        n = len;
        for (int i = 0; i < len; i++) w[i] = (unsigned char)e->name[i] < 0x80 ? (wchar_t)e->name[i] : L'?';
    }
    w[n] = 0;
    for (int i = 0; i < n; i++)
        if (w[i] < 0x20 || w[i] == 0x7F) w[i] = L'?';
    return w;
}

/* Opens path as a zip archive and unpacks the game file. Returns ZIP_OK or
   a ZIP_ERR_* code, or -1 when the file cannot be opened or is not a zip
   archive (no zip signature, and not named .zip with a zip directory). */
static int unzip_game(const wchar_t *path, size_t max_size, uint8_t **out, size_t *out_size, ZipPick *pick)
{
    memset(pick, 0, sizeof(*pick));
    *out = NULL;
    *out_size = 0;
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return -1;
    ZipSource src;
    src.ctx = h;
    src.size = 0;
    src.read = file_read_at;
    LARGE_INTEGER li;
    uint8_t head[4];
    int signature = 0;
    if (GetFileSizeEx(h, &li) && li.QuadPart >= 0) {
        src.size = (uint64_t)li.QuadPart;
        signature = src.size >= 4 && file_read_at(h, 0, head, 4) && zip_signature(head, 4);
    }
    if (!signature && !ends_with_ci(path, L".zip")) {
        CloseHandle(h);
        return -1;
    }
    ZipArchive z;
    int err = zip_open(&z, &src);
    if (err == ZIP_ERR_FORMAT && !signature) {
        /* named .zip, but no zip archive at all: treated as a plain file */
        CloseHandle(h);
        return -1;
    }
    if (err == ZIP_OK) {
        int index = zip_choose_rom(&z, JAPANESE_CRC, JAPANESE_SIZE, &pick->by_name);
        if (index < 0) {
            err = ZIP_ERR_EMPTY;
        } else {
            const ZipEntry *e = &z.entries[index];
            pick->name = entry_name(e);
            pick->method = e->method;
            pick->packed_size = e->comp_size;
            pick->size = e->size;
            pick->crc32 = e->crc32;
            err = zip_extract(&z, index, max_size, out, out_size);
        }
        zip_close(&z);
    }
    CloseHandle(h);
    return err;
}

int rom_unzip(const wchar_t *path, size_t max_size, uint8_t **out, size_t *out_size, ZipPick *pick)
{
    return unzip_game(path, max_size, out, out_size, pick);
}

static const wchar_t k_extract_first[] =
    L"Please extract the zip first: right-click it, choose Extract All, then open the extracted "
    L"game file (.ngc).";

/* Why a zip could not be used, and what to do. */
static void zip_message(RomPrep *p, int err)
{
    const wchar_t *w = shown(p);
    wchar_t *m = p->message;
    switch (err) {
    case ZIP_ERR_ENCRYPTED:
        swprintf(m, 2048, L"The game file in this zip is protected by a password:\n%ls\n\n"
                          L"Please extract the zip first: right-click it, choose Extract All (Windows asks for "
                          L"the password), then open the extracted game file (.ngc).", w);
        break;
    case ZIP_ERR_METHOD:
        swprintf(m, 2048, L"The game file in this zip is compressed with a method this player cannot unpack "
                          L"(%hs):\n%ls\n\n%ls", zip_method_name(p->zip.method), w, k_extract_first);
        break;
    case ZIP_ERR_ZIP64:
        swprintf(m, 2048, L"This zip file uses the ZIP64 format, which this player cannot read:\n%ls\n\n%ls",
                 w, k_extract_first);
        break;
    case ZIP_ERR_SPLIT:
        swprintf(m, 2048, L"This zip file is one part of an archive split into several files:\n%ls\n\n"
                          L"Please extract the zip first with an archive program (for example 7-Zip), then "
                          L"open the extracted game file (.ngc).", w);
        break;
    case ZIP_ERR_EMPTY:
        swprintf(m, 2048, L"This zip file contains no files:\n%ls", w);
        break;
    case ZIP_ERR_TOO_BIG:
        swprintf(m, 2048, L"Cannot open the ROM file:\n%ls\n(too large for a Neo Geo Pocket ROM: %u bytes)",
                 w, (unsigned)p->zip.size);
        break;
    case ZIP_ERR_CRC:
        swprintf(m, 2048, L"The game file in this zip is damaged: once unpacked, its checksum (CRC32) differs "
                          L"from the one stored in the zip:\n%ls\n\nCopy or download the zip again.", w);
        break;
    case ZIP_ERR_CORRUPT:
        swprintf(m, 2048, L"The game file in this zip is damaged (its packed data is invalid or incomplete):\n"
                          L"%ls\n\nCopy or download the zip again.", w);
        break;
    case ZIP_ERR_FORMAT:
        swprintf(m, 2048, L"This zip file is damaged or incomplete (the list of its contents at the end of the "
                          L"file is missing or broken):\n%ls\n\nCopy or download it again.", w);
        break;
    case ZIP_ERR_NOMEM:
        swprintf(m, 2048, L"Not enough memory to unpack the zip file:\n%ls", w);
        break;
    default:
        swprintf(m, 2048, L"Cannot read the zip file:\n%ls\n(%hs)", w, zip_error_string(err));
        break;
    }
}

/* rom_path for messages; for a zip with a line naming the file inside. */
static wchar_t *make_shown_path(const RomPrep *p)
{
    if (!p->zip.name) return zen_wcsdup(p->rom_path);
    size_t n = wcslen(p->rom_path) + wcslen(p->zip.name) + 32;
    wchar_t *s = (wchar_t *)malloc(n * sizeof(wchar_t));
    if (s) swprintf(s, n, L"%ls\n(file in the zip: %ls)", p->rom_path, p->zip.name);
    return s;
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
        if (p->zip.name && !p->zip.by_name)
            swprintf(out, cap, L"It does not look like a Neo Geo Pocket ROM (it has no SNK cartridge header). "
                               L"The zip holds no .ngc, .ngp or .npc file; this is the largest file in it.");
        else if (!p->zip.name && ends_with_ci(p->rom_path, L".zip"))
            swprintf(out, cap, L"It is named like a zip file, but it is neither a zip archive nor a Neo Geo "
                               L"Pocket ROM (a damaged or incomplete download?).");
        else
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

    /* a .zip: the game file inside it, unpacked in memory */
    int ze = unzip_game(p->rom_path, NGP_ROM_MAX, &p->file, &p->file_size, &p->zip);
    p->shown_path = make_shown_path(p);
    if (ze > 0) {
        zip_message(p, ze);
        return ROMPREP_ERROR;
    }
    if (ze < 0) {   /* not a zip: the file itself */
        int e = zen_read_file(p->rom_path, &p->file, &p->file_size, NGP_ROM_MAX);
        if (e != ZEN_FILE_OK) {
            swprintf(p->message, 2048, L"Cannot open the ROM file:\n%ls\n(%hs)", p->rom_path,
                     e == ZEN_FILE_TOO_BIG ? "too large for a Neo Geo Pocket ROM" : zen_file_error(e));
            return ROMPREP_ERROR;
        }
    }
    if (is_archive(p->file, p->file_size)) {
        if (p->zip.name)
            swprintf(p->message, 2048,
                     L"The file in this zip is itself a compressed archive, not a ROM:\n%ls\n\n"
                     L"Extract the game file (.ngc) from it first, then open that file.", shown(p));
        else
            swprintf(p->message, 2048,
                     L"This is a compressed archive (.7z, .rar or .gz), not a ROM:\n%ls\n\n"
                     L"Extract the game file (.ngc) from it first, then open that file. "
                     L"(A .zip file can be opened directly.)", p->rom_path);
        return ROMPREP_ERROR;
    }
    if (p->file_size <= 0x40) {
        swprintf(p->message, 2048, L"This file is not a Neo Geo Pocket ROM (too small):\n%ls", shown(p));
        return ROMPREP_ERROR;
    }
    sha1(p->file, p->file_size, p->file_sha1);
    p->file_crc = bps_crc32(0, p->file, p->file_size);

    find_patch(p, patch_override);
    uint8_t *patch = NULL;
    size_t patch_size = 0;
    if (p->patch_path) {
        int e = zen_read_file(p->patch_path, &patch, &patch_size, PATCH_MAX_SIZE);
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
                 shown(p), p->file_size, (unsigned)p->file_crc, hex, p->why, k_expected);
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
    s_image_size = size;
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

const uint8_t *rom_image(size_t *size)
{
    if (size) *size = s_pristine ? s_image_size : 0;
    return s_pristine;
}

int rom_write_image(const RomPrep *p, const wchar_t *out_path)
{
    if (!p->image) return 0;
    return zen_write_file_atomic(out_path, p->image, p->image_size) == ZEN_FILE_OK;
}
