"""Dump raw (non-bytecode) text in a ROM range for review.

Usage: python -m tools.text.rawdump rom/baserom.ngc LO-HI [LO-HI ...]

Splits the range into window-format strings ('00' new line, '00 00' end,
'01' space) and prints each with its address, byte length (including the
terminating '00 00'), the widest line in cells, the number of 24-bit
references to its first byte found anywhere in the ROM, and the text.
Bytes that are not text codes are shown as <XX>.
"""
import sys

from ..recomp.rom import Rom, ROM_BASE
from .charmap import DECODE


def ref_counts(rom, addrs):
    want = {a: 0 for a in addrs}
    d = rom.data
    for off in range(len(d) - 2):
        v = d[off] | (d[off + 1] << 8) | (d[off + 2] << 16)
        if v in want:
            want[v] += 1
    return want


def split_strings(rom, lo, hi):
    """[(addr, raw bytes incl. terminator)] for lo <= addr < hi."""
    out = []
    a = lo
    while a < hi:
        start = a
        while a < hi and not (rom.read8(a) == 0 and rom.read8(a + 1) == 0):
            a += 1
        a = min(a + 2, hi)
        out.append((start, rom.bytes(start, a - start)))
    return out


def render(bs):
    s = []
    for i, b in enumerate(bs):
        if b == 0:
            if i + 1 < len(bs) and bs[i + 1] == 0:
                break
            s.append('⏎')
        elif b == 1:
            s.append('·')
        else:
            s.append(DECODE.get(b, '<%02X>' % b))
    return ''.join(s)


def widest_line(bs):
    body = bs[:-2] if bs.endswith(b'\x00\x00') else bs
    return max((len(line) for line in body.split(b'\x00')), default=0)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rom = Rom(sys.argv[1])
    ranges = []
    for r in sys.argv[2:]:
        lo, hi = (int(x, 16) for x in r.split('-'))
        ranges.append((lo, hi))
    pieces = [p for lo, hi in ranges for p in split_strings(rom, lo, hi)]
    refs = ref_counts(rom, [a for a, _ in pieces])
    for a, bs in pieces:
        print('%06X len=%3d w=%2d refs=%d  %s' % (a, len(bs), widest_line(bs), refs[a], render(bs)))


if __name__ == '__main__':
    main()
