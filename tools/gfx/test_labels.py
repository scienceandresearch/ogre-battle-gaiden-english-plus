"""Tests for the graphics target 'labels' (tools/gfx/labels.py,
translation/en/labels.txt).

Usage: python -m tools.gfx.test_labels [ROM]

ROM  the original ROM (rom/baserom.ngc). With it, the apply-path test runs on
     the real ROM and the original labels are checked against the style
     assumptions; without it, a synthetic 2 MB image is used (our own bytes).

Covers: labels.txt (every label once, only NEXT kept, parse errors); every
label at most 64 px with its outline; the style of the original art (colours
0, 1 and 3 only, capitals and the glyph tops on row 1, the outline exactly
the 8-neighbour ring of the ink, left-biased centring); the 8 tiles of a
label round-trip; the output (45 x 128 bytes with the kept label, two builds
identical); the Result (one range, 0x218112-0x219791, writes inside it,
nothing for the kept label, previews); applying the target to the base ROM
(tools.gfx.apply path) changes no byte outside the range and leaves NEXT
alone; the names quoted elsewhere (ui.txt help texts, script.txt tips, the
map popup and its Link submenu) equal the labels; the check command on
synthetic harness dumps; the command line (fit, preview).

Everything is written to a temporary folder; build/ and the repository are
not touched.
"""
import contextlib
import hashlib
import io
import os
import sys
import tempfile
import time
import traceback

from ..common import png
from ..common.tiles import encode_tile_2bpp
from ..patch.layout import FREE_START
from ..recomp.rom import EXPECTED_SHA1, ROM_BASE
from . import apply as gfxapply
from . import labels as L
from .target import Context, TargetError
from .textart import FitError, measure

ROM_SIZE = 0x200000
RANGE = (0x218112, 0x219792)
NEXT = 0x23

# Places outside labels.txt that quote a label's name: they must stay identical.
QUOTED = (
    (0x00, 'script.txt', 'Deploy unit'),        # Game System Tips 5
    (0x14, 'script.txt', 'Rite of revival'),    # Game System Tips 2
    (0x18, 'ui.txt', 'Use item'),               # item command help texts
    (0x19, 'ui.txt', 'Equip item'),
    (0x1A, 'ui.txt', 'Remove item'),
    (0x1B, 'ui.txt', 'Sell item'),
    (0x1C, 'ui.txt', 'Discard item'),
    (0x1D, 'ui.txt', 'Sort'),
    (0x1E, 'ui.txt', 'Tidy up'),
)
# Font-text menu entries for the same commands (ui.txt, padded with spaces):
# the map popup's Monitor (screen settings) and Organize (the organize screen)
# and its Link submenu. The Link submenu's Settings 1/2 differ from labels
# 27/28 in the original too.
SAME_ENTRY = (0x04, 0x20, 0x24, 0x25, 0x26, 0x29, 0x2A)


def synthetic_rom():
    """2 MB of our own pattern, 0xFF from 0x36746D like the original."""
    n = FREE_START - ROM_BASE
    pattern = bytes(((i * 13) ^ (i >> 2)) & 0xFF for i in range(4096))
    rom = bytearray((pattern * (n // len(pattern) + 1))[:n])
    rom += b'\xFF' * (ROM_SIZE - n)
    return bytes(rom)


def expect(exc, fn, *args, contains=None, **kw):
    try:
        fn(*args, **kw)
    except exc as e:
        if contains and contains not in str(e):
            raise AssertionError('%s raised, but without %r: %s' % (exc.__name__, contains, e))
        return e
    raise AssertionError('%s not raised' % exc.__name__)


class Ctx:
    def __init__(self, folder, base, real):
        self.folder = folder
        self.base = base
        self.real = real
        self.n = 0
        self.labels = L.load(L.source_path())
        self.font = L.load_vwf()
        self.data = L.build_all(self.font, self.labels)

    def tmp(self, name):
        self.n += 1
        path = os.path.join(self.folder, '%02d_%s' % (self.n, name))
        os.makedirs(path, exist_ok=True)
        return path


def _source(lines):
    return '\n'.join(lines) + '\n'


def _all_lines(texts=None, skip=()):
    texts = texts or {}
    return ['@%02X %s' % (n, texts.get(n, 'Label')) for n in range(L.COUNT) if n not in skip]


# ---------------------------------------------------------------------------

def test_source(ctx):
    """labels.txt: every label once, English text, only NEXT kept."""
    labels = ctx.labels
    assert sorted(labels) == list(range(L.COUNT))
    kept = [n for n, t in labels.items() if t == L.KEEP]
    assert kept == [NEXT], kept
    for n, t in labels.items():
        assert t == t.strip() and t, (n, t)
        assert all(32 <= ord(c) < 127 for c in t), (n, t)
        assert not ctx.font.missing(t), (n, t)
    with open(L.source_path(), 'rb') as f:
        raw = f.read()
    assert all(b < 0x80 for b in raw), 'labels.txt must be ASCII'


def test_parse_errors(ctx):
    """Malformed sources are refused with the line named."""
    good = _all_lines()
    assert len(L.parse(_source(good))) == L.COUNT
    assert L.parse(_source(['# c', '', '@00  Two  words  '] + good[1:]))[0] == 'Two  words'
    expect(TargetError, L.parse, _source(good[1:]), contains='no line for label 00')
    expect(TargetError, L.parse, _source(good[:-1]), contains='no line for label 2C')
    expect(TargetError, L.parse, _source(good + ['@05 Again']), contains='label 05 is given twice')
    expect(TargetError, L.parse, _source(good + ['@2D Extra']), contains='label 2D does not exist')
    expect(TargetError, L.parse, _source(['@5 Short'] + good), contains='two-digit hex')
    expect(TargetError, L.parse, _source(['@0G Bad'] + good), contains='two-digit hex')
    expect(TargetError, L.parse, _source(['junk'] + good), contains=':1:')
    expect(TargetError, L.parse, _source(['@00'] + good[1:]), contains='has no text')
    expect(TargetError, L.parse, _source(['@00    '] + good[1:]), contains='has no text')


def test_fit(ctx):
    """Every label is at most 64 px wide with its outline; too wide is refused."""
    widths = {}
    for n, t in ctx.labels.items():
        if t == L.KEEP:
            continue
        widths[n] = measure(ctx.font, t, L.STYLE)
        assert widths[n] <= L.WIDTH, (n, t, widths[n])
        bm = L.render(ctx.font, t)
        x0, x1 = L.box(bm)
        assert x1 - x0 + 1 == widths[n], (n, t)
    assert max(widths.values()) == 63                   # Rite of revival
    texts = dict(ctx.labels)
    texts[0x05] = 'This text is far too wide'
    e = expect(TargetError, L.build_all, ctx.font, texts, contains='label 05')
    assert isinstance(e.__cause__, FitError)
    expect(FitError, L.render, ctx.font, 'W' * 12)


def _ring8(bm):
    ink = {(x, y) for y in range(bm.h) for x in range(bm.w) if bm.get(x, y) == L.INK}
    ring = set()
    for x, y in ink:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                p = (x + dx, y + dy)
                if p not in ink and 0 <= p[0] < bm.w and 0 <= p[1] < bm.h:
                    ring.add(p)
    return ink, ring


def test_style(ctx):
    """The original's treatment: colours 0, 1 and 3; the glyph tops on row 1
    (row 0 outline only); the outline exactly the 8-neighbour ring of the ink;
    centred, an odd spare pixel on the right."""
    for n, t in ctx.labels.items():
        if t == L.KEEP:
            continue
        bm = L.render(ctx.font, t)
        assert (bm.w, bm.h) == (L.WIDTH, L.HEIGHT)
        assert bm.values() <= {0, L.INK, L.OUTLINE}, (n, t, bm.values())
        top, bottom = L.ink_rows(bm)
        assert top == 1, (n, t, top)                    # capitals start on row 1 like the original glyphs
        assert bottom in (6, 7), (n, t, bottom)         # baseline row 6; descenders on row 7
        assert (bottom == 7) == any(c in t for c in 'gjpqy'), (n, t)
        ink, ring = _ring8(bm)
        outline = {(x, y) for y in range(bm.h) for x in range(bm.w) if bm.get(x, y) == L.OUTLINE}
        assert outline == ring, (n, t)
        x0, x1 = L.box(bm)
        w = x1 - x0 + 1
        assert x0 == (L.WIDTH - w) // 2, (n, t, x0, w)
        assert not any(bm.get(x, 0) == L.INK for x in range(bm.w))


def test_encode(ctx):
    """8 tiles left to right; decode(encode(b)) == b."""
    for n, t in ctx.labels.items():
        if t == L.KEEP:
            continue
        bm = L.render(ctx.font, t)
        data = L.encode(bm)
        assert len(data) == L.SIZE and data == ctx.data[n]
        assert L.decode(data) == bm
        for k in range(8):
            rows = [bm.row(y)[8 * k:8 * k + 8] for y in range(8)]
            assert data[16 * k:16 * k + 16] == encode_tile_2bpp(rows)


def test_output(ctx):
    """45 x 128 bytes with the kept label from the base ROM; two builds identical."""
    again = L.build_all(L.load_vwf(), L.load(L.source_path()))
    assert again == ctx.data
    assert [n for n, d in enumerate(ctx.data) if d is None] == [NEXT]
    final = L.final(ctx.data, ctx.base)
    assert len(final) == L.COUNT and all(len(d) == L.SIZE for d in final)
    assert len(b''.join(final)) == 45 * 128 == RANGE[1] - RANGE[0]
    assert final[NEXT] == L.original(ctx.base, NEXT)
    assert L.address(0) == RANGE[0] and L.address(L.COUNT) == RANGE[1] == L.END


def test_result(ctx):
    """build(ctx): one range 0x218112-0x219791, writes inside it, nothing for
    NEXT, previews written; deterministic."""
    results = []
    for k in range(2):
        work = ctx.tmp('build%d' % k)
        c = Context(L.ROOT, 'labels', ctx.base, ctx.base, work, None, None, log=lambda s: None)
        results.append(L.build(c))
    r = results[0]
    assert r.allow == [RANGE], r.allow
    assert r.asm is None
    assert [(a, bytes(d)) for a, d in r.writes] == [(a, bytes(d)) for a, d in results[1].writes]
    covered = set()
    for addr, data in r.writes:
        assert RANGE[0] <= addr and addr + len(data) <= RANGE[1], hex(addr)
        assert (addr - RANGE[0]) % L.SIZE == 0 and len(data) % L.SIZE == 0
        for i in range(len(data) // L.SIZE):
            n = (addr - RANGE[0]) // L.SIZE + i
            assert n not in covered
            covered.add(n)
            assert data[L.SIZE * i:L.SIZE * (i + 1)] == ctx.data[n]
    assert covered == set(range(L.COUNT)) - {NEXT}
    assert len(r.writes) == 2                           # 00-22 and 24-2C
    names = sorted(os.path.basename(p) for p in r.previews)
    assert names == ['compare_x1.png', 'compare_x3.png', 'preview.png'], names
    for p in r.previews:
        w, h, _, _ = png.read(p)
        assert w > 0 and h > 0
    assert r.stats['labels'] == 44 and r.stats['kept'] == 1


def test_apply(ctx):
    """The tools.gfx.apply path on the base ROM: only the label block changes,
    NEXT stays the original, every other label is the built one."""
    folder = ctx.tmp('apply')
    with contextlib.redirect_stdout(io.StringIO()):
        out, report = gfxapply.apply_targets(ctx.base, ctx.base, ['labels'], work=os.path.join(folder, 'work'),
                                             gfx_dir=os.path.join(folder, 'gfx'))
    lo, hi = RANGE[0] - ROM_BASE, RANGE[1] - ROM_BASE
    assert out[:lo] == ctx.base[:lo] and out[hi:] == ctx.base[hi:], 'bytes changed outside the label block'
    for n in range(L.COUNT):
        got = out[lo + L.SIZE * n:lo + L.SIZE * (n + 1)]
        want = L.original(ctx.base, n) if n == NEXT else ctx.data[n]
        assert got == want, 'label %02X' % n
    assert any('labels:' in line and '2 writes' in line for line in report), report
    # applying again is refused (the ranges are no longer original)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            gfxapply.apply_targets(ctx.base, out, ['labels'], work=os.path.join(folder, 'work2'),
                                   gfx_dir=os.path.join(folder, 'gfx2'))
    except Exception as e:
        assert 'another part of the patch changed' in str(e), e
    else:
        raise AssertionError('applying twice was not refused')


def test_original(ctx):
    """With the ROM: the original labels have the treatment this target copies
    (ink on rows 1-6, outline colour 3 on rows 0-7 around it)."""
    if not ctx.real:
        print('     (skipped: give the ROM to check the original art)')
        return
    four_ok = four_all = diag_ok = diag_all = 0
    for n in range(L.COUNT):
        bm = L.decode(L.original(ctx.base, n))
        assert L.ink_rows(bm) == (1, 6), (n, L.ink_rows(bm))
        ink = {(x, y) for y in range(8) for x in range(64) if bm.get(x, y) in (1, 2)}
        four = {(x + dx, y + dy) for x, y in ink for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
        four = {(x, y) for x, y in four - ink if 0 <= x < 64 and 0 <= y < 8}
        diag = {(x + dx, y + dy) for x, y in ink for dx in (-1, 1) for dy in (-1, 1)}
        diag = {(x, y) for x, y in diag - ink - four if 0 <= x < 64 and 0 <= y < 8}
        four_ok += sum(1 for x, y in four if bm.get(x, y) == 3)
        four_all += len(four)
        diag_ok += sum(1 for x, y in diag if bm.get(x, y) == 3)
        diag_all += len(diag)
    assert four_ok >= four_all - 1, (four_ok, four_all)            # a 1-px outline all around
    assert diag_ok > 0.8 * diag_all, (diag_ok, diag_all)            # mostly 8-neighbour


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_quoted_names(ctx):
    """Names that help texts and dialogue quote equal the labels."""
    files = {}
    for n, name, text in QUOTED:
        assert ctx.labels[n] == text, 'label %02X is %r, but %s quotes "%s"' % (n, ctx.labels[n], name, text)
        body = files.setdefault(name, _read(os.path.join(L.ROOT, 'translation', 'en', name)))
        assert '"%s"' % text in body, '%s no longer quotes "%s" (label %02X)' % (name, text, n)
    entries = {line.strip() for line in files.setdefault('ui.txt', _read(os.path.join(
        L.ROOT, 'translation', 'en', 'ui.txt'))).splitlines()}
    for n in SAME_ENTRY:
        assert ctx.labels[n] in entries, 'label %02X %r is not a map popup entry of ui.txt' % (n, ctx.labels[n])


def _dump(entries, vram):
    m = bytearray(0x10000)
    m[0x400D] = len(entries)
    for i, (words, dest, src) in enumerate(entries):
        a = 0x400E + 8 * i
        m[a:a + 8] = words.to_bytes(2, 'little') + dest.to_bytes(2, 'little') + src.to_bytes(4, 'little')
    for addr, data in vram.items():
        m[addr:addr + len(data)] = data
    return bytes(m)


def _screen(path, mark=None):
    img = [[(10, 20, 30)] * 160 for _ in range(152)]
    if mark:
        img[mark[1]][mark[0]] = (255, 255, 255)
    png.write_rgb(path, 160, 152, img, 2)


def test_check(ctx):
    """check_dumps on synthetic dumps: the queue names the label, VRAM equals
    the ROM and the built label; expected order; screenshots compared outside
    the strip only."""
    final = L.final(ctx.data, ctx.base)
    rom = bytearray(ctx.base)
    lo = RANGE[0] - ROM_BASE
    rom[lo:lo + 45 * 128] = b''.join(final)
    rom = bytes(rom)
    run, ref = ctx.tmp('run'), ctx.tmp('ref')
    for frame, n in ((10, 0x03), (20, NEXT)):
        with open(os.path.join(run, 'mem_%05d.bin' % frame), 'wb') as f:
            f.write(_dump([(0x40, 0xAC00, L.address(n)), (8, 0xB9D0, 0x20AE54)], {0xAC00: final[n]}))
        _screen(os.path.join(run, 'frame_%05d.png' % frame), (60, 90))       # inside the strip
        _screen(os.path.join(ref, 'frame_%05d.png' % frame))
    quiet = []
    ok, found = L.check_dumps(rom, run, final, 0xAC00, [0x03, NEXT], ref, quiet.append)
    assert ok and found == [0x03, NEXT], quiet
    ok, _ = L.check_dumps(rom, run, final, 0xAC00, [0x05, NEXT], None, quiet.append)
    assert not ok
    ok, _ = L.check_dumps(rom, run, final, 0xB600, None, None, quiet.append)
    assert not ok                                       # no copy to that destination
    _screen(os.path.join(run, 'frame_00020.png'), (30, 90))                 # outside the strip
    ok, _ = L.check_dumps(rom, run, final, 0xAC00, None, ref, quiet.append)
    assert not ok
    bad = bytearray(final[0x03])
    bad[5] ^= 0xFF
    with open(os.path.join(run, 'mem_00010.bin'), 'wb') as f:
        f.write(_dump([(0x40, 0xAC00, L.address(0x03))], {0xAC00: bytes(bad)}))
    _screen(os.path.join(run, 'frame_00020.png'), (60, 90))
    ok, _ = L.check_dumps(rom, run, final, 0xAC00, None, ref, quiet.append)
    assert not ok
    assert any('VRAM differs' in line for line in quiet)


def test_cli(ctx):
    """fit and preview from the command line."""
    folder = ctx.tmp('cli')
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert L.main(['fit']) == 0
        assert L.main(['preview', folder, '--base', ctx.rom_path]) == 0
    text = out.getvalue()
    assert '14  Rite of revival   63' in text and 'original art kept' in text, text
    assert os.path.isfile(os.path.join(folder, 'preview.png'))
    assert os.path.isfile(os.path.join(folder, 'compare_x3.png'))


TESTS = [test_source, test_parse_errors, test_fit, test_style, test_encode, test_output, test_result, test_apply,
         test_original, test_quoted_names, test_check, test_cli]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    real = False
    if argv:
        base = open(argv[0], 'rb').read()
        if hashlib.sha1(base).hexdigest() != EXPECTED_SHA1:
            print('error: %s is not the original ROM' % argv[0])
            return 1
        real = True
    else:
        base = synthetic_rom()
        print('note: no ROM given; the apply-path tests use a synthetic ROM')
    failed = 0
    with tempfile.TemporaryDirectory(prefix='test_labels_') as folder:
        ctx = Ctx(folder, base, real)
        ctx.rom_path = os.path.join(folder, 'base.ngc')
        with open(ctx.rom_path, 'wb') as f:
            f.write(base)
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
