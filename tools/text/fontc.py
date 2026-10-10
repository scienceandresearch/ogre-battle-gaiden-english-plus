"""Compile assets/font/vwf8.txt into ROM data.

Outputs (binary, laid out by text code 0x00-0xFF):
  vwf_glyphs.bin  256 x 8 bytes, 1bpp rows, bit 7 = leftmost pixel
  vwf_widths.bin  256 bytes, advance in pixels (0 = not drawable)
  font8.bin       codes 0x02-0xDC as 8x8 2bpp K2GE tiles (background colour 2,
                  ink colour 1) for the tile-mapped UI printer; same layout as
                  the original font so it can replace it 1:1
  preview.png     sample rendering

Usage: python -m tools.text.fontc assets/font/vwf8.txt OUTDIR
"""
import os
import sys

from ..common import png
from ..common.tiles import encode_tile_2bpp
from .encoding_en import GLYPH_OF_CODE


def parse_font(path):
    glyphs = {}
    name, rows, adv = None, [], None
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f]
    for line in lines + ['@END']:
        if line.startswith('#') and not line.startswith('#.') and not set(line) <= set('#.'):
            continue
        if line.startswith('@'):
            if name is not None:
                if len(rows) != 8:
                    raise ValueError('glyph %s has %d rows' % (name, len(rows)))
                w = len(rows[0])
                if any(len(r) != w for r in rows):
                    raise ValueError('glyph %s rows differ in width' % name)
                glyphs[name] = (rows, adv if adv is not None else w + 1)
            parts = line[1:].split()
            name = parts[0] if parts else None
            adv = None
            for p in parts[1:]:
                if p.startswith('advance='):
                    adv = int(p.split('=')[1])
            rows = []
            continue
        if line.strip() == '':
            continue
        if set(line) <= set('#.'):
            rows.append(line)
    return glyphs


def build(font_path, out_dir):
    glyphs = parse_font(font_path)
    vwf = bytearray(256 * 8)
    widths = bytearray(256)
    for code in range(256):
        g = GLYPH_OF_CODE.get(code)
        if g is None:
            continue
        if g not in glyphs:
            raise ValueError('no glyph for %s (code %02X)' % (g, code))
        rows, adv = glyphs[g]
        for r in range(8):
            bits = 0
            for x, ch in enumerate(rows[r][:8]):
                if ch == '#':
                    bits |= 0x80 >> x
            vwf[code * 8 + r] = bits
        widths[code] = adv
    # fixed 8x8 tiles for the UI printer: glyph centred-left with 1px margin
    font8 = bytearray()
    for code in range(0x02, 0xDD):
        tile = [[2] * 8 for _ in range(8)]
        g = GLYPH_OF_CODE.get(code)
        if g is not None:
            rows, adv = glyphs[g]
            w = len(rows[0])
            ox = max(0, (7 - w) // 2) if w < 7 else 0
            for r in range(8):
                for x, ch in enumerate(rows[r][:8]):
                    if ch == '#' and ox + x < 8:
                        tile[r][ox + x] = 1
        font8 += encode_tile_2bpp(tile)
    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, 'vwf_glyphs.bin'), 'wb').write(bytes(vwf))
    open(os.path.join(out_dir, 'vwf_widths.bin'), 'wb').write(bytes(widths))
    open(os.path.join(out_dir, 'font8.bin'), 'wb').write(bytes(font8))
    preview(glyphs, os.path.join(out_dir, 'preview.png'))
    return vwf, widths, font8


SAMPLE = ['Fix Tristram Zenobia, prince of a fallen',
          'kingdom. The quick brown fox jumps over',
          'the lazy dog! 0123456789 (Yes/No)? “OK”…']


def preview(glyphs, path):
    from .encoding_en import ENCODE
    W, H = 200, 8 * len(SAMPLE) + 4
    img = [[(36, 52, 140)] * W for _ in range(H)]
    for li, text in enumerate(SAMPLE):
        x = 2
        for ch in text:
            code = ENCODE.get(ch, ENCODE['?'])
            g = GLYPH_OF_CODE.get(code, 'SPACE')
            rows, adv = glyphs[g]
            for r in range(8):
                for cx, c in enumerate(rows[r]):
                    if c == '#' and x + cx < W:
                        img[2 + li * 8 + r][x + cx] = (248, 248, 248)
            x += adv
    png.write_rgb(path, W, H, img, scale=4)


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
    print('font compiled to', sys.argv[2])
