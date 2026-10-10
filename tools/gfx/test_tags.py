"""Tests for the graphics target 'tags' (tools/gfx/tags.py).

Usage: python -m tools.gfx.test_tags [ROM]

ROM  the original ROM (rom/baserom.ngc). With it, the tests also check the
     game's own tags at build time: everything of our deployed tag outside
     the lettering area (box, blue margins, transparent columns) equals the
     original's at both addresses, the original lettering fills exactly that
     area (ink at x 8-31, last shadow at x 32), the original paralysis label
     uses the colour indices ours uses; and applying the target to the
     original ROM changes only its three ranges, with the built bytes.

Without the ROM, a synthetic base holds our own box at the deployed addresses
(no ROM data). Covers: the font (6 rows, character set, widths), the text file
and its errors, the deployed tag (box, transparent columns, blue margins, ink
area, the right shadow, centring, FitError above 24 px), the paralysis label
(colours, 8-neighbour outline, rows, centring and cut outline columns,
FitError), the Result (ranges, sizes, identical copies, determinism), the
frame check (box and margins), the harness dump check on synthetic dumps, the
registry entry and the command line.

Everything is written to a temporary folder; build/ and the repository are not
touched.
"""
import contextlib
import io
import os
import sys
import tempfile
import traceback

from ..patch.layout import FREE_START
from ..recomp.rom import ROM_BASE
from . import build as gfxbuild
from . import tags as T
from .font import MissingGlyphError
from .image import Bitmap
from .target import Context, Result, TargetError
from .textart import FitError
from .tiles import tiles_rowmajor

ROOT = T.ROOT
ROM_SIZE = 0x200000
N8 = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1))
ROWS = range(T.TEXT_TOP, T.TEXT_TOP + T.TEXT_ROWS)              # the lettering rows 1-6
MARGINS = [x for x in range(T.INNER_X0, T.INNER_X1 + 1) if not T.LETTER_X0 <= x <= T.SHADOW_X]

_base = None                                    # the original ROM when given


def font():
    return T.load_tag_font(ROOT)


def texts():
    return T.load_text(os.path.join(ROOT, 'translation', 'en', T.TEXT_FILE))


def box_only():
    """Our deployed tag with no lettering (box and fill only)."""
    bm = Bitmap(T.DEPLOYED_W, T.DEPLOYED_H)
    for y in range(T.DEPLOYED_H):
        for x in range(T.BOX_X0, T.BOX_X1 + 1):
            bm.set(x, y, T.DARK if y in (0, T.DEPLOYED_H - 1) or x in (T.BOX_X0, T.BOX_X1) else T.FILL)
    return bm


def synthetic_base():
    """2 MB of a fixed pattern, 0xFF from FREE_START, our box-only tag at the
    deployed addresses (no ROM data)."""
    n = FREE_START - ROM_BASE
    pattern = bytes(((i * 5) ^ (i >> 2)) & 0xFF for i in range(4096))
    rom = bytearray((pattern * (n // len(pattern) + 1))[:n]) + b'\xFF' * (ROM_SIZE - n)
    frame = tiles_rowmajor(box_only())
    for a in T.DEPLOYED_ADDRS:
        rom[a - ROM_BASE:a - ROM_BASE + len(frame)] = frame
    return bytes(rom)


def base():
    return _base if _base is not None else synthetic_base()


def run_build(tmp, b=None):
    b = base() if b is None else b
    ctx = Context(ROOT, 'tags', b, b, os.path.join(tmp, 'work'), None, None, log=lambda s: None)
    return T.build(ctx)


def ink_of(bm):
    return {(x, y) for y in range(bm.h) for x in range(bm.w) if bm.get(x, y) == T.INK}


def check_deployed(bm, text, f):
    """The invariants of a deployed tag (module notes)."""
    assert (bm.w, bm.h) == (40, 8), (bm.w, bm.h)
    for y in range(8):
        for x in range(40):
            v = bm.get(x, y)
            if x < T.BOX_X0 or x > T.BOX_X1:
                assert v == 0, ('transparent column', x, y, v)
            elif y in (0, 7) or x in (T.BOX_X0, T.BOX_X1):
                assert v == T.DARK, ('border', x, y, v)
            elif not T.in_lettering(x, y):
                assert v == T.FILL, ('blue margin (the original keeps x 5-7 and 33-34 blue)', x, y, v)
            else:
                assert v in (T.INK, T.FILL, T.DARK), ('interior colour', x, y, v)
    ink = ink_of(bm)
    assert ink, 'no ink'
    assert all(T.LETTER_X0 <= x <= T.LETTER_X1 and y in ROWS for x, y in ink), 'ink outside x 8-31, rows 1-6'
    for x, y in ink:                                            # right shadow
        assert bm.get(x + 1, y) in (T.INK, T.DARK), ('no shadow right of', x, y)
    for y in ROWS:
        for x in range(T.INNER_X0, T.INNER_X1 + 1):
            if bm.get(x, y) == T.DARK:
                assert (x - 1, y) in ink, ('dark pixel not a shadow', x, y)
                assert x <= T.SHADOW_X, ('shadow right of x 32', x, y)
    w = T.ink_width(f, text)
    x0 = min(x for x, _ in ink)
    assert x0 == T.LETTER_X0 + (T.LETTER_W - w) // 2, ('centring', x0, w)
    assert max(x for x, _ in ink) == x0 + w - 1
    # the ink is the word's own ink, unchanged
    word = T.render(f, text, T.INK_STYLE)
    assert {(x - x0, y - T.TEXT_TOP) for x, y in ink} == \
        {(x, y) for y in range(word.h) for x in range(word.w) if word.get(x, y)}, 'ink differs from the font'


def check_paralysis(bm, text, f):
    assert (bm.w, bm.h) == (16, 8), (bm.w, bm.h)
    assert bm.values() <= {0, T.INK, T.DARK}, bm.values()
    ink = ink_of(bm)
    assert ink and all(T.TEXT_TOP <= y <= T.TEXT_TOP + 5 for _, y in ink), 'ink rows'
    ring = {(x + dx, y + dy) for x, y in ink for dx, dy in N8} - ink
    ring = {(x, y) for x, y in ring if 0 <= x < 16 and 0 <= y < 8}
    dark = {(x, y) for y in range(8) for x in range(16) if bm.get(x, y) == T.DARK}
    assert dark == ring, ('outline is not the 8-neighbour ring', sorted(dark ^ ring))
    w = T.ink_width(f, text)
    x0 = min(x for x, _ in ink)
    assert x0 == (16 - w) // 2, ('centring', x0, w)


def expect_fit_error(fn, text, width, limit):
    try:
        fn(font(), text)
    except FitError as e:
        assert (e.width, e.limit) == (width, limit), (text, e.width, e.limit)
    else:
        raise AssertionError('%r (%d px) fitted a %d-px limit' % (text, width, limit))


# ---------------------------------------------------------------------------

def test_font():
    f = font()
    assert f.height == 6
    for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ!?-. ':
        assert ch in f, 'missing %r' % ch
    widths = {name: g.width for name, g in f.glyphs.items()}
    assert widths['I'] == 1 and widths['L'] == 2 and widths['M'] == 5 and widths['W'] == 5
    assert all(widths[c] == 3 for c in 'ABCDEFGHJKNOPQRSTUVXYZ'), widths
    for name, g in f.glyphs.items():
        assert all(len(r) == g.width for r in g.rows) and g.height == 6, name
        if name != 'SPACE':
            assert g.advance == g.width + 1, name
            cols = [any(r[x] == '#' for r in g.rows) for x in range(g.width)]
            assert cols[0] and cols[-1], '%s has a blank edge column' % name
    assert T.ink_width(f, 'FIELDED') == 24 and T.ink_width(f, 'STUN') == 15
    assert T.ink_width(f, 'ON MAP') == 23 and T.ink_width(f, 'DEPLOYED') == 30
    with open(os.path.join(ROOT, T.FONT_FILE), 'rb') as fh:
        raw = fh.read()
    assert raw.isascii(), 'the font is ASCII'      # LF or CRLF (git checks out CRLF on Windows)


def test_text_file():
    t = texts()
    assert set(t) == set(T.KEYS)
    for k, v in t.items():
        assert v is None or (v.isascii() and v == v.upper()), (k, v)
    with open(os.path.join(ROOT, 'translation', 'en', T.TEXT_FILE), 'rb') as fh:
        raw = fh.read()
    assert raw.isascii(), 'tags.txt is ASCII'         # LF or CRLF (git checks out CRLF on Windows)


def test_text_errors():
    ok = T.parse_text('# c\n@deployed ON MAP\n@paralysis keep\n')
    assert ok == {'deployed': 'ON MAP', 'paralysis': None}
    for bad, word in (('@deployed A\n@deployed B\n@paralysis C\n', 'twice'),
                      ('@deployed A\n', 'missing'),
                      ('@deployed A\n@paralysis B\n@other C\n', 'unknown key'),
                      ('@deployed\n@paralysis B\n', 'no text'),
                      ('deployed A\n@paralysis B\n', 'expected')):
        try:
            T.parse_text(bad)
        except TargetError as e:
            assert word in str(e), (word, str(e))
        else:
            raise AssertionError('accepted: %r' % bad)


def test_deployed_current():
    f = font()
    t = texts()['deployed']
    if t is not None:
        check_deployed(T.render_deployed(f, t), t, f)


def test_deployed_others():
    f = font()
    for text in ('FIELDED', 'ON MAP', 'IN FIELD', 'AFIELD', 'SORTIE', 'DEPLOY', 'OUT', 'A', 'MW'):
        check_deployed(T.render_deployed(f, text), text, f)
    bm = T.render_deployed(f, 'FIELDED')                       # 24 px: exactly the original lettering area
    inks = {x for x, _ in ink_of(bm)}
    assert (min(inks), max(inks)) == (T.LETTER_X0, T.LETTER_X1) == (8, 31), (min(inks), max(inks))
    assert any(bm.get(T.SHADOW_X, y) == T.DARK for y in ROWS), 'no shadow at x 32'
    assert all(bm.get(x, y) == T.FILL for x in MARGINS for y in ROWS), 'margins not blue'
    assert MARGINS == [5, 6, 7, 33, 34], MARGINS
    bm = T.render_deployed(f, 'ON MAP')                        # 23 px: x 8-30, left bias
    assert min(x for x, _ in ink_of(bm)) == 8 and max(x for x, _ in ink_of(bm)) == 30
    expect_fit_error(T.render_deployed, 'DEPLOYED', 30, T.LETTER_W)   # the previous word: 30 px
    expect_fit_error(T.render_deployed, 'ON DUTY', 25, T.LETTER_W)    # one px too many
    assert T.LETTER_W == 24
    try:
        T.render_deployed(f, 'Fielded')
    except MissingGlyphError:
        pass
    else:
        raise AssertionError('lower case accepted')


def test_paralysis_current():
    f = font()
    t = texts()['paralysis']
    if t is not None:
        check_paralysis(T.render_paralysis(f, t), t, f)


def test_paralysis_others():
    f = font()
    for text in ('ZAP!', 'STOP', 'A', 'HALT'):
        check_paralysis(T.render_paralysis(f, text), text, f)
    bm = T.render_paralysis(f, 'STUN')                         # 15 px: the left outline column is cut
    assert any(bm.get(0, y) == T.INK for y in range(8))
    assert all(bm.get(15, y) != T.INK for y in range(8)), 'right outline column kept'
    assert all(bm.get(15, y) == T.DARK for y in range(8) if bm.get(14, y) == T.INK)
    bm = T.render_paralysis(f, 'ZAP!')                         # 13 px: full outline
    assert all(bm.get(x, y) != T.INK for y in range(8) for x in (0, 15))
    expect_fit_error(T.render_paralysis, 'STUNS', 19, 16)


def test_result():
    with tempfile.TemporaryDirectory() as tmp:
        r = run_build(tmp)
        assert isinstance(r, Result) and r.asm is None
        assert r.allow == T.ranges()
        addrs = [a for a, _ in r.writes]
        assert addrs == [0x214A00, 0x2E736A, 0x2FE5ED], addrs
        sizes = [len(d) for _, d in r.writes]
        assert sizes == [80, 80, 32], sizes
        assert r.writes[0][1] == r.writes[1][1], 'the two deployed copies differ'
        for a, d in r.writes:
            assert any(lo <= a and a + len(d) <= hi for lo, hi in r.allow), hex(a)
            assert a + len(d) <= FREE_START
        spans = sorted(r.allow)
        assert all(spans[i][1] <= spans[i + 1][0] for i in range(len(spans) - 1)), 'overlapping ranges'
        f = font()
        t = texts()
        assert r.writes[0][1] == tiles_rowmajor(T.render_deployed(f, t['deployed']))
        assert r.writes[2][1] == tiles_rowmajor(T.render_paralysis(f, t['paralysis']))
        assert all(os.path.isfile(p) and p.startswith(tmp) for p in r.previews), r.previews
        r2 = run_build(tmp)
        assert [(a, d) for a, d in r.writes] == [(a, d) for a, d in r2.writes], 'not deterministic'


def test_keep():
    f = font()
    b = T.Built({'deployed': None, 'paralysis': 'STUN'}, f)
    assert [a for a, _ in b.writes()] == [0x2FE5ED]
    b = T.Built({'deployed': 'FIELDED', 'paralysis': None}, f)
    assert [a for a, _ in b.writes()] == list(T.DEPLOYED_ADDRS)


def _with_pixel(rom, addr, x, y, v):
    """A copy of the ROM image whose deployed strip at addr has pixel (x, y) = v."""
    out = bytearray(rom)
    o = addr - ROM_BASE
    strip = T.decode_strip(out[o:o + 80], 5)
    strip.set(x, y, v)
    out[o:o + 80] = tiles_rowmajor(strip)
    return bytes(out)


def test_frame_check():
    f = font()
    built = T.Built(texts(), f)
    b = synthetic_base()
    T.check_frame(lambda a, n: b[a - ROM_BASE:a - ROM_BASE + n], built)
    # the lettering area x 8-32, rows 1-6 may differ (the original lettering is there)
    ok = _with_pixel(_with_pixel(b, 0x214A00, 8, 1, T.INK), 0x214A00, 32, 6, T.DARK)
    T.check_frame(lambda a, n: ok[a - ROM_BASE:a - ROM_BASE + n], built)
    # a border pixel of the copy, a blue margin pixel (left and right), a transparent column
    for addr, x, y, v in ((0x2E736A, 4, 0, T.FILL), (0x214A00, 6, 3, T.INK), (0x2E736A, 33, 5, T.DARK),
                          (0x214A00, 7, 1, T.DARK), (0x214A00, 34, 6, T.INK), (0x2E736A, 38, 2, T.INK)):
        bad = _with_pixel(b, addr, x, y, v)
        try:
            T.check_frame(lambda a, n: bad[a - ROM_BASE:a - ROM_BASE + n], built)
        except TargetError as e:
            assert '%06X' % addr in str(e) and 'x %d, y %d' % (x, y) in str(e), str(e)
        else:
            raise AssertionError('a changed pixel at x %d, y %d of %06X was accepted' % (x, y, addr))


def _dump(tile0, data, sprites):
    m = bytearray(0x10000)
    m[0xA000 + 16 * tile0:0xA000 + 16 * tile0 + len(data)] = data
    for n, (tile, x, y, pal) in enumerate(sprites):
        m[0x8800 + 4 * n:0x8800 + 4 * n + 4] = bytes((tile & 0xFF, 0x10 | (tile >> 8), x, y))
        m[0x8C00 + n] = pal
    return bytes(m)


def test_check_dump():
    built = T.Built(texts(), font())
    t0, p0 = T.DEPLOYED_VRAM_TILE, T.PARALYSIS_VRAM_TILE
    dep = [(t0 + i, 8 + 8 * i, 54, T.DEPLOYED_PAL) for i in range(5)]
    ok, lines = T.check_dump(_dump(t0, built.deployed_bytes, dep), built)
    assert ok and 'holds' in lines[0], lines
    ok, lines = T.check_dump(_dump(t0, bytes(80), dep), built)
    assert not ok, lines                                       # a blank deployed tag is an error
    ok, lines = T.check_dump(_dump(t0, built.deployed_bytes, dep[:3]), built)
    assert not ok and 'NOT a whole tag' in lines[0], lines
    para = [(p0, 72, 28, T.PARALYSIS_PAL), (p0 + 1, 80, 28, T.PARALYSIS_PAL)]
    ok, lines = T.check_dump(_dump(p0, built.paralysis_bytes, para), built)
    assert ok, lines
    ok, lines = T.check_dump(_dump(p0, bytes(32), para), built)
    assert ok and 'wiped' in lines[0], lines                   # the game clears the label
    ok, lines = T.check_dump(_dump(p0, b'\xFF' * 32, para), built)
    assert not ok, lines
    ok, lines = T.check_dump(bytes(0x10000), built)
    assert ok and 'no tag shown' in lines[0]


def test_registry():
    assert gfxbuild.TARGETS.get('tags', 'absent') is None, 'tags must be registered in place only'
    assert isinstance(T.FULL_BUILD, bool)
    selected, notes = gfxbuild.select_targets(None)       # the full build takes it only when enabled
    if T.FULL_BUILD:
        assert 'tags' in [t.name for t in selected]
        assert ('tags', gfxbuild.LEFT_OUT) not in notes, notes
    else:
        assert 'tags' not in [t.name for t in selected]
        assert ('tags', gfxbuild.LEFT_OUT) in notes, notes
    selected, notes = gfxbuild.select_targets(['tags'])
    assert [t.name for t in selected] == ['tags']


def test_cli():
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = T.main(['fit'])
    t = texts()
    for k in T.KEYS:
        assert code == 0 and (t[k] or 'keep') in out.getvalue(), out.getvalue()
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            assert T.main(['preview', tmp]) == 0
        assert sorted(os.listdir(tmp)) == ['deployed.png', 'deployed_8x.png', 'paralysis.png', 'paralysis_8x.png']


# --- with the original ROM ---------------------------------------------------

def test_rom_frame():
    """Everything outside the lettering area x 8-32, rows 1-6 (box, blue
    margins, transparent columns) equals the original's at both addresses
    (build-time check); the original lettering fills exactly that area (ink at
    x 8-31, last shadow at x 32); the two copies are identical."""
    f = font()
    built = T.Built(texts(), f)
    T.check_frame(lambda a, n: _base[a - ROM_BASE:a - ROM_BASE + n], built)
    a, b = (_base[x - ROM_BASE:x - ROM_BASE + 80] for x in T.DEPLOYED_ADDRS)
    assert a == b, 'the two original copies differ'
    orig = T.decode_strip(a, 5)
    assert T.frame_cells(orig) == T.frame_cells(box_only()), 'original lettering outside the area'
    inks = [x for x, _ in ink_of(orig)]
    darks = [x for y in ROWS for x in range(T.INNER_X0, T.INNER_X1 + 1) if orig.get(x, y) == T.DARK]
    assert (min(inks), max(inks), max(darks)) == (T.LETTER_X0, T.LETTER_X1, T.SHADOW_X), \
        (min(inks), max(inks), max(darks))


def test_rom_paralysis_colours():
    off = T.PARALYSIS_ADDR - ROM_BASE
    orig = T.decode_strip(_base[off:off + 32], 2)
    assert orig.values() == {0, T.INK, T.DARK}, orig.values()
    rows = {y for y in range(8) for x in range(16) if orig.get(x, y) == T.INK}
    assert rows == set(range(1, 7)), rows                      # the same ink rows as ours


def test_rom_apply():
    from .apply import apply_targets
    with tempfile.TemporaryDirectory() as tmp:
        out, report = apply_targets(_base, _base, ['tags'], work=tmp, gfx_dir=tmp, log=lambda s: None)
        built = T.Built(texts(), font())
        lo_hi = [(lo - ROM_BASE, hi - ROM_BASE) for lo, hi in T.ranges()]
        for a, d in built.writes():
            assert out[a - ROM_BASE:a - ROM_BASE + len(d)] == d, hex(a)
        diff = 0
        for k in range(0, len(out), 4096):
            if out[k:k + 4096] != _base[k:k + 4096]:
                for i in range(k, min(len(out), k + 4096)):
                    if out[i] != _base[i]:
                        diff += 1
                        assert any(lo <= i < hi for lo, hi in lo_hi), 'changed byte at %06X' % (i + ROM_BASE)
        assert diff > 0
        assert any('tags' in line for line in report), report
        for addr in T.DEPLOYED_ADDRS:                            # only the lettering area changed
            o = addr - ROM_BASE
            old, new = T.decode_strip(_base[o:o + 80], 5), T.decode_strip(out[o:o + 80], 5)
            assert T.frame_cells(old) == T.frame_cells(new), '%06X: a pixel outside the lettering changed' % addr


TESTS = [test_font, test_text_file, test_text_errors, test_deployed_current, test_deployed_others,
         test_paralysis_current, test_paralysis_others, test_result, test_keep, test_frame_check,
         test_check_dump, test_registry, test_cli]
ROM_TESTS = [test_rom_frame, test_rom_paralysis_colours, test_rom_apply]


def main(argv=None):
    global _base
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        with open(argv[0], 'rb') as fh:
            _base = fh.read()
        from ..recomp.rom import EXPECTED_SHA1
        import hashlib
        if hashlib.sha1(_base).hexdigest() != EXPECTED_SHA1:
            print('error: %s is not the original ROM' % argv[0])
            return 2
    tests = TESTS + (ROM_TESTS if _base is not None else [])
    failed = 0
    for t in tests:
        try:
            t()
            print('ok    %s' % t.__name__)
        except Exception:
            failed += 1
            print('FAIL  %s' % t.__name__)
            traceback.print_exc(file=sys.stdout)
    skipped = '' if _base is not None else ' (%d ROM tests skipped: no ROM given)' % len(ROM_TESTS)
    print('test_tags: %d of %d passed%s' % (len(tests) - failed, len(tests), skipped))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
