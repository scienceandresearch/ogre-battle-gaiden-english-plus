"""Graphics target 'title': the English title logo and the warning window, in place.

The title screen is one uncompressed package in bank 0x28 (docs/workstreams/
gfx-title-logo.md). This target rewrites, in place, with no hooks and no new
ROM:

* the logo band, map rows 7-12 (y 56-103) of both scroll planes, as two
  text-art layers:
    plane 1 (front): the letter fill, plane-1 palette 0 (fire) or 1 (white);
    plane 2 (back):  the 1-px black outline and the cyan/blue glow (plane-2
                     palette 0) and the subtitle (palette 5: amber letters
                     with a brown outline);
  each 8x8 cell uses one palette per plane, as in the original;
* the warning window that NewGame or Load opens over suspend data: rows 1-3
  of its 20x5 map, in vwf8 (ink colour 1 on colour 2, plane-1 palette 3);
* the tiles of both, from the pool of tiles that only the old logo and the
  old window text used, or that nothing on the screen references; identical
  and mirrored cells share a tile;
* the count byte of the flag sprite list (50 -> 48), which drops the two
  sprites that patched fire pixels into white cells of the old logo.
Palettes are written only for colours that the art does not mark 'keep'
(today all are 'keep': the logo uses the original colours). Reserved cells
(row 7, columns 11 and 13-15: arm artwork) stay as they are and must be
empty in the art.

Sources
    translation/en/title.txt          @kicker, @logo (FIRE|WHITE), @subtitle, @window (twice),
                                      @yes, @no
    assets/gfx/title/logo_front.txt   plane 1 (160x48 text-art; palettes 'keep')
    assets/gfx/title/logo_back.txt    plane 2 (160x48 text-art; palettes 'keep')
    assets/font/vwf8.txt              the window text
  and, for `draft` only: assets/font/logo19.txt (main title),
  assets/gfx/title/kicker5.txt (the line above it), assets/gfx/title/italic9.txt
  (subtitle).

The layers are drawn by `draft` from title.txt and the fonts, then reviewed
and committed; the build reads them as committed. The style rules (in this
module) follow the original logo: mottled fire and white fills (the fire
darker on the edges and the top and bottom rows, the white grey on the right
and bottom edges), a 1-px black outline on the 4 neighbours of the fill (and
on diagonal steps and some outer corners), a cyan glow with a blue fringe
(light on the outer edges, the row above the subtitle left empty), nothing
but the outline under the see-through thumb of the fist sprite, and thin
italic amber subtitle letters with a 1-px brown outline. Their header names
the wording they show ('# kicker:', '# logo:', '# subtitle:'), and the build
stops when title.txt says something else: run `draft`, review, replace.

    python -m tools.gfx.title fit                       widths, cells, palettes, tile budget (no ROM)
    python -m tools.gfx.title draft [OUTDIR]            draw both layers from title.txt (text-art;
                                                        default build/gfx/title/draft)
    python -m tools.gfx.title preview OUTDIR [--rom ROM]   our layers as PNG; with the ROM also the
                                                        whole screen and the window (local only)
    python -m tools.gfx.title decode ROM OUTDIR         a ROM's title screen and window as PNG
                                                        (local only: never commit the originals)
    python -m tools.gfx.title check ROM DUMP|DIR ... [--window]
                                                        harness --vram dumps: VRAM tiles and maps
                                                        equal the ROM package
    python -m tools.gfx.title warn-test IN OUT          test ROM only: NewGame always opens the
                                                        warning window (2 NOPs at 0x28CDA4)
"""
import argparse
import hashlib
import os
import sys

from ..common import png
from ..common.tiles import decode_tile_2bpp
from ..recomp.rom import ROM_BASE
from ..recomp.tlcs900 import DecodeError, decode
from .font import load_font
from .image import Bitmap, PaletteBinding, format_textart, ngp_to_rgb, parse_textart
from .target import Result, TargetError
from .textart import FitError
from .tiles import PaletteError, TileBank, cell_slot, cells, map_entry

# Part of the full build: enabled by the verify step (gfx-verify, 2026-10-10)
# together with the other graphics targets.
FULL_BUILD = True

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TEXT_FILE = 'title.txt'                                         # translation/en/
ART_DIR = os.path.join('assets', 'gfx', 'title')
FRONT_FILE = os.path.join(ART_DIR, 'logo_front.txt')
BACK_FILE = os.path.join(ART_DIR, 'logo_back.txt')
LOGO_FONT = os.path.join('assets', 'font', 'logo19.txt')
KICKER_FONT = os.path.join(ART_DIR, 'kicker5.txt')
SUB_FONT = os.path.join(ART_DIR, 'italic9.txt')
WINDOW_FONT = os.path.join('assets', 'font', 'vwf8.txt')

# ---------------------------------------------------------------------------
# The title package (CPU addresses)

TILES = 0x28D307                    # 512 tiles x 16 bytes (copied to VRAM 0xA000)
P2PAL = 0x28D277                    # plane-2 palettes 0-6, 4 words each
P1PAL = 0x28D2AF                    # plane-1 palettes 0-3
P1MAP_HDR, P1MAP = 0x28F4C3, 0x28F4C5       # [20][19] then 20x19 entries -> plane 1 (0x9000)
WINMAP_HDR, WINMAP = 0x28F7BD, 0x28F7BF     # [20][5] then 20x5 entries -> 0x9340 (plane 1, row 13)
P2MAP_HDR, P2MAP = 0x28F887, 0x28F889       # [20][19] then 20x19 entries -> plane 2 (0x9800)
FLAG_LIST = 0x28F307                # flag sprite list: count byte, 5-byte records
FLAG_COUNT_OLD, FLAG_COUNT_NEW = 50, 48     # the last two records are the old logo's fill sprites
PRESS_LIST = 0x28F480               # PRESS A BUTTON sprites (preview only)
BG_COLOUR = 0x28CBC6
SPRPAL = 0x28D2CF
# The menu code jumps over the window when there is no suspend data; warn-test
# (test ROMs only) replaces this instruction with two NOPs. The check decodes it.
WARN_JUMP = 0x28CDA4
WARN_JUMP_TEXT = 'jr Z, 0x28CDD0'
WARN_JUMP_LEN = 2

MAP_W, MAP_H = 20, 19
ROW0, ROWS = 7, 6                   # the logo band: map rows 7-12
LOGO_W, LOGO_H = 160, 48
LOGO_Y = 8 * ROW0                   # screen y of the layers' row 0
RESERVED = frozenset((7, c) for c in (11, 13, 14, 15))     # (row, col), both planes: arm artwork
# The thumb of the fist (sprites drawn in front of the logo) is an outline with
# see-through holes that must show the dark background, as in the original:
# screen box x0, y0, x1, y1 (inclusive) where the logo has nothing but the
# black outline of a letter next to it.
THUMB = (107, 64, 113, 71)

WIN_W, WIN_H = 20, 5
WIN_ROWS = (1, 2, 3)                # interior rows and columns of the window block
WIN_COLS = range(1, 19)
WIN_PAL = 3                         # plane-1 palette 3: white ink on dark blue
WIN_BLANK = 0x132                   # the window's blank interior tile (kept)
WIN_INK, WIN_PAPER = 1, 2
WIN_SCREEN_ROW = 13                 # the block is drawn at plane-1 row 13 (0x9340)
MENU_ROWS = (13, 14)                # the menu draws its label maps (17x2) at plane-2 row 13 (0x9B44)
# (window row, first column, last column) per text item; the answer cursor
# (sprite tile 0x13A) sits in column 5 (x 40) for yes and 11 (x 88) for no.
WIN_ITEMS = (('window1', 1, 1, 18), ('window2', 2, 1, 18), ('yes', 3, 6, 10), ('no', 3, 12, 18))


def _r(a, b):
    return list(range(a, b + 1))


WINDOW_TILES = _r(0x062, 0x075) + _r(0x12F, 0x131)                      # the old window text (23)
OLD_LOGO = [t for t in _r(0x001, 0x04B) if t != 0x00B] + _r(0x04C, 0x061) + _r(0x076, 0x0B3)   # 158
UNUSED = ([0x00B] + _r(0x0B4, 0x0BF) + _r(0x0F4, 0x0FF) + _r(0x11E, 0x11F) + _r(0x12C, 0x12E) +
          _r(0x13B, 0x13F) + _r(0x1DE, 0x1DF) + _r(0x1EC, 0x1F7))       # referenced by nothing (49)
POOL = WINDOW_TILES + OLD_LOGO + UNUSED                                 # window first, then the logo
WINDOW_BUDGET = 29
LOGO_BUDGET = 201

# Which hardware palettes each layer may use (plane, palette): plane-1 palettes 0-1
# are faded in from ROM (2 = flag highlights, 3 = the window); plane-2 palettes 1 and 6
# are loaded but unused on this screen; plane-2 palette 5 colour 3 also colours the
# flag (tile 0x148), so it must stay 'keep'.
LAYER_PALETTES = {'plane1': (0, 1), 'plane2': (0, 1, 5, 6)}
KEEP_REQUIRED = {('plane2', 5, 3)}

WORDING_KEYS = ('kicker', 'logo', 'subtitle')

# ---------------------------------------------------------------------------
# Draft style (tools for `draft`; the build reads the committed art)

Y_MAIN = 65                 # main title glyph row 0 (19 rows: fill y 65-83, outline 84, glow 85-86,
                            # the original's rows; with or without a kicker)
Y_KICK = 57                 # kicker glyph row 0 (5 rows: y 57-61; its outline on y 56, the band's top)
Y_SUB = 89                  # subtitle cap row 0 (9 rows: y 89-97, the original's amber rows)
MAIN_SPACING = 0            # extra px after each main glyph advance (letters 1 px apart)
WORD_GAP = 4                # px between the fire and the white part (= logo19's word space)
FILL_MIN, FILL_MAX = 4, 155         # x range of the main title's ink
KICK_MAX = 84               # rightmost kicker ink (its glow must stay out of column 11)
BAND_CENTRE = 79.5
GLOW_ROWS = (56, 87)        # plane-2 rows of the outline and glow (palette 0): map rows 7-10 without
                            # y 87, which stays empty above the subtitle as in the original
GLOW_X = (2, 158)           # columns of the glow (the original's reach x 3-156, +1 px each side)
SUB_ROWS = (88, 104)        # plane-2 rows of the subtitle (palette 5): map rows 11-12
FIRE_FRAC = (0.13, 0.39, 0.48)      # share of colours 1-3 (yellow, orange-red, dark red)
KICK_FRAC = (0.25, 0.45, 0.30)      # the small kicker: brighter, so that its 2-px strokes read at 1x
WHITE_FRAC = (0.36, 0.22, 0.42)     # white, light grey, grey
# Fill shading (added to smooth value noise before the colours are given by share):
# fire: brighter inside the strokes, darker on the edges and on the first and last rows
FIRE_IN, FIRE_RB, FIRE_LT, FIRE_TOP, FIRE_BOTTOM = 0.05, 0.07, 0.03, 0.10, 0.25
# white: grey towards the right and bottom edges, white towards the left and top
WHITE_R, WHITE_B, WHITE_L, WHITE_T = 0.18, 0.28, 0.10, 0.06
CORNER_SHARE = 0.25         # outer corners of the outlines that the original also fills (about 1 in 4)
# The glow by the side of the lettering a pixel is on (outer_side), as measured on the
# original logo. On the outer edges: (share of blue in ring 2, else cyan; share of blue
# and of cyan in ring 3, else empty). Above the letters ring 2 is cyan and ring 3 mostly
# blue; under them ring 2 is half blue, ring 3 a few blue pixels and the row above the
# subtitle stays empty; left and right ring 3 is sparse blue.
OUTER_GLOW = {'above': (0.05, 0.53, 0.20), 'below': (0.50, 0.20, 0.00), 'left': (0.30, 0.37, 0.00),
              'right': (0.55, 0.25, 0.00), 'corner': (0.50, 0.33, 0.24)}
# Enclosed places (counters, gaps between letters, the row between the kicker and the
# main title): ring 2 cyan (blue where weak); ring 3 where surrounded cyan above the
# first strength, blue above the second, elsewhere blue above ENCLOSED_OPEN; ring 4
# cyan (next to cyan) or blue (next to the glow) above RING4, and on the outer edges
# above the letters blue above RING4_OUTER (next to the glow).
ENCLOSED_RING3, ENCLOSED_OPEN = (0.45, 0.15), 0.45
RING4, RING4_OUTER = (0.75, 0.65), 0.80
OUTER_RAY = 6               # px: how far outer_side looks for the fill
SEED_FIRE, SEED_WHITE, SEED_KICK, SEED_GLOW, SEED_SUB = 1, 2, 3, 4, 5
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
D4 = ((1, 1), (-1, 1), (1, -1), (-1, -1))

# Text-art characters of the two layers
FRONT_CHARS = {'.': 0, 'Y': 1, 'O': 2, 'R': 3, 'W': 5, 'L': 6, 'G': 7}
BACK_CHARS = {'.': 0, 'b': 1, 'c': 2, 'k': 3, 'n': 5, 'a': 6, 'z': 7}
FRONT_PALETTES = [PaletteBinding('fire', 'plane1', 0, (None, None, None)),
                  PaletteBinding('white', 'plane1', 1, (None, None, None))]
BACK_PALETTES = [PaletteBinding('glow', 'plane2', 0, (None, None, None)),
                 PaletteBinding('sub', 'plane2', 5, (None, None, None))]

# Preview colours for 'keep' entries when no ROM is given: our own rough choice
# (the game shows its own palettes; with a ROM the previews use those)
PREVIEW_KEEP = {('plane1', 0): [(250, 210, 60), (235, 90, 20), (150, 20, 10)],
                ('plane1', 1): [(250, 250, 250), (210, 210, 215), (160, 160, 170)],
                ('plane2', 0): [(30, 90, 200), (40, 200, 240), (10, 10, 10)],
                ('plane2', 5): [(130, 80, 20), (250, 180, 30), (20, 20, 20)]}
PREVIEW_BG = (10, 10, 150)


def rel(path):
    try:
        r = os.path.relpath(path, ROOT)
    except ValueError:
        return path
    return path if r.startswith('..') else r.replace(os.sep, '/')


def in_thumb(q):
    """Is the screen pixel q under the thumb of the fist (THUMB)?"""
    return THUMB[0] <= q[0] <= THUMB[2] and THUMB[1] <= q[1] <= THUMB[3]


# ---------------------------------------------------------------------------
# translation/en/title.txt

def parse_text(text, source='title.txt'):
    """{'kicker', 'logo': (fire, white or ''), 'subtitle', 'window1', 'window2', 'yes', 'no'}."""
    out = {}
    windows = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        where = '%s:%d' % (source, n)
        if not line.startswith('@'):
            raise TargetError('%s: expected "@KEY TEXT", not %r' % (where, line))
        key, _, value = line[1:].partition(' ')
        value = value.strip()
        if key == 'window':
            windows.append(value)
            continue
        if key not in ('kicker', 'logo', 'subtitle', 'yes', 'no'):
            raise TargetError('%s: unknown key @%s (known: kicker, logo, subtitle, window, yes, no)' % (where, key))
        if key in out:
            raise TargetError('%s: @%s is given twice' % (where, key))
        if not value and key != 'kicker':
            raise TargetError('%s: @%s has no text' % (where, key))
        out[key] = value
    missing = [k for k in ('kicker', 'logo', 'subtitle', 'yes', 'no') if k not in out]
    if missing:
        raise TargetError('%s: missing %s (an empty "@kicker" means no kicker)'
                          % (source, ', '.join('@' + k for k in missing)))
    if len(windows) != 2:
        raise TargetError('%s: @window must be given twice (window lines 1 and 2), not %d times'
                          % (source, len(windows)))
    out['window1'], out['window2'] = windows
    if out['logo'].count('|') > 1:
        raise TargetError('%s: @logo has more than one "|" (fire part|white part)' % source)
    return out


def load_text(path):
    with open(path, encoding='utf-8-sig') as f:
        return parse_text(f.read(), rel(path))


def logo_parts(logo):
    fire, _, white = logo.partition('|')
    return fire.strip(), white.strip()


# ---------------------------------------------------------------------------
# Text-art layers

class Layer:
    """A logo layer: bitmap (160x48), palettes (PaletteBinding per slot), plane,
    wording {'kicker', 'logo', 'subtitle'} from its header, path."""

    def __init__(self, bitmap, palettes, plane, wording, path):
        self.bitmap = bitmap
        self.palettes = palettes
        self.plane = plane
        self.wording = wording
        self.path = path


def parse_wording(text):
    out = {}
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith('#'):
            if s.startswith('@data'):
                break
            continue
        body = s[1:].strip()
        key, colon, value = body.partition(':')
        if colon and key.strip() in WORDING_KEYS:
            out[key.strip()] = value.strip()
    return out


def parse_layer(text, plane, source):
    art = parse_textart(text, source)
    bm = art.bitmap
    if (bm.w, bm.h) != (LOGO_W, LOGO_H):
        raise TargetError('%s: the layer is %dx%d, not %dx%d (map rows %d-%d)'
                          % (source, bm.w, bm.h, LOGO_W, LOGO_H, ROW0, ROW0 + ROWS - 1))
    for p in art.palettes:
        if p.plane != plane or p.number not in LAYER_PALETTES[plane]:
            raise TargetError('%s: palette %s is %s %d; this layer may use %s palettes %s'
                              % (source, p.name, p.plane, p.number, plane,
                                 ', '.join(map(str, LAYER_PALETTES[plane]))))
        for c, rgb in enumerate(p.colors, 1):
            if (p.plane, p.number, c) in KEEP_REQUIRED and rgb is not None:
                raise TargetError('%s: colour %d of %s palette %d must be keep (the flag uses it)'
                                  % (source, c, p.plane, p.number))
    for v in bm.values():
        if v and (v >> 2) >= len(art.palettes):
            raise TargetError('%s: pixel value %d has no palette (slot %d)' % (source, v, v >> 2))
    wording = parse_wording(text)
    missing = [k for k in WORDING_KEYS if k not in wording]
    if missing:
        raise TargetError('%s: the header does not say which wording the art shows (missing %s)'
                          % (source, ', '.join('"# %s:"' % k for k in missing)))
    return Layer(bm, art.palettes, plane, wording, source)


def load_layer(path, plane):
    with open(path, encoding='utf-8-sig') as f:
        return parse_layer(f.read(), plane, rel(path))


def load_layers(root=ROOT):
    return (load_layer(os.path.join(root, FRONT_FILE), 'plane1'),
            load_layer(os.path.join(root, BACK_FILE), 'plane2'))


def check_wording(texts, *layers):
    want = {'kicker': texts['kicker'], 'logo': texts['logo'], 'subtitle': texts['subtitle']}
    for layer in layers:
        for k in WORDING_KEYS:
            if layer.wording[k] != want[k]:
                raise TargetError('title.txt says @%s %r, but %s is drawn for %r: run "python -m tools.gfx.title '
                                  'draft", review the new layers and replace %s'
                                  % (k, want[k], layer.path, layer.wording[k], ART_DIR.replace(os.sep, '/')))


# ---------------------------------------------------------------------------
# Window text

def window_bitmap(font, text, cells_max):
    """The text as Bitmap(8 * n, 8): ink 1 on paper 2, from the pen at x 0 (vwf8 rows 0-7)."""
    if font.height != 8:
        raise TargetError('the window font must have 8 rows, not %d' % font.height)
    ink = []
    pen = 0
    for ch in text:
        rows, adv = font.glyph(ch)
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                if c == '#':
                    ink.append((pen + x, y))
        pen += adv
    width = max([x for x, _ in ink] + [-1]) + 1
    n = max(1, (width + 7) // 8)
    if n > cells_max:
        raise FitError(text, width, 8 * cells_max)
    bm = Bitmap(8 * n, 8, [WIN_PAPER] * (64 * n))
    for x, y in ink:
        bm.set(x, y, WIN_INK)
    return bm, width


# ---------------------------------------------------------------------------
# Encoding

class Plan:
    """Tiles and map entries for the window and both logo layers.

    tiles      [(tile number, 16 bytes)] in allocation order (window first)
    p1, p2     {(row, col): entry} for map rows 7-12 (reserved cells left out)
    win        {(row, col): entry} for window rows 1-3, columns 1-18
    """

    def __init__(self, texts, front, back, wfont):
        self.texts = texts
        bank = TileBank(POOL, flips=True)
        self.win = {}
        self.win_widths = {}
        blank = map_entry(WIN_BLANK, WIN_PAL)
        for row in WIN_ROWS:
            for col in WIN_COLS:
                self.win[(row, col)] = blank
        for key, row, c0, c1 in WIN_ITEMS:
            bm, width = window_bitmap(wfont, texts[key], c1 - c0 + 1)
            self.win_widths[key] = (width, 8 * (c1 - c0 + 1))
            for i, cell in enumerate(cells(bm)):
                if all(v == WIN_PAPER for r in cell for v in r):
                    continue
                t, h, v = bank.add(cell)
                self.win[(row, c0 + i)] = map_entry(t, WIN_PAL, h, v)
        self.window_tiles = len(bank)
        if self.window_tiles > WINDOW_BUDGET:
            raise TargetError('the window text needs %d tiles; the budget is %d'
                              % (self.window_tiles, WINDOW_BUDGET))
        self.p1, self.cells1 = self._layer(front, bank)
        self.p2, self.cells2 = self._layer(back, bank)
        self.logo_tiles = len(bank) - self.window_tiles
        if self.logo_tiles > LOGO_BUDGET:
            raise TargetError('the logo needs %d tiles; the budget is %d' % (self.logo_tiles, LOGO_BUDGET))
        self.tiles = list(zip(bank.used, bank.tiles))
        self.front, self.back = front, back

    @staticmethod
    def _layer(layer, bank):
        entries = {}
        used = 0
        for cell in cells(layer.bitmap):
            row, col = ROW0 + cell.row, cell.col
            try:
                slot = cell_slot(cell)
            except PaletteError as e:
                raise TargetError('%s: map row %d, column %d (x %d-%d, y %d-%d): %s' % (
                    layer.path, row, col, 8 * col, 8 * col + 7, 8 * row, 8 * row + 7, e))
            if (row, col) in RESERVED:
                if slot is not None:
                    raise TargetError('%s: map row %d, column %d is reserved (arm artwork) and must be empty'
                                      % (layer.path, row, col))
                continue
            if slot is None:
                entries[(row, col)] = 0
                continue
            t, h, v = bank.add(cell)
            entries[(row, col)] = map_entry(t, layer.palettes[slot].number, h, v)
            used += 1
        return entries, used

    def palette_writes(self):
        out = []
        for layer, base in ((self.front, P1PAL), (self.back, P2PAL)):
            for p in layer.palettes:
                for c, word in enumerate(p.words(), 1):
                    if word is not None:
                        out.append((base + 8 * p.number + 2 * c, bytes((word & 0xFF, word >> 8))))
        return out

    def writes(self):
        out = [(TILES + 16 * t, data) for t, data in self.tiles]
        for entries, base in ((self.p1, P1MAP), (self.p2, P2MAP)):
            for row in range(ROW0, ROW0 + ROWS):
                for c0, c1 in _segments(row, range(MAP_W)):
                    out.append((base + 2 * (MAP_W * row + c0),
                                b''.join(_le(entries[(row, c)]) for c in range(c0, c1 + 1))))
        for row in WIN_ROWS:
            out.append((WINMAP + 2 * (WIN_W * row + WIN_COLS[0]),
                        b''.join(_le(self.win[(row, c)]) for c in WIN_COLS)))
        out.append((FLAG_LIST, bytes((FLAG_COUNT_NEW,))))
        out += self.palette_writes()
        return sorted(out)

    def stats(self):
        return {'logo tiles': '%d of %d' % (self.logo_tiles, LOGO_BUDGET),
                'window tiles': '%d of %d' % (self.window_tiles, WINDOW_BUDGET),
                'cells': '%d front, %d back' % (self.cells1, self.cells2),
                'palette writes': len(self.palette_writes())}


def _le(v):
    return bytes((v & 0xFF, v >> 8))


def _segments(row, cols):
    """Runs (c0, c1) of the columns of a map row that are not reserved."""
    out = []
    for c in cols:
        if (row, c) in RESERVED:
            continue
        if out and out[-1][1] == c - 1:
            out[-1] = (out[-1][0], c)
        else:
            out.append((c, c))
    return out


def _merge(ranges):
    out = []
    for lo, hi in sorted(ranges):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(hi, out[-1][1]))
        else:
            out.append((lo, hi))
    return out


def ranges():
    """The in-place ranges of this target: [(lo, hi)], hi exclusive."""
    out = [(TILES + 16 * t, TILES + 16 * t + 16) for t in POOL]
    for base in (P1MAP, P2MAP):
        for row in range(ROW0, ROW0 + ROWS):
            for c0, c1 in _segments(row, range(MAP_W)):
                out.append((base + 2 * (MAP_W * row + c0), base + 2 * (MAP_W * row + c1 + 1)))
    for row in WIN_ROWS:
        out.append((WINMAP + 2 * (WIN_W * row + WIN_COLS[0]), WINMAP + 2 * (WIN_W * row + WIN_COLS[-1] + 1)))
    out.append((FLAG_LIST, FLAG_LIST + 1))
    for plane, base in (('plane1', P1PAL), ('plane2', P2PAL)):
        for p in LAYER_PALETTES[plane]:
            for c in (1, 2, 3):
                if (plane, p, c) not in KEEP_REQUIRED:
                    a = base + 8 * p + 2 * c
                    out.append((a, a + 2))
    return _merge(out)


def check_package(read):
    """The package must be the one the addresses describe (read: ctx.read)."""
    for hdr, w, h in ((P1MAP_HDR, MAP_W, MAP_H), (P2MAP_HDR, MAP_W, MAP_H), (WINMAP_HDR, WIN_W, WIN_H)):
        got = tuple(read(hdr, 2))
        if got != (w, h):
            raise TargetError('the map header at %06X is %dx%d, not %dx%d: not the expected title package'
                              % (hdr, got[0], got[1], w, h))
    n = read(FLAG_LIST, 1)[0]
    if n != FLAG_COUNT_OLD:
        raise TargetError('the flag sprite list at %06X has %d records, not %d' % (FLAG_LIST, n, FLAG_COUNT_OLD))


def warn_jump(rom):
    """The instruction at WARN_JUMP in a ROM image, as text ('?' when it does not decode)."""
    try:
        insn = decode(lambda a: rom[a - ROM_BASE], WARN_JUMP)
    except (DecodeError, IndexError):
        return '?'
    return insn.text() if insn.length == WARN_JUMP_LEN else '%s (%d bytes)' % (insn.text(), insn.length)


def make_plan(root=ROOT, text_path=None):
    texts = load_text(text_path or os.path.join(root, 'translation', 'en', TEXT_FILE))
    front, back = load_layers(root)
    check_wording(texts, front, back)
    wfont = load_font(os.path.join(root, WINDOW_FONT))
    return Plan(texts, front, back, wfont)


# ---------------------------------------------------------------------------
# Graphics build

def build(ctx):
    texts = load_text(ctx.translation(TEXT_FILE))
    front = load_layer(ctx.path(FRONT_FILE), 'plane1')
    back = load_layer(ctx.path(BACK_FILE), 'plane2')
    check_wording(texts, front, back)
    check_package(ctx.read)
    plan = Plan(texts, front, back, load_font(ctx.path(WINDOW_FONT)))
    rom = bytearray(ctx.base)
    for addr, data in plan.writes():
        rom[addr - ROM_BASE:addr - ROM_BASE + len(data)] = data
    previews = write_previews(plan, ctx.work, bytes(rom))
    for key, (w, limit) in plan.win_widths.items():
        ctx.log('window %s: %r %d of %d px' % (key, texts[key], w, limit))
    stats = plan.stats()
    stats['bytes'] = sum(len(d) for _, d in plan.writes())
    return Result(writes=plan.writes(), allow=ranges(), previews=previews, stats=stats)


# ---------------------------------------------------------------------------
# Rendering the package (previews and `decode`; ROM-derived images stay local)

class Package:
    """The title package of a ROM image (bytes, CPU address = ROM_BASE + offset)."""

    def __init__(self, rom):
        self.rom = rom

    def u8(self, a):
        return self.rom[a - ROM_BASE]

    def u16(self, a):
        return self.rom[a - ROM_BASE] | (self.rom[a - ROM_BASE + 1] << 8)

    def colour(self, base, pal, c):
        return ngp_to_rgb(self.u16(base + 8 * pal + 2 * c) & 0xFFF)

    def tile(self, t):
        return decode_tile_2bpp(self.rom, TILES - ROM_BASE + 16 * t)

    def map_pixels(self, base, w, h, row0=0):
        """{(x, y): (palette, colour)} of a map block drawn from map row row0."""
        out = {}
        for row in range(h):
            for col in range(w):
                e = self.u16(base + 2 * (w * row + col))
                tile = self.tile(e & 0x1FF)
                for y in range(8):
                    for x in range(8):
                        v = tile[7 - y if e & 0x4000 else y][7 - x if e & 0x8000 else x]
                        if v:
                            out[(8 * col + x, 8 * (row0 + row) + y)] = ((e >> 9) & 15, v)
        return out

    def sprites(self, src, ox, oy, count=None):
        n = self.u8(src) if count is None else count
        out = []
        for i in range(n):
            a = src + 1 + 5 * i
            lo, attr, x, y, pal = (self.u8(a + k) for k in range(5))
            out.append((lo | ((attr & 1) << 8), attr, (x + ox) & 0xFF, (y + oy) & 0xFF, pal & 15))
        return out

    def screen(self, window=False, press=False, sprites=True):
        """The title screen as rows of (r, g, b): background, plane 2, plane 1 (in front),
        then the sprites (in front of both; lower-numbered sprites win)."""
        bg = ngp_to_rgb(self.u16(BG_COLOUR) & 0xFFF)
        img = [[bg] * 160 for _ in range(152)]
        for (x, y), (p, c) in self.map_pixels(P2MAP, MAP_W, MAP_H).items():
            img[y][x] = self.colour(P2PAL, p, c)
        p1 = self.map_pixels(P1MAP, MAP_W, MAP_H)
        if window:
            for key in [k for k in p1 if WIN_SCREEN_ROW * 8 <= k[1] < (WIN_SCREEN_ROW + WIN_H) * 8]:
                del p1[key]
            p1.update(self.map_pixels(WINMAP, WIN_W, WIN_H, WIN_SCREEN_ROW))
        for (x, y), (p, c) in p1.items():
            if y < 152:
                img[y][x] = self.colour(P1PAL, p, c)
        if sprites:
            spr = self.sprites(FLAG_LIST, 0x50, 0)
            if press:
                spr += self.sprites(PRESS_LIST, 0x18, 0x6A)
            done = set()
            for tile, attr, sx, sy, pal in spr:
                data = self.tile(tile)
                for y in range(8):
                    for x in range(8):
                        v = data[7 - y if attr & 0x40 else y][7 - x if attr & 0x80 else x]
                        px, py = sx + x, sy + y
                        if v and px < 160 and py < 152 and (px, py) not in done:
                            done.add((px, py))
                            img[py][px] = self.colour(SPRPAL, pal, v)
        return img


def _scaled(img, scale):
    return [[p for p in row for _ in range(scale)] for row in img for _ in range(scale)]


def save_rgb(path, img, scale=1):
    rows = _scaled(img, scale) if scale != 1 else img
    png.write_rgb(path, len(rows[0]), len(rows), rows, 1)
    return path


def layer_image(layer, rom=None, bg=PREVIEW_BG):
    """One layer over a plain background, in the ROM's colours (keep) or ours."""
    pkg = Package(rom) if rom is not None else None
    img = [[bg] * LOGO_W for _ in range(LOGO_H)]
    for y in range(LOGO_H):
        for x in range(LOGO_W):
            v = layer.bitmap.get(x, y)
            if v:
                p = layer.palettes[v >> 2]
                c = v & 3
                rgb = p.colors[c - 1]
                if rgb is None:
                    if pkg is not None:
                        rgb = pkg.colour(P1PAL if p.plane == 'plane1' else P2PAL, p.number, c)
                    else:
                        rgb = PREVIEW_KEEP.get((p.plane, p.number), [(255, 0, 255)] * 3)[c - 1]
                img[y][x] = rgb
    return img


def layers_image(front, back, rom=None, bg=PREVIEW_BG):
    """Both layers composed (plane 1 in front) over a plain background."""
    img = layer_image(back, rom, bg)
    top = layer_image(front, rom, bg)
    for y in range(LOGO_H):
        for x in range(LOGO_W):
            if front.bitmap.get(x, y):
                img[y][x] = top[y][x]
    return img


def write_previews(plan, folder, rom=None):
    """Previews of our art; with rom (the patched ROM image) also the whole screen
    and the window as the package draws them (local only). Returns the paths."""
    os.makedirs(folder, exist_ok=True)
    paths = []
    img = layers_image(plan.front, plan.back, rom)
    paths.append(save_rgb(os.path.join(folder, 'logo.png'), img))
    paths.append(save_rgb(os.path.join(folder, 'logo_4x.png'), img, 4))
    if rom is not None:
        pkg = Package(rom)
        paths.append(save_rgb(os.path.join(folder, 'title.png'), pkg.screen(), 2))
        paths.append(save_rgb(os.path.join(folder, 'window.png'), pkg.screen(window=True), 2))
    return paths


# ---------------------------------------------------------------------------
# Draft: draw the layers from title.txt and the fonts

def _noise(x, y, seed):
    h = hashlib.blake2b(b'%d,%d,%d' % (x, y, seed), digest_size=4).digest()
    return int.from_bytes(h, 'little') / 2 ** 32


def _smooth9(points, seed, own):
    """Value noise over a pixel set: own * noise + (1 - own) * mean of the 3x3 neighbourhood."""
    n = {p: _noise(p[0], p[1], seed) for p in points}
    out = {}
    for (x, y), v in n.items():
        nb = [n[(x + dx, y + dy)] for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (x + dx, y + dy) in n]
        out[(x, y)] = own * v + (1 - own) * sum(nb) / len(nb)
    return out


def _smooth5(points, seed, own):
    """As _smooth9, with the 4 neighbours."""
    n = {p: _noise(p[0], p[1], seed) for p in points}
    out = {}
    for (x, y), v in n.items():
        nb = [n[q] for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if q in n]
        out[(x, y)] = own * v + (1 - own) * (sum(nb) / len(nb) if nb else v)
    return out


def _by_share(scores, shares):
    """Colours 1-3 by rank: the highest scores get colour 1 (shares: fractions of 1, 2, 3)."""
    order = sorted(scores, key=lambda p: (-scores[p], p))
    a = round(len(order) * shares[0])
    b = a + round(len(order) * shares[1])
    return {p: 1 if i < a else (2 if i < b else 3) for i, p in enumerate(order)}


def fire_fill(mask, allfill, seed, shares, top=None, bottom=None, edges=True):
    """Mottled fire: value noise, a little brighter inside the strokes, darker on
    the edges (right and bottom more; edges=False: not) and on the glyphs' first
    and last rows (top, bottom: those screen rows), then colours by share."""
    s = _smooth9(mask, seed, 0.4)
    sc = {}
    for (x, y) in mask:
        v = s[(x, y)]
        if edges:
            r, b = (x + 1, y) not in allfill, (x, y + 1) not in allfill
            l, t = (x - 1, y) not in allfill, (x, y - 1) not in allfill
            if not (r or b or l or t):
                v += FIRE_IN
            v -= FIRE_RB * (r + b) + FIRE_LT * (l + t)
        if bottom is not None and y >= bottom:
            v -= FIRE_BOTTOM
        if top is not None and y <= top:
            v -= FIRE_TOP
        sc[(x, y)] = v
    return _by_share(sc, shares)


def white_fill(mask, allfill, seed, shares):
    """Metal: light grey patches in white, greyer towards the right and bottom
    edges of the strokes, whiter towards the left and top."""
    s = _smooth5(mask, seed, 0.5)
    sc = {}
    for (x, y) in mask:
        e = WHITE_R * ((x + 1, y) not in allfill) + WHITE_B * ((x, y + 1) not in allfill) \
            - WHITE_L * ((x - 1, y) not in allfill) - WHITE_T * ((x, y - 1) not in allfill)
        sc[(x, y)] = s[(x, y)] - e
    return _by_share(sc, shares)


def outline_corners(ink, ring, seed):
    """The diagonal neighbours of the ink that the original outlines also fill:
    those between two ink diagonals (a step of a slanted edge) and about one in
    four outer corners (CORNER_SHARE, by a hash of the position). ring: the
    4-neighbour outline already drawn."""
    out = set()
    for (x, y) in ink:
        for dx, dy in D4:
            q = (x + dx, y + dy)
            if q in ink or q in ring or q in out:
                continue
            diag = sum((q[0] + a, q[1] + b) in ink for a, b in D4)
            if diag >= 2 or _noise(q[0], q[1], seed) < CORNER_SHARE:
                out.add(q)
    return out


def sub_outline(ink, seed=SEED_SUB):
    """The subtitle: amber ink (colour 2) with a brown outline (colour 1) on its 4
    neighbours and on outline_corners, inside SUB_ROWS. Returns {pixel: colour}."""
    out = {p: 2 for p in ink}
    for (x, y) in ink:
        for dx, dy in N4:
            q = (x + dx, y + dy)
            if q not in ink and SUB_ROWS[0] <= q[1] < SUB_ROWS[1]:
                out[q] = 1
    ring = {q for q, c in out.items() if c == 1}
    for q in outline_corners(ink, ring, seed):
        if SUB_ROWS[0] <= q[1] < SUB_ROWS[1]:
            out[q] = 1
    return out


def outer_side(fill, q):
    """The side of the lettering a glow pixel is on: 'below', 'above', 'left' or
    'right' when the fill lies in one direction only (within OUTER_RAY px, straight
    up, down, left or right), None (enclosed) when in more. With none straight, the
    fill diagonally next to it decides: only above ('below', e.g. under a letter's
    corner) or only below ('above'); else 'corner'."""
    x, y = q
    hits = [side for side, (dx, dy) in (('below', (0, -1)), ('above', (0, 1)), ('right', (-1, 0)),
                                        ('left', (1, 0)))
            if any((x + k * dx, y + k * dy) in fill for k in range(1, OUTER_RAY + 1))]
    if hits:
        return hits[0] if len(hits) == 1 else None
    up = any((x + k * dx, y - k) in fill for dx in (-1, 1) for k in range(1, OUTER_RAY + 1))
    down = any((x + k * dx, y + k) in fill for dx in (-1, 1) for k in range(1, OUTER_RAY + 1))
    if up != down:
        return 'below' if up else 'above'
    return 'corner'


def glow_rings(fill, allowed, seed, outline_only=None):
    """The outline and glow of the original logo: ring 1 (4 neighbours) black,
    plus the diagonal corners of outline_corners; then by the side of the
    lettering (outer_side): on the outer edges ring 2 blue or cyan and ring 3
    blue, cyan or empty by the shares of OUTER_GLOW, ring 4 a few blue pixels
    above the letters; in enclosed places ring 2 cyan (blue where the glow is
    weak or at the band's edges), ring 3 cyan, blue or empty where surrounded,
    blue or empty elsewhere, ring 4 a few cyan and blue pixels (ENCLOSED_RING3,
    ENCLOSED_OPEN, RING4). 'Strength' is smooth value noise, by rank.
    allowed(q): plane-2 pixels the outline and glow may use; outline_only(q): of
    those, the ones for the black ring only. Returns {pixel: colour}."""
    taken = set(fill)
    rings = []
    front = set(fill)
    for k in range(4):
        r = set()
        for (x, y) in front:
            for dx, dy in N4:
                q = (x + dx, y + dy)
                if q not in taken and allowed(q) and (k == 0 or outline_only is None or not outline_only(q)):
                    r.add(q)
        taken |= r
        rings.append(r)
        front = r
    raw = _smooth9(rings[1] | rings[2] | rings[3], seed, 0.3)
    order = sorted(raw, key=lambda p: (raw[p], p))
    strength = {p: i / max(1, len(order) - 1) for i, p in enumerate(order)}
    side = {q: outer_side(fill, q) for q in rings[1] | rings[2] | rings[3]}

    def cut(q):
        """Next to the edge of the glow band (map row 7's top, the original's left and
        right extent): the glow ends in blue there."""
        x, y = q
        return any(not (GLOW_ROWS[0] <= y + dy < GLOW_ROWS[1] and GLOW_X[0] <= x + dx < GLOW_X[1])
                   for dx, dy in N4)

    out = {q: 3 for q in rings[0]}
    corners = outline_corners(set(fill), rings[0], seed + 7)
    for q in rings[1]:
        if q in corners:
            out[q] = 3
        elif side[q]:
            out[q] = 1 if strength[q] < OUTER_GLOW[side[q]][0] else 2
        else:
            out[q] = 1 if strength[q] < 0.2 or cut(q) else 2
    inner = set(fill) | rings[0] | rings[1] | rings[2]
    for q in rings[2]:
        x, y = q
        s = strength[q]
        if side[q]:
            _, blue, cyan = OUTER_GLOW[side[q]]
            if s > 1 - cyan:
                out[q] = 2
            elif s > 1 - cyan - blue:
                out[q] = 1
        elif cut(q):
            if s > 0.35:
                out[q] = 1
        elif all((x + dx, y + dy) in inner for dx, dy in N4):
            if s > ENCLOSED_RING3[0]:
                out[q] = 2
            elif s > ENCLOSED_RING3[1]:
                out[q] = 1
        elif s > ENCLOSED_OPEN:
            out[q] = 1
    for q in rings[3]:
        x, y = q
        s = strength[q]
        nb = [out.get((x + dx, y + dy)) for dx, dy in N4]
        if side[q] is None:
            if s > RING4[0] and 2 in nb:
                out[q] = 2
            elif s > RING4[1] and (1 in nb or 2 in nb):
                out[q] = 1
        elif side[q] in ('above', 'corner') and s > RING4_OUTER and (1 in nb or 2 in nb):
            out[q] = 1
    for q in rings[2] | rings[3]:       # no cyan pixel without cyan or black next to it
        x, y = q
        if out.get(q) == 2 and not any(out.get((x + dx, y + dy)) == 2 or (x + dx, y + dy) in rings[0]
                                       for dx, dy in N4):
            out[q] = 1
    return out


def _ink(font, text, x0, y0, spacing):
    """Ink pixels of a line (pen layout with extra spacing after every advance)."""
    out = set()
    pen = x0
    for ch in text:
        rows, adv = font.glyph(ch)
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                if c == '#':
                    out.add((pen + x, y0 + y))
        pen += adv + spacing
    return out


def _extent(ink):
    xs = [x for x, _ in ink]
    return (min(xs), max(xs)) if xs else (0, -1)


def place_logo(font, fire, white):
    """(x of the fire part, x of the white part or None): the white part starts on
    a cell boundary (one palette per cell), WORD_GAP px after the fire part, and
    the whole line is as close to the band's centre as the limits allow."""
    wf = _extent(_ink(font, fire, 0, 0, MAIN_SPACING))[1] + 1 if fire else 0
    if not white:
        x = int(BAND_CENTRE + 0.5 - wf / 2)
        if x < FILL_MIN or x + wf - 1 > FILL_MAX:
            raise FitError(fire, wf, FILL_MAX - FILL_MIN + 1)
        return x, None
    ww = _extent(_ink(font, white, 0, 0, MAIN_SPACING))[1] + 1
    best = None
    for xw in range(8, 160, 8):
        xf = xw - WORD_GAP - wf if fire else xw
        if xf < FILL_MIN or xw + ww - 1 > FILL_MAX:
            continue
        score = abs((xf + xw + ww - 1) / 2 - BAND_CENTRE)
        if best is None or score < best[0]:
            best = (score, xf, xw)
    if best is None:
        raise FitError('%s|%s' % (fire, white), wf + WORD_GAP + ww, FILL_MAX - FILL_MIN + 1)
    return best[1], best[2]


def draft(texts, root=ROOT):
    """Draw both layers from the texts: (front Bitmap, back Bitmap, info lines)."""
    main = load_font(os.path.join(root, LOGO_FONT))
    kick = load_font(os.path.join(root, KICKER_FONT))
    sub = load_font(os.path.join(root, SUB_FONT))
    info = []
    fire_text, white_text = logo_parts(texts['logo'])
    has_kicker = bool(texts['kicker'])
    y_main, y_sub = Y_MAIN, Y_SUB
    xf, xw = place_logo(main, fire_text, white_text)
    fire = _ink(main, fire_text, xf, y_main, MAIN_SPACING) if fire_text else set()
    white = _ink(main, white_text, xw, y_main, MAIN_SPACING) if white_text else set()
    info.append('logo: %r x %d-%d, %r x %d-%d, glyph rows y %d-%d' % (
        fire_text, *_extent(fire), white_text, *_extent(white), y_main, y_main + main.height - 1))
    # the letters stop at the thumb of the fist (its holes show the background)
    hidden = {q for q in fire | white if in_thumb(q)}
    fire -= hidden
    white -= hidden
    if hidden:
        info.append('thumb: %d fill px left out (x %d-%d, y %d-%d)' % (
            len(hidden), THUMB[0], THUMB[2], THUMB[1], THUMB[3]))
    kicker = set()
    if has_kicker:
        kicker = _ink(kick, texts['kicker'], xf, Y_KICK, 0)
        k0, k1 = _extent(kicker)
        if k1 > KICK_MAX:
            raise FitError(texts['kicker'], k1 - k0 + 1, KICK_MAX - xf + 1)
        info.append('kicker: %r x %d-%d, y %d-%d' % (texts['kicker'], k0, k1, Y_KICK, Y_KICK + kick.height - 1))
    allfill = fire | white | kicker
    front = Bitmap(LOGO_W, LOGO_H)

    def put(bm, pixels, base):
        for (x, y), c in pixels.items():
            if not (0 <= x < LOGO_W and LOGO_Y <= y < LOGO_Y + LOGO_H):
                raise FitError(texts['logo'], LOGO_W, LOGO_W, 'pixel (%d, %d) is outside the band' % (x, y))
            bm.set(x, y - LOGO_Y, base + c)

    put(front, fire_fill(fire, allfill, SEED_FIRE, FIRE_FRAC, y_main, y_main + main.height - 1), 0)
    put(front, white_fill(white, allfill, SEED_WHITE, WHITE_FRAC), 4)
    put(front, fire_fill(kicker, allfill, SEED_KICK, KICK_FRAC, edges=False), 0)

    def allowed(q):
        x, y = q
        return (GLOW_X[0] <= x < GLOW_X[1] and GLOW_ROWS[0] <= y < GLOW_ROWS[1] and q not in allfill
                and (y // 8, x // 8) not in RESERVED)

    back = Bitmap(LOGO_W, LOGO_H)
    put(back, glow_rings(allfill, allowed, SEED_GLOW, in_thumb), 0)
    # subtitle: thin italic capitals, amber, with a brown outline, centred
    ink = _ink(sub, texts['subtitle'], 0, y_sub, 0)
    w = _extent(ink)[1] + 1
    x0 = int(BAND_CENTRE + 0.5 - w / 2)
    ink = {(x + x0, y) for x, y in ink}
    s0, s1 = _extent(ink)
    if s0 < 1 or s1 > LOGO_W - 2:
        raise FitError(texts['subtitle'], w + 2, LOGO_W)
    info.append('subtitle: %r x %d-%d, y %d-%d (with the outline x %d-%d)' % (
        texts['subtitle'], s0, s1, y_sub, y_sub + sub.height - 1, s0 - 1, s1 + 1))
    put(back, sub_outline(ink), 4)
    return front, back, info


def draft_text(bitmap, palettes, chars, texts, what):
    comments = ['title screen logo, %s: map rows %d-%d (y %d-%d), drawn by python -m tools.gfx.title draft'
                % (what, ROW0, ROW0 + ROWS - 1, LOGO_Y, LOGO_Y + LOGO_H - 1),
                'from translation/en/title.txt and our own fonts (assets/font/logo19.txt,',
                'assets/gfx/title/kicker5.txt, assets/gfx/title/italic9.txt). Our own art (MIT).',
                'The build checks that these three lines match title.txt:',
                'kicker: %s' % texts['kicker'],
                'logo: %s' % texts['logo'],
                'subtitle: %s' % texts['subtitle'],
                'Palettes: "keep" uses the colours of the original title screen.']
    chars = {ch: v for ch, v in chars.items() if v == 0 or (v >> 2) < len(palettes)}
    return format_textart(bitmap, palettes, chars, comments)


def write_draft(texts, outdir, root=ROOT):
    front, back, info = draft(texts, root)
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for name, bm, pals, chars, what in (
            ('logo_front.txt', front, FRONT_PALETTES, FRONT_CHARS, 'plane 1 (fill: fire, white)'),
            ('logo_back.txt', back, BACK_PALETTES, BACK_CHARS, 'plane 2 (outline and glow, subtitle)')):
        path = os.path.join(outdir, name)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(draft_text(bm, pals, chars, texts, what))
        paths.append(path)
    return paths, info


# ---------------------------------------------------------------------------
# Harness dumps

def check_dump(m, rom, window=False):
    """(ok, lines) for one --vram dump against the ROM's package."""
    lines, ok = [], True
    tiles = rom[TILES - ROM_BASE:TILES - ROM_BASE + 0x2000]
    bad = [t for t in range(512) if m[0xA000 + 16 * t:0xA010 + 16 * t] != tiles[16 * t:16 * t + 16]]
    ok &= not bad
    lines.append('tiles: %s' % ('VRAM 0xA000-0xBFFF equals ROM %06X' % TILES if not bad else
                                '%d tiles differ (first %03X)' % (len(bad), bad[0])))

    def block(vbase, rbase, w, h, row0=0, rows=None):
        diff = []
        for r in rows if rows is not None else range(h):
            for c in range(w):
                va = vbase + 2 * (32 * (row0 + r) + c)
                if m[va] | (m[va + 1] << 8) != rom[rbase - ROM_BASE + 2 * (w * r + c)] | \
                        (rom[rbase - ROM_BASE + 2 * (w * r + c) + 1] << 8):
                    diff.append((r, c))
        return diff

    # With the window open the menu is up too: it draws its label maps into plane-2 rows 13-14.
    p1_skip = range(WIN_SCREEN_ROW, WIN_SCREEN_ROW + WIN_H) if window else ()
    p2_skip = MENU_ROWS if window else ()
    for name, vbase, rbase, skip, why in (('plane 1', 0x9000, P1MAP, p1_skip, 'the window'),
                                          ('plane 2', 0x9800, P2MAP, p2_skip, 'the menu labels')):
        diff = block(vbase, rbase, MAP_W, MAP_H, 0, [r for r in range(MAP_H) if r not in skip])
        ok &= not diff
        note = ' (rows %d-%d not compared: %s)' % (skip[0], skip[-1], why) if skip else ''
        lines.append('%s map: %s' % (name, 'equals ROM %06X%s' % (rbase, note) if not diff else
                                     '%d entries differ (rows %s)' % (len(diff), sorted({r for r, _ in diff}))))
    if window:
        diff = block(0x9000, WINMAP, WIN_W, WIN_H, WIN_SCREEN_ROW)
        ok &= not diff
        lines.append('window map at 0x9340: %s' % ('equals ROM %06X' % WINMAP if not diff else
                                                    '%d entries differ' % len(diff)))
    return ok, lines


def _dump_paths(items):
    paths = []
    for item in items:
        if os.path.isdir(item):
            paths += sorted(os.path.join(item, f) for f in os.listdir(item)
                            if f.startswith('mem_') and f.endswith('.bin'))
        else:
            paths.append(item)
    return paths


# ---------------------------------------------------------------------------
# Command line

def fit_lines(plan):
    lines = []
    for key, (w, limit) in plan.win_widths.items():
        lines.append('window %-8s %-34r %3d of %3d px' % (key, plan.texts[key], w, limit))
    lines.append('logo: %d front cells, %d back cells; tiles: logo %d of %d, window %d of %d, pool %d'
                 % (plan.cells1, plan.cells2, plan.logo_tiles, LOGO_BUDGET, plan.window_tiles, WINDOW_BUDGET,
                    len(POOL)))
    for layer in (plan.front, plan.back):
        lines.append('%s: %s' % (layer.path, ', '.join('%s = %s palette %d (%s)' % (
            p.name, p.plane, p.number, ' '.join('keep' if c is None else '#%02X%02X%02X' % c for c in p.colors))
            for p in layer.palettes)))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.gfx.title', description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('fit', help='widths, cells, palettes and the tile budget (no ROM needed)')
    p = sub.add_parser('draft', help='draw both logo layers from title.txt (text-art)')
    p.add_argument('outdir', nargs='?', default=os.path.join(ROOT, 'build', 'gfx', 'title', 'draft'))
    p = sub.add_parser('preview', help='our layers as PNG (with --rom: the whole screen, local only)')
    p.add_argument('outdir')
    p.add_argument('--rom', help='the original ROM: compose our art into its title package')
    p = sub.add_parser('decode', help="a ROM's title screen and window as PNG (local only)")
    p.add_argument('rom')
    p.add_argument('outdir')
    p = sub.add_parser('check', help='harness --vram dumps: VRAM tiles and maps equal the ROM package')
    p.add_argument('rom', help='the ROM the harness ran')
    p.add_argument('dumps', nargs='+', help='mem_NNNNN.bin files or folders')
    p.add_argument('--window', action='store_true', help='the warning window is open: check its map')
    p = sub.add_parser('warn-test', help='test ROM only: NewGame always opens the warning window')
    p.add_argument('inp')
    p.add_argument('out')
    args = ap.parse_args(argv)
    try:
        if args.cmd == 'draft':
            texts = load_text(os.path.join(ROOT, 'translation', 'en', TEXT_FILE))
            paths, info = write_draft(texts, args.outdir)
            print('\n'.join(info))
            for path in paths:
                print('wrote %s' % path)
            return 0
        if args.cmd == 'warn-test':
            rom = bytearray(open(args.inp, 'rb').read())
            got = warn_jump(rom)
            if got != WARN_JUMP_TEXT:
                print('error: %s has %r at %06X, not the expected jump %r'
                      % (args.inp, got, WARN_JUMP, WARN_JUMP_TEXT), file=sys.stderr)
                return 1
            o = WARN_JUMP - ROM_BASE
            rom[o:o + WARN_JUMP_LEN] = bytes(WARN_JUMP_LEN)       # NOP (0x00) for each byte
            with open(args.out, 'wb') as f:
                f.write(rom)
            print('wrote %s (2 NOPs at %06X: NewGame and Load always open the warning window; test only)'
                  % (args.out, WARN_JUMP))
            return 0
        if args.cmd == 'decode':
            rom = open(args.rom, 'rb').read()
            os.makedirs(args.outdir, exist_ok=True)
            pkg = Package(rom)
            for name, img in (('title', pkg.screen()), ('title_press', pkg.screen(press=True)),
                              ('window', pkg.screen(window=True))):
                for scale in (1, 3):
                    path = os.path.join(args.outdir, '%s%s.png' % (name, '' if scale == 1 else '_%dx' % scale))
                    save_rgb(path, img, scale)
                    print('wrote %s' % path)
            return 0
        if args.cmd == 'check':
            rom = open(args.rom, 'rb').read()
            ok = True
            paths = _dump_paths(args.dumps)
            if not paths:
                print('error: no dumps', file=sys.stderr)
                return 1
            for path in paths:
                with open(path, 'rb') as f:
                    m = f.read()
                if len(m) != 0x10000:
                    print('%s: not a --vram dump (%d bytes)' % (path, len(m)))
                    ok = False
                    continue
                good, lines = check_dump(m, rom, args.window)
                ok &= good
                print('%s:' % os.path.basename(path))
                print('\n'.join('  ' + s for s in lines))
            print('check: %s' % ('ok' if ok else 'FAILED'))
            return 0 if ok else 1
        plan = make_plan()
        if args.cmd == 'fit':
            print('\n'.join(fit_lines(plan)))
            return 0
        # preview
        rom = None
        if args.rom:
            rom = bytearray(open(args.rom, 'rb').read())
            for addr, data in plan.writes():
                rom[addr - ROM_BASE:addr - ROM_BASE + len(data)] = data
            rom = bytes(rom)
        for path in write_previews(plan, args.outdir, rom):
            print('wrote %s' % path)
        return 0
    except (TargetError, ValueError, OSError) as e:
        print('error: %s' % e, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
