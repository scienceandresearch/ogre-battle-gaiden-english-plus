/*
 * SHA-1 (FIPS 180-4), used to identify ROM images.
 */
#ifndef ZEN_SHA1_H
#define ZEN_SHA1_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t h[5];
    uint64_t length;      /* bytes hashed so far */
    uint8_t  block[64];
    size_t   used;        /* bytes waiting in block */
} Sha1;

void sha1_init(Sha1 *s);
void sha1_update(Sha1 *s, const void *data, size_t len);
void sha1_final(Sha1 *s, uint8_t digest[20]);

/* One-shot helpers. */
void sha1(const void *data, size_t len, uint8_t digest[20]);
void sha1_hex(const uint8_t digest[20], char out[41]);

#endif
