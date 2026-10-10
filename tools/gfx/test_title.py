"""Tests for the graphics target 'title' (tools/gfx/title.py).

Usage: python -m tools.gfx.test_title [ROM]

ROM  the original ROM (rom/baserom.ngc). With it, the tests also run the
     target on the original ROM (tools.gfx.apply path) and check: only pool
     tiles change; the maps change only in rows 7-12 of both planes and in
     rows 1-3 of the window block; the reserved cells, every palette (plane-2
     palette 5 colour 3 included) and everything else stay as they are; the
     flag sprite count goes from 50 to 48; two builds are identical; the
     package checks and the harness-dump check work on the result.

Without the ROM: the text file and its errors; the fonts (rows, character
set, the subtitle font's italic grid, the main font's 3-px stems); both
layers (size, palettes 'keep', one palette per cell, reserved cells empty,
the wording header); the original treatment on our art (plane 2 transparent
under the fill, a black outline on the 4 neighbours of every fill pixel and
on its diagonal steps, the glow only in map rows 7-10 and the subtitle only
in rows 11-12, a brown outline on the 4 neighbours and the diagonal steps of
the subtitle's letters, fire and white fills in separate cells, the
original's rows: fill 65-83, the outline on 84, a light glow on 85-86 and
row 87 empty above the subtitle letters 89-97, the kicker in row 7 left of
the arm, nothing but the outline under the fist's thumb); the outer-edge
rule of the glow; the tile budget and pool; the window text (fit, cells,
blank interior); the in-place writes (inside the declared ranges, no
overlaps, the flag count, no palette writes); the draft (reproduces the
committed art, deterministic, other wordings, FitError); the wording check;
the registry entry and the command line.

Everything is written to a temporary folder; build/ and the repository are not
touched.
"""
import contextlib
import hashlib
import io
import os
import sys
import tempfile
import traceback

from ..recomp.rom import EXPECTED_SHA1, ROM_BASE
from . import build as gfxbuild
from . import title as T
from .font import load_font
from .target import TargetError
from .textart import FitError
from .tiles import cell_slot, cells

ROOT = T.ROOT
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

_base = None                                    # the original ROM when given


def texts():
    return T.load_text(os.path.join(ROOT, 'translation', 'en', T.TEXT_FILE))


def layers():
    return T.load_layers(ROOT)


def plan():
    return T.make_plan(ROOT)


def screen(layer):
    """{(x, screen y): pixel} of a layer's non-zero pixels."""
    bm = layer.bitmap
    return {(x, T.LOGO_Y + y): bm.get(x, y) for y in range(bm.h) for x in range(bm.w) if bm.get(x, y)}


# ---------------------------------------------------------------------------

def test_text_file():
    t = texts()
    assert t['kicker'] == 'THE LEGEND OF', t['kicker']
    assert T.logo_parts(t['logo']) == ('OGRE BATTLE', 'GAIDEN'), t['logo']
    assert t['subtitle'] == 'PRINCE OF ZENOBIA'
    assert (t['window1'], t['window2'], t['yes'], t['no']) == (
        'The suspend data will be erased.', 'Is that OK?', 'Yes', 'No')
    for v in t.values():
        assert all(ord(c) < 128 for c in v), v


def test_text_errors():
    good = '@kicker A\n@logo B|C\n@subtitle D\n@window E\n@window F\n@yes G\n@no H\n'
    T.parse_text(good)
    assert T.parse_text(good.replace('@kicker A', '@kicker'))['kicker'] == ''
    for bad, word in ((good.replace('@yes G\n', ''), 'missing'),
                      (good + '@no I\n', 'twice'),
                      (good + '@window X\n', 'twice (window lines'),
                      (good.replace('@logo B|C', '@logo B|C|D'), 'more than one'),
                      (good.replace('@subtitle D', '@subtitle'), 'no text'),
                      (good + '@colour red\n', 'unknown key'),
                      (good + 'plain line\n', 'expected')):
        try:
            T.parse_text(bad)
        except TargetError as e:
            assert word in str(e), (word, str(e))
        else:
            raise AssertionError('no error for %r' % bad)


def test_fonts():
    main = load_font(os.path.join(ROOT, T.LOGO_FONT))
    kick = load_font(os.path.join(ROOT, T.KICKER_FONT))
    sub = load_font(os.path.join(ROOT, T.SUB_FONT))
    assert (main.height, kick.height, sub.height) == (19, 5, 9), (main.height, kick.height, sub.height)
    letters = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    for f in (main, kick, sub):
        assert letters | {'SPACE'} == set(f.glyphs), (f.name, sorted(set(f.glyphs) ^ letters))
        for name, g in f.glyphs.items():
            if name == 'SPACE':
                continue
            assert g.advance == g.width + 1, (f.name, name)
            rows = g.rows
            assert '#' in rows[0] and '#' in rows[-1], (f.name, name)      # the full height
            if f is sub:
                # italic on an upright grid of 5x9 (I: 1x9): rows 0-2 shifted 2 px right
                # of rows 6-8, rows 3-5 1 px
                assert g.width - 2 == (1 if name == 'I' else 5), (name, g.width)
                assert all(r[:2] == '..' for r in rows[:3]) and all(r[0] == '.' for r in rows[3:6]), name
                assert all(r[-2:] == '..' for r in rows[6:]) and all(r[-1] == '.' for r in rows[3:6]), name
            else:
                assert any(r[0] == '#' for r in rows) and any(r[-1] == '#' for r in rows), (f.name, name)
    # the main title's stems are 3 px wide: no ink run in a row is 1 or 2 px long except
    # at the slanted and tapered places that the design allows (none in I, H, U)
    for name in 'IHU':
        for r in main.glyph(name).rows:
            runs = [len(s) for s in r.split('.') if s]
            assert all(n >= 3 for n in runs), (name, r)


def test_layers():
    t = texts()
    front, back = layers()
    for layer, plane, nums in ((front, 'plane1', (0, 1)), (back, 'plane2', (0, 5))):
        assert (layer.bitmap.w, layer.bitmap.h) == (160, 48)
        assert layer.plane == plane
        assert tuple(p.number for p in layer.palettes) == nums, layer.palettes
        assert all(p.plane == plane and p.colors == (None, None, None) for p in layer.palettes), \
            'the logo keeps the original colours'
        for cell in cells(layer.bitmap):
            slot = cell_slot(cell)                  # raises when a cell mixes palettes
            if (T.ROW0 + cell.row, cell.col) in T.RESERVED:
                assert slot is None, (layer.path, cell.row, cell.col)
        assert layer.wording == {'kicker': t['kicker'], 'logo': t['logo'], 'subtitle': t['subtitle']}
    T.check_wording(t, front, back)


def test_treatment():
    """The structure of the original logo, on our art."""
    front, back = layers()
    f, b = screen(front), screen(back)
    assert not set(f) & set(b), 'plane 2 must be transparent under the fill'
    for (x, y), v in f.items():
        assert 56 <= y < 88, 'fill outside map rows 7-10 at (%d, %d)' % (x, y)
        for dx, dy in N4:
            q = (x + dx, y + dy)
            if q not in f:
                assert b.get(q) == 3, 'no black outline at %r next to the fill' % (q,)
    fire = {p for p, v in f.items() if v >> 2 == 0}
    white = {p for p, v in f.items() if v >> 2 == 1}
    assert fire and white
    assert max(x for x, _ in fire) // 8 < min(x for x, _ in white) // 8, 'fire and white share a cell column'
    glow = {p: v & 3 for p, v in b.items() if v >> 2 == 0}
    sub = {p: v & 3 for p, v in b.items() if v >> 2 == 1}
    assert all(56 <= y < 88 for _, y in glow), 'glow outside map rows 7-10'
    assert all(88 <= y < 104 for _, y in sub), 'subtitle outside map rows 11-12'
    assert set(glow.values()) == {1, 2, 3} and set(sub.values()) == {1, 2}, (set(glow.values()), set(sub.values()))
    for (x, y), c in sub.items():
        if c == 2:
            for dx, dy in N4:
                assert sub.get((x + dx, y + dy)) in (1, 2), 'subtitle letter without a brown outline at %r' % ((x, y),)
    # every glow pixel touches the fill or another glow pixel (no stray dots)
    for (x, y) in glow:
        assert any((x + dx, y + dy) in glow or (x + dx, y + dy) in f for dx, dy in N4), (x, y)
    # a diagonal step of the fill (a pixel between two fill diagonals) is outlined in black,
    # as in the original; so is a step of the subtitle in brown
    def in_glow(q):
        return (T.GLOW_X[0] <= q[0] < T.GLOW_X[1] and T.GLOW_ROWS[0] <= q[1] < T.GLOW_ROWS[1]
                and (q[1] // 8, q[0] // 8) not in T.RESERVED)

    def in_sub(q):
        return T.SUB_ROWS[0] <= q[1] < T.SUB_ROWS[1]

    steps = 0
    for ink, ring, colour, inside in ((set(f), glow, 3, in_glow),
                                      ({p for p, c in sub.items() if c == 2}, sub, 1, in_sub)):
        for (x, y) in ink:
            for dx, dy in T.D4:
                q = (x + dx, y + dy)
                if q in ink or not inside(q) or any((q[0] + a, q[1] + b) in ink for a, b in N4):
                    continue
                if sum((q[0] + a, q[1] + b) in ink for a, b in T.D4) >= 2:
                    steps += 1
                    assert ring.get(q) == colour, 'diagonal step at %r not outlined' % (q,)
    assert steps, 'no diagonal steps found (the check would be vacuous)'
    # the placement of the original lettering: fill rows 65-83 with the outline on 84,
    # subtitle letters (amber) rows 89-97 with their outline from 88, the kicker in row 7
    # left of the arm (column 11)
    main = [p for p in f if p[1] >= 64]
    assert (T.Y_MAIN, min(y for _, y in main), max(y for _, y in main)) == (65, 65, 83)
    amber = [p for p, c in sub.items() if c == 2]
    assert (min(y for _, y in amber), max(y for _, y in amber)) == (89, 97)
    kick = [p for p in f if p[1] < 64]
    assert kick and all(56 <= y < 64 and x <= T.KICK_MAX for x, y in kick)
    # under the main title, as in the original: the black outline (y 84), one row of blue
    # mixed with cyan (85), a few blue pixels (86), then nothing (87) above the subtitle
    assert not any(y >= 87 for _, y in glow) and not any(y < 88 for _, y in sub), 'row 87 must stay empty'
    row = {y: [c for (x, yy), c in glow.items() if yy == y] for y in (84, 85, 86)}
    assert row[84].count(3) > 60, row[84]
    assert 0.4 <= row[85].count(1) / len(row[85]) <= 0.7, row[85]
    assert set(row[86]) == {1} and len(row[86]) <= 0.35 * row[84].count(3), row[86]
    # under the fist's thumb: no fill, nothing of plane 2 but the black outline
    assert not [p for p in f if T.in_thumb(p)], 'fill under the thumb'
    assert all(glow.get(p) == 3 for p in b if T.in_thumb(p)), 'glow under the thumb'
    assert any(T.in_thumb(p) for p in glow), 'no outline under the thumb (the check would be vacuous)'


def test_outer_side():
    """Which side of the lettering a glow pixel is on (the glow follows the original by side)."""
    fill = {(0, 0), (8, 0)}
    assert T.outer_side(fill, (0, 2)) == 'below' and T.outer_side(fill, (0, -3)) == 'above'
    assert T.outer_side(fill, (-2, 0)) == 'left' and T.outer_side(fill, (10, 0)) == 'right'
    assert T.outer_side(fill, (4, 0)) is None, 'between two letters: enclosed'
    assert T.outer_side(fill, (2, 2)) == 'below' and T.outer_side(fill, (2, -2)) == 'above', 'diagonal'
    assert T.outer_side({(0, 0), (0, 4)}, (2, 2)) == 'corner', 'fill diagonally above and below'
    assert T.outer_side(fill, (0, 2 + T.OUTER_RAY)) == 'corner', 'farther than OUTER_RAY'
    # the shares measured on the original: under the letters ring 2 is bluer than above
    # them, and ring 3 is the sparsest there
    assert all(0 <= v <= 1 for t in T.OUTER_GLOW.values() for v in t)
    assert all(t[1] + t[2] <= 1 for t in T.OUTER_GLOW.values())
    assert T.OUTER_GLOW['below'][0] > T.OUTER_GLOW['above'][0]
    assert T.OUTER_GLOW['below'][1] + T.OUTER_GLOW['below'][2] == min(t[1] + t[2] for t in T.OUTER_GLOW.values())


def test_budget():
    p = plan()
    assert p.logo_tiles <= T.LOGO_BUDGET and p.window_tiles <= T.WINDOW_BUDGET, (p.logo_tiles, p.window_tiles)
    nums = [t for t, _ in p.tiles]
    assert len(set(nums)) == len(nums)
    assert nums == T.POOL[:len(nums)], 'tiles are allocated in pool order'
    k = min(p.window_tiles, len(T.WINDOW_TILES))
    assert nums[:k] == T.WINDOW_TILES[:k], 'the window takes the old window tiles first'
    assert len(T.POOL) == len(set(T.POOL)) == 230
    assert len(T.WINDOW_TILES) == 23 and len(T.OLD_LOGO) == 158 and len(T.UNUSED) == 49
    for entries in (p.p1, p.p2, p.win):
        for e in entries.values():
            assert e == 0 or (e & 0x1FF) in set(nums) | {T.WIN_BLANK}, hex(e)


def test_window():
    p = plan()
    for key, (w, limit) in p.win_widths.items():
        assert 0 < w <= limit, (key, w, limit)
    assert set(p.win) == {(r, c) for r in T.WIN_ROWS for c in T.WIN_COLS}
    blank = T.map_entry(T.WIN_BLANK, T.WIN_PAL)
    assert all((e >> 9) & 15 == T.WIN_PAL for e in p.win.values())
    # Yes from column 6, No from column 12 (right of the cursor at columns 5 and 11)
    assert p.win[(3, 6)] != blank and p.win[(3, 12)] != blank
    assert all(p.win[(3, c)] == blank for c in (1, 2, 3, 4, 5, 11)), [hex(p.win[(3, c)]) for c in range(1, 19)]
    wfont = load_font(os.path.join(ROOT, T.WINDOW_FONT))
    try:
        T.window_bitmap(wfont, 'Yes, of course', 5)
    except FitError:
        pass
    else:
        raise AssertionError('no FitError for a long answer')
    bm, w = T.window_bitmap(wfont, 'Is that OK?', 18)
    assert bm.values() <= {T.WIN_INK, T.WIN_PAPER} and bm.h == 8 and bm.w % 8 == 0


def test_writes():
    p = plan()
    ranges = T.ranges()
    writes = p.writes()
    end = 0
    for addr, data in writes:
        assert addr >= end, 'overlapping writes at %06X' % addr
        end = addr + len(data)
        assert any(lo <= addr and addr + len(data) <= hi for lo, hi in ranges), 'write %06X outside' % addr
    d = dict(writes)
    assert d[T.FLAG_LIST] == bytes((48,))
    assert not p.palette_writes()
    for base in (T.P1MAP, T.P2MAP):
        for row, col in T.RESERVED:
            a = base + 2 * (T.MAP_W * row + col)
            assert not any(lo <= a < hi for lo, hi in ranges), 'reserved cell %d,%d is writable' % (row, col)
    for plane, base in (('plane2', T.P2PAL),):
        a = base + 8 * 5 + 6
        assert not any(lo <= a < hi for lo, hi in ranges), 'plane-2 palette 5 colour 3 is writable'
    tiles = {a: t for t in T.POOL for a in [T.TILES + 16 * t]}
    for addr, data in writes:
        if T.TILES <= addr < T.TILES + 0x2000:
            assert addr in tiles and len(data) == 16, hex(addr)


def test_draft():
    t = texts()
    with tempfile.TemporaryDirectory() as tmp:
        paths, info = T.write_draft(t, tmp)
        for path, committed in zip(paths, (T.FRONT_FILE, T.BACK_FILE)):
            with open(path, encoding='utf-8') as a, open(os.path.join(ROOT, committed), encoding='utf-8') as b:
                assert a.read() == b.read(), '%s differs from the draft of title.txt' % committed
        paths2, _ = T.write_draft(t, os.path.join(tmp, 'again'))
        for a, b in zip(paths, paths2):
            assert open(a, 'rb').read() == open(b, 'rb').read(), 'the draft is not deterministic'


def test_draft_others():
    t = dict(texts())
    # no kicker: nothing in row 7, the main title and the subtitle in place
    t['kicker'] = ''
    front, back, info = T.draft(t, ROOT)
    ys = [y for y in range(48) for x in range(160) if front.get(x, y)]
    assert min(ys) + T.LOGO_Y == T.Y_MAIN, min(ys) + T.LOGO_Y
    subs = [y for y in range(48) for x in range(160) if back.get(x, y) >> 2 == 1 and back.get(x, y) & 3 == 2]
    assert min(subs) + T.LOGO_Y == T.Y_SUB
    # one word, all fire, centred
    t['logo'] = 'OGRE BATTLE'
    front, back, info = T.draft(t, ROOT)
    xs = [x for y in range(48) for x in range(160) if front.get(x, y)]
    assert abs((min(xs) + max(xs)) / 2 - T.BAND_CENTRE) <= 1, (min(xs), max(xs))
    assert {front.get(x, y) >> 2 for y in range(48) for x in range(160) if front.get(x, y)} == {0}
    # too long
    t['logo'] = 'OGRE BATTLE GAIDEN|SIDE STORY'
    try:
        T.draft(t, ROOT)
    except FitError:
        pass
    else:
        raise AssertionError('no FitError for a logo that does not fit')
    t = dict(texts())
    t['kicker'] = 'THE GREAT LEGEND OF'
    try:
        T.draft(t, ROOT)
    except FitError:
        pass
    else:
        raise AssertionError('no FitError for a kicker that reaches the arm')


def test_wording_check():
    t = dict(texts())
    front, back = layers()
    t['subtitle'] = 'PRINCE OF NOWHERE'
    try:
        T.check_wording(t, front, back)
    except TargetError as e:
        assert 'draft' in str(e) and 'subtitle' in str(e), str(e)
    else:
        raise AssertionError('no error when title.txt and the art disagree')
    text = open(os.path.join(ROOT, T.FRONT_FILE), encoding='utf-8').read()
    try:
        T.parse_layer(text.replace('# kicker:', '# kick:'), 'plane1', 'x.txt')
    except TargetError as e:
        assert 'kicker' in str(e)
    else:
        raise AssertionError('no error for a layer without its wording line')
    try:
        T.parse_layer(text.replace('plane1 1 ', 'plane1 2 '), 'plane1', 'x.txt')
    except TargetError as e:
        assert 'palette' in str(e)
    else:
        raise AssertionError('no error for a front layer on plane-1 palette 2')
    back_text = open(os.path.join(ROOT, T.BACK_FILE), encoding='utf-8').read()
    bad = back_text.replace('plane2 5  keep keep keep', 'plane2 5  keep keep #000000')
    assert bad != back_text
    try:
        T.parse_layer(bad, 'plane2', 'x.txt')
    except TargetError as e:
        assert 'must be keep' in str(e)
    else:
        raise AssertionError('no error for plane-2 palette 5 colour 3')


def test_registry():
    assert gfxbuild.TARGETS.get('title') == 'GFX_TITLE'
    assert gfxbuild.module_path('title')
    assert isinstance(T.FULL_BUILD, bool)        # True once gfx-verify enabled the target
    targets, notes = gfxbuild.select_targets(['title'])
    assert [t.name for t in targets] == ['title'] and not notes


def test_cli():
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert T.main(['fit']) == 0
    s = out.getvalue()
    assert 'tiles: logo' in s and 'window window1' in s, s
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            assert T.main(['draft', tmp]) == 0
            assert T.main(['preview', tmp]) == 0
        assert os.path.isfile(os.path.join(tmp, 'logo_front.txt'))
        assert os.path.isfile(os.path.join(tmp, 'logo_4x.png'))
        fake = os.path.join(tmp, 'x.ngc')
        with open(fake, 'wb') as f:
            f.write(bytes(0x200000))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert T.main(['warn-test', fake, os.path.join(tmp, 'y.ngc')]) == 1
        assert 'not the expected jump' in err.getvalue()


# ---------------------------------------------------------------------------
# With the original ROM

def _applied():
    from .apply import apply_targets
    with tempfile.TemporaryDirectory() as tmp:
        out, report = apply_targets(_base, _base, ['title'], work=tmp, gfx_dir=tmp, log=lambda s: None)
    return out, report


def test_rom_package():
    T.check_package(lambda a, n: _base[a - ROM_BASE:a - ROM_BASE + n])
    assert T.warn_jump(_base) == T.WARN_JUMP_TEXT, T.warn_jump(_base)


def test_rom_apply():
    out, report = _applied()
    assert any('title' in line for line in report), report
    b, o = _base, out
    pool = set(T.POOL)

    def changed(lo, hi):
        return [i for i in range(lo - ROM_BASE, hi - ROM_BASE) if b[i] != o[i]]

    # tiles: only pool tiles
    for t in range(512):
        a = T.TILES + 16 * t
        if changed(a, a + 16):
            assert t in pool, 'tile %03X changed outside the pool' % t
    # maps: only rows 7-12 of both planes, the window's rows 1-3 (columns 1-18)
    for base, w, h, rows in ((T.P1MAP, 20, 19, range(7, 13)), (T.P2MAP, 20, 19, range(7, 13)),
                             (T.WINMAP, 20, 5, (1, 2, 3))):
        for r in range(h):
            for c in range(w):
                a = base + 2 * (w * r + c)
                if changed(a, a + 2):
                    assert r in rows and (r, c) not in T.RESERVED and (base != T.WINMAP or 1 <= c <= 18), \
                        'map %06X row %d col %d changed' % (base, r, c)
    # palettes, background colour, sprite lists: unchanged except the flag count
    for lo, hi in ((T.P2PAL, T.P2PAL + 56), (T.P1PAL, T.P1PAL + 32), (T.SPRPAL, T.SPRPAL + 56),
                   (T.BG_COLOUR, T.BG_COLOUR + 2), (T.FLAG_LIST + 1, T.PRESS_LIST + 61)):
        assert not changed(lo, hi), 'changed bytes in %06X-%06X' % (lo, hi - 1)
    assert b[T.FLAG_LIST - ROM_BASE] == 50 and o[T.FLAG_LIST - ROM_BASE] == 48
    # nothing else
    ranges = [(lo - ROM_BASE, hi - ROM_BASE) for lo, hi in T.ranges()]
    for k in range(0, len(o), 4096):
        if o[k:k + 4096] != b[k:k + 4096]:
            for i in range(k, min(len(o), k + 4096)):
                if o[i] != b[i]:
                    assert any(lo <= i < hi for lo, hi in ranges), 'changed byte at %06X' % (i + ROM_BASE)


def test_rom_deterministic():
    a, _ = _applied()
    b, _ = _applied()
    assert a == b, 'two builds differ'


def test_rom_screen_and_dump():
    out, _ = _applied()
    pkg = T.Package(out)
    img = pkg.screen()
    assert len(img) == 152 and len(img[0]) == 160
    win = pkg.screen(window=True)
    assert win != img
    # a synthetic --vram dump of the title (tiles and maps as the script copies them)
    m = bytearray(0x10000)
    m[0xA000:0xC000] = out[T.TILES - ROM_BASE:T.TILES - ROM_BASE + 0x2000]
    for vbase, rbase in ((0x9000, T.P1MAP), (0x9800, T.P2MAP)):
        for r in range(19):
            for c in range(20):
                s = rbase - ROM_BASE + 2 * (20 * r + c)
                m[vbase + 2 * (32 * r + c):vbase + 2 * (32 * r + c) + 2] = out[s:s + 2]
    ok, lines = T.check_dump(bytes(m), out)
    assert ok, lines
    m[0xA000 + 16 * 0x30] ^= 0xFF
    ok, lines = T.check_dump(bytes(m), out)
    assert not ok and 'tiles differ' in ' '.join(lines), lines


TESTS = [test_text_file, test_text_errors, test_fonts, test_layers, test_treatment, test_outer_side, test_budget,
         test_window, test_writes, test_draft, test_draft_others, test_wording_check, test_registry, test_cli]
ROM_TESTS = [test_rom_package, test_rom_apply, test_rom_deterministic, test_rom_screen_and_dump]


def main(argv=None):
    global _base
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        with open(argv[0], 'rb') as fh:
            _base = fh.read()
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
    print('test_title: %d of %d passed%s' % (len(tests) - failed, len(tests), skipped))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
