"""Tests for the chapter cards target (tools/gfx/cards.py, patch/src/cards.asm,
translation/en/cards.txt).

Usage: python -m tools.gfx.test_cards [ROM]

Without the ROM: the text parses (40 cards, 'same' sharing for chapters
18-20) and the parser refuses malformed text; every line fits the original
lettering block (96 px with the outline), with at most one heading and one
title line per card, and the lettering lies inside that block (screen x
32-127, y 64-95); words are 4 px apart; the lettering sits on the original
rows with a 4-neighbour outline in colours 1 and 3, centred, with bold
heading digits; every record's map block is the original 12x4 block (tiles
from 0x44, blank cells 0); the records assemble with patch/src/cards.asm into
GFX_CARDS and parse back from the assembled bytes; the output is
deterministic; the command line works; no Japanese in these files.
With the original ROM (rom/baserom.ngc): the hook sites disassemble to the
instructions named in the comments of cards.asm, and the old loader uses the
addresses and lengths that card_load repeats; the original lettering uses the
rows and the block the English uses; applying the target to the original ROM
changes only the two hooks and GFX_CARDS, and the records read back from that
ROM.
"""
import contextlib
import hashlib
import io
import os
import re
import shutil
import sys
import tempfile
import time
import traceback

from ..asm.tlcs900asm import Assembler
from ..common.tiles import encode_tile_2bpp
from ..patch.layout import FREE_START
from ..recomp.rom import EXPECTED_SHA1, ROM_BASE, Rom
from ..recomp.tlcs900 import decode
from ..text.script import decode_script
from . import cards as C
from .build import SUBREGIONS
from .font import Font, MissingGlyphError, load_font
from .image import Bitmap
from .target import TargetError
from .textart import FitError, embolden, render

ROOT = C.ROOT
ASM = os.path.join(ROOT, C.ASM_ENTRY)
OWN_FILES = ('translation/en/cards.txt', 'tools/gfx/cards.py', 'tools/gfx/test_cards.py', 'patch/src/cards.asm',
             'docs/workstreams/gfx-chapter-cards.md')
GFX_LO, GFX_HI = SUBREGIONS[C.SUBREGION]
ELLIPSIS = chr(0x2026)


class Ctx:
    def __init__(self, folder, rom_path):
        self.folder = folder
        self.rom_path = rom_path
        self.font = load_font(C.FONT_FILE)
        self.tfont, self.hfont = C.card_fonts(self.font)
        self.cards = C.load_cards()
        self.gen = C.generate(self.cards, self.font)
        self._base = None

    @property
    def base(self):
        if self._base is None and self.rom_path:
            data = open(self.rom_path, 'rb').read()
            if hashlib.sha1(data).hexdigest() != EXPECTED_SHA1:
                raise AssertionError('%s is not the original ROM' % self.rom_path)
            self._base = data
        return self._base


def needs_rom(test):
    test.needs_rom = True
    return test


def card_text(body):
    """A full cards.txt with the given lines for story 1 and plain cards elsewhere."""
    out = ['[story 1]'] + body
    for s in C.SETS:
        for n in range(1, C.CHAPTERS + 1):
            if (s, n) != ('story', 1):
                out += ['[%s %d]' % (s, n), 'Title %d' % n]
    return '\n'.join(out) + '\n'


def lettering(bm):
    """[(x, y)] of the non-zero pixels of a bitmap."""
    return [(x, y) for y in range(bm.h) for x in range(bm.w) if bm.get(x, y)]


# ---------------------------------------------------------------------------
# Text

def test_text_parses(ctx):
    cards = ctx.cards
    assert len(cards) == 2 * C.CHAPTERS
    for s in C.SETS:
        for n in (19, 20):
            assert cards[(s, n)].same == 18, (s, n)
        for n in range(1, 19):
            assert cards[(s, n)].same is None and len(cards[(s, n)].titles) == 1, (s, n)
    for n in range(1, 13):
        assert cards[('story', n)].heading == 'Chapter %d' % n
    assert cards[('story', 13)].heading == 'Final Chapter'
    assert cards[('story', 13)].titles == ['White Night']
    for n in range(14, 21):
        assert cards[('story', n)].heading is None
    for n in range(1, 21):
        assert cards[('area', n)].heading is None
    assert cards[('area', 6)].titles == ['Litt Island Waters']
    assert cards[('story', 18)].titles == cards[('area', 18)].titles == ['Free Battle Area']


def test_parser_errors(ctx):
    good = C.parse_cards(card_text(['^Chapter 1', 'Quickening']))
    assert good[('story', 1)].heading == 'Chapter 1'
    bad = {
        'two headings': card_text(['^A', '^B', 'Title']),
        'heading after a title': card_text(['Title', '^A']),
        'two titles': card_text(['^A', 'B', 'C']),
        'two titles, no heading': card_text(['B', 'C']),
        'no title': card_text(['^A']),
        'empty heading': card_text(['^ ', 'Title']),
        'same with text': card_text(['same 2', 'Title']),
        'text after same': card_text(['Title', 'same 2']),
        'same itself': card_text(['same 1']),
        'same missing': card_text(['same 99']),
        'missing card': card_text(['Title']).replace('[area 7]\nTitle 7\n', ''),
        'duplicate card': card_text(['Title']) + '[area 7]\nAgain\n',
        'number 0': card_text(['Title']) + '[area 0]\nX\n',
        'bad header': card_text(['Title']).replace('[area 7]', '[zone 7]'),
        'text first': 'Stray\n' + card_text(['Title']),
    }
    for name, text in bad.items():
        try:
            C.parse_cards(text)
        except TargetError:
            continue
        raise AssertionError('accepted: %s' % name)
    chain = card_text(['Title']).replace('[story 3]\nTitle 3', '[story 3]\nsame 2').replace(
        '[story 2]\nTitle 2', '[story 2]\nsame 1')
    try:
        C.parse_cards(chain)
    except TargetError:
        pass
    else:
        raise AssertionError('accepted "same" naming a "same" card')
    # rendering errors: wider than the original block, unknown character
    for body, err in ((['W' * 30], FitError), (['The Northern Kingdom'], FitError),
                      (['Title ' + chr(0xA7)], MissingGlyphError)):
        cards = C.parse_cards(card_text(body))
        try:
            C.generate(cards, ctx.font)
        except err:
            continue
        raise AssertionError('no %s for %r' % (err.__name__, body))


# ---------------------------------------------------------------------------
# Rendering

def test_widths_and_lines(ctx):
    assert C.MAX_LINE == 8 * C.ORIG_BLOCK[2] == 96
    assert (C.MAX_HEADINGS, C.MAX_TITLES) == (1, 1)
    for (s, n), card in ctx.cards.items():
        if card.same is not None:
            continue
        lines = C.card_lines(card, ctx.tfont, ctx.hfont)
        assert sum(1 for b, _, _ in lines if b == 0) <= C.MAX_HEADINGS
        assert sum(1 for b, _, _ in lines if b > 0) == C.MAX_TITLES
        for band, text, f in lines:
            w = C.measure(f, text, C.STYLE)
            assert 0 < w <= C.MAX_LINE, (s, n, text, w)
    # every line of every distinct card is in the generated records, with its width
    lines = [(r.label, b, t) for r, b, t, _ in ctx.gen.widths()]
    want = [('card_%s_%02d' % key, b, t) for key, card in sorted(ctx.cards.items(), key=lambda kv: (
        C.SETS.index(kv[0][0]), kv[0][1])) if card.same is None for b, t, _ in C.card_lines(card, None, None)]
    assert lines == want, (lines[:3], want[:3])
    assert max(w for _, _, _, w in ctx.gen.widths()) <= C.MAX_LINE


def test_bounds(ctx):
    """The lettering stays inside the original block: 12 x 4 cells at column 4, row 8 (screen x
    32-127, y 64-95), one heading band (rows 8-9) and one title band (rows 10-11)."""
    col, row, w, h = C.ORIG_BLOCK
    assert (col, row, w, h) == (4, 8, 12, 4)
    assert C.BLOCK_RECT == (32, 64, 127, 95)
    assert (C.TOP_ROW, C.BANDS * C.BAND_H) == (row, 8 * h)
    for rec in ctx.gen.records:
        bm = rec.bitmap
        assert (bm.w, bm.h) == (C.SCREEN_W, 8 * h), rec.label      # canvas = screen rows 8-11
        px = lettering(bm)
        x0, y0, x1, y1 = C.BLOCK_RECT
        assert all(x0 <= x <= x1 and y0 <= 8 * C.TOP_ROW + y <= y1 for x, y in px), rec.label
        assert (rec.col, rec.row, rec.w, rec.h) == C.ORIG_BLOCK, rec.label
        assert rec.mapaddr == 0x9208, rec.label                     # the original gfxfe 0x6080, 0x9208
    # the encoder refuses lettering outside the block, and the renderer a line of 97 px
    for x in (C.BLOCK_RECT[0] - 1, C.BLOCK_RECT[2] + 1):
        bm = Bitmap(C.SCREEN_W, 8 * h)
        bm.set(64, 20, 1)
        bm.set(x, 20, 1)
        try:
            C.encode_card(bm, 'probe')
        except TargetError:
            continue
        raise AssertionError('lettering at x %d accepted' % x)
    k = 1
    while C.measure(ctx.tfont, 'W' * k, C.STYLE) <= C.MAX_LINE:
        k += 1
    widest = C.parse_cards(card_text(['^Chapter 20', 'W' * (k - 1)]))[('story', 1)]
    bm, _ = C.render_card(widest, ctx.tfont, ctx.hfont)
    x0, _, x1, _ = C.BLOCK_RECT
    assert all(x0 <= x <= x1 for x, _ in lettering(bm))
    card = C.parse_cards(card_text(['W' * k]))[('story', 1)]
    try:
        C.render_card(card, ctx.tfont, ctx.hfont)
    except FitError:
        pass
    else:
        raise AssertionError('a line wider than %d px was accepted' % C.MAX_LINE)


def _gaps(bm, part_value):
    """Lengths of the runs of columns with no pixel equal to part_value (None = any non-zero)
    between the first and last such column."""
    cols = [any((bm.get(x, y) == part_value) if part_value else bm.get(x, y) for y in range(bm.h))
            for x in range(bm.w)]
    xs = [x for x, c in enumerate(cols) if c]
    runs, run = [], 0
    for x in range(xs[0], xs[-1] + 1):
        if cols[x]:
            if run:
                runs.append(run)
            run = 0
        else:
            run += 1
    return runs


def test_word_gap(ctx):
    """Words are 4 px apart (SPACE advance 3), 2 px between the outlines, in both card fonts."""
    assert C.SPACE_ADVANCE == 3 and ctx.font.glyphs['SPACE'].advance == 4
    for f in (ctx.tfont, ctx.hfont):
        assert f.glyphs['SPACE'].advance == C.SPACE_ADVANCE
        assert f.glyphs['SPACE'].rows == ctx.font.glyphs['SPACE'].rows
        for name, g in ctx.font.glyphs.items():
            if name != 'SPACE' and not name.isdigit():
                assert f.glyphs[name] == g, name
    ink = render(ctx.tfont, 'I I', C.STYLE, part='ink')
    allpx = render(ctx.tfont, 'I I', C.STYLE)
    assert _gaps(ink, 1) == [4], _gaps(ink, 1)
    assert _gaps(allpx, None) == [2], _gaps(allpx, None)
    # 1 px less per word gap than with title16's own SPACE: a line with n spaces is n px narrower
    for rec in ctx.gen.records:
        for band, text, w in rec.widths:
            plain = C.measure(_plain_space(ctx.hfont if band == 0 else ctx.tfont, ctx.font), text, C.STYLE)
            assert plain - w == text.count(' '), (text, plain, w)


def _plain_space(card_font, font):
    """A card font with title16's own SPACE again (for the width comparison)."""
    glyphs = dict(card_font.glyphs)
    glyphs['SPACE'] = font.glyphs['SPACE']
    return Font(glyphs, font.height, 'plain space', None)


def _rings_ok(bm, y0, y1):
    """Every outline pixel touches ink (4 neighbours) and every 4-neighbour of ink is ink or outline."""
    w = bm.w
    for y in range(y0, y1):
        for x in range(w):
            v = bm.get(x, y)
            near = [bm.get(xx, yy) for xx, yy in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                    if 0 <= xx < w and y0 <= yy < y1]
            if v == 3 and 1 not in near:
                return 'outline pixel at (%d, %d) does not touch the ink' % (x, y)
            if v == 0 and 1 in near:
                return 'gap in the outline at (%d, %d)' % (x, y)
    return None


def test_layout_and_style(ctx):
    for rec in ctx.gen.records:
        bm = rec.bitmap
        assert (bm.w, bm.h) == (C.SCREEN_W, C.BAND_H * C.BANDS)
        assert bm.values() <= {0, 1, 3}, (rec.label, bm.values())
        bands = {b: (t, w) for b, t, w in rec.widths}
        for band in range(C.BANDS):
            y0, y1 = band * C.BAND_H, (band + 1) * C.BAND_H
            ink = [(x, y - y0) for y in range(y0, y1) for x in range(bm.w) if bm.get(x, y) == 1]
            if band not in bands:
                assert not ink and all(bm.get(x, y) == 0 for y in range(y0, y1) for x in range(bm.w)), \
                    (rec.label, band)
                continue
            text, width = bands[band]
            top = C.BAND_TOPS[band]
            ys = [y for _, y in ink]
            # every line has a capital or a digit, whose top is glyph row 0
            assert min(ys) == top, (rec.label, text, min(ys))
            assert max(ys) <= top + ctx.font.height - 1, (rec.label, text)
            allpx = [(x, y - y0) for y in range(y0, y1) for x in range(bm.w) if bm.get(x, y)]
            xs = [x for x, _ in allpx]
            assert max(xs) - min(xs) + 1 == width, (rec.label, text)
            assert min(xs) == (C.SCREEN_W - width) // 2, (rec.label, text, min(xs))
            problem = _rings_ok(bm, y0, y1)
            assert problem is None, (rec.label, text, problem)
    # heading rows as the original: glyph row 0 on band row 2 (ink 2-12), title row 4 (ink 4-14)
    assert C.BAND_TOPS == (2, 4)
    assert C.STYLE.outline8 is False and C.STYLE.ink == 1 and C.STYLE.outline == 3 and not C.STYLE.glow


def test_bold_digits(ctx):
    tf, hf = ctx.tfont, ctx.hfont
    for name, glyph in tf.glyphs.items():
        if name in '0123456789' and len(name) == 1:
            rows, adv = embolden(name, glyph.rows, glyph.advance)
            assert hf.glyphs[name] == (rows, adv), name
            assert hf.glyphs[name].width == glyph.width + 1
        else:
            assert hf.glyphs[name] == glyph, name
    # a heading with a digit differs from the plain rendering only in the number
    card = ctx.cards[('story', 1)]
    a, _ = C.render_card(card, tf, hf)
    b, _ = C.render_card(card, tf, tf)
    diff = [(x, y) for y in range(a.h) for x in range(a.w) if a.get(x, y) != b.get(x, y)]
    assert diff and all(y < C.BAND_H for _, y in diff)


def test_records(ctx):
    gen = ctx.gen
    assert len(gen.records) == 36, len(gen.records)
    for s in C.SETS:
        assert gen.table[(s, 19)] is gen.table[(s, 18)] is gen.table[(s, 20)]
        assert len({id(gen.table[(s, n)]) for n in range(1, 21)}) == 18
    for rec in gen.records:
        n = len(rec.tiles)
        assert 0 < n <= rec.w * rec.h < C.MAX_TILES, rec.label           # at most 48 of the 360 VRAM tiles
        assert len(set(rec.tiles)) == n, rec.label                       # identical tiles shared
        assert len(rec.entries) == rec.w * rec.h == 48
        seen = []
        for e in rec.entries:
            assert e & ~0x1FF == 0, (rec.label, hex(e))                  # palette 0, no flips
            if e:
                assert C.FIRST_TILE <= e <= C.LAST_TILE, (rec.label, hex(e))
                if e not in seen:
                    seen.append(e)
        assert seen == list(range(C.FIRST_TILE, C.FIRST_TILE + n)), rec.label   # numbered in first use
        # the entries rebuild the canvas (block columns 4-15 of the 160 x 32 canvas)
        for i, e in enumerate(rec.entries):
            r, c = i // rec.w, rec.col + i % rec.w
            cell = [rec.bitmap.row(8 * r + y)[8 * c:8 * c + 8] for y in range(8)]
            if e == 0:
                assert not any(v for row in cell for v in row)
            else:
                assert encode_tile_2bpp(cell) == rec.tiles[e - C.FIRST_TILE]
    assert gen.size + C.CODE_RESERVE <= GFX_HI - GFX_LO


def test_deterministic(ctx):
    again = C.generate(C.load_cards(), ctx.font)
    assert again.asm == ctx.gen.asm
    assert [r.tile_bytes() for r in again.records] == [r.tile_bytes() for r in ctx.gen.records]
    assert [r.bitmap.px for r in again.records] == [r.bitmap.px for r in ctx.gen.records]


# ---------------------------------------------------------------------------
# Assembly

def assemble(ctx, gen=None):
    """Assemble patch/src/cards.asm with the generated data, from a copy in the test folder
    (the include path of cards.asm is kept). Returns (chunks, symbols)."""
    gen = gen or ctx.gen
    work = os.path.join(ctx.folder, 'asm')
    src = os.path.join(work, 'patch', 'src')
    data = os.path.join(work, 'build', 'gfx', 'cards')
    for d in (src, data):
        os.makedirs(d, exist_ok=True)
    shutil.copy(ASM, os.path.join(src, 'cards.asm'))
    with open(os.path.join(data, 'data.asm'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(gen.asm)
    wrapper = os.path.join(work, 'wrap.asm')
    with open(wrapper, 'w', newline='\n') as f:
        f.write('%s = 0x%06X\n%s_END = 0x%06X\n        .include "patch/src/cards.asm"\n'
                % (C.SUBREGION, GFX_LO, C.SUBREGION, GFX_HI))
    asm = Assembler()
    asm.load(wrapper)
    chunks = asm.assemble()
    return chunks, asm.symbols


def test_assemble_and_parse_back(ctx):
    chunks, syms = assemble(ctx)
    hooks = [(org, data) for org, data in chunks if org < FREE_START]
    new = [(org, data) for org, data in chunks if org >= FREE_START]
    assert [(org, len(d)) for org, d in hooks] == list(C.HOOKS), [(hex(o), len(d)) for o, d in hooks]
    assert len(new) == 1 and new[0][0] == GFX_LO
    end = GFX_LO + len(new[0][1])
    assert end <= GFX_HI, hex(end)
    for name in ('card_find', 'card_load', 'card_draw', 'card_story', 'card_area', 'card_sets'):
        assert GFX_LO <= syms[name] < end, name
    assert syms['card_story'] == GFX_LO + C.TABLE_STORY and syms['card_area'] == GFX_LO + C.TABLE_AREA
    for name, value in syms.items():
        if isinstance(value, int) and GFX_LO <= value < GFX_HI and not name.startswith(C.SUBREGION):
            assert name.startswith('card_'), name                           # one namespace: prefixed labels
    (h1, d1), (h2, d2) = hooks
    load, draw = syms['card_load'], syms['card_draw']
    assert d1[:4] == bytes((0x1D, load & 0xFF, (load >> 8) & 0xFF, load >> 16)), d1.hex()   # call card_load
    assert d1[4] == 0x68 and h1 + 6 + d1[5] == 0x29ED02, d1.hex()                           # jr 0x29ED02
    assert d2 == bytes((0x2E, draw & 0xFF, (draw >> 8) & 0xFF, draw >> 16, 0xCE, 0x20)), d2.hex()
    # the records read back from the assembled bytes
    rom = bytearray(b'\xff' * 0x200000)
    for org, data in chunks:
        rom[org - ROM_BASE:org - ROM_BASE + len(data)] = data
    errors = C.check_rom(bytes(rom), ctx.gen)
    assert not errors, errors
    got = C.read_tables(bytes(rom))
    for s in C.SETS:
        assert got[(s, 19)][0] == got[(s, 18)][0] == got[(s, 20)][0]
    # card_sets: the record table, then the original sheet and layout table of each set
    off = syms['card_sets'] - ROM_BASE
    sets = [int.from_bytes(rom[off + 4 * i:off + 4 * i + 4], 'little') for i in range(6)]
    want = []
    for s in C.SETS:
        want += [syms['card_%s' % s]] + list(C.ORIG_SETS[s])
    assert sets == want, [hex(v) for v in sets]
    # the code fits the reserve kept after the data
    code = end - (GFX_LO + ctx.gen.size)
    assert 0 < code <= C.CODE_RESERVE, code


def test_cli(ctx):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert C.main(['fit']) == 0
        assert C.main(['preview', os.path.join(ctx.folder, 'preview')]) == 0
    assert 'widest line' in out.getvalue()
    for name in ('preview.png', 'preview_3x.png'):
        assert os.path.getsize(os.path.join(ctx.folder, 'preview', name)) > 0
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assert C.main(['nonsense']) == 2


def test_no_japanese(ctx):
    # kana, CJK punctuation and ideographs, full-width forms (code points, so this file stays ASCII)
    pat = re.compile('[%s-%s%s-%s%s-%s%s-%s]' % tuple(chr(c) for c in (
        0x3000, 0x30FF, 0x3400, 0x4DBF, 0x4E00, 0x9FFF, 0xFF00, 0xFFEF)))
    for rel in OWN_FILES:
        path = os.path.join(ROOT, *rel.split('/'))
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as f:
            for n, line in enumerate(f, 1):
                assert not pat.search(line), '%s:%d has Japanese text' % (rel, n)


# ---------------------------------------------------------------------------
# With the original ROM

_WAS = re.compile(r'^\s*\.org\s+(0x[0-9A-Fa-f]+)\s*;\s*was( \(script\))?:\s*(.+?)\s*$')


def _norm(text):
    return re.sub(r'\s+', '', text).lower()


def _script_text(ins):
    return ins.mnem + (' ' + ', '.join('0x%X' % a for a in ins.args) if ins.args else '')


@needs_rom
def test_hook_sites(ctx):
    rom = Rom(ctx.rom_path)
    documented = []
    with open(ASM, encoding='utf-8') as f:
        for line in f:
            m = _WAS.match(line)
            if m:
                documented.append((int(m.group(1), 16), bool(m.group(2)), [p.strip() for p in m.group(3).split(' / ')]))
    assert [a for a, _, _ in documented] == [a for a, _ in C.HOOKS], documented
    chunks, _ = assemble(ctx)
    sizes = dict((org, len(d)) for org, d in chunks if org < FREE_START)
    for addr, script, parts in documented:
        a = addr
        for part in parts:
            if script:
                ins = decode_script(rom, a)
                got, length = _script_text(ins), ins.length
            else:
                ins = decode(rom.read8, a)
                got, length = ins.text(), ins.length
            assert _norm(got) == _norm(part), '%06X: %r, not %r' % (a, got, part)
            a += length
        assert sizes[addr] <= a - addr, '%06X: the hook (%d bytes) is longer than the documented code' % (addr, sizes[addr])
    # where hook 1 jumps to, and what the skipped code ended with
    assert decode(rom.read8, 0x29ED02).text() == 'ld.l XIX, 0x60E2'
    assert decode(rom.read8, 0x29ECFE).text() == 'call 0x200B37'
    assert decode(rom.read8, 0x29ECB3).text() == 'push.l XIY'
    # the op after hook 2 sets the same counter as its filler
    assert _script_text(decode_script(rom, 0x29EDDA)) == 'cnt0 0x20'
    # what card_load repeats: the old code's sheets and layout tables (card_sets), its layout copy
    # (0x31 words to RAM 0x6080) and its sheet load (0xB40 words to VRAM 0xA440)
    (sheet_s, table_s), (sheet_a, table_a) = C.ORIG_SETS['story'], C.ORIG_SETS['area']
    old = {0x29ECC4: 'ld.l XIX, 0x%X' % sheet_s, 0x29ECC9: 'ld.l XIY, 0x%X' % table_s,
           0x29ECD0: 'ld.l XIX, 0x%X' % sheet_a, 0x29ECD5: 'ld.l XIY, 0x%X' % table_a,
           0x29ECED: 'ld.w BC, 0x%X' % C.ORIG_LAYOUT_WORDS, 0x29ECF0: 'ld.l XIX, 0x%X' % C.ORIG_LAYOUT_RAM,
           0x29ECF5: 'ldir.w', 0x29ECF8: 'ld.w IX, 0x%X' % C.VRAM_TILES,
           0x29ECFB: 'ld.w BC, 0x%X' % C.ORIG_COPY_WORDS}
    for a, text in old.items():
        assert decode(rom.read8, a).text() == text, '%06X: %r' % (a, decode(rom.read8, a).text())
    with open(ASM, encoding='utf-8') as f:
        src = f.read()
    for value in ('0x%X' % C.ORIG_LAYOUT_RAM, '0x%X' % C.ORIG_LAYOUT_WORDS, '0x%X' % C.ORIG_COPY_WORDS,
                  '0x%X' % C.VRAM_TILES):
        assert re.search(r'^\s+ld\.[wl]\s+\w+,\s*%s\b' % value, src, re.M | re.I), value


@needs_rom
def test_original_rows(ctx):
    """The original lettering: heading ink in rows 2-12 of band 0, title ink in rows 4-14 of band 1,
    inside the 12x4 block at column 4, row 8; blank map entries use the emblem's tile 0, which is blank."""
    base = ctx.base
    assert not any(base[0x29EF0A - ROM_BASE:0x29EF0A - ROM_BASE + 16])
    for s in C.SETS:
        for n in range(1, C.CHAPTERS + 1):
            w, h, img = C.decode_original(base, s, n)
            assert (w, h) == (8 * C.ORIG_BLOCK[2], 8 * C.ORIG_BLOCK[3])
            for band in range(2):
                ys = [y - 16 * band for y in range(16 * band, 16 * band + 16) if any(v in (1, 2) for v in img[y])]
                if ys:
                    assert (min(ys), max(ys)) == (C.BAND_TOPS[band], C.BAND_TOPS[band] + 10), (s, n, band, ys)
    # and the English: ink never above or below the original's rows
    for rec in ctx.gen.records:
        for band, _, _ in rec.widths:
            ys = [y - 16 * band for y in range(16 * band, 16 * band + 16)
                  if any(v == 1 for v in rec.bitmap.row(y))]
            assert C.BAND_TOPS[band] <= min(ys) and max(ys) <= C.BAND_TOPS[band] + 10, (rec.label, band)


@needs_rom
def test_apply_to_original(ctx):
    from .apply import apply_targets
    base = ctx.base
    with contextlib.redirect_stdout(io.StringIO()):
        out, report = apply_targets(base, base, ['cards'], work=os.path.join(ctx.folder, 'apply'))
    changed = [i + ROM_BASE for i in range(len(base)) if out[i] != base[i]]
    hooks = [(a, a + n) for a, n in C.HOOKS]
    for a in changed:
        assert any(lo <= a < hi for lo, hi in hooks) or GFX_LO <= a < GFX_HI, hex(a)
    for lo, hi in hooks:
        assert any(lo <= a < hi for a in changed)
    errors = C.check_rom(out, ctx.gen)
    assert not errors, errors
    # the old data stays: text palette, emblem, layouts and sheets unchanged
    assert out[0x29EE8E - ROM_BASE:0x2A2F0C - ROM_BASE] == base[0x29EE8E - ROM_BASE:0x2A2F0C - ROM_BASE]


TESTS = [test_text_parses, test_parser_errors, test_widths_and_lines, test_bounds, test_word_gap,
         test_layout_and_style, test_bold_digits, test_records, test_deterministic, test_assemble_and_parse_back,
         test_cli, test_no_japanese, test_hook_sites, test_original_rows, test_apply_to_original]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    rom = argv[0] if argv else None
    if rom and not os.path.isfile(rom):
        print('error: %s does not exist' % rom)
        return 2
    failed = skipped = 0
    with tempfile.TemporaryDirectory(prefix='test_cards_') as folder:
        ctx = Ctx(folder, rom)
        for test in TESTS:
            if getattr(test, 'needs_rom', False) and not rom:
                skipped += 1
                print('skip %s (needs the original ROM)' % test.__name__)
                continue
            t0 = time.time()
            try:
                test(ctx)
            except Exception:
                failed += 1
                print('FAIL %s' % test.__name__)
                traceback.print_exc()
            else:
                print('ok   %s (%.2f s)' % (test.__name__, time.time() - t0))
    print('%d tests, %d failed%s' % (len(TESTS) - skipped, failed, ', %d skipped (no ROM)' % skipped if skipped else ''))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
