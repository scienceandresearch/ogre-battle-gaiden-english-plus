"""Tests for the intro narration target (tools/gfx/intro.py).

Usage: python -m tools.gfx.test_intro [ROM]

Without the ROM: translation/en/intro.txt has 15 lines in 6/6/3 paragraphs
(in-place mode) with characters of the title16 font; every line is at most
144 px including the outline; the style is that of the original lettering
(colours 0, 1 and 3 only, ink rows 4-14, outline rows 3-15, exactly the
4-neighbour ring, centred); the build gives 15 x 576 bytes at 0x290F5D +
0x240 * n inside 0x290F5D-0x29311C, no asm, deterministic, and decoding the
tiles gives the rendered lines back; the layout generator (original
structure: triggers, end 552, 74 map rows; the VRAM slot rule); the
relocated mode with a 17-line, 4-paragraph test text: its generated asm
assembles to the three operand hooks and a table, map and extra line
bitmaps inside GFX_INTRO that parse back; errors (line too wide, missing
glyph, GFX_INTRO too small); the check command on synthetic dumps.

With ROM (rom/baserom.ngc): the golden test (the generator fed the original
structure reproduces the original line table at 0x28D1EA and the narration
map at 0x293DDD byte for byte; the hook sites hold the documented
instructions and operands); the original lettering has the style the target
reproduces (colours, rows, 4-neighbour outline); applying the target to the
original ROM changes only 0x290F5D-0x29311C (in place), or only that range,
the 10 operand bytes and GFX_INTRO (relocated test text).

Everything is written to a temporary folder; build/ and the repository are
not touched. Nothing from the ROM is stored.
"""
import hashlib
import os
import re
import sys
import tempfile
import time
import traceback

from ..asm.tlcs900asm import Assembler
from ..recomp.rom import EXPECTED_SHA1, ROM_BASE
from . import apply as gfxapply
from . import build as gfxbuild
from . import intro
from .font import MissingGlyphError, load_font
from .target import Context, TargetError

ROOT = intro.ROOT
GFX_INTRO = gfxbuild.SUBREGIONS['GFX_INTRO']
LINES_END = intro.LINES + intro.LINE_BYTES * intro.INPLACE_LINES      # 0x29311D
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
D4 = ((1, 1), (-1, 1), (1, -1), (-1, -1))
# kana, CJK punctuation, kanji and full-width forms (the build's check of translation/en)
JAPANESE = re.compile('[%s-%s%s-%s%s-%s]' % tuple(chr(c) for c in (0x3000, 0x30FF, 0x4E00, 0x9FFF, 0xFF01, 0xFF9F)))

# <...> = the ellipsis and the curly double quotes (kept out of the source as characters)
TEXT17 = '''# relocated-layout test: 17 lines in 4 paragraphs (4/2/6/5)
To take all the suffering
of the people upon oneself,
and to bear one's own
suffering alone<...>

Whoever can do this
is truly a <lq>true king<rq><...>

But<...>
can such a way of life
be called happiness?
And to force such a life
upon others<...>
is that truly right?

Imperial Year 15.
Our story begins
in Estoa, a village
on a small
peninsula<...>
'''.replace('<...>', chr(0x2026)).replace('<lq>', chr(0x201C)).replace('<rq>', chr(0x201D))
STRUCTURE17 = (4, 2, 6, 5)


class Ctx:
    def __init__(self, folder, base, rom_path=None):
        self.folder = folder
        self.base = base            # the original ROM, or None
        self.rom_path = rom_path
        self.font = load_font(os.path.join(ROOT, 'assets', 'font', intro.FONT + '.txt'))
        self.text = intro.read_text(os.path.join(ROOT, 'translation', 'en', intro.TEXT_FILE))
        self.n = 0

    def tmp(self, name):
        self.n += 1
        path = os.path.join(self.folder, '%02d_%s' % (self.n, name))
        os.makedirs(path, exist_ok=True)
        return path

    def context(self, base=None):
        """A build Context on a synthetic ROM (the in-place build reads no ROM bytes)."""
        rom = base or bytes(0x200000)
        return Context(ROOT, 'intro', rom, rom, self.tmp('work'), 'GFX_INTRO', GFX_INTRO, log=lambda s: None)


def pixels(bm):
    return [[bm.get(x, y) for x in range(bm.w)] for y in range(bm.h)]


def ring_stats(px):
    """(outline pixels, ink-adjacent empty pixels, diagonal-only outline, diagonal-only empty) of a line."""
    h, w = len(px), len(px[0])
    g = lambda x, y: px[y][x] if 0 <= x < w and 0 <= y < h else 0
    out4 = miss = dout = dempty = 0
    for y in range(h):
        for x in range(w):
            v = px[y][x]
            if v == 1:
                continue
            orth = any(g(x + dx, y + dy) == 1 for dx, dy in N4)
            diag = any(g(x + dx, y + dy) == 1 for dx, dy in D4)
            if orth:
                out4 += v == 3
                miss += v == 0
            elif diag:
                dout += v == 3
                dempty += v == 0
            elif v == 3:
                raise AssertionError('outline pixel at (%d, %d) touches no ink' % (x, y))
    return out4, miss, dout, dempty


def rows_of(px, value):
    return [y for y, r in enumerate(px) if value in r]


# ---------------------------------------------------------------------------
# Without the ROM

def test_source(ctx):
    paras = intro.parse(ctx.text)
    assert intro.structure(paras) == intro.STRUCTURE == (6, 6, 3), intro.structure(paras)
    assert intro.is_inplace(paras)
    lines = [t for p in paras for _, t in p]
    assert len(lines) == 15
    assert not JAPANESE.search(ctx.text), 'Japanese characters in intro.txt'
    for t in lines:
        assert not ctx.font.missing(t), (t, ctx.font.missing(t))
        assert t == t.strip()
    # the glossary term and the dialogue's term
    assert any('Imperial Year 15' in t for t in lines)
    assert any('true king' in t for t in lines)


def test_widths(ctx):
    paras = intro.parse(ctx.text)
    widest = 0
    for lineno, text in (l for p in paras for l in p):
        w = intro.line_width(ctx.font, text)
        assert w <= intro.LINE_W, '%s:%d is %d px' % (intro.SOURCE, lineno, w)
        bm = intro.render_line(ctx.font, text, lineno=lineno)
        assert (bm.w, bm.h) == (144, 16)
        x0, _, x1, _ = bm.bbox()
        assert x1 - x0 == w, (text, x1 - x0, w)
        widest = max(widest, w)
    assert widest <= 144


def test_style(ctx):
    """Colours 0/1/3, rows of the original lettering, the exact 4-neighbour ring, centred."""
    assert intro.STYLE.ink == 1 and intro.STYLE.outline == 3 and not intro.STYLE.outline8
    assert not intro.STYLE.bold and not intro.STYLE.glow
    for _, text in (l for p in intro.parse(ctx.text) for l in p):
        bm = intro.render_line(ctx.font, text)
        px = pixels(bm)
        assert bm.values() <= {0, 1, 3}, bm.values()
        ink, out = rows_of(px, 1), rows_of(px, 3)
        assert ink[0] == intro.TOP == 4 and ink[-1] <= 14, (text, ink[0], ink[-1])
        assert out[0] == 3 and out[-1] <= 15, (text, out[0], out[-1])
        out4, miss, dout, _ = ring_stats(px)
        assert miss == 0 and dout == 0, (text, miss, dout)          # exactly the 4-neighbour ring
        x0, _, x1, _ = bm.bbox()
        assert x0 == (144 - (x1 - x0)) // 2, (text, x0, x1)         # centred (left-biased by half a pixel)
        assert sum(1 for r in px for v in r if v == 3) == out4


def test_build_inplace(ctx):
    res = intro.build(ctx.context())
    assert res.asm is None
    assert res.allow == [(0x290F5D, 0x29311D)]
    assert res.stats['mode'] == 'in place' and res.stats['lines'] == 15
    assert [a for a, _ in res.writes] == [0x290F5D + 0x240 * n for n in range(15)]
    assert all(len(d) == 576 for _, d in res.writes)
    lo, hi = res.allow[0]
    assert all(lo <= a and a + len(d) <= hi for a, d in res.writes)
    assert sum(len(d) for _, d in res.writes) == 15 * 576
    again = intro.build(ctx.context())
    assert again.writes == res.writes, 'the build is not deterministic'
    paras = intro.parse(ctx.text)
    for (_, text), (_, data) in zip((l for p in paras for l in p), res.writes):
        assert intro.decode_line(data) == pixels(intro.render_line(ctx.font, text)), text
    for p in res.previews:
        assert os.path.isfile(p)


def test_layout(ctx):
    lay = intro.Layout(intro.STRUCTURE)
    assert lay.triggers == [0, 24, 48, 72, 96, 120, 184, 208, 232, 256, 280, 304, 368, 392, 416]
    assert lay.end == 552 == intro.END and lay.rows == 74
    assert lay.dests == [intro.SLOTS[n % 5] for n in range(15)]
    table = lay.table(intro.inplace_sources(15))
    assert len(table) == 15 * 7 + 2 and table.endswith(b'\xff\xff')
    rows = lay.map_rows()
    assert len(lay.map()) == 74 * 40
    for n, (t, d) in enumerate(zip(lay.triggers, lay.dests)):
        tile = (d - 0xA000) // 16
        assert rows[t // 8][1:19] == list(range(tile, tile + 18))
        assert rows[t // 8 + 1][1:19] == list(range(tile + 18, tile + 36))
    assert all(r[0] == 0 and r[19] == 0 for r in rows)
    assert sum(1 for r in rows if any(r)) == 30
    intro.Layout((7,))                                  # 7 lines in a row: slot reused after exactly 120 px
    try:
        intro.check_slots([0, 8, 16, 24, 32, 40])
    except TargetError:
        pass
    else:
        raise AssertionError('slot reuse after 40 px was accepted')
    lay17 = intro.Layout(STRUCTURE17)
    assert lay17.triggers == [0, 24, 48, 72, 136, 160, 224, 248, 272, 296, 320, 344, 408, 432, 456, 480, 504]
    assert lay17.end == 640


def assemble(folder, asm_path):
    wrapper = os.path.join(folder, 'wrapper.asm')
    with open(wrapper, 'w', newline='\n') as f:
        f.write('GFX_INTRO = 0x%06X\nGFX_INTRO_END = 0x%06X\n        .include "%s"\n'
                % (GFX_INTRO[0], GFX_INTRO[1], gfxbuild.include_path(asm_path, folder)))
    asm = Assembler()
    asm.load(wrapper)
    return asm.assemble(), asm.symbols


def test_relocated(ctx):
    c = ctx.context()
    res = intro.build_text(c, TEXT17, 'test17.txt')
    assert res.stats['mode'] == 'relocated' and res.stats['lines'] == 17
    assert res.asm and os.path.isfile(res.asm)
    assert [a for a, _ in res.writes] == [0x290F5D + 0x240 * n for n in range(15)]
    chunks, sym = assemble(c.work, res.asm)
    mem = {}
    hooks = []
    for org, data in chunks:
        if not data:
            continue
        if org < 0x36746D:
            hooks.append((org, len(data)))
        else:
            assert GFX_INTRO[0] <= org and org + len(data) <= GFX_INTRO[1], 'chunk %06X outside GFX_INTRO' % org
        for i, b in enumerate(data):
            mem[org + i] = b
    assert sorted(hooks) == [(0x28D0A3, 4), (0x28D0B7, 2), (0x28D0E2, 4)], hooks

    def u(a, n):
        return int.from_bytes(bytes(mem[a + i] for i in range(n)), 'little')

    table, mapa, end = u(0x28D0A3, 4), u(0x28D0E2, 4), u(0x28D0B7, 2)
    assert table == sym['intro_table'] and mapa == sym['intro_map'] and end == 640
    assert all(GFX_INTRO[0] <= a < GFX_INTRO[1] for a in (table, mapa))
    lay = intro.Layout(STRUCTURE17)
    recs, a = [], table
    while u(a, 2) != 0xFFFF:
        recs.append((u(a, 2), u(a + 2, 2), u(a + 4, 3)))
        a += 7
    assert [r[0] for r in recs] == lay.triggers and [r[1] for r in recs] == lay.dests
    lines = [t for p in intro.parse(TEXT17) for _, t in p]
    for n, (_, _, src) in enumerate(recs):
        if n < 15:
            assert src == 0x290F5D + 0x240 * n
        else:
            assert GFX_INTRO[0] <= src and src + 576 <= GFX_INTRO[1]
            data = bytes(mem[src + i] for i in range(576))
            assert data == intro.encode_line(intro.render_line(ctx.font, lines[n])), n
    assert bytes(mem[mapa + i] for i in range(len(lay.map()))) == lay.map()
    used = sum(len(d) for o, d in chunks if o >= GFX_INTRO[0])
    assert used == intro.relocated_size(lay, 2) == res.stats['GFX_INTRO bytes']
    intro.check_slots([r[0] for r in recs], [r[1] for r in recs])
    again = intro.build_text(ctx.context(), TEXT17, 'test17.txt')
    assert open(again.asm, 'rb').read() == open(res.asm, 'rb').read()


def test_errors(ctx):
    for text, kind, word in (('a' * 40 + '\n', TargetError, 'px'),
                             ('Hello {world}\n', MissingGlyphError, '{'),
                             ('\n'.join(['Line'] * 40) + '\n', TargetError, 'GFX_INTRO'),
                             ('  indented\n', TargetError, 'leading spaces'),
                             ('# only a comment\n', TargetError, 'no text')):
        try:
            intro.build_text(ctx.context(), text, 'bad.txt')
        except kind as e:
            assert word in str(e), (word, str(e))
        else:
            raise AssertionError('accepted: %r' % text[:30])


def test_check_synthetic(ctx):
    """The check command on a synthetic ROM and synthetic dumps."""
    rom = bytearray(0x200000)
    table = 0x3A6000
    counts = (6,)
    lay = intro.Layout(counts)
    sources = [0x3A7000 + 0x240 * n for n in range(6)]
    for n, s in enumerate(sources):
        rom[s - ROM_BASE:s - ROM_BASE + 0x240] = bytes([n + 1]) * 0x240
    t = lay.table(sources)
    rom[table - ROM_BASE:table - ROM_BASE + len(t)] = t
    rom[0x28D0A3 - ROM_BASE:0x28D0A7 - ROM_BASE] = table.to_bytes(4, 'little')
    rom[0x28D0B7 - ROM_BASE:0x28D0B9 - ROM_BASE] = lay.end.to_bytes(2, 'little')
    folder = ctx.tmp('dumps')

    def dump(frame, pos, loaded, slots):
        mem = bytearray(0x10000)
        base = 0x4086 + 0x38 * 3
        mem[base + 32:base + 36] = ((pos << 16) + 0x3000).to_bytes(4, 'little')
        mem[base + 36:base + 40] = (0x17C0).to_bytes(4, 'little')
        mem[base + 40:base + 44] = (table + 7 * loaded).to_bytes(4, 'little')
        for s, n in zip(intro.SLOTS, slots):
            if n is not None:
                mem[s:s + 0x240] = bytes([n + 1]) * 0x240
        with open(os.path.join(folder, 'mem_%05d.bin' % frame), 'wb') as f:
            f.write(mem)

    dump(100, 130, 6, (5, 1, 2, 3, 4))
    dump(200, 30, 2, (0, 1, None, None, None))
    log = []
    assert intro.check(bytes(rom), folder, log=log.append) == 0, log
    assert intro.check(bytes(rom), folder, expect=intro.parse_expect('100:5 1 2 3 4;200:0 1 - - -'),
                       log=log.append) == 0
    dump(300, 130, 6, (0, 1, 2, 3, 4))                  # line 5 missing from its slot
    log = []
    assert intro.check(bytes(rom), folder, log=log.append) == 1, log
    assert any('FAIL' in l and 'frame   300' in l for l in log), log
    recs = [(tt, d, s) for tt, d, s in zip(lay.triggers, lay.dests, sources)]
    masks = intro.text_masks(recs, 130, 6)
    # at position 130 line 0 (trigger 0) has left; line 5 (trigger 120) is at screen row 118
    assert (8, 121, 151, 127) in masks and (8, 25, 151, 37) in masks and len(masks) == 5, masks


# ---------------------------------------------------------------------------
# With the ROM

def test_golden(ctx):
    base = ctx.base

    def u(a, n):
        return int.from_bytes(base[a - ROM_BASE:a - ROM_BASE + n], 'little')

    lay = intro.Layout(intro.STRUCTURE)
    table = lay.table(intro.inplace_sources(15))
    assert table == base[intro.TABLE - ROM_BASE:intro.TABLE - ROM_BASE + len(table)], 'line table differs'
    m = lay.map()
    assert m == base[intro.MAP - ROM_BASE:intro.MAP - ROM_BASE + len(m)], 'narration map differs'
    recs, at = intro.read_table(base)
    assert at == intro.TABLE and [r[0] for r in recs] == lay.triggers and len(recs) == 15
    from ..recomp.rom import Rom
    from ..recomp.tlcs900 import decode
    from ..text.script import decode_script
    rom = Rom(ctx.rom_path)
    for addr, size, value, insn_addr, text in intro.HOOKS:
        assert u(addr, size) == value, '%06X' % addr
        if insn_addr == 0x28D0A2:
            ins = decode_script(rom, insn_addr)
            got = '%s 0x%x, 0x%x' % (ins.mnem, ins.args[0], ins.args[1])
            assert insn_addr + 1 == addr
        else:
            ins = decode(rom.read8, insn_addr)
            got = ins.text()
            assert ins.next - size == addr
        assert got == text, (got, text)


def test_original_style(ctx):
    """The original lettering has the treatment the target reproduces."""
    diag_out = diag_empty = 0
    for n in range(15):
        src = intro.LINES + 0x240 * n
        px = intro.decode_line(ctx.base[src - ROM_BASE:src - ROM_BASE + 0x240])
        vals = {v for r in px for v in r}
        assert vals == {0, 1, 3}, (n, vals)                                 # palette colours 1 and 3
        ink, out = rows_of(px, 1), rows_of(px, 3)
        assert (ink[0], ink[-1]) == (intro.TOP, intro.TOP + 10), (n, ink)   # 11 rows from TOP
        assert (out[0], out[-1]) == (intro.TOP - 1, intro.TOP + 11), (n, out)
        out4, miss, dout, dempty = ring_stats(px)
        assert miss <= 2, (n, miss)                                         # the orthogonal ring is complete
        diag_out += dout
        diag_empty += dempty
    assert diag_empty > 9 * diag_out, (diag_out, diag_empty)                # 4-neighbour, not 8


def test_apply_inplace(ctx):
    base = ctx.base
    target = gfxbuild.Target('intro', intro.build, 'GFX_INTRO')
    work = ctx.tmp('apply')
    out, report = gfxapply.apply_targets(base, base, [target], work=work, gfx_dir=work, log=lambda s: None)
    changed = [i + ROM_BASE for i in range(len(base)) if out[i] != base[i]]
    assert changed and min(changed) >= 0x290F5D and max(changed) <= 0x29311C, (hex(min(changed)), hex(max(changed)))
    res = intro.build(ctx.context(base))
    for a, d in res.writes:
        assert out[a - ROM_BASE:a - ROM_BASE + len(d)] == d
    assert out[intro.PALETTE - ROM_BASE:intro.PALETTE - ROM_BASE + 8] == base[intro.PALETTE - ROM_BASE:
                                                                             intro.PALETTE - ROM_BASE + 8]


def test_apply_relocated(ctx):
    base = ctx.base
    target = gfxbuild.Target('intro', lambda c: intro.build_text(c, TEXT17, 'test17.txt'), 'GFX_INTRO')
    work = ctx.tmp('apply17')
    out, report = gfxapply.apply_targets(base, base, [target], work=work, gfx_dir=work, log=lambda s: None)
    hooks = set(range(0x28D0A3, 0x28D0A7)) | set(range(0x28D0B7, 0x28D0B9)) | set(range(0x28D0E2, 0x28D0E6))
    for i in range(len(base)):
        if out[i] != base[i]:
            a = i + ROM_BASE
            assert 0x290F5D <= a < LINES_END or a in hooks or GFX_INTRO[0] <= a < GFX_INTRO[1], '%06X' % a
    recs, table = intro.read_table(out)
    assert len(recs) == 17 and GFX_INTRO[0] <= table < GFX_INTRO[1]
    assert int.from_bytes(out[0x28D0B7 - ROM_BASE:0x28D0B9 - ROM_BASE], 'little') == 640


TESTS = [test_source, test_widths, test_style, test_build_inplace, test_layout, test_relocated, test_errors,
         test_check_synthetic]
ROM_TESTS = [test_golden, test_original_style, test_apply_inplace, test_apply_relocated]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    base = None
    if argv:
        base = open(argv[0], 'rb').read()
        if hashlib.sha1(base).hexdigest() != EXPECTED_SHA1:
            print('error: %s is not the original ROM' % argv[0])
            return 1
    else:
        print('note: no ROM given; the golden, original-style and apply tests are skipped')
    tests = TESTS + (ROM_TESTS if base else [])
    failed = 0
    with tempfile.TemporaryDirectory(prefix='test_intro_') as folder:
        ctx = Ctx(folder, base, argv[0] if argv else None)
        for test in tests:
            t0 = time.time()
            try:
                test(ctx)
            except Exception:
                failed += 1
                print('FAIL %s' % test.__name__)
                traceback.print_exc()
            else:
                print('ok   %s (%.2f s)' % (test.__name__, time.time() - t0))
    print('%d tests, %d failed%s' % (len(tests), failed, '' if base else ' (ROM tests skipped)'))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
