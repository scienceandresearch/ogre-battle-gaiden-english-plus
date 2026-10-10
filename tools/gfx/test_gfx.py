"""Tests for the graphics library (tools/gfx/font.py, textart.py, image.py, tiles.py).

Usage: python -m tools.gfx.test_gfx [ROM]

No ROM is needed (an argument is accepted and ignored, for tools.gfx.test_all).
Covers: vwf8 against tools/text/fontc (glyphs, advances, widths); the font
syntax and its errors; outline and glow rings (4 and 8 neighbours), bold,
per-row gradients and patterns on synthetic glyphs; render_box alignment, top
and FitError; text-art files (round trip, unknown character, wrong size,
'keep' palettes, other errors); PNG export/import (exact colours, shared
colours, alpha) and the command line; colour words; cells, palette slots,
TileBank deduplication with H/V/HV flips and its budget; map-entry bits,
gfxfe blocks and the tile orders; determinism; and that the library uses no
PIL and holds no Japanese text.
"""
import ast
import contextlib
import io
import os
import struct
import sys
import tempfile
import time
import traceback
import zlib

from ..common import png
from ..common.tiles import decode_tile_2bpp, encode_tile_2bpp
from ..text import fontc
from ..text.encoding_en import ENCODE, GLYPH_OF_CODE
from . import font as F
from . import image as I
from . import textart as A
from . import tiles as T

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
VWF8 = os.path.join(ROOT, 'assets', 'font', 'vwf8.txt')
HERE = os.path.dirname(os.path.abspath(__file__))
LIB_FILES = ('font.py', 'textart.py', 'image.py', 'tiles.py', 'test_gfx.py')

# synthetic fonts (1 row: single pixels and marks; 3 rows: blocks for colours)
DOTS = F.Font.from_text('''
# one-row test font
@o
#
@m
#.#
@"
#.#
@LQUOTE
#.#
@ELLIPSIS
#.#.#
@SPACE advance=2
..
@n advance=1
#
''', 'dots')
BLOCKS = F.Font.from_text('''
@B
###
###
###
@i
.#.
.#.
.#.
@SPACE advance=2
...
...
...
''', 'blocks')
PLAIN = A.Style(outline=None)


def expect(cls, fn, *args, **kw):
    """Call fn and return the exception it must raise."""
    try:
        fn(*args, **kw)
    except cls as e:
        return e
    raise AssertionError('%s not raised by %s%r' % (cls.__name__, getattr(fn, '__name__', fn), args))


def grid(bm):
    return [list(r) for r in bm.rows()]


# ---------------------------------------------------------------------------
# Fonts

def test_vwf8_matches_fontc(ctx):
    font = F.load_font(VWF8)
    assert font.height == 8 and font is F.load_font(VWF8)
    vwf, widths, _ = fontc.build(VWF8, ctx.tmp('fontc'))
    for code, name in GLYPH_OF_CODE.items():
        g = font.glyphs[name]
        assert g.advance == widths[code], (name, g.advance, widths[code])
        for y in range(8):
            bits = sum(0x80 >> x for x, c in enumerate(g.rows[y][:8]) if c == '#')
            assert bits == vwf[code * 8 + y], (name, y)

    def fontc_extent(text):
        """Ink extent from fontc's compiled glyph bits and advances."""
        pen, xs = 0, []
        for ch in text:
            code = ENCODE[ch]
            for y in range(8):
                xs += [pen + x for x in range(8) if vwf[code * 8 + y] & (0x80 >> x)]
            pen += widths[code]
        return max(xs) - min(xs) + 1 if xs else 0

    texts = [ch for ch in ENCODE if ch not in '\n '] + list(fontc.SAMPLE) + [
        'Return to map', 'Imperial Year 15. Our story', 'is truly a \u201ctrue king\u201d\u2026',
        "one's own", 'A  B', ' lead and trail ']
    for text in texts:
        w = fontc_extent(text)
        assert A.measure(font, text, PLAIN) == w, (text, A.measure(font, text, PLAIN), w)
        assert A.measure(font, text, A.Style()) == (w + 2 if w else 0), text
        assert A.measure(font, text, A.Style(glow=(2, 2))) == (w + 6 if w else 0), text
        assert A.render(font, text, A.Style()).w == A.measure(font, text, A.Style())
    # the character mapping
    for ch, name in ((' ', 'SPACE'), ('\u2026', 'ELLIPSIS'), ('\u201c', 'LQUOTE'), ('\u201d', '"'),
                     ('\u2019', "'"), ('"', '"'), ("'", "'"), ('A', 'A')):
        assert font.glyph_name(ch) == name and font.glyph(ch) is font.glyphs[name], ch
    assert font.missing('Hi \u2026\u201c\u201d\u2019!') == set()
    assert font.missing('a{b}@\u00e9') == {'{', '}', '@', '\u00e9'}
    e = expect(F.MissingGlyphError, A.render, font, 'Bad {x}', A.Style())
    assert e.chars == {'{', '}'} and "'{'" in str(e) and 'Bad {x}' in str(e) and 'vwf8' in str(e)


def test_font_syntax(ctx):
    f = F.Font.from_text('''# comment line
## another comment, '#' at the start but not only '#' and '.'
#
.
@A advance=7
.#.
#.#

@b
#
#
''', 'syn')
    # rows before the first glyph are ignored (as fontc does)
    assert f.height == 2 and f.glyph('A') == F.Glyph(('.#.', '#.#'), 7) and f.glyph('b').advance == 2
    assert f.glyph('A').width == 3 and f.glyph('A').ink() == [(1, 0), (0, 1), (2, 1)]
    assert 'A' in f and 'z' not in f and f.missing('Abz') == {'z'}
    bad = {
        'height': '@a\n#\n@b\n#\n#\n',
        'width': '@a\n##\n#\n',
        'twice': '@a\n#\n@a\n#\n',
        'option': '@a wide=3\n#\n',
        'advance': '@a advance=x\n#\n',
        'empty glyph': '@a\n@b\n#\n',
        'junk': '@a\n#\nhello\n',
        'no name': '@\n#\n',
        'no glyphs': '# nothing\n',
    }
    for what, text in bad.items():
        expect(F.FontError, F.Font.from_text, text, what)
    e = expect(F.FontError, F.Font.from_text, '@a\n#\n@b\n#\n#\n', 'h.txt')
    assert 'h.txt:3' in str(e) and 'glyph b' in str(e) and '2 rows' in str(e)
    # load_font caches per path and reloads a changed file
    path = ctx.tmp('font.txt')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('@a\n#\n')
    f1 = F.load_font(path)
    assert F.load_font(path) is f1 and f1.height == 1 and f1.name == 'font'
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('@a\n#\n#\n')
    f2 = F.load_font(path)
    assert f2 is not f1 and f2.height == 2
    with open(path, 'wb') as fh:                                     # a byte-order mark is tolerated
        fh.write(b'\xef\xbb\xbf# font\n@a\n#\n')
    assert F.load_font(path).height == 1


# ---------------------------------------------------------------------------
# Text rendering

def test_outline_rings(ctx):
    one = A.render(DOTS, 'o', PLAIN)
    assert (one.w, one.h, one.px) == (1, 1, [1])
    four = A.render(DOTS, 'o', A.Style(outline8=False))
    assert grid(four) == [[0, 3, 0], [3, 1, 3], [0, 3, 0]]
    eight = A.render(DOTS, 'o', A.Style(outline8=True))
    assert grid(eight) == [[3, 3, 3], [3, 1, 3], [3, 3, 3]]
    glow8 = A.render(DOTS, 'o', A.Style(glow=(5,)))
    assert grid(glow8) == [[5] * 5, [5, 3, 3, 3, 5], [5, 3, 1, 3, 5], [5, 3, 3, 3, 5], [5] * 5]
    glow4 = A.render(DOTS, 'o', A.Style(outline8=False, glow=(5, 6)))
    assert grid(glow4) == [
        [0, 0, 0, 6, 0, 0, 0],
        [0, 0, 6, 5, 6, 0, 0],
        [0, 6, 5, 3, 5, 6, 0],
        [6, 5, 3, 1, 3, 5, 6],
        [0, 6, 5, 3, 5, 6, 0],
        [0, 0, 6, 5, 6, 0, 0],
        [0, 0, 0, 6, 0, 0, 0]]
    # glow without an outline: ring 1 is an empty gap
    gap = A.render(DOTS, 'o', A.Style(outline=None, glow=(5,)))
    assert grid(gap) == [[5] * 5, [5, 0, 0, 0, 5], [5, 0, 1, 0, 5], [5, 0, 0, 0, 5], [5] * 5]
    assert A.Style(outline=0).rings == () and A.Style(outline=None, glow=(5,)).rings == (0, 5)
    # rings are computed over the whole line: ink always wins over a neighbour's ring
    two = A.render(DOTS, 'oo', A.Style(outline8=False))       # pen 0 and 2
    assert grid(two) == [[0, 3, 0, 3, 0], [3, 1, 3, 1, 3], [0, 3, 0, 3, 0]]
    touch = A.render(DOTS, 'no', A.Style())                   # advance 1: the dots touch
    assert grid(touch) == [[3, 3, 3, 3], [3, 1, 1, 3], [3, 3, 3, 3]]
    # parts share one box
    for style in (A.Style(), A.Style(outline8=False, glow=(5, 6))):
        whole = A.render(DOTS, 'om', style)
        ink = A.render(DOTS, 'om', style, part='ink')
        rings = A.render(DOTS, 'om', style, part='rings')
        assert (ink.w, ink.h) == (rings.w, rings.h) == (whole.w, whole.h)
        assert all((a == b if b else a == c) for a, b, c in zip(whole.px, ink.px, rings.px))
        assert not any(b and c for b, c in zip(ink.px, rings.px))
        assert set(ink.px) == {0, 1} and 1 not in rings.px
    expect(ValueError, A.render, DOTS, 'o', A.Style(), 'outline')


def test_bold(ctx):
    bold = PLAIN._replace(bold=True)
    assert grid(A.render(DOTS, 'm', PLAIN)) == [[1, 0, 1]]
    assert grid(A.render(DOTS, 'm', bold)) == [[1, 1, 1, 1]]                  # 1 px wider
    assert grid(A.render(DOTS, '"', bold)) == [[1, 1, 0, 1, 1]]               # marks kept apart
    assert grid(A.render(DOTS, '\u201d', bold)) == [[1, 1, 0, 1, 1]]
    assert grid(A.render(DOTS, '\u201c', bold)) == [[1, 1, 0, 1, 1]]
    assert grid(A.render(DOTS, '\u2026', bold)) == [[1, 1, 0, 1, 1, 0, 1, 1]]
    # advances: m 4 -> 5, SPACE unchanged (2), '"' -> new width 5 + 1
    assert A.measure(DOTS, 'm m', PLAIN) == 9 and A.measure(DOTS, 'm m', bold) == 11
    assert A.measure(DOTS, '"m', bold) == 6 + 4 and A.measure(DOTS, '\u2026m', bold) == 9 + 4
    assert A.embolden('m', ('#.#',), 4) == (('####',), 5)
    assert A.embolden('ELLIPSIS', ('#.#.#',), 6) == (('##.##.##',), 9)
    assert A.embolden('SPACE', ('..',), 2) == (('..',), 2)
    # bold on a real font: every glyph with ink gets 1 px wider
    vwf = F.load_font(VWF8)
    for text in ('Items', 'Return to map', 'A'):
        n = sum(1 for ch in text if ch != ' ')
        assert A.measure(vwf, text, bold) == A.measure(vwf, text, PLAIN) + n, text


def test_colours(ctx):
    rows = A.render(BLOCKS, 'B', A.Style(rows=(1, 2, 3), outline=None))
    assert grid(rows) == [[1, 1, 1], [2, 2, 2], [3, 3, 3]]
    grad = A.render(BLOCKS, 'B', A.Style(rows=(1, 2, 3), outline=7))       # slot 1 outline colour
    assert grid(grad)[0] == [7] * 5 and grid(grad)[2] == [7, 2, 2, 2, 7]
    pat = A.render(BLOCKS, 'BB', A.Style(pattern=[[1, 2], [3, 1]], outline=None))
    # anchored at the pen origin: the second B starts at x 4, an even column
    assert grid(pat) == [[1, 2, 1, 0, 1, 2, 1], [3, 1, 3, 0, 3, 1, 3], [1, 2, 1, 0, 1, 2, 1]]
    stripes = A.render(BLOCKS, 'B', A.Style(pattern=(5, 6), outline=None))  # flat = per pixel row
    assert grid(stripes) == [[5, 5, 5], [6, 6, 6], [5, 5, 5]]
    shifted = A.render(BLOCKS, 'iB', A.Style(pattern=[[1, 2]], outline=None))
    assert grid(shifted)[0] == [2, 0, 0, 1, 2, 1]                  # 'i' ink at x 1: pattern column 1
    assert A.Style(pattern=(5, 6)).pattern == ((5,), (6,))
    expect(ValueError, A.Style, rows=(1, 2, 3), pattern=(1,))
    expect(ValueError, A.Style, pattern=[[1, 2], [3]])
    expect(ValueError, A.render, BLOCKS, 'B', A.Style(rows=(1, 2)))
    assert A.Style()._replace(glow=[2, 3]).glow == (2, 3)          # _replace normalises too
    assert grid(A.render(BLOCKS, 'i', A.Style(ink=9, outline=None))) == [[9], [9], [9]]


def test_render_box(ctx):
    style = A.Style()                                   # 'B' with its outline is 5 x 5
    left = A.render_box(BLOCKS, 'B', style, 11, 7, 'left', 1)
    assert left.bbox() == (0, 0, 5, 5) and left.get(1, 1) == 1 and left.get(0, 0) == 3
    centre = A.render_box(BLOCKS, 'B', style, 11, 7, 'center', 1)
    assert centre.bbox() == (3, 0, 8, 5)                # (11 - 5) // 2 = 3, left biased
    assert A.render_box(BLOCKS, 'B', style, 12, 7, top=1).bbox() == (3, 0, 8, 5)
    right = A.render_box(BLOCKS, 'B', style, 11, 7, 'right', 1)
    assert right.bbox() == (6, 0, 11, 5)
    # top is the box row of glyph row 0; the rings may be clipped at the edges
    top0 = A.render_box(BLOCKS, 'B', style, 5, 3, 'left', 0)
    assert grid(top0) == [[3, 1, 1, 1, 3]] * 3
    low = A.render_box(BLOCKS, 'B', style, 5, 7, 'left', 3)
    assert low.bbox() == (0, 2, 5, 7) and low.get(1, 3) == 1
    mid = A.render_box(BLOCKS, 'B', style, 5, 8, 'left', None)      # centred: (8 - 5) // 2
    assert mid.bbox() == (0, 1, 5, 6)
    # does not fit: too wide (the message names the text and its width), ink outside vertically
    e = expect(A.FitError, A.render_box, BLOCKS, 'BB', style, 8, 7)
    assert (e.text, e.width, e.limit) == ('BB', 9, 8) and "'BB'" in str(e) and '9 px' in str(e)
    e = expect(A.FitError, A.render_box, BLOCKS, 'B', style, 9, 7, 'left', 5)
    assert e.width == 5 and "'B'" in str(e) and 'rows 5-7' in str(e)
    expect(A.FitError, A.render_box, BLOCKS, 'B', style, 9, 7, 'left', -1)
    expect(ValueError, A.render_box, BLOCKS, 'B', style, 9, 7, 'middle')
    # exactly the width fits; spacing widens; empty text gives an empty box
    assert A.render_box(BLOCKS, 'BB', style, 9, 5, 'left', 1).bbox() == (0, 0, 9, 5)
    assert A.measure(BLOCKS, 'BB', style._replace(spacing=2)) == 11
    assert A.render_box(BLOCKS, '', style, 4, 4).bbox() is None and A.measure(BLOCKS, '  ') == 0
    # an 8-px label: vwf8 glyph rows 0-7 in the box, outline rows outside are clipped
    vwf = F.load_font(VWF8)
    label = A.render_box(vwf, 'Items', A.Style(), 64, 8)
    assert (label.w, label.h) == (64, 8) and A.measure(vwf, 'Items') == 25
    assert label.bbox() == ((64 - 25) // 2, 0, (64 - 25) // 2 + 25, 8)
    ink_rows = [y for y in range(8) if 1 in label.row(y)]
    assert ink_rows == [1, 2, 3, 4, 5, 6], ink_rows


def test_deterministic(ctx):
    vwf = F.load_font(VWF8)
    style = A.Style(bold=True, glow=(2,), rows=(1, 1, 1, 2, 2, 3, 3, 3))
    a = A.render_box(vwf, 'The quick brown fox', style, 160, 16, 'center', 4)
    b = A.render_box(vwf, 'The quick brown fox', style, 160, 16, 'center', 4)
    assert a == b and T.tiles_rowmajor(a) == T.tiles_rowmajor(b)
    bank1, bank2 = T.TileBank(range(100), True), T.TileBank(range(100), True)
    assert [bank1.add(c) for c in T.cells(a)] == [bank2.add(c) for c in T.cells(b)]
    assert bank1.blob() == bank2.blob()


# ---------------------------------------------------------------------------
# Text-art images and PNG

ART = '''# test art
@size 4 2
@palette fire plane1 0  #FF0000 #00FF00 #0000FF
@palette sub  plane2 5  #102030 #405060 keep
@chars . = 0   a = fire.1   b = fire.2   c = fire.3
@chars x = sub.1   y = sub.2   z = sub.3
@data
.abc
xyz.
# trailing comment
'''


def test_textart_roundtrip(ctx):
    art = I.parse_textart(ART, 'art.txt')
    assert art.bitmap == I.Bitmap(4, 2, [0, 1, 2, 3, 5, 6, 7, 0])
    fire, sub = art.palettes
    assert fire == I.PaletteBinding('fire', 'plane1', 0, ((255, 0, 0), (0, 255, 0), (0, 0, 255)))
    assert (sub.plane, sub.number, sub.colors[2]) == ('plane2', 5, None)
    assert art.chars == {'.': 0, 'a': 1, 'b': 2, 'c': 3, 'x': 5, 'y': 6, 'z': 7}
    text = I.format_textart(art.bitmap, art.palettes, art.chars, ['round trip'])
    assert text == I.format_textart(art.bitmap, art.palettes, art.chars, ['round trip'])
    again = I.parse_textart(text)
    assert again == (art.bitmap, art.palettes, art.chars)
    # default characters, plain pixel numbers without a palette, save/load
    bm = I.Bitmap(3, 1, [0, 9, 5])
    text = I.format_textart(bm, [fire])
    assert '9 = 9' in text and '5 = 5' in text and I.parse_textart(text).bitmap == bm
    path = ctx.tmp('art.txt')
    I.save_textart(path, art.bitmap, art.palettes, art.chars)
    assert I.load_textart(path) == (art.bitmap, art.palettes)
    with open(path, 'rb') as fh:
        data = fh.read()
    assert b'\r' not in data
    with open(path, 'wb') as fh:                                     # a byte-order mark is tolerated
        fh.write(b'\xef\xbb\xbf' + data)
    assert I.load_textart(path) == (art.bitmap, art.palettes)
    expect(ValueError, I.format_textart, I.Bitmap(1, 1, [4]))       # colour 0 of slot 1


def test_textart_errors(ctx):
    def err(text, *needles):
        e = expect(I.TextArtError, I.parse_textart, text, 't.txt')
        for n in needles:
            assert n in str(e), (n, str(e))
    head = ART.split('@data')[0] + '@data\n'
    err(head + '.abq\nxyz.\n', 'unknown character', "'q'", 'x 3, y 0')
    err(head + '.ab\nxyz.\n', 'wrong size', '3 characters')
    err(head + '.abc\n', 'wrong size', '1 data rows')
    err(head + '.abc\nxyz.\n.abc\n', 'wrong size', 'more than 2')
    err(head + '.abc\n\nxyz.\n', 'wrong size')
    err(ART.replace('#0000FF', '#00FF'), "'#00FF'")
    err(ART.replace('#0000FF', 'blue'), "'blue'")
    err(ART.replace(' keep', ''), '@palette NAME')
    err(ART.replace('plane2', 'plane3'), 'plane3')
    err(ART.replace('plane2 5', 'plane2 16'), '0-15')
    err(ART.replace('@palette sub  plane2 5', '@palette sub  plane1 0'), 'declared twice')
    err(ART.replace('@palette sub ', '@palette fire'), 'repeated palette name')
    err(ART.replace('z = sub.3', 'z = sab.3'), "'sab.3'")
    err(ART.replace('z = sub.3', 'z = sub.4'), "'sub.4'")
    err(ART.replace('z = sub.3', 'c = sub.3'), "'c' is mapped twice")
    err(ART.replace('z = sub.3', 'z = 4'), 'colour 0')
    err(ART.replace('@size 4 2\n', ''), 'no @size')
    err(ART.replace('@data', '@dato'), 'unknown line')
    err(ART.split('@data')[0], 'no @data')
    # 'keep' entries: no colour word, a placeholder or override in previews, overrides only for keep
    sub = I.parse_textart(ART).palettes[1]
    assert sub.colors[2] is None and sub.words() == [I.rgb_to_ngp((16, 32, 48)), I.rgb_to_ngp((64, 80, 96)), None]
    pals = I.parse_textart(ART).palettes
    assert I.preview_rgb(pals)[7] == I.keep_placeholder(7)
    assert I.preview_rgb(pals, keep={'sub.3': '#010203'})[7] == (1, 2, 3)
    assert I.preview_rgb(pals, keep={7: (4, 5, 6)})[7] == (4, 5, 6)
    expect(ValueError, I.preview_rgb, pals, keep={'fire.1': (1, 2, 3)})
    expect(ValueError, I.preview_rgb, pals, keep={'sub.9': (1, 2, 3)})


def _write_png(path, w, h, rows, ctype=6, plte=None):
    """A truecolour PNG (ctype 6 = RGBA, 2 = RGB), optionally with a suggested PLTE."""
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b''.join(b'\0' + bytes(v for px in row for v in px) for row in rows)
    extra = chunk(b'PLTE', b''.join(bytes(c) for c in plte)) if plte else b''
    with open(path, 'wb') as fh:
        fh.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ctype, 0, 0, 0))
                 + extra + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def test_png(ctx):
    art = I.parse_textart(ART)
    pals = art.palettes
    # preview -> import gives the same pixels (keep entries through their placeholder)
    path = ctx.tmp('art.png')
    I.save_png(path, art.bitmap, I.preview_rgb(pals))
    assert I.import_png(path, pals, cell=None) == art.bitmap
    e = expect(I.ImageError, I.import_png, path, pals)               # both palettes in one 8x8 cell
    assert 'cell at (0, 0) mixes palettes' in str(e)
    w, h, rows, _ = png.read(path)
    assert (w, h) == (4, 2) and rows[0][0][:3] == I.TRANSPARENT and rows[0][1][:3] == (255, 0, 0)
    I.save_png(ctx.tmp('big.png'), art.bitmap, I.preview_rgb(pals), scale=3)
    assert png.read(ctx.tmp('big.png'))[:2] == (12, 6)
    I.save_png(ctx.tmp('grey.png'), art.bitmap)                     # default greys
    expect(I.ImageError, I.save_png, ctx.tmp('x.png'), art.bitmap, {0: (0, 0, 0)})
    # keep colours with an override
    I.save_png(path, art.bitmap, I.preview_rgb(pals, keep={'sub.3': (9, 9, 9)}))
    assert I.import_png(path, pals, keep={'sub.3': (9, 9, 9)}, cell=None) == art.bitmap
    e = expect(I.ImageError, I.import_png, path, pals, cell=None)   # (9, 9, 9) is unknown without it
    assert '#090909' in str(e)
    # a colour shared by two palettes is resolved per 8x8 cell
    shared = [I.PaletteBinding('a', 'plane1', 0, ((0, 0, 0), (255, 0, 0), (0, 255, 0))),
              I.PaletteBinding('b', 'plane1', 1, ((0, 0, 0), (0, 0, 255), (0, 255, 0)))]
    k, r, g, b, m = (0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255), I.TRANSPARENT
    img = [[k, r] + [m] * 6 + [k, b] + [m] * 6] + [[m] * 16] * 7
    png.write_rgb(path, 16, 8, img)
    got = I.import_png(path, shared)
    assert got.row(0)[:2] == [1, 2] and got.row(0)[8:10] == [5, 6], got.row(0)
    per_pixel = I.import_png(path, shared, cell=None)
    assert per_pixel.row(0)[8:10] == [1, 6]                         # lowest slot per pixel
    png.write_rgb(path, 16, 8, [[r, b] + [m] * 14] + [[m] * 16] * 7)
    e = expect(I.ImageError, I.import_png, path, shared)
    assert 'mixes palettes' in str(e) and '#0000FF' in str(e) and '#FF0000' in str(e)
    png.write_rgb(path, 2, 1, [[r, (1, 2, 3)]])
    e = expect(I.ImageError, I.import_png, path, shared)
    assert '#010203' in str(e) and '(1, 0)' in str(e)
    # indexed PNGs, and alpha 0 as transparent
    png.write_indexed(path, 3, 1, [[0, 1, 2]], [m, r, b])
    assert I.import_png(path, shared, cell=None).px == [0, 2, 6]
    png.write_indexed(path, 3, 1, [[0, 1, 2]], [m, k, g])
    assert I.import_png(path, shared).px == [0, 1, 3]
    _write_png(path, 3, 1, [[(1, 1, 1, 0), (255, 0, 0, 255), (0, 0, 255, 255)]])
    assert I.import_png(path, shared, cell=None).px == [0, 2, 6]
    _write_png(path, 1, 1, [[(255, 0, 0, 128)]])
    expect(I.ImageError, I.import_png, path, shared)
    # a truecolour PNG may carry a suggested palette: its pixels are still RGB
    _write_png(path, 3, 1, [[m, r, g]], ctype=2, plte=[k, b])
    assert png.read(path)[3] is not None and I.import_png(path, shared).px == [0, 2, 3]
    # transparent=None: only alpha 0 is transparent, so magenta is an unknown colour
    e = expect(I.ImageError, I.import_png, path, shared, transparent=None)
    assert '#FF00FF at (0, 0)' in str(e)
    # a palette colour equal to the transparent colour is ambiguous: an error, never silently transparent
    magenta = [I.PaletteBinding('m', 'plane1', 0, (m, g, b))]
    png.write_rgb(path, 2, 1, [[m, g]])
    e = expect(I.ImageError, I.import_png, path, magenta)
    assert 'transparent colour #FF00FF is also a palette colour' in str(e)
    assert I.import_png(path, magenta, transparent=None).px == [1, 2]


def test_image_cli(ctx):
    spec = ctx.tmp('spec.txt')
    with open(spec, 'w', encoding='utf-8') as fh:
        fh.write(ART)
    out_png, out_txt = ctx.tmp('cli.png'), ctx.tmp('cli.txt')

    def cli(*args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = I.main(list(args))
        return code, out.getvalue() + err.getvalue()

    assert cli('export', spec, out_png, '--keep', 'sub.3=#112233') == (0, 'wrote %s (4x2, scale 1)\n' % out_png)
    code, msg = cli('import', out_png, out_txt, '--like', spec, '--keep', 'sub.3=#112233', '--cell', '0')
    assert code == 0 and 'wrote' in msg
    with open(out_txt, encoding='utf-8') as fh:
        art = I.parse_textart(fh.read())
    assert (art.bitmap, art.palettes, art.chars) == I.parse_textart(ART)
    code, msg = cli('import', out_png, out_txt, '--like', spec, '--cell', '0')        # keep colour unknown
    assert code == 1 and 'colour #112233 at (2, 1) is not in the palettes' in msg
    code, msg = cli('import', out_png, out_txt, '--like', spec, '--keep', 'sub.3=#112233')
    assert code == 1 and 'mixes palettes' in msg                                     # two palettes, one cell


def test_bitmap(ctx):
    bm = I.Bitmap(3, 2, [[1, 2, 3], [4, 5, 6]])
    assert bm.px == [1, 2, 3, 4, 5, 6] and bm.get(2, 1) == 6 and bm.row(1) == [4, 5, 6]
    assert I.Bitmap.from_rows(bm.rows()) == bm and bm.copy() == bm and bm.copy() is not bm
    assert bm.crop(1, 1, 3, 2) == I.Bitmap(3, 2, [5, 6, 0, 0, 0, 0])
    dst = I.Bitmap(4, 2, [7] * 8)
    dst.paste(I.Bitmap(2, 2, [0, 1, 2, 0]), 3, -1)
    assert dst.px == [7, 7, 7, 2, 7, 7, 7, 7]
    dst = I.Bitmap(2, 1, [7, 7])
    dst.blit(I.Bitmap(2, 1, [0, 1]), 0, 0)
    assert dst.px == [7, 1] and I.Bitmap(2, 2).bbox() is None
    expect(ValueError, I.Bitmap, 2, 2, [0, 0, 0])
    expect(ValueError, I.Bitmap, 2, 2, [[0, 0], [0]])


def test_colour_words(ctx):
    assert I.rgb_to_ngp((255, 0, 0)) == 0x00F and I.rgb_to_ngp((0, 255, 0)) == 0x0F0
    assert I.rgb_to_ngp((0, 0, 255)) == 0xF00 and I.rgb_to_ngp('#FFE040') == 0x4DF
    assert I.rgb_to_ngp((8, 8, 25)) == 0x100 and I.rgb_to_ngp((26, 0, 0)) == 0x002
    assert I.rgb_to_ngp((0, 9, 0)) == 0x010                        # 9 * 15 / 255 = 0.53 rounds up
    assert I.ngp_to_rgb(0x4DF) == (255, 221, 68)
    assert all(I.rgb_to_ngp(I.ngp_to_rgb(w)) == w for w in range(0x1000))
    assert I.parse_rgb('#a0B1c2') == (0xA0, 0xB1, 0xC2) and I.format_rgb((1, 2, 3)) == '#010203'
    expect(ValueError, I.parse_rgb, '#12345')


# ---------------------------------------------------------------------------
# Cells and tiles

def _cell(seed):
    return [[(x * 3 + y * 5 + seed) % 4 for x in range(8)] for y in range(8)]


def test_cells_and_slots(ctx):
    bm = I.Bitmap(16, 8)
    bm.set(9, 0, 6)
    cs = T.cells(bm)
    assert [(c.col, c.row) for c in cs] == [(0, 0), (1, 0)]
    assert T.cell_slot(cs[0]) is None and T.cell_slot(cs[1]) == 1 and cs[1][0][1] == 6
    assert len(T.cells(I.Bitmap(16, 16), 2, 2)) == 4
    expect(ValueError, T.cells, bm, 3, 1)
    expect(ValueError, T.cells, I.Bitmap(12, 8))
    bm.set(10, 1, 2)
    e = expect(T.PaletteError, T.cell_slot, T.cells(bm)[1])
    assert 'col 1, row 0' in str(e) and 'slots 0, 1' in str(e)
    expect(T.PaletteError, T.tiles_rowmajor, bm)
    expect(T.PaletteError, T.cell_slot, [[4] + [0] * 7] + [[0] * 8] * 7)
    expect(ValueError, T.Cell, [[0] * 8] * 7)
    cell = _cell(1)
    assert T.encode_cell(cell) == encode_tile_2bpp(cell)
    assert decode_tile_2bpp(T.encode_cell(cell)) == cell
    slot2 = [[v + 8 if v else 0 for v in r] for r in cell]
    assert T.encode_cell(slot2) == T.encode_cell(cell) and T.cell_slot(slot2) == 2


def test_tilebank_flips(ctx):
    cell = _cell(0)
    cell[0][0] = 3                                     # make it asymmetric both ways
    h = [list(reversed(r)) for r in cell]
    v = list(reversed(cell))
    hv = [list(reversed(r)) for r in v]
    bank = T.TileBank([0x40, 0x41, 0x42, 0x43], flips=True)
    assert bank.add(cell) == (0x40, False, False)
    assert bank.add(h) == (0x40, True, False)
    assert bank.add(v) == (0x40, False, True)
    assert bank.add(hv) == (0x40, True, True)
    assert bank.add(cell) == (0x40, False, False)
    # same colours in another palette slot share the tile
    assert bank.add([[x + 4 if x else 0 for x in r] for r in h]) == (0x40, True, False)
    # a symmetric cell matches exactly before any flip
    sym = [[1, 2, 3, 0, 0, 3, 2, 1]] * 8
    assert bank.add(sym) == (0x41, False, False) and bank.add(sym) == (0x41, False, False)
    assert bank.used == [0x40, 0x41] and bank.tiles == [T.encode_cell(cell), T.encode_cell(sym)]
    assert bank.remaining == [0x42, 0x43] and len(bank) == 2
    assert bank.blob() == T.encode_cell(cell) + T.encode_cell(sym)
    # without flips a mirror is a new tile
    exact = T.TileBank(range(10), flips=False)
    assert exact.add(cell) == (0, False, False) and exact.add(h) == (1, False, False)
    assert exact.add(v) == (2, False, False) and exact.add(hv) == (3, False, False)
    # budget
    small = T.TileBank([7], flips=True)
    small.add(cell)
    small.add(hv)
    e = expect(T.BudgetError, small.add, T.cells(I.Bitmap(8, 8, [1] * 64))[0])
    assert 'budget' in str(e) and '1 pool tiles' in str(e) and 'col 0, row 0' in str(e)
    expect(ValueError, T.TileBank, [1, 1])
    expect(ValueError, T.TileBank, [512])
    expect(T.PaletteError, bank.add, [[1, 5] + [0] * 6] + [[0] * 8] * 7)


def test_map_entries(ctx):
    assert T.map_entry(0x1FF) == 0x01FF and T.map_entry(0x100, 0) == 0x0100
    assert T.map_entry(0, 1) == 0x0200 and T.map_entry(0, 15) == 0x1E00
    assert T.map_entry(0, 0, vflip=True) == 0x4000 and T.map_entry(0, 0, hflip=True) == 0x8000
    assert T.map_entry(0x1AB, 5, True, True) == 0x1AB | (5 << 9) | 0xC000
    assert T.map_entry(3, 2, False, True) & 0x2000 == 0              # bit 13 stays clear
    expect(ValueError, T.map_entry, 512)
    expect(ValueError, T.map_entry, 1, 16)
    assert T.gfxfe_block(2, 1, [0x1234, 0xABCD]) == b'\x02\x01\x34\x12\xcd\xab'
    block = T.gfxfe_block(3, 2, range(6))
    assert block[:2] == b'\x03\x02' and len(block) == 2 + 12 and block[2 + 2 * 4] == 4
    expect(ValueError, T.gfxfe_block, 2, 2, [0, 0, 0])
    expect(ValueError, T.gfxfe_block, 0, 1, [])
    expect(ValueError, T.gfxfe_block, 1, 1, [0x10000])


def test_tile_orders(ctx):
    # a label strip: 8 tiles left to right
    strip = I.Bitmap(64, 8)
    for t in range(8):
        strip.set(t * 8, 0, 1 + t % 3)
        strip.set(t * 8 + 1 + t % 7, 7, 3)
    data = T.tiles_rowmajor(strip)
    assert len(data) == 128
    assert [data[16 * t:16 * t + 16] for t in range(8)] == [T.encode_cell(c) for c in T.cells(strip)]
    # an intro line: 144 x 16 = the top 18 tiles, then the bottom 18
    line = I.Bitmap(144, 16)
    for t in range(36):
        line.set((t % 18) * 8 + t % 8, (t // 18) * 8 + t % 5, 1 + t % 3)
    data = T.tiles_lines(line, 2)
    assert len(data) == 576
    for t in range(36):
        cell = line.crop((t % 18) * 8, (t // 18) * 8, 8, 8)
        assert data[16 * t:16 * t + 16] == T.encode_cell(cell.rows()), t
    assert data == T.tiles_rowmajor(line)
    # two stacked lines come out line by line
    two = I.Bitmap(16, 32)
    two.paste(line.crop(0, 0, 16, 16), 0, 0)
    two.paste(line.crop(16, 0, 16, 16), 0, 16)
    data = T.tiles_lines(two, 2)
    assert data[:64] == T.tiles_rowmajor(line.crop(0, 0, 16, 16))
    assert data[64:] == T.tiles_rowmajor(line.crop(16, 0, 16, 16))
    expect(ValueError, T.tiles_lines, I.Bitmap(8, 24), 2)


# ---------------------------------------------------------------------------
# Repository rules

def test_pure_python_and_english(ctx):
    allowed = {'argparse', 'ast', 'collections', 'contextlib', 'io', 'os', 'struct', 'sys', 'tempfile', 'time',
               'traceback', 'zlib'}
    allowed_from = {'common', 'common.png', 'common.tiles', 'text', 'text.encoding_en', 'font', 'image',
                    'textart', 'tiles', None}
    for name in LIB_FILES:
        path = os.path.join(HERE, name)
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        for node in ast.walk(ast.parse(src, path)):
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split('.')[0] in allowed, (name, a.name)
            elif isinstance(node, ast.ImportFrom):
                assert node.level >= 1 or node.module in allowed, (name, node.module)
                if node.level:
                    assert node.module in allowed_from, (name, node.module)
        bad = [c for c in src if 0x3000 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF
               or 0xFF00 <= ord(c) <= 0xFFEF]
        assert not bad, (name, len(bad))


TESTS = [test_vwf8_matches_fontc, test_font_syntax, test_outline_rings, test_bold, test_colours,
         test_render_box, test_deterministic, test_textart_roundtrip, test_textart_errors, test_png,
         test_image_cli, test_bitmap, test_colour_words, test_cells_and_slots, test_tilebank_flips,
         test_map_entries, test_tile_orders, test_pure_python_and_english]


class Context:
    def __init__(self, folder):
        self.folder = folder

    def tmp(self, name):
        return os.path.join(self.folder, name)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    failed = 0
    with tempfile.TemporaryDirectory(prefix='test_gfx_') as folder:
        ctx = Context(folder)
        for test in TESTS:
            t0 = time.time()
            try:
                test(ctx)
            except Exception:
                failed += 1
                print('FAIL %s' % test.__name__)
                traceback.print_exc()
            else:
                print('ok   %s (%.2f s)' % (test.__name__, time.time() - t0))
    print('%d tests, %d failed' % (len(TESTS), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
