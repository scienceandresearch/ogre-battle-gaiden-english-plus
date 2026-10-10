/*
 * Minimal PNG writer (uncompressed deflate blocks) for screenshots.
 */
#include "png.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t crc_table[256];
static int crc_ready;

static void crc_init(void)
{
    for (uint32_t n = 0; n < 256; n++) {
        uint32_t c = n;
        for (int k = 0; k < 8; k++) c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
        crc_table[n] = c;
    }
    crc_ready = 1;
}

static uint32_t crc_update(uint32_t crc, const uint8_t *buf, size_t len)
{
    if (!crc_ready) crc_init();
    for (size_t i = 0; i < len; i++) crc = crc_table[(crc ^ buf[i]) & 0xFF] ^ (crc >> 8);
    return crc;
}

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16); p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v;
}

static void chunk(FILE *f, const char *type, const uint8_t *data, uint32_t len)
{
    uint8_t hdr[8];
    put32(hdr, len);
    memcpy(hdr + 4, type, 4);
    fwrite(hdr, 1, 8, f);
    if (len) fwrite(data, 1, len, f);
    uint32_t crc = crc_update(0xFFFFFFFFu, (const uint8_t *)type, 4);
    crc = crc_update(crc, data, len) ^ 0xFFFFFFFFu;
    uint8_t c[4];
    put32(c, crc);
    fwrite(c, 1, 4, f);
}

int png_write_rgb(const char *path, const uint32_t *xrgb, int w, int h, int scale)
{
    if (scale < 1) scale = 1;
    int W = w * scale, H = h * scale;
    size_t raw_len = (size_t)H * (size_t)(W * 3 + 1);
    uint8_t *raw = (uint8_t *)malloc(raw_len);
    if (!raw) return 0;
    uint8_t *p = raw;
    for (int y = 0; y < H; y++) {
        *p++ = 0;
        const uint32_t *row = xrgb + (size_t)(y / scale) * (size_t)w;
        for (int x = 0; x < W; x++) {
            uint32_t c = row[x / scale];
            *p++ = (uint8_t)(c >> 16); *p++ = (uint8_t)(c >> 8); *p++ = (uint8_t)c;
        }
    }
    /* zlib stream with stored blocks */
    size_t nblocks = (raw_len + 65534) / 65535;
    size_t z_len = 2 + raw_len + nblocks * 5 + 4;
    uint8_t *z = (uint8_t *)malloc(z_len);
    if (!z) { free(raw); return 0; }
    uint8_t *q = z;
    *q++ = 0x78; *q++ = 0x01;
    size_t off = 0;
    uint32_t a = 1, b = 0;
    for (size_t i = 0; i < raw_len; i++) { a = (a + raw[i]) % 65521; b = (b + a) % 65521; }
    while (off < raw_len) {
        size_t n = raw_len - off;
        if (n > 65535) n = 65535;
        *q++ = (uint8_t)(off + n == raw_len ? 1 : 0);
        *q++ = (uint8_t)n; *q++ = (uint8_t)(n >> 8);
        *q++ = (uint8_t)~n; *q++ = (uint8_t)(~n >> 8);
        memcpy(q, raw + off, n);
        q += n;
        off += n;
    }
    put32(q, (b << 16) | a);
    q += 4;

    FILE *f = fopen(path, "wb");
    if (!f) { free(raw); free(z); return 0; }
    static const uint8_t sig[8] = {0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n'};
    fwrite(sig, 1, 8, f);
    uint8_t ihdr[13];
    put32(ihdr, (uint32_t)W);
    put32(ihdr + 4, (uint32_t)H);
    ihdr[8] = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
    chunk(f, "IHDR", ihdr, 13);
    chunk(f, "IDAT", z, (uint32_t)(q - z));
    chunk(f, "IEND", NULL, 0);
    fclose(f);
    free(raw);
    free(z);
    return 1;
}
