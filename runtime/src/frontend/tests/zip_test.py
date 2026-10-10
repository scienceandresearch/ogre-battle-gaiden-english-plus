"""The game opened straight from a .zip (zipread.c), through zenobia.exe.

    python runtime/src/frontend/tests/zip_test.py --exe build/zenobia.exe --rom rom/baserom.ngc
        --patch build/ogre_en.bps --english build/ogre_en.ngc --work NEW_DIR

Every zip is made at test time in WORK from the original ROM (nothing from
the game is ever stored in the repository). Checks:
 1. zips that must work, with --selftest (image SHA-1 = the English ROM),
    --write-patched and --unzip: stored and deflate from Python's zipfile;
    raw deflate from zlib at several levels and strategies (also level 0,
    stored blocks inside deflate); another file next to the game, the game
    in a folder with an upper-case extension, no .ngc name (largest file),
    two .ngc/.ngp files (the original is chosen by its CRC32), an archive
    comment and data in front, a data descriptor, UTF-8 and code page 437
    names;
 2. the inflate decoder on data no zlib setting produces: an independent
    deflate encoder below (stored/fixed/dynamic blocks, empty blocks, a
    single one-bit distance code, length 258 as code 284, distance 32768,
    padded code counts, code-length repeats across the literal/distance
    boundary), unpacked with --unzip;
 3. damaged and unsupported zips refused with the right message and exit
    code: bad CRC32, damaged deflate data, truncated file, encrypted flag,
    LZMA and BZIP2 methods, ZIP64 (archive and entry), split archive, empty
    zip, a file too large for a ROM, the 8 MB unpack limit, a zip inside
    the zip, a non-zip named .zip; .7z still refused.
WORK must be a new or empty folder.
"""
import argparse
import hashlib
import heapq
import os
import random
import struct
import subprocess
import sys
import zipfile
import zlib

EXIT_UNREADABLE, EXIT_REFUSED, EXIT_ZIP = 2, 3, 30
Z_FORMAT, Z_SPLIT, Z_ZIP64, Z_EMPTY, Z_ENCRYPTED, Z_METHOD, Z_TOO_BIG, Z_CORRUPT, Z_CRC = range(2, 11)
EXTRACT = 'extract the zip first'


class T:
    passed = failed = 0

    @classmethod
    def check(cls, name, cond, detail=''):
        print('%s %s%s' % ('ok  ' if cond else 'FAIL', name, ('  [%s]' % detail.strip()[-1500:]) if detail and not cond else ''))
        if cond:
            cls.passed += 1
        else:
            cls.failed += 1
        return cond


def run(args):
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    return r.returncode, r.stdout + r.stderr


def sha1(data):
    return hashlib.sha1(data).hexdigest()


# ---------------------------------------------------------------- zip files

def raw_deflate(data, level=6, strategy=zlib.Z_DEFAULT_STRATEGY):
    c = zlib.compressobj(level, zlib.DEFLATED, -15, 8, strategy)
    return c.compress(data) + c.flush()


def build_zip(entries, comment=b'', prefix=b'', descriptor=False, eocd=None):
    """entries: (name bytes, content, method, packed data, flags). Offsets are
    relative to the archive (after prefix), like a zip appended to a stub."""
    out = bytearray(prefix)
    central = bytearray()
    for name, content, method, packed, flags in entries:
        crc = zlib.crc32(content)
        off = len(out) - len(prefix)
        lflags = flags | (8 if descriptor else 0)
        lcrc, lcs, lus = (0, 0, 0) if descriptor else (crc, len(packed), len(content))
        out += struct.pack('<IHHHHHIIIHH', 0x04034B50, 20, lflags, method, 0, 0x2821, lcrc, lcs, lus,
                           len(name), 0) + name + packed
        if descriptor:
            out += struct.pack('<IIII', 0x08074B50, crc, len(packed), len(content))
        central += struct.pack('<IHHHHHHIIIHHHHHII', 0x02014B50, 20, 20, lflags, method, 0, 0x2821, crc,
                               len(packed), len(content), len(name), 0, 0, 0, 0, 0, off) + name
    cd_off = len(out) - len(prefix)
    out += central
    fields = [0, 0, len(entries), len(entries), len(central), cd_off]
    if eocd:
        fields = eocd(fields)
    out += struct.pack('<IHHHHIIH', 0x06054B50, *fields, len(comment)) + comment
    return bytes(out)


def stdlib_zip(path, name, data, method):
    with zipfile.ZipFile(path, 'w', method) as z:
        zi = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
        zi.compress_type = method
        z.writestr(zi, data)


# ------------------------------------- an independent deflate encoder (tests)

LBASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195,
         227, 258]
LEXT = [0] * 8 + [1] * 4 + [2] * 4 + [3] * 4 + [4] * 4 + [5] * 4 + [0]
DBASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073,
         4097, 6145, 8193, 12289, 16385, 24577]
DEXT = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13]
ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]


class Bits:
    def __init__(self):
        self.out, self.acc, self.n = bytearray(), 0, 0

    def put(self, v, n):
        self.acc |= v << self.n
        self.n += n
        while self.n >= 8:
            self.out.append(self.acc & 0xFF)
            self.acc >>= 8
            self.n -= 8

    def code(self, c, length):   # Huffman codes go most significant bit first
        self.put(int(format(c, '0%db' % length)[::-1], 2) if length else 0, length)

    def align(self):
        if self.n:
            self.put(0, 8 - self.n)

    def data(self):
        return bytes(self.out) + (bytes([self.acc]) if self.n else b'')


def canonical(lens):
    count = [0] * 16
    for x in lens:
        count[x] += x > 0
    nxt, c = [0] * 16, 0
    for b in range(1, 16):
        c = (c + count[b - 1]) << 1
        nxt[b] = c
    codes = [0] * len(lens)
    for i, x in enumerate(lens):
        if x:
            codes[i], nxt[x] = nxt[x], nxt[x] + 1
    return codes


def huffman_lengths(freqs, limit):
    syms = [i for i, f in enumerate(freqs) if f]
    lens = [0] * len(freqs)
    if len(syms) == 1:
        lens[syms[0]] = 1          # one symbol: a single one-bit code
    if len(syms) <= 1:
        return lens
    w = {s: freqs[s] for s in syms}
    while True:
        heap = [(w[s], i, [s]) for i, s in enumerate(syms)]
        heapq.heapify(heap)
        depth, k = {s: 0 for s in syms}, len(heap)
        while len(heap) > 1:
            a, b = heapq.heappop(heap), heapq.heappop(heap)
            for s in a[2] + b[2]:
                depth[s] += 1
            k += 1
            heapq.heappush(heap, (a[0] + b[0], k, a[2] + b[2]))
        if max(depth.values()) <= limit:
            for s in syms:
                lens[s] = depth[s]
            return lens
        w = {s: max(1, int(w[s] ** 0.5)) for s in syms}


def lz77(data, maxdist):
    toks, head, i = [], {}, 0
    while i < len(data):
        best = (0, 0)
        if i + 3 <= len(data):
            for j in reversed(head.get(data[i:i + 3], [])[-8:]):
                if i - j > maxdist:
                    continue
                k = 0
                while k < 258 and i + k < len(data) and data[j + k] == data[i + k]:
                    k += 1
                best = max(best, (k, i - j))
        step = best[0] if best[0] >= 3 else 1
        toks.append((i, best if best[0] >= 3 else data[i]))
        for p in range(i, min(i + step, len(data) - 2)):
            head.setdefault(data[p:p + 3], []).append(p)
        i += step
    return toks


def len_code(length, use284):
    if length == 258:
        return (27, 31) if use284 else (28, 0)
    i = max(k for k in range(28) if LBASE[k] <= length)
    return i, length - LBASE[i]


def dist_code(d):
    i = max(k for k in range(30) if DBASE[k] <= d)
    return i, d - DBASE[i]


def put_symbols(bw, toks, llens, dlens, use284):
    lc, dc = canonical(llens), canonical(dlens)
    for _, t in toks:
        if isinstance(t, int):
            bw.code(lc[t], llens[t])
            continue
        c, x = len_code(t[0], use284)
        bw.code(lc[257 + c], llens[257 + c])
        bw.put(x, LEXT[c])
        c, x = dist_code(t[1])
        bw.code(dc[c], dlens[c])
        bw.put(x, DEXT[c])
    bw.code(lc[256], llens[256])


def stored_blocks(bw, raw, last):
    pieces = [raw[i:i + 65535] for i in range(0, len(raw), 65535)] or [b'']
    for k, piece in enumerate(pieces):
        bw.put(int(last and k == len(pieces) - 1), 1)
        bw.put(0, 2)
        bw.align()
        bw.put(len(piece), 16)
        bw.put(len(piece) ^ 0xFFFF, 16)
        for b in piece:
            bw.put(b, 8)


def fixed_block(bw, toks, last, use284):
    bw.put(last, 1)
    bw.put(1, 2)
    put_symbols(bw, toks, [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8, [5] * 30, use284)


def dynamic_block(bw, toks, last, rnd, use284):
    lf, df = [0] * 286, [0] * 30
    for _, t in toks:
        if isinstance(t, int):
            lf[t] += 1
        else:
            lf[257 + len_code(t[0], use284)[0]] += 1
            df[dist_code(t[1])[0]] += 1
    lf[256] += 1
    llens, dlens = huffman_lengths(lf, 15), huffman_lengths(df, 15)
    nlit = max(257, 1 + max(i for i in range(286) if llens[i]))
    ndist = 1 + max([i for i in range(30) if dlens[i]] or [0])
    if rnd.random() < 0.3:          # trailing unused codes are allowed
        nlit, ndist = rnd.randint(nlit, 286), rnd.randint(ndist, 30)
    seq, rle, i = llens[:nlit] + dlens[:ndist], [], 0
    while i < len(seq):              # runs may cross into the distance lengths
        v, run = seq[i], 1
        while i + run < len(seq) and seq[i + run] == v:
            run += 1
        if v == 0 and run >= 3:
            r = min(run, 138)
            rle.append((18, r - 11, 7) if r >= 11 else (17, r - 3, 3))
            i += r
        elif v and run >= 4:
            rle.append((v, 0, 0))
            i, run = i + 1, run - 1
            while run >= 3:
                r = min(run, 6)
                rle.append((16, r - 3, 2))
                i, run = i + r, run - r
        else:
            rle.append((v, 0, 0))
            i += 1
    cf = [0] * 19
    for s, _, _ in rle:
        cf[s] += 1
    if sum(1 for f in cf if f) < 2:   # the code length code must be complete
        cf[1 if rle[0][0] == 0 else 0] += 1
    clens = huffman_lengths(cf, 7)
    nclen = 19
    while nclen > 4 and clens[ORDER[nclen - 1]] == 0 and rnd.random() < 0.9:
        nclen -= 1
    bw.put(last, 1)
    bw.put(2, 2)
    bw.put(nlit - 257, 5)
    bw.put(ndist - 1, 5)
    bw.put(nclen - 4, 4)
    for k in range(nclen):
        bw.put(clens[ORDER[k]], 3)
    cc = canonical(clens)
    for s, x, nb in rle:
        bw.code(cc[s], clens[s])
        bw.put(x, nb)
    put_symbols(bw, toks, llens, dlens, use284)


def own_deflate(data, rnd, kinds=('stored', 'fixed', 'dynamic', 'dynamic')):
    toks = lz77(data, rnd.choice([32768, 4096, 1]) if len(kinds) > 1 else 32768)
    use284 = rnd.random() < 0.5
    cuts = sorted(rnd.sample(range(1, len(toks)), min(3, len(toks) - 1))) if len(toks) > 1 else []
    bounds = [0] + cuts + [len(toks)]
    bw = Bits()
    for b in range(len(bounds) - 1):
        chunk, last = toks[bounds[b]:bounds[b + 1]], int(b == len(bounds) - 2)
        if rnd.random() < 0.2:
            fixed_block(bw, [], 0, use284)      # empty blocks in between
            stored_blocks(bw, b'', 0)
        kind = rnd.choice(kinds)
        if kind == 'stored':
            start = chunk[0][0] if chunk else len(data)
            end = toks[bounds[b + 1]][0] if bounds[b + 1] < len(toks) else len(data)
            stored_blocks(bw, data[start:end], last)
        elif kind == 'fixed':
            fixed_block(bw, chunk, last, use284)
        else:
            dynamic_block(bw, chunk, last, rnd, use284)
    return bw.data()


def payloads(rnd):
    """(label, data, block kinds to use)"""
    half = bytes(rnd.getrandbits(8) for _ in range(32768))
    yield 'distance 32768', half + half[:5000], ('dynamic',)
    yield 'one byte repeated (a single one-bit distance code)', bytes([0x5A]) * 40000, ('dynamic',)
    yield 'empty', b'', ('stored', 'fixed', 'dynamic')
    mixed = ('stored', 'fixed', 'dynamic', 'dynamic')
    yield 'random', bytes(rnd.getrandbits(8) for _ in range(30000)), mixed
    yield 'runs', b''.join(bytes([rnd.getrandbits(8)]) * rnd.randint(1, 700) for _ in range(200)), mixed
    yield 'skewed bytes (long codes)', bytes(int(255 * rnd.random() ** 6) for _ in range(30000)), ('dynamic',)
    words = [bytes(rnd.choice(b'abcdefgh ijk') for _ in range(rnd.randint(1, 8))) for _ in range(40)]
    yield 'text', b' '.join(rnd.choice(words) for _ in range(8000)), mixed
    yield 'text, fixed codes only', b' '.join(rnd.choice(words) for _ in range(3000)), ('fixed',)
    yield 'large stored data (over 65535 bytes)', bytes(rnd.getrandbits(8) for _ in range(70000)), ('stored',)


# ---------------------------------------------------------------- the test

def main():
    ap = argparse.ArgumentParser()
    for a in ('exe', 'rom', 'patch', 'english', 'work'):
        ap.add_argument('--' + a, required=True)
    a = ap.parse_args()
    exe, rom_path, patch, english, work = (os.path.abspath(p) for p in (a.exe, a.rom, a.patch, a.english, a.work))
    if os.path.isdir(work) and os.listdir(work):
        sys.exit('WORK must be a new or empty folder: %s' % work)
    os.makedirs(work, exist_ok=True)
    rom = open(rom_path, 'rb').read()
    en_sha1 = sha1(open(english, 'rb').read())
    rnd = random.Random(1234)
    W = lambda *p: os.path.join(work, *p)          # noqa: E731

    def write(name, data):
        with open(W(name), 'wb') as f:
            f.write(data)
        return W(name)

    def selftest(path):
        return run([exe, '--selftest', path, '--patch', patch, '--frames', '10'])

    print('== 1. zips that work')
    ok_cases = []
    stdlib_zip(W('stored.zip'), 'Ogre Battle.ngc', rom, zipfile.ZIP_STORED)
    ok_cases.append(('zipfile, stored', W('stored.zip'), 'Ogre Battle.ngc'))
    stdlib_zip(W('deflate.zip'), 'Ogre Battle.ngc', rom, zipfile.ZIP_DEFLATED)
    ok_cases.append(('zipfile, deflate', W('deflate.zip'), 'Ogre Battle.ngc'))
    for label, level, strategy in (('level 1', 1, 0), ('level 9', 9, 0), ('level 0 (stored blocks)', 0, 0),
                                   ('fixed codes', 6, zlib.Z_FIXED), ('Huffman only', 6, zlib.Z_HUFFMAN_ONLY),
                                   ('run lengths', 6, zlib.Z_RLE), ('filtered', 6, zlib.Z_FILTERED)):
        name = 'zlib_%s.zip' % label.split()[0]
        write(name, build_zip([(b'game.ngc', rom, 8, raw_deflate(rom, level, strategy), 0)]))
        ok_cases.append(('raw deflate, %s' % label, W(name), 'game.ngc'))
    write('with_url.zip', build_zip([(b'CDRomance.url', b'[InternetShortcut]\r\nURL=x\r\n', 0,
                                      b'[InternetShortcut]\r\nURL=x\r\n', 0),
                                     (b'Densetsu no Ogre Battle (Japan).ngc', rom, 8, raw_deflate(rom), 0)]))
    ok_cases.append(('another file next to the game', W('with_url.zip'), 'Densetsu no Ogre Battle (Japan).ngc'))
    write('folder.zip', build_zip([(b'roms/', b'', 0, b'', 0), (b'readme.txt', b'x' * 9000, 0, b'x' * 9000, 0),
                                   (b'roms/Ogre Battle (J).NGC', rom, 8, raw_deflate(rom), 0)]))
    ok_cases.append(('in a folder, upper-case .NGC', W('folder.zip'), 'roms/Ogre Battle (J).NGC'))
    write('noname.zip', build_zip([(b'notes.txt', b'hello', 0, b'hello', 0), (b'game.bin', rom, 8, raw_deflate(rom), 0)]))
    ok_cases.append(('no .ngc name: the largest file', W('noname.zip'), 'game.bin'))
    other = bytes(2500000)
    write('two.zip', build_zip([(b'other.ngp', other, 8, raw_deflate(other), 0),
                                (b'zzz.ngc', rom, 8, raw_deflate(rom), 0)]))
    ok_cases.append(('two ROM names: the original by its CRC32', W('two.zip'), 'zzz.ngc'))
    write('stub.zip', build_zip([(b'game.ngc', rom, 8, raw_deflate(rom), 0)], comment=b'a comment PK\x05\x06 x' * 3,
                                prefix=b'MZ' + bytes(4000)))
    ok_cases.append(('archive comment, data in front', W('stub.zip'), 'game.ngc'))
    write('descriptor.zip', build_zip([(b'game.ngc', rom, 8, raw_deflate(rom), 0)], descriptor=True))
    ok_cases.append(('data descriptor (sizes after the data)', W('descriptor.zip'), 'game.ngc'))
    utf8_name = '\u03a9\u03bc\u03ad\u03b3\u03b1 \u0440\u043e\u043c.ngc'
    write('utf8.zip', build_zip([(utf8_name.encode('utf-8'), rom, 8, raw_deflate(rom), 0x800)]))
    ok_cases.append(('UTF-8 name', W('utf8.zip'), utf8_name))
    write('cp437.zip', build_zip([(b'caf\x82 \x9b.ngc', rom, 0, rom, 0)]))
    ok_cases.append(('code page 437 name', W('cp437.zip'), 'caf\u00e9 \u00a2.ngc'))
    for label, path, entry in ok_cases:
        code, out = selftest(path)
        T.check('%s: runs (exit %d)' % (label, code), code == 0 and 'zip entry %s (' % entry in out
                and 'patch applied' in out and 'image sha1 ' + en_sha1 in out, out)
    code, out = run([exe, W('deflate.zip'), '--patch', patch, '--write-patched', W('written.ngc')])
    T.check('--write-patched from a zip = English ROM (exit %d)' % code,
            code == 0 and os.path.isfile(W('written.ngc')) and sha1(open(W('written.ngc'), 'rb').read()) == en_sha1, out)
    greek = W('\u0444\u0430\u0439\u043b \u03a9')                       # Cyrillic and Greek
    os.makedirs(greek)
    stdlib_zip(os.path.join(greek, '\u0438\u0433\u0440\u0430 \u03a9.zip'), 'game.ngc', rom, zipfile.ZIP_DEFLATED)
    out_ngc = os.path.join(greek, '\u03b1\u03b3\u03b3\u03bb\u03b9\u03ba\u03ac.ngc')
    code, out = run([exe, os.path.join(greek, '\u0438\u0433\u0440\u0430 \u03a9.zip'), '--patch', patch,
                     '--write-patched', out_ngc])
    T.check('non-ASCII folder and names: zip read, English ROM written (exit %d)' % code,
            code == 0 and os.path.isfile(out_ngc) and sha1(open(out_ngc, 'rb').read()) == en_sha1, out)
    for path in (W('deflate.zip'), W('descriptor.zip'), W('two.zip')):
        if os.path.exists(W('unzipped.ngc')):
            os.remove(W('unzipped.ngc'))
        code, out = run([exe, '--unzip', path, W('unzipped.ngc')])
        T.check('--unzip %s = the ROM (exit %d)' % (os.path.basename(path), code),
                code == 0 and open(W('unzipped.ngc'), 'rb').read() == rom, out)

    print('== 2. the inflate decoder on data from an independent encoder')
    for label, data, kinds in payloads(rnd):
        packed = own_deflate(data, rnd, kinds)
        ref = zlib.decompressobj(-15)
        good = ref.decompress(packed) + ref.flush() == data and ref.eof
        path = write('own.zip', build_zip([(b'data.ngc', data, 8, packed, 0)]))
        out_path = W('own.out')
        if os.path.exists(out_path):
            os.remove(out_path)
        code, out = run([exe, '--unzip', path, out_path])
        T.check('%s: %d bytes from %d (exit %d)' % (label, len(data), len(packed), code),
                good and code == 0 and open(out_path, 'rb').read() == data, out)

    print('== 3. damaged and unsupported zips')
    base = build_zip([(b'game.ngc', rom, 8, raw_deflate(rom), 0)])
    cd = base.rindex(b'PK\x01\x02')

    def patched(data, offset, fmt, value):
        b = bytearray(data)
        struct.pack_into(fmt, b, offset, value)
        return bytes(b)

    lzma = patched(patched(base, 8, '<H', 14), cd + 10, '<H', 14)
    bzip = patched(patched(base, 8, '<H', 12), cd + 10, '<H', 12)
    enc = patched(patched(base, 6, '<H', 1), cd + 8, '<H', 1)
    bad_crc = patched(base, cd + 16, '<I', zlib.crc32(rom) ^ 0x1234)
    mid = 30 + len(b'game.ngc') + 300000
    damaged = base[:mid] + bytes([base[mid] ^ 0x55]) + base[mid + 1:]
    # ZIP64: end record fields saturated, with the ZIP64 end record and locator in front of it
    z64_end = struct.pack('<IQHHIIQQQQ', 0x06064B50, 44, 45, 45, 0, 0, 1, 1, len(base) - cd - 22, cd)
    z64 = base[:-22] + z64_end + struct.pack('<IIQI', 0x07064B50, 0, len(base) - 22, 1) + \
        struct.pack('<IHHHHIIH', 0x06054B50, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0)
    z64_entry = patched(patched(base, cd + 20, '<I', 0xFFFFFFFF), cd + 24, '<I', 0xFFFFFFFF)
    split = build_zip([(b'game.ngc', rom, 8, raw_deflate(rom), 0)], eocd=lambda f: [1, 1] + f[2:])
    inner = build_zip([(b'game.ngc', rom, 0, rom, 0)])
    refused = [
        ('bad CRC32', bad_crc, 'checksum (CRC32)', Z_CRC),
        ('damaged deflate data', damaged, 'is damaged', None),
        ('truncated download (end missing)', base[:len(base) // 2], 'damaged or incomplete', Z_FORMAT),
        ('encrypted flag', enc, 'protected by a password', Z_ENCRYPTED),
        ('LZMA method', lzma, '(LZMA)', Z_METHOD),
        ('BZIP2 method', bzip, '(BZIP2)', Z_METHOD),
        ('ZIP64 archive', z64, 'ZIP64', Z_ZIP64),
        ('ZIP64 entry', z64_entry, 'ZIP64', Z_ZIP64),
        ('split archive', split, 'split into several files', Z_SPLIT),
        ('empty zip', build_zip([]), 'contains no files', Z_EMPTY),
        ('only a folder', build_zip([(b'roms/', b'', 0, b'', 0)]), 'contains no files', Z_EMPTY),
    ]
    for label, data, text, zcode in refused:
        path = write('bad.zip', data)
        code, out = selftest(path)
        needs_extract = zcode in (Z_ENCRYPTED, Z_METHOD, Z_ZIP64)
        T.check('%s: refused (exit %d) with the reason' % (label, code),
                code == EXIT_UNREADABLE and text in out
                and (not needs_extract or (EXTRACT in out and 'Extract All' in out)), out)
        if zcode is not None:
            code, out = run([exe, '--unzip', path, W('never.out')])
            T.check('  --unzip exit %d = %d' % (code, EXIT_ZIP + zcode),
                    code == EXIT_ZIP + zcode and not os.path.exists(W('never.out')), out)
    big = bytes(5 * 1024 * 1024)
    code, out = selftest(write('big.zip', build_zip([(b'game.ngc', big, 8, raw_deflate(big), 0)])))
    T.check('a 5 MB file in the zip: too large for a ROM (exit %d), not unpacked' % code,
            code == EXIT_UNREADABLE and 'too large for a Neo Geo Pocket ROM: 5242880 bytes' in out, out)
    limit = 8 * 1024 * 1024
    for size, want in ((limit, 0), (limit + 1, EXIT_ZIP + Z_TOO_BIG)):
        data = bytes(size)
        path = write('limit.zip', build_zip([(b'data.bin', data, 8, raw_deflate(data), 0)]))
        code, out = run([exe, '--unzip', path, W('limit.out')])
        T.check('--unzip of %d bytes: exit %d (limit 8 MB)' % (size, code), code == want, out)
        if os.path.exists(W('limit.out')):
            os.remove(W('limit.out'))
    code, out = run([exe, write('enc2.zip', enc), '--patch', patch, '--write-patched', W('never.ngc')])
    T.check('--write-patched refuses an encrypted zip (exit %d), nothing written' % code,
            code == EXIT_UNREADABLE and not os.path.exists(W('never.ngc')) and 'nothing written' in out, out)
    code, out = selftest(write('nested.zip', build_zip([(b'game.zip', inner, 0, inner, 0)])))
    T.check('a zip inside the zip: refused (exit %d)' % code,
            code == EXIT_REFUSED and 'itself a compressed archive' in out, out)
    code, out = selftest(write('notzip.zip', b'hello' * 100))
    T.check('not a zip but named .zip: explained (exit %d)' % code,
            code == 0 and 'named like a zip file' in out and 'not a ROM the patch knows' in out, out)
    code, out = selftest(write('game.7z', b'7z\xbc\xaf\x27\x1c' + bytes(200)))
    T.check('.7z still refused (exit %d), told to extract it' % code,
            code == EXIT_REFUSED and 'compressed archive (.7z, .rar or .gz)' in out and 'Extract' in out, out)

    print('passed %d, failed %d' % (T.passed, T.failed))
    return 1 if T.failed else 0


if __name__ == '__main__':
    sys.exit(main())
