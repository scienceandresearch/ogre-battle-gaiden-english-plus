"""Tests for the graphics build integration (tools/gfx/target.py, romio.py,
build.py, apply.py, vram.py, harness.py) and the save-block layout check.

Usage: python -m tools.gfx.test_build [ROM]

ROM  the original ROM (rom/baserom.ngc). With it, the apply-path tests run on
     the real ROM; without it on a synthetic 2 MB image (0xFF from 0x36746D,
     like the original). The test bytes are our own, never ROM data.

Covers: the sub-region table and the generated gfx.asm; RomPatch refusals
(outside the owner's ranges, overlaps, the save blocks, bytes already changed
by another writer; nothing written then); tools.patch.layout.check refusing a
changed byte in 0x3B0000-0x3EFFFF or outside every region; a dummy target
(defined here, not in the registry) with one in-place write, a hook and an
asm chunk in its sub-region, through the apply path; refusals: a chunk
outside its sub-region, new data without a sub-region, code before the first
.org, a symbol defined twice, a non-target chunk in the graphics region,
in-place ranges in free space, clashes with bytes the input ROM already
changed, an assembly without the generated gfx.asm (or with one that another
build rewrote in the meantime); no targets gives an identical ROM; the registry (missing module
skipped with a note, errors inside a module propagate, FULL_BUILD = False);
library errors reported with the target's name, other errors kept;
tools.gfx.vram (registers, sprites, composite, comparisons, the queue) and
tools.gfx.harness (poke, state RAM, diff, contact sheet) on synthetic data.
With NGP_HARNESS set and a ROM given, also a short harness run.

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

from ..asm.tlcs900asm import Assembler
from ..common import png
from ..patch import layout
from ..patch.layout import FREE_START, LayoutError, SAVE_END, SAVE_START
from ..recomp.rom import EXPECTED_SHA1, ROM_BASE
from . import apply as gfxapply
from . import build as gfxbuild
from . import harness as H
from . import vram as V
from .build import GFX_END, GFX_START, SUBREGIONS, ChunkError, Target
from .romio import PatchError, RomPatch
from .target import GfxError, Result, TargetError

ROM_SIZE = 0x200000
INPLACE = 0x218112                      # the dummy target's in-place range (any original-program address)
HOOK = 0x2A0000                         # the dummy target's hook
DATA = bytes(range(0x10, 0x18))         # its in-place bytes
SPARE = SUBREGIONS['GFX_SPARE'][0]

GOOD_ASM = '''; dummy target (test only)
        .org GFX_SPARE
dummy_blob:
        .db 0x44, 0x55, 0x4D, 0x4D, 0x59, 0x00
        .include "data.asm"
        .org 0x2A0000                   ; a hook (test only)
        .dl dummy_blob
'''
DATA_ASM = '''dummy_more:
        .dw 0x1234, dummy_more - dummy_blob
'''
# what GOOD_ASM places at GFX_SPARE and at the hook
GOOD_BLOB = bytes((0x44, 0x55, 0x4D, 0x4D, 0x59, 0x00, 0x34, 0x12, 0x06, 0x00))
GOOD_HOOK = SPARE.to_bytes(4, 'little')


def synthetic_rom():
    n = FREE_START - ROM_BASE
    pattern = bytes(((i * 7) ^ (i >> 3)) & 0xFF for i in range(4096))
    rom = bytearray((pattern * (n // len(pattern) + 1))[:n])
    rom += b'\xFF' * (ROM_SIZE - n)
    return bytes(rom)


def dummy(asm=GOOD_ASM, subregion='GFX_SPARE', writes=None, allow=None, files=None, name='dummy'):
    """A target defined here (not in the registry)."""
    def build(ctx):
        for fname, text in (files if files is not None else {'data.asm': DATA_ASM}).items():
            ctx.write_file(fname, text)
        path = ctx.write_file('dummy.asm', asm) if asm is not None else None
        return Result(writes=[(INPLACE, DATA)] if writes is None else writes,
                      allow=[(INPLACE, INPLACE + 0x80)] if allow is None else allow,
                      asm=path, stats={'test': 1})
    return Target(name, build, subregion)


def expect(exc, fn, *args, contains=None, **kw):
    try:
        fn(*args, **kw)
    except exc as e:
        if contains is not None and contains not in str(e):
            raise AssertionError('%s raised, but %r is not in: %s' % (exc.__name__, contains, e))
        return e
    raise AssertionError('%s not raised' % exc.__name__)


class Ctx:
    def __init__(self, folder, base, real):
        self.folder = folder
        self.base = base
        self.real = real
        self.n = 0

    def tmp(self, name):
        self.n += 1
        path = os.path.join(self.folder, '%02d_%s' % (self.n, name))
        os.makedirs(path, exist_ok=True)
        return path

    def apply(self, targets, rom_in=None, name='apply'):
        """The standalone path (tools.gfx.apply)."""
        folder = self.tmp(name)
        quiet = io.StringIO()
        with contextlib.redirect_stdout(quiet):
            return gfxapply.apply_targets(self.base, self.base if rom_in is None else rom_in, targets,
                                          work=os.path.join(folder, 'work'), gfx_dir=os.path.join(folder, 'gfx'))

    def full(self, targets, name='full'):
        """Phase 1 and the chunk check as in the full build: the include comes
        after other sections, like at the end of patch/main.asm."""
        folder = self.tmp(name)
        with contextlib.redirect_stdout(io.StringIO()):
            gfx = gfxbuild.prepare(gfxbuild.ROOT, self.base, bytearray(self.base), targets=targets, gfx_dir=folder)
        main = os.path.join(folder, 'main.asm')
        with open(main, 'w') as f:
            f.write('        .org 0x370000\nmain_code:\n        .db 1, 2\n        .include "gfx.asm"\n')
        asm = Assembler()
        asm.load(main)
        chunks = asm.assemble()
        return gfx.check_chunks(chunks, asm.lines)


# ---------------------------------------------------------------------------

def test_subregions(ctx):
    lo, hi = layout.region('gfx')
    assert (GFX_START, GFX_END) == (lo, hi) == (0x3A0000, 0x3B0000)
    assert SUBREGIONS == {'GFX_CARDS': (0x3A0000, 0x3A6000), 'GFX_INTRO': (0x3A6000, 0x3AA000),
                          'GFX_TITLE': (0x3AA000, 0x3AE000), 'GFX_SPARE': (0x3AE000, 0x3B0000)}
    pos = lo
    for a, b in SUBREGIONS.values():
        assert a == pos and b > a
        pos = b
    assert pos == hi
    for name, sub in gfxbuild.TARGETS.items():
        assert sub is None or sub in SUBREGIONS, name
    # the generated include: constants only, assembled alone it gives no chunk
    folder = ctx.tmp('gfxasm')
    gfx = gfxbuild.prepare(gfxbuild.ROOT, ctx.base, bytearray(ctx.base), targets=(), gfx_dir=folder)
    text = open(gfx.asm_path, encoding='utf-8').read()
    assert text == gfxbuild.gfx_asm_text([], folder) and '.include' not in text
    asm = Assembler()
    asm.load(gfx.asm_path)
    assert asm.assemble() == []
    assert asm.symbols['GFX_START'] == GFX_START and asm.symbols['GFX_END'] == GFX_END
    for name, (a, b) in SUBREGIONS.items():
        assert asm.symbols[name] == a and asm.symbols[name + '_END'] == b
    assert gfx.report()[0].startswith('graphics: no targets')
    assert gfx.check_chunks([], asm.lines) == [] and gfx.apply_inplace() == []
    # rewriting the same content leaves the file alone
    mtime = os.stat(gfx.asm_path).st_mtime_ns
    gfxbuild.prepare(gfxbuild.ROOT, ctx.base, bytearray(ctx.base), targets=(), gfx_dir=folder)
    assert os.stat(gfx.asm_path).st_mtime_ns == mtime


def test_rompatch_refusals(ctx):
    base = bytes(ctx.base)
    rom = bytearray(base)
    p = RomPatch(base, rom)
    expect(PatchError, p.allow, ROM_BASE - 16, ROM_BASE + 16, 'a', contains='outside the ROM')
    expect(PatchError, p.allow, ROM_BASE + ROM_SIZE - 8, ROM_BASE + ROM_SIZE + 8, 'a', contains='outside the ROM')
    expect(PatchError, p.allow, 0x218000, 0x218000, 'a', contains='bad range')
    expect(PatchError, p.allow, SAVE_START - 4, SAVE_START + 4, 'a', contains='save blocks')
    expect(PatchError, p.allow, SAVE_END - 1, SAVE_END + 4, 'a', contains='save blocks')
    p.allow(0x218000, 0x218100, 'a')
    p.allow(0x218100, 0x218200, 'a')                # adjacent: merged with the first
    p.allow(0x219000, 0x219100, 'b')
    expect(PatchError, p.allow, 0x2190F0, 0x219110, 'a', contains='overlaps')
    assert p.ranges['a'] == [(0x218000, 0x218200)]
    expect(PatchError, p.write, 0x219000, b'\1\2', 'a', contains='outside its ranges')    # b's range
    expect(PatchError, p.write, 0x2181FF, b'\1\2', 'a', contains='outside its ranges')    # past the end
    expect(PatchError, p.write, 0x218000, b'\1', 'c', contains='none declared')
    p.write(0x2180FE, b'\xAA' * 4, 'a')             # across the two allowed ranges
    p.write(0x218010, b'\xBB' * 16, 'a')
    p.write(0x219000, b'\xCC' * 8, 'b')
    p.write(0x218020, b'', 'a')                     # empty: ignored
    expect(PatchError, p.write, 0x218018, b'\1' * 4, 'a', contains='overlaps the write')     # same owner
    expect(PatchError, p.write, 0x218000, b'\1' * 0x20, 'a', contains='overlaps the write')  # covers one
    expect(PatchError, p.write, 0x218101, b'\1', 'a', contains='overlaps the write')
    assert len(p.writes) == 3
    # another writer changes a byte inside a queued range: refused, nothing written
    rom[0x219004 - ROM_BASE] ^= 0xFF
    e = expect(PatchError, p.commit, contains='another part of the patch changed')
    assert '219004' in str(e) and 'b:' in str(e)
    assert rom[0x218010 - ROM_BASE:0x218020 - ROM_BASE] == base[0x218010 - ROM_BASE:0x218020 - ROM_BASE]
    rom[0x219004 - ROM_BASE] ^= 0xFF
    lines = p.commit()
    assert rom[0x2180FE - ROM_BASE:0x218102 - ROM_BASE] == b'\xAA' * 4
    assert rom[0x218010 - ROM_BASE:0x218020 - ROM_BASE] == b'\xBB' * 16
    assert rom[0x219000 - ROM_BASE:0x219008 - ROM_BASE] == b'\xCC' * 8
    diff = [i for i in range(len(rom)) if rom[i] != base[i]]
    assert diff and min(diff) >= 0x218010 - ROM_BASE and max(diff) < 0x219008 - ROM_BASE
    assert len(lines) == 2 and lines[0].startswith('  a: 20 bytes in 2 writes') and p.log == lines
    expect(PatchError, p.write, 0x218050, b'\1', 'a', contains='committed')
    expect(PatchError, p.commit, contains='committed')
    expect(TypeError, RomPatch, base, bytes(base))
    expect(PatchError, RomPatch, base, bytearray(base[:-1]), contains='differs')


def test_layout_check(ctx):
    base = ctx.base
    usage = layout.check(base, bytearray(base))
    assert all(changed == 0 for _, _, _, _, changed in usage)
    for addr in (SAVE_START, 0x3B1234, 0x3C0000, 0x3E8000, SAVE_END - 1):
        rom = bytearray(base)
        rom[addr - ROM_BASE] ^= 0x5A
        expect(LayoutError, layout.check, base, rom, contains='save blocks')
    for addr in (FREE_START, 0x367F00):             # free, but in no region
        rom = bytearray(base)
        rom[addr - ROM_BASE] ^= 0x5A
        expect(LayoutError, layout.check, base, rom, contains='no patch region')
    rom = bytearray(base)
    for addr in (SPARE, SPARE + 9, 0x3F0000):
        rom[addr - ROM_BASE] = 0x00
    usage = {name: (used, changed) for name, _, _, used, changed in layout.check(base, rom)}
    assert usage['gfx'] == (SPARE + 10 - GFX_START, 2) and usage['tables'] == (1, 1)
    expect(LayoutError, layout.check_chunk, 0x3AFFF0, 0x3B0010, contains='save blocks')
    expect(LayoutError, layout.check_chunk, 0x3AFFF0, 0x3B0000 + 0x40000, contains='save blocks')
    layout.check_chunk(SPARE, SPARE + 16)


def test_dummy_target(ctx):
    out, report = ctx.apply([dummy()])
    expected = bytearray(ctx.base)
    expected[INPLACE - ROM_BASE:INPLACE - ROM_BASE + len(DATA)] = DATA
    expected[SPARE - ROM_BASE:SPARE - ROM_BASE + len(GOOD_BLOB)] = GOOD_BLOB
    expected[HOOK - ROM_BASE:HOOK - ROM_BASE + 4] = GOOD_HOOK
    assert out == bytes(expected), 'the apply path wrote something else'
    text = '\n'.join(report)
    assert 'graphics: 1 target (dummy)' in text, text
    assert '  dummy: 1 hook (4 bytes), new data 3AE000-3AE009 in GFX_SPARE (10 of 8,192 bytes)' in text, text
    assert '  hook 2A0000:' in text and '  dummy: 8 bytes in 1 write' in text, text
    assert 'graphics: sub-regions\n  GFX_SPARE 3AE000-3AFFFF: 10 of 8,192 bytes used (' in text, text
    assert text.endswith('in the graphics region)')
    # the same through the full-build interface: phase 1, assemble, check, chunks, phase 2
    folder = ctx.tmp('phases')
    rom = bytearray(ctx.base)
    gfx = gfxbuild.prepare(gfxbuild.ROOT, ctx.base, rom, targets=[dummy()], gfx_dir=folder)
    assert rom == bytearray(ctx.base), 'phase 1 must not write the ROM'
    gtext = open(gfx.asm_path, encoding='utf-8').read()
    assert '        .include "dummy/dummy.asm"' in gtext and '; end of target dummy' in gtext, gtext
    main = os.path.join(folder, 'main.asm')
    with open(main, 'w') as f:
        f.write('        .org 0x370000\n        .db 1, 2\n        .include "gfx.asm"\n        .org 0x370002\n'
                '        .db 3\n')
    asm = Assembler()
    asm.load(main)
    chunks = asm.assemble()
    lines = gfx.check_chunks(chunks, asm.lines)
    assert lines == ['  dummy: 1 hook (4 bytes), new data 3AE000-3AE009 in GFX_SPARE (10 of 8,192 bytes)'], lines
    assert gfx.chunks['dummy'] == {'hooks': [(HOOK, HOOK + 4)], 'data': [(SPARE, SPARE + 10)]}
    for org, data in chunks:
        rom[org - ROM_BASE:org - ROM_BASE + len(data)] = data
    lines = gfx.apply_inplace()
    assert lines[0] == 'graphics: in-place writes' and rom[INPLACE - ROM_BASE:INPLACE - ROM_BASE + 8] == DATA
    expect(GfxError, gfx.apply_inplace, contains='ran already')
    # a later writer (dialogue, tables...) overwrites the target's hook: phase 2 refuses
    rom = bytearray(ctx.base)
    gfx = gfxbuild.prepare(gfxbuild.ROOT, ctx.base, rom, targets=[dummy()], gfx_dir=folder)
    asm = Assembler()
    asm.load(main)
    chunks = asm.assemble()
    gfx.check_chunks(chunks, asm.lines)
    for org, data in chunks:
        rom[org - ROM_BASE:org - ROM_BASE + len(data)] = data
    rom[HOOK + 2 - ROM_BASE] ^= 0xFF
    expect(GfxError, gfx.apply_inplace, contains='chunk 2A0000-2A0003 was overwritten by a later writer')
    assert rom[INPLACE - ROM_BASE:INPLACE - ROM_BASE + 8] != DATA
    # determinism: a second run gives the same ROM
    out2, _ = ctx.apply([dummy()])
    assert out2 == out


def test_chunk_refusals(ctx):
    cases = [
        ('        .org GFX_CARDS\n        .db 1, 2, 3\n', 'GFX_SPARE', 'outside its sub-region GFX_SPARE'),
        ('        .org GFX_SPARE_END - 2\n        .db 1, 2, 3, 4\n', 'GFX_SPARE', 'outside its sub-region'),
        ('        .org GFX_SPARE\n        .db 1\n', None, 'no sub-region'),
        ('        .org 0x36FFFE\n        .db 1, 2, 3, 4\n', 'GFX_SPARE', 'outside its sub-region'),
        ('        .org 0x36746B\n        .db 1, 2, 3, 4\n', 'GFX_SPARE', 'straddles'),
        ('        .db 1\n        .org GFX_SPARE\n', 'GFX_SPARE', 'before the first .org'),
        ('early:\n        .org GFX_SPARE\n        .db 1\n', 'GFX_SPARE', 'label early before the first .org'),
        ('GFX_SPARE = 0x3AE000\n        .org GFX_SPARE\n        .db 1\n', 'GFX_SPARE', 'defined more than once'),
        ('        .org GFX_SPARE\nx:      .db 1\nx:      .db 2\n', 'GFX_SPARE', 'defined more than once'),
        ('        .org GFX_SPARE\nmain_code:\n        .db 1\n', 'GFX_SPARE', 'symbol main_code is defined more'),
    ]
    for asm, sub, msg in cases:
        expect(ChunkError, ctx.full, [dummy(asm, sub, files={})], contains=msg)
        # the standalone path (no main.asm) refuses them too; data before the first .org is
        # already refused by the assembler there, as nothing comes before the include
        if 'main_code' not in asm:
            expect(GfxError, ctx.apply, [dummy(asm, sub, files={})],
                   contains=None if msg == 'before the first .org' else msg)
    assert ctx.full([dummy()]) == ['  dummy: 1 hook (4 bytes), new data 3AE000-3AE009 in GFX_SPARE '
                                   '(10 of 8,192 bytes)']
    # two targets may not define the same symbol
    a = dummy('        .org GFX_SPARE\nshared: .db 1\n', files={}, name='one')
    b = dummy('        .org GFX_SPARE + 16\nshared: .db 2\n', files={}, name='two', writes=[], allow=[])
    expect(ChunkError, ctx.apply, [a, b], contains='symbol shared is defined more than once')
    # a chunk outside the sub-region is refused even when another target owns that space
    expect(ChunkError, ctx.apply, [dummy('        .org GFX_INTRO\n        .db 1\n', files={})], contains='outside')
    # in-place ranges and writes
    expect(TargetError, ctx.apply, [dummy(allow=[(0x3A0000, 0x3A0010)])], contains='not inside the target')
    expect(TargetError, ctx.apply, [dummy(allow=[(SAVE_START, SAVE_START + 16)])], contains='free area')
    expect(PatchError, ctx.apply, [dummy(writes=[(INPLACE + 0x7C, b'\1' * 8)])], contains='outside its ranges')
    one = dummy(asm=None, name='one')
    two = dummy(asm=None, name='two', allow=[(INPLACE + 0x40, INPLACE + 0x100)], writes=[])
    expect(PatchError, ctx.apply, [one, two], contains='overlaps')
    # a non-target chunk in the graphics region (main.asm or any other file)
    folder = ctx.tmp('nontarget')
    gfx = gfxbuild.prepare(gfxbuild.ROOT, ctx.base, bytearray(ctx.base), targets=(), gfx_dir=folder)
    main = os.path.join(folder, 'main.asm')
    with open(main, 'w') as f:
        f.write('        .include "gfx.asm"\n        .org 0x370000\n        .db 1\n        .org GFX_CARDS + 0x100\n'
                '        .db 1\n')
    asm = Assembler()
    asm.load(main)
    expect(ChunkError, gfx.check_chunks, asm.assemble(), asm.lines, contains='only the tools/gfx targets')


def test_assembled_as_generated(ctx):
    """The assembly must hold the gfx.asm that phase 1 wrote, once, and every
    target's asm entry; otherwise a target's chunks would go missing silently."""
    folder = ctx.tmp('assembled')

    def phase1(targets):
        with contextlib.redirect_stdout(io.StringIO()):
            return gfxbuild.prepare(gfxbuild.ROOT, ctx.base, bytearray(ctx.base), targets=targets, gfx_dir=folder)

    def assemble(text):
        main = os.path.join(folder, 'main.asm')
        with open(main, 'w') as f:
            f.write(text)
        asm = Assembler()
        asm.load(main)
        return asm.assemble(), asm.lines

    head = '        .org 0x370000\n        .db 1\n'
    inc = '        .include "gfx.asm"\n'
    one = dummy('        .org GFX_SPARE\none_blob:\n        .db 1\n', files={}, name='one', writes=[], allow=[])
    two = dummy('        .org 0x2A0000\n        .db 0\n', files={}, name='two', writes=[], allow=[])  # a hook only
    gfx = phase1([one])
    assert gfx.check_chunks(*assemble(head + inc)) == ['  one: 0 hooks (0 bytes), new data 3AE000-3AE000 in '
                                                       'GFX_SPARE (1 of 8,192 bytes)']
    expect(ChunkError, gfx.check_chunks, *assemble(head), contains='does not include')
    expect(ChunkError, gfx.check_chunks, *assemble(head + inc + inc), contains='not the file that graphics phase 1')
    phase1(())                                  # another build (--no-gfx) rewrites gfx.asm in the meantime
    expect(ChunkError, gfx.check_chunks, *assemble(head + inc), contains='not the file that graphics phase 1')
    phase1([two])                               # another build with another target (same number of includes)
    expect(ChunkError, gfx.check_chunks, *assemble(head + inc), contains='target one: its asm entry')
    # an empty asm entry contributes no line and is fine
    empty = dummy('', files={}, name='empty', writes=[], allow=[])
    gfx = phase1([empty])
    assert gfx.check_chunks(*assemble(head + inc)) == ['  empty: 0 hooks (0 bytes)']


def test_clashes_with_input(ctx):
    # the in-place range was changed already (e.g. the target applied twice)
    rom_in = bytearray(ctx.base)
    rom_in[INPLACE + 3 - ROM_BASE] ^= 0xFF
    expect(PatchError, ctx.apply, [dummy()], bytes(rom_in), contains='another part of the patch changed')
    out, _ = ctx.apply([dummy()])
    expect(GfxError, ctx.apply, [dummy()], out, contains='changed already')     # applied twice
    expect(PatchError, ctx.apply, [dummy(asm=None)], out, contains='another part of the patch changed')
    # a hook on a byte that the input (or an earlier writer of the build) already changed
    rom_in = bytearray(ctx.base)
    rom_in[HOOK + 1 - ROM_BASE] ^= 0xFF
    expect(ChunkError, ctx.apply, [dummy()], bytes(rom_in), contains='hook 2A0000-2A0003 is on bytes that were '
                                                                     'changed already')
    expect(GfxError, gfxapply.place_chunks, ctx.base, bytes(rom_in), bytearray(rom_in),
           [(HOOK, b'\0\0\0\0')], contains='already differs')
    expect(GfxError, gfxapply.place_chunks, ctx.base, ctx.base, bytearray(ctx.base),
           [(HOOK, b'\0\0\0\0'), (HOOK + 2, b'\0')], contains='overlaps')
    # new data on bytes that are not free in the input
    rom_in = bytearray(ctx.base)
    rom_in[SPARE + 2 - ROM_BASE] = 0x00
    expect(GfxError, ctx.apply, [dummy()], bytes(rom_in), contains='not on free')


def test_no_targets_identical(ctx):
    # an input like the old snapshot: patch bytes in a region and in the save blocks
    rom_in = bytearray(ctx.base)
    for addr in (0x368000, 0x3C0000, 0x3E0010, 0x200100):
        rom_in[addr - ROM_BASE] ^= 0x33
    rom_in = bytes(rom_in)
    out, report = ctx.apply((), rom_in)
    assert out == rom_in and report[0] == 'graphics: no targets' and report[-1].startswith('changed: 0 bytes')
    with _registry({'nosuchmodule': None}):
        out, report = ctx.apply(None, rom_in)
    assert out == rom_in and report[0] == 'graphics: no targets (no module yet: nosuchmodule)', report


@contextlib.contextmanager
def _registry(targets, folder=None, package=None):
    saved = gfxbuild.TARGETS, gfxbuild.HERE, gfxbuild.PACKAGE
    gfxbuild.TARGETS = targets
    if folder:
        gfxbuild.HERE, gfxbuild.PACKAGE = folder, package
    try:
        yield
    finally:
        gfxbuild.TARGETS, gfxbuild.HERE, gfxbuild.PACKAGE = saved


def test_registry(ctx):
    folder = ctx.tmp('pkg')
    package = 'gfxtestpkg_%d' % os.getpid()
    pkg = os.path.join(folder, package)
    os.makedirs(pkg)
    sources = {
        '__init__.py': '',
        'good.py': 'from tools.gfx.target import Result\n\ndef build(ctx):\n    return Result(stats={"ok": 1})\n',
        'off.py': 'from tools.gfx.target import Result\nFULL_BUILD = False\n\ndef build(ctx):\n    return Result()\n',
        'broken.py': 'raise RuntimeError("broken at import")\n',
        'nobuild.py': 'X = 1\n',
    }
    for name, text in sources.items():
        with open(os.path.join(pkg, name), 'w') as f:
            f.write(text)
    sys.path.insert(0, folder)
    try:
        with _registry({'good': None, 'missing': None, 'off': 'GFX_SPARE', 'broken': None, 'nobuild': None},
                       pkg, package):
            ts, notes = gfxbuild.select_targets(['good', 'missing', 'off'])
            assert [t.name for t in ts] == ['good', 'off'] and notes == [('missing', 'no module yet')]
            assert ts[1].subregion == 'GFX_SPARE' and ts[1].region == SUBREGIONS['GFX_SPARE']
            expect(RuntimeError, gfxbuild.select_targets, ['broken'], contains='broken at import')
            expect(TargetError, gfxbuild.select_targets, ['nobuild'], contains='no build(ctx)')
            expect(GfxError, gfxbuild.select_targets, ['unknown'], contains='unknown target')
            expect(GfxError, gfxbuild.select_targets, ['good', 'good'], contains='twice')
            expect(RuntimeError, gfxbuild.select_targets, None)        # the default selection imports broken too
        with _registry({'good': None, 'missing': None, 'off': 'GFX_SPARE'}, pkg, package):
            ts, notes = gfxbuild.select_targets(None)
            assert [t.name for t in ts] == ['good'], ts
            assert notes == [('missing', 'no module yet'), ('off', 'left out (FULL_BUILD = False)')], notes
            out, report = ctx.apply(None)
            assert out == ctx.base and report[0] == ('graphics: 1 target (good); no module yet: missing; '
                                                     'left out (FULL_BUILD = False): off'), report
            assert report[1] == '  good: 0 in-place writes (0 bytes), ok 1', report
    finally:
        sys.path.remove(folder)
        for name in [m for m in sys.modules if m == package or m.startswith(package + '.')]:
            del sys.modules[name]


def test_errors_named(ctx):
    FitError = type('FitError', (ValueError,), {'__module__': 'tools.gfx.textart'})

    def fit(c):
        raise FitError("'Organize screen' is 66 px wide; the limit is 64")

    e = expect(TargetError, ctx.apply, [Target('fitting', fit)], contains='target fitting: FitError:')
    assert isinstance(e.__cause__, FitError)

    def bug(c):
        return {}['x']

    expect(KeyError, ctx.apply, [Target('buggy', bug)])

    def own(c):
        raise TargetError('labels.txt:3: label 2D does not exist')

    expect(TargetError, ctx.apply, [Target('own', own)], contains='target own: labels.txt:3')
    bad_stats = Result()
    bad_stats.stats = [1]
    for result, msg in ((None, 'not a tools.gfx.target.Result'),
                        (Result(writes=[(INPLACE, 'text')]), 'not (address, bytes)'),
                        (Result(writes=[INPLACE]), 'not (address, bytes)'),
                        (Result(allow=[(INPLACE, INPLACE)]), 'bad range'),
                        (Result(asm='build/gfx/no/such/file.asm'), 'does not exist'),
                        (bad_stats, 'stats')):
        expect(TargetError, ctx.apply, [Target('bad', lambda c, r=result: r)], contains=msg)
    expect(GfxError, Target, 'x', fit, 'GFX_NOWHERE')


def test_context(ctx):
    seen = {}

    def build(c):
        seen['ctx'] = c
        assert c.read(INPLACE, 4) == ctx.base[INPLACE - ROM_BASE:INPLACE - ROM_BASE + 4]
        expect(TargetError, c.read, ROM_BASE + ROM_SIZE - 2, 4)
        assert c.translation('labels.txt').endswith(os.path.join('translation', 'en', 'labels.txt'))
        p = c.write_file('a.txt', 'line\n')
        assert open(p, 'rb').read() == b'line\n'
        c.log('hello')
        return Result()

    out = io.StringIO()
    folder = ctx.tmp('context')
    with contextlib.redirect_stdout(out):
        gfxapply.apply_targets(ctx.base, ctx.base, [Target('ctx', build, 'GFX_CARDS')],
                               work=os.path.join(folder, 'work'), gfx_dir=os.path.join(folder, 'gfx'))
    c = seen['ctx']
    assert c.name == 'ctx' and c.subregion == 'GFX_CARDS' and c.region == SUBREGIONS['GFX_CARDS']
    assert c.work == os.path.join(folder, 'gfx', 'ctx') and os.path.isdir(c.work)
    assert isinstance(c.rom, bytes) and c.rom == ctx.base
    assert '  ctx: hello' in out.getvalue()


def _dump():
    m = bytearray(V.SIZE)
    m[0x8004], m[0x8005] = 160, 152                          # window: the whole screen
    m[0x8118] = 0x80                                         # background colour 0
    m[0x83E0:0x83E2] = (0x0F0).to_bytes(2, 'little')         # background: green
    a = 0x8200 + 2 * (0x40 + 2 * 4 + 1)                      # plane 1, palette 2, colour 1: red
    m[a:a + 2] = (0x00F).to_bytes(2, 'little')
    a = 0x8200 + 2 * (1 * 4 + 1)                             # sprite palette 1, colour 1: blue
    m[a:a + 2] = (0xF00).to_bytes(2, 'little')
    m[0xA000 + 16 * 5:0xA000 + 16 * 5 + 2] = b'\x55\x55'     # tile 5: top row colour 1
    m[0x9000:0x9002] = (5 | 2 << 9).to_bytes(2, 'little')    # plane 1 (0, 0): tile 5, palette 2
    m[0x8800:0x8804] = bytes((5, 0x18, 20, 30))              # sprite 0: tile 5, priority 3
    m[0x8804:0x8808] = bytes((5, 0x18 | 0x06, 8, 0))         # sprite 1: chained, 8 px right of sprite 0
    m[0x8C00], m[0x8C01] = 1, 1
    m[V.QUEUE_COUNT] = 2
    m[V.QUEUE:V.QUEUE + 8] = (64).to_bytes(2, 'little') + (0xA050).to_bytes(2, 'little') + \
        (0x218112 + 3 * 128).to_bytes(4, 'little')
    m[V.QUEUE + 8:V.QUEUE + 16] = (8).to_bytes(2, 'little') + (0xB9D0).to_bytes(2, 'little') + \
        (0x20AE54).to_bytes(4, 'little')
    return m


def test_vram(ctx):
    mem = V.Vram(bytes(_dump()))
    red, blue, green = (255, 0, 0), (0, 0, 255), (0, 255, 0)
    sp = mem.sprites()
    assert (sp[0].x, sp[0].y, sp[0].prio, sp[0].tile, sp[0].pal) == (20, 30, 3, 5, 1)
    assert (sp[1].x, sp[1].y) == (28, 30)
    screen = mem.screen()
    assert screen[0][0:8] == [red] * 8 and screen[0][8] == green and screen[1][0] == green
    assert screen[30][20:36] == [blue] * 16 and screen[31][20] == green
    p1 = mem.plane_image(1)
    assert p1[0][0] == red and p1[0][8] is None and p1[1][0] is None
    spr = mem.sprite_image()
    assert spr[30][27] == blue and spr[29][27] is None
    w, h, rows = mem.tile_sheet()
    assert (w, h) == (32 * 9 + 1, 16 * 9 + 1)
    assert mem.queue() == [(64, 0xA050, 0x218112 + 384), (8, 0xB9D0, 0x20AE54)]
    rom = bytearray(ROM_SIZE)
    rom[0x218112 - ROM_BASE + 384:0x218112 - ROM_BASE + 386] = b'\x55\x55'
    assert V.compare_bytes(mem, rom, 0xA050, 0x218112 + 384, 16) == []
    assert V.compare_bytes(mem, rom, 0xA040, 0x218112 + 384, 32) == [0, 1, 16, 17]
    rom[0x300000 - ROM_BASE:0x300002 - ROM_BASE] = (5 | 2 << 9).to_bytes(2, 'little')
    assert V.compare_map(mem, rom, 0x9000, 0x300000, 20, 19) == []
    assert V.compare_map(mem, rom, 0x9002, 0x300000, 2, 1) == [(0, 0, 0, 0x405)]
    blocks = 0x310000
    tile = mem.m[0xA050:0xA060]
    rom[blocks - ROM_BASE + 16:blocks - ROM_BASE + 32] = tile
    rom[blocks - ROM_BASE + 32:blocks - ROM_BASE + 48] = tile
    rom[blocks - ROM_BASE:blocks - ROM_BASE + 16] = b'\x01' * 16
    assert V.find_blocks(mem, rom, 0xA050, 16, blocks, 4) == [1, 2]
    assert V.find_blocks(mem, rom, 0xA060, 16, blocks, 1) is None             # VRAM all zero, no zero block
    assert V.find_blocks(mem, rom, 0xA060, 16, blocks, 4) == [3]               # block 3 is zero
    assert V.find_blocks(mem, rom, 0xA050, 16, blocks + 1, 1) == []
    folder = ctx.tmp('vram')
    path = os.path.join(folder, 'mem_00010.bin')
    with open(path, 'wb') as f:
        f.write(mem.m)
    rom[0x20AE54 - ROM_BASE] = 1                # the second queue entry's source differs from VRAM
    rom_path = os.path.join(folder, 'rom.bin')
    with open(rom_path, 'wb') as f:
        f.write(rom)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        paths = V.render(V.Vram.load(path), os.path.join(folder, 'r'), maps=True, sprites=True, scale=1)
        assert V.main(['bytes', path, rom_path, 'A050', '218292', '10']) == 0
        assert V.main(['bytes', path, rom_path, 'A040', '218292', '20']) == 1
        assert V.main(['map', path, rom_path, '9002', '300000', '2', '1']) == 1
        V.main(['queue', folder, '--rom', rom_path, '--index', '218112', '80'])
        V.main(['queue', path, '--dest', 'B000'])
        V.main(['find', folder, rom_path, 'A050,A060,A070', '10', '310000', '3'])
    text = out.getvalue()
    assert len(paths) == 5 and all(os.path.isfile(p) for p in paths)
    w, h, rows, _ = png.read(paths[3])
    assert (w, h) == (160, 152) and rows[0][0][:3] == red
    assert 'tile 005 x= 28 y= 30 prio 3 pal 1' in text, text
    assert '0 of 16 bytes differ' in text and '4 of 32 bytes differ' in text, text
    assert 'first at row 0 col 0: VRAM 0000, ROM 0405' in text, text
    assert 'mem_00010.bin: 218292->A050 x64 #03 ok, 20AE54->B9D0 x8 differs' in text, text
    assert 'mem_00010.bin: no entry for B000' in text, text
    assert 'mem_00010.bin: 1/2  -  -' in text, text


def test_harness_tools(ctx):
    folder = ctx.tmp('harness')
    st = os.path.join(folder, 'a.state')
    raw = bytearray(H.STATE_MAGIC + bytes(H.STATE_SIZE - 8))
    raw[H.STATE_RAM + 0x5490] = 0x01
    with open(st, 'wb') as f:
        f.write(raw)
    out = os.path.join(folder, 'b.state')
    H.poke(st, out, H.parse_pokes(['5490=04', '546E=20000000']))
    ram = H.state_ram(out)
    assert len(ram) == 0x10000 and ram[0x5490] == 4 and ram[0x546E:0x5472] == b'\x20\0\0\0'
    data = open(out, 'rb').read()
    assert len(data) == H.STATE_SIZE and data[:H.STATE_RAM] == bytes(raw[:H.STATE_RAM])
    assert data[H.STATE_RAM + 0x10000:] == bytes(raw[H.STATE_RAM + 0x10000:])
    with open(st, 'wb') as f:
        f.write(b'NGPSTAT2' + bytes(H.STATE_SIZE - 8))
    expect(H.HarnessError, H.poke, st, out, {0x5490: b'\1'}, contains='magic')
    with open(st, 'wb') as f:
        f.write(H.STATE_MAGIC + bytes(H.STATE_SIZE - 9))         # one byte short
    expect(H.HarnessError, H.state_ram, st, contains='format changed')
    with open(st, 'wb') as f:                                   # with flash blocks: longer, accepted
        f.write(bytes(raw) + bytes(65536))
    assert len(H.state_ram(st)) == 0x10000
    expect(H.HarnessError, H.parse_pokes, ['5490'])
    expect(H.HarnessError, H.parse_pokes, ['5490=4'])
    with open(st, 'wb') as f:
        f.write(raw)
    expect(H.HarnessError, H.poke, st, out, {0xFFFF: b'\1\2'}, contains='outside')
    # screenshots at 2x (like the harness) and 1x
    grey = (90, 90, 90)
    img = [[grey] * 160 for _ in range(152)]
    a = os.path.join(folder, 'frame_00010.png')
    png.write_rgb(a, 160, 152, img, 2)
    img[60][10] = (255, 255, 255)            # inside the mask below
    img[5][5] = (0, 0, 0)                    # outside
    img[140][150] = (0, 0, 0)
    b = os.path.join(folder, 'frame_00020.png')
    png.write_rgb(b, 160, 152, img, 2)
    c = os.path.join(folder, 'one.png')
    png.write_rgb(c, 160, 152, img, 1)
    assert H.diff_png(a, b) == (3, (5, 5, 150, 140))
    assert H.diff_png(a, b, [(0, 56, 159, 103)]) == (2, (5, 5, 150, 140))
    assert H.diff_png(a, b, [(0, 56, 159, 103), (0, 0, 9, 9), (150, 140, 150, 140)]) == (0, None)
    assert H.diff_png(b, c) == (0, None)
    with contextlib.redirect_stdout(io.StringIO()):
        assert H.main(['diff', a, b, '0', '0', '159', '151']) == 0
        assert H.main(['diff', a, b]) == 1
    path, frames = H.contact_sheet(folder, cols=8)
    w, h, rows, _ = png.read(path)
    assert frames == [10, 20] and (w, h) == (2 * 162, 161)
    assert rows[1][1][:3] == grey and rows[155][2][:3] == (255, 255, 255)      # top of the 1 of "10"
    assert rows[155][1][:3] != (255, 255, 255)
    saved = os.environ.get('NGP_HARNESS')
    os.environ['NGP_HARNESS'] = os.path.join(folder, 'missing.exe')
    try:
        expect(H.HarnessError, H.find_exe, contains='not found')
        assert H.find_exe(sys.executable) == sys.executable
    finally:
        if saved is None:
            del os.environ['NGP_HARNESS']
        else:
            os.environ['NGP_HARNESS'] = saved


def test_harness_run(ctx):
    """A short run with the harness named by NGP_HARNESS (opt-in) on the real ROM."""
    if not os.environ.get('NGP_HARNESS') or not ctx.real:
        print('     (skipped: set NGP_HARNESS and give the ROM to run the harness)')
        return
    folder = ctx.tmp('run')
    rom = os.path.join(folder, 'rom.ngc')
    with open(rom, 'wb') as f:
        f.write(ctx.base)
    r = H.run(rom, out=os.path.join(folder, 'out'), frames=40, shots=[39], vram=[39])
    assert 'ran 40 frames' in r.stderr, r.stderr
    mem = V.Vram.load(r.path('mem', 39))
    shot = os.path.join(folder, 'screen.png')
    V.save_rgb(shot, mem.screen(), 2)
    assert H.diff_png(shot, r.path('frame', 39)) == (0, None)


TESTS = [test_subregions, test_rompatch_refusals, test_layout_check, test_dummy_target, test_chunk_refusals,
         test_assembled_as_generated, test_clashes_with_input, test_no_targets_identical, test_registry,
         test_errors_named, test_context, test_vram, test_harness_tools, test_harness_run]


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
    with tempfile.TemporaryDirectory(prefix='test_build_') as folder:
        ctx = Ctx(folder, base, real)
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
