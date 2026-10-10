"""Intro narration (graphics target 'intro'): the text crawl after power-on.

After the publisher logo, 15 pre-drawn lines of narration scroll up over a
cloud picture before the title screen. This target replaces them with English
rendered from translation/en/intro.txt. Notes: docs/workstreams/gfx-intro-narration.md.

Source format (translation/en/intro.txt): one text line per bitmap line, a
blank line between paragraphs, '#' at the start of a comment line. Three
paragraphs of 6, 6 and 3 lines keep the original layout; any other structure
selects the relocated layout.

Style (STYLE, TOP): the treatment of the original lettering. 1-px strokes in
colour 1 (white) with a 1-px outline in colour 3 (blue) on the 4 orthogonal
neighbours, in the title16 font, centred in the 144 x 16 line, glyph row 0 on
line row 4: ink rows 4-14 and outline rows 3-15, the rows of the original
lettering. The text palette (PALETTE) is kept as it is.

Modes:
* in place (the original structure): line n is written over the original
  bitmap at LINES + LINE_BYTES * n. No hooks, no new ROM; the original line
  table and narration map stay in use.
* relocated (any other structure): lines 0-14 are written in place; a new
  line table, a new narration map and the bitmaps of lines 15 and up go to
  GFX_INTRO through the generated build/gfx/intro/intro.asm, which also
  repoints three operands (HOOKS).

Layout rules (both modes; the generator reproduces the original table and
map byte for byte from the original structure): triggers are scroll
positions, multiples of 8, 24 px apart in a paragraph and 64 px between
paragraphs; line n goes to VRAM slot n mod 5, so a line must start at least
120 px after the line five places before it (a line leaves the window 120 px
after its trigger); the crawl ends at the last trigger + 136; the map has one
row of 20 entries per 8 px of scroll up to the end, plus 4 blank rows. Each
extra line makes the crawl 24 px (about 4.3 s) longer.

    python -m tools.gfx.intro fit [TEXT]                 widths, structure, mode, layout
    python -m tools.gfx.intro preview OUTDIR [TEXT]      our English lines as PNGs (no ROM needed)
    python -m tools.gfx.intro decode ROM OUTDIR          the lines a ROM shows, as PNGs (local only)
    python -m tools.gfx.intro compare ROM OUTDIR [TEXT]  the ROM's lines next to ours, 1x and 3x (local only)
    python -m tools.gfx.intro check ROM DUMPDIR [--ref REFDIR] [--expect default|F:SLOTS;...]
    python -m tools.gfx.intro testrom IN OUT [--text TEXT] [--base ROM]   a test ROM with another text

check reads the line table that the ROM's operand points to, then for each
harness --vram dump in DUMPDIR (mem_NNNNN.bin) names the line held by each of
the 5 VRAM slots ('-' = empty, '?' = something else) and compares them with
the lines the crawl has loaded at that moment (the crawl task's table
pointer in RAM); slots not loaded yet may hold anything. A line that has not
yet left the screen must still be in its slot. --expect adds fixed
expectations ('default': the in-place recipe, 1200:0 1 2 3 -;2400:5 6 2 3 4;
3600:10 11 7 8 9;4800:10 11 12 13 14). With --ref (a run of the unmodified
ROM with the same shots and dumps), each frame_NNNNN.png must equal the
reference outside the text rows of the lines on screen (rows 3-15 of each
line box, x 8-151), placed from the crawl position in the dump of the same
frame. A frame whose dump has no crawl task (logo, title) must be identical
on the whole screen; a shot without a dump is compared outside the whole
text band (x 8-151, y 24-127). Exit status 1 on any mismatch.

testrom runs this target with another source text through the standalone
apply path (tools.gfx.apply), for scratch tests of the relocated layout; its
work folder is build/gfx/intro-test/. The build never uses it.
"""
import argparse
import os
import sys

from ..recomp.rom import ROM_BASE
from .target import Result, TargetError
from .textart import FitError, Style, measure, render_box
from .tiles import tiles_lines

# Part of the full build: enabled by the verify step (gfx-verify, 2026-10-10)
# together with the other graphics targets.
FULL_BUILD = True

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TEXT_FILE = 'intro.txt'
SOURCE = 'translation/en/' + TEXT_FILE

# ---------------------------------------------------------------------------
# Style: the treatment of the original lettering

FONT = 'title16'
STYLE = Style(ink=1, outline=3, outline8=False)     # white ink, blue outline on the 4 orthogonal neighbours
TOP = 4                     # line row of glyph row 0: ink rows 4-14, outline rows 3-15
LINE_W, LINE_H = 144, 16    # one line: 18 x 2 cells
ALIGN = 'center'

# ---------------------------------------------------------------------------
# ROM layout (CPU addresses)

PALETTE = 0x290F55          # text palette (4 words), kept: colour 1 strokes, colour 3 outline
LINES = 0x290F5D            # line n at LINES + LINE_BYTES * n, n = 0-14
LINE_BYTES = 0x240          # 36 tiles: the top 18 left to right, then the bottom 18
INPLACE_LINES = 15
TABLE = 0x28D1EA            # line table: [u16 trigger][u16 VRAM dest][u24 source] per line, then 0xFFFF
MAP = 0x293DDD              # narration map: 20 entries per 8 px of scroll
END = 0x228                 # scroll position where the crawl ends (552)
STRUCTURE = (6, 6, 3)       # the original paragraphs
SKY = 0x29311D              # cloud palette word 0, also the background colour (local previews only)

# Operands repointed by the relocated layout: (operand address, size, original
# value, address of the instruction, the instruction as the disassemblers print it)
HOOK_TABLE = 0x28D0A3
HOOK_END = 0x28D0B7
HOOK_MAP = 0x28D0E2
HOOKS = (
    (HOOK_TABLE, 4, TABLE, 0x28D0A2, 'stv32 0x28d1ea, 0x28'),   # script op: line table -> task var 0x28
    (HOOK_END, 2, END, 0x28D0B5, 'cp.w WA, 0x228'),             # per-frame loop: end of the crawl
    (HOOK_MAP, 4, MAP, 0x28D0E1, 'ld.l XIY, 0x293DDD'),         # per-frame loop: narration map
)

# ---------------------------------------------------------------------------
# Crawl layout

SLOTS = (0xA010, 0xA250, 0xA490, 0xA6D0, 0xA910)    # VRAM line slots: tiles 0x01, 0x25, 0x49, 0x6D, 0x91
PITCH = 24                  # trigger step between lines of a paragraph
GAP = 64                    # trigger step from the last line of a paragraph to the next
TAIL = 136                  # end position = last trigger + TAIL
VISIBLE = 120               # a line leaves the window this many px after its trigger
SPARE_ROWS = 4              # blank map rows after the last row the crawl reads
MAP_W = 20                  # map entries per row: columns 0 and 19 blank, 1-18 the line
WINDOW = (24, 127)          # screen rows of the crawl window
TEXT_X = (8, 151)           # screen columns of the line boxes (map columns 1-18)
TEXT_ROWS = (3, 15)         # rows of a line box that lettering uses (the original's and ours)
TASKS, TASK_BASE, TASK_SIZE = 16, 0x4086, 0x38      # task slots in RAM (for check)
VAR_POS, VAR_SPEED, VAR_TABLE = 32, 36, 40          # crawl task: var 0x20 position (16.16), 0x24 speed, 0x28 table


# ---------------------------------------------------------------------------
# Source text

def parse(text, source=SOURCE):
    """Paragraphs of the source: [[(line number, text), ...], ...]."""
    paras, cur = [], []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if line.lstrip().startswith('#'):
            continue
        if not line.strip():
            if cur:
                paras.append(cur)
                cur = []
            continue
        if line != line.strip():
            raise TargetError('%s:%d: leading spaces in %r (lines are centred automatically)' % (source, n, line))
        cur.append((n, line))
    if cur:
        paras.append(cur)
    if not paras:
        raise TargetError('%s: no text' % source)
    return paras


def read_text(path):
    with open(path, encoding='utf-8-sig') as f:
        return f.read()


def structure(paras):
    return tuple(len(p) for p in paras)


def is_inplace(paras):
    return structure(paras) == STRUCTURE


ASCII_FORMS = ((0x2026, '...'), (0x201C, '"'), (0x201D, '"'), (0x2018, "'"), (0x2019, "'"))


def ascii_text(text):
    """The text for a console that may not print the ellipsis and curly quotes."""
    for code, plain in ASCII_FORMS:
        text = text.replace(chr(code), plain)
    return text.encode('ascii', 'replace').decode()


# ---------------------------------------------------------------------------
# Rendering

def render_line(font, text, source=SOURCE, lineno=None):
    """The line as a 144 x 16 Bitmap (pixels 0, 1, 3)."""
    try:
        return render_box(font, text, STYLE, LINE_W, LINE_H, align=ALIGN, top=TOP)
    except FitError as e:
        where = '%s:%d' % (source, lineno) if lineno else source
        raise TargetError('%s: %s (shorten or split it; python -m tools.gfx.intro fit)' % (where, e))


def encode_line(bitmap):
    """576 bytes: 36 tiles, the line's top 18 cells, then its bottom 18."""
    data = tiles_lines(bitmap, 2)
    assert len(data) == LINE_BYTES
    return data


def line_width(font, text):
    return measure(font, text, STYLE)


# ---------------------------------------------------------------------------
# Layout: line table and narration map

def check_slots(triggers, dests=None):
    """TargetError if a line takes over a VRAM slot whose previous line is still on screen."""
    dests = dests or [SLOTS[n % len(SLOTS)] for n in range(len(triggers))]
    last = {}
    for n, (t, d) in enumerate(zip(triggers, dests)):
        if d in last and t - triggers[last[d]] < VISIBLE:
            raise TargetError('line %d takes over the VRAM slot of line %d %d px after it, while line %d is still '
                              'on screen (at least %d px)' % (n, last[d], t - triggers[last[d]], last[d], VISIBLE))
        last[d] = n


class Layout:
    """The crawl for a paragraph structure: triggers, dests (VRAM slot per
    line), end position and the number of map rows."""

    def __init__(self, counts):
        self.counts = tuple(counts)
        if not self.counts or any(c < 1 for c in self.counts):
            raise TargetError('bad paragraph structure %r' % (self.counts,))
        trig, t = [], 0
        for p, count in enumerate(self.counts):
            if p:
                t += GAP - PITCH
            for _ in range(count):
                trig.append(t)
                t += PITCH
        self.triggers = trig
        self.dests = [SLOTS[n % len(SLOTS)] for n in range(len(trig))]
        check_slots(self.triggers, self.dests)
        self.end = trig[-1] + TAIL
        self.rows = self.end // 8 + 1 + SPARE_ROWS
        if self.end > 0xFFFE:
            raise TargetError('the crawl is too long (end position %d)' % self.end)

    def __len__(self):
        return len(self.triggers)

    def table(self, sources):
        """The line table: [u16 trigger][u16 VRAM dest][u24 source] per line, then 0xFFFF."""
        if len(sources) != len(self):
            raise ValueError('%d sources for %d lines' % (len(sources), len(self)))
        out = bytearray()
        for t, dest, src in zip(self.triggers, self.dests, sources):
            out += t.to_bytes(2, 'little') + dest.to_bytes(2, 'little') + src.to_bytes(3, 'little')
        return bytes(out + b'\xff\xff')

    def map_rows(self):
        """The narration map as rows of 20 entries (palette 0, no flips)."""
        rows = [[0] * MAP_W for _ in range(self.rows)]
        for t, dest in zip(self.triggers, self.dests):
            r, tile = t // 8, (dest - 0xA000) // 16
            for c in range(18):
                rows[r][1 + c] = tile + c
                rows[r + 1][1 + c] = tile + 18 + c
        return rows

    def map(self):
        return b''.join(e.to_bytes(2, 'little') for row in self.map_rows() for e in row)


def inplace_sources(n):
    return [LINES + LINE_BYTES * i for i in range(n)]


# ---------------------------------------------------------------------------
# Relocated layout: generated assembly

def _db_lines(data, per=16):
    return ['        .db     ' + ', '.join('0x%02X' % b for b in data[i:i + per]) for i in range(0, len(data), per)]


def relocated_asm(layout, extra, source=SOURCE):
    """Assembly for the relocated layout. extra: the bitmaps of lines 15 and up."""
    out = ['; Generated by tools/gfx/intro.py from %s (relocated layout). Do not edit.' % source,
           '; %d lines in %d paragraphs (%s); end position %d.' % (
               len(layout), len(layout.counts), '/'.join(map(str, layout.counts)), layout.end),
           'intro_end_pos = %d' % layout.end,
           '',
           '; Operand hooks in the narration code (original values: HOOKS in tools/gfx/intro.py)']
    labels = {HOOK_TABLE: ('.dl', 'intro_table'), HOOK_END: ('.dw', 'intro_end_pos'), HOOK_MAP: ('.dl', 'intro_map')}
    for addr, _, _, insn_addr, insn in HOOKS:
        op, label = labels[addr]
        out.append('        .org 0x%06X                   ; operand of %s at 0x%06X' % (addr, insn, insn_addr))
        out.append('        %-7s %s' % (op, label))
    out += ['',
            '        .org GFX_INTRO',
            'intro_table:                            ; [u16 trigger][u16 VRAM dest][u24 source] per line, then 0xFFFF']
    for i, (t, dest) in enumerate(zip(layout.triggers, layout.dests)):
        src = '0x%06X' % (LINES + LINE_BYTES * i) if i < INPLACE_LINES else 'intro_line%d' % i
        out.append('        .dw     %d, 0x%04X' % (t, dest))
        out.append('        .d24    %s' % src)
    out.append('        .dw     0xFFFF')
    out.append('intro_map:                              ; one row of 20 entries per 8 px of scroll')
    for row in layout.map_rows():
        out.append('        .dw     ' + ', '.join('0x%04X' % e for e in row))
    for k, data in enumerate(extra):
        out.append('intro_line%d:' % (INPLACE_LINES + k))
        out += _db_lines(data)
    out.append('intro_data_end:')
    return '\n'.join(out) + '\n'


def relocated_size(layout, extra_count):
    return len(layout) * 7 + 2 + layout.rows * MAP_W * 2 + extra_count * LINE_BYTES


# ---------------------------------------------------------------------------
# Build

def render_all(font, paras, source=SOURCE):
    """[(lineno, text, Bitmap, width)] for every line, in order."""
    out = []
    for para in paras:
        for lineno, text in para:
            bm = render_line(font, text, source, lineno)
            out.append((lineno, text, bm, line_width(font, text)))
    return out


def build_text(ctx, text, source=SOURCE):
    """build() for a given source text (the tests and testrom use other texts)."""
    paras = parse(text, source)
    font = ctx.font(FONT)
    lines = render_all(font, paras, source)
    layout = Layout(structure(paras))          # checks the slot rule for any structure
    data = [encode_line(bm) for _, _, bm, _ in lines]
    inplace = is_inplace(paras)
    k = min(len(data), INPLACE_LINES)
    writes = [(LINES + LINE_BYTES * i, data[i]) for i in range(k)]
    allow = [(LINES, LINES + LINE_BYTES * INPLACE_LINES)]
    asm = None
    widest = max(lines, key=lambda l: l[3])
    stats = {'mode': 'in place' if inplace else 'relocated', 'lines': len(lines),
             'paragraphs': '/'.join(map(str, structure(paras))),
             'widest': '%d px (%s:%d)' % (widest[3], source, widest[0])}
    if not inplace:
        extra = data[INPLACE_LINES:]
        size = relocated_size(layout, len(extra))
        region = ctx.region
        if region is None:
            raise TargetError('the relocated layout needs the GFX_INTRO sub-region')
        if size > region[1] - region[0]:
            raise TargetError('the relocated layout needs %d bytes; GFX_INTRO has %d' % (size, region[1] - region[0]))
        asm = ctx.write_file('intro.asm', relocated_asm(layout, extra, source))
        stats['end'] = layout.end
        stats['GFX_INTRO bytes'] = size
    previews = [write_preview(ctx.work, lines, paras)]
    ctx.log('%d lines (%s), %s, widest %d px' % (len(lines), stats['paragraphs'], stats['mode'], widest[3]))
    return Result(writes=writes, allow=allow, asm=asm, previews=previews, stats=stats)


def build(ctx):
    return build_text(ctx, read_text(ctx.translation(TEXT_FILE)), SOURCE)


# ---------------------------------------------------------------------------
# Previews (our English only; the preview colours are our own, not the game's)

PREVIEW_RGB = {0: (20, 40, 110), 1: (255, 255, 255), 2: (150, 170, 255), 3: (40, 60, 230)}


def _bitmap_rows(bm, rgb):
    return [[rgb[bm.get(x, y)] for x in range(bm.w)] for y in range(bm.h)]


def write_preview(folder, lines, paras, scale=2):
    """preview.png: the lines with the crawl's spacing and 8-px margins, at 2x."""
    from ..common import png
    rgb = PREVIEW_RGB
    layout = Layout(structure(paras))
    h = layout.triggers[-1] + LINE_H + 16
    img = [[rgb[0]] * (LINE_W + 16) for _ in range(h)]
    for (_, _, bm, _), t in zip(lines, layout.triggers):
        rows = _bitmap_rows(bm, rgb)
        for y in range(LINE_H):
            img[8 + t + y][8:8 + LINE_W] = rows[y]
    path = os.path.join(folder, 'preview.png')
    png.write_rgb(path, LINE_W + 16, h, img, scale)
    return path


# ---------------------------------------------------------------------------
# Reading ROMs and dumps (decode, compare, check)

def _u(rom, addr, n):
    off = addr - ROM_BASE
    return int.from_bytes(rom[off:off + n], 'little')


def read_table(rom):
    """([(trigger, dest, source)], table address) of the line table the ROM's operand points to."""
    table = _u(rom, HOOK_TABLE, 4) & 0xFFFFFF
    recs, a = [], table
    while _u(rom, a, 2) != 0xFFFF:
        recs.append((_u(rom, a, 2), _u(rom, a + 2, 2), _u(rom, a + 4, 3)))
        a += 7
        if len(recs) > 512:
            raise TargetError('no end mark in the line table at %06X' % table)
    return recs, table


def rom_line(rom, src):
    off = src - ROM_BASE
    return bytes(rom[off:off + LINE_BYTES])


def decode_line(data):
    """576 bytes -> 16 rows of 144 pixels (0-3)."""
    from ..common.tiles import decode_tile_2bpp
    px = [[0] * LINE_W for _ in range(LINE_H)]
    for half in range(2):
        for tx in range(18):
            t = decode_tile_2bpp(data, 16 * (half * 18 + tx))
            for y in range(8):
                px[half * 8 + y][tx * 8:tx * 8 + 8] = t[y]
    return px


def rom_rgb(rom):
    """Colours of the ROM's text palette, with the sky colour as colour 0 (local previews only)."""
    def rgb(w):
        return (w & 15) * 17, ((w >> 4) & 15) * 17, ((w >> 8) & 15) * 17
    pal = {i: rgb(_u(rom, PALETTE + 2 * i, 2)) for i in range(4)}
    pal[0] = rgb(_u(rom, SKY, 2))
    return pal


def _sheet(rows_list, gap_rgb=(0, 0, 0), gap=2):
    out = []
    for rows in rows_list:
        out += rows + [[gap_rgb] * len(rows[0])] * gap
    return out


def decode(rom, outdir):
    from ..common import png
    os.makedirs(outdir, exist_ok=True)
    recs, table = read_table(rom)
    rgb = rom_rgb(rom)
    images = []
    for n, (t, dest, src) in enumerate(recs):
        px = decode_line(rom_line(rom, src))
        rows = [[rgb[v] for v in r] for r in px]
        png.write_rgb(os.path.join(outdir, 'line_%02d.png' % n), LINE_W, LINE_H, rows, 4)
        images.append(rows)
        print('line %2d: trigger %3d, slot %04X, source %06X' % (n, t, dest, src))
    sheet = _sheet(images)
    for s in (1, 3):
        png.write_rgb(os.path.join(outdir, 'lines_%dx.png' % s), LINE_W, len(sheet), sheet, s)
    print('%d lines, table %06X, end position %d; wrote %s' % (len(recs), table, _u(rom, HOOK_END, 2), outdir))


def compare(rom, outdir, text, source):
    """Side-by-side sheets: each line the ROM shows (normally the original) next to ours."""
    from ..common import png
    from .font import load_font
    os.makedirs(outdir, exist_ok=True)
    recs, _ = read_table(rom)
    font = load_font(os.path.join(ROOT, 'assets', 'font', FONT + '.txt'))
    paras = parse(text, source)
    lines = render_all(font, paras, source)
    rgb = rom_rgb(rom)
    n = max(len(recs), len(lines))
    blank = [[rgb[0]] * LINE_W for _ in range(LINE_H)]
    pairs = []
    for i in range(n):
        left = [[rgb[v] for v in r] for r in decode_line(rom_line(rom, recs[i][2]))] if i < len(recs) else blank
        right = _bitmap_rows(lines[i][2], rgb) if i < len(lines) else blank
        pairs.append([l + [(0, 0, 0)] * 4 + r for l, r in zip(left, right)])
    sheet = _sheet(pairs)
    w = len(sheet[0])
    paths = []
    for s in (1, 3):
        p = os.path.join(outdir, 'compare_%dx.png' % s)
        png.write_rgb(p, w, len(sheet), sheet, s)
        paths.append(p)
    for i, pair in enumerate(pairs):
        png.write_rgb(os.path.join(outdir, 'pair_%02d_1x.png' % i), w, LINE_H, pair, 1)
        png.write_rgb(os.path.join(outdir, 'pair_%02d_3x.png' % i), w, LINE_H, pair, 3)
    return paths


def _s32(data, at):
    v = int.from_bytes(data[at:at + 4], 'little')
    return v - (1 << 32) if v & 0x80000000 else v


def crawl_task(mem, table, count):
    """(position, displayed position, table pointer) of the crawl task in a dump, or None.
    position is the integer part of var 0x20 (16.16 fixed point). The picture of the
    same frame shows the scroll of two updates earlier (the scroll register is set
    from a shadow copy in VBlank), so the displayed position is var 0x20 - 2 * speed."""
    for t in range(TASKS):
        base = TASK_BASE + TASK_SIZE * t
        ptr = int.from_bytes(mem[base + VAR_TABLE:base + VAR_TABLE + 4], 'little') & 0xFFFFFF
        if table <= ptr <= table + 7 * count and (ptr - table) % 7 == 0:
            v = _s32(mem, base + VAR_POS)
            speed = _s32(mem, base + VAR_SPEED)
            return v >> 16, (v - 2 * speed) >> 16, ptr
    return None


def _dumps(folder):
    return sorted((int(f[4:9]), os.path.join(folder, f)) for f in os.listdir(folder)
                  if f.startswith('mem_') and f.endswith('.bin') and f[4:9].isdigit())


def parse_expect(text):
    out = {}
    for item in filter(None, (s.strip() for s in text.split(';'))):
        frame, _, slots = item.partition(':')
        out[int(frame)] = slots.split()
    return out


DEFAULT_EXPECT = '1200:0 1 2 3 -;2400:5 6 2 3 4;3600:10 11 7 8 9;4800:10 11 12 13 14'


def text_masks(recs, shown, loaded):
    """Screen rectangles (x0, y0, x1, y1) of the text rows of the loaded lines at the
    displayed position. A line's box starts at screen row 128 + trigger - position (its
    map rows enter the plane just below the window). A line far above the window does
    not wrap around: its map rows are overwritten 256 px after its trigger."""
    masks = []
    for t, _, _ in recs[:loaded]:
        y = 128 + t - shown
        y0, y1 = max(WINDOW[0], y + TEXT_ROWS[0]), min(WINDOW[1], y + TEXT_ROWS[1])
        if y0 <= y1:
            masks.append((TEXT_X[0], y0, TEXT_X[1], y1))
    return masks


def check(rom, folder, ref=None, expect=None, log=print):
    """The acceptance checks on a harness run (see the module notes). Returns the number of failures."""
    from .harness import diff_png
    recs, table = read_table(rom)
    blobs = {}
    for n, (_, _, src) in enumerate(recs):
        blobs.setdefault(rom_line(rom, src), n)
    slots = sorted({d for _, d, _ in recs})
    log('%d lines, table %06X, end position %d, slots %s' % (
        len(recs), table, _u(rom, HOOK_END, 2), ' '.join('%04X' % s for s in slots)))
    fails = 0
    try:
        check_slots([t for t, _, _ in recs], [d for _, d, _ in recs])
    except TargetError as e:
        log('FAIL table: %s' % e)
        fails += 1
    scrolls = {}
    for frame, path in _dumps(folder):
        with open(path, 'rb') as f:
            mem = f.read()
        got = []
        for s in slots:
            blob = mem[s:s + LINE_BYTES]
            n = blobs.get(blob)
            got.append(str(n) if n is not None else ('-' if not any(blob) else '?'))
        task = crawl_task(mem, table, len(recs))
        line = 'frame %5d: slots %s' % (frame, ' '.join('%2s' % g for g in got))
        bad = []
        if task is None:
            line += '  (no crawl task)'
            scrolls[frame] = None                   # none of our lettering on screen: compare it all
        else:
            pos, shown, ptr = task
            loaded = (ptr - table) // 7
            scrolls[frame] = (shown, loaded)
            want = [None] * len(slots)              # None: not loaded yet, anything goes
            for n in range(loaded):
                want[slots.index(recs[n][1])] = str(n)
            line += '  position %d (shown %d), %d lines loaded' % (pos, shown, loaded)
            if any(w is not None and g != w for g, w in zip(got, want)):
                bad.append('expected %s' % ' '.join(w or '.' for w in want))
            for n in range(loaded):
                if recs[n][0] <= pos < recs[n][0] + VISIBLE and got[slots.index(recs[n][1])] != str(n):
                    bad.append('line %d is on screen but not in its slot' % n)
        if expect and frame in expect and got != expect[frame]:
            bad.append('expected (--expect) %s' % ' '.join(expect[frame]))
        if bad:
            fails += 1
            line += '  FAIL: ' + '; '.join(bad)
        log(line)
    if expect:
        for frame in sorted(set(expect) - set(scrolls)):
            log('FAIL frame %5d: no dump for an --expect entry' % frame)
            fails += 1
    if ref:
        shots = sorted(int(f[6:11]) for f in os.listdir(folder)
                       if f.startswith('frame_') and f.endswith('.png') and f[6:11].isdigit())
        compared = 0
        for frame in shots:
            a = os.path.join(folder, 'frame_%05d.png' % frame)
            b = os.path.join(ref, 'frame_%05d.png' % frame)
            if not os.path.isfile(b):
                continue
            if frame in scrolls and scrolls[frame] is None:
                masks, how = [], 'on the whole screen'
            elif frame in scrolls:
                masks = text_masks(recs, *scrolls[frame])
                how = 'outside the %d line box%s' % (len(masks), '' if len(masks) == 1 else 'es')
            else:
                masks = [(TEXT_X[0], WINDOW[0], TEXT_X[1], WINDOW[1])]
                how = 'outside the text band (no dump)'
            count, box = diff_png(a, b, masks)
            compared += 1
            if count:
                fails += 1
                log('FAIL frame %5d: %d pixels differ from the reference %s (x %d-%d, y %d-%d)'
                    % (frame, count, how, box[0], box[2], box[1], box[3]))
            else:
                log('frame %5d: identical to the reference %s' % (frame, how))
        if not compared:
            log('FAIL: no screenshot to compare with %s' % ref)
            fails += 1
    return fails


# ---------------------------------------------------------------------------
# Command line

def _default_text():
    return os.path.join(ROOT, 'translation', 'en', TEXT_FILE)


def _font():
    from .font import load_font
    return load_font(os.path.join(ROOT, 'assets', 'font', FONT + '.txt'))


def _fit(path):
    font = _font()
    source = os.path.basename(path)
    paras = parse(read_text(path), source)
    errors = 0
    k = 0
    for p, para in enumerate(paras):
        for lineno, text in para:
            w = line_width(font, text)
            ok = w <= LINE_W
            errors += not ok
            print('%2d  %3d px %-8s %s' % (k, w, 'ok' if ok else 'TOO WIDE', ascii_text(text)))
            k += 1
        if p + 1 < len(paras):
            print()
    counts = structure(paras)
    mode = 'in place' if counts == STRUCTURE else 'relocated'
    try:
        lay = Layout(counts)
        extra = max(0, len(lay) - INPLACE_LINES)
        print('%d lines in %d paragraphs (%s): %s layout; triggers %s; end position %d%s' % (
            len(lay), len(counts), '/'.join(map(str, counts)), mode, ' '.join(map(str, lay.triggers)), lay.end,
            '' if mode == 'in place' else '; GFX_INTRO %d bytes' % relocated_size(lay, extra)))
    except TargetError as e:
        print('layout: %s' % e)
        errors += 1
    if errors:
        print('%d problem%s' % (errors, '' if errors == 1 else 's'))
    return 1 if errors else 0


def _preview(outdir, path):
    from ..common import png
    font = _font()
    source = os.path.basename(path)
    paras = parse(read_text(path), source)
    lines = render_all(font, paras, source)
    os.makedirs(outdir, exist_ok=True)
    p = write_preview(outdir, lines, paras)
    sheet = _sheet([_bitmap_rows(bm, PREVIEW_RGB) for _, _, bm, _ in lines])
    for s in (1, 3):
        png.write_rgb(os.path.join(outdir, 'lines_%dx.png' % s), LINE_W, len(sheet), sheet, s)
    print('wrote %s, lines_1x.png and lines_3x.png' % p)
    return 0


def _testrom(args):
    """A test ROM with another text (never used by the build)."""
    import hashlib
    from . import apply as gfxapply
    from . import build as gfxbuild
    from ..recomp.rom import EXPECTED_SHA1
    text = read_text(args.text)
    source = os.path.basename(args.text)
    base = open(args.base, 'rb').read()
    if hashlib.sha1(base).hexdigest() != EXPECTED_SHA1:
        print('error: %s is not the original ROM' % args.base, file=sys.stderr)
        return 1
    if os.path.exists(args.out) and os.path.samefile(args.inp, args.out):
        print('error: OUT is the input ROM; IN is never modified', file=sys.stderr)
        return 1
    rom_in = open(args.inp, 'rb').read()
    target = gfxbuild.Target('intro', lambda ctx: build_text(ctx, text, source), gfxbuild.TARGETS['intro'])
    work = os.path.join(ROOT, 'build', 'gfx', 'intro-test')
    out, report = gfxapply.apply_targets(base, rom_in, [target], work=work, gfx_dir=work)
    print('\n'.join(report))
    with open(args.out, 'wb') as f:
        f.write(out)
    print('wrote %s (SHA-1 %s)' % (args.out, hashlib.sha1(out).hexdigest()))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.gfx.intro', description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd')
    p = sub.add_parser('fit', help='widths, structure, mode and layout of a text')
    p.add_argument('text', nargs='?', default=_default_text())
    p = sub.add_parser('preview', help='our English lines as PNGs')
    p.add_argument('outdir')
    p.add_argument('text', nargs='?', default=_default_text())
    p = sub.add_parser('decode', help='the lines a ROM shows, as PNGs (local only)')
    p.add_argument('rom')
    p.add_argument('outdir')
    p = sub.add_parser('compare', help="the ROM's lines next to ours, 1x and 3x (local only)")
    p.add_argument('rom')
    p.add_argument('outdir')
    p.add_argument('text', nargs='?', default=_default_text())
    p = sub.add_parser('check', help='acceptance checks on harness --vram dumps and screenshots')
    p.add_argument('rom')
    p.add_argument('dumpdir')
    p.add_argument('--ref', help='folder of a reference run (same shots and dumps) for the screen diff')
    p.add_argument('--expect', help="fixed slot expectations 'F:SLOTS;...', or 'default' (the in-place recipe)")
    p = sub.add_parser('testrom', help='a test ROM with another text (scratch only)')
    p.add_argument('inp', metavar='IN')
    p.add_argument('out', metavar='OUT')
    p.add_argument('--text', default=_default_text())
    p.add_argument('--base', default=os.path.join(ROOT, 'rom', 'baserom.ngc'))
    args = ap.parse_args(argv)
    try:
        if args.cmd == 'fit':
            return _fit(args.text)
        if args.cmd == 'preview':
            return _preview(args.outdir, args.text)
        if args.cmd == 'decode':
            decode(open(args.rom, 'rb').read(), args.outdir)
            return 0
        if args.cmd == 'compare':
            paths = compare(open(args.rom, 'rb').read(), args.outdir, read_text(args.text),
                            os.path.basename(args.text))
            print('wrote %s' % ', '.join(paths))
            return 0
        if args.cmd == 'check':
            expect = None
            if args.expect:
                expect = parse_expect(DEFAULT_EXPECT if args.expect == 'default' else args.expect)
            fails = check(open(args.rom, 'rb').read(), args.dumpdir, args.ref, expect)
            print('check: %s' % ('passed' if not fails else '%d failure%s' % (fails, '' if fails == 1 else 's')))
            return 1 if fails else 0
        if args.cmd == 'testrom':
            return _testrom(args)
    except (TargetError, ValueError, OSError) as e:
        print('error: %s' % e, file=sys.stderr)
        return 1
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
