"""Minimal dependency-free PNG reader/writer (8-bit, non-interlaced).

Images are represented as (width, height, pixels) where pixels is a list of
rows, each row a list of (r, g, b) or (r, g, b, a) tuples, or palette indices
when a palette is used.
"""
import struct
import zlib


def _chunk(tag, data):
    c = struct.pack('>I', len(data)) + tag + data
    return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_rgb(path, width, height, rows, scale=1):
    """rows: list of rows of (r, g, b) tuples."""
    raw = bytearray()
    for y in range(height * scale):
        raw.append(0)
        row = rows[y // scale]
        for x in range(width * scale):
            r, g, b = row[x // scale][:3]
            raw += bytes((r, g, b))
    data = b'\x89PNG\r\n\x1a\n'
    data += _chunk(b'IHDR', struct.pack('>IIBBBBB', width * scale, height * scale, 8, 2, 0, 0, 0))
    data += _chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    data += _chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(data)


def write_indexed(path, width, height, rows, palette):
    """rows: list of rows of palette indices; palette: list of (r, g, b)."""
    raw = bytearray()
    for row in rows:
        raw.append(0)
        raw += bytes(row)
    plte = b''.join(bytes(c[:3]) for c in palette)
    data = b'\x89PNG\r\n\x1a\n'
    data += _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 3, 0, 0, 0))
    data += _chunk(b'PLTE', plte)
    data += _chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    data += _chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(data)


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read(path):
    """Returns (width, height, rows, palette). Rows contain palette indices for
    indexed images, else (r, g, b, a) tuples."""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG file')
    pos = 8
    idat = b''
    palette = None
    trns = None
    width = height = depth = ctype = interlace = None
    while pos < len(data):
        (length,) = struct.unpack('>I', data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if tag == b'IHDR':
            width, height, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', body)
        elif tag == b'PLTE':
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif tag == b'tRNS':
            trns = body
        elif tag == b'IDAT':
            idat += body
        elif tag == b'IEND':
            break
    if interlace:
        raise ValueError('interlaced PNG not supported')
    if depth != 8 and not (ctype == 3 and depth in (1, 2, 4)):
        raise ValueError('unsupported bit depth %d' % depth)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = max(1, channels * depth // 8)
    stride = (width * channels * depth + 7) // 8
    raw = zlib.decompress(idat)
    rows = []
    prev = bytearray(stride)
    i = 0
    for _ in range(height):
        ft = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if ft == 1:
                line[x] = (line[x] + a) & 0xFF
            elif ft == 2:
                line[x] = (line[x] + b) & 0xFF
            elif ft == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 0xFF
            elif ft == 4:
                line[x] = (line[x] + _paeth(a, b, c)) & 0xFF
        prev = line
        row = []
        if ctype == 3:
            if depth == 8:
                row = list(line[:width])
            else:
                per = 8 // depth
                mask = (1 << depth) - 1
                for x in range(width):
                    byte = line[x // per]
                    shift = 8 - depth * (x % per + 1)
                    row.append((byte >> shift) & mask)
        else:
            for x in range(width):
                px = line[x * channels:(x + 1) * channels]
                if ctype == 0:
                    row.append((px[0], px[0], px[0], 255))
                elif ctype == 2:
                    row.append((px[0], px[1], px[2], 255))
                elif ctype == 4:
                    row.append((px[0], px[0], px[0], px[1]))
                else:
                    row.append((px[0], px[1], px[2], px[3]))
        rows.append(row)
    return width, height, rows, palette
