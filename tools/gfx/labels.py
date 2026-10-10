"""Graphics target 'labels': the 45 pre-drawn 64x8 menu labels in English.

    python -m tools.gfx.labels fit                          widths and margins (no ROM needed)
    python -m tools.gfx.labels preview [OUTDIR] [--base ROM]   the 45 labels as built (default build/gfx/labels)
    python -m tools.gfx.labels decode ROM OUTDIR            the labels of a ROM as images and text (local only)
    python -m tools.gfx.labels compare ROM [OUTDIR]         original vs English, 1x and 3x (local only)
    python -m tools.gfx.labels check ROM DUMPDIR [--dest VADDR] [--expect NN,NN,...] [--ref REFDIR] [--base ROM]
    python -m tools.gfx.labels recipes TEST.ngc REF.ngc OUTDIR [--states DIR] [--exe EXE] [--base ROM]

The game (docs/workstreams/gfx-labels.md): label n (n = 0x00-0x2C) is 8
tiles, 64x8 px, 128 bytes, at 0x218112 + 128 * n; the block ends at 0x219791
and code follows. Every icon menu's label task copies the selected label from
the ROM to its 8 sprite tiles every frame (0x217271, through the VBlank copy
queue), so the labels are replaced in place: no hooks, no new ROM.

Source: translation/en/labels.txt, one line per label, every label once:

    # comment
    @NN text        the English label (NN = 00-2C, hex)
    @NN keep        keep the original art (label 23, NEXT, is English already)

Style: the treatment of the original art. Its glyphs are 1-px white strokes
(colour 1) on glyph rows 1-6, inside a 1-px near-black outline (colour 3) on
rows 0-7 that mostly takes the 8 neighbours; the label is centred in the
64-px strip (an odd spare pixel goes to the right), on transparent pixels.
English: vwf8 glyph shapes (capitals on rows 1-6 like the original glyphs,
x-height rows 3-6), ink colour 1, an 8-neighbour outline in colour 3, the same
centring. Colour 2 is never used: it differs between screens (sprite palette 0
on the map, 13 in battle). Descenders (g j p q y) take row 7, where their
outline below is cut by the strip edge; compact descenders inside rows 1-6
were tried and read worse ('g' like 'a'), see gfx-labels.md.

decode, compare, check and recipes read ROM art; their outputs (and the
previews, which show the kept original NEXT) stay in build/ or a scratch
folder, never in the repository.

check verifies harness --vram dumps: the VBlank queue (count 0x400D, 8-byte
entries [u16 words][u16 dest][u32 src] from 0x400E) must copy one label
(src = 0x218112 + 128 * n, 0x40 words, dest --dest if given), and the 128
bytes of VRAM there must equal the ROM there and the label built from
labels.txt (a kept label: the original, from --base). --expect gives the
label numbers in dump order; --ref compares the screenshots of DUMPDIR with
those of a reference run (the same run on the unmodified ROM): no pixel may
differ outside x 48-111, y 88-95. recipes runs the six harness runs of the
acceptance list on TEST and REF and checks each (harness: --exe, else
NGP_HARNESS, else build/ngp_harness.exe; states: --states, default
build/states).
"""
import argparse
import os
import sys

from ..common import png
from ..common.tiles import decode_tile_2bpp
from ..recomp.rom import ROM_BASE
from .image import Bitmap
from .target import Result, TargetError
from .textart import FitError, Style, measure, render_box
from .tiles import tiles_rowmajor

# Part of the full build: enabled by the verify step (gfx-verify, 2026-10-10)
# together with the other graphics targets.
FULL_BUILD = True

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

BASE = 0x218112                 # label n at BASE + SIZE * n
COUNT = 45
SIZE = 128                      # 8 tiles of 16 bytes
END = BASE + COUNT * SIZE       # 0x219792: code starts here
WIDTH, HEIGHT = 64, 8           # 8 sprites in a row (sprite layout 0x2172A9)
WORDS = SIZE // 2               # the label task copies 0x40 words

SOURCE = 'labels.txt'
KEEP = 'keep'

# Style constants (gfx-pipeline.md 1.5)
FONT = 'vwf8'
INK, OUTLINE = 1, 3
STYLE = Style(ink=INK, outline=OUTLINE, outline8=True)
ALIGN = 'center'                # x = (64 - width) // 2
TOP = 0                         # glyph row 0 on strip row 0: capitals on rows 1-6

# Screen rectangle of the label strip (sprites at x 48-111, y 88-95; inclusive)
STRIP = (48, 88, 111, 95)

# Preview colours: our own, not the game's palettes (gfx-pipeline.md 1.1).
# White ink, black outline; colour 2 only occurs in the original art; a green
# of our own behind transparent pixels. The sheets show shapes only: the real
# colours are seen in the harness screenshots.
PREVIEW_RGB = {1: (255, 255, 255), 2: (160, 160, 240), 3: (0, 0, 0)}
PREVIEW_BG = (46, 112, 58)
SHEET_BG = (64, 64, 64)
DIGIT_RGB = (230, 230, 230)

# 3x5 hex digits for the label numbers on the sheets (our own; b and d in
# lower case so that they differ from 8 and 0)
_HEX = {
    '0': '111101101101111', '1': '010110010010111', '2': '111001111100111', '3': '111001111001111',
    '4': '101101111001001', '5': '111100111001111', '6': '111100111101111', '7': '111001001001001',
    '8': '111101111101111', '9': '111101111001111', 'A': '010101111101101', 'B': '100100111101111',
    'C': '011100100100011', 'D': '001001111101111', 'E': '111100110100111', 'F': '111100110100100',
}

# The six harness runs of the acceptance list: name, state, frames, input,
# frames with a shot and a --vram dump, label VRAM, expected labels
RECIPES = (
    ('command_bar', 'command_bar_forecast.state', 330, '40:L:2;80:L:2;120:L:2;160:L:2;200:L:2;240:L:2;280:L:2',
     (30, 70, 110, 150, 190, 230, 270, 310), 0xAC00, (0x03, 0x05, 0x01, 0x20, 0x23, 0x22, 0x04, 0x03)),
    ('unit_window', 'stage0_gameplay.state', 330, '46:A:2;100:R:2;150:A:2;200:R:2;240:R:2;280:R:2',
     (190, 230, 270, 310), 0xAC00, (0x0E, 0x10, 0x07, 0x0E)),
    ('item_commands', 'command_bar_forecast.state', 400,
     '10:L:2;50:L:2;90:A:2;170:R:2;210:R:2;250:R:2;290:R:2;330:R:2;370:R:2',
     (160, 200, 240, 280, 320, 360, 395), 0xAC00, (0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E)),
    ('organize', 'hq_status_screen.state', 200, '20:B:2;100:R:2;140:R:2',
     (90, 130, 170), 0xB600, (0x02, 0x0B, 0x0C)),
    ('organize_character', 'hq_status_screen.state', 400,
     '20:B:2;60:B:2;140:R:2;180:R:2;220:R:2;260:R:2;300:R:2;340:R:2',
     (130, 170, 210, 250, 290, 330, 370), 0xB600, (0x17, 0x09, 0x1F, 0x0A, 0x0D, 0x01, 0x17)),
    ('battle', 'battle-inbattle_cmdbar.state', 200, '20:R:2;60:R:2;100:R:2;140:R:2',
     (10, 50, 90, 130, 170), 0xA010, (0x05, 0x10, 0x15, 0x21, 0x05)),
)


# ---------------------------------------------------------------------------
# Source

def parse(text, source='<text>'):
    """{n: English text or KEEP} for n = 0..COUNT-1 from labels.txt source text."""
    labels = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        where = '%s:%d' % (source, lineno)
        if not line.startswith('@'):
            raise TargetError('%s: expected "@NN text", a comment or a blank line, not %r' % (where, line))
        num, _, label = line[1:].partition(' ')
        if len(num) != 2 or any(c not in '0123456789abcdefABCDEF' for c in num):
            raise TargetError('%s: %r is not a two-digit hex label number' % (where, '@' + num))
        n = int(num, 16)
        if n >= COUNT:
            raise TargetError('%s: label %02X does not exist (00-%02X)' % (where, n, COUNT - 1))
        if n in labels:
            raise TargetError('%s: label %02X is given twice' % (where, n))
        label = label.strip()
        if not label:
            raise TargetError('%s: label %02X has no text (write "keep" to keep the original)' % (where, n))
        labels[n] = label
    missing = [n for n in range(COUNT) if n not in labels]
    if missing:
        raise TargetError('%s: no line for label%s %s' % (source, '' if len(missing) == 1 else 's',
                                                          ' '.join('%02X' % n for n in missing)))
    return labels


def load(path):
    """parse() of a labels.txt file."""
    with open(path, encoding='utf-8-sig') as f:
        return parse(f.read(), path)


def source_path(root=ROOT):
    return os.path.join(root, 'translation', 'en', SOURCE)


def load_vwf(root=ROOT):
    from .font import load_font
    return load_font(os.path.join(root, 'assets', 'font', FONT + '.txt'))


# ---------------------------------------------------------------------------
# Rendering

def render(font, text):
    """The label as a 64x8 Bitmap (pixels 0, INK, OUTLINE). FitError when it is
    wider than 64 px with its outline."""
    return render_box(font, text, STYLE, WIDTH, HEIGHT, ALIGN, top=TOP)


def encode(bitmap):
    """128 bytes: the 8 tiles of a 64x8 bitmap, left to right."""
    if (bitmap.w, bitmap.h) != (WIDTH, HEIGHT):
        raise TargetError('a label is %dx%d px, not %dx%d' % (bitmap.w, bitmap.h, WIDTH, HEIGHT))
    data = tiles_rowmajor(bitmap)
    assert len(data) == SIZE
    return data


def build_all(font, labels):
    """[128 bytes, or None for a kept label] for the 45 labels; raises
    TargetError naming the label that does not fit."""
    out = []
    for n in range(COUNT):
        text = labels[n]
        if text == KEEP:
            out.append(None)
            continue
        try:
            out.append(encode(render(font, text)))
        except FitError as e:
            raise TargetError('label %02X %r is %d px wide with its outline; the strip is %d px'
                              % (n, text, e.width, WIDTH)) from e
    return out


def address(n):
    return BASE + SIZE * n


def runs(data):
    """In-place writes [(address, bytes)]: consecutive built labels merged, kept ones left out."""
    out, start, buf = [], None, b''
    for n, d in enumerate(list(data) + [None]):
        if d is None:
            if buf:
                out.append((address(start), buf))
            start, buf = None, b''
            continue
        if start is None:
            start = n
        buf += d
    return out


def original(rom, n):
    """The 128 bytes of label n in a ROM image (offset 0 = CPU 0x200000)."""
    off = address(n) - ROM_BASE
    return bytes(rom[off:off + SIZE])


def final(data, base=None):
    """[128 bytes] as in the built ROM: kept labels from base (the original
    ROM), or None when base is not given."""
    return [d if d is not None else (original(base, n) if base is not None else None) for n, d in enumerate(data)]


def decode(data):
    """A 64x8 Bitmap of 128 bytes of label tiles."""
    bm = Bitmap(WIDTH, HEIGHT)
    for t in range(WIDTH // 8):
        tile = decode_tile_2bpp(data, 16 * t)
        for y in range(8):
            for x in range(8):
                bm.set(8 * t + x, y, tile[y][x])
    return bm


def ink_rows(bm, colour=INK):
    rows = [y for y in range(bm.h) if any(v == colour for v in bm.row(y))]
    return (rows[0], rows[-1]) if rows else None


def box(bm):
    """(x0, x1) of the non-zero pixels, inclusive, or None."""
    b = bm.bbox()
    return (b[0], b[2] - 1) if b else None


def built(root=ROOT, labels=None):
    """(labels, data) from the repository's labels.txt (or the given labels)."""
    labels = load(source_path(root)) if labels is None else labels
    return labels, build_all(load_vwf(root), labels)


# ---------------------------------------------------------------------------
# The target

def build(ctx):
    font = ctx.font(FONT)
    labels = load(ctx.translation(SOURCE))
    data = build_all(font, labels)
    writes = runs(data)
    previews = write_previews(ctx.work, labels, data, ctx.base)
    widths = {n: measure(font, t, STYLE) for n, t in labels.items() if t != KEEP}
    widest = max(widths, key=lambda n: (widths[n], -n))
    kept = [n for n in range(COUNT) if data[n] is None]
    ctx.log('%d labels in English, %d kept (%s); widest %d px (%02X %r)'
            % (COUNT - len(kept), len(kept), ' '.join('%02X' % n for n in kept) or 'none',
               widths[widest], widest, labels[widest]))
    return Result(writes=writes, allow=[(BASE, END)], previews=previews,
                  stats={'labels': COUNT - len(kept), 'kept': len(kept), 'widest': '%d px' % widths[widest]})


# ---------------------------------------------------------------------------
# Sheets (build/ only)

def _digits(img, x0, y0, text, rgb=DIGIT_RGB):
    for k, ch in enumerate(text):
        bits = _HEX[ch]
        for i, bit in enumerate(bits):
            if bit == '1':
                img[y0 + i // 3][x0 + 4 * k + i % 3] = rgb


def _strip_rgb(bm, bg=PREVIEW_BG):
    return [[bg if v == 0 else PREVIEW_RGB[v & 3] for v in bm.row(y)] for y in range(bm.h)]


def sheet(path, columns, scale=1):
    """A sheet of label strips: columns = [[Bitmap or None] * COUNT, ...]; one
    row per label (its number on the left), the columns side by side. None
    draws a crossed placeholder."""
    num_w, gap = 2 * 4 + 1, 4
    w = 2 + num_w + len(columns) * (WIDTH + gap)
    h = 2 + COUNT * (HEIGHT + 2)
    img = [[SHEET_BG] * w for _ in range(h)]
    for n in range(COUNT):
        y0 = 2 + n * (HEIGHT + 2)
        _digits(img, 2, y0 + 1, '%02X' % n)
        x0 = 2 + num_w + 2
        for col in columns:
            bm = col[n]
            if bm is None:
                rows = [[(255, 0, 255) if (x + y) % 4 == 0 else (90, 0, 90) for x in range(WIDTH)]
                        for y in range(HEIGHT)]
            else:
                rows = _strip_rgb(bm)
            for y in range(HEIGHT):
                img[y0 + y][x0:x0 + WIDTH] = rows[y]
            x0 += WIDTH + gap
    png.write_rgb(path, w, h, img, scale)
    return path


def write_previews(folder, labels, data, base=None):
    """preview.png (the labels as built, 4x) and, with the original ROM,
    compare_x1.png / compare_x3.png (original | English). Returns the paths."""
    os.makedirs(folder, exist_ok=True)
    finals = final(data, base)
    english = [decode(d) if d is not None else None for d in finals]
    paths = [sheet(os.path.join(folder, 'preview.png'), [english], 4)]
    if base is not None:
        origs = [decode(original(base, n)) for n in range(COUNT)]
        for scale in (1, 3):
            paths.append(sheet(os.path.join(folder, 'compare_x%d.png' % scale), [origs, english], scale))
    return paths


# ---------------------------------------------------------------------------
# Harness checks

def check_dumps(rom, folder, data, dest=None, expect=None, ref=None, out=print):
    """Check the --vram dumps (and screenshots) of one harness run (see the
    module notes). data: final() labels (bytes; None = unknown kept label).
    Returns (ok, [label numbers found, in dump order])."""
    from . import harness as H
    from . import vram as V
    ok, found = True, []
    mems = sorted(f for f in os.listdir(folder) if f.startswith('mem_') and f.endswith('.bin'))
    if not mems:
        out('  %s: no --vram dumps (mem_*.bin)' % folder)
        return False, found
    for name in mems:
        mem = V.Vram.load(os.path.join(folder, name))
        hits = [(w, d, s) for w, d, s in mem.queue() if BASE <= s < END and (dest is None or d == dest)]
        if len(hits) != 1:
            out('  %s: %d label copies in the VBlank queue%s: FAIL' % (
                name, len(hits), '' if dest is None else ' to %04X' % dest))
            ok = False
            found.append(None)
            continue
        words, d, src = hits[0]
        n, rest = divmod(src - BASE, SIZE)
        found.append(n)
        problems = []
        if rest or words != WORDS:
            problems.append('copy %06X x%d is not one whole label' % (src, words))
        else:
            have = mem.m[d:d + SIZE]
            if have != original(rom, n):
                problems.append('VRAM differs from the ROM')
            if data[n] is None:
                problems.append('no reference for the kept label (give --base)')
            elif have != data[n]:
                problems.append('VRAM differs from the built label')
        out('  %s: label %02X -> %04X %s' % (name, n, d, 'ok' if not problems else 'FAIL: ' + '; '.join(problems)))
        ok = ok and not problems
    if expect is not None:
        same = list(expect) == found
        out('  expected %s, found %s: %s' % (' '.join('%02X' % n for n in expect),
                                             ' '.join('--' if n is None else '%02X' % n for n in found),
                                             'ok' if same else 'FAIL'))
        ok = ok and same
    if ref is not None:
        shots = sorted(f for f in os.listdir(folder) if f.startswith('frame_') and f.endswith('.png'))
        if not shots:
            out('  %s: no screenshots to compare' % folder)
            ok = False
        for name in shots:
            other = os.path.join(ref, name)
            if not os.path.isfile(other):
                out('  %s: no %s in %s: FAIL' % (name, name, ref))
                ok = False
                continue
            count, where = H.diff_png(os.path.join(folder, name), other, [STRIP])
            out('  %s: %d pixels differ outside x %d-%d, y %d-%d%s' % (
                name, count, STRIP[0], STRIP[2], STRIP[1], STRIP[3],
                '' if not count else ' (within x %d-%d, y %d-%d): FAIL' % (where[0], where[2], where[1], where[3])))
            ok = ok and not count
    return ok, found


def run_recipes(test, ref, outdir, states, data, exe=None, out=print):
    """The six harness runs on TEST and REF, each checked. Returns True if all pass."""
    from . import harness as H
    with open(test, 'rb') as f:
        rom = f.read()
    passed = []
    for name, state, frames, inputs, shots, dest, expect in RECIPES:
        st = os.path.join(states, state)
        if not os.path.isfile(st):
            out('%s: state %s not found: FAIL' % (name, st))
            passed.append((name, False))
            continue
        dirs = {}
        for which, path in (('test', test), ('ref', ref)):
            dirs[which] = os.path.join(outdir, name, which)
            H.run(path, dirs[which], frames=frames, shots=shots, vram=shots, inputs=inputs, load_state=st, exe=exe)
        out('%s (%s, VRAM %04X):' % (name, state, dest))
        ok, _ = check_dumps(rom, dirs['test'], data, dest, expect, dirs['ref'], out)
        passed.append((name, ok))
    out('recipes: %s' % ', '.join('%s %s' % (n, 'ok' if ok else 'FAIL') for n, ok in passed))
    return all(ok for _, ok in passed)


# ---------------------------------------------------------------------------
# Command line

def _read_rom(path):
    with open(path, 'rb') as f:
        return f.read()


def _default_base(path):
    if path:
        return _read_rom(path)
    default = os.path.join(ROOT, 'rom', 'baserom.ngc')
    return _read_rom(default) if os.path.isfile(default) else None


def cmd_fit(args):
    font = load_vwf()
    labels = load(source_path())
    bad = 0
    print('NN  %-16s %3s  %-5s  notes' % ('text', 'px', 'L/R'))
    for n in range(COUNT):
        text = labels[n]
        if text == KEEP:
            print('%02X  %-16s %3s  %-5s  original art kept' % (n, '(keep)', '-', '-'))
            continue
        width = measure(font, text, STYLE)
        try:
            bm = render(font, text)
        except FitError:
            print('%02X  %-16s %3d  %-5s  TOO WIDE (limit %d)' % (n, text, width, '-', WIDTH))
            bad += 1
            continue
        x0, x1 = box(bm)
        notes = []
        rows = ink_rows(bm)
        if rows and rows[1] > 6:
            notes.append('descender on row 7')
        print('%02X  %-16s %3d  %-5s  %s' % (n, text, width, '%d/%d' % (x0, WIDTH - 1 - x1), ', '.join(notes)))
    widths = [measure(font, t, STYLE) for t in labels.values() if t != KEEP]
    print('%d labels, %d kept; widest %d px of %d%s' % (
        COUNT, sum(1 for t in labels.values() if t == KEEP), max(widths), WIDTH,
        '; %d too wide' % bad if bad else ''))
    return 1 if bad else 0


def cmd_preview(args):
    labels, data = built()
    folder = args.outdir or os.path.join(ROOT, 'build', 'gfx', 'labels')
    paths = write_previews(folder, labels, data, _default_base(args.base))
    for p in paths:
        print('wrote %s' % p)
    return 0


def cmd_decode(args):
    rom = _read_rom(args.rom)
    os.makedirs(args.outdir, exist_ok=True)
    bms = [decode(original(rom, n)) for n in range(COUNT)]
    lines = []
    for n, bm in enumerate(bms):
        lines.append('@%02X' % n)
        lines += [''.join('.123'[v] if v else '.' for v in bm.row(y)) for y in range(HEIGHT)]
    with open(os.path.join(args.outdir, 'labels.txt'), 'w', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print('wrote %s' % sheet(os.path.join(args.outdir, 'labels_x4.png'), [bms], 4))
    print('wrote %s' % os.path.join(args.outdir, 'labels.txt'))
    return 0


def cmd_compare(args):
    labels, data = built()
    base = _read_rom(args.rom)
    folder = args.outdir or os.path.join(ROOT, 'build', 'gfx', 'labels')
    for p in write_previews(folder, labels, data, base):
        print('wrote %s' % p)
    return 0


def _hex(text):
    return int(text, 16)


def cmd_check(args):
    labels, data = built()
    data = final(data, _default_base(args.base))
    rom = _read_rom(args.rom)
    expect = [int(v, 16) for v in args.expect.split(',') if v] if args.expect else None
    ok, _ = check_dumps(rom, args.dumpdir, data, args.dest, expect, args.ref)
    print('check: %s' % ('ok' if ok else 'FAIL'))
    return 0 if ok else 1


def cmd_recipes(args):
    labels, data = built()
    data = final(data, _default_base(args.base))
    states = args.states or os.path.join(ROOT, 'build', 'states')
    ok = run_recipes(args.test, args.ref, args.outdir, states, data, args.exe)
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.gfx.labels', description=__doc__.split('\n')[0],
                                 epilog='See the module notes (python -c "import tools.gfx.labels as m; '
                                        'print(m.__doc__)").')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('fit', help='widths and margins of every label (no ROM needed)')
    p = sub.add_parser('preview', help='preview sheet of the 45 labels as built')
    p.add_argument('outdir', nargs='?')
    p.add_argument('--base', help='the original ROM, for the kept labels and the comparison (default rom/baserom.ngc)')
    p = sub.add_parser('decode', help='the labels of a ROM as images and text (local only)')
    p.add_argument('rom')
    p.add_argument('outdir')
    p = sub.add_parser('compare', help='original vs English sheets at 1x and 3x (local only)')
    p.add_argument('rom', help='the original ROM')
    p.add_argument('outdir', nargs='?')
    p = sub.add_parser('check', help='check harness --vram dumps (and screenshots) of one run')
    p.add_argument('rom', help='the ROM that the harness ran')
    p.add_argument('dumpdir')
    p.add_argument('--dest', type=_hex, help='label VRAM address (AC00, B600 or A010)')
    p.add_argument('--expect', help='expected label numbers, hex, comma separated, in dump order')
    p.add_argument('--ref', help='screenshots of the same run on the unmodified ROM')
    p.add_argument('--base', help='the original ROM (default rom/baserom.ngc), for kept labels')
    p = sub.add_parser('recipes', help='run and check the six harness runs of the acceptance list')
    p.add_argument('test', help='the ROM with the labels (tools.gfx.apply ... --target labels)')
    p.add_argument('ref', help='the same ROM without them (the input of tools.gfx.apply)')
    p.add_argument('outdir')
    p.add_argument('--states', help='folder of the saved states (default build/states)')
    p.add_argument('--exe', help='ngp_harness.exe (default: NGP_HARNESS, else build/ngp_harness.exe)')
    p.add_argument('--base', help='the original ROM (default rom/baserom.ngc), for kept labels')
    args = ap.parse_args(argv)
    from .harness import HarnessError
    try:
        return {'fit': cmd_fit, 'preview': cmd_preview, 'decode': cmd_decode, 'compare': cmd_compare,
                'check': cmd_check, 'recipes': cmd_recipes}[args.cmd](args)
    except (TargetError, HarnessError, OSError, ValueError) as e:
        print('error: %s' % e, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
