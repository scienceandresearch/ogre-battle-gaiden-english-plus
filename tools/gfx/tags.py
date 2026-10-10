"""Graphics target 'tags': the two small pre-drawn status tags, in place.

    deployed   the tag above the formation grid on the organize status pane
               of a unit that is deployed on the stage map: 5 sprite tiles
               (40x8 px), 80 bytes at 0x214A00 (tiles 0x5B-0x5F of the
               organize sheet 0x214450, VRAM tiles 0x13B-0x13F, sprite palette
               8), and the same 80 bytes at 0x2E736A (the link-battle copy of
               that sheet), so that both sheets stay identical.
    paralysis  the hit-reaction label over a combatant that a paralysing
               effect hits in battle: 2 sprite tiles (16x8 px), 32 bytes at
               0x2FE5ED (VRAM tiles 0x2D-0x2E, sprite palette 15).

No hooks, no new ROM, no palette writes: the tiles keep the colour indices of
the original art. Sources: translation/en/tags.txt (the words) and
assets/gfx/tags/caps6.txt (6-row capitals, our own design). The style
reproduces the treatment of the original art (docs/workstreams/gfx-tags.md):

    deployed   a box at x 4-35 of the 40-px strip, rows 0-7: a 1-px border in
               colour 3 and a fill in colour 2; columns 0-3 and 36-39 stay
               transparent. Inside, the word in colour 1 on rows 1-6 (the
               whole interior height), every ink pixel with a 1-px shadow in
               colour 3 on its right. The word stays inside the original
               lettering's area: ink at x 8-31 (so at most 24 px of ink),
               its last shadow at x 32 at most, centred there
               (x = 8 + (24 - width) // 2). The blue fill columns x 5-7 and
               33-34 stay as in the original. The box and those margins are
               checked against the ROM's tag at build time: only the lettering
               area (x 8-32, rows 1-6) changes.
    paralysis  the word in colour 1 on rows 1-6 with a 1-px outline over the
               8 neighbours in colour 3, on a transparent background; the ink
               is centred in the 16 px (left bias). Outline columns that fall
               outside the 16 px are cut, so up to 16 px of ink fit (STUN is
               15 px: its left outline column is cut).

translation/en/tags.txt: one '@KEY TEXT' line per tag (KEY: deployed,
paralysis), '#' comments; TEXT 'keep' keeps the original art.

    python -m tools.gfx.tags fit                     widths against the limits (no ROM)
    python -m tools.gfx.tags preview OUTDIR          our tags as PNG (1x and 8x)
    python -m tools.gfx.tags decode ROM OUTDIR       a ROM's tags as PNG (local only: never commit
                                                     the originals)
    python -m tools.gfx.tags check ROM DUMP|DIR ...  the ROM holds the built tiles; in harness --vram
                                                     dumps, each tag shown has the built tiles in VRAM
                                                     and whole sprite rows with its palette number
"""
import argparse
import os
import sys

from ..common.tiles import decode_tile_2bpp
from ..recomp.rom import ROM_BASE
from .font import load_font
from .image import Bitmap, save_png
from .target import Result, TargetError
from .textart import FitError, Style, render
from .tiles import tiles_rowmajor

# Part of the full build: enabled by the verify step (gfx-verify, 2026-10-10)
# together with the other graphics targets.
FULL_BUILD = True

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TEXT_FILE = 'tags.txt'                                  # translation/en/
FONT_FILE = os.path.join('assets', 'gfx', 'tags', 'caps6.txt')
KEYS = ('deployed', 'paralysis')
KEEP = 'keep'

INK, FILL, DARK = 1, 2, 3                               # colour indices of the original art

# deployed
DEPLOYED_ADDRS = (0x214A00, 0x2E736A)                   # organize sheet, link-battle copy
DEPLOYED_W, DEPLOYED_H = 40, 8
BOX_X0, BOX_X1 = 4, 35                                  # border columns (inclusive); rows 0 and 7
INNER_X0, INNER_X1 = BOX_X0 + 1, BOX_X1 - 1             # interior x 5-34 (30 px)
INNER_W = INNER_X1 - INNER_X0 + 1
LETTER_X0, LETTER_X1 = 8, 31                            # the original lettering's ink columns
LETTER_W = LETTER_X1 - LETTER_X0 + 1                    # 24 px: the most ink a word may have
SHADOW_X = LETTER_X1 + 1                                # 32: the last column a shadow may use
TEXT_TOP = 1                                            # strip row of glyph row 0 (rows 1-6)
TEXT_ROWS = 6
DEPLOYED_PAL = 8                                        # sprite palette on the status pane
DEPLOYED_VRAM_TILE = 0x13B                              # VRAM tile of strip tile 0 (organize screen)

# paralysis
PARALYSIS_ADDR = 0x2FE5ED
PARALYSIS_W, PARALYSIS_H = 16, 8
PARALYSIS_STYLE = Style(ink=INK, outline=DARK, outline8=True)
PARALYSIS_PAL = 15
PARALYSIS_VRAM_TILE = 0x2D

INK_STYLE = Style(ink=INK, outline=None)

# Preview colours (our own choice; the game shows its palettes)
PREVIEW = {0: (150, 150, 150), INK: (255, 255, 255), FILL: (56, 64, 200), DARK: (16, 16, 24)}


def ranges():
    """The in-place ranges of this target: [(lo, hi)], hi exclusive."""
    n = DEPLOYED_W // 8 * 16
    return [(a, a + n) for a in DEPLOYED_ADDRS] + [(PARALYSIS_ADDR, PARALYSIS_ADDR + PARALYSIS_W // 8 * 16)]


# ---------------------------------------------------------------------------
# Sources

def parse_text(text, source='tags.txt'):
    """{key: text or None (keep)} from the tags.txt syntax."""
    out = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        where = '%s:%d' % (source, n)
        if not line.startswith('@'):
            raise TargetError('%s: expected "@KEY TEXT" (KEY: %s), not %r' % (where, ', '.join(KEYS), line))
        key, _, value = line[1:].partition(' ')
        value = value.strip()
        if key not in KEYS:
            raise TargetError('%s: unknown key @%s (known: %s)' % (where, key, ', '.join(KEYS)))
        if key in out:
            raise TargetError('%s: @%s is given twice' % (where, key))
        if not value:
            raise TargetError('%s: @%s has no text (write %r to keep the original art)' % (where, key, KEEP))
        out[key] = None if value == KEEP else value
    missing = [k for k in KEYS if k not in out]
    if missing:
        raise TargetError('%s: missing %s' % (source, ', '.join('@' + k for k in missing)))
    return out


def load_text(path):
    with open(path, encoding='utf-8-sig') as f:
        return parse_text(f.read(), path)


def load_tag_font(root=ROOT):
    font = load_font(os.path.join(root, FONT_FILE))
    if font.height != TEXT_ROWS:
        raise TargetError('%s has %d rows per glyph; the tags need %d' % (FONT_FILE, font.height, TEXT_ROWS))
    return font


# ---------------------------------------------------------------------------
# Rendering

def ink_width(font, text):
    """Width of the word's ink in px (no outline, no shadow)."""
    return render(font, text, INK_STYLE).w


def render_deployed(font, text):
    """The deployed tag: Bitmap(40, 8) of colours 0-3 (see the module notes)."""
    ink = render(font, text, INK_STYLE)                 # tight box, glyph rows 0-5
    if ink.w > LETTER_W:
        raise FitError(text, ink.w, LETTER_W,
                       'the lettering of the deployed tag must stay in the original lettering area, '
                       'strip x %d-%d (%d px of ink)' % (LETTER_X0, LETTER_X1, LETTER_W))
    bm = Bitmap(DEPLOYED_W, DEPLOYED_H)
    for y in range(DEPLOYED_H):
        for x in range(BOX_X0, BOX_X1 + 1):
            bm.set(x, y, DARK if y in (0, DEPLOYED_H - 1) or x in (BOX_X0, BOX_X1) else FILL)
    x0 = LETTER_X0 + (LETTER_W - ink.w) // 2
    pts = [(x0 + x, TEXT_TOP + y) for y in range(ink.h) for x in range(ink.w) if ink.get(x, y)]
    for x, y in pts:
        bm.set(x, y, INK)
    for x, y in pts:
        if bm.get(x + 1, y) != INK:                     # x + 1 is at most SHADOW_X
            bm.set(x + 1, y, DARK)
    return bm


def render_paralysis(font, text):
    """The paralysis label: Bitmap(16, 8) of colours 0, 1 and 3 (see the module notes)."""
    width = ink_width(font, text)
    if width > PARALYSIS_W:
        raise FitError(text, width, PARALYSIS_W)
    art = render(font, text, PARALYSIS_STYLE)           # ink + 1-px ring: (width + 2) x 8
    bm = Bitmap(PARALYSIS_W, PARALYSIS_H)
    bm.paste(art, (PARALYSIS_W - width) // 2 - 1, TEXT_TOP - 1)
    return bm


def decode_strip(data, n):
    """Bitmap(8 * n, 8) of n 2bpp tiles (left to right)."""
    tiles = [decode_tile_2bpp(data, 16 * t) for t in range(n)]
    return Bitmap(8 * n, 8, [v for y in range(8) for t in tiles for v in t[y]])


def in_lettering(x, y):
    """True for the pixels of a deployed tag that the English lettering may
    change: the original lettering's area, x 8-32 (ink and its last shadow),
    rows 1-6."""
    return LETTER_X0 <= x <= SHADOW_X and TEXT_TOP <= y < TEXT_TOP + TEXT_ROWS


def frame_cells(bm):
    """The pixels of a deployed tag outside the lettering area: the box, the
    blue margins x 5-7 and 33-34, the transparent columns."""
    return [(x, y, bm.get(x, y)) for y in range(DEPLOYED_H) for x in range(DEPLOYED_W)
            if not in_lettering(x, y)]


class Built:
    """The built tags: texts, bitmaps (None = kept) and tile bytes."""

    def __init__(self, texts, font):
        self.texts = texts
        self.deployed = None if texts['deployed'] is None else render_deployed(font, texts['deployed'])
        self.paralysis = None if texts['paralysis'] is None else render_paralysis(font, texts['paralysis'])
        self.deployed_bytes = None if self.deployed is None else tiles_rowmajor(self.deployed)
        self.paralysis_bytes = None if self.paralysis is None else tiles_rowmajor(self.paralysis)

    def writes(self):
        out = []
        if self.deployed_bytes is not None:
            out += [(a, self.deployed_bytes) for a in DEPLOYED_ADDRS]
        if self.paralysis_bytes is not None:
            out.append((PARALYSIS_ADDR, self.paralysis_bytes))
        return out

    def fit_lines(self, font):
        lines = []
        t = self.texts['deployed']
        if t is None:
            lines.append('deployed: keep (original art)')
        else:
            w = ink_width(font, t)
            x0 = LETTER_X0 + (LETTER_W - w) // 2
            lines.append('deployed: %-10s %2d px of ink at x %d-%d, lettering area %d px (%d px free)' % (
                t, w, x0, x0 + w - 1, LETTER_W, LETTER_W - w))
        t = self.texts['paralysis']
        if t is None:
            lines.append('paralysis: keep (original art)')
        else:
            w = ink_width(font, t)
            cut = []
            x = (PARALYSIS_W - w) // 2
            if x < 1:
                cut.append('left')
            if x + w > PARALYSIS_W - 1:
                cut.append('right')
            lines.append('paralysis: %-10s %2d px of ink, label %d px%s' % (
                t, w, PARALYSIS_W, ' (outline cut: %s)' % ' and '.join(cut) if cut else ''))
        return lines


def build_tags(root=ROOT, text_path=None):
    font = load_tag_font(root)
    texts = load_text(text_path or os.path.join(root, 'translation', 'en', TEXT_FILE))
    return Built(texts, font), font


def write_previews(built, folder):
    """PNG previews of our tags (1x and 8x); returns the paths."""
    os.makedirs(folder, exist_ok=True)
    paths = []
    for name, bm in (('deployed', built.deployed), ('paralysis', built.paralysis)):
        if bm is None:
            continue
        for scale in (1, 8):
            path = os.path.join(folder, '%s%s.png' % (name, '' if scale == 1 else '_%dx' % scale))
            save_png(path, bm, PREVIEW, scale)
            paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# Graphics build

def check_frame(ctx_read, built):
    """Everything of our deployed tag outside the lettering area (the box, the
    blue margins, the transparent columns) must equal the original's, pixel for
    pixel, at both addresses: only the lettering may change."""
    if built.deployed is None:
        return
    ours = frame_cells(built.deployed)
    for addr in DEPLOYED_ADDRS:
        orig = decode_strip(ctx_read(addr, DEPLOYED_W // 8 * 16), DEPLOYED_W // 8)
        bad = [(x, y) for (x, y, v), (_, _, w) in zip(ours, frame_cells(orig)) if v != w]
        if bad:
            raise TargetError('deployed tag at %06X: outside the lettering area (x %d-%d, rows %d-%d) the original '
                              'differs from ours at %d pixels (first at x %d, y %d); check the address and the '
                              'box constants' % (addr, LETTER_X0, SHADOW_X, TEXT_TOP, TEXT_TOP + TEXT_ROWS - 1,
                                                 len(bad), *bad[0]))


def build(ctx):
    font = load_tag_font(ctx.root)
    texts = load_text(ctx.translation(TEXT_FILE))
    built = Built(texts, font)
    check_frame(ctx.read, built)
    previews = write_previews(built, ctx.work)
    for line in built.fit_lines(font):
        ctx.log(line)
    stats = {'deployed': texts['deployed'] or KEEP, 'paralysis': texts['paralysis'] or KEEP,
             'bytes': sum(len(d) for _, d in built.writes())}
    return Result(writes=built.writes(), allow=ranges(), previews=previews, stats=stats)


# ---------------------------------------------------------------------------
# Harness dumps

def _sprites(m):
    """[(n, tile, x, y, palette)] of the 64 sprites (chaining and the sprite offset applied)."""
    out = []
    px = py = 0
    for n in range(64):
        s = m[0x8800 + 4 * n:0x8800 + 4 * n + 4]
        attr, ox, oy = s[1], s[2], s[3]
        if attr & 4:
            ox = (ox + px) & 0xFF
        if attr & 2:
            oy = (oy + py) & 0xFF
        px, py = ox, oy
        if (attr >> 3) & 3:
            out.append((n, s[0] | ((attr & 1) << 8), (ox + m[0x8020]) & 0xFF, (oy + m[0x8021]) & 0xFF,
                        m[0x8C00 + n] & 15))
    return out


def vram_state(vram, data):
    """'holds' (VRAM equals the built tiles), 'cleared' (blank, or only some of
    the built pixels left: the game wipes the paralysis label away after about
    a second) or 'differs'."""
    if data is None:
        return 'differs'
    if vram == data:
        return 'holds'
    if all(v & ~d & 0xFF == 0 for v, d in zip(vram, data)):
        return 'cleared'
    return 'differs'


def check_dump(m, built, name=''):
    """(ok, lines) for one --vram dump (64 KB): for each tag whose tiles a
    visible sprite shows, VRAM must hold the built tiles (or a blank or partly
    wiped copy of them, see vram_state), and the sprites must form the tag (in
    order, 8 px apart, one row) with the tag's palette."""
    lines, ok = [], True
    sprites = _sprites(m)
    for tag, data, tile0, ntiles, pal in (
            ('deployed', built.deployed_bytes, DEPLOYED_VRAM_TILE, DEPLOYED_W // 8, DEPLOYED_PAL),
            ('paralysis', built.paralysis_bytes, PARALYSIS_VRAM_TILE, PARALYSIS_W // 8, PARALYSIS_PAL)):
        shown = [s for s in sprites if tile0 <= s[1] < tile0 + ntiles and s[4] == pal]
        if not shown:
            continue
        a = 0xA000 + 16 * tile0
        state = vram_state(m[a:a + 16 * ntiles], data)
        if state == 'cleared' and tag != 'paralysis':          # only the paralysis label is wiped away
            state = 'differs'
        ok &= state != 'differs'
        groups = []
        for n, tile, x, y, p in shown:
            if tile == tile0:
                groups.append([(n, tile, x, y)])
            elif groups:
                groups[-1].append((n, tile, x, y))
        shapes = []
        for g in groups:
            good = len(g) == ntiles and all(t == tile0 + i and yy == g[0][3] and xx == (g[0][2] + 8 * i) & 0xFF
                                            for i, (_, t, xx, yy) in enumerate(g))
            ok &= good
            shapes.append('sprites %d-%d at x %d, y %d%s' % (g[0][0], g[-1][0], g[0][2], g[0][3],
                                                             '' if good else ' (NOT a whole tag)'))
        lines.append('%s%s: VRAM %04X %s; %s' % (
            name + ': ' if name else '', tag, a,
            {'holds': 'holds the built tiles', 'cleared': 'is blank or partly wiped (the game clears it)',
             'differs': 'does NOT hold the built tiles'}[state],
            '; '.join(shapes) or 'no whole tag'))
    if not lines:
        lines.append('%sno tag shown' % (name + ': ' if name else ''))
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

def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.gfx.tags', description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('fit', help='widths against the limits (no ROM needed)')
    p = sub.add_parser('preview', help='our tags as PNG (1x and 8x)')
    p.add_argument('outdir')
    p = sub.add_parser('decode', help="a ROM's tags as PNG (local only)")
    p.add_argument('rom')
    p.add_argument('outdir')
    p = sub.add_parser('check', help='harness --vram dumps: the tags shown hold the built tiles')
    p.add_argument('rom', help='the test ROM (must hold the built tags)')
    p.add_argument('dumps', nargs='+', help='mem_NNNNN.bin files or folders')
    args = ap.parse_args(argv)
    try:
        built, font = build_tags()
        if args.cmd == 'fit':
            print('\n'.join(built.fit_lines(font)))
            return 0
        if args.cmd == 'preview':
            for path in write_previews(built, args.outdir):
                print('wrote %s' % path)
            return 0
        rom = open(args.rom, 'rb').read()
        if args.cmd == 'decode':
            os.makedirs(args.outdir, exist_ok=True)
            items = [('deployed_%06X' % a, a, DEPLOYED_W // 8) for a in DEPLOYED_ADDRS]
            items.append(('paralysis_%06X' % PARALYSIS_ADDR, PARALYSIS_ADDR, PARALYSIS_W // 8))
            for name, addr, n in items:
                off = addr - ROM_BASE
                bm = decode_strip(rom[off:off + 16 * n], n)
                for scale in (1, 8):
                    path = os.path.join(args.outdir, '%s%s.png' % (name, '' if scale == 1 else '_%dx' % scale))
                    save_png(path, bm, PREVIEW, scale)
                    print('wrote %s' % path)
            return 0
        # check
        ok = True
        for addr, data in built.writes():
            off = addr - ROM_BASE
            same = rom[off:off + len(data)] == data
            ok &= same
            print('ROM %06X: %s' % (addr, 'holds the built tiles' if same else 'does NOT hold the built tiles'))
        paths = _dump_paths(args.dumps)
        if not paths:
            print('error: no dumps')
            return 1
        for path in paths:
            with open(path, 'rb') as f:
                m = f.read()
            if len(m) != 0x10000:
                print('%s: not a --vram dump (%d bytes)' % (path, len(m)))
                ok = False
                continue
            good, lines = check_dump(m, built, os.path.basename(path))
            ok &= good
            print('\n'.join(lines))
        print('check: %s' % ('ok' if ok else 'FAILED'))
        return 0 if ok else 1
    except (TargetError, ValueError, OSError) as e:
        print('error: %s' % e, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
