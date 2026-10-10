"""Inventory of menu/window (UI) strings for translators.

Usage: python -m tools.text.uiscan rom/baserom.ngc [build/ui_ja.txt]

Collects raw (non-bytecode) strings that the program references:
  * 24-bit immediates in native code (ld/lda of a register) pointing at text,
  * message pointers stored by scripts (stv32 <ptr>, var 0x20),
  * known tables (see TABLES).
For each reference the following instructions are inspected to guess how the
string is used:
  sysmsg   stored to task+32 and shown by the message routine (0x202FA1)
  window   drawn by 0x200BAC        uiprint  drawn by 0x200B72
  copy N   copied with a fixed length N (composed into a RAM buffer)
The output (local only, it contains the Japanese text) lists each string with
its address, byte length, line count, widest line, character (tile) count,
references and usage, followed by the text. Entries already present in
translation/en/ui.txt are marked [done].
"""
import os
import sys

from ..recomp.rom import Rom, ROM_BASE
from ..recomp.tlcs900 import decode, DecodeError, Imm, Mem, Reg
from .charmap import DECODE
from .extract import build_walker
from .textscore import TextScorer
from .rawdump import render

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# (name, base, stride, count) of fixed-width name tables (8 chars + 00 00)
TABLES = []


def window_string(rom, a, maxlen=400):
    """Bytes of the window-format string at a (incl. 00 00), or None."""
    out = bytearray()
    for i in range(maxlen):
        if not rom.contains(a + i):
            return None
        b = rom.read8(a + i)
        if b >= 0xDF:
            return None
        out.append(b)
        if b == 0 and len(out) >= 2 and out[-2] == 0:
            return bytes(out)
    return None


def plausible(scorer, bs, drawn=False):
    """Text-like window string. `drawn`: the code visibly hands it to a
    renderer, so any valid codes are accepted (Latin text scores low)."""
    if bs is None or len(bs) < 3:
        return False
    body = bs[:-2]
    if not body or body[0] == 0:
        return False
    chars = bytes(b for b in body if b not in (0, 1))
    if not chars or any(b not in DECODE and b not in (0xDD, 0xDE) for b in chars):
        return False
    if drawn:
        return True
    if len(chars) <= 2:
        return scorer.logprob(chars) > 1.0
    return scorer.logprob(chars) > 0.6


def usage_after(rom, a, limit=10):
    """Guess what the code does with a pointer loaded by the instruction at a."""
    try:
        ins = decode(rom.read8, a)
    except DecodeError:
        return '?'
    p = ins.next
    for _ in range(limit):
        try:
            ins = decode(rom.read8, p)
        except DecodeError:
            return '?'
        t = str(ins)
        if '(XIY+32)' in t and ins.mnem == 'ld':
            return 'sysmsg'
        # message pointer of task k stored directly: 0x4086 + 0x38*k + 0x20
        if ins.mnem == 'ld' and ins.ops and isinstance(ins.ops[0], Mem) and ins.ops[0].mode == 'abs' \
                and 0x4086 <= ins.ops[0].disp < 0x4086 + 0x38 * 16 \
                and (ins.ops[0].disp - 0x4086) % 0x38 == 0x20:
            return 'sysmsg'
        if ins.kind == 'call' and ins.target == 0x200BAC:
            return 'window'
        if ins.kind == 'call' and ins.target == 0x200B72:
            return 'uiprint'
        if ins.mnem.startswith('ldir'):
            return 'copy'
        if ins.mnem == 'ld' and len(ins.ops) == 2 and isinstance(ins.ops[0], Reg) and \
                ins.ops[0].size in (8, 16) and repr(ins.ops[0]) in ('BC', 'C') and isinstance(ins.ops[1], Imm):
            return 'copy %d' % ins.ops[1].value
        if ins.kind in ('ret', 'jump') and ins.cond is None:
            return 'jump'
        p = ins.next
    return ''


def code_refs(rom, w, scorer):
    """{string address: [(site, instruction text, usage)]}"""
    refs = {}
    d = rom.data
    for off in range(len(d) - 2):
        v = d[off] | (d[off + 1] << 8) | (d[off + 2] << 16)
        if not (0x200000 <= v < 0x380000):
            continue
        a = ROM_BASE + off
        if a in w.cover:
            continue
        bs = window_string(rom, v)
        if bs is None or not plausible(scorer, bs, drawn=True):
            continue
        for back in range(1, 3):
            try:
                ins = decode(rom.read8, a - back)
            except DecodeError:
                continue
            if ins.next not in (a + 3, a + 4) or ins.mnem not in ('ld', 'lda'):
                continue
            if not ins.ops or not isinstance(ins.ops[0], Reg) or ins.ops[0].size != 32:
                continue
            src = ins.ops[1]
            if (isinstance(src, Imm) and (src.value & 0xFFFFFF) == v and src.value >> 24 == 0) or \
                    (isinstance(src, Mem) and src.mode == 'abs' and src.disp == v and ins.mnem == 'lda'):
                txt = str(ins).split(': ', 1)[1][21:].strip()
                use = usage_after(rom, ins.addr)
                drawn = use in ('window', 'uiprint', 'sysmsg') or use.startswith('copy')
                if plausible(scorer, bs, drawn):
                    refs.setdefault(v, []).append((ins.addr, txt, use))
                break
    return refs


def script_refs(rom, w, scorer=None):
    """Message pointers set by scripts (stv32 <ptr>, var 0x20): the walked
    scripts, plus a byte-pattern scan (9C p0 p1 p2 00 20) for scripts the
    walker does not reach (e.g. bytecode entered from native code)."""
    refs = {}
    for a, i in w.script.items():
        if i.op == 0x9C and i.args[1] == 0x20 and 0x200000 <= i.args[0] < 0x400000:
            v = i.args[0] & 0xFFFFFF
            if window_string(rom, v) is not None:
                refs.setdefault(v, []).append((a, 'stv32 var 0x20', 'sysmsg'))
        elif i.op == 0x8A and i.args[1] in TASK_MSG_VARS and 0x200000 <= i.args[0] < 0x400000:
            v = i.args[0] & 0xFFFFFF
            if window_string(rom, v) is not None:
                refs.setdefault(v, []).append((a, 'st32 (0x%04X)' % i.args[1], 'sysmsg'))
    if scorer is not None:
        d = rom.data
        for op, tails in ((0x9C, (b'\x00\x20',)),
                          (0x8A, tuple(b'\x00' + bytes([t & 0xFF, t >> 8]) for t in TASK_MSG_VARS))):
            i = d.find(bytes([op]))
            while i >= 0:
                if any(d[i + 4:i + 4 + len(t)] == t for t in tails) and ROM_BASE + i not in w.script:
                    v = d[i + 1] | (d[i + 2] << 8) | (d[i + 3] << 16)
                    if 0x200000 <= v < 0x380000 and plausible(scorer, window_string(rom, v)):
                        refs.setdefault(v, []).append((ROM_BASE + i, '%s (scan)' % (
                            'stv32 var 0x20' if op == 0x9C else 'st32 task+32'), 'sysmsg'))
                i = d.find(bytes([op]), i + 1)
    return refs


# Message pointer fields (task+32) of the three map tasks, written with st32.
TASK_MSG_VARS = (0x40A6, 0x40DE, 0x4116)


def shape(bs):
    body = bs[:-2]
    lines = body.split(b'\x00')
    return len(lines), max(len(l) for l in lines), sum(1 for b in body if b not in (0, 1))


def done_addresses():
    path = os.path.join(ROOT, 'translation', 'en', 'ui.txt')
    out = set()
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            if line.startswith('@') and not line.startswith('@='):
                out.add(int(line[1:].split()[0], 16))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rom = Rom(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'build', 'ui_ja.txt')
    w = build_walker(rom, log=lambda *a: None)
    scorer = TextScorer([i.text for _, i in w.strings()])
    refs = code_refs(rom, w, scorer)
    for v, l in script_refs(rom, w, scorer).items():
        refs.setdefault(v, []).extend(l)
    done = done_addresses()
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# UI strings referenced by the program (local only; never commit).\n')
        f.write('# %d strings. usage: sysmsg/window/uiprint/copy N (see tools/text/uiscan.py)\n\n'
                % len(refs))
        for v in sorted(refs):
            bs = window_string(rom, v)
            n, wd, ch = shape(bs)
            sites = ' '.join('%06X:%s%s' % (s, t.split(',')[0], '[%s]' % u if u else '') for s, t, u in refs[v][:4])
            f.write('@%06X len=%d lines=%d width=%d chars=%d%s  refs %s\n' % (
                v, len(bs), n, wd, ch, ' [done]' if v in done else '', sites))
            f.write(render(bs).replace('⏎', '\n') + '\n\n')
    print('wrote %d UI strings to %s (%d already in ui.txt)' % (
        len(refs), out, sum(1 for v in refs if v in done)))


if __name__ == '__main__':
    main()
