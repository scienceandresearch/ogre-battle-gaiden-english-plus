"""Round-trip test: disassemble game instructions, re-assemble, decode, compare.

Usage: python -m tools.asm.test_roundtrip rom/baserom.ngc
"""
import sys
from collections import Counter

from ..recomp.rom import Rom
from ..recomp.tlcs900 import decode, DecodeError
from ..text.extract import build_walker
from .tlcs900asm import Assembler, AsmError


def canon(ins):
    return (ins.mnem, ins.size, ins.cond, tuple(repr(o) for o in ins.ops), ins.target, ins.extra)


def main():
    rom = Rom(sys.argv[1])
    w = build_walker(rom, log=lambda *a: None)
    addrs = sorted(w.native)
    ok = 0
    fails = Counter()
    examples = {}
    for a in addrs:
        ins = w.native[a]
        if ins.extra in ('ldx',) or ins.mnem == 'undefined':
            continue
        if ins.extra and '?' in str(ins.extra):
            continue
        text = ins.text()
        if ins.mnem == 'ldi' or ins.mnem in ('ldir', 'ldd', 'lddr'):
            text = ins.mnem + {8: '.b', 16: '.w'}[ins.size] + (' (XIX+)' if ins.extra == 'xix' else '')
        asm = Assembler()
        asm.add_source('.org 0x%X\n    %s\n' % (a, text))
        try:
            chunks = asm.assemble()
        except AsmError as e:
            key = 'asm-error:' + ins.mnem
            fails[key] += 1
            examples.setdefault(key, (a, text, str(e).splitlines()[0]))
            continue
        data = chunks[0][1]
        buf = data + b'\x00' * 8
        try:
            back = decode(lambda x: buf[x - a] if 0 <= x - a < len(buf) else 0, a)
        except DecodeError as e:
            fails['undecodable'] += 1
            examples.setdefault('undecodable', (a, text, data.hex(' ')))
            continue
        if canon(back) != canon(ins):
            key = 'mismatch:' + ins.mnem
            fails[key] += 1
            examples.setdefault(key, (a, text, back.text() + '  [' + data.hex(' ') + ' vs ' + ins.raw.hex(' ') + ']'))
            continue
        ok += 1
    print('round-trip ok: %d  failed: %d' % (ok, sum(fails.values())))
    for k, v in fails.most_common():
        a, t, e = examples[k]
        print('  %-24s %5d  e.g. %06X  %-30s -> %s' % (k, v, a, t, e))


if __name__ == '__main__':
    main()
