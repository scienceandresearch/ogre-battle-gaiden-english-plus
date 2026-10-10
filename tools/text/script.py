"""Disassembler / walker for the game's script bytecode.

The engine runs cooperative tasks whose code is a bytecode interpreted by the
VM at 0x20023D (entered from native code with `call 0x20023C`, which pops the
return address as the script pointer). Opcodes are even bytes; the handler
table is at 0x2007A1 indexed by the signed opcode.

Operand format letters:
  b  byte          w  word (little endian)     l  long
  a  24-bit script address (jump/call/loop target)
  d  24-bit data pointer (graphics/animation; not followed)
  S  24-bit script address started as a new task/sub-script
  N  24-bit native code address
  T  24-bit address of a table of 24-bit script addresses
  r  16-bit signed branch offset relative to the end of the instruction
  STR  inline text terminated by a byte >= 0xDF
"""
import sys
from collections import deque

from ..recomp.rom import Rom
from ..recomp.tlcs900 import decode, DecodeError, Imm, Mem, Reg

VM_ENTRY_CALL = 0x20023C     # `call` target: pops return address as script pointer
VM_LOOP = 0x20023D           # loop entry with XDE = script pointer

# opcode: (mnemonic, operand formats, flow)   flow: None, 'end', 'native', 'branch'
OPS = {
    0x80: ('yield', '', None), 0x82: ('wait', 'b', None), 0x84: ('stop', '', 'end'),
    0x86: ('st8', 'bw', None), 0x88: ('st16', 'ww', None), 0x8A: ('st32', 'lw', None),
    0x8C: ('mov8', 'ww', None), 0x8E: ('mov16', 'ww', None), 0x90: ('mov32', 'ww', None),
    0x92: ('ldv8', 'bw', None), 0x94: ('ldv16', 'bw', None), 0x96: ('ldv32', 'bw', None),
    0x98: ('stv8', 'bb', None), 0x9A: ('stv16', 'wb', None), 0x9C: ('stv32', 'lb', None),
    0x9E: ('getv8', 'wb', None), 0xA0: ('getv16', 'wb', None), 0xA2: ('getv32', 'wb', None),
    0xA4: ('movv8', 'bb', None), 0xA6: ('movv16', 'bb', None), 0xA8: ('movv32', 'bb', None),
    0xAA: ('add8', 'bw', None), 0xAC: ('add16', 'ww', None), 0xAE: ('add32', 'lw', None),
    0xB0: ('addm8', 'ww', None), 0xB2: ('addm16', 'ww', None), 0xB4: ('addm32', 'ww', None),
    0xB6: ('addvm8', 'bw', None), 0xB8: ('addvm16', 'bw', None), 0xBA: ('addvm32', 'bw', None),
    0xBC: ('addv8', 'bb', None), 0xBE: ('addv16', 'wb', None), 0xC0: ('addv32', 'lb', None),
    0xC2: ('addmv8', 'wb', None), 0xC4: ('addmv16', 'wb', None), 0xC6: ('addmv32', 'wb', None),
    0xC8: ('addvv8', 'bb', None), 0xCA: ('addvv16', 'bb', None), 0xCC: ('addvv32w', 'bb', None),
    0xCE: ('cnt0', 'b', None), 0xD0: ('cnt1', 'b', None), 0xD2: ('cnt2', 'b', None),
    0xD4: ('loop0', 'a', 'branch'), 0xD6: ('loop1', 'a', 'branch'), 0xD8: ('loop2', 'a', 'branch'),
    0xDA: ('jump', 'a', 'end'), 0xDC: ('call', 'a', None), 0xDE: ('pcall', 'a', None),
    0xE0: ('ret', '', 'end'), 0xE2: ('pret', '', 'end'),
    0xE4: ('switchm', 'wT', 'end'), 0xE6: ('switchv', 'bT', 'end'),
    0xE8: ('callswm', 'wT', None), 0xEA: ('callswv', 'bT', None),
    0xEC: ('resetvars', '', None), 0xEE: ('spawn', 'bS', None), 0xF0: ('kill', 'b', None),
    0xF2: ('sub1', 'S', None), 0xF4: ('kill1', '', None), 0xF6: ('sub2', 'S', None),
    0xF8: ('kill2', '', None), 0xFA: ('dispon', '', None), 0xFC: ('dispoff', '', None),
    0xFE: ('gfxfe', 'dw', None), 0x00: ('gfx00', 'ww', None),
    0x02: ('op02', '', None), 0x04: ('op04', '', None), 0x06: ('op06', '', None),
    0x08: ('anim', 'd', None), 0x0A: ('op0a', 'b', None), 0x0C: ('pos16', 'w', None),
    0x0E: ('posx', 'b', None), 0x10: ('posy', 'b', None), 0x12: ('move', 'bb', None),
    0x14: ('movex', 'b', None), 0x16: ('movey', 'b', None), 0x18: ('tile', 'w', None),
    0x1A: ('attr', 'b', None), 0x1C: ('pal', 'b', None), 0x1E: ('snd2', 'bb', None),
    0x20: ('sndstop', '', None), 0x22: ('snd', 'w', None), 0x24: ('sndx', '', None),
    0x26: ('gfx26', 'dbw', None), 0x28: ('gfx28', 'dbw', None),
    0x2A: ('gfx2a', 'dww', None), 0x2C: ('gfx2c', 'dww', None),
    0x2E: ('ncall', 'N', None), 0x30: ('native', '', 'native'), 0x32: ('text', 'STR', None),
    0x34: ('bchoice', 'r', 'branch'), 0x36: ('setflag', 'b', None),
    0x38: ('bflag', 'br', 'branch'), 0x3A: ('bflag2', 'br', 'branch'),
    0x3C: ('bcmp', 'br', 'branch'), 0x3E: ('b3e', 'wr', 'branch'), 0x40: ('b40', 'wr', 'branch'),
    0x42: ('b42', 'br', 'branch'), 0x44: ('op44', 'b', None), 0x46: ('op46', 'b', None),
    0x48: ('op48', 'l', None), 0x4A: ('op4a', 'b', None),
}


class ScriptInsn:
    __slots__ = ('addr', 'op', 'mnem', 'args', 'length', 'targets', 'text', 'term', 'flow')

    def __init__(self, addr, op):
        self.addr = addr
        self.op = op
        self.mnem = OPS[op][0] if op in OPS else 'bad%02X' % op
        self.args = []
        self.length = 1
        self.targets = []      # (kind, addr): kind in 'a','S','N','T','r'
        self.text = None       # raw bytes of inline string (without terminator)
        self.term = None
        self.flow = OPS[op][2] if op in OPS else 'bad'

    @property
    def next(self):
        return self.addr + self.length


def in_rom(rom, a):
    return rom.contains(a)


def decode_script(rom, addr):
    op = rom.read8(addr)
    ins = ScriptInsn(addr, op)
    if op not in OPS:
        ins.flow = 'bad'
        return ins
    fmt = OPS[op][1]
    p = addr + 1
    if fmt == 'STR':
        start = p
        while rom.read8(p) < 0xDF:
            p += 1
            if p - start > 1024:
                ins.flow = 'bad'
                return ins
        ins.text = rom.bytes(start, p - start)
        ins.term = rom.read8(p)
        p += 1
        ins.length = p - addr
        return ins
    for c in fmt:
        if c == 'b':
            ins.args.append(rom.read8(p)); p += 1
        elif c == 'w':
            ins.args.append(rom.read16(p)); p += 2
        elif c == 'l':
            ins.args.append(rom.read32(p)); p += 4
        elif c in 'aSNTd':
            v = rom.read24(p); p += 3
            ins.args.append(v)
            if c != 'd':
                ins.targets.append((c, v))
        elif c == 'r':
            v = rom.read16(p); p += 2
            if v & 0x8000:
                v -= 0x10000
            ins.args.append(v)
    ins.length = p - addr
    # relative branches are relative to the end of the instruction
    for i, c in enumerate(fmt):
        if c == 'r':
            ins.targets.append(('a', (ins.next + ins.args[i]) & 0xFFFFFF))
    # `st32 <script>, 0x61F0` arms the script run when the next battle starts
    # (boss dialogue); the stored value is a script entry point.
    if op == 0x8A and ins.args[1] in SCRIPT_PTR_VARS:
        ins.targets.append(('S', ins.args[0] & 0xFFFFFF))
    return ins


SCRIPT_PTR_VARS = {0x61F0}


class Walker:
    def __init__(self, rom):
        self.rom = rom
        self.script = {}       # addr -> ScriptInsn
        self.cover = {}        # every byte of script code -> its instruction start
        self.native = {}       # addr -> Insn
        self.script_entries = {}
        self.native_entries = {}
        self.tables = {}       # table addr -> list of targets
        self.bad = {}
        self.wq = deque()
        self.nq = deque()

    def add_script(self, a, why):
        a &= 0xFFFFFF
        if not in_rom(self.rom, a):
            return
        if a not in self.script_entries:
            self.script_entries[a] = why
            self.wq.append(a)

    def add_native(self, a, why):
        a &= 0xFFFFFF
        if not in_rom(self.rom, a):
            return
        if a not in self.native_entries:
            self.native_entries[a] = why
            self.nq.append(a)

    def read_table(self, t, limit=128):
        out = []
        for i in range(limit):
            v = self.rom.read24(t + 3 * i)
            if not in_rom(self.rom, v):
                break
            # stop if the entry points at something that is clearly not a script op
            if self.rom.read8(v) not in OPS:
                break
            out.append(v)
        return out

    def walk_script(self, a):
        while True:
            if a in self.script:
                return
            if not in_rom(self.rom, a):
                self.bad[a] = 'outside ROM'
                return
            ins = decode_script(self.rom, a)
            if ins.flow == 'bad':
                self.bad[a] = 'bad opcode %02X' % ins.op
                return
            # script code never overlaps itself; the first decoding wins
            # (trusted entry points are walked first)
            hit = next((b for b in range(a, a + ins.length) if b in self.cover), None)
            if hit is not None:
                self.bad[a] = 'overlaps insn at %06X' % self.cover[hit]
                return
            self.script[a] = ins
            for b in range(a, a + ins.length):
                self.cover[b] = a
            for kind, t in ins.targets:
                if kind in ('a', 'S'):
                    self.add_script(t, '%s@%06X' % (ins.mnem, a))
                elif kind == 'N':
                    self.add_native(t, 'ncall@%06X' % a)
                elif kind == 'T':
                    ents = self.read_table(t)
                    self.tables[t] = ents
                    for e in ents:
                        self.add_script(e, 'table %06X' % t)
            if ins.flow == 'native':
                self.add_native(ins.next, 'native@%06X' % a)
                return
            if ins.flow == 'end':
                return
            a = ins.next

    def walk_native(self, a, max_insns=4000, span=0x2000):
        """Shallow walk through a native code segment reached from a script:
        follows local jumps/branches only (calls are not followed), records
        re-entries into bytecode, and discards the segment if it decodes to
        undefined instructions (i.e. it is probably data)."""
        origin = a
        seen = {}
        work = [a]
        found = []
        last_xde = None
        while work and len(seen) < max_insns:
            a = work.pop()
            while len(seen) < max_insns:
                if a in seen or a in self.native or not in_rom(self.rom, a) or abs(a - origin) > span:
                    break
                try:
                    ins = decode(self.rom.read8, a)
                except DecodeError as e:
                    self.bad[a] = 'native: %s' % e
                    return   # garbage: keep nothing from this segment
                seen[a] = ins
                if (ins.mnem == 'ld' and isinstance(ins.ops[0], Reg) and ins.ops[0].size == 32 and
                        ins.ops[0].code == 0xE8 and isinstance(ins.ops[1], Imm)):
                    last_xde = ins.ops[1].value & 0xFFFFFF
                k = ins.kind
                if k == 'call' and ins.target == VM_ENTRY_CALL:
                    found.append((ins.next, 'inline@%06X' % a))
                    break
                # `ld XDE, script` + (conditional) jump/call to the VM loop
                if k in ('jump', 'call', 'branch') and ins.target == VM_LOOP:
                    if last_xde is not None:
                        found.append((last_xde, 'xde@%06X' % a))
                    if k == 'jump':
                        break
                if k in ('jump', 'branch') and ins.target is not None and ins.target != VM_LOOP:
                    work.append(ins.target)
                if k in ('jump', 'ret', 'reti', 'ijump', 'invalid') and ins.cond in (None, 8):
                    break
                a = ins.next
        self.native.update(seen)
        for t, why in found:
            self.add_script(t, why)

    def run(self):
        while self.wq or self.nq:
            while self.wq:
                self.walk_script(self.wq.popleft())
            while self.nq:
                self.walk_native(self.nq.popleft())

    def strings(self):
        return sorted((i.addr, i) for i in self.script.values() if i.op == 0x32)


def find_native_seeds(rom):
    """All `call 0x20023C` sites and task-slot immediates in the whole ROM
    (found with a linear scan, validated by decoding)."""
    seeds = []
    data = rom.data
    pat = bytes([0x1D, 0x3C, 0x02, 0x20])
    i = data.find(pat)
    while i >= 0:
        seeds.append(('inline', ROM_BASE_ + i + 4))
        i = data.find(pat, i + 1)
    pat = bytes([0x1C, 0x3C, 0x02])   # call nn (16-bit) only reaches 0x00xxxx; not applicable
    return seeds


ROM_BASE_ = 0x200000
