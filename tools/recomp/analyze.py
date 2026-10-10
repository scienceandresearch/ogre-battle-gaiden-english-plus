"""Static control-flow analysis of the cartridge program.

Finds all code reachable from the known entry points (header entry, interrupt
vectors, code pointers found in immediates and data tables), splits it into
basic blocks and groups blocks into regions (one region per entry point).

Usage: python -m tools.recomp.analyze rom/baserom.ngc [--report]
"""
import sys
import json
from collections import defaultdict, deque

from .tlcs900 import decode, DecodeError, Imm, Mem, Reg
from .rom import Rom, ROM_BASE


class Analysis:
    def __init__(self, rom, config=None):
        self.rom = rom
        self.config = config or {}
        self.insns = {}            # addr -> Insn
        self.owner = {}            # byte addr -> insn addr (for overlap detection)
        self.entries = {}          # addr -> reason (set of strings)
        self.block_starts = set()
        self.call_targets = set()
        self.ijumps = []           # addresses of indirect jumps
        self.icalls = []
        self.invalid = {}          # addr -> message
        self.overlaps = set()
        self.code_ptrs = defaultdict(set)   # target -> set(source addrs)
        self.swi = defaultdict(set)

    # ------------------------------------------------------------------
    def add_entry(self, addr, reason):
        addr &= 0xFFFFFF
        if not self.rom.contains(addr):
            return False
        self.entries.setdefault(addr, set()).add(reason)
        return True

    def explore(self, roots):
        work = deque(roots)
        seen_entry = set()
        while work:
            start = work.popleft()
            if start in seen_entry:
                continue
            seen_entry.add(start)
            self.block_starts.add(start)
            addr = start
            while True:
                if addr in self.insns:
                    self.block_starts.add(addr)
                    break
                if not self.rom.contains(addr):
                    self.invalid[addr] = 'outside ROM'
                    break
                if addr in self.owner and self.owner[addr] != addr:
                    self.overlaps.add(addr)
                try:
                    insn = decode(self.rom.read8, addr)
                except DecodeError as e:
                    self.invalid[addr] = str(e)
                    break
                self.insns[addr] = insn
                for i in range(insn.length):
                    self.owner.setdefault(addr + i, addr)
                k = insn.kind
                # Record immediates that look like code pointers.
                for op in insn.ops:
                    if isinstance(op, Imm) and op.size in (24, 32) and insn.mnem in ('ld', 'push'):
                        v = op.value & 0xFFFFFF
                        if self.rom.contains(v) and (op.value >> 24) == 0:
                            self.code_ptrs[v].add(addr)
                    if isinstance(op, Mem) and op.mode == 'abs' and insn.mnem in ('lda', 'ldar'):
                        v = op.disp
                        if self.rom.contains(v):
                            self.code_ptrs[v].add(addr)
                if k == 'seq' or k == 'halt':
                    addr = insn.next
                    continue
                if k == 'branch':
                    work.append(insn.target)
                    self.block_starts.add(insn.target)
                    self.block_starts.add(insn.next)
                    addr = insn.next
                    continue
                if k == 'jump':
                    work.append(insn.target)
                    self.block_starts.add(insn.target)
                    break
                if k == 'call':
                    work.append(insn.target)
                    self.call_targets.add(insn.target)
                    self.block_starts.add(insn.target)
                    self.block_starts.add(insn.next)
                    addr = insn.next
                    continue
                if k == 'icall':
                    self.icalls.append(addr)
                    self.block_starts.add(insn.next)
                    addr = insn.next
                    continue
                if k == 'swi':
                    self.swi[insn.ops[0].value].add(addr)
                    self.block_starts.add(insn.next)
                    addr = insn.next
                    continue
                if k == 'ijump':
                    self.ijumps.append(addr)
                    if insn.cond != 8:
                        self.block_starts.add(insn.next)
                        addr = insn.next
                        continue
                    break
                if k in ('ret', 'reti'):
                    if insn.cond is not None and insn.cond != 8:
                        self.block_starts.add(insn.next)
                        addr = insn.next
                        continue
                    break
                break

    # ------------------------------------------------------------------
    def code_size(self):
        return sum(i.length for i in self.insns.values())


def main():
    rom = Rom(sys.argv[1])
    an = Analysis(rom)
    entry = rom.read32(ROM_BASE + 0x1C) & 0xFFFFFF
    an.add_entry(entry, 'header')
    roots = [entry]
    an.explore(roots)
    # Iterate: follow code pointers found in immediates.
    for it in range(20):
        new = [t for t in an.code_ptrs if t not in an.insns and t not in an.invalid]
        if not new:
            break
        for t in new:
            an.add_entry(t, 'imm-ptr')
        an.explore(new)
    print('instructions: %d  bytes: %d (%.1f%% of ROM)' % (len(an.insns), an.code_size(),
                                                         100.0 * an.code_size() / rom.size))
    print('call targets: %d  block starts: %d' % (len(an.call_targets), len(an.block_starts)))
    print('indirect jumps: %d  indirect calls: %d' % (len(an.ijumps), len(an.icalls)))
    print('invalid decodes: %d  overlaps: %d' % (len(an.invalid), len(an.overlaps)))
    print('swi:', {k: len(v) for k, v in an.swi.items()})
    mn = defaultdict(int)
    for i in an.insns.values():
        mn[i.mnem] += 1
    print('mnemonics:', dict(sorted(mn.items(), key=lambda x: -x[1])))
    if '--report' in sys.argv:
        for a in sorted(an.invalid):
            print('INVALID %06X %s' % (a, an.invalid[a]))
        for a in an.ijumps:
            print('IJUMP  %r' % an.insns[a])
        for a in an.icalls:
            print('ICALL  %r' % an.insns[a])


if __name__ == '__main__':
    main()
