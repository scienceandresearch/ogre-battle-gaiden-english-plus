/*
 * Minimal ZIP reader for the player, so the game can be opened straight from
 * the .zip it usually comes in. Original code for this project (MIT License),
 * including its own inflate decoder (RFC 1951); no zlib.
 *
 * Supported: one-part archives (an archive comment and data in front of the
 * archive, e.g. a self-extractor stub, are fine), entries stored (method 0)
 * or compressed with deflate (method 8), names in UTF-8 (flag bit 11) or the
 * original PC code page 437, data descriptors (flag bit 3; the sizes and
 * CRC32 are taken from the central directory). Every entry is checked
 * against its CRC32 after unpacking.
 *
 * Reported as unsupported (the caller asks the user to extract the zip):
 * encrypted entries, other compression methods, ZIP64 archives or entries,
 * archives split into several parts.
 *
 * The archive is read through a callback (ZipSource), so large archives are
 * never loaded whole: only the end record, the central directory and the
 * chosen entry are read.
 */
#ifndef ZEN_ZIPREAD_H
#define ZEN_ZIPREAD_H

#include <stddef.h>
#include <stdint.h>

enum {
    ZIP_OK = 0,
    ZIP_ERR_READ,        /* the archive file cannot be read */
    ZIP_ERR_FORMAT,      /* no usable end record / central directory: damaged or truncated */
    ZIP_ERR_SPLIT,       /* one part of an archive split into several files */
    ZIP_ERR_ZIP64,       /* the archive or the entry needs ZIP64 */
    ZIP_ERR_EMPTY,       /* the archive holds no files */
    ZIP_ERR_ENCRYPTED,   /* the entry is encrypted (password-protected) */
    ZIP_ERR_METHOD,      /* the entry uses a compression method other than stored or deflate */
    ZIP_ERR_TOO_BIG,     /* the entry is larger than the caller's limit */
    ZIP_ERR_CORRUPT,     /* the entry's header or compressed data is damaged or truncated */
    ZIP_ERR_CRC,         /* the unpacked data does not match the entry's CRC32 */
    ZIP_ERR_NOMEM,       /* out of memory */
    ZIP_ERR_COUNT
};

/* Largest entry the player unpacks (Neo Geo Pocket ROMs are at most 4 MB). */
#define ZIP_MAX_ENTRY_SIZE (8u * 1024u * 1024u)

typedef struct {
    void    *ctx;
    uint64_t size;   /* archive size in bytes */
    /* Reads len bytes at offset into buf; returns 1 only if all were read. */
    int    (*read)(void *ctx, uint64_t offset, void *buf, size_t len);
} ZipSource;

typedef struct {
    const char *name;          /* NUL-terminated copy of the stored name (bytes as stored) */
    size_t   name_len;
    int      utf8;             /* flag bit 11: the name is UTF-8 (else code page 437) */
    int      is_dir;           /* the name ends with a slash */
    int      needs_zip64;      /* a size or the offset is in a ZIP64 extra field */
    uint16_t flags;            /* general purpose bit flags */
    uint16_t method;           /* 0 stored, 8 deflate, others unsupported */
    uint32_t crc32;
    uint32_t comp_size;
    uint32_t size;             /* uncompressed size */
    uint64_t local_offset;     /* local header, adjusted for data in front of the archive */
} ZipEntry;

typedef struct {
    ZipSource src;
    ZipEntry *entries;
    int       count;
    char     *names;           /* storage for the entries' names */
} ZipArchive;

/* 1 if data (at least 4 bytes) starts like a zip archive (local header,
   empty archive or split-archive marker). */
int  zip_signature(const uint8_t *data, size_t size);

/* Reads the end record and the central directory. On success the caller
   calls zip_close(). On failure nothing needs to be freed. */
int  zip_open(ZipArchive *z, const ZipSource *src);
void zip_close(ZipArchive *z);

/* The game file in the archive: among the files whose names end in .ngc,
   .ngp or .npc (any case), or all files when there is none, the one with
   CRC32 known_crc and size known_size, else the largest (the first one on a
   tie). Directories are never chosen. Returns the entry index, or -1 when
   the archive holds no files. *by_name is set to 1 when the name decided. */
int  zip_choose_rom(const ZipArchive *z, uint32_t known_crc, uint32_t known_size, int *by_name);

/* Unpacks entry index into a malloc'd buffer (*out, *out_size; the caller
   frees it). Entries larger than max_size give ZIP_ERR_TOO_BIG. */
int  zip_extract(const ZipArchive *z, int index, size_t max_size, uint8_t **out, size_t *out_size);

/* Raw deflate decoder: decodes in[0, in_size) into exactly out_size bytes.
   Returns ZIP_OK, or ZIP_ERR_CORRUPT for invalid or truncated data and for
   data that does not decode to exactly out_size bytes. */
int  zip_inflate(const uint8_t *in, size_t in_size, uint8_t *out, size_t out_size);

const char *zip_error_string(int err);
/* Name of a compression method ("stored", "deflate", "LZMA", "method 77"...). */
const char *zip_method_name(int method);

#endif
