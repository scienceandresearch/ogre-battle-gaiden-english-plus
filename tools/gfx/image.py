"""Indexed bitmaps, text-art images and PNG import/export.

Bitmap
    Bitmap(w, h, px) holds w x h pixels in a flat row-major list px (a list of
    rows is accepted too). A pixel is 0 (transparent) or 4 * slot + colour,
    where colour is 1-3 and slot is the layer's palette slot (for a text-art
    file: the palette's position in the file).
    get/set, row/rows, copy, crop(x, y, w, h), paste(src, x, y) (every pixel),
    blit(src, x, y) (non-zero pixels only), bbox(), values().

Text-art files (assets/gfx/<target>/*.txt, UTF-8):

    # comment
    @size 160 48
    @palette fire  plane1 0  #FFE040 #FF6020 #A01000
    @palette sub   plane2 5  #C08030 #FFD060 keep
    @chars . = 0   Y = fire.1   O = fire.2   R = fire.3
    @chars B = sub.1   A = sub.2   K = sub.3
    @data
    ....YYYY....        (exactly H rows of W characters)

* @size W H is required.
* @palette NAME PLANE N C1 C2 C3: PLANE is plane1, plane2 or sprite, N the
  hardware palette (0-15), and each colour is '#RRGGBB' (our own value) or
  'keep' (the build keeps the ROM's value). The palette's position in the
  file is its slot.
* @chars (one or more lines) maps single characters to 0 (transparent),
  NAME.K (colour K = 1-3 of palette NAME, pixel 4 * slot + K), or a plain
  pixel number.
* The H lines after @data are the rows, taken literally (no comments inside;
  trailing spaces are ignored). Only blank lines and comments may follow.

PNG and colours
    save_png(path, bitmap, rgb=None, scale=1)     preview; rgb maps pixel -> (r, g, b)
    preview_rgb(palettes, transparent, keep)      rgb table of a text-art image
    import_png(path, palettes, ...) -> Bitmap     exact colours only
    rgb_to_ngp((r, g, b)) -> 0x0BGR word          round(v * 15 / 255) per channel
    ngp_to_rgb(word) -> (r, g, b)                 v4 * 17

Command line (PNG is only an import and preview format; never commit PNGs):
    python -m tools.gfx.image import IN.png OUT.txt --like SPEC.txt [--keep NAME.K=#RRGGBB ...]
    python -m tools.gfx.image export IN.txt OUT.png [--scale N] [--keep NAME.K=#RRGGBB ...]
"""
import argparse
import os
import sys
from collections import namedtuple

from ..common import png

TRANSPARENT = (255, 0, 255)          # transparent pixels in imported and preview PNGs
PLANES = ('plane1', 'plane2', 'sprite')
DEFAULT_PREVIEW = {0: TRANSPARENT, 1: (255, 255, 255), 2: (160, 160, 160), 3: (40, 40, 40)}


class ImageError(ValueError):
    """An image that cannot be converted (unknown colour, mixed palettes...)."""


class TextArtError(ImageError):
    """A malformed text-art file."""


# ---------------------------------------------------------------------------
# Bitmap

class Bitmap:
    __slots__ = ('w', 'h', 'px')

    def __init__(self, w, h, px=None):
        if w < 0 or h < 0:
            raise ValueError('bad bitmap size %dx%d' % (w, h))
        if px is None:
            px = [0] * (w * h)
        else:
            px = list(px)
            if px and not isinstance(px[0], int):            # a list of rows
                if len(px) != h or any(len(r) != w for r in px):
                    raise ValueError('expected %d rows of %d pixels' % (h, w))
                px = [v for r in px for v in r]
            elif len(px) != w * h:
                raise ValueError('expected %d pixels for %dx%d, got %d' % (w * h, w, h, len(px)))
        self.w, self.h, self.px = w, h, px

    @classmethod
    def from_rows(cls, rows):
        rows = [list(r) for r in rows]
        return cls(len(rows[0]) if rows else 0, len(rows), rows)

    def get(self, x, y):
        return self.px[y * self.w + x]

    def set(self, x, y, v):
        self.px[y * self.w + x] = v

    def row(self, y):
        return self.px[y * self.w:(y + 1) * self.w]

    def rows(self):
        return [self.row(y) for y in range(self.h)]

    def copy(self):
        return Bitmap(self.w, self.h, self.px[:])

    def crop(self, x, y, w, h):
        """A w x h piece from (x, y); parts outside this bitmap are 0."""
        out = Bitmap(w, h)
        out.paste(self, -x, -y)
        return out

    def paste(self, src, x, y):
        """Copy every pixel of src (zeros included) to (x, y), clipped."""
        self._copy(src, x, y, True)

    def blit(self, src, x, y):
        """Copy the non-zero pixels of src to (x, y), clipped."""
        self._copy(src, x, y, False)

    def _copy(self, src, x, y, opaque):
        x0, x1 = max(0, x), min(self.w, x + src.w)
        y0, y1 = max(0, y), min(self.h, y + src.h)
        n = x1 - x0
        if n <= 0 or y0 >= y1:
            return
        for yy in range(y0, y1):
            so = (yy - y) * src.w + (x0 - x)
            do = yy * self.w + x0
            if opaque:
                self.px[do:do + n] = src.px[so:so + n]
            else:
                for i in range(n):
                    v = src.px[so + i]
                    if v:
                        self.px[do + i] = v

    def bbox(self):
        """(x0, y0, x1, y1) of the non-zero pixels, end exclusive; None if empty."""
        xs, ys = [], []
        for i, v in enumerate(self.px):
            if v:
                y, x = divmod(i, self.w)
                xs.append(x)
                ys.append(y)
        if not xs:
            return None
        return min(xs), min(ys), max(xs) + 1, max(ys) + 1

    def values(self):
        return set(self.px)

    def __eq__(self, other):
        return isinstance(other, Bitmap) and (self.w, self.h, self.px) == (other.w, other.h, other.px)

    __hash__ = None

    def __repr__(self):
        return '<Bitmap %dx%d>' % (self.w, self.h)


# ---------------------------------------------------------------------------
# Colours

def parse_rgb(text):
    """'#RRGGBB' (or 'RRGGBB') -> (r, g, b)."""
    s = text[1:] if text.startswith('#') else text
    if len(s) != 6 or any(c not in '0123456789abcdefABCDEF' for c in s):
        raise ValueError('not a #RRGGBB colour: %r' % text)
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def format_rgb(rgb):
    return '#%02X%02X%02X' % tuple(rgb[:3])


def rgb_to_ngp(rgb):
    """(r, g, b) or '#RRGGBB' -> K2GE colour word 0x0BGR, round(v * 15 / 255) per channel."""
    if isinstance(rgb, str):
        rgb = parse_rgb(rgb)
    r, g, b = (round(v * 15 / 255) for v in rgb[:3])
    return (b << 8) | (g << 4) | r


def ngp_to_rgb(word):
    """K2GE colour word 0x0BGR -> (r, g, b), v4 * 17 per channel."""
    return (word & 0xF) * 17, ((word >> 4) & 0xF) * 17, ((word >> 8) & 0xF) * 17


def keep_placeholder(value):
    """Preview colour of a 'keep' entry without an override (distinct per pixel value)."""
    return 0, 255, 255 - value


# ---------------------------------------------------------------------------
# Text-art images

class PaletteBinding(namedtuple('PaletteBinding', 'name plane number colors')):
    """One @palette line. colors: 3 entries, (r, g, b) or None for 'keep'."""
    __slots__ = ()

    def words(self):
        """The 3 colour words (None for 'keep')."""
        return [None if c is None else rgb_to_ngp(c) for c in self.colors]


TextArt = namedtuple('TextArt', 'bitmap palettes chars')      # chars: character -> pixel


def _uint(s):
    return s.isascii() and s.isdigit()


def _value(token, names, where):
    if _uint(token):
        v = int(token)
        if v and not v & 3:
            raise TextArtError('%s: pixel %d has colour 0 (use 0 for transparent)' % (where, v))
        return v
    name, dot, k = token.rpartition('.')
    if not dot or name not in names or k not in ('1', '2', '3'):
        raise TextArtError('%s: bad pixel %r (use 0, NAME.1-3 with a declared palette, or a number)'
                           % (where, token))
    return 4 * names[name] + int(k)


def parse_textart(text, source='<text>'):
    """Parse text-art source; returns TextArt(bitmap, palettes, chars)."""
    lines = text.splitlines()
    size = None
    palettes, names, hw = [], {}, set()
    specs = []
    data_at = None
    for i, raw in enumerate(lines):
        n = i + 1
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        where = '%s:%d' % (source, n)
        parts = line.split()
        key = parts[0]
        if key == '@size':
            if size is not None:
                raise TextArtError('%s: @size given twice' % where)
            if len(parts) != 3 or not _uint(parts[1]) or not _uint(parts[2]) \
                    or int(parts[1]) < 1 or int(parts[2]) < 1:
                raise TextArtError('%s: expected @size W H' % where)
            size = int(parts[1]), int(parts[2])
        elif key == '@palette':
            if len(parts) != 7:
                raise TextArtError('%s: expected @palette NAME PLANE N C1 C2 C3' % where)
            name, plane, num = parts[1:4]
            if name in names or '.' in name:
                raise TextArtError('%s: bad or repeated palette name %r' % (where, name))
            if plane not in PLANES:
                raise TextArtError('%s: plane must be one of %s, not %r' % (where, ', '.join(PLANES), plane))
            if not _uint(num) or int(num) > 15:
                raise TextArtError('%s: palette number must be 0-15, not %r' % (where, num))
            if (plane, int(num)) in hw:
                raise TextArtError('%s: %s palette %s is declared twice' % (where, plane, num))
            colors = []
            for tok in parts[4:]:
                if tok == 'keep':
                    colors.append(None)
                elif tok.startswith('#') and len(tok) == 7:
                    try:
                        colors.append(parse_rgb(tok))
                    except ValueError:
                        raise TextArtError("%s: colour must be '#RRGGBB' or 'keep', not %r" % (where, tok))
                else:
                    raise TextArtError("%s: colour must be '#RRGGBB' or 'keep', not %r" % (where, tok))
            names[name] = len(palettes)
            hw.add((plane, int(num)))
            palettes.append(PaletteBinding(name, plane, int(num), tuple(colors)))
        elif key == '@chars':
            toks = parts[1:]
            if not toks or len(toks) % 3 or any(toks[k + 1] != '=' for k in range(0, len(toks), 3)):
                raise TextArtError('%s: expected @chars C = VALUE [C = VALUE ...]' % where)
            for k in range(0, len(toks), 3):
                if len(toks[k]) != 1:
                    raise TextArtError('%s: %r is not a single character' % (where, toks[k]))
                specs.append((toks[k], toks[k + 2], where))
        elif key == '@data':
            data_at = n
            break
        else:
            raise TextArtError('%s: unknown line %r (expected @size, @palette, @chars or @data)'
                               % (where, line))
    if size is None:
        raise TextArtError('%s: no @size line' % source)
    if data_at is None:
        raise TextArtError('%s: no @data line' % source)
    chars = {}
    for ch, tok, where in specs:
        if ch in chars:
            raise TextArtError('%s: character %r is mapped twice' % (where, ch))
        chars[ch] = _value(tok, names, where)
    w, h = size
    rows = lines[data_at:data_at + h]
    if len(rows) < h:
        raise TextArtError('%s: wrong size: %d data rows, @size says %d' % (source, len(rows), h))
    px = []
    for r, raw in enumerate(rows):
        row = raw.rstrip()
        n = data_at + 1 + r
        if len(row) != w:
            raise TextArtError('%s:%d: wrong size: data row %d has %d characters, @size says %d'
                               % (source, n, r, len(row), w))
        for x, ch in enumerate(row):
            v = chars.get(ch)
            if v is None:
                raise TextArtError('%s:%d: unknown character %r at x %d, y %d (not in @chars)'
                                   % (source, n, ch, x, r))
            px.append(v)
    for k in range(data_at + h, len(lines)):
        s = lines[k].strip()
        if s and not s.startswith('#'):
            raise TextArtError('%s:%d: wrong size: more than %d data rows' % (source, k + 1, h))
    return TextArt(Bitmap(w, h, px), palettes, chars)


def load_textart(path):
    """Load a text-art image: (Bitmap, [PaletteBinding]) in slot order."""
    with open(path, encoding='utf-8-sig') as f:         # tolerate a byte-order mark
        art = parse_textart(f.read(), path)
    return art.bitmap, art.palettes


_DEFAULT_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
_SPARE_CHARS = '+*%&$?!~^<>/|:;' + ''.join(chr(c) for c in range(0xC0, 0x250) if chr(c).isalpha())


def _pixel_token(v, palettes):
    if v == 0:
        return '0'
    if (v >> 2) < len(palettes):
        return '%s.%d' % (palettes[v >> 2].name, v & 3)
    return str(v)


def format_textart(bitmap, palettes=(), chars=None, comments=()):
    """Text-art source for a bitmap. chars: optional {character: pixel}; values
    without a character get a default one ('.' for 0, then 1-9, A-Z, a-z...)."""
    palettes = list(palettes)
    chars = dict(chars or {})
    for ch, v in chars.items():
        if len(ch) != 1 or ch.isspace() or ch == '=':
            raise ValueError('bad text-art character %r' % ch)
    for v in sorted(bitmap.values()):
        if v < 0 or (v and not v & 3):
            raise ValueError('pixel %d is not 0 or 4 * slot + colour (1-3)' % v)
    used = set(chars)
    have = {}
    for ch, v in chars.items():
        have.setdefault(v, ch)
    for v in sorted(bitmap.values()):
        if v in have:
            continue
        first = '.' if v == 0 else (_DEFAULT_CHARS[v] if v < len(_DEFAULT_CHARS) else None)
        ch = first if first is not None and first not in used else \
            next(c for c in '.' + _DEFAULT_CHARS + _SPARE_CHARS if c not in used)
        chars[ch] = v
        have[v] = ch
        used.add(ch)
    out = ['# ' + c if c else '#' for c in comments]
    out.append('@size %d %d' % (bitmap.w, bitmap.h))
    width = max([len(p.name) for p in palettes] + [1])
    for p in palettes:
        cols = ' '.join('keep' if c is None else format_rgb(c) for c in p.colors)
        out.append('@palette %-*s %s %d  %s' % (width, p.name, p.plane, p.number, cols))
    groups = {}
    for ch, v in sorted(chars.items(), key=lambda cv: (cv[1], cv[0])):
        groups.setdefault(v >> 2 if v else -1, []).append('%s = %s' % (ch, _pixel_token(v, palettes)))
    for key in sorted(groups):
        out.append('@chars ' + '   '.join(groups[key]))
    out.append('@data')
    for y in range(bitmap.h):
        out.append(''.join(have[v] for v in bitmap.row(y)))
    return '\n'.join(out) + '\n'


def save_textart(path, bitmap, palettes=(), chars=None, comments=()):
    """Write a text-art file (see format_textart)."""
    text = format_textart(bitmap, palettes, chars, comments)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


# ---------------------------------------------------------------------------
# PNG

def _keep_values(palettes, keep):
    """keep: {NAME.K or pixel value: rgb} overrides for 'keep' entries -> {pixel: rgb}."""
    out = {}
    names = {p.name: s for s, p in enumerate(palettes)}
    for key, rgb in (keep or {}).items():
        if isinstance(key, int):
            v = key
        else:
            name, _, k = key.rpartition('.')
            if name not in names or k not in ('1', '2', '3'):
                raise ValueError('bad keep key %r (expected NAME.K)' % key)
            v = 4 * names[name] + int(k)
        slot, c = v >> 2, v & 3
        if slot >= len(palettes) or not c or palettes[slot].colors[c - 1] is not None:
            raise ValueError('%r is not a keep colour' % key)
        out[v] = parse_rgb(rgb) if isinstance(rgb, str) else tuple(rgb[:3])
    return out


def _colours(palettes, keep):
    """{pixel: (r, g, b)} for every palette colour (not 0)."""
    over = _keep_values(palettes, keep)
    table = {}
    for s, p in enumerate(palettes):
        for c, rgb in enumerate(p.colors, 1):
            v = 4 * s + c
            table[v] = tuple(rgb) if rgb is not None else over.get(v, keep_placeholder(v))
    return table


def preview_rgb(palettes, transparent=TRANSPARENT, keep=None):
    """{pixel: (r, g, b)} for a text-art image: 0 -> transparent, 'keep' entries
    -> the keep override or keep_placeholder()."""
    table = {0: tuple(transparent)}
    table.update(_colours(palettes, keep))
    return table


def save_png(path, bitmap, rgb=None, scale=1):
    """Preview PNG. rgb: {pixel: (r, g, b)} or a sequence indexed by pixel;
    default: greys by colour (0 = magenta)."""
    if bitmap.w == 0 or bitmap.h == 0:
        raise ImageError('cannot write an empty bitmap to %s' % path)
    if rgb is None:
        lut = {v: DEFAULT_PREVIEW[v & 3] for v in bitmap.values()}
    else:
        lut = {}
        for v in bitmap.values():
            try:
                lut[v] = tuple(rgb[v][:3])
            except (KeyError, IndexError):
                raise ImageError('no preview colour for pixel %d' % v)
    rows = [[lut[v] for v in bitmap.row(y)] for y in range(bitmap.h)]
    png.write_rgb(path, bitmap.w, bitmap.h, rows, scale)


def import_png(path, palettes, transparent=TRANSPARENT, keep=None, cell=8):
    """Convert a PNG that uses exactly the colours of the palettes into a
    Bitmap. Transparent pixels have the transparent colour (None: none; it
    must not be a palette colour) or alpha 0 (RGBA PNGs; the tRNS chunk of
    indexed PNGs is not read). A colour
    that several palettes share is resolved per cell, from the image origin:
    the cell's pixels take the lowest slot that has all of the cell's colours
    (cell=None: per pixel), and the lowest colour of that slot. 'keep'
    entries match their override in keep, else keep_placeholder()."""
    w, h, rows, pal = png.read(path)
    table = {}
    for v, rgb in sorted(_colours(palettes, keep).items()):
        table.setdefault(rgb, []).append(v)
    transparent = None if transparent is None else tuple(transparent)
    if transparent in table:            # ambiguous: those pixels would silently become transparent
        raise ImageError('%s: the transparent colour %s is also a palette colour; choose another one'
                         % (path, format_rgb(transparent)))
    cands = [None] * (w * h)
    for y in range(h):
        for x in range(w):
            rgb, a = _rgba(rows, pal, path, x, y)
            if a == 0 or rgb == transparent:
                continue
            if a != 255:
                raise ImageError('%s: partly transparent pixel at (%d, %d)' % (path, x, y))
            c = table.get(rgb)
            if c is None:
                raise ImageError('%s: colour %s at (%d, %d) is not in the palettes'
                                 % (path, format_rgb(rgb), x, y))
            cands[y * w + x] = c
    out = Bitmap(w, h)
    step = cell if cell else 1
    for cy in range(0, h, step):
        for cx in range(0, w, step):
            idx = [y * w + x for y in range(cy, min(h, cy + step)) for x in range(cx, min(w, cx + step))
                   if cands[y * w + x] is not None]
            if not idx:
                continue
            slots = None
            for i in idx:
                s = {v >> 2 for v in cands[i]}
                slots = s if slots is None else slots & s
            if not slots:
                colours = sorted({format_rgb(_rgba(rows, pal, path, i % w, i // w)[0]) for i in idx})
                raise ImageError('%s: cell at (%d, %d) mixes palettes: %s' % (path, cx, cy, ' '.join(colours)))
            slot = min(slots)
            for i in idx:
                out.px[i] = min(v for v in cands[i] if v >> 2 == slot)
    return out


def _rgba(rows, pal, path, x, y):
    """((r, g, b), alpha) of a pixel from tools.common.png.read."""
    p = rows[y][x]
    if isinstance(p, int):              # indexed image (a truecolour PNG may also carry a PLTE)
        if pal is None or p >= len(pal):
            raise ImageError('%s: palette index %d at (%d, %d) is out of range' % (path, p, x, y))
        return tuple(pal[p][:3]), 255
    return tuple(p[:3]), p[3]


# ---------------------------------------------------------------------------
# Command line

def _keep_args(items):
    keep = {}
    for item in items or ():
        key, eq, rgb = item.partition('=')
        if not eq:
            raise SystemExit('--keep needs NAME.K=#RRGGBB, not %r' % item)
        keep[key] = parse_rgb(rgb)
    return keep


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.gfx.image', description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('import', help='PNG -> text-art, with the palettes and characters of a spec')
    p.add_argument('png')
    p.add_argument('out')
    p.add_argument('--like', required=True, help='text-art file whose palettes and @chars to use')
    p.add_argument('--keep', action='append', help='NAME.K=#RRGGBB: colour of a keep entry in the PNG')
    p.add_argument('--transparent', default=format_rgb(TRANSPARENT), help='transparent colour (default #FF00FF)')
    p.add_argument('--cell', type=int, default=8,
                   help='resolve colours shared by palettes per CELL x CELL cell (default 8; 0 = per pixel)')
    p = sub.add_parser('export', help='text-art -> preview PNG')
    p.add_argument('txt')
    p.add_argument('out')
    p.add_argument('--scale', type=int, default=1)
    p.add_argument('--keep', action='append', help='NAME.K=#RRGGBB: preview colour of a keep entry')
    p.add_argument('--transparent', default=format_rgb(TRANSPARENT), help='transparent colour (default #FF00FF)')
    args = ap.parse_args(argv)
    try:
        keep = _keep_args(args.keep)
        if args.cmd == 'import':
            with open(args.like, encoding='utf-8-sig') as f:
                spec = parse_textart(f.read(), args.like)
            bm = import_png(args.png, spec.palettes, parse_rgb(args.transparent), keep, args.cell or None)
            if (bm.w, bm.h) != (spec.bitmap.w, spec.bitmap.h):
                print('note: %s is %dx%d, %s is %dx%d' % (args.png, bm.w, bm.h, args.like,
                                                         spec.bitmap.w, spec.bitmap.h))
            save_textart(args.out, bm, spec.palettes, spec.chars,
                         ['imported from %s with the palettes of %s' % (os.path.basename(args.png),
                                                                        os.path.basename(args.like))])
            print('wrote %s (%dx%d)' % (args.out, bm.w, bm.h))
        else:
            bm, palettes = load_textart(args.txt)
            save_png(args.out, bm, preview_rgb(palettes, parse_rgb(args.transparent), keep), args.scale)
            print('wrote %s (%dx%d, scale %d)' % (args.out, bm.w, bm.h, args.scale))
    except (ImageError, ValueError, OSError) as e:
        print('error: %s' % e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
