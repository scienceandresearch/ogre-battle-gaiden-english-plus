/*
 * ZIP reader and inflate decoder. See zipread.h.
 *
 * Original code for this project (MIT License), written from the format
 * descriptions: PKWARE's APPNOTE.TXT for the archive structure and RFC 1951
 * for deflate.
 */
#include "zipread.h"
#include "bps.h"   /* bps_crc32: the CRC32 zip uses */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint16_t rd16(const uint8_t *p)
{
    return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* ------------------------------------------------------------------ */
/* Inflate (RFC 1951)                                                   */
/* ------------------------------------------------------------------ */

/* A Huffman code is decoded with a table indexed by the next FAST_BITS
   input bits, which holds every code up to that length. The longer codes
   belong to rare symbols; they are kept in a short list and compared one
   by one. */
#define FAST_BITS    9
#define FAST_SIZE    (1u << FAST_BITS)
#define MAX_CODE_LEN 15
#define MAX_SYMBOLS  288

typedef struct {
    uint16_t fast[FAST_SIZE];         /* (symbol << 4) | code length; 0 = no code that short */
    uint16_t long_code[MAX_SYMBOLS];  /* longer codes, in input bit order */
    uint16_t long_sym[MAX_SYMBOLS];
    uint8_t  long_len[MAX_SYMBOLS];
    int      nlong;
} Huff;

typedef struct {
    const uint8_t *in;
    size_t   in_size, in_pos;
    uint32_t hold;   /* input bits not used yet; the next one is bit 0 */
    int      held;   /* number of valid bits in hold (the rest are zero) */
    uint8_t *out;
    size_t   out_size, out_pos;
} Inflater;

/* Length symbols 257..285 and distance symbols 0..29: base value and number
   of extra bits (RFC 1951, 3.2.5). */
static const uint16_t k_len_base[29] = {
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
    35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258,
};
static const uint8_t k_len_extra[29] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
    3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
};
static const uint16_t k_dist_base[30] = {
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
    257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577,
};
static const uint8_t k_dist_extra[30] = {
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
    7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13,
};
/* Order in which a dynamic block lists the code lengths of the code length
   alphabet (RFC 1951, 3.2.7). */
static const uint8_t k_clen_order[19] = {16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15};

/* Tops up hold with whole input bytes while there is room for another one. */
static void refill(Inflater *s)
{
    while (s->held <= 24 && s->in_pos < s->in_size) {
        s->hold |= (uint32_t)s->in[s->in_pos++] << s->held;
        s->held += 8;
    }
}

/* The next n (0..16) input bits as a number (first bit lowest), or -1 when
   the input ends first. */
static int take_bits(Inflater *s, int n)
{
    if (s->held < n) {
        refill(s);
        if (s->held < n) return -1;
    }
    int v = (int)(s->hold & ((1u << n) - 1u));
    s->hold >>= n;
    s->held -= n;
    return v;
}

/* Builds the decoder for a code given by its code lengths (0 = symbol not
   used), assigning the canonical codes of RFC 1951, 3.2.2. Returns 0 when
   the lengths ask for more codes than exist (over-subscribed), or leave
   codes unused (incomplete) except in the two cases deflate encoders
   produce: no code at all (a block that needs none) and, when one_ok, a
   single one-bit code (one distance in use). Unused bit patterns fail when
   decoded. */
static int huff_build(Huff *h, const uint8_t *lens, int n, int one_ok)
{
    int count[MAX_CODE_LEN + 1];
    memset(count, 0, sizeof(count));
    for (int i = 0; i < n; i++) count[lens[i]]++;
    count[0] = 0;

    int free_codes = 1, used = 0;
    for (int len = 1; len <= MAX_CODE_LEN; len++) {
        free_codes = free_codes * 2 - count[len];
        if (free_codes < 0) return 0;
        used += count[len];
    }
    if (free_codes > 0 && used > 0 && !(one_ok && used == 1 && count[1] == 1)) return 0;

    int next[MAX_CODE_LEN + 1];   /* next code to hand out, per length */
    int code = 0;
    next[0] = 0;
    for (int len = 1; len <= MAX_CODE_LEN; len++) {
        code = (code + count[len - 1]) << 1;
        next[len] = code;
    }

    memset(h->fast, 0, sizeof(h->fast));
    h->nlong = 0;
    for (int sym = 0; sym < n; sym++) {
        int len = lens[sym];
        if (len == 0) continue;
        /* the code's first bit is its most significant one and arrives
           first, so in input bit order the code is reversed */
        unsigned c = (unsigned)next[len]++, rev = 0;
        for (int i = 0; i < len; i++) {
            rev = (rev << 1) | (c & 1u);
            c >>= 1;
        }
        if (len <= FAST_BITS) {
            for (unsigned k = rev; k < FAST_SIZE; k += 1u << len)
                h->fast[k] = (uint16_t)(((unsigned)sym << 4) | (unsigned)len);
        } else {
            h->long_code[h->nlong] = (uint16_t)rev;
            h->long_sym[h->nlong] = (uint16_t)sym;
            h->long_len[h->nlong] = (uint8_t)len;
            h->nlong++;
        }
    }
    return 1;
}

/* Decodes one symbol; -1 for a bit pattern that is no code, or when the
   input ends inside the code. */
static int huff_decode(Inflater *s, const Huff *h)
{
    if (s->held < MAX_CODE_LEN) refill(s);
    int sym = -1, len = 0;
    unsigned e = h->fast[s->hold & (FAST_SIZE - 1u)];
    if (e) {
        sym = (int)(e >> 4);
        len = (int)(e & 15u);
    } else {
        for (int i = 0; i < h->nlong; i++) {
            if ((s->hold & ((1u << h->long_len[i]) - 1u)) == h->long_code[i]) {
                sym = h->long_sym[i];
                len = h->long_len[i];
                break;
            }
        }
    }
    if (sym < 0 || len > s->held) return -1;
    s->hold >>= len;
    s->held -= len;
    return sym;
}

/* A stored (uncompressed) block: LEN, NLEN = ~LEN, then LEN bytes, starting
   at the next byte boundary. */
static int inflate_stored(Inflater *s)
{
    int skip = s->held & 7;   /* the rest of the current byte; hold then holds whole bytes */
    s->hold >>= skip;
    s->held -= skip;
    int len = take_bits(s, 16), nlen = take_bits(s, 16);
    if (len < 0 || nlen < 0 || (len ^ 0xFFFF) != nlen) return 0;
    if ((size_t)len > s->out_size - s->out_pos) return 0;
    while (len > 0 && s->held >= 8) {
        s->out[s->out_pos++] = (uint8_t)s->hold;
        s->hold >>= 8;
        s->held -= 8;
        len--;
    }
    if ((size_t)len > s->in_size - s->in_pos) return 0;
    memcpy(s->out + s->out_pos, s->in + s->in_pos, (size_t)len);
    s->out_pos += (size_t)len;
    s->in_pos += (size_t)len;
    return 1;
}

/* The symbols of a Huffman-coded block, up to its end-of-block symbol. */
static int inflate_codes(Inflater *s, const Huff *lit, const Huff *dist)
{
    for (;;) {
        int sym = huff_decode(s, lit);
        if (sym < 0) return 0;
        if (sym < 256) {
            if (s->out_pos >= s->out_size) return 0;
            s->out[s->out_pos++] = (uint8_t)sym;
            continue;
        }
        if (sym == 256) return 1;
        sym -= 257;
        if (sym >= 29) return 0;   /* 286 and 287 do not occur in valid data */
        int x = take_bits(s, k_len_extra[sym]);
        if (x < 0) return 0;
        size_t len = (size_t)k_len_base[sym] + (size_t)x;
        int dsym = huff_decode(s, dist);
        if (dsym < 0 || dsym >= 30) return 0;
        x = take_bits(s, k_dist_extra[dsym]);
        if (x < 0) return 0;
        size_t d = (size_t)k_dist_base[dsym] + (size_t)x;
        if (d > s->out_pos || len > s->out_size - s->out_pos) return 0;
        /* byte by byte: a copy may overlap the bytes it produces (d < len
           repeats the last d bytes) */
        uint8_t *dst = s->out + s->out_pos;
        const uint8_t *src = dst - d;
        for (size_t i = 0; i < len; i++) dst[i] = src[i];
        s->out_pos += len;
    }
}

/* The code tables of a dynamic block (RFC 1951, 3.2.7). */
static int read_dynamic(Inflater *s, Huff *lit, Huff *dist)
{
    int nlit = take_bits(s, 5), ndist = take_bits(s, 5), nclen = take_bits(s, 4);
    if (nlit < 0 || ndist < 0 || nclen < 0) return 0;
    nlit += 257;
    ndist += 1;
    nclen += 4;
    if (nlit > 286 || ndist > 30) return 0;

    uint8_t clens[19];
    memset(clens, 0, sizeof(clens));
    for (int i = 0; i < nclen; i++) {
        int v = take_bits(s, 3);
        if (v < 0) return 0;
        clens[k_clen_order[i]] = (uint8_t)v;
    }
    Huff clh;
    if (!huff_build(&clh, clens, 19, 0)) return 0;

    uint8_t lens[286 + 30];
    int n = 0, total = nlit + ndist;
    while (n < total) {
        int sym = huff_decode(s, &clh);
        if (sym < 0) return 0;
        if (sym < 16) {
            lens[n++] = (uint8_t)sym;
            continue;
        }
        int rep, val = 0;
        if (sym == 16) {            /* repeat the previous length 3-6 times */
            if (n == 0) return 0;
            val = lens[n - 1];
            rep = take_bits(s, 2);
            if (rep < 0) return 0;
            rep += 3;
        } else if (sym == 17) {     /* 3-10 zeros */
            rep = take_bits(s, 3);
            if (rep < 0) return 0;
            rep += 3;
        } else {                    /* 11-138 zeros */
            rep = take_bits(s, 7);
            if (rep < 0) return 0;
            rep += 11;
        }
        if (rep > total - n) return 0;
        memset(lens + n, val, (size_t)rep);
        n += rep;
    }
    if (lens[256] == 0) return 0;   /* the block could never end */
    return huff_build(lit, lens, nlit, 1) && huff_build(dist, lens + nlit, ndist, 1);
}

static void build_fixed(Huff *lit, Huff *dist)
{
    uint8_t lens[MAX_SYMBOLS];
    int i = 0;
    for (; i < 144; i++) lens[i] = 8;
    for (; i < 256; i++) lens[i] = 9;
    for (; i < 280; i++) lens[i] = 7;
    for (; i < 288; i++) lens[i] = 8;
    huff_build(lit, lens, 288, 0);
    /* 32 five-bit codes, of which 30 and 31 never occur in valid data */
    memset(lens, 5, 32);
    huff_build(dist, lens, 32, 0);
}

int zip_inflate(const uint8_t *in, size_t in_size, uint8_t *out, size_t out_size)
{
    Inflater s;
    memset(&s, 0, sizeof(s));
    s.in = in;
    s.in_size = in ? in_size : 0;
    s.out = out;
    s.out_size = out ? out_size : 0;
    Huff lit, dist;
    int last = 0, ok = 1;
    while (ok && !last) {
        int head = take_bits(&s, 3);
        if (head < 0) return ZIP_ERR_CORRUPT;
        last = head & 1;
        switch (head >> 1) {
        case 0:
            ok = inflate_stored(&s);
            break;
        case 1:
            build_fixed(&lit, &dist);
            ok = inflate_codes(&s, &lit, &dist);
            break;
        case 2:
            ok = read_dynamic(&s, &lit, &dist) && inflate_codes(&s, &lit, &dist);
            break;
        default:   /* block type 3 is reserved */
            ok = 0;
            break;
        }
    }
    return ok && s.out_pos == out_size ? ZIP_OK : ZIP_ERR_CORRUPT;
}

/* ------------------------------------------------------------------ */
/* Archive structure (APPNOTE.TXT)                                      */
/* ------------------------------------------------------------------ */

#define SIG_LOCAL      0x04034B50u   /* "PK\3\4" local file header */
#define SIG_CENTRAL    0x02014B50u   /* "PK\1\2" central directory file header */
#define SIG_END        0x06054B50u   /* "PK\5\6" end of central directory */
#define SIG_LOCATOR64  0x07064B50u   /* "PK\6\7" ZIP64 end of central directory locator */
#define SIG_SPLIT      0x08074B50u   /* "PK\7\8" first bytes of a split archive */
#define SIG_SPLIT_ONE  0x30304B50u   /* "PK00": split archive that fit in one part */
#define LOCAL_SIZE     30u
#define CENTRAL_SIZE   46u
#define END_SIZE       22u
#define LOCATOR64_SIZE 20u
#define MAX_COMMENT    0xFFFFu
#define MAX_DIR_SIZE   (16u * 1024u * 1024u)

/* general purpose flags: encrypted, strong encryption, encrypted directory */
#define FLAGS_ENCRYPTED 0x2041u
#define FLAG_UTF8       0x0800u
#define METHOD_AES      99

int zip_signature(const uint8_t *data, size_t size)
{
    if (!data || size < 4) return 0;
    uint32_t s = rd32(data);
    return s == SIG_LOCAL || s == SIG_END || s == SIG_SPLIT || s == SIG_SPLIT_ONE;
}

void zip_close(ZipArchive *z)
{
    free(z->entries);
    free(z->names);
    memset(z, 0, sizeof(*z));
}

/* Reads the central directory an end record (at end_at) describes. Returns
   ZIP_ERR_FORMAT when the record does not lead to a directory, so the caller
   can look for another one. */
static int read_directory(ZipArchive *z, const ZipSource *src, const uint8_t *e, uint64_t end_at)
{
    uint16_t disk = rd16(e + 4), dir_disk = rd16(e + 6), n_here = rd16(e + 8), n_total = rd16(e + 10);
    uint32_t dir_size = rd32(e + 12), dir_offset = rd32(e + 16);

    /* a ZIP64 archive puts its own end records in front of this one */
    uint8_t loc[4];
    if (end_at >= LOCATOR64_SIZE && src->read(src->ctx, end_at - LOCATOR64_SIZE, loc, 4) &&
        rd32(loc) == SIG_LOCATOR64)
        return ZIP_ERR_ZIP64;
    if (disk == 0xFFFFu || dir_disk == 0xFFFFu || n_here == 0xFFFFu || n_total == 0xFFFFu ||
        dir_size == 0xFFFFFFFFu || dir_offset == 0xFFFFFFFFu)
        return ZIP_ERR_ZIP64;
    if (disk != 0 || dir_disk != 0 || n_here != n_total) return ZIP_ERR_SPLIT;

    /* The directory ends where the end record starts. When it is not where
       the record says, data was put in front of the archive (a
       self-extractor stub, for example): every offset moves by as much. */
    if (dir_size > end_at || end_at - dir_size < dir_offset) return ZIP_ERR_FORMAT;
    uint64_t dir_at = end_at - dir_size;
    uint64_t shift = dir_at - dir_offset;
    if (dir_size > MAX_DIR_SIZE || (uint64_t)n_total * CENTRAL_SIZE > dir_size) return ZIP_ERR_FORMAT;
    if (n_total == 0) {
        memset(z, 0, sizeof(*z));
        z->src = *src;
        return ZIP_OK;
    }

    uint8_t *dir = (uint8_t *)malloc(dir_size);
    ZipEntry *entries = (ZipEntry *)calloc(n_total, sizeof(ZipEntry));
    char *names = (char *)malloc((size_t)dir_size + n_total);   /* each name plus its NUL */
    int err = ZIP_OK;
    if (!dir || !entries || !names) err = ZIP_ERR_NOMEM;
    else if (!src->read(src->ctx, dir_at, dir, dir_size)) err = ZIP_ERR_READ;

    size_t pos = 0, npos = 0;
    for (int k = 0; err == ZIP_OK && k < n_total; k++) {
        const uint8_t *c = dir + pos;
        if (dir_size - pos < CENTRAL_SIZE || rd32(c) != SIG_CENTRAL) {
            err = ZIP_ERR_FORMAT;
            break;
        }
        uint16_t name_len = rd16(c + 28), extra_len = rd16(c + 30), comment_len = rd16(c + 32);
        size_t rec = (size_t)CENTRAL_SIZE + name_len + extra_len + comment_len;
        if (rec > dir_size - pos) {
            err = ZIP_ERR_FORMAT;
            break;
        }
        ZipEntry *en = &entries[k];
        memcpy(names + npos, c + CENTRAL_SIZE, name_len);
        names[npos + name_len] = 0;
        en->name = names + npos;
        en->name_len = name_len;
        npos += (size_t)name_len + 1;
        en->flags = rd16(c + 8);
        en->method = rd16(c + 10);
        en->crc32 = rd32(c + 16);
        en->comp_size = rd32(c + 20);
        en->size = rd32(c + 24);
        uint32_t local = rd32(c + 42);
        en->utf8 = (en->flags & FLAG_UTF8) != 0;
        en->is_dir = name_len > 0 && (en->name[name_len - 1] == '/' || en->name[name_len - 1] == '\\');
        en->needs_zip64 = en->comp_size == 0xFFFFFFFFu || en->size == 0xFFFFFFFFu ||
                          local == 0xFFFFFFFFu || rd16(c + 34) == 0xFFFFu;
        en->local_offset = (uint64_t)local + shift;
        pos += rec;
    }
    free(dir);
    if (err != ZIP_OK) {
        free(entries);
        free(names);
        return err;
    }
    memset(z, 0, sizeof(*z));
    z->src = *src;
    z->entries = entries;
    z->count = n_total;
    z->names = names;
    return ZIP_OK;
}

int zip_open(ZipArchive *z, const ZipSource *src)
{
    memset(z, 0, sizeof(*z));
    if (!src || !src->read) return ZIP_ERR_READ;
    if (src->size < END_SIZE) return ZIP_ERR_FORMAT;

    /* The end record is at the very end, unless an archive comment (at most
       65535 bytes) follows it. */
    size_t tail_size = src->size < (uint64_t)END_SIZE + MAX_COMMENT ? (size_t)src->size : END_SIZE + MAX_COMMENT;
    uint64_t tail_at = src->size - tail_size;
    uint8_t *tail = (uint8_t *)malloc(tail_size);
    if (!tail) return ZIP_ERR_NOMEM;
    if (!src->read(src->ctx, tail_at, tail, tail_size)) {
        free(tail);
        return ZIP_ERR_READ;
    }
    /* Search backwards, first for a record whose comment ends exactly at the
       end of the file, then for any (some writers leave bytes after the
       archive); the first one whose directory checks out wins. The comment
       itself could contain the signature. */
    int err = ZIP_ERR_FORMAT;
    for (int pass = 0; pass < 2 && err == ZIP_ERR_FORMAT; pass++) {
        for (size_t i = tail_size - END_SIZE + 1; i-- > 0;) {
            if (rd32(tail + i) != SIG_END) continue;
            int exact = i + END_SIZE + rd16(tail + i + 20) == tail_size;
            if (exact != (pass == 0)) continue;
            int r = read_directory(z, src, tail + i, tail_at + i);
            if (r == ZIP_ERR_FORMAT) continue;
            err = r;   /* found: usable, or a real record of an unsupported kind */
            break;
        }
    }
    free(tail);
    return err;
}

static int lower_ascii(int c)
{
    return c >= 'A' && c <= 'Z' ? c + ('a' - 'A') : c;
}

/* The name ends in .ngc, .ngp or .npc (any case). */
static int has_rom_name(const ZipEntry *e)
{
    if (e->name_len < 4) return 0;
    const char *x = e->name + e->name_len - 4;
    if (x[0] != '.' || lower_ascii(x[1]) != 'n') return 0;
    int b = lower_ascii(x[2]), c = lower_ascii(x[3]);
    return (b == 'g' && (c == 'c' || c == 'p')) || (b == 'p' && c == 'c');
}

int zip_choose_rom(const ZipArchive *z, uint32_t known_crc, uint32_t known_size, int *by_name)
{
    int named = 0;
    for (int i = 0; i < z->count; i++)
        if (!z->entries[i].is_dir && has_rom_name(&z->entries[i])) named = 1;
    int best = -1;
    for (int i = 0; i < z->count; i++) {
        const ZipEntry *e = &z->entries[i];
        if (e->is_dir || (named && !has_rom_name(e))) continue;
        if (!e->needs_zip64 && e->crc32 == known_crc && e->size == known_size) {
            best = i;
            break;
        }
        if (best < 0 || e->size > z->entries[best].size) best = i;
    }
    if (by_name) *by_name = named;
    return best;
}

int zip_extract(const ZipArchive *z, int index, size_t max_size, uint8_t **out, size_t *out_size)
{
    *out = NULL;
    *out_size = 0;
    if (index < 0 || index >= z->count) return ZIP_ERR_EMPTY;
    const ZipEntry *e = &z->entries[index];
    const ZipSource *src = &z->src;
    if (e->needs_zip64) return ZIP_ERR_ZIP64;
    if ((e->flags & FLAGS_ENCRYPTED) || e->method == METHOD_AES) return ZIP_ERR_ENCRYPTED;
    if (e->method != 0 && e->method != 8) return ZIP_ERR_METHOD;
    if (e->size > max_size) return ZIP_ERR_TOO_BIG;
    /* Stored data is the file itself. Deflate data is never much larger
       than what it unpacks to, so a far larger size means damage. */
    if (e->method == 0 ? e->comp_size != e->size : (uint64_t)e->comp_size > (uint64_t)e->size * 2 + 65536)
        return ZIP_ERR_CORRUPT;

    uint8_t lh[LOCAL_SIZE];
    if (e->local_offset > src->size || src->size - e->local_offset < LOCAL_SIZE) return ZIP_ERR_CORRUPT;
    if (!src->read(src->ctx, e->local_offset, lh, LOCAL_SIZE)) return ZIP_ERR_READ;
    if (rd32(lh) != SIG_LOCAL) return ZIP_ERR_CORRUPT;
    if (rd16(lh + 6) & FLAGS_ENCRYPTED) return ZIP_ERR_ENCRYPTED;
    /* the local header has its own name and extra field lengths */
    uint64_t data_at = e->local_offset + LOCAL_SIZE + rd16(lh + 26) + rd16(lh + 28);
    if (data_at > src->size || src->size - data_at < e->comp_size) return ZIP_ERR_CORRUPT;   /* truncated */

    uint8_t *buf = (uint8_t *)malloc(e->size ? e->size : 1);
    if (!buf) return ZIP_ERR_NOMEM;
    int r = ZIP_OK;
    if (e->method == 0) {
        if (e->size && !src->read(src->ctx, data_at, buf, e->size)) r = ZIP_ERR_READ;
    } else {
        uint8_t *packed = (uint8_t *)malloc(e->comp_size ? e->comp_size : 1);
        if (!packed) r = ZIP_ERR_NOMEM;
        else if (e->comp_size && !src->read(src->ctx, data_at, packed, e->comp_size)) r = ZIP_ERR_READ;
        else r = zip_inflate(packed, e->comp_size, buf, e->size);
        free(packed);
    }
    if (r == ZIP_OK && bps_crc32(0, buf, e->size) != e->crc32) r = ZIP_ERR_CRC;
    if (r != ZIP_OK) {
        free(buf);
        return r;
    }
    *out = buf;
    *out_size = e->size;
    return ZIP_OK;
}

const char *zip_error_string(int err)
{
    switch (err) {
    case ZIP_OK:            return "no error";
    case ZIP_ERR_READ:      return "the zip file cannot be read";
    case ZIP_ERR_FORMAT:    return "the zip file is damaged or incomplete (no valid directory at its end)";
    case ZIP_ERR_SPLIT:     return "the zip file is one part of an archive split into several files";
    case ZIP_ERR_ZIP64:     return "the zip file uses the ZIP64 format, which is not supported";
    case ZIP_ERR_EMPTY:     return "the zip file contains no files";
    case ZIP_ERR_ENCRYPTED: return "the file in the zip is encrypted (password-protected)";
    case ZIP_ERR_METHOD:    return "the file in the zip uses an unsupported compression method";
    case ZIP_ERR_TOO_BIG:   return "the file in the zip is too large";
    case ZIP_ERR_CORRUPT:   return "the file in the zip is damaged (invalid or incomplete data)";
    case ZIP_ERR_CRC:       return "the file in the zip is damaged (CRC32 mismatch)";
    case ZIP_ERR_NOMEM:     return "out of memory";
    default:                return "unknown error";
    }
}

const char *zip_method_name(int method)
{
    static char other[24];
    switch (method) {
    case 0:  return "stored";
    case 1:  return "Shrink";
    case 2: case 3: case 4: case 5: return "Reduce";
    case 6:  return "Implode";
    case 8:  return "Deflate";
    case 9:  return "Deflate64";
    case 10: return "PKWARE DCL Implode";
    case 12: return "BZIP2";
    case 14: return "LZMA";
    case 18: return "IBM TERSE";
    case 19: return "IBM LZ77";
    case 20: case 93: return "Zstandard";
    case 95: return "XZ";
    case 96: return "JPEG";
    case 97: return "WavPack";
    case 98: return "PPMd";
    case 99: return "AES encryption";
    default:
        snprintf(other, sizeof(other), "method %d", method);
        return other;
    }
}
