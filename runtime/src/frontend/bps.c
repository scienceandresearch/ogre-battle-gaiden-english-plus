/*
 * BPS patch applier. See bps.h for the format.
 */
#include "bps.h"

#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------------ */
/* CRC32 (IEEE 802.3, reflected, as used by zlib and BPS)               */
/* ------------------------------------------------------------------ */

static uint32_t s_crc_table[256];
static int s_crc_ready;

static void crc_init(void)
{
    for (uint32_t n = 0; n < 256; n++) {
        uint32_t c = n;
        for (int k = 0; k < 8; k++) c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
        s_crc_table[n] = c;
    }
    s_crc_ready = 1;
}

uint32_t bps_crc32(uint32_t crc, const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;
    if (!s_crc_ready) crc_init();
    crc = ~crc;
    for (size_t i = 0; i < len; i++) crc = s_crc_table[(crc ^ p[i]) & 0xFF] ^ (crc >> 8);
    return ~crc;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                              */
/* ------------------------------------------------------------------ */

static uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* Reads one variable-length number from p[*pos] (pos < end). At most 8 bytes
   are accepted, which bounds the value below 2^57 (no 64-bit overflow). */
static int read_number(const uint8_t *p, size_t end, size_t *pos, uint64_t *out)
{
    uint64_t data = 0, shift = 1;
    for (int i = 0; i < 8; i++) {
        if (*pos >= end) return BPS_ERR_TRUNCATED;
        uint8_t x = p[(*pos)++];
        data += (uint64_t)(x & 0x7F) * shift;
        if (x & 0x80) {
            *out = data;
            return BPS_OK;
        }
        shift <<= 7;
        data += shift;
    }
    return BPS_ERR_NUMBER;
}

/* Applies a signed relative move encoded as d (bit 0 = sign, rest = magnitude)
   to *rel; the result must stay within [0, limit]. */
static int seek_relative(uint64_t *rel, uint64_t d, uint64_t limit)
{
    uint64_t mag = d >> 1;
    if (d & 1) {
        if (mag > *rel) return BPS_ERR_BOUNDS;
        *rel -= mag;
    } else {
        if (mag > limit || *rel > limit - mag) return BPS_ERR_BOUNDS;
        *rel += mag;
    }
    return BPS_OK;
}

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */

int bps_read_info(const uint8_t *patch, size_t patch_size, BpsInfo *info)
{
    if (!patch || !info) return BPS_ERR_ARGS;
    memset(info, 0, sizeof(*info));
    /* "BPS1" + three one-byte numbers + 12-byte footer */
    if (patch_size < 4 + 3 + 12) return BPS_ERR_TOO_SMALL;
    if (memcmp(patch, "BPS1", 4) != 0) return BPS_ERR_MAGIC;

    uint32_t patch_crc = rd32(patch + patch_size - 4);
    if (bps_crc32(0, patch, patch_size - 4) != patch_crc) return BPS_ERR_PATCH_CRC;

    size_t end = patch_size - 12, pos = 4;
    int e;
    if ((e = read_number(patch, end, &pos, &info->source_size)) != BPS_OK) return e;
    if ((e = read_number(patch, end, &pos, &info->target_size)) != BPS_OK) return e;
    if ((e = read_number(patch, end, &pos, &info->metadata_size)) != BPS_OK) return e;
    if (info->metadata_size > (uint64_t)(end - pos)) return BPS_ERR_TRUNCATED;
    info->metadata_offset = pos;
    pos += (size_t)info->metadata_size;
    info->actions_offset = pos;
    info->source_crc = rd32(patch + patch_size - 12);
    info->target_crc = rd32(patch + patch_size - 8);
    info->patch_crc = patch_crc;
    return BPS_OK;
}

int bps_apply(const uint8_t *patch, size_t patch_size,
              const uint8_t *source, size_t source_size,
              uint8_t **out, size_t *out_size, uint64_t max_target, BpsInfo *info_out)
{
    BpsInfo info;
    int e;

    if (!out || !out_size || (!source && source_size)) return BPS_ERR_ARGS;
    *out = NULL;
    *out_size = 0;
    if ((e = bps_read_info(patch, patch_size, &info)) != BPS_OK) return e;
    if (info_out) *info_out = info;

    if (info.source_size != (uint64_t)source_size) return BPS_ERR_SOURCE_SIZE;
    if (bps_crc32(0, source, source_size) != info.source_crc) return BPS_ERR_SOURCE_CRC;
    if (!max_target) max_target = BPS_DEFAULT_MAX_TARGET;
    if (info.target_size > (uint64_t)(SIZE_MAX / 2) || info.target_size > max_target) return BPS_ERR_HEADER;

    const uint64_t tsize = info.target_size;
    const uint64_t ssize = (uint64_t)source_size;
    uint8_t *t = (uint8_t *)malloc(tsize ? (size_t)tsize : 1);
    if (!t) return BPS_ERR_NOMEM;

    const size_t end = patch_size - 12;
    size_t pos = info.actions_offset;
    uint64_t out_off = 0, src_rel = 0, tgt_rel = 0;

    while (pos < end) {
        uint64_t data, d;
        if ((e = read_number(patch, end, &pos, &data)) != BPS_OK) goto fail;
        unsigned cmd = (unsigned)(data & 3);
        uint64_t len = (data >> 2) + 1;
        if (len > tsize - out_off) { e = BPS_ERR_BOUNDS; goto fail; }   /* out_off <= tsize */

        switch (cmd) {
        case 0:   /* SourceRead */
            if (out_off > ssize || len > ssize - out_off) { e = BPS_ERR_BOUNDS; goto fail; }
            memcpy(t + out_off, source + out_off, (size_t)len);
            break;
        case 1:   /* TargetRead */
            if (len > (uint64_t)(end - pos)) { e = BPS_ERR_TRUNCATED; goto fail; }
            memcpy(t + out_off, patch + pos, (size_t)len);
            pos += (size_t)len;
            break;
        case 2:   /* SourceCopy */
            if ((e = read_number(patch, end, &pos, &d)) != BPS_OK) goto fail;
            if ((e = seek_relative(&src_rel, d, ssize)) != BPS_OK) goto fail;
            if (len > ssize - src_rel) { e = BPS_ERR_BOUNDS; goto fail; }
            memcpy(t + out_off, source + src_rel, (size_t)len);
            src_rel += len;
            break;
        default:  /* TargetCopy: reads only bytes already written, may overlap */
            if ((e = read_number(patch, end, &pos, &d)) != BPS_OK) goto fail;
            if ((e = seek_relative(&tgt_rel, d, tsize)) != BPS_OK) goto fail;
            if (tgt_rel >= out_off) { e = BPS_ERR_BOUNDS; goto fail; }
            for (uint64_t i = 0; i < len; i++) t[out_off + i] = t[tgt_rel + i];
            tgt_rel += len;
            break;
        }
        out_off += len;
    }
    if (out_off != tsize) { e = BPS_ERR_TARGET_SIZE; goto fail; }
    if (bps_crc32(0, t, (size_t)tsize) != info.target_crc) { e = BPS_ERR_TARGET_CRC; goto fail; }

    *out = t;
    *out_size = (size_t)tsize;
    return BPS_OK;

fail:
    free(t);
    return e;
}

const char *bps_error_string(int err)
{
    switch (err) {
    case BPS_OK:              return "no error";
    case BPS_ERR_ARGS:        return "invalid arguments";
    case BPS_ERR_TOO_SMALL:   return "the file is too small to be a BPS patch";
    case BPS_ERR_MAGIC:       return "not a BPS patch (no BPS1 signature)";
    case BPS_ERR_PATCH_CRC:   return "the patch file is damaged (patch checksum mismatch)";
    case BPS_ERR_NUMBER:      return "the patch contains a malformed number";
    case BPS_ERR_HEADER:      return "the patch header is invalid or the output is too large";
    case BPS_ERR_SOURCE_SIZE: return "the ROM size differs from the one the patch was made for";
    case BPS_ERR_SOURCE_CRC:  return "the ROM is not the one the patch was made for (source checksum mismatch)";
    case BPS_ERR_TRUNCATED:   return "the patch data ends unexpectedly";
    case BPS_ERR_BOUNDS:      return "a patch action is out of bounds";
    case BPS_ERR_TARGET_SIZE: return "the patch did not produce the declared output size";
    case BPS_ERR_TARGET_CRC:  return "the patched result is wrong (target checksum mismatch)";
    case BPS_ERR_NOMEM:       return "out of memory";
    default:                  return "unknown error";
    }
}
