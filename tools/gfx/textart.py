"""Text rendering for the replacement graphics: one line of text in a pixel
font (tools/gfx/font.py) with a style, as an indexed Bitmap
(tools/gfx/image.py).

    style = Style(ink=1, outline=3, outline8=True)
    measure(font, text, style) -> width in px, rings included
    render(font, text, style, part='all') -> Bitmap
    render_box(font, text, style, w, h, align='center', top=0) -> Bitmap(w, h)

Style fields:
* ink: colour (pixel value) of the glyph ink.
* rows: per-glyph-row ink colours (a vertical gradient), one per font row.
* pattern: colours repeated over the ink, given as rows of colours (a flat
  sequence of numbers is one colour per pixel row). It is anchored at the pen
  origin of the first glyph and at glyph row 0, so it does not depend on where
  the text is placed. rows and pattern replace ink and exclude each other.
* outline: colour of ring 1, the 1-px ring around the ink; None or 0 = none.
* outline8: rings grow to the 8 neighbours (True) or to 4 (False).
* glow: colours of rings 2..k, each 1 px outside the previous ring. With glow
  but no outline, ring 1 is an empty (transparent) gap.
* bold: each glyph with ink gets 1 px wider: every ink pixel also inks the
  pixel to its right, and the advance grows by 1. The marks in BOLD_MARKS
  (ellipsis, both double quotes) double each ink pixel instead and keep the
  gaps, so their dots stay apart (advance = new width + 1).
* spacing: extra px added to every advance.

Pixel values are used as given: plain colours 1-3, or 4 * slot + colour for
layers with several palettes. Ink always wins over rings, and the rings are
computed over the whole line, so neighbouring glyphs never cover each other.

Geometry. render() returns the tight box horizontally (leftmost to rightmost
ink, plus the rings on both sides; measure() is this width) and the full font
height vertically (plus the rings), so glyph row 0 is at y = number of rings.
part='ink' or part='rings' keeps only that part, in the same box, for
two-layer art.

render_box() places the text in a w x h box. align is 'left', 'center' (left
biased: x = (w - width) // 2) or 'right'. top is the box row of glyph row 0;
the rings extend above it (top=None centres the text's box vertically). It
raises FitError when the width (rings included) exceeds w, or when ink falls
outside the box vertically. Rings may be clipped at the top and bottom: 8-px
labels use top=0 and lose the outline above row 0 and below descenders.
"""
from collections import namedtuple

from .font import MissingGlyphError
from .image import Bitmap

BOLD_MARKS = frozenset(('ELLIPSIS', 'LQUOTE', '"'))
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
N8 = N4 + ((1, 1), (-1, 1), (1, -1), (-1, -1))
ALIGNS = ('left', 'center', 'right')
PARTS = ('all', 'ink', 'rings')


class FitError(ValueError):
    """A text that does not fit its box. Attributes: text, width, limit."""

    def __init__(self, text, width, limit, detail=None):
        self.text, self.width, self.limit = text, width, limit
        if detail is None:
            msg = '%r is %d px wide; the box is %d px' % (text, width, limit)
        else:
            msg = '%r (%d px wide) does not fit the box: %s' % (text, width, detail)
        super().__init__(msg)


def _pattern(p):
    p = list(p)
    if not p:
        raise ValueError('Style.pattern is empty')
    if all(isinstance(v, int) for v in p):
        return tuple((v,) for v in p)
    rows = tuple(tuple(r) for r in p)
    if not rows[0] or any(len(r) != len(rows[0]) for r in rows):
        raise ValueError('Style.pattern rows must have the same, non-zero length')
    return rows


class Style(namedtuple('Style', 'ink outline outline8 bold glow rows pattern spacing')):
    """How a text is drawn (see the module notes); immutable, vary it with _replace()."""
    __slots__ = ()

    def __new__(cls, ink=1, outline=3, outline8=True, bold=False, glow=(), rows=None, pattern=None,
                spacing=0):
        glow = tuple(glow)
        rows = None if rows is None else tuple(rows)
        pattern = None if pattern is None else _pattern(pattern)
        if rows is not None and pattern is not None:
            raise ValueError('Style: rows and pattern exclude each other')
        return super().__new__(cls, ink, outline, bool(outline8), bool(bold), glow, rows, pattern,
                               int(spacing))

    @classmethod
    def _make(cls, iterable):           # so that _replace() normalises like the constructor
        return cls(*iterable)

    @property
    def rings(self):
        """Colours of rings 1..k (0 = transparent ring)."""
        if self.glow:
            return (self.outline or 0,) + self.glow
        return (self.outline,) if self.outline else ()


def embolden(name, rows, advance):
    """Bold version of a glyph (see Style.bold): (rows, advance)."""
    if name in BOLD_MARKS:
        rows = [''.join('##' if c == '#' else '.' for c in r) for r in rows]
        w = max(len(r) for r in rows)
        return tuple(r.ljust(w, '.') for r in rows), w + 1
    if not any('#' in r for r in rows):
        return tuple(rows), advance
    return tuple(''.join('#' if (i < len(r) and r[i] == '#') or (i > 0 and r[i - 1] == '#') else '.'
                         for i in range(len(r) + 1)) for r in rows), advance + 1


def _painter(font, style):
    if style.pattern is not None:
        pat = style.pattern
        ph, pw = len(pat), len(pat[0])
        return lambda x, y: pat[y % ph][x % pw]
    if style.rows is not None:
        rows = style.rows
        if len(rows) != font.height:
            raise ValueError('Style.rows has %d colours; font %s has %d rows'
                             % (len(rows), font.name, font.height))
        return lambda x, y: rows[y]
    ink = style.ink
    return lambda x, y: ink


def _ink(font, text, style):
    """Ink of a line: {(x, y): colour}; x from the pen origin, y = glyph row."""
    missing = font.missing(text)
    if missing:
        raise MissingGlyphError(missing, text, font.name)
    paint = _painter(font, style)
    ink = {}
    pen = 0
    for ch in text:
        name = font.glyph_name(ch)
        rows, adv = font.glyphs[name]
        if style.bold:
            rows, adv = embolden(name, rows, adv)
        for y, r in enumerate(rows):
            for gx, c in enumerate(r):
                if c == '#':
                    x = pen + gx
                    ink[(x, y)] = paint(x, y)
        pen += adv + style.spacing
    return ink


def measure(font, text, style=None):
    """Width in px of the rendered text, rings included (0 if it has no ink)."""
    style = Style() if style is None else style
    ink = _ink(font, text, style)
    if not ink:
        return 0
    xs = [x for x, _ in ink]
    return max(xs) - min(xs) + 1 + 2 * len(style.rings)


def _render(font, text, style, part):
    """(Bitmap, (first, last) glyph rows with ink or None)."""
    if part not in PARTS:
        raise ValueError('part must be one of %s, not %r' % (', '.join(PARTS), part))
    rings = style.rings
    r = len(rings)
    ink = _ink(font, text, style)
    h = font.height + 2 * r
    if not ink:
        return Bitmap(0, h), None
    x0 = min(x for x, _ in ink)
    w = max(x for x, _ in ink) - x0 + 1 + 2 * r
    bm = Bitmap(w, h)
    px = bm.px
    taken = bytearray(w * h)
    frontier = []
    for (x, y), colour in ink.items():
        i = (y + r) * w + (x - x0 + r)
        taken[i] = 1
        frontier.append(i)
        if part != 'rings':
            px[i] = colour
    nb = N8 if style.outline8 else N4
    for colour in rings:
        ring = []
        for i in frontier:
            y, x = divmod(i, w)
            for dx, dy in nb:
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h:
                    j = yy * w + xx
                    if not taken[j]:
                        taken[j] = 1
                        ring.append(j)
        if part != 'ink':
            for j in ring:
                px[j] = colour
        frontier = ring
    ys = [y for _, y in ink]
    return bm, (min(ys), max(ys))


def render(font, text, style=None, part='all'):
    """The text with its rings in its tight box (see the module notes)."""
    return _render(font, text, Style() if style is None else style, part)[0]


def render_box(font, text, style, w, h, align='center', top=0, part='all'):
    """The text placed in a w x h Bitmap (see the module notes); FitError if it does not fit."""
    style = Style() if style is None else style
    bm, inkrows = _render(font, text, style, part)
    r = len(style.rings)
    if bm.w > w:
        raise FitError(text, bm.w, w)
    if align == 'left':
        x = 0
    elif align == 'center':
        x = (w - bm.w) // 2
    elif align == 'right':
        x = w - bm.w
    else:
        raise ValueError('align must be one of %s, not %r' % (', '.join(ALIGNS), align))
    y = (h - bm.h) // 2 if top is None else top - r
    if inkrows is not None:
        a, b = y + r + inkrows[0], y + r + inkrows[1]
        if a < 0 or b >= h:
            raise FitError(text, bm.w, w, 'its ink covers rows %d-%d of a %d-row box' % (a, b, h))
    out = Bitmap(w, h)
    out.paste(bm, x, y)
    return out
