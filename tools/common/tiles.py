"""NGP tile formats.

K2GE character data: 8x8 pixels, 2 bits per pixel, 16 bytes per tile.
Each row is a little-endian 16-bit word; pixel 0 (leftmost) is in bits 15-14.
"""


def decode_tile_2bpp(data, offset=0):
    """Returns 8 rows of 8 pixel values (0-3)."""
    rows = []
    for r in range(8):
        w = data[offset + r * 2] | (data[offset + r * 2 + 1] << 8)
        rows.append([(w >> (14 - 2 * x)) & 3 for x in range(8)])
    return rows


def encode_tile_2bpp(rows):
    out = bytearray(16)
    for r in range(8):
        w = 0
        for x in range(8):
            w |= (rows[r][x] & 3) << (14 - 2 * x)
        out[r * 2] = w & 0xFF
        out[r * 2 + 1] = w >> 8
    return bytes(out)


GRAY4 = [(255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)]


def tiles_to_rows(tiles, per_row, palette=GRAY4, gap=1, gap_color=(255, 0, 255)):
    """Lay out a list of decoded tiles into an RGB image (rows of tuples)."""
    n = len(tiles)
    nrows = (n + per_row - 1) // per_row
    w = per_row * (8 + gap) + gap
    h = nrows * (8 + gap) + gap
    img = [[gap_color] * w for _ in range(h)]
    for i, t in enumerate(tiles):
        ox = gap + (i % per_row) * (8 + gap)
        oy = gap + (i // per_row) * (8 + gap)
        for y in range(8):
            for x in range(8):
                img[oy + y][ox + x] = palette[t[y][x]]
    return w, h, img
