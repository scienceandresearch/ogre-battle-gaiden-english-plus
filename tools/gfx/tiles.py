"""8x8 cells, 2bpp tiles and plane maps in the K2GE formats.

* cells(bitmap, cols, rows) cuts an indexed Bitmap into 8x8 Cells, row-major.
  A Cell is a tuple of 8 rows of 8 pixels and knows its grid position.
* cell_slot(cell) is the palette slot of the cell's non-zero pixels (None if
  the cell is empty); PaletteError if they use several slots.
* encode_cell(cell) -> 16 bytes, through tools.common.tiles.encode_tile_2bpp
  (each row a little-endian word, leftmost pixel in bits 15-14; the colour is
  pixel & 3).
* TileBank(pool, flips) numbers the tiles from a pool and shares identical
  tiles, and with flips=True also mirrored ones (H, V, then HV):
  add(cell) -> (tile, hflip, vflip). .tiles (16-byte tiles) and .used (their
  numbers) are in allocation order, .remaining is the unused pool. BudgetError
  when a new tile is needed and the pool is used up.
* map_entry(tile, pal, hflip, vflip): bits 0-8 tile, 9-12 palette, 14 V flip,
  15 H flip.
* gfxfe_block(w, h, entries): [w][h] then w*h little-endian words (the map
  block of script op gfxfe).
* tiles_rowmajor(bitmap): every cell left to right, then top to bottom
  (labels: 8 tiles left to right).
* tiles_lines(bitmap, rows): the bitmap as text lines of `rows` cell rows;
  line by line, the line's top cell row, then the next (intro: the top 18
  tiles, then the bottom 18).
"""
from ..common.tiles import encode_tile_2bpp


class PaletteError(ValueError):
    """A cell whose pixels use several palette slots (or a bad pixel value)."""


class BudgetError(ValueError):
    """The tile pool is used up."""


class Cell(tuple):
    """8 rows (tuples) of 8 pixels; col and row give its grid position, if known."""

    def __new__(cls, rows, col=None, row=None):
        cell = super().__new__(cls, (tuple(r) for r in rows))
        if len(cell) != 8 or any(len(r) != 8 for r in cell):
            raise ValueError('a cell is 8 rows of 8 pixels')
        cell.col, cell.row = col, row
        return cell

    @property
    def where(self):
        return 'cell (col %d, row %d)' % (self.col, self.row) if self.col is not None else 'cell'

    def __repr__(self):
        return '<Cell %s %r>' % (self.where, tuple(self))


def _cell(cell):
    return cell if isinstance(cell, Cell) else Cell(cell)


def cells(bitmap, cols=None, rows=None):
    """Cut a bitmap into cols x rows cells (default: the whole bitmap, whose size
    must be a multiple of 8). Returns the Cells in row-major order."""
    cols = bitmap.w // 8 if cols is None else cols
    rows = bitmap.h // 8 if rows is None else rows
    if (bitmap.w, bitmap.h) != (cols * 8, rows * 8):
        raise ValueError('a %dx%d bitmap is not %d x %d cells' % (bitmap.w, bitmap.h, cols, rows))
    w, px = bitmap.w, bitmap.px
    out = []
    for r in range(rows):
        for c in range(cols):
            base = r * 8 * w + c * 8
            out.append(Cell([px[base + y * w:base + y * w + 8] for y in range(8)], c, r))
    return out


def cell_slot(cell):
    """The palette slot of the cell's non-zero pixels; None for an empty cell."""
    cell = _cell(cell)
    slots = set()
    for row in cell:
        for v in row:
            if v:
                if v < 0 or not v & 3:
                    raise PaletteError('%s: pixel %d is not 4 * slot + colour (1-3)' % (cell.where, v))
                slots.add(v >> 2)
    if len(slots) > 1:
        raise PaletteError('%s mixes palette slots %s' % (cell.where, ', '.join(map(str, sorted(slots)))))
    return slots.pop() if slots else None


def encode_cell(cell):
    """16 bytes of 2bpp tile data (colour = pixel & 3)."""
    return encode_tile_2bpp(_cell(cell))


def flip_cell(cell, hflip=False, vflip=False):
    """The cell mirrored left-right (hflip) and/or top-bottom (vflip)."""
    rows = [tuple(reversed(r)) if hflip else tuple(r) for r in cell]
    if vflip:
        rows.reverse()
    return Cell(rows, getattr(cell, 'col', None), getattr(cell, 'row', None))


class TileBank:
    """Tile numbering with deduplication. pool: the tile numbers to use, in order.
    flips: also share a tile with its H, V and HV mirror images (map-entry flip bits).
    Blank cells get no special treatment: map them to a blank tile or entry 0 first
    if the target wants that."""

    def __init__(self, pool, flips=False):
        self.pool = list(pool)
        if len(set(self.pool)) != len(self.pool):
            raise ValueError('the tile pool lists a tile twice')
        if any(not 0 <= t <= 511 for t in self.pool):
            raise ValueError('tile numbers are 0-511')
        self.flips = bool(flips)
        self.tiles = []         # 16-byte tiles, in allocation order
        self.used = []          # their tile numbers
        self._index = {}        # tile data -> tile number

    @property
    def remaining(self):
        return self.pool[len(self.used):]

    def add(self, cell):
        """Tile for a cell: (tile, hflip, vflip). A new tile takes the next pool number."""
        cell = _cell(cell)
        cell_slot(cell)
        data = encode_cell(cell)
        tile = self._index.get(data)
        if tile is not None:
            return tile, False, False
        if self.flips:
            for h, v in ((True, False), (False, True), (True, True)):
                tile = self._index.get(encode_cell(flip_cell(cell, h, v)))
                if tile is not None:
                    return tile, h, v
        if len(self.used) >= len(self.pool):
            raise BudgetError('tile budget exhausted: all %d pool tiles are used (at %s)'
                              % (len(self.pool), cell.where))
        tile = self.pool[len(self.used)]
        self._index[data] = tile
        self.tiles.append(data)
        self.used.append(tile)
        return tile, False, False

    def blob(self):
        """All tiles, in allocation order."""
        return b''.join(self.tiles)

    def __len__(self):
        return len(self.tiles)


def map_entry(tile, pal=0, hflip=False, vflip=False):
    """Plane map entry: bits 0-8 tile, 9-12 palette, 14 V flip, 15 H flip."""
    if not 0 <= tile <= 511:
        raise ValueError('tile %r is not 0-511' % tile)
    if not 0 <= pal <= 15:
        raise ValueError('palette %r is not 0-15' % pal)
    return tile | (pal << 9) | (0x4000 if vflip else 0) | (0x8000 if hflip else 0)


def gfxfe_block(w, h, entries):
    """Map block for script op gfxfe: [w][h], then w*h little-endian words, row by row."""
    entries = list(entries)
    if not (1 <= w <= 32 and 1 <= h <= 32):
        raise ValueError('map block size %dx%d is not 1-32 x 1-32' % (w, h))
    if len(entries) != w * h:
        raise ValueError('map block %dx%d needs %d entries, got %d' % (w, h, w * h, len(entries)))
    out = bytearray((w, h))
    for e in entries:
        if not 0 <= e <= 0xFFFF:
            raise ValueError('map entry %r is not 16 bits' % e)
        out += bytes((e & 0xFF, e >> 8))
    return bytes(out)


def tiles_rowmajor(bitmap):
    """Every cell of the bitmap, left to right, then top to bottom."""
    data = bytearray()
    for cell in cells(bitmap):
        cell_slot(cell)
        data += encode_cell(cell)
    return bytes(data)


def tiles_lines(bitmap, rows=2):
    """The bitmap as text lines of `rows` cell rows each; line by line, each line's
    top cell row left to right, then its next cell row. (Row-major within each
    line; the height must be a whole number of lines.)"""
    if bitmap.h % (8 * rows):
        raise ValueError('a %d-px high bitmap is not made of %d-cell lines' % (bitmap.h, rows))
    grid = cells(bitmap)
    cols = bitmap.w // 8
    data = bytearray()
    for line in range(bitmap.h // (8 * rows)):
        for r in range(line * rows, (line + 1) * rows):
            for cell in grid[r * cols:(r + 1) * cols]:
                cell_slot(cell)
                data += encode_cell(cell)
    return bytes(data)
