"""Pixel fonts for the replacement graphics (assets/font/*.txt).

The syntax is that of assets/font/vwf8.txt, which tools/text/fontc.py also
reads:

    @NAME [advance=N]       starts a glyph; NAME is one character or a word
                            (SPACE, ELLIPSIS, LQUOTE)
    .###.                   glyph rows: '#' = ink, '.' = blank

* All glyphs of one file have the same number of rows (any height); all rows
  of one glyph have the same width. The advance defaults to width + 1.
* A line that starts with '#' is a comment, unless it holds only '#' and '.'
  (then it is a glyph row). Blank lines are ignored, and so are rows before
  the first glyph (as in fontc). Anything else is an error.
* Text characters map to glyph names directly, except ' ' -> SPACE,
  U+2026 -> ELLIPSIS, U+201C -> LQUOTE, U+201D -> '"', and U+2019 and
  U+2018 -> "'" (the same quotes as tools/text/encoding_en.py).

    font = load_font('assets/font/vwf8.txt')    # cached per path
    font.height                                  # rows per glyph
    font.glyph('A') -> Glyph(rows, advance)      # rows: tuple of '#'/'.' strings
    font.missing('Hello?') -> set of characters that have no glyph

Rendering (outline, bold, colours, boxes) is in tools/gfx/textart.py.
"""
import os
from collections import namedtuple

# text character -> glyph name, used when the character is not a glyph name itself
ALIASES = {
    ' ': 'SPACE',
    '\u2026': 'ELLIPSIS',
    '\u201c': 'LQUOTE',
    '\u201d': '"',
    '\u2019': "'",
    '\u2018': "'",
}


class FontError(ValueError):
    """A malformed font file."""


class MissingGlyphError(ValueError):
    """Characters of a text that the font does not have."""

    def __init__(self, chars, text=None, font=None):
        self.chars = set(chars)
        self.text = text
        self.font = font
        msg = 'no glyph for %s' % ', '.join(repr(c) for c in sorted(self.chars))
        if text is not None:
            msg += ' in %r' % text
        if font:
            msg += ' (font %s)' % font
        super().__init__(msg)


class Glyph(namedtuple('Glyph', 'rows advance')):
    """rows: tuple of strings of '#' (ink) and '.' (blank); advance: pen step in px."""
    __slots__ = ()

    @property
    def width(self):
        return len(self.rows[0]) if self.rows else 0

    @property
    def height(self):
        return len(self.rows)

    def ink(self):
        """Ink pixels as a list of (x, y)."""
        return [(x, y) for y, r in enumerate(self.rows) for x, c in enumerate(r) if c == '#']


class Font:
    """A parsed font: glyphs by name, all of the same height."""

    def __init__(self, glyphs, height, name='', path=None):
        self.glyphs = dict(glyphs)
        self.height = height
        self.name = name
        self.path = path
        self._key = None        # (path, mtime, size) for the load_font cache

    @classmethod
    def from_text(cls, text, source='<text>', name=None):
        """Parse font source text (the file syntax above)."""
        glyphs, height = _parse(text.splitlines(), source)
        if name is None:
            name = os.path.splitext(os.path.basename(source))[0]
        return cls(glyphs, height, name, None)

    def glyph_name(self, ch):
        """The glyph name used for a text character (or a glyph name)."""
        if ch in self.glyphs:
            return ch
        alias = ALIASES.get(ch)
        if alias is not None and alias in self.glyphs:
            return alias
        raise MissingGlyphError(ch, None, self.name)

    def glyph(self, ch):
        return self.glyphs[self.glyph_name(ch)]

    def missing(self, text):
        """The set of characters of text that have no glyph."""
        return {ch for ch in text if ch not in self.glyphs and ALIASES.get(ch) not in self.glyphs}

    def __contains__(self, ch):
        return ch in self.glyphs or ALIASES.get(ch) in self.glyphs

    def __repr__(self):
        return '<Font %s: %d glyphs, %d rows>' % (self.name, len(self.glyphs), self.height)


def _parse(lines, source):
    glyphs = {}
    height = None
    cur = None          # [name, advance, rows, line number]

    def finish():
        nonlocal height
        name, adv, rows, at = cur
        where = '%s:%d: glyph %s' % (source, at, name)
        if not rows:
            raise FontError('%s has no rows' % where)
        w = len(rows[0])
        if any(len(r) != w for r in rows):
            raise FontError('%s: rows differ in width' % where)
        if height is None:
            height = len(rows)
        elif len(rows) != height:
            raise FontError('%s has %d rows; the font has %d' % (where, len(rows), height))
        glyphs[name] = Glyph(tuple(rows), w + 1 if adv is None else adv)

    for n, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith('@'):
            if cur is not None:
                finish()
            parts = line[1:].split()
            if not parts:
                raise FontError('%s:%d: glyph header without a name' % (source, n))
            name, adv = parts[0], None
            if name in glyphs:
                raise FontError('%s:%d: glyph %s is defined twice' % (source, n, name))
            for opt in parts[1:]:
                key, _, value = opt.partition('=')
                if key != 'advance' or not value.isdigit():
                    raise FontError('%s:%d: bad glyph option %r (only advance=N)' % (source, n, opt))
                adv = int(value)
            cur = [name, adv, [], n]
        elif set(line) <= set('#.'):
            if cur is not None:
                cur[2].append(line)
        elif line.startswith('#'):
            continue
        else:
            raise FontError('%s:%d: not a glyph row, header or comment: %r' % (source, n, line))
    if cur is not None:
        finish()
    if not glyphs:
        raise FontError('%s: no glyphs' % source)
    return glyphs, height


_cache = {}


def load_font(path):
    """Load a font file; the result is cached per path (reloaded if the file changes)."""
    full = os.path.normcase(os.path.abspath(path))
    st = os.stat(full)
    key = (full, st.st_mtime_ns, st.st_size)
    font = _cache.get(full)
    if font is not None and font._key == key:
        return font
    with open(full, encoding='utf-8-sig') as f:         # tolerate a byte-order mark
        lines = f.read().splitlines()
    glyphs, height = _parse(lines, path)
    font = Font(glyphs, height, os.path.splitext(os.path.basename(path))[0], path)
    font._key = key
    _cache[full] = font
    return font
