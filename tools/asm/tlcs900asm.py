"""TLCS-900/H assembler for the translation patch.

Syntax follows the disassembler in tools/recomp/tlcs900.py, for example:

    label:  ld.b    A, (XIY+5)
            ld      XHL, my_table          ; size inferred from register
            ld.w    (0x4406), IX
            ldir.w
            jr      NZ, label
            call    0x200BAC
            ret

Memory operands: (expr) (REG) (REG+expr) (REG-expr) (REG+REG) (-REG) (REG+)
Pre-decrement/post-increment steps default to the access size; use
(-REG:4) or (REG+:4) to force one.

Directives: .org ADDR, .db a,b,"str", .dw, .d24, .dl, .align N, .fill N,V,
            NAME = expr, .include "file"

Every encoded instruction is decoded again with the project's decoder and
compared, so encoder mistakes are caught at assembly time.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from tools.recomp.tlcs900 import decode, DecodeError, Reg as DReg, Mem as DMem, Imm as DImm  # noqa: E402


class AsmError(Exception):
    pass


# ----------------------------------------------------------------------------
# Registers
# ----------------------------------------------------------------------------

REG8 = {'W': 0xE1, 'A': 0xE0, 'B': 0xE5, 'C': 0xE4, 'D': 0xE9, 'E': 0xE8, 'H': 0xED, 'L': 0xEC,
        'QA': 0xE2, 'QW': 0xE3, 'QC': 0xE6, 'QB': 0xE7, 'QE': 0xEA, 'QD': 0xEB, 'QL': 0xEE, 'QH': 0xEF,
        'IXL': 0xF0, 'IXH': 0xF1, 'QIXL': 0xF2, 'QIXH': 0xF3, 'IYL': 0xF4, 'IYH': 0xF5,
        'QIYL': 0xF6, 'QIYH': 0xF7, 'IZL': 0xF8, 'IZH': 0xF9, 'QIZL': 0xFA, 'QIZH': 0xFB,
        'SPL': 0xFC, 'SPH': 0xFD, 'QSPL': 0xFE, 'QSPH': 0xFF}
REG16 = {'WA': 0xE0, 'BC': 0xE4, 'DE': 0xE8, 'HL': 0xEC, 'IX': 0xF0, 'IY': 0xF4, 'IZ': 0xF8, 'SP': 0xFC,
         'QWA': 0xE2, 'QBC': 0xE6, 'QDE': 0xEA, 'QHL': 0xEE, 'QIX': 0xF2, 'QIY': 0xF6, 'QIZ': 0xFA, 'QSP': 0xFE}
REG32 = {'XWA': 0xE0, 'XBC': 0xE4, 'XDE': 0xE8, 'XHL': 0xEC, 'XIX': 0xF0, 'XIY': 0xF4, 'XIZ': 0xF8, 'XSP': 0xFC}

for bank in range(4):
    for i, n in enumerate(('A', 'W', 'QA', 'QW', 'C', 'B', 'QC', 'QB', 'E', 'D', 'QE', 'QD', 'L', 'H', 'QL', 'QH')):
        name = ('R' + n if not n.startswith('Q') else n) + str(bank)
        REG8[name] = bank * 16 + i
    for i, n in enumerate(('WA', 'QWA', 'BC', 'QBC', 'DE', 'QDE', 'HL', 'QHL')):
        name = ('R' + n if not n.startswith('Q') else n) + str(bank)
        REG16[name] = bank * 16 + i * 2
    for i, n in enumerate(('XWA', 'XBC', 'XDE', 'XHL')):
        REG32[n + str(bank)] = bank * 16 + i * 4
for i, n in enumerate(('A', 'W', 'QA', 'QW', 'C', 'B', 'QC', 'QB', 'E', 'D', 'QE', 'QD', 'L', 'H', 'QL', 'QH')):
    REG8[n + "'"] = 0xD0 + i
for i, n in enumerate(('WA', 'QWA', 'BC', 'QBC', 'DE', 'QDE', 'HL', 'QHL')):
    REG16[n + "'"] = 0xD0 + i * 2
for i, n in enumerate(('XWA', 'XBC', 'XDE', 'XHL')):
    REG32[n + "'"] = 0xD0 + i * 4

R3_8 = {0xE1: 0, 0xE0: 1, 0xE5: 2, 0xE4: 3, 0xE9: 4, 0xE8: 5, 0xED: 6, 0xEC: 7}
R3_16 = {0xE0: 0, 0xE4: 1, 0xE8: 2, 0xEC: 3, 0xF0: 4, 0xF4: 5, 0xF8: 6, 0xFC: 7}

COND = {'F': 0, 'LT': 1, 'LE': 2, 'ULE': 3, 'OV': 4, 'PE': 4, 'MI': 5, 'M': 5, 'Z': 6, 'EQ': 6,
        'C': 7, 'ULT': 7, 'T': 8, 'GE': 9, 'GT': 10, 'UGT': 11, 'NOV': 12, 'PO': 12, 'PL': 13,
        'P': 13, 'NZ': 14, 'NE': 14, 'NC': 15, 'UGE': 15}

ALU = ('add', 'adc', 'sub', 'sbc', 'and', 'xor', 'or', 'cp')
SHIFTS = ('rlc', 'rrc', 'rl', 'rr', 'sla', 'sra', 'sll', 'srl')
CFOPS = ('andcf', 'orcf', 'xorcf', 'ldcf', 'stcf')
SIZES = {'b': 8, 'w': 16, 'l': 32}


class Reg:
    def __init__(self, size, code, name):
        self.size, self.code, self.name = size, code, name

    @property
    def r3(self):
        t = R3_8 if self.size == 8 else R3_16
        return t.get(self.code)


class Imm:
    def __init__(self, expr):
        self.expr = expr


class Mem:
    def __init__(self, mode, base=None, disp=None, index=None, step=None):
        self.mode, self.base, self.disp, self.index, self.step = mode, base, disp, index, step


class Cond:
    def __init__(self, cc):
        self.cc = cc


# ----------------------------------------------------------------------------
# Expressions
# ----------------------------------------------------------------------------

_TOKEN = re.compile(r'\s*(0x[0-9A-Fa-f]+|\$[0-9A-Fa-f]+|[0-9]+|[A-Za-z_.][A-Za-z0-9_.]*|<<|>>|[-+*/%&|^~()])')


def eval_expr(expr, symbols, pc):
    tokens = []
    pos = 0
    expr = expr.strip()
    while pos < len(expr):
        m = _TOKEN.match(expr, pos)
        if not m:
            raise AsmError('bad expression: %r' % expr)
        tokens.append(m.group(1))
        pos = m.end()
    out = []
    for t in tokens:
        if t.startswith('0x'):
            out.append(str(int(t, 16)))
        elif t.startswith('$'):
            out.append(str(int(t[1:], 16)))
        elif t[0].isdigit():
            out.append(t)
        elif re.match(r'[A-Za-z_.]', t):
            if t == '.':
                out.append(str(pc))
            elif t in symbols:
                out.append(str(symbols[t]))
            else:
                raise KeyError(t)
        elif t == '/':
            out.append('//')
        else:
            out.append(t)
    return int(eval(' '.join(out), {'__builtins__': {}}, {}))


# ----------------------------------------------------------------------------
# Operand parsing
# ----------------------------------------------------------------------------

def parse_reg(tok):
    u = tok.strip().upper()
    if u in REG32 and not u.startswith('R'):
        return Reg(32, REG32[u], u)
    if u in REG16:
        return Reg(16, REG16[u], u)
    if u in REG8:
        return Reg(8, REG8[u], u)
    if u in REG32:
        return Reg(32, REG32[u], u)
    return None


def split_operands(s):
    ops, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            ops.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        ops.append(cur.strip())
    return ops


def parse_operand(tok, mnem):
    t = tok.strip()
    if t.startswith('(') and t.endswith(')') and _balanced_outer(t):
        inner = t[1:-1].strip()
        m = re.match(r'^-\s*([A-Za-z0-9\']+)\s*(?::\s*(\d+))?$', inner)
        if m and parse_reg(m.group(1)) and parse_reg(m.group(1)).size == 32:
            return Mem('pre', base=parse_reg(m.group(1)), step=int(m.group(2)) if m.group(2) else None)
        m = re.match(r'^([A-Za-z0-9\']+)\s*\+\s*(?::\s*(\d+))?$', inner)
        if m and parse_reg(m.group(1)) and parse_reg(m.group(1)).size == 32:
            return Mem('post', base=parse_reg(m.group(1)), step=int(m.group(2)) if m.group(2) else None)
        r = parse_reg(inner)
        if r is not None:
            if r.size != 32:
                raise AsmError('memory base must be 32-bit: %s' % t)
            return Mem('r', base=r, disp='0')
        m = re.match(r'^([A-Za-z0-9\']+)\s*([+-])\s*(.+)$', inner)
        if m and parse_reg(m.group(1)) is not None and parse_reg(m.group(1)).size == 32:
            base = parse_reg(m.group(1))
            rest = m.group(3).strip()
            idx = parse_reg(rest)
            if idx is not None and m.group(2) == '+':
                if idx.size == 32:
                    raise AsmError('index register must be 8/16-bit: %s' % t)
                return Mem('rr', base=base, index=idx)
            return Mem('r', base=base, disp=('-(%s)' % rest) if m.group(2) == '-' else rest)
        return Mem('abs', disp=inner)
    if t.startswith('#'):
        t = t[1:]
    r = parse_reg(t)
    if r is not None:
        return r
    if t.upper() in ('SR', 'F', "F'"):
        return t.upper()
    return Imm(t)


def _balanced_outer(t):
    depth = 0
    for i, ch in enumerate(t):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0 and i != len(t) - 1:
                return False
    return True


# ----------------------------------------------------------------------------
# Encoder
# ----------------------------------------------------------------------------

def le(v, n):
    return bytes((v >> (8 * i)) & 0xFF for i in range(n))


class Encoder:
    def __init__(self, symbols, pc, final):
        self.symbols = symbols
        self.pc = pc
        self.final = final

    def val(self, expr):
        try:
            return eval_expr(expr, self.symbols, self.pc)
        except KeyError as e:
            if self.final:
                raise AsmError('undefined symbol %s' % e)
            return 0x7FFFFF   # pessimistic: forces the longest encodings until known

    # ---- memory addressing -------------------------------------------------
    def mem_src_prefix(self, m, size):
        """Prefix bytes for a source-memory operand of the given size (8/16/32)."""
        grp = {8: 0, 16: 1, 32: 2}[size]
        if m.mode == 'r':
            d = self.val(m.disp)
            r3 = R3_16.get(m.base.code)
            if r3 is not None and d == 0:
                return bytes([0x80 + 0x10 * grp + r3])
            if r3 is not None and -128 <= d <= 127:
                return bytes([0x88 + 0x10 * grp + r3, d & 0xFF])
            if d == 0:
                return bytes([0xC3 + 0x10 * grp, m.base.code & ~3])
            return bytes([0xC3 + 0x10 * grp, (m.base.code & ~3) | 1]) + le(d & 0xFFFF, 2)
        raise AsmError('internal: mem_src_prefix only handles (R+d)')

    def mem_dst_prefix(self, m):
        if m.mode == 'r':
            d = self.val(m.disp)
            r3 = R3_16.get(m.base.code)
            if r3 is not None and d == 0:
                return bytes([0xB0 + r3])
            if r3 is not None and -128 <= d <= 127:
                return bytes([0xB8 + r3, d & 0xFF])
            if d == 0:
                return bytes([0xF3, m.base.code & ~3])
            return bytes([0xF3, (m.base.code & ~3) | 1]) + le(d & 0xFFFF, 2)
        raise AsmError('internal: mem_dst_prefix only handles (R+d)')

    def mem_ext_tail(self, m, size):
        """Tail bytes after a C0/D0/E0/F0 group byte; .nib is the low nibble
        to add to the group byte."""
        if m.mode == 'abs':
            a = self.val(m.disp) & 0xFFFFFF
            if a < 0x100:
                return _Ext(0, bytes([a]))
            if a < 0x10000:
                return _Ext(1, le(a, 2))
            return _Ext(2, le(a, 3))
        if m.mode == 'rr':
            code = 0x03 if m.index.size == 8 else 0x07
            return _Ext(3, bytes([code, m.base.code & ~3, m.index.code]))
        if m.mode in ('pre', 'post'):
            step = m.step or (size // 8 if size else 1)
            st = {1: 0, 2: 1, 4: 2}[step]
            return _Ext(4 if m.mode == 'pre' else 5, bytes([(m.base.code & ~3) | st]))
        raise AsmError('bad memory mode')


class _Ext(bytes):
    """Extended addressing tail carrying the low nibble of the prefix byte."""
    def __new__(cls, nib, data):
        o = bytes.__new__(cls, data)
        o.nib = nib
        return o


# ----------------------------------------------------------------------------
# Instruction encoding
# ----------------------------------------------------------------------------

def src_prefix(enc, m, size):
    if m.mode == 'r':
        return enc.mem_src_prefix(m, size)
    grp = {8: 0xC0, 16: 0xD0, 32: 0xE0}[size]
    ext = enc.mem_ext_tail(m, size)
    return bytes([grp + ext.nib]) + bytes(ext)


def dst_prefix(enc, m, size=None):
    """Prefix for a destination memory operand; `size` (access size in bits)
    gives (REG+) and (-REG) their default step."""
    if m.mode == 'r':
        return enc.mem_dst_prefix(m)
    ext = enc.mem_ext_tail(m, size)
    return bytes([0xF0 + ext.nib]) + bytes(ext)


def reg_prefix(r):
    grp = {8: 0xC8, 16: 0xD8, 32: 0xE8}[r.size]
    if r.r3 is not None and (r.size == 8 or r.code in R3_16):
        return bytes([grp + r.r3])
    return bytes([grp - 1, r.code])


def imm_bytes(enc, expr, size):
    v = enc.val(expr)
    return le(v & ((1 << size) - 1), size // 8)


def encode(mnem, size, ops, enc):
    """Returns bytes for one instruction."""
    m = mnem
    n = len(ops)

    def isreg(o, sz=None):
        return isinstance(o, Reg) and (sz is None or o.size == sz)

    def isimm(o):
        return isinstance(o, Imm)

    def ismem(o):
        return isinstance(o, Mem)

    # ---- no-operand -----------------------------------------------------
    simple = {'nop': 0x00, 'halt': 0x05, 'reti': 0x07, 'incf': 0x0C, 'decf': 0x0D, 'rcf': 0x10,
              'scf': 0x11, 'ccf': 0x12, 'zcf': 0x13}
    if m in simple and n == 0:
        return bytes([simple[m]])
    if m == 'ret' and n == 0:
        return b'\x0E'
    if m == 'ret' and n == 1 and isinstance(ops[0], Cond):
        return bytes([0xB0, 0xF0 + ops[0].cc])
    if m == 'retd':
        return b'\x0F' + imm_bytes(enc, ops[0].expr, 16)
    if m == 'di':
        return b'\x06\x07'
    if m == 'ei':
        return bytes([0x06, (enc.val(ops[0].expr) if n else 0) & 7])
    if m == 'ldf':
        return bytes([0x17, enc.val(ops[0].expr) & 3])
    if m == 'swi':
        return bytes([0xF8 + (enc.val(ops[0].expr) & 7)])
    if m == 'exff' or (m == 'ex' and n == 2 and ops[0] == 'F'):
        return b'\x16'

    # ---- block transfers -------------------------------------------------
    if m in ('ldi', 'ldir', 'ldd', 'lddr'):
        sz = size or 8
        base = 0x83 if sz == 8 else 0x93
        if n and isinstance(ops[0], Mem) and ops[0].base and ops[0].base.name == 'XIX':
            base += 2
        return bytes([base, {'ldi': 0x10, 'ldir': 0x11, 'ldd': 0x12, 'lddr': 0x13}[m]])
    if m in ('cpi', 'cpir', 'cpd', 'cpdr'):
        sz = size or 8
        ptr = ops[1] if n == 2 else ops[0]
        r3 = R3_16[ptr.code]
        return bytes([(0x80 if sz == 8 else 0x90) + r3, {'cpi': 0x14, 'cpir': 0x15, 'cpd': 0x16, 'cpdr': 0x17}[m]])

    # ---- control flow ----------------------------------------------------
    if m in ('jp', 'call', 'jr', 'jrl', 'calr'):
        cond = 8
        if n == 2 and isinstance(ops[0], Cond):
            cond = ops[0].cc
            ops = ops[1:]
            n = 1
        tgt = ops[0]
        if m in ('jp', 'call') and ismem(tgt) and tgt.mode != 'abs':
            pre = dst_prefix(enc, tgt)
            return pre + bytes([(0xD0 if m == 'jp' else 0xE0) + cond])
        expr = tgt.expr if isimm(tgt) else tgt.disp
        a = enc.val(expr) & 0xFFFFFF
        if m == 'jr':
            d = a - (enc.pc + 2)
            if enc.final and not -128 <= d <= 127:
                raise AsmError('jr out of range')
            return bytes([0x60 + cond, d & 0xFF])
        if m == 'jrl':
            d = a - (enc.pc + 3)
            return bytes([0x70 + cond]) + le(d & 0xFFFF, 2)
        if m == 'calr':
            d = a - (enc.pc + 3)
            return b'\x1E' + le(d & 0xFFFF, 2)
        if cond == 8:
            if m == 'jp':
                return (b'\x1A' + le(a, 2)) if a < 0x10000 and False else (b'\x1B' + le(a, 3))
            return b'\x1D' + le(a, 3)
        # conditional absolute: dst prefix with (nnn)
        pre = bytes([0xF2]) + le(a, 3)
        return pre + bytes([(0xD0 if m == 'jp' else 0xE0) + cond])
    if m == 'djnz':
        r = ops[0]
        a = enc.val(ops[1].expr)
        pre = reg_prefix(r)
        d = a - (enc.pc + len(pre) + 2)
        if enc.final and not -128 <= d <= 127:
            raise AsmError('djnz out of range')
        return pre + bytes([0x1C, d & 0xFF])

    # ---- push / pop ------------------------------------------------------
    if m in ('push', 'pop'):
        o = ops[0]
        if o == 'SR':
            return b'\x02' if m == 'push' else b'\x03'
        if o == 'F':
            return b'\x18' if m == 'push' else b'\x19'
        if isreg(o):
            if o.size == 8 and o.code == 0xE0:
                return b'\x14' if m == 'push' else b'\x15'
            if o.size in (16, 32) and o.code in R3_16:
                return bytes([(0x28 if m == 'push' else 0x48) + (0x10 if o.size == 32 else 0) + R3_16[o.code]])
            return reg_prefix(o) + bytes([0x04 if m == 'push' else 0x05])
        if isimm(o) and m == 'push':
            sz = size or 16
            if sz == 8:
                return b'\x09' + imm_bytes(enc, o.expr, 8)
            return b'\x0B' + imm_bytes(enc, o.expr, 16)
        if ismem(o):
            sz = size or 8
            if m == 'push':
                return src_prefix(enc, o, sz) + b'\x04'
            return dst_prefix(enc, o, sz) + (b'\x04' if sz == 8 else b'\x06')

    # ---- loads -----------------------------------------------------------
    if m == 'lda' or m == 'ldar':
        r, mm = ops
        if m == 'ldar':
            a = enc.val(mm.disp if ismem(mm) else mm.expr)
            # F3 13 dd dd op : address = (pc+4) + dd
            d = a - (enc.pc + 4)
            return b'\xF3\x13' + le(d & 0xFFFF, 2) + bytes([(0x20 if r.size == 16 else 0x30) + R3_16[r.code]])
        if isimm(mm):
            mm = Mem('abs', disp=mm.expr)
        return dst_prefix(enc, mm) + bytes([(0x20 if r.size == 16 else 0x30) + R3_16[r.code]])
    if m == 'ld':
        dst, src = ops
        if isreg(dst) and isimm(src):
            sz = dst.size
            if dst.r3 is not None and (sz == 8 or dst.code in R3_16):
                if sz == 8:
                    return bytes([0x20 + dst.r3]) + imm_bytes(enc, src.expr, 8)
                if sz == 16:
                    return bytes([0x30 + dst.r3]) + imm_bytes(enc, src.expr, 16)
                return bytes([0x40 + dst.r3]) + imm_bytes(enc, src.expr, 32)
            v = enc.val(src.expr)
            if 0 <= v <= 7 and enc.final is not None:
                return reg_prefix(dst) + bytes([0xA8 + v])
            return reg_prefix(dst) + b'\x03' + imm_bytes(enc, src.expr, sz)
        if isreg(dst) and isreg(src):
            if dst.size != src.size:
                raise AsmError('register size mismatch')
            if dst.r3 is not None and (dst.size == 8 or dst.code in R3_16):
                return reg_prefix(src) + bytes([0x88 + dst.r3])
            if src.r3 is not None and (src.size == 8 or src.code in R3_16):
                return reg_prefix(dst) + bytes([0x98 + src.r3])
            raise AsmError('ld between two extended registers needs a temporary')
        if isreg(dst) and ismem(src):
            if dst.r3 is None or (dst.size > 8 and dst.code not in R3_16):
                raise AsmError('ld r,(mem) needs a current-bank register')
            return src_prefix(enc, src, dst.size) + bytes([0x20 + dst.r3])
        if ismem(dst) and isreg(src):
            if src.r3 is None or (src.size > 8 and src.code not in R3_16):
                raise AsmError('ld (mem),r needs a current-bank register')
            return dst_prefix(enc, dst, src.size) + bytes([{8: 0x40, 16: 0x50, 32: 0x60}[src.size] + src.r3])
        if ismem(dst) and isimm(src):
            sz = size or 8
            if dst.mode == 'abs' and enc.val(dst.disp) < 0x100 and sz in (8, 16):
                a = enc.val(dst.disp)
                return bytes([0x08 if sz == 8 else 0x0A, a]) + imm_bytes(enc, src.expr, sz)
            if sz == 32:
                raise AsmError('no ld.l (mem),#')
            return dst_prefix(enc, dst, sz) + (b'\x00' if sz == 8 else b'\x02') + imm_bytes(enc, src.expr, sz)
        if ismem(dst) and ismem(src):
            sz = size or 8
            if dst.mode == 'abs' and enc.val(dst.disp) < 0x10000:
                return src_prefix(enc, src, sz) + b'\x19' + le(enc.val(dst.disp), 2)
            if src.mode == 'abs' and enc.val(src.disp) < 0x10000:
                return dst_prefix(enc, dst, sz) + (b'\x14' if sz == 8 else b'\x16') + le(enc.val(src.disp), 2)
            raise AsmError('unsupported memory-to-memory ld')
    if m == 'ex':
        a, b = ops
        if isreg(a) and isreg(b):
            if a.r3 is not None:
                return reg_prefix(b) + bytes([0xB8 + a.r3])
            return reg_prefix(a) + bytes([0xB8 + b.r3])
        if ismem(a) and isreg(b):
            return src_prefix(enc, a, b.size) + bytes([0x30 + b.r3])

    # ---- ALU -------------------------------------------------------------
    if m in ALU:
        k = ALU.index(m)
        dst, src = ops
        if isreg(dst) and isimm(src):
            if m == 'cp' and dst.size != 32:
                v = enc.val(src.expr)
                if 0 <= v <= 7:
                    return reg_prefix(dst) + bytes([0xD8 + v])
            return reg_prefix(dst) + bytes([0xC8 + k]) + imm_bytes(enc, src.expr, dst.size)
        if isreg(dst) and isreg(src):
            base = {0: 0x80, 1: 0x90, 2: 0xA0, 3: 0xB0, 4: 0xC0, 5: 0xD0, 6: 0xE0, 7: 0xF0}[k]
            if dst.r3 is not None and (dst.size == 8 or dst.code in R3_16):
                return reg_prefix(src) + bytes([base + dst.r3])
            raise AsmError('ALU destination must be a current-bank register')
        if isreg(dst) and ismem(src):
            return src_prefix(enc, src, dst.size) + bytes([0x80 + 0x10 * k + dst.r3])
        if ismem(dst) and isreg(src):
            return src_prefix(enc, dst, src.size) + bytes([0x88 + 0x10 * k + src.r3])
        if ismem(dst) and isimm(src):
            sz = size or 8
            return src_prefix(enc, dst, sz) + bytes([0x38 + k]) + imm_bytes(enc, src.expr, sz)

    # ---- inc/dec ---------------------------------------------------------
    if m in ('inc', 'dec'):
        if n == 1:
            cnt, tgt = '1', ops[0]
        else:
            cnt, tgt = ops[0].expr, ops[1]
        v = enc.val(cnt)
        if not 1 <= v <= 8:
            raise AsmError('inc/dec count must be 1..8')
        code = (0x60 if m == 'inc' else 0x68) + (v & 7)
        if isreg(tgt):
            return reg_prefix(tgt) + bytes([code])
        return src_prefix(enc, tgt, size or 8) + bytes([code])

    # ---- misc register ops ----------------------------------------------
    one = {'cpl': 0x06, 'neg': 0x07, 'daa': 0x10, 'extz': 0x12, 'exts': 0x13, 'paa': 0x14,
           'mirr': 0x16, 'mula': 0x19, 'unlk': 0x0D}
    if m in one:
        return reg_prefix(ops[-1]) + bytes([one[m]])
    if m == 'link':
        return reg_prefix(ops[0]) + b'\x0C' + imm_bytes(enc, ops[1].expr, 16)
    if m in ('bs1f', 'bs1b'):
        return reg_prefix(ops[1]) + (b'\x0E' if m == 'bs1f' else b'\x0F')
    if m in ('mul', 'muls', 'div', 'divs'):
        k = ('mul', 'muls', 'div', 'divs').index(m)
        dst, src = ops
        # dst may be written as the wide register (e.g. WA for byte ops) or the operand register
        if isreg(dst) and isimm(src):
            r = dst
            sz = size or (8 if r.size == 16 else 16)
            rr = _narrow(r, sz)
            return reg_prefix(rr) + bytes([0x08 + k]) + imm_bytes(enc, src.expr, sz)
        if isreg(dst) and isreg(src):
            sz = src.size
            rr = _narrow(dst, sz)
            return reg_prefix(src) + bytes([0x40 + 8 * k + rr.r3])
        if isreg(dst) and ismem(src):
            sz = size or (8 if dst.size == 16 else 16)
            rr = _narrow(dst, sz)
            return src_prefix(enc, src, sz) + bytes([0x40 + 8 * k + rr.r3])
    if m in ('minc1', 'minc2', 'minc4', 'mdec1', 'mdec2', 'mdec4'):
        code = {'minc1': 0x38, 'minc2': 0x39, 'minc4': 0x3A, 'mdec1': 0x3C, 'mdec2': 0x3D, 'mdec4': 0x3E}[m]
        return reg_prefix(ops[1]) + bytes([code]) + imm_bytes(enc, ops[0].expr, 16)
    if m == 'scc':
        return reg_prefix(ops[1]) + bytes([0x70 + ops[0].cc])
    if m == 'ldc':
        dst, src = ops
        if isreg(src):
            return reg_prefix(src) + b'\x2E' + bytes([enc.val(dst.expr) & 0xFF])
        return reg_prefix(dst) + b'\x2F' + bytes([enc.val(src.expr) & 0xFF])

    # ---- shifts ----------------------------------------------------------
    if m in SHIFTS:
        k = SHIFTS.index(m)
        if n == 1 and ismem(ops[0]):
            return src_prefix(enc, ops[0], size or 8) + bytes([0x78 + k])
        cnt, tgt = (ops[0], ops[1]) if n == 2 else (Imm('1'), ops[0])
        if ismem(tgt):
            if enc.val(cnt.expr) != 1:
                raise AsmError('memory shifts are by 1 only')
            return src_prefix(enc, tgt, size or 8) + bytes([0x78 + k])
        if isreg(cnt) and cnt.code == 0xE0 and cnt.size == 8:
            return reg_prefix(tgt) + bytes([0xF8 + k])
        v = enc.val(cnt.expr) & 15
        return reg_prefix(tgt) + bytes([0xE8 + k, v])

    # ---- bit ops ---------------------------------------------------------
    if m in ('bit', 'set', 'res', 'chg', 'tset'):
        bitn, tgt = ops
        b = enc.val(bitn.expr)
        if isreg(tgt):
            code = {'res': 0x30, 'set': 0x31, 'chg': 0x32, 'bit': 0x33, 'tset': 0x34}[m]
            return reg_prefix(tgt) + bytes([code, b & 15])
        code = {'tset': 0xA8, 'res': 0xB0, 'set': 0xB8, 'chg': 0xC0, 'bit': 0xC8}[m]
        return dst_prefix(enc, tgt, 8) + bytes([code + (b & 7)])
    if m in CFOPS:
        k = CFOPS.index(m)
        bitn, tgt = ops
        if isreg(tgt):
            if isreg(bitn):
                return reg_prefix(tgt) + bytes([0x28 + k])
            return reg_prefix(tgt) + bytes([0x20 + k, enc.val(bitn.expr) & 15])
        if isreg(bitn):
            return dst_prefix(enc, tgt, 8) + bytes([0x28 + k])
        return dst_prefix(enc, tgt, 8) + bytes([0x80 + 8 * k + (enc.val(bitn.expr) & 7)])

    raise AsmError('cannot encode: %s %s' % (mnem, ops))


def _narrow(r, sz):
    """For MUL/DIV the 3-bit register field names the operand register of size
    `sz`: byte ops use A,C,E,L (odd codes of WA,BC,DE,HL); word ops use WA..SP."""
    if r.size == sz:
        return r
    if sz == 8 and r.size == 16:
        low = {0xE0: 0xE0, 0xE4: 0xE4, 0xE8: 0xE8, 0xEC: 0xEC}[r.code]
        return Reg(8, low, r.name)
    if sz == 16 and r.size == 32:
        return Reg(16, r.code, r.name)
    raise AsmError('bad mul/div operand')


# ----------------------------------------------------------------------------
# Assembler driver
# ----------------------------------------------------------------------------

class Section:
    def __init__(self, org):
        self.org = org
        self.data = bytearray()


def _control_register_symbols():
    syms = {}
    for ch in range(4):
        for name, base in (('DMAS', 0x00), ('DMAD', 0x10)):
            c = base + 4 * ch
            syms['%s%d' % (name, ch)] = c
            syms['%s%dL' % (name, ch)] = c
            syms['%s%dH' % (name, ch)] = c + 2
            for b in range(4):
                syms['%s%d.b%d' % (name, ch, b)] = c + b
        syms['DMAC%d' % ch] = 0x20 + 4 * ch
        syms['DMAM%d' % ch] = 0x22 + 4 * ch
        for b in range(4):
            syms['DMAC%d.b%d' % (ch, b)] = 0x20 + 4 * ch + b
    syms['INTNEST'] = 0x3C
    return syms


CONTROL_REGISTERS = _control_register_symbols()


class Assembler:
    def __init__(self, symbols=None):
        self.symbols = dict(CONTROL_REGISTERS)
        self.symbols.update(symbols or {})
        self.lines = []

    def load(self, path):
        base = os.path.dirname(path)
        with open(path, encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                s = line.split(';', 1)[0].rstrip()
                m = re.match(r'^\s*\.include\s+"([^"]+)"', s)
                if m:
                    self.load(os.path.join(base, m.group(1)))
                    continue
                self.lines.append((path, i, s))

    def add_source(self, text, name='<src>'):
        for i, line in enumerate(text.splitlines(), 1):
            self.lines.append((name, i, line.split(';', 1)[0].rstrip()))

    def assemble(self):
        """Repeats passes until label values are stable, then a final pass
        with verification. Returns list of (org, bytes) chunks."""
        prev = None
        for _ in range(12):
            self._pass(False)
            snap = dict(self.symbols)
            if snap == prev:
                break
            prev = snap
        else:
            raise AsmError('symbol values did not converge')
        return self._pass(True)

    def _pass(self, final):
        for final in (final,):
            sections = []
            cur = None
            pc = 0
            for (fname, lineno, s) in self.lines:
                self.cur_file = fname
                try:
                    if not s.strip():
                        continue
                    m = re.match(r'^\s*([A-Za-z_.][A-Za-z0-9_.]*)\s*:(.*)$', s)
                    if m:
                        self.symbols[m.group(1)] = pc
                        s = m.group(2)
                        if not s.strip():
                            continue
                    m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.+)$', s)
                    if m:
                        try:
                            self.symbols[m.group(1)] = eval_expr(m.group(2), self.symbols, pc)
                        except KeyError:
                            if final:
                                raise
                        continue
                    s = s.strip()
                    parts = s.split(None, 1)
                    op = parts[0].lower()
                    rest = parts[1] if len(parts) > 1 else ''
                    if op == '.org':
                        pc = eval_expr(rest, self.symbols, pc)
                        cur = Section(pc)
                        sections.append(cur)
                        continue
                    if cur is None:
                        raise AsmError('code before .org')
                    data = self.directive(op, rest, pc, final) if op.startswith('.') else \
                        self.instruction(op, rest, pc, final)
                    cur.data += data
                    pc += len(data)
                except AsmError as e:
                    raise AsmError('%s:%d: %s\n    %s' % (fname, lineno, e, s))
                except KeyError as e:
                    if final:
                        raise AsmError('%s:%d: undefined symbol %s' % (fname, lineno, e))
        return [(s.org, bytes(s.data)) for s in sections]

    def directive(self, op, rest, pc, final):
        def v(e):
            try:
                return eval_expr(e, self.symbols, pc)
            except KeyError:
                if final:
                    raise
                return 0
        if op == '.db':
            out = bytearray()
            for item in _split_data(rest):
                if item.startswith('"'):
                    out += item[1:-1].encode('latin-1')
                else:
                    out.append(v(item) & 0xFF)
            return bytes(out)
        if op in ('.dw', '.d24', '.dl'):
            n = {'.dw': 2, '.d24': 3, '.dl': 4}[op]
            return b''.join(le(v(x) & ((1 << (8 * n)) - 1), n) for x in _split_data(rest))
        if op == '.fill':
            args = _split_data(rest)
            return bytes([v(args[1]) & 0xFF if len(args) > 1 else 0]) * v(args[0])
        if op == '.align':
            a = v(rest)
            return b'\xFF' * ((-pc) % a)
        if op == '.incbin':
            path = rest.strip().strip('"')
            if not os.path.isabs(path):
                path = os.path.join(os.path.dirname(self.cur_file), path)
            with open(path, 'rb') as f:
                return f.read()
        raise AsmError('unknown directive %s' % op)

    def instruction(self, op, rest, pc, final):
        mnem, size = op, 0
        if '.' in op:
            mnem, suf = op.split('.', 1)
            size = SIZES[suf]
        raw = split_operands(rest) if rest.strip() else []
        ops = []
        for i, o in enumerate(raw):
            cond_slot = (mnem in ('jr', 'jrl', 'jp', 'call') and len(raw) == 2 and i == 0) or                         (mnem in ('ret', 'scc') and i == 0)
            if cond_slot and o.strip().upper() in COND:
                ops.append(Cond(COND[o.strip().upper()]))
            else:
                ops.append(parse_operand(o, mnem))
        if not size:
            for o in ops:
                if isinstance(o, Reg) and mnem not in ('ldc', 'djnz') and not (
                        mnem in SHIFTS + ('mul', 'muls', 'div', 'divs') and o is ops[0] and len(ops) == 2):
                    size = o.size
                    break
        enc = Encoder(self.symbols, pc, final)
        data = encode(mnem, size, ops, enc)
        if final:
            self.verify(data, pc)
        return data

    def verify(self, data, pc):
        buf = bytes(data) + b'\x00' * 8

        def rd(a):
            return buf[a - pc] if 0 <= a - pc < len(buf) else 0
        try:
            ins = decode(rd, pc)
        except DecodeError as e:
            raise AsmError('encoder produced undecodable bytes %s: %s' % (data.hex(' '), e))
        if ins.length != len(data):
            raise AsmError('encoder length mismatch: %s decodes as %s' % (data.hex(' '), ins.text()))


def _split_data(s):
    out, cur, q = [], '', False
    for ch in s:
        if ch == '"':
            q = not q
        if ch == ',' and not q:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def assemble_text(text, symbols=None):
    a = Assembler(symbols)
    a.add_source(text)
    return a.assemble(), a.symbols


if __name__ == '__main__':
    a = Assembler()
    a.load(sys.argv[1])
    for org, data in a.assemble():
        print('%06X: %s' % (org, data.hex(' ')))
