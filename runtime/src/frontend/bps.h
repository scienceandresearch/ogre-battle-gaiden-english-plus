/*
 * BPS patch applier (the "beat" patch format designed by byuu/Near).
 *
 * Layout:
 *   "BPS1"
 *   number source_size, number target_size, number metadata_size
 *   metadata (metadata_size bytes, ignored here)
 *   actions until 12 bytes before the end:
 *     number data; command = data & 3, length = (data >> 2) + 1
 *       0 SourceRead  target[out..+len] = source[out..+len]
 *       1 TargetRead  target[out..+len] = next len patch bytes
 *       2 SourceCopy  number d; source_rel += (d & 1 ? -1 : +1) * (d >> 1);
 *                     copy len bytes from source[source_rel++]
 *       3 TargetCopy  number d; target_rel += (d & 1 ? -1 : +1) * (d >> 1);
 *                     copy len bytes from target[target_rel++] (may overlap)
 *   uint32 source CRC32, uint32 target CRC32, uint32 patch CRC32 (little endian;
 *   the patch CRC covers every byte before it)
 *
 * Numbers are variable length: 7 data bits per byte, the last byte has bit 7
 * set, and each continuation adds an implicit offset so encodings are unique.
 *
 * Every offset and length is bounds-checked; all three checksums are verified.
 */
#ifndef ZEN_BPS_H
#define ZEN_BPS_H

#include <stddef.h>
#include <stdint.h>

enum {
    BPS_OK = 0,
    BPS_ERR_ARGS,          /* invalid arguments */
    BPS_ERR_TOO_SMALL,     /* shorter than the smallest possible patch */
    BPS_ERR_MAGIC,         /* no "BPS1" signature */
    BPS_ERR_PATCH_CRC,     /* patch checksum mismatch: damaged patch file */
    BPS_ERR_NUMBER,        /* malformed (over-long) variable-length number */
    BPS_ERR_HEADER,        /* sizes in the header are unusable */
    BPS_ERR_SOURCE_SIZE,   /* the input file has a different size */
    BPS_ERR_SOURCE_CRC,    /* the input file is not the patch's source */
    BPS_ERR_TRUNCATED,     /* data runs past the end of the action area */
    BPS_ERR_BOUNDS,        /* an action reads or writes out of bounds */
    BPS_ERR_TARGET_SIZE,   /* the actions did not fill the target exactly */
    BPS_ERR_TARGET_CRC,    /* the result does not match the target checksum */
    BPS_ERR_NOMEM,         /* out of memory */
    BPS_ERR_COUNT
};

typedef struct {
    uint64_t source_size;
    uint64_t target_size;
    uint64_t metadata_size;
    size_t   metadata_offset;   /* offset of the metadata inside the patch */
    size_t   actions_offset;    /* offset of the first action */
    uint32_t source_crc;
    uint32_t target_crc;
    uint32_t patch_crc;
} BpsInfo;

/* zlib-compatible CRC32. Start with crc = 0; pass the previous result to
   continue over more data. */
uint32_t bps_crc32(uint32_t crc, const void *data, size_t len);

/* Checks the signature and the patch checksum, and reads the header and
   footer into *info. */
int bps_read_info(const uint8_t *patch, size_t patch_size, BpsInfo *info);

/* Largest target accepted when the caller passes max_target = 0 (the same
   limit as tools/patch/bps.py), so a damaged header can never make the
   applier try to allocate an absurd amount of memory. */
#define BPS_DEFAULT_MAX_TARGET (256u * 1024u * 1024u)

/* Applies a patch to source. On success *out receives a malloc'd buffer of
   *out_size bytes (the caller frees it). Patches that declare a target larger
   than max_target (0 = BPS_DEFAULT_MAX_TARGET) are rejected with
   BPS_ERR_HEADER. info may be NULL. */
int bps_apply(const uint8_t *patch, size_t patch_size,
              const uint8_t *source, size_t source_size,
              uint8_t **out, size_t *out_size, uint64_t max_target, BpsInfo *info);

/* Human-readable description of an error code. */
const char *bps_error_string(int err);

#endif
