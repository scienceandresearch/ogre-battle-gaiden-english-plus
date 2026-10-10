"""Summarise a harness --text-log: strings drawn by the UI text renderers.

Usage: python -m tools.text.textlog LOG [--en]

Each log line is
  FRAME RENDERER src=ADDR caller=ADDR ix=MAP iz=TILE HEXBYTES
where RENDERER is 'window' (0x200BAC) or 'uiprint' (0x200B72). Strings are
decoded with the Japanese table (or the English one with --en); RAM sources
(the 0x6000 composition buffer) are listed with their caller so the code that
composed them can be found.
"""
import sys

from .charmap import DECODE


def decode_window(bs, table):
    out = []
    for i, b in enumerate(bs):
        if b == 0:
            if i + 1 < len(bs) and bs[i + 1] == 0:
                break
            out.append('⏎')
        elif b == 1:
            out.append(' ')
        else:
            out.append(table.get(b, '<%02X>' % b))
    return ''.join(out)


def parse(path):
    rows = []
    with open(path, encoding='ascii', errors='replace') as f:
        for line in f:
            parts = line.split()
            if len(parts) < 7:
                continue
            frame, kind = int(parts[0]), parts[1]
            kv = dict(p.split('=') for p in parts[2:6])
            data = bytes.fromhex(parts[6]) if len(parts) > 6 else b''
            rows.append((frame, kind, int(kv['src'], 16), int(kv['caller'], 16),
                         int(kv['ix'], 16), int(kv['iz'], 16), data))
    return rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    table = DECODE
    if '--en' in sys.argv:
        from .encoding_en import DECODE as table
    rows = parse(sys.argv[1])
    for frame, kind, src, caller, ix, iz, data in rows:
        where = 'ROM' if src >= 0x200000 else 'RAM'
        print('%6d %-7s %s %06X  caller %06X  map %04X tile %03X  %s' % (
            frame, kind, where, src, caller, ix, iz, decode_window(data, table)))


if __name__ == '__main__':
    main()
