/*
 * SHA-1 (FIPS 180-4).
 */
#include "sha1.h"

#include <string.h>

static uint32_t rol(uint32_t v, int n) { return (v << n) | (v >> (32 - n)); }

static void sha1_block(Sha1 *s, const uint8_t *p)
{
    uint32_t w[80];
    for (int i = 0; i < 16; i++)
        w[i] = ((uint32_t)p[i * 4] << 24) | ((uint32_t)p[i * 4 + 1] << 16) |
               ((uint32_t)p[i * 4 + 2] << 8) | (uint32_t)p[i * 4 + 3];
    for (int i = 16; i < 80; i++) w[i] = rol(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);

    uint32_t a = s->h[0], b = s->h[1], c = s->h[2], d = s->h[3], e = s->h[4];
    for (int i = 0; i < 80; i++) {
        uint32_t f, k;
        if (i < 20)      { f = (b & c) | (~b & d);           k = 0x5A827999u; }
        else if (i < 40) { f = b ^ c ^ d;                    k = 0x6ED9EBA1u; }
        else if (i < 60) { f = (b & c) | (b & d) | (c & d);  k = 0x8F1BBCDCu; }
        else             { f = b ^ c ^ d;                    k = 0xCA62C1D6u; }
        uint32_t t = rol(a, 5) + f + e + k + w[i];
        e = d;
        d = c;
        c = rol(b, 30);
        b = a;
        a = t;
    }
    s->h[0] += a; s->h[1] += b; s->h[2] += c; s->h[3] += d; s->h[4] += e;
}

void sha1_init(Sha1 *s)
{
    s->h[0] = 0x67452301u;
    s->h[1] = 0xEFCDAB89u;
    s->h[2] = 0x98BADCFEu;
    s->h[3] = 0x10325476u;
    s->h[4] = 0xC3D2E1F0u;
    s->length = 0;
    s->used = 0;
}

void sha1_update(Sha1 *s, const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;
    s->length += len;
    if (s->used) {
        size_t n = 64 - s->used;
        if (n > len) n = len;
        memcpy(s->block + s->used, p, n);
        s->used += n;
        p += n;
        len -= n;
        if (s->used < 64) return;
        sha1_block(s, s->block);
        s->used = 0;
    }
    while (len >= 64) {
        sha1_block(s, p);
        p += 64;
        len -= 64;
    }
    if (len) {
        memcpy(s->block, p, len);
        s->used = len;
    }
}

void sha1_final(Sha1 *s, uint8_t digest[20])
{
    uint64_t bits = s->length * 8;
    uint8_t pad = 0x80;
    sha1_update(s, &pad, 1);
    uint8_t zero = 0;
    while (s->used != 56) sha1_update(s, &zero, 1);
    uint8_t len_be[8];
    for (int i = 0; i < 8; i++) len_be[i] = (uint8_t)(bits >> (56 - 8 * i));
    sha1_update(s, len_be, 8);
    for (int i = 0; i < 5; i++) {
        digest[i * 4 + 0] = (uint8_t)(s->h[i] >> 24);
        digest[i * 4 + 1] = (uint8_t)(s->h[i] >> 16);
        digest[i * 4 + 2] = (uint8_t)(s->h[i] >> 8);
        digest[i * 4 + 3] = (uint8_t)s->h[i];
    }
}

void sha1(const void *data, size_t len, uint8_t digest[20])
{
    Sha1 s;
    sha1_init(&s);
    sha1_update(&s, data, len);
    sha1_final(&s, digest);
}

void sha1_hex(const uint8_t digest[20], char out[41])
{
    static const char hex[] = "0123456789abcdef";
    for (int i = 0; i < 20; i++) {
        out[i * 2] = hex[digest[i] >> 4];
        out[i * 2 + 1] = hex[digest[i] & 15];
    }
    out[40] = 0;
}
