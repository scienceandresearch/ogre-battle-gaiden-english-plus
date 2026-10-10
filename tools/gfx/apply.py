"""Apply graphics targets to a ROM without the full patch build.

    python -m tools.gfx.apply IN.ngc OUT.ngc [--target NAME ...] [--base rom/baserom.ngc] [--work DIR]

IN is usually a copy of the stable English snapshot ROM; it is never
modified. Without --target, every registered target whose module exists runs
(as in the full build; a module with FULL_BUILD = False is left out).
--target NAME (repeatable) runs only the named targets.

The checks are those of the full build (tools/patch/build.py):
1. graphics phase 1 (tools/gfx/build.py prepare): each target's build(ctx)
   runs with the work folders of the full build (build/gfx/<name>/, so a
   hand-written asm entry finds its generated data there). The wrapper (the
   region constants and the selected targets' includes) goes to --work
   (default build/gfx/apply/) as apply-<names>.asm, with its symbols in
   apply-<names>.sym.
2. The wrapper is assembled alone, so target asm must be self-contained.
   Chunks of new data must lie in their target's sub-region and land on 0xFF
   bytes of IN; hooks must land on bytes that IN still has from the original
   (--base); chunks must not overlap.
3. Graphics phase 2: the in-place writes, refused where IN differs from the
   original (a target applied twice, or a clash with the English patch).
4. Every byte that differs between IN and OUT is below 0x36746D or in the
   graphics region (tools.patch.layout.check on IN -> OUT).
With no target, OUT is a copy of IN.
"""
import argparse
import hashlib
import os
import sys

from ..asm.tlcs900asm import Assembler, AsmError
from ..patch import layout
from ..patch.layout import FREE_START, LayoutError
from ..recomp.rom import EXPECTED_SHA1, ROM_BASE
from . import build as gfxbuild
from .target import GfxError

ROOT = gfxbuild.ROOT
DEFAULT_BASE = os.path.join(ROOT, 'rom', 'baserom.ngc')
DEFAULT_WORK = os.path.join(ROOT, 'build', 'gfx', 'apply')


def _hex(data, limit=16):
    s = data[:limit].hex(' ')
    return s + (' ... (%d bytes)' % len(data) if len(data) > limit else '')


def count_diff(a, b, lo, hi, step=4096):
    """Number of offsets in [lo, hi) where a and b differ."""
    n = 0
    for x in range(lo, hi, step):
        y = min(hi, x + step)
        if a[x:y] != b[x:y]:
            n += sum(1 for i in range(x, y) if a[i] != b[i])
    return n


def place_chunks(base, rom_in, rom, chunks):
    """Write assembled chunks into rom (a copy of rom_in). New data must be on
    0xFF bytes of rom_in (and outside the save blocks); hooks on bytes that
    rom_in has unchanged from base. Returns [(org, old, new)] for the hooks."""
    used, hooks = [], []
    for org, data in chunks:
        if not data:
            continue
        end = org + len(data)
        if org < ROM_BASE or end > ROM_BASE + len(rom):
            raise GfxError('chunk %06X-%06X is outside the ROM' % (org, end - 1))
        for a, b in used:
            if org < b and a < end:
                raise GfxError('chunk %06X-%06X overlaps chunk %06X-%06X' % (org, end - 1, a, b - 1))
        used.append((org, end))
        off = org - ROM_BASE
        if org >= FREE_START:
            try:
                layout.check_chunk(org, end)
            except LayoutError as e:
                raise GfxError(str(e))
            if any(x != 0xFF for x in rom_in[off:off + len(data)]):
                raise GfxError('chunk %06X-%06X is not on free (0xFF) bytes of the input ROM' % (org, end - 1))
        else:
            if rom_in[off:off + len(data)] != base[off:off + len(data)]:
                raise GfxError('hook %06X-%06X: the input ROM already differs from the original there'
                               % (org, end - 1))
            hooks.append((org, bytes(base[off:off + len(data)]), data))
        rom[off:off + len(data)] = data
    return hooks


def apply_targets(base, rom_in, targets=None, work=None, gfx_dir=None, log=print):
    """Run the selected targets (see tools.gfx.build.select_targets) on a copy
    of rom_in. Returns (out bytes, report lines). Raises GfxError."""
    if len(base) != len(rom_in):
        raise GfxError('the input ROM has %d bytes, the original %d' % (len(rom_in), len(base)))
    work = work or DEFAULT_WORK
    selected, notes = gfxbuild.select_targets(targets)
    names = [t.name for t in selected]
    wrapper = os.path.join(work, 'apply-%s.asm' % ('-'.join(names) or 'none'))
    rom = bytearray(rom_in)
    gfx = gfxbuild.prepare(ROOT, base, rom, targets=selected, gfx_dir=gfx_dir, asm_path=wrapper, log=log,
                           notes=notes)
    report = gfx.report()

    asm = Assembler()
    asm.load(gfx.asm_path)
    try:
        chunks = asm.assemble()
    except AsmError as e:
        raise GfxError('assembly: %s' % e)
    report += gfx.check_chunks(chunks, asm.lines)
    hooks = place_chunks(base, rom_in, rom, chunks)
    for org, old, new in hooks:
        report.append('  hook %06X: %s -> %s' % (org, _hex(old), _hex(new)))
    with open(os.path.splitext(gfx.asm_path)[0] + '.sym', 'w', newline='\n') as f:
        for k, v in sorted(asm.symbols.items(), key=lambda kv: (kv[1], kv[0])):
            if isinstance(v, int) and v >= ROM_BASE:
                f.write('%06X %s\n' % (v, k))

    report += gfx.apply_inplace()

    try:
        usage = layout.check(rom_in, rom)
    except LayoutError as e:
        raise GfxError('layout check (input -> output): %s' % e)
    for name, s, e, used, changed in usage:
        if name != 'gfx' and changed:
            raise GfxError('%d bytes changed in region %s (%06X-%06X); a graphics target may only change the '
                           'original program and the graphics region' % (changed, name, s, e - 1))
    below = count_diff(rom_in, rom, 0, FREE_START - ROM_BASE)
    in_gfx = dict((n, c) for n, _, _, _, c in usage).get('gfx', 0)
    report.append('changed: %s bytes (%s below %06X, %s in the graphics region)'
                  % (format(below + in_gfx, ','), format(below, ','), FREE_START, format(in_gfx, ',')))
    return bytes(rom), report


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.gfx.apply',
                                 description='Apply graphics targets to a copy of a ROM (test path).')
    ap.add_argument('inp', metavar='IN.ngc', help='input ROM (usually the English snapshot); never modified')
    ap.add_argument('out', metavar='OUT.ngc', help='output ROM')
    ap.add_argument('--target', action='append', metavar='NAME',
                    help='run this target (repeatable; default: every registered target present)')
    ap.add_argument('--base', default=DEFAULT_BASE, help='the original ROM (default rom/baserom.ngc)')
    ap.add_argument('--work', default=DEFAULT_WORK, help='folder for the wrapper (default build/gfx/apply)')
    args = ap.parse_args(argv)

    for path in (args.inp, args.base):
        if not os.path.isfile(path):
            print('error: %s does not exist' % path, file=sys.stderr)
            return 1
    if os.path.exists(args.out) and os.path.samefile(args.inp, args.out):
        print('error: OUT is the input ROM; IN is never modified', file=sys.stderr)
        return 1
    base = open(args.base, 'rb').read()
    if hashlib.sha1(base).hexdigest() != EXPECTED_SHA1:
        print('error: %s is not the original ROM (expected SHA-1 %s)' % (args.base, EXPECTED_SHA1),
              file=sys.stderr)
        return 1
    rom_in = open(args.inp, 'rb').read()
    for name in args.target or ():
        if name in gfxbuild.TARGETS and gfxbuild.module_path(name) is None:
            print('error: target %s has no module yet (tools/gfx/%s.py)' % (name, name), file=sys.stderr)
            return 1
    try:
        out, report = apply_targets(base, rom_in, args.target, args.work)
    except GfxError as e:
        print('error: %s' % e, file=sys.stderr)
        return 1
    print('\n'.join(report))
    folder = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(folder, exist_ok=True)
    with open(args.out, 'wb') as f:
        f.write(out)
    print('wrote %s (SHA-1 %s%s)' % (args.out, hashlib.sha1(out).hexdigest(),
                                    ', identical to the input' if out == rom_in else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
