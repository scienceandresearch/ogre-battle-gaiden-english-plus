"""Chapter title cards in English (graphics target 'cards').

When a stage starts, the card scene shows the chapter's title card: an emblem
on scroll plane 2 and the lettering on plane 1. There are two sets of 20 cards
(chapter = RAM 0x5490, 1-20): the story set the first time a chapter is
played, and the area set when a cleared chapter is played again (bit
chapter - 1 of the cleared-stage bits at RAM 0x546E). Notes:
docs/workstreams/gfx-chapter-cards.md.

Sources
    translation/en/cards.txt     the English text (format below)
    assets/font/title16.txt      the 11-row display font
    patch/src/cards.asm          two hooks and three routines (hand-written)
Generated, in ctx.work (build/gfx/cards/)
    data.asm                     card_story (at GFX_CARDS) and card_area (at
                                 GFX_CARDS + 0x50): 20 record pointers each, then
                                 the records; included by patch/src/cards.asm
    preview.png                  the English cards, for review

cards.txt
    [story N] or [area N]        starts card N (1-20) of a set
    ^text                        the heading line (at most one, before the title)
    text                         the title line (one)
    same N                       the card is card N of the same set (one record)
    Lines starting with '#' and blank lines are ignored.

Layout and style: the original lettering's
    * The lettering stays inside the original block: 12 x 4 cells at plane-1
      column 4, row 8 (screen x 32-127, y 64-95). A card is a 160 x 32 canvas
      = screen rows 8-11, in two 16-px bands: band 0 (rows 8-9) holds the
      heading, band 1 (rows 10-11) the title; a card without a heading leaves
      band 0 empty, as the original cards 14-20 and the area cards do.
      Plane-1 palette 0 is the game's text palette, which stays unchanged.
    * Glyph row 0 sits on row 2 of the heading band and on row 4 of the title
      band, as the original glyphs do: ink in band rows 2-12 / 4-14, outline
      in rows 1-13 / 3-15 (title16: capitals in glyph rows 0-8, descenders 9-10).
    * Every line is centred on the screen, x = (160 - width) // 2, as the
      original lines are centred in their 96-px block (columns 4-15).
    * Ink is colour 1, with a 1-px outline in colour 3 grown to 4 neighbours.
      The heading's digits have 2-px strokes (textart bold), like the
      original chapter numbers. Colour 2 is not used.
    * Words are 4 px apart (SPACE advance 3 instead of title16's 4), which
      leaves 2 px between the outlines of two words.
    * Limits: a line is at most 96 px wide with its outline (the width of the
      original block); a card has at most one heading line and one title line.

Records (sub-region GFX_CARDS)
    .dl tiles, .dw words (8 per tile), .dw plane-1 map address (0x9000 +
    64 * row + 2 * column), .db w, h, then w * h map entries (palette 0;
    tiles from 0x44, the order of first use; 0 = blank, the emblem's blank
    tile 0), then the tiles (16 bytes each; identical tiles are shared within
    a card). The map block of every record is the original block (12 x 4 at
    column 4, row 8: map address 0x9208), so a card writes the same 48 map
    entries as the original layout did. VRAM holds tiles 0x44-0x1AB for the
    card (360 tiles); a card uses at most 48.

Command line
    python -m tools.gfx.cards fit                        widths, tiles and sizes (no ROM needed)
    python -m tools.gfx.cards preview OUTDIR [--rom ROM] the English cards (preview.png, 1x and 3x)
    python -m tools.gfx.cards decode ROM OUTDIR          the original cards, for review (local only)
    python -m tools.gfx.cards check ROM [DIR]            the records in ROM; with DIR, the VRAM dumps
                                                         DIR/<set>_NN/mem_00200.bin of the card runs
    python -m tools.gfx.cards recipe TEST REF OUTDIR --state S [--exe H]
                                                         the harness acceptance recipe (gfx-pipeline.md 5)

recipe makes the 40 card states (S, a stage0_selected.state, poked to each
chapter and set), runs them on TEST (the ROM with the cards) and REF (the
same ROM without them), checks VRAM against the records and RAM against REF,
compares the screens outside the original lettering block, runs the sequence
check (S with no input and with A at frame 45, 120 or 200), and writes
contact sheets and side-by-side sheets (REF | TEST, 1x and 3x). The harness
is --exe, else NGP_HARNESS, else build/ngp_harness.exe. Everything in OUTDIR
shows original art: keep it local (build/ or a scratch folder), never in the
repository.
"""
import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from ..common import png
from ..recomp.rom import ROM_BASE
from . import harness
from .build import SUBREGIONS
from .font import Font, Glyph, load_font
from .image import Bitmap, ngp_to_rgb
from .target import Result, TargetError
from .textart import FitError, Style, embolden, measure, render_box
from .tiles import TileBank, cells, map_entry

# Part of the full build: enabled by the verify step (gfx-verify, 2026-10-10)
# together with the other graphics targets.
FULL_BUILD = True

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TEXT_FILE = os.path.join(ROOT, 'translation', 'en', 'cards.txt')
FONT = 'title16'
FONT_FILE = os.path.join(ROOT, 'assets', 'font', FONT + '.txt')
ASM_ENTRY = os.path.join('patch', 'src', 'cards.asm')

# Style (see the module notes)
STYLE = Style(ink=1, outline=3, outline8=False)
BOLD_DIGITS = True              # heading digits with 2-px strokes
SPACE_ADVANCE = 3               # px; a 4-px word gap (1 px after the last letter + 3)
PALETTE = 0                     # plane-1 palette of the map entries (the text palette)

# Layout: the original lettering block, and the bands inside it
ORIG_BLOCK = (4, 8, 12, 4)      # column, row, w, h (cells) of the original layout on plane 1
SCREEN_W = 160
BAND_H = 16
BANDS = 2                       # heading band (rows 8-9), title band (rows 10-11)
TOP_ROW = ORIG_BLOCK[1]         # screen cell row of band 0
BAND_TOPS = (2, 4)              # band row of glyph row 0, per band
MAX_LINE = 8 * ORIG_BLOCK[2]    # 96 px, outline included: the width of the original block
MAX_HEADINGS, MAX_TITLES = 1, 1
BLOCK_RECT = (8 * ORIG_BLOCK[0], 8 * ORIG_BLOCK[1], 8 * (ORIG_BLOCK[0] + ORIG_BLOCK[2]) - 1,
              8 * (ORIG_BLOCK[1] + ORIG_BLOCK[3]) - 1)          # (32, 64, 127, 95), inclusive
SCENE_Y = (64, 111)             # screen rows 8-13: the spec's lettering area (the outside must not change)
SHEET_Y = (56, 119)             # rows shown in the side-by-side sheets

# VRAM and records
FIRST_TILE, LAST_TILE = 0x44, 0x1AB
MAX_TILES = LAST_TILE - FIRST_TILE + 1          # 360: the VRAM the original sheet fills
ORIG_COPY_WORDS = 8 * MAX_TILES                 # 0xB40: what the original loader copies (and the hook too)
PLANE1 = 0x9000
VRAM_TILES = 0xA000 + 16 * FIRST_TILE           # 0xA440
SETS = ('story', 'area')
CHAPTERS = 20
SUBREGION = 'GFX_CARDS'
TABLE_STORY, TABLE_AREA = 0, 0x50               # offsets of the tables in GFX_CARDS
HOOKS = ((0x29ECB4, 6), (0x29EDD4, 6))          # (address, bytes) of the two hooks
CODE_RESERVE = 0x100                            # room kept for the routines after the data

# The original card data (read by `decode`, the checks and the hook at run time; never copied here).
TEXT_PALETTE = 0x29EF02                         # plane-1 palette 0 of the scene (4 words)
ORIG_SETS = {'story': (0x29F34A, 0x29EEA2), 'area': (0x2A09CA, 0x29EECA)}   # tile sheet, layout table
ORIG_LAYOUT_RAM = 0x6080                        # where the original loader copies the layout record
ORIG_LAYOUT_WORDS = 0x31                        # [w][h] + 48 entries

# Preview colours when no ROM is given (our own values; with a ROM the text palette is used)
PREVIEW_RGB = {0: (20, 20, 28), 1: (255, 255, 255), 2: (170, 170, 221), 3: (40, 56, 160)}
PREVIEW_GAP = (70, 70, 70)


# ---------------------------------------------------------------------------
# cards.txt

class Card:
    """One card of cards.txt: heading (text or None), titles [text], same (N or None)."""
    __slots__ = ('set', 'n', 'heading', 'titles', 'same', 'where')

    def __init__(self, set_, n, where):
        self.set, self.n, self.where = set_, n, where
        self.heading = None
        self.titles = []
        self.same = None

    @property
    def lines(self):
        return ([self.heading] if self.heading is not None else []) + self.titles

    def __repr__(self):
        return '<Card %s %d %s>' % (self.set, self.n, 'same %d' % self.same if self.same else ' / '.join(self.lines))


_HEADER = re.compile(r'^\[\s*(story|area)\s+(\d+)\s*\]$')
_SAME = re.compile(r'^same\s+(\d+)$')


def parse_cards(text, source='cards.txt'):
    """{(set, n): Card} for every card of both sets; TargetError on any problem."""
    cards = {}
    cur = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        where = '%s:%d' % (source, lineno)
        if not line or line.startswith('#'):
            continue
        m = _HEADER.match(line)
        if m:
            key = (m.group(1), int(m.group(2)))
            if not 1 <= key[1] <= CHAPTERS:
                raise TargetError('%s: card number %d is not 1-%d' % (where, key[1], CHAPTERS))
            if key in cards:
                raise TargetError('%s: [%s %d] is defined twice' % (where, key[0], key[1]))
            cur = cards[key] = Card(key[0], key[1], where)
            continue
        if line.startswith('['):
            raise TargetError('%s: bad card header %r (expected [story N] or [area N])' % (where, line))
        if cur is None:
            raise TargetError('%s: text before the first card header' % where)
        m = _SAME.match(line)
        if m:
            if cur.lines or cur.same is not None:
                raise TargetError('%s: "same N" must be the only line of a card' % where)
            cur.same = int(m.group(1))
            continue
        if cur.same is not None:
            raise TargetError('%s: "same N" must be the only line of a card' % where)
        if line.startswith('^'):
            head = line[1:].strip()
            if not head:
                raise TargetError('%s: empty heading' % where)
            if cur.heading is not None:
                raise TargetError('%s: a card has at most %d heading line' % (where, MAX_HEADINGS))
            if cur.titles:
                raise TargetError('%s: the heading must come before the title line' % where)
            cur.heading = head
            continue
        if len(cur.titles) >= MAX_TITLES:
            raise TargetError('%s: a card has at most %d title line (the original lettering block holds a '
                              'heading and one title line)' % (where, MAX_TITLES))
        cur.titles.append(line)
    for s in SETS:
        for n in range(1, CHAPTERS + 1):
            card = cards.get((s, n))
            if card is None:
                raise TargetError('%s: [%s %d] is missing' % (source, s, n))
            if card.same is not None:
                other = cards.get((s, card.same))
                if card.same == n or other is None or other.same is not None:
                    raise TargetError('%s: "same %d" must name another card of the %s set that has text'
                                      % (card.where, card.same, s))
            elif not card.titles:
                raise TargetError('%s: [%s %d] has no title line' % (card.where, s, n))
    return cards


def load_cards(path=TEXT_FILE):
    with open(path, encoding='utf-8-sig') as f:
        return parse_cards(f.read(), os.path.relpath(path, ROOT) if path.startswith(ROOT) else path)


# ---------------------------------------------------------------------------
# Rendering and encoding

def card_font(font):
    """The title font of the cards: font with a SPACE advance of SPACE_ADVANCE (4-px word gaps)."""
    space = font.glyphs.get('SPACE')
    if space is None or space.advance == SPACE_ADVANCE:
        return font
    glyphs = dict(font.glyphs)
    glyphs['SPACE'] = Glyph(space.rows, SPACE_ADVANCE)
    return Font(glyphs, font.height, font.name + '+card space', font.path)


def heading_font(font):
    """The heading font: the card font with 2-px digit strokes (textart.embolden), like the
    original chapter numbers."""
    font = card_font(font)
    if not BOLD_DIGITS:
        return font
    glyphs = dict(font.glyphs)
    for d in '0123456789':
        if d in glyphs:
            rows, adv = embolden(d, glyphs[d].rows, glyphs[d].advance)
            glyphs[d] = Glyph(rows, adv)
    return Font(glyphs, font.height, font.name + '+bold digits', font.path)


def card_fonts(font):
    """(title font, heading font) of the cards, from the base font (title16)."""
    return card_font(font), heading_font(font)


def card_lines(card, font, hfont):
    """[(band, text, font)] of a card (not a 'same' card)."""
    out = []
    if card.heading is not None:
        out.append((0, card.heading, hfont))
    for i, text in enumerate(card.titles):
        out.append((1 + i, text, font))
    return out


def render_card(card, font, hfont):
    """(Bitmap 160 x 32 of pixel values 0, 1, 3: screen rows 8-11, [(band, text, width)]).
    font and hfont are the card fonts (card_fonts)."""
    bm = Bitmap(SCREEN_W, BAND_H * BANDS)
    widths = []
    for band, text, f in card_lines(card, font, hfont):
        w = measure(f, text, STYLE)
        if w > MAX_LINE:
            raise FitError(text, w, MAX_LINE, 'it is %d px wide; the original lettering block is %d px'
                           % (w, MAX_LINE))
        bm.blit(render_box(f, text, STYLE, SCREEN_W, BAND_H, 'center', BAND_TOPS[band]), 0, BAND_H * band)
        widths.append((band, text, w))
    return bm, widths


class Record:
    """A card record: the map block (col, row, w, h: screen cells; entries) and its tiles."""
    __slots__ = ('label', 'keys', 'col', 'row', 'w', 'h', 'entries', 'tiles', 'bitmap', 'widths')

    def __init__(self, label, col, row, w, h, entries, tiles, bitmap=None, widths=()):
        self.label, self.col, self.row, self.w, self.h = label, col, row, w, h
        self.entries, self.tiles, self.bitmap, self.widths = list(entries), list(tiles), bitmap, list(widths)
        self.keys = []          # (set, n) of the cards that use it

    @property
    def mapaddr(self):
        return PLANE1 + 64 * self.row + 2 * self.col

    @property
    def words(self):
        return 8 * len(self.tiles)

    @property
    def size(self):
        return 10 + 2 * len(self.entries) + 16 * len(self.tiles)

    def tile_bytes(self):
        return b''.join(self.tiles)

    def to_bytes(self, tiles_addr):
        out = bytearray(tiles_addr.to_bytes(4, 'little'))
        out += self.words.to_bytes(2, 'little') + self.mapaddr.to_bytes(2, 'little') + bytes((self.w, self.h))
        for e in self.entries:
            out += e.to_bytes(2, 'little')
        return bytes(out)

    def same_as(self, other):
        return (self.mapaddr, self.w, self.h, self.entries, self.tiles) == \
            (other.mapaddr, other.w, other.h, other.entries, other.tiles)

    def __repr__(self):
        return '<Record %s %dx%d at col %d row %d, %d tiles>' % (self.label, self.w, self.h, self.col, self.row,
                                                                 len(self.tiles))


def encode_card(bm, label='card'):
    """Record of a card canvas (160 x 32, screen rows 8-11): the original 12 x 4 block, identical
    tiles shared, blank cells 0. TargetError if lettering lies outside the block."""
    col0, row0, bw, bh = ORIG_BLOCK
    if (bm.w, bm.h) != (SCREEN_W, 8 * bh):
        raise TargetError('%s: the canvas is %dx%d, not %dx%d' % (label, bm.w, bm.h, SCREEN_W, 8 * bh))
    cols = SCREEN_W // 8
    grid = cells(bm)
    lit = [c for c in grid if any(v for row in c for v in row)]
    if not lit:
        raise TargetError('%s: the card has no lettering' % label)
    out = [c for c in lit if not col0 <= c.col < col0 + bw]
    if out:
        raise TargetError('%s: lettering in cell column %d, outside the original block (columns %d-%d)'
                          % (label, out[0].col, col0, col0 + bw - 1))
    bank = TileBank(range(FIRST_TILE, LAST_TILE + 1))
    entries = []
    for r in range(bh):                 # canvas row r = screen row TOP_ROW + r = row0 + r
        for c in range(col0, col0 + bw):
            cell = grid[r * cols + c]
            if any(v for row in cell for v in row):
                tile, hflip, vflip = bank.add(cell)
                entries.append(map_entry(tile, PALETTE, hflip, vflip))
            else:
                entries.append(0)
    return Record(label, col0, row0, bw, bh, entries, bank.tiles, bm)


class Generated:
    """The result of generate(): records (distinct, in table order), table {(set, n): Record},
    asm (data.asm text), size (bytes of the tables and records)."""

    def __init__(self, records, table, asm):
        self.records = records
        self.table = table
        self.asm = asm
        self.size = 8 * CHAPTERS + sum(r.size for r in records)

    @property
    def tiles(self):
        return sum(len(r.tiles) for r in self.records)

    def widths(self):
        """[(record, band, text, px)] of every line."""
        return [(r, band, text, w) for r in self.records for band, text, w in r.widths]


def generate(cards, font):
    """Render and encode every card (font: title16); returns Generated. Raises FitError,
    BudgetError, MissingGlyphError or TargetError."""
    tfont, hfont = card_fonts(font)
    records, table = [], {}
    for s in SETS:
        for n in range(1, CHAPTERS + 1):
            card = cards[(s, n)]
            if card.same is not None:
                continue
            bm, widths = render_card(card, tfont, hfont)
            rec = encode_card(bm, 'card_%s_%02d' % (s, n))
            rec.widths = widths
            records.append(rec)
            table[(s, n)] = rec
        for n in range(1, CHAPTERS + 1):
            card = cards[(s, n)]
            if card.same is not None:
                table[(s, n)] = table[(s, card.same)]
            table[(s, n)].keys.append((s, n))
    gen = Generated(records, table, None)
    gen.asm = data_asm(gen, cards)
    lo, hi = SUBREGIONS[SUBREGION]
    if gen.size + CODE_RESERVE > hi - lo:
        raise TargetError('the cards need %d bytes (and %d for the code); %s has %d'
                          % (gen.size, CODE_RESERVE, SUBREGION, hi - lo))
    return gen


def _describe(card):
    return ' / '.join(card.lines)


def data_asm(gen, cards):
    """The generated data.asm (tables, then the records)."""
    out = ['; Generated by tools/gfx/cards.py from translation/en/cards.txt and assets/font/%s.txt.' % FONT,
           '; Rewritten by every build; do not edit. Included by patch/src/cards.asm at %s.' % SUBREGION,
           '; %d records, %d tiles, %d bytes.' % (len(gen.records), gen.tiles, gen.size)]
    for s, offset in (('story', TABLE_STORY), ('area', TABLE_AREA)):
        out.append('card_%s:%s; %s + 0x%02X' % (s, ' ' * (32 - len('card_%s:' % s)), SUBREGION, offset))
        for n in range(1, CHAPTERS + 1):
            rec = gen.table[(s, n)]
            card = cards[(s, n)]
            note = 'same as %d' % card.same if card.same is not None else _describe(card)
            out.append('        .dl     %-23s ; %d: %s' % (rec.label, n, note))
    for rec in gen.records:
        out.append('')
        out.append('%s:%s; %s' % (rec.label, ' ' * max(1, 32 - len(rec.label) - 1),
                                  ' / '.join(text for _, text, _ in rec.widths)))
        out.append('        .dl     %s_tiles' % rec.label)
        out.append('        .dw     0x%04X                  ; %d tiles' % (rec.words, len(rec.tiles)))
        out.append('        .dw     0x%04X                  ; plane 1, row %d, column %d'
                   % (rec.mapaddr, rec.row, rec.col))
        out.append('        .db     %d, %d' % (rec.w, rec.h))
        for i in range(0, len(rec.entries), rec.w):
            out.append('        .dw     ' + ', '.join('0x%04X' % e for e in rec.entries[i:i + rec.w]))
        out.append('%s_tiles:' % rec.label)
        for t in rec.tiles:
            out.append('        .db     ' + ', '.join('0x%02X' % b for b in t))
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------------------
# Previews

def preview_rgb(rom=None):
    """{pixel: rgb}: the game's text palette when rom (the original or any build) is given."""
    if rom is None:
        return dict(PREVIEW_RGB)
    off = TEXT_PALETTE - ROM_BASE
    words = [rom[off + 2 * i] | (rom[off + 2 * i + 1] << 8) for i in range(4)]
    rgb = {c: ngp_to_rgb(words[c]) for c in (1, 2, 3)}
    rgb[0] = PREVIEW_RGB[0]
    return rgb


def preview_image(gen, rgb, cols=2):
    """(w, h, rows): every distinct card canvas, cols per row, with grey gaps; a darker
    frame marks the original lettering block."""
    gap = 4
    cw, ch = SCREEN_W + gap, BAND_H * BANDS + gap
    nrows = (len(gen.records) + cols - 1) // cols
    w, h = cols * cw + gap, nrows * ch + gap
    img = [[PREVIEW_GAP] * w for _ in range(h)]
    x0, x1 = BLOCK_RECT[0], BLOCK_RECT[2]
    for k, rec in enumerate(gen.records):
        ox, oy = gap + (k % cols) * cw, gap + (k // cols) * ch
        bm = rec.bitmap
        for y in range(bm.h):
            row = bm.row(y)
            img[oy + y][ox:ox + bm.w] = [rgb[v] if v or x0 <= x <= x1 else (8, 8, 12) for x, v in enumerate(row)]
    return w, h, img


def write_previews(gen, folder, rgb):
    os.makedirs(folder, exist_ok=True)
    w, h, img = preview_image(gen, rgb)
    paths = []
    for scale, name in ((1, 'preview.png'), (3, 'preview_3x.png')):
        path = os.path.join(folder, name)
        png.write_rgb(path, w, h, img, scale)
        paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# Target entry point

def build(ctx):
    font = ctx.font(FONT)
    path = ctx.translation('cards.txt')
    with open(path, encoding='utf-8-sig') as f:
        cards = parse_cards(f.read(), 'translation/en/cards.txt')
    gen = generate(cards, font)
    ctx.write_file('data.asm', gen.asm)
    previews = write_previews(gen, ctx.work, preview_rgb(ctx.base))
    widest = max(w for _, _, _, w in gen.widths())
    ctx.log('%d records (%d cards), %d tiles, %s bytes; widest line %d px (block %d); most tiles in a card %d'
            % (len(gen.records), 2 * CHAPTERS, gen.tiles, format(gen.size, ','), widest, MAX_LINE,
               max(len(r.tiles) for r in gen.records)))
    return Result(asm=ctx.path(ASM_ENTRY), previews=previews,
                  stats={'records': len(gen.records), 'tiles': gen.tiles, 'bytes': gen.size})


# ---------------------------------------------------------------------------
# Reading records back from a ROM, checking harness dumps

def _u16(data, off):
    return data[off] | (data[off + 1] << 8)


def _u32(data, off):
    return int.from_bytes(data[off:off + 4], 'little')


def read_record(rom, addr):
    """The record at CPU address addr of a ROM image (bytes): Record (label = its address)."""
    off = addr - ROM_BASE
    if not 0 <= off < len(rom) - 10:
        raise ValueError('record address %06X is outside the ROM' % addr)
    tiles_addr, words, mapaddr = _u32(rom, off), _u16(rom, off + 4), _u16(rom, off + 6)
    w, h = rom[off + 8], rom[off + 9]
    if not (1 <= w <= 32 and 1 <= h <= 32) or words % 8 or not PLANE1 <= mapaddr < PLANE1 + 0x800:
        raise ValueError('record %06X: bad header (%d words, map %04X, %dx%d)' % (addr, words, mapaddr, w, h))
    entries = [_u16(rom, off + 10 + 2 * i) for i in range(w * h)]
    toff = tiles_addr - ROM_BASE
    if not 0 <= toff <= len(rom) - 2 * words:
        raise ValueError('record %06X: tiles at %06X are outside the ROM' % (addr, tiles_addr))
    tiles = [bytes(rom[toff + 16 * i:toff + 16 * i + 16]) for i in range(words // 8)]
    cell = (mapaddr - PLANE1) // 2
    return Record('%06X' % addr, cell % 32, cell // 32, w, h, entries, tiles)


def read_tables(rom):
    """{(set, n): (record address, Record)} from the card tables in a built ROM."""
    base = SUBREGIONS[SUBREGION][0]
    out = {}
    for s, offset in (('story', TABLE_STORY), ('area', TABLE_AREA)):
        for n in range(1, CHAPTERS + 1):
            addr = _u32(rom, base + offset + 4 * (n - 1) - ROM_BASE)
            out[(s, n)] = (addr, read_record(rom, addr))
    return out


def check_rom(rom, gen):
    """Errors (list of str) where the ROM's card tables and records differ from gen."""
    errors = []
    try:
        got = read_tables(rom)
    except ValueError as e:
        return ['card tables: %s' % e]
    addrs = {}
    for key, rec in gen.table.items():
        addr, have = got[key]
        if not have.same_as(rec):
            errors.append('%s %d: the record at %06X differs from the sources' % (key[0], key[1], addr))
        addrs.setdefault(rec.label, set()).add(addr)
    for label, a in addrs.items():
        if len(a) != 1:
            errors.append('%s: the cards that share it point to %d different records' % (label, len(a)))
    return errors


def check_dump(mem, rec):
    """Errors where a --vram dump (64 KB) does not show the record: the tiles at VRAM 0xA440,
    the map block on plane 1, and nothing else on plane 1."""
    errors = []
    data = rec.tile_bytes()
    if bytes(mem[VRAM_TILES:VRAM_TILES + len(data)]) != data:
        first = next(i for i in range(len(data)) if mem[VRAM_TILES + i] != data[i]) // 16
        errors.append('VRAM tile %03X differs from the record' % (FIRST_TILE + first))
    block = {}
    for i, e in enumerate(rec.entries):
        block[((rec.row + i // rec.w) & 31, (rec.col + i % rec.w) & 31)] = e
    bad = []
    for r in range(32):
        for c in range(32):
            e = _u16(mem, PLANE1 + 64 * r + 2 * c)
            if e != block.get((r, c), 0):
                bad.append((r, c, e, block.get((r, c), 0)))
    if bad:
        r, c, e, want = bad[0]
        errors.append('%d plane-1 map entries differ (first at row %d col %d: %04X, expected %04X)'
                      % (len(bad), r, c, e, want))
    return errors


# What must equal REF in the frame-200 dumps: everything the scene leaves alone, plus what the
# hooks recreate as the original did (the layout copy at 0x6080, the sheet's tiles after the card's)
SAME_AS_REF = (('main RAM', 0x4000, 0x7000), ('palettes', 0x8200, 0x8400), ('sprites', 0x8800, 0x8900),
               ('plane-2 map', 0x9800, 0xA000), ('emblem tiles', 0xA000, VRAM_TILES))


def check_dump_ref(mem, ref, rec):
    """Errors where a TEST dump differs from the REF dump outside the card itself: SAME_AS_REF,
    and VRAM tiles 0x44 + (tiles of the card) to 0x1AB (the rest of the original sheet)."""
    errors = []
    for name, lo, hi in SAME_AS_REF + (('VRAM tiles after the card', VRAM_TILES + 16 * len(rec.tiles),
                                        VRAM_TILES + 2 * ORIG_COPY_WORDS),):
        if bytes(mem[lo:hi]) != bytes(ref[lo:hi]):
            first = next(i for i in range(lo, hi) if mem[i] != ref[i])
            errors.append('%s differ from REF (first at %04X)' % (name, first))
    return errors


def lettering_rects(rec=None):
    """Screen rectangles (inclusive) where the cards may differ from REF: the original lettering
    block only (every record's block is that block)."""
    return [BLOCK_RECT]


# ---------------------------------------------------------------------------
# The originals (decode, review only)

def decode_original(rom, set_, n):
    """(w, h, pixel rows 0-3) of the original card n of a set, from its layout record and sheet."""
    sheet, table = ORIG_SETS[set_]
    off = table - ROM_BASE
    rec = table + _u16(rom, off + 2 * (n - 1)) - ROM_BASE
    w, h = rom[rec], rom[rec + 1]
    img = [[0] * (8 * w) for _ in range(8 * h)]
    for i in range(w * h):
        e = _u16(rom, rec + 2 + 2 * i)
        t = e & 0x1FF
        if not t:
            continue
        toff = sheet - ROM_BASE + 16 * (t - FIRST_TILE)
        tile = [[(_u16(rom, toff + 2 * y) >> (14 - 2 * x)) & 3 for x in range(8)] for y in range(8)]
        for y in range(8):
            for x in range(8):
                xx = 7 - x if e & 0x8000 else x
                yy = 7 - y if e & 0x4000 else y
                img[8 * (i // w) + y][8 * (i % w) + x] = tile[yy][xx]
    return 8 * w, 8 * h, img


def cmd_decode(rom, out):
    os.makedirs(out, exist_ok=True)
    rgb = preview_rgb(rom)
    for s in SETS:
        seen = {}
        sheet = []
        for n in range(1, CHAPTERS + 1):
            table = ORIG_SETS[s][1]
            addr = table + _u16(rom, table - ROM_BASE + 2 * (n - 1))
            if addr in seen:
                print('%s %d: same layout as %d' % (s, n, seen[addr]))
                continue
            seen[addr] = n
            w, h, img = decode_original(rom, s, n)
            rows = [[rgb[v] for v in r] for r in img]
            png.write_rgb(os.path.join(out, 'orig_%s_%02d.png' % (s, n)), w, h, rows, 4)
            sheet += rows + [[PREVIEW_GAP] * w] * 2
        png.write_rgb(os.path.join(out, 'orig_%s.png' % s), len(sheet[0]), len(sheet), sheet, 2)
    print('wrote the original cards to %s (local only: never commit them)' % out)
    return 0


# ---------------------------------------------------------------------------
# The harness recipe

def _sheet_pairs(pairs, path, scale, per_row):
    """Side-by-side sheet: pairs [(rows_a, rows_b)] of equal-size crops, per_row pairs per row."""
    gap = 4
    ch, cw = len(pairs[0][0]), len(pairs[0][0][0])
    pw = 2 * cw + gap
    w = per_row * (pw + 3 * gap) + gap
    nrows = (len(pairs) + per_row - 1) // per_row
    h = nrows * (ch + gap) + gap
    img = [[PREVIEW_GAP] * w for _ in range(h)]
    for k, (a, b) in enumerate(pairs):
        ox, oy = gap + (k % per_row) * (pw + 3 * gap), gap + (k // per_row) * (ch + gap)
        for y in range(ch):
            img[oy + y][ox:ox + cw] = a[y]
            img[oy + y][ox + cw + gap:ox + 2 * cw + gap] = b[y]
    png.write_rgb(path, w, h, img, scale)
    return path


def cmd_recipe(test, ref, out, exe=None, state=None, frame=200, jobs=8):
    """Run the cards recipe; returns (errors, report lines)."""
    cards = load_cards()
    gen = generate(cards, load_font(FONT_FILE))
    if not state or not os.path.isfile(state):
        raise TargetError('--state must name a stage0_selected.state of the harness (got %r)' % state)
    rom = open(test, 'rb').read()
    errors = ['ROM: %s' % e for e in check_rom(rom, gen)]
    report = ['ROM %s: card tables and %d records %s' % (os.path.basename(test), len(gen.records),
                                                         'match the sources' if not errors else 'DIFFER')]
    states = os.path.join(out, 'states')
    os.makedirs(states, exist_ok=True)
    keys = [(s, n) for s in SETS for n in range(1, CHAPTERS + 1)]

    def poked(key):
        s, n = key
        path = os.path.join(states, 'st_%s_%02d.state' % key)
        bits = (1 << (n - 1)) if s == 'area' else 0
        harness.poke(state, path, {0x5490: bytes((n,)), 0x546E: bits.to_bytes(4, 'little')})
        return path

    def run_card(args):
        tag, rom_path, key = args
        d = os.path.join(out, tag, '%s_%02d' % key)
        harness.run(rom_path, d, frames=frame + 1, shots=[frame], vram=[frame],
                    load_state=os.path.join(states, 'st_%s_%02d.state' % key), exe=exe)
        return d

    for key in keys:
        poked(key)
    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(run_card, [(tag, path, key) for tag, path in (('test', test), ('ref', ref)) for key in keys]))
    shot = 'frame_%05d.png' % frame
    pairs = {s: [] for s in SETS}
    fulls = {s: [] for s in SETS}
    for key in keys:
        rec = gen.table[key]
        tdir = os.path.join(out, 'test', '%s_%02d' % key)
        rdir = os.path.join(out, 'ref', '%s_%02d' % key)
        mem = open(os.path.join(tdir, 'mem_%05d.bin' % frame), 'rb').read()
        rmem = open(os.path.join(rdir, 'mem_%05d.bin' % frame), 'rb').read()
        errs = check_dump(mem, rec) + check_dump_ref(mem, rmem, rec)
        n_scene, _ = harness.diff_png(os.path.join(tdir, shot), os.path.join(rdir, shot),
                                      [(0, SCENE_Y[0], SCREEN_W - 1, SCENE_Y[1])])
        n_block, box = harness.diff_png(os.path.join(tdir, shot), os.path.join(rdir, shot), lettering_rects(rec))
        if n_scene:
            errs.append('%d pixels differ from REF outside y %d-%d' % (n_scene, SCENE_Y[0], SCENE_Y[1]))
        if n_block:
            errs.append('%d pixels differ from REF outside the original lettering block (within %s)'
                        % (n_block, box))
        report.append('%s %2d: %-40s tiles %2d, map %dx%d at col %d row %d: %s' % (
            key[0], key[1], ' / '.join(cards[key].lines) if cards[key].same is None else 'same as %d' % cards[key].same,
            len(rec.tiles), rec.w, rec.h, rec.col, rec.row, 'ok' if not errs else '; '.join(errs)))
        errors += ['%s %d: %s' % (key[0], key[1], e) for e in errs]
        sa, ra = harness.read_screen(os.path.join(rdir, shot))
        sb, rb = harness.read_screen(os.path.join(tdir, shot))
        crop = lambda rows, s: [r[::s] for r in rows[::s][SHEET_Y[0]:SHEET_Y[1] + 1]]
        pairs[key[0]].append((crop(ra, sa), crop(rb, sb)))
        fulls[key[0]].append(([r[::sa] for r in ra[::sa]], [r[::sb] for r in rb[::sb]]))
    sheets = []
    for s in SETS:
        folder = os.path.join(out, 'sheet_%s' % s)
        os.makedirs(folder, exist_ok=True)
        for n in range(1, CHAPTERS + 1):
            with open(os.path.join(out, 'test', '%s_%02d' % (s, n), shot), 'rb') as f:
                data = f.read()
            with open(os.path.join(folder, 'frame_%05d.png' % n), 'wb') as f:
                f.write(data)
        sheets.append(harness.contact_sheet(folder, None, os.path.join(out, 'sheet_%s.png' % s), 5)[0])
        sheets.append(_sheet_pairs(pairs[s], os.path.join(out, 'compare_%s_1x.png' % s), 1, 2))
        for part in range(2):
            sheets.append(_sheet_pairs(pairs[s][10 * part:10 * part + 10],
                                       os.path.join(out, 'compare_%s_3x_%d.png' % (s, part + 1)), 3, 1))
        sheets.append(_sheet_pairs(fulls[s], os.path.join(out, 'compare_%s_full.png' % s), 1, 2))
    # Sequence: the stage-0 card with no input and with A at 45, 120 or 200
    seq = [None, '45:A:2', '120:A:2', '200:A:2']
    shots = [400, 600, 900]

    def run_seq(args):
        tag, rom_path, k = args
        d = os.path.join(out, 'seq', '%s_%d' % (tag, k))
        harness.run(rom_path, d, frames=max(shots) + 1, shots=shots, inputs=seq[k], load_state=state, exe=exe)
        return d

    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(run_seq, [(tag, path, k) for tag, path in (('test', test), ('ref', ref))
                              for k in range(len(seq))]))
    for k, inp in enumerate(seq):
        diffs = []
        for f in shots:
            name = 'frame_%05d.png' % f
            n, _ = harness.diff_png(os.path.join(out, 'seq', 'test_%d' % k, name),
                                    os.path.join(out, 'seq', 'ref_%d' % k, name))
            diffs.append(n)
        ok = not any(diffs)
        report.append('sequence (%s): shots %s: %s' % (inp or 'no input', ', '.join(map(str, shots)),
                                                       'identical' if ok else 'differ %s' % diffs))
        if not ok:
            errors.append('sequence %s: %s differing pixels at %s' % (inp or 'no input', diffs, shots))
    report.append('sheets: %s' % ', '.join(os.path.basename(p) for p in sheets))
    return errors, report


# ---------------------------------------------------------------------------
# Command line

def cmd_fit():
    cards = load_cards()
    font = load_font(FONT_FILE)
    try:
        gen = generate(cards, font)
    except (ValueError, TargetError) as e:
        print('error: %s' % e)
        return 1
    print('%-14s %-5s %4s  %s' % ('record', 'tiles', 'px', 'line'))
    for rec in gen.records:
        first = True
        for band, text, w in rec.widths:
            print('%-14s %-5s %4d  %s%s' % (rec.label if first else '', len(rec.tiles) if first else '', w,
                                            '^' if band == 0 else '', text))
            first = False
    widest = max(w for _, _, _, w in gen.widths())
    lo, hi = SUBREGIONS[SUBREGION]
    print('%d records for %d cards, %d tiles (at most %d in a card), %s bytes of %s in %s'
          % (len(gen.records), 2 * CHAPTERS, gen.tiles, max(len(r.tiles) for r in gen.records),
             format(gen.size, ','), format(hi - lo - CODE_RESERVE, ','), SUBREGION))
    print('widest line %d px (limit %d: the original lettering block, %d x %d cells at column %d, row %d)'
          % (widest, MAX_LINE, ORIG_BLOCK[2], ORIG_BLOCK[3], ORIG_BLOCK[0], ORIG_BLOCK[1]))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, 'reconfigure'):          # card texts may hold characters the console lacks
        try:
            sys.stdout.reconfigure(errors='replace')
        except (OSError, ValueError):
            pass
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == 'fit':
            return cmd_fit()
        if cmd == 'preview':
            ap = argparse.ArgumentParser(prog='python -m tools.gfx.cards preview')
            ap.add_argument('out')
            ap.add_argument('--rom')
            args = ap.parse_args(rest)
            gen = generate(load_cards(), load_font(FONT_FILE))
            rom = open(args.rom, 'rb').read() if args.rom else None
            for p in write_previews(gen, args.out, preview_rgb(rom)):
                print('wrote %s' % p)
            return 0
        if cmd == 'decode':
            if len(rest) != 2:
                print('usage: python -m tools.gfx.cards decode ROM OUTDIR', file=sys.stderr)
                return 2
            return cmd_decode(open(rest[0], 'rb').read(), rest[1])
        if cmd == 'check':
            if len(rest) not in (1, 2):
                print('usage: python -m tools.gfx.cards check ROM [DIR]', file=sys.stderr)
                return 2
            gen = generate(load_cards(), load_font(FONT_FILE))
            errors = check_rom(open(rest[0], 'rb').read(), gen)
            print('ROM: %s' % ('the card tables and %d records match the sources' % len(gen.records)
                                if not errors else '; '.join(errors)))
            if len(rest) == 2:
                for s in SETS:
                    for n in range(1, CHAPTERS + 1):
                        d = os.path.join(rest[1], '%s_%02d' % (s, n))
                        dumps = sorted(f for f in os.listdir(d) if f.startswith('mem_')) if os.path.isdir(d) else []
                        if not dumps:
                            continue
                        mem = open(os.path.join(d, dumps[-1]), 'rb').read()
                        errs = check_dump(mem, gen.table[(s, n)])
                        print('%s %2d %s: %s' % (s, n, dumps[-1], 'ok' if not errs else '; '.join(errs)))
                        errors += errs
            return 1 if errors else 0
        if cmd == 'recipe':
            ap = argparse.ArgumentParser(prog='python -m tools.gfx.cards recipe')
            ap.add_argument('test')
            ap.add_argument('ref')
            ap.add_argument('out')
            ap.add_argument('--exe')
            ap.add_argument('--state', required=True)
            ap.add_argument('--jobs', type=int, default=8)
            args = ap.parse_args(rest)
            errors, report = cmd_recipe(args.test, args.ref, args.out, args.exe, args.state, jobs=args.jobs)
            print('\n'.join(report))
            print('%s: %d errors' % ('FAILED' if errors else 'passed', len(errors)))
            for e in errors[:40]:
                print('  ' + e)
            return 1 if errors else 0
    except (TargetError, harness.HarnessError, ValueError, OSError) as e:
        print('error: %s' % e, file=sys.stderr)
        return 1
    print('unknown command %r (fit, preview, decode, check, recipe)' % cmd, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
