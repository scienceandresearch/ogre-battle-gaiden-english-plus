"""TLCS-900/H instruction decoder.

Decodes one instruction at a time into an `Insn` object with typed operands.
Used by the disassembler, the control-flow analyser and the C code generator.

Register operands use the CPU's native 8-bit register codes:
  0x00-0x3F  register banks 0-3 (absolute)        e.g. 0x3C = XHL3
  0xD0-0xDF  previous bank (RFP-1)                e.g. 0xD0 = XWA'
  0xE0-0xEF  current bank (RFP)                   e.g. 0xE0 = XWA / WA / A
  0xF0-0xFF  XIX, XIY, XIZ, XSP
Within a 32-bit register the low two bits select the byte (0 = bits 0-7,
1 = bits 8-15, 2 = bits 16-23, 3 = bits 24-31); 16-bit codes are even.
"""

from .cycles_900h import CYCLES

# 3-bit register fields ("R") always address the current bank.
R3_8 = (0xE1, 0xE0, 0xE5, 0xE4, 0xE9, 0xE8, 0xED, 0xEC)   # W A B C D E H L
R3_16 = (0xE0, 0xE4, 0xE8, 0xEC, 0xF0, 0xF4, 0xF8, 0xFC)  # WA BC DE HL IX IY IZ SP
R3_32 = R3_16                                            # XWA ... XSP

COND_NAMES = ('F', 'LT', 'LE', 'ULE', 'OV', 'MI', 'Z', 'C',
              'T', 'GE', 'GT', 'UGT', 'NOV', 'PL', 'NZ', 'NC')

# Size-agnostic opcode groups (rows of 8 in the reg/src tables).
ALU8 = ('add', 'adc', 'sub', 'sbc', 'and', 'xor', 'or', 'cp')
SHIFT8 = ('rlc', 'rrc', 'rl', 'rr', 'sla', 'sra', 'sll', 'srl')
CF_OPS = ('andcf', 'orcf', 'xorcf', 'ldcf', 'stcf')


class DecodeError(Exception):
    pass


# --------------------------------------------------------------------------
# Operands
# --------------------------------------------------------------------------

class Reg:
    __slots__ = ('size', 'code')

    def __init__(self, size, code):
        self.size = size
        if size == 16:
            code &= ~1
        elif size == 32:
            code &= ~3
        self.code = code & 0xFF

    def __repr__(self):
        return reg_name(self.size, self.code)

    def __eq__(self, other):
        return isinstance(other, Reg) and other.size == self.size and other.code == self.code

    def __hash__(self):
        return hash(('R', self.size, self.code))


class Imm:
    __slots__ = ('size', 'value')

    def __init__(self, size, value):
        self.size = size
        self.value = value

    def __repr__(self):
        if self.size == 3 or self.size == 4:
            return str(self.value)
        return '0x%X' % self.value


class Mem:
    """Memory operand.

    mode: 'abs'  -> address in `disp`
          'r'    -> (base + disp)          disp may be 0
          'rr'   -> (base + index)         index is a Reg (8 or 16 bit, signed)
          'pre'  -> (-base) predecrement by `step`
          'post' -> (base+) postincrement by `step`
    size: access size in bits (8/16/32) or 0 for address-only operands.
    """
    __slots__ = ('size', 'mode', 'base', 'disp', 'index', 'step')

    def __init__(self, size, mode, base=None, disp=0, index=None, step=0):
        self.size = size
        self.mode = mode
        self.base = base
        self.disp = disp
        self.index = index
        self.step = step

    def with_size(self, size):
        return Mem(size, self.mode, self.base, self.disp, self.index, self.step)

    def __repr__(self):
        if self.mode == 'abs':
            return '(0x%X)' % self.disp
        b = reg_name(32, self.base)
        if self.mode == 'r':
            if self.disp == 0:
                return '(%s)' % b
            return '(%s%+d)' % (b, self.disp)
        if self.mode == 'rr':
            return '(%s+%r)' % (b, self.index)
        if self.mode == 'pre':
            return '(-%s:%d)' % (b, self.step)
        if self.mode == 'post':
            return '(%s+:%d)' % (b, self.step)
        return '(?)'


class CReg:
    __slots__ = ('size', 'code')

    def __init__(self, size, code):
        self.size = size
        self.code = code

    def __repr__(self):
        return creg_name(self.size, self.code)


class Special:
    """Implicit operands: 'SR', 'F', "F'", 'A'(plain) etc."""
    __slots__ = ('name',)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


SR = Special('SR')
F = Special('F')
FP = Special("F'")


# --------------------------------------------------------------------------
# Register naming
# --------------------------------------------------------------------------

_B8 = ('A', 'W', 'QA', 'QW', 'C', 'B', 'QC', 'QB', 'E', 'D', 'QE', 'QD', 'L', 'H', 'QL', 'QH')
_B16 = ('WA', 'QWA', 'BC', 'QBC', 'DE', 'QDE', 'HL', 'QHL')
_B32 = ('XWA', 'XBC', 'XDE', 'XHL')
_I8 = ('IXL', 'IXH', 'QIXL', 'QIXH', 'IYL', 'IYH', 'QIYL', 'QIYH',
       'IZL', 'IZH', 'QIZL', 'QIZH', 'SPL', 'SPH', 'QSPL', 'QSPH')
_I16 = ('IX', 'QIX', 'IY', 'QIY', 'IZ', 'QIZ', 'SP', 'QSP')
_I32 = ('XIX', 'XIY', 'XIZ', 'XSP')


def reg_name(size, code):
    if size == 8:
        if code < 0x40:
            n = _B8[code & 15]
            return ('R' + n if not n.startswith('Q') else n) + str(code >> 4)
        if 0xD0 <= code <= 0xDF:
            return _B8[code & 15] + "'"
        if 0xE0 <= code <= 0xEF:
            return _B8[code & 15]
        if code >= 0xF0:
            return _I8[code & 15]
    elif size == 16:
        if code < 0x40:
            n = _B16[(code & 15) >> 1]
            return ('R' + n if not n.startswith('Q') else n) + str(code >> 4)
        if 0xD0 <= code <= 0xDF:
            return _B16[(code & 15) >> 1] + "'"
        if 0xE0 <= code <= 0xEF:
            return _B16[(code & 15) >> 1]
        if code >= 0xF0:
            return _I16[(code & 15) >> 1]
    elif size == 32:
        if code < 0x40:
            return _B32[(code & 15) >> 2] + str(code >> 4)
        if 0xD0 <= code <= 0xDF:
            return _B32[(code & 15) >> 2] + "'"
        if 0xE0 <= code <= 0xEF:
            return _B32[(code & 15) >> 2]
        if code >= 0xF0:
            return _I32[(code & 15) >> 2]
    return 'r%d?%02X' % (size, code)


def valid_reg(code):
    return code < 0x40 or code >= 0xD0


_CREG32 = {0x00: 'DMAS0', 0x04: 'DMAS1', 0x08: 'DMAS2', 0x0C: 'DMAS3',
           0x10: 'DMAD0', 0x14: 'DMAD1', 0x18: 'DMAD2', 0x1C: 'DMAD3',
           0x20: 'DMAC0', 0x24: 'DMAC1', 0x28: 'DMAC2', 0x2C: 'DMAC3',
           0x3C: 'INTNEST'}


def creg_name(size, code):
    if size == 32:
        return _CREG32.get(code & ~3, 'cr32?%02X' % code)
    if size == 16:
        base = _CREG32.get(code & ~3)
        if base is None:
            return 'cr16?%02X' % code
        if base.startswith('DMAC'):
            return base if (code & 2) == 0 else base + 'H'
        return base + ('L' if (code & 2) == 0 else 'H') if base != 'INTNEST' else base
    base = _CREG32.get(code & ~3)
    if base is None:
        return 'cr8?%02X' % code
    if base.startswith('DMAM') or base.startswith('DMAC'):
        return base.replace('DMAC', 'DMAM') if (code & 3) == 2 else '%s.b%d' % (base, code & 3)
    return '%s.b%d' % (base, code & 3)


# --------------------------------------------------------------------------
# Instruction
# --------------------------------------------------------------------------

class Insn:
    """A decoded instruction.

    kind (control flow):
      'seq'     falls through
      'jump'    unconditional static jump to `target`
      'branch'  conditional static jump to `target` (cond) or fall through
      'ijump'   jump through computed address (operand 0 is a Mem with mode != abs),
                possibly conditional
      'call'    static call (possibly conditional)
      'icall'   computed call
      'ret'     return (possibly conditional)
      'reti'    return from interrupt
      'swi'     software interrupt
      'halt'
      'invalid' undefined opcode
    """
    __slots__ = ('addr', 'length', 'mnem', 'size', 'ops', 'cond', 'kind',
                 'target', 'cycles', 'raw', 'extra', 'raw_first')

    def __init__(self, addr):
        self.addr = addr
        self.length = 0
        self.mnem = None
        self.size = 0
        self.ops = ()
        self.cond = None
        self.kind = 'seq'
        self.target = None
        self.cycles = 0
        self.raw = b''
        self.extra = None   # misc decoder info (e.g. LDI register pair)
        self.raw_first = 0

    @property
    def next(self):
        return self.addr + self.length

    def text(self):
        m = self.mnem
        if self.size and self.mnem not in ('jp', 'call', 'jr', 'jrl', 'calr', 'ret', 'djnz', 'lda', 'ldar'):
            m += {8: '.b', 16: '.w', 32: '.l'}.get(self.size, '')
        parts = []
        if self.cond is not None and self.mnem in ('jp', 'call', 'jr', 'jrl', 'ret', 'scc'):
            parts.append(COND_NAMES[self.cond])
        for op in self.ops:
            parts.append(repr(op))
        if self.target is not None and self.mnem in ('jr', 'jrl', 'calr', 'djnz'):
            parts[-1] = '0x%06X' % self.target
        return m + (' ' + ', '.join(parts) if parts else '')

    def __repr__(self):
        return '%06X: %-20s %s' % (self.addr, ' '.join('%02X' % b for b in self.raw), self.text())


# --------------------------------------------------------------------------
# Decoder
# --------------------------------------------------------------------------

def _s8(v):
    return v - 0x100 if v & 0x80 else v


def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


class _Stream:
    __slots__ = ('read', 'start', 'pc')

    def __init__(self, read, addr):
        self.read = read
        self.start = addr
        self.pc = addr

    def u8(self):
        v = self.read(self.pc & 0xFFFFFF)
        self.pc += 1
        return v

    def u16(self):
        lo = self.u8()
        return lo | (self.u8() << 8)

    def u24(self):
        lo = self.u16()
        return lo | (self.u8() << 16)

    def u32(self):
        lo = self.u16()
        return lo | (self.u16() << 16)


def _imm(st, size):
    if size == 8:
        return Imm(8, st.u8())
    if size == 16:
        return Imm(16, st.u16())
    return Imm(32, st.u32())


# Extra states charged for each addressing form (TLCS-900/H, per MAME).
_MODE_CYCLES = {'abs8': 1, 'abs16': 2, 'abs24': 3, 'r': 1, 'rd16': 3, 'rr': 3,
                'prepost': 1, 'pcrel': 3}


def _decode_mem_ext(st, size, insn):
    """Decode the operand of C0-C5/D0-D5/E0-E5/F0-F5 prefixes.

    Returns (Mem, extra_cycles)."""
    op = insn.raw_first & 7
    if op == 0:
        return Mem(size, 'abs', disp=st.u8()), _MODE_CYCLES['abs8']
    if op == 1:
        return Mem(size, 'abs', disp=st.u16()), _MODE_CYCLES['abs16']
    if op == 2:
        return Mem(size, 'abs', disp=st.u24()), _MODE_CYCLES['abs24']
    if op == 3:
        b = st.u8()
        if (b & 3) == 0:
            if not valid_reg(b):
                raise DecodeError('bad base register %02X' % b)
            return Mem(size, 'r', base=b & ~3, disp=0), _MODE_CYCLES['r']
        if (b & 3) == 1:
            if not valid_reg(b):
                raise DecodeError('bad base register %02X' % b)
            return Mem(size, 'r', base=b & ~3, disp=_s16(st.u16())), _MODE_CYCLES['rd16']
        if b == 0x03 or b == 0x07:
            base = st.u8()
            idx = st.u8()
            if not valid_reg(base) or not valid_reg(idx):
                raise DecodeError('bad index registers')
            isz = 8 if b == 0x03 else 16
            return Mem(size, 'rr', base=base & ~3, index=Reg(isz, idx)), _MODE_CYCLES['rr']
        if b == 0x13:
            d = _s16(st.u16())
            return Mem(size, 'abs', disp=(st.pc + d) & 0xFFFFFF), _MODE_CYCLES['pcrel']
        raise DecodeError('bad extended mode byte %02X' % b)
    if op == 4 or op == 5:
        b = st.u8()
        if (b & 3) == 3:
            raise DecodeError('bad pre/post step')
        if not valid_reg(b):
            raise DecodeError('bad base register %02X' % b)
        return Mem(size, 'pre' if op == 4 else 'post', base=b & ~3, step=1 << (b & 3)), \
            _MODE_CYCLES['prepost']
    raise DecodeError('undefined prefix')


def decode(read, addr):
    """Decode one instruction. `read(addr)` returns a byte. Raises DecodeError."""
    insn = Insn(addr)
    st = _Stream(read, addr)
    op = st.u8()
    insn.raw_first = op
    _decode_main(st, op, insn)
    insn.length = st.pc - addr
    insn.raw = bytes(read((addr + i) & 0xFFFFFF) for i in range(insn.length))
    return insn


def _decode_main(st, op, insn):
    C = CYCLES['main']
    insn.cycles = C[op]

    if op == 0x00:
        insn.mnem = 'nop'
    elif op == 0x02:
        insn.mnem, insn.size, insn.ops = 'push', 16, (SR,)
    elif op == 0x03:
        insn.mnem, insn.size, insn.ops = 'pop', 16, (SR,)
    elif op == 0x05:
        insn.mnem, insn.kind = 'halt', 'halt'
    elif op == 0x06:
        n = st.u8() & 7
        if n == 7:
            insn.mnem = 'di'
        else:
            insn.mnem, insn.ops = 'ei', (Imm(3, n),)
    elif op == 0x07:
        insn.mnem, insn.kind = 'reti', 'reti'
    elif op == 0x08:
        a = st.u8()
        insn.mnem, insn.size, insn.ops = 'ld', 8, (Mem(8, 'abs', disp=a), Imm(8, st.u8()))
    elif op == 0x09:
        insn.mnem, insn.size, insn.ops = 'push', 8, (Imm(8, st.u8()),)
    elif op == 0x0A:
        a = st.u8()
        insn.mnem, insn.size, insn.ops = 'ld', 16, (Mem(16, 'abs', disp=a), Imm(16, st.u16()))
    elif op == 0x0B:
        insn.mnem, insn.size, insn.ops = 'push', 16, (Imm(16, st.u16()),)
    elif op == 0x0C:
        insn.mnem = 'incf'
    elif op == 0x0D:
        insn.mnem = 'decf'
    elif op == 0x0E:
        insn.mnem, insn.kind = 'ret', 'ret'
    elif op == 0x0F:
        insn.mnem, insn.kind, insn.ops = 'retd', 'ret', (Imm(16, _s16(st.u16())),)
    elif op == 0x10:
        insn.mnem = 'rcf'
    elif op == 0x11:
        insn.mnem = 'scf'
    elif op == 0x12:
        insn.mnem = 'ccf'
    elif op == 0x13:
        insn.mnem = 'zcf'
    elif op == 0x14:
        insn.mnem, insn.size, insn.ops = 'push', 8, (Reg(8, 0xE0),)
    elif op == 0x15:
        insn.mnem, insn.size, insn.ops = 'pop', 8, (Reg(8, 0xE0),)
    elif op == 0x16:
        insn.mnem, insn.ops = 'exff', (F, FP)
    elif op == 0x17:
        insn.mnem, insn.ops = 'ldf', (Imm(3, st.u8() & 3),)
    elif op == 0x18:
        insn.mnem, insn.size, insn.ops = 'push', 8, (F,)
    elif op == 0x19:
        insn.mnem, insn.size, insn.ops = 'pop', 8, (F,)
    elif op == 0x1A or op == 0x1B:
        t = st.u16() if op == 0x1A else st.u24()
        insn.mnem, insn.kind, insn.target = 'jp', 'jump', t
        insn.ops = (Imm(24, t),)
    elif op == 0x1C or op == 0x1D:
        t = st.u16() if op == 0x1C else st.u24()
        insn.mnem, insn.kind, insn.target = 'call', 'call', t
        insn.ops = (Imm(24, t),)
    elif op == 0x1E:
        d = _s16(st.u16())
        t = (st.pc + d) & 0xFFFFFF
        insn.mnem, insn.kind, insn.target = 'calr', 'call', t
        insn.ops = (Imm(24, t),)
    elif 0x20 <= op <= 0x27:
        insn.mnem, insn.size, insn.ops = 'ld', 8, (Reg(8, R3_8[op & 7]), Imm(8, st.u8()))
    elif 0x28 <= op <= 0x2F:
        insn.mnem, insn.size, insn.ops = 'push', 16, (Reg(16, R3_16[op & 7]),)
    elif 0x30 <= op <= 0x37:
        insn.mnem, insn.size, insn.ops = 'ld', 16, (Reg(16, R3_16[op & 7]), Imm(16, st.u16()))
    elif 0x38 <= op <= 0x3F:
        insn.mnem, insn.size, insn.ops = 'push', 32, (Reg(32, R3_32[op & 7]),)
    elif 0x40 <= op <= 0x47:
        insn.mnem, insn.size, insn.ops = 'ld', 32, (Reg(32, R3_32[op & 7]), Imm(32, st.u32()))
    elif 0x48 <= op <= 0x4F:
        insn.mnem, insn.size, insn.ops = 'pop', 16, (Reg(16, R3_16[op & 7]),)
    elif 0x58 <= op <= 0x5F:
        insn.mnem, insn.size, insn.ops = 'pop', 32, (Reg(32, R3_32[op & 7]),)
    elif 0x60 <= op <= 0x7F:
        if op < 0x70:
            d = _s8(st.u8())
            insn.mnem = 'jr'
        else:
            d = _s16(st.u16())
            insn.mnem = 'jrl'
        t = (st.pc + d) & 0xFFFFFF
        cc = op & 15
        insn.cond, insn.target = cc, t
        insn.ops = (Imm(24, t),)
        if cc == 8:
            insn.kind = 'jump'
        elif cc == 0:
            insn.kind = 'seq'   # never taken
        else:
            insn.kind = 'branch'
    elif 0x80 <= op <= 0xAF:
        size = (8, 16, 32)[(op - 0x80) >> 4]
        base = R3_32[op & 7]
        extra = 0
        if op & 8:
            mem = Mem(size, 'r', base=base, disp=_s8(st.u8()))
            extra = 1
        else:
            mem = Mem(size, 'r', base=base, disp=0)
        tbl = {0x80: '80', 0x88: '88', 0x90: '90', 0x98: '98', 0xA0: 'a0', 0xA8: 'a0'}[op & 0xF8]
        _decode_src(st, op, mem, insn, tbl, extra)
    elif 0xB0 <= op <= 0xBF:
        base = R3_32[op & 7]
        if op & 8:
            mem = Mem(0, 'r', base=base, disp=_s8(st.u8()))
            _decode_dst(st, op, mem, insn, 'b8', 1)
        else:
            mem = Mem(0, 'r', base=base, disp=0)
            _decode_dst(st, op, mem, insn, 'b0', 0)
    elif op in (0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5,
                0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5,
                0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5):
        size = {0xC0: 8, 0xD0: 16, 0xE0: 32}[op & 0xF0]
        mem, extra = _decode_mem_ext(st, size, insn)
        _decode_src(st, op, mem, insn, {8: 'c0', 16: 'd0', 32: 'e0'}[size], extra)
    elif op in (0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5):
        mem, extra = _decode_mem_ext(st, 0, insn)
        _decode_dst(st, op, mem, insn, 'f0', extra)
    elif op in (0xC7, 0xD7, 0xE7) or 0xC8 <= op <= 0xCF or 0xD8 <= op <= 0xDF or 0xE8 <= op <= 0xEF:
        size = {0xC0: 8, 0xD0: 16, 0xE0: 32}[op & 0xF0]
        extra = 0
        if (op & 7) == 7 and not (op & 8):
            code = st.u8()
            if not valid_reg(code):
                raise DecodeError('bad register code %02X' % code)
            reg = Reg(size, code)
            extra = 1
        else:
            reg = Reg(size, (R3_8 if size == 8 else R3_16)[op & 7])
        _decode_reg(st, op, reg, insn, {8: 'c8', 16: 'd8', 32: 'e8'}[size], extra)
    elif op == 0xF7:
        z0 = st.u8()
        a = st.u8()
        z1 = st.u8()
        v = st.u8()
        z2 = st.u8()
        insn.mnem, insn.size, insn.ops = 'ld', 8, (Mem(8, 'abs', disp=a), Imm(8, v))
        insn.extra = 'ldx'
    elif 0xF8 <= op <= 0xFF:
        insn.mnem, insn.kind, insn.ops = 'swi', 'swi', (Imm(3, op & 7),)
    else:
        insn.mnem, insn.kind = 'undefined', 'invalid'
        raise DecodeError('undefined opcode %02X' % op)


def _bad(insn, why):
    insn.mnem, insn.kind = 'undefined', 'invalid'
    raise DecodeError(why)


def _decode_src(st, first, mem, insn, tbl, extra):
    op = st.u8()
    size = mem.size
    insn.cycles = CYCLES[tbl][op] + extra
    long_ = size == 32
    r3 = R3_8 if size == 8 else R3_16

    if op == 0x04 and not long_:
        insn.mnem, insn.size, insn.ops = 'push', size, (mem,)
    elif op in (0x06, 0x07) and size == 8:
        insn.mnem, insn.size, insn.ops = ('rld', 'rrd')[op - 6], 8, (Reg(8, 0xE0), mem)
    elif 0x10 <= op <= 0x13 and size in (8, 16):
        insn.mnem = ('ldi', 'ldir', 'ldd', 'lddr')[op - 0x10]
        insn.size = size
        # (XIX+),(XIY+) form when the prefix register is XIY, else (XDE+),(XHL+)
        insn.extra = 'xix' if (first & 7) == 5 else 'xde'
        if first & 0xF0 not in (0x80, 0x90) or (first & 8):
            # Only (R) prefixes encode block transfers sensibly.
            insn.extra += '?'
    elif 0x14 <= op <= 0x17 and size in (8, 16):
        insn.mnem = ('cpi', 'cpir', 'cpd', 'cpdr')[op - 0x14]
        insn.size = size
        insn.ops = (Reg(size, 0xE0), Reg(32, R3_32[first & 7]))
        if first & 0xF0 not in (0x80, 0x90) or (first & 8):
            insn.extra = '?'
    elif op == 0x19 and not long_:
        dst = Mem(size, 'abs', disp=st.u16())
        insn.mnem, insn.size, insn.ops = 'ld', size, (dst, mem)
    elif 0x20 <= op <= 0x27:
        insn.mnem, insn.size, insn.ops = 'ld', size, (Reg(size, r3[op & 7]), mem)
    elif 0x30 <= op <= 0x37 and not long_:
        insn.mnem, insn.size, insn.ops = 'ex', size, (mem, Reg(size, r3[op & 7]))
    elif 0x38 <= op <= 0x3F and not long_:
        insn.mnem, insn.size, insn.ops = ALU8[op - 0x38], size, (mem, _imm(st, size))
    elif 0x40 <= op <= 0x5F and not long_:
        insn.mnem = ('mul', 'muls', 'div', 'divs')[(op - 0x40) >> 3]
        insn.size = size
        insn.ops = (Reg(size, r3[op & 7]), mem)
    elif 0x60 <= op <= 0x6F and not long_:
        n = op & 7
        insn.mnem = 'inc' if op < 0x68 else 'dec'
        insn.size, insn.ops = size, (Imm(4, n if n else 8), mem)
    elif 0x78 <= op <= 0x7F and not long_:
        insn.mnem, insn.size, insn.ops = SHIFT8[op - 0x78], size, (Imm(4, 1), mem)
    elif op >= 0x80:
        grp = (op - 0x80) >> 4
        insn.mnem = ALU8[grp]
        insn.size = size
        r = Reg(size, r3[op & 7])
        insn.ops = (mem, r) if op & 8 else (r, mem)
    else:
        _bad(insn, 'undefined src op %02X/%02X' % (first, op))


def _decode_dst(st, first, mem, insn, tbl, extra):
    op = st.u8()
    insn.cycles = CYCLES[tbl][op] + extra
    if op == 0x00:
        insn.mnem, insn.size, insn.ops = 'ld', 8, (mem.with_size(8), Imm(8, st.u8()))
    elif op == 0x02:
        insn.mnem, insn.size, insn.ops = 'ld', 16, (mem.with_size(16), Imm(16, st.u16()))
    elif op == 0x04:
        insn.mnem, insn.size, insn.ops = 'pop', 8, (mem.with_size(8),)
    elif op == 0x06:
        insn.mnem, insn.size, insn.ops = 'pop', 16, (mem.with_size(16),)
    elif op == 0x14:
        insn.mnem, insn.size, insn.ops = 'ld', 8, (mem.with_size(8), Mem(8, 'abs', disp=st.u16()))
    elif op == 0x16:
        insn.mnem, insn.size, insn.ops = 'ld', 16, (mem.with_size(16), Mem(16, 'abs', disp=st.u16()))
    elif 0x20 <= op <= 0x27:
        insn.mnem, insn.size, insn.ops = 'lda', 16, (Reg(16, R3_16[op & 7]), mem.with_size(0))
    elif 0x28 <= op <= 0x2C:
        insn.mnem, insn.size, insn.ops = CF_OPS[op - 0x28], 8, (Reg(8, 0xE0), mem.with_size(8))
    elif 0x30 <= op <= 0x37:
        insn.mnem, insn.size, insn.ops = 'lda', 32, (Reg(32, R3_32[op & 7]), mem.with_size(0))
    elif 0x40 <= op <= 0x47:
        insn.mnem, insn.size, insn.ops = 'ld', 8, (mem.with_size(8), Reg(8, R3_8[op & 7]))
    elif 0x50 <= op <= 0x57:
        insn.mnem, insn.size, insn.ops = 'ld', 16, (mem.with_size(16), Reg(16, R3_16[op & 7]))
    elif 0x60 <= op <= 0x67:
        insn.mnem, insn.size, insn.ops = 'ld', 32, (mem.with_size(32), Reg(32, R3_32[op & 7]))
    elif 0x80 <= op <= 0xCF:
        grp = (op - 0x80) >> 3
        insn.mnem = ('andcf', 'orcf', 'xorcf', 'ldcf', 'stcf', 'tset', 'res', 'set', 'chg', 'bit')[grp]
        insn.size, insn.ops = 8, (Imm(3, op & 7), mem.with_size(8))
    elif 0xD0 <= op <= 0xDF:
        cc = op & 15
        insn.mnem, insn.cond, insn.ops = 'jp', cc, (mem.with_size(0),)
        if mem.mode == 'abs':
            insn.target = mem.disp
            insn.kind = 'jump' if cc == 8 else ('seq' if cc == 0 else 'branch')
        else:
            insn.kind = 'ijump' if cc != 0 else 'seq'
    elif 0xE0 <= op <= 0xEF:
        cc = op & 15
        insn.mnem, insn.cond, insn.ops = 'call', cc, (mem.with_size(0),)
        if mem.mode == 'abs':
            insn.target = mem.disp
            insn.kind = 'call' if cc != 0 else 'seq'
        else:
            insn.kind = 'icall' if cc != 0 else 'seq'
    elif 0xF0 <= op <= 0xFF:
        cc = op & 15
        insn.mnem, insn.cond = 'ret', cc
        insn.kind = 'ret' if cc != 0 else 'seq'
        if mem.mode in ('pre', 'post'):
            # Address side effects still happen; keep the operand around.
            insn.ops = (mem.with_size(0),)
            insn.extra = 'ret-sidefx'
    else:
        _bad(insn, 'undefined dst op %02X/%02X' % (first, op))
    if insn.mnem == 'lda' and first == 0xF3 and mem.mode == 'abs':
        insn.mnem = 'ldar'


def _decode_reg(st, first, reg, insn, tbl, extra):
    op = st.u8()
    size = reg.size
    insn.cycles = CYCLES[tbl][op] + extra
    B, W, L = size == 8, size == 16, size == 32
    r3 = R3_8 if B else R3_16
    insn.size = size

    def need(ok):
        if not ok:
            _bad(insn, 'undefined reg op %02X/%02X (size %d)' % (first, op, size))

    if op == 0x03:
        insn.mnem, insn.ops = 'ld', (reg, _imm(st, size))
    elif op == 0x04:
        insn.mnem, insn.ops = 'push', (reg,)
    elif op == 0x05:
        insn.mnem, insn.ops = 'pop', (reg,)
    elif op == 0x06:
        need(not L)
        insn.mnem, insn.ops = 'cpl', (reg,)
    elif op == 0x07:
        need(not L)
        insn.mnem, insn.ops = 'neg', (reg,)
    elif 0x08 <= op <= 0x0B:
        need(not L)
        insn.mnem = ('mul', 'muls', 'div', 'divs')[op - 8]
        insn.ops = (reg, _imm(st, size))
    elif op == 0x0C:
        need(L)
        insn.mnem, insn.ops = 'link', (reg, Imm(16, _s16(st.u16())))
    elif op == 0x0D:
        need(L)
        insn.mnem, insn.ops = 'unlk', (reg,)
    elif op == 0x0E or op == 0x0F:
        need(W)
        insn.mnem, insn.ops = ('bs1f', 'bs1b')[op - 0x0E], (Reg(8, 0xE0), reg)
    elif op == 0x10:
        need(B)
        insn.mnem, insn.ops = 'daa', (reg,)
    elif op == 0x12 or op == 0x13:
        need(not B)
        insn.mnem, insn.ops = ('extz', 'exts')[op - 0x12], (reg,)
    elif op == 0x14:
        need(not B)
        insn.mnem, insn.ops = 'paa', (reg,)
    elif op == 0x16:
        need(W)
        insn.mnem, insn.ops = 'mirr', (reg,)
    elif op == 0x19:
        need(W)
        insn.mnem, insn.ops = 'mula', (reg,)
    elif op == 0x1C:
        need(not L)
        d = _s8(st.u8())
        t = (st.pc + d) & 0xFFFFFF
        insn.mnem, insn.ops, insn.target, insn.kind = 'djnz', (reg, Imm(24, t)), t, 'branch'
    elif 0x20 <= op <= 0x24:
        need(not L)
        insn.mnem, insn.ops = CF_OPS[op - 0x20], (Imm(4, st.u8() & 15), reg)
    elif 0x28 <= op <= 0x2C:
        need(not L)
        insn.mnem, insn.ops = CF_OPS[op - 0x28], (Reg(8, 0xE0), reg)
    elif op == 0x2E:
        insn.mnem, insn.ops = 'ldc', (CReg(size, st.u8()), reg)
    elif op == 0x2F:
        insn.mnem, insn.ops = 'ldc', (reg, CReg(size, st.u8()))
    elif 0x30 <= op <= 0x34:
        need(not L)
        insn.mnem = ('res', 'set', 'chg', 'bit', 'tset')[op - 0x30]
        insn.ops = (Imm(4, st.u8() & 15), reg)
    elif op in (0x38, 0x39, 0x3A, 0x3C, 0x3D, 0x3E):
        need(W)
        insn.mnem = {0x38: 'minc1', 0x39: 'minc2', 0x3A: 'minc4',
                     0x3C: 'mdec1', 0x3D: 'mdec2', 0x3E: 'mdec4'}[op]
        insn.ops = (Imm(16, st.u16()), reg)
    elif 0x40 <= op <= 0x5F:
        need(not L)
        insn.mnem = ('mul', 'muls', 'div', 'divs')[(op - 0x40) >> 3]
        insn.ops = (Reg(size, r3[op & 7]), reg)
    elif 0x60 <= op <= 0x6F:
        n = op & 7
        insn.mnem = 'inc' if op < 0x68 else 'dec'
        insn.ops = (Imm(4, n if n else 8), reg)
    elif 0x70 <= op <= 0x7F:
        need(not L)
        insn.mnem, insn.cond, insn.ops = 'scc', op & 15, (reg,)
    elif 0x80 <= op <= 0x87:
        insn.mnem, insn.ops = 'add', (Reg(size, r3[op & 7]), reg)
    elif 0x88 <= op <= 0x8F:
        insn.mnem, insn.ops = 'ld', (Reg(size, r3[op & 7]), reg)
    elif 0x90 <= op <= 0x97:
        insn.mnem, insn.ops = 'adc', (Reg(size, r3[op & 7]), reg)
    elif 0x98 <= op <= 0x9F:
        insn.mnem, insn.ops = 'ld', (reg, Reg(size, r3[op & 7]))
    elif 0xA0 <= op <= 0xA7:
        insn.mnem, insn.ops = 'sub', (Reg(size, r3[op & 7]), reg)
    elif 0xA8 <= op <= 0xAF:
        insn.mnem, insn.ops = 'ld', (reg, Imm(size, op & 7))
    elif 0xB0 <= op <= 0xB7:
        insn.mnem, insn.ops = 'sbc', (Reg(size, r3[op & 7]), reg)
    elif 0xB8 <= op <= 0xBF:
        need(not L)
        insn.mnem, insn.ops = 'ex', (Reg(size, r3[op & 7]), reg)
    elif 0xC0 <= op <= 0xC7:
        insn.mnem, insn.ops = 'and', (Reg(size, r3[op & 7]), reg)
    elif 0xC8 <= op <= 0xCF:
        insn.mnem, insn.ops = ALU8[op - 0xC8], (reg, _imm(st, size))
    elif 0xD0 <= op <= 0xD7:
        insn.mnem, insn.ops = 'xor', (Reg(size, r3[op & 7]), reg)
    elif 0xD8 <= op <= 0xDF:
        need(not L)
        insn.mnem, insn.ops = 'cp', (reg, Imm(size, op & 7))
    elif 0xE0 <= op <= 0xE7:
        insn.mnem, insn.ops = 'or', (Reg(size, r3[op & 7]), reg)
    elif 0xE8 <= op <= 0xEF:
        n = st.u8() & 15
        insn.mnem, insn.ops = SHIFT8[op - 0xE8], (Imm(4, n if n else 16), reg)
    elif 0xF0 <= op <= 0xF7:
        insn.mnem, insn.ops = 'cp', (Reg(size, r3[op & 7]), reg)
    elif 0xF8 <= op <= 0xFF:
        insn.mnem, insn.ops = SHIFT8[op - 0xF8], (Reg(8, 0xE0), reg)
    else:
        _bad(insn, 'undefined reg op %02X/%02X' % (first, op))
