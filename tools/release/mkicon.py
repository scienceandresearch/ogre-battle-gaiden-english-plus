"""Turn the text-art icon source into a Windows icon (.ico).

    python tools/release/mkicon.py SOURCE.txt OUT.ico [--preview PREVIEW.png]
    python -m tools.release.mkicon SOURCE.txt OUT.ico [--preview PREVIEW.png]

SOURCE is a text-art file such as assets/icon/zenobia.txt (the format is
described at the top of that file): `@chars` lines give each character a
colour (#RRGGBB, #RRGGBBAA or none), each `@size W H` + `@data` block is one
image of H rows of W characters, and `@scale FROM to TO` also stores the
FROM-pixel image enlarged to TO pixels without smoothing.

The .ico holds every drawn image as a 32-bit BGRA bitmap with its AND mask
(the classic format every Windows version reads) and every scaled image as a
PNG (the format Windows uses for large icons). Output is deterministic and is
written through a temporary file, so a failed run never leaves a partial
icon. --preview writes a PNG with all images side by side, for review.

Standard library only: CMakeLists.txt runs this script while it builds
zenobia.exe (the icon resource); without Python the player is built without
an icon. Exit code 0 on success, 1 on any error in the source.
"""
import os
import re
import struct
import sys
import zlib

MAX_SIZE = 256                       # largest icon a Windows .ico entry can hold
PNG_FROM = 64                        # images this big or bigger are stored as PNG


class IconError(Exception):
    pass


class Image:
    def __init__(self, width, height, pixels, line):
        self.width = width
        self.height = height
        self.pixels = pixels             # rows of (r, g, b, a) tuples, top row first
        self.line = line

    def scaled(self, factor):
        rows = []
        for row in self.pixels:
            wide = [p for p in row for _ in range(factor)]
            rows.extend([wide] * factor)
        return Image(self.width * factor, self.height * factor, rows, self.line)

    def rgba(self):
        return b''.join(bytes(p) for row in self.pixels for p in row)


_COMMENT = re.compile(r'\s+#(\s.*)?$')
_CHARS = re.compile(r'(\S)\s*=\s*(\S+)')


def parse_colour(text, where):
    if text.lower() == 'none':
        return (0, 0, 0, 0)
    m = re.fullmatch(r'#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?', text)
    if not m:
        raise IconError('%s: colour %r is not #RRGGBB, #RRGGBBAA or none' % (where, text))
    v = bytes.fromhex(m.group(1) + (m.group(2) or 'FF'))
    return tuple(v)


def parse(text, name='<icon>'):
    """Return (images, scales): the drawn images in file order and the list
    of (from, to, line) scale requests."""
    colours = {}
    images, scales = [], []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        where = '%s:%d' % (name, i)
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        s = _COMMENT.sub('', s)
        if s.startswith('@chars'):
            rest = s[len('@chars'):].strip()
            pairs = _CHARS.findall(rest)
            if not pairs or _CHARS.sub('', rest).strip():
                raise IconError('%s: expected "@chars C = COLOUR ..."' % where)
            for ch, value in pairs:
                if ch in colours:
                    raise IconError('%s: character %r is defined twice' % (where, ch))
                colours[ch] = parse_colour(value, where)
        elif s.startswith('@size'):
            m = re.fullmatch(r'@size\s+(\d+)\s+(\d+)', s)
            if not m:
                raise IconError('%s: expected "@size W H"' % where)
            w, h = int(m.group(1)), int(m.group(2))
            if w != h or not 1 <= w <= MAX_SIZE:
                raise IconError('%s: icon images are square, 1 to %d pixels (got %dx%d)' % (where, MAX_SIZE, w, h))
            if any(im.width == w for im in images):
                raise IconError('%s: a %dx%d image is drawn twice' % (where, w, h))
            while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith('#')):
                i += 1
            if i >= len(lines) or _COMMENT.sub('', lines[i].strip()) != '@data':
                raise IconError('%s: "@size" must be followed by "@data"' % where)
            i += 1
            rows = []
            while len(rows) < h:
                if i >= len(lines):
                    raise IconError('%s: the %dx%d image has only %d of %d rows' % (where, w, h, len(rows), h))
                row = lines[i].rstrip('\r\n').rstrip()
                i += 1
                rw = '%s:%d' % (name, i)
                if len(row) != w:
                    raise IconError('%s: row of %d characters, the image is %d wide' % (rw, len(row), w))
                out = []
                for ch in row:
                    if ch not in colours:
                        raise IconError('%s: character %r has no colour (add it to @chars)' % (rw, ch))
                    out.append(colours[ch])
                rows.append(out)
            images.append(Image(w, h, rows, where))
        elif s.startswith('@scale'):
            m = re.fullmatch(r'@scale\s+(\d+)\s+to\s+(\d+)', s)
            if not m:
                raise IconError('%s: expected "@scale FROM to TO"' % where)
            scales.append((int(m.group(1)), int(m.group(2)), where))
        elif s.startswith('@data'):
            raise IconError('%s: "@data" without "@size"' % where)
        else:
            raise IconError('%s: unexpected line %r' % (where, raw.strip()[:40]))
    if not images:
        raise IconError('%s: no image (@size ... @data)' % name)
    return images, scales


def build_images(images, scales):
    """All images of the icon, drawn and scaled, sorted by size."""
    by_size = {im.width: im for im in images}
    out = dict(by_size)
    for src, dst, where in scales:
        if src not in by_size:
            raise IconError('%s: there is no drawn %dx%d image to scale' % (where, src, src))
        if dst % src or dst <= src or dst > MAX_SIZE:
            raise IconError('%s: %d is not a whole multiple of %d up to %d' % (where, dst, src, MAX_SIZE))
        if dst in out:
            raise IconError('%s: the icon already has a %dx%d image' % (where, dst, dst))
        out[dst] = by_size[src].scaled(dst // src)
    return [out[k] for k in sorted(out)]


def png_bytes(width, height, rgba):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    stride = width * 4
    raw = b''.join(b'\x00' + rgba[y * stride:(y + 1) * stride] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))


def dib_bytes(im):
    """BITMAPINFOHEADER + 32-bit BGRA rows (bottom-up) + 1-bit AND mask."""
    w, h = im.width, im.height
    mask_stride = ((w + 31) // 32) * 4
    xor = bytearray()
    mask = bytearray()
    for row in reversed(im.pixels):
        for r, g, b, a in row:
            xor += bytes((b, g, r, a))
        bits = bytearray(mask_stride)
        for x, (_, _, _, a) in enumerate(row):
            if a == 0:
                bits[x >> 3] |= 0x80 >> (x & 7)
        mask += bits
    header = struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, 32, 0, len(xor) + len(mask), 0, 0, 0, 0)
    return header + bytes(xor) + bytes(mask)


def ico_bytes(images):
    blobs = []
    for im in images:
        if im.width >= PNG_FROM:
            blobs.append(png_bytes(im.width, im.height, im.rgba()))
        else:
            blobs.append(dib_bytes(im))
    out = bytearray(struct.pack('<HHH', 0, 1, len(images)))
    offset = 6 + 16 * len(images)
    for im, blob in zip(images, blobs):
        dim = im.width if im.width < 256 else 0
        out += struct.pack('<BBBBHHII', dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    for blob in blobs:
        out += blob
    return bytes(out)


def preview_bytes(images, background=(0xF0, 0xF0, 0xF0)):
    pad = 8
    width = sum(im.width + pad for im in images) + pad
    height = max(im.height for im in images) + 2 * pad
    canvas = bytearray(bytes(background) + b'\xff') * (width * height)
    x0 = pad
    for im in images:
        for y, row in enumerate(im.pixels):
            for x, (r, g, b, a) in enumerate(row):
                o = ((pad + y) * width + x0 + x) * 4
                br, bg, bb = canvas[o:o + 3]
                canvas[o:o + 4] = bytes(((r * a + br * (255 - a)) // 255, (g * a + bg * (255 - a)) // 255,
                                         (b * a + bb * (255 - a)) // 255, 255))
        x0 += im.width + pad
    return png_bytes(width, height, bytes(canvas))


def write_file(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)


def convert(source, out, preview=None):
    with open(source, encoding='utf-8') as f:
        text = f.read()
    images = build_images(*parse(text, source))
    data = ico_bytes(images)
    write_file(out, data)
    if preview:
        write_file(preview, preview_bytes(images))
    return images, data


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    preview = None
    if '--preview' in args:
        k = args.index('--preview')
        if k + 1 >= len(args):
            print(__doc__, file=sys.stderr)
            return 1
        preview = args[k + 1]
        del args[k:k + 2]
    if len(args) != 2 or args[0].startswith('-'):
        print(__doc__, file=sys.stderr)
        return 1
    try:
        images, data = convert(args[0], args[1], preview)
    except IconError as e:
        print('mkicon: error: %s' % e, file=sys.stderr)
        return 1
    except OSError as e:
        print('mkicon: error: %s' % e, file=sys.stderr)
        return 1
    print('mkicon: %s -> %s (%s; %d bytes)' % (
        args[0], args[1], ', '.join('%d' % im.width for im in images), len(data)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
