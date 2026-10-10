"""In-place text replacement used for early renderer tests.

File format (UTF-8):
    @2995D9                  address of a text opcode (0x32)
    English text...          lines joined with newlines
    (blank line ends the entry)

The English text is padded with spaces to the original string's exact length
so that the following bytecode is untouched.
"""
from ..recomp.rom import ROM_BASE
from ..text.encoding_en import encode


def read_entries(path):
    entries, cur, lines = [], None, []
    with open(path, encoding='utf-8') as f:
        for raw in f.read().splitlines() + ['']:
            if raw.startswith('@'):
                cur, lines = int(raw[1:].split()[0], 16), []
            elif raw.strip() == '' and cur is not None:
                entries.append((cur, '\n'.join(lines)))
                cur = None
            elif cur is not None:
                lines.append(raw)
    return entries


def apply_inplace(rom, path):
    n = 0
    for addr, text in read_entries(path):
        off = addr - ROM_BASE
        if rom[off] != 0x32:
            raise SystemExit('%06X is not a text opcode' % addr)
        end = off + 1
        while rom[end] < 0xDF:
            end += 1
        room = end - (off + 1)
        data = encode(text)
        if len(data) > room:
            raise SystemExit('%06X: English text is %d bytes, room for %d' % (addr, len(data), room))
        data += bytes([0x01]) * (room - len(data))
        rom[off + 1:end] = data
        n += 1
    return n
