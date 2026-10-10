"""Insert translated dialogue into the ROM.

Every original message instruction (opcode 0x32 + text + terminator) that has
a translation is replaced in place by a script jump (0xDA + 24-bit address;
the VM reads one more byte and ignores it) to a fragment in free space:

    0x32 <page 1> 0xFE        (intermediate pages wait for a button press)
    0x32 <page 2> 0xFE
    0x32 <last page> <original terminator>
    0xDA <address after the original message> 0x00

so the original control flow, button waits and choice prompts are kept.
Messages shorter than the 4-byte jump (e.g. a lone "…") are rewritten in
place instead and must fit in the original length.
"""
from ..recomp.rom import ROM_BASE
from .script import decode_script
from .encoding_en import encode
from .layout import paginate, TAG_WIDTH, line_width_for

BUFFER_CAPACITY = 120     # bytes of text that fit in the 0x6000 message buffer
YESNO_TERM = 0xFC         # yes/no question: the game draws "Yes No" on the window's third line


class InsertError(Exception):
    pass


class Allocator:
    def __init__(self, start, end):
        self.ptr = start
        self.end = end

    def alloc(self, n):
        a = self.ptr
        if a + n > self.end:
            raise InsertError('out of free space for text')
        self.ptr += n
        return a


def read_translations(path):
    """Parse a translation file: '@ADDR' then text lines; blank line ends an entry.
    Lines starting with '#' are comments."""
    entries = {}
    cur, lines = None, []
    with open(path, encoding='utf-8') as f:
        raw_lines = f.read().split('\n')
    for raw in raw_lines + ['']:
        line = raw.rstrip('\r')
        if line.startswith('#'):
            continue
        if line.startswith('@'):
            cur, lines = int(line[1:].split()[0], 16), []
            continue
        if line.strip() == '' and cur is not None:
            if lines:
                entries[cur] = '\n'.join(lines)
            cur = None
            continue
        if cur is not None:
            lines.append(line)
    return entries


def build_fragment(text, term, ret_addr, width=None):
    pages = paginate(text, width) if width else paginate(text)
    if term == YESNO_TERM and len(pages[-1]) > 2:
        raise InsertError('yes/no question: its last page has %d lines, but the game draws the '
                          'Yes/No choice on the third line; keep that page to 2 lines' % len(pages[-1]))
    frag = bytearray()
    for i, page in enumerate(pages):
        body = encode('\n'.join(page))
        expanded = len(body) + body.count(0xDD) * 9 + body.count(0xDE) * 5
        if expanded > BUFFER_CAPACITY:
            raise InsertError('page too long for the message buffer (%d bytes)' % expanded)
        last = i == len(pages) - 1
        frag += bytes([0x32]) + body + bytes([term if last else 0xFE])
    frag += bytes([0xDA, ret_addr & 0xFF, (ret_addr >> 8) & 0xFF, ret_addr >> 16, 0x00])
    return frag, len(pages)


def insert_dialogue(base, rom, translations, alloc, log=None):
    """base: original ROM bytes (for decoding); rom: bytearray being patched."""
    class _View:
        def __init__(self, data):
            self.data = data

        def read8(self, a):
            return self.data[a - ROM_BASE]

        def read16(self, a):
            return self.read8(a) | (self.read8(a + 1) << 8)

        def read24(self, a):
            return self.read16(a) | (self.read8(a + 2) << 16)

        def read32(self, a):
            return self.read16(a) | (self.read16(a + 2) << 16)

        def bytes(self, a, n):
            return self.data[a - ROM_BASE:a - ROM_BASE + n]

        def contains(self, a):
            return 0 <= a - ROM_BASE < len(self.data)

    view = _View(base)
    stats = {'messages': 0, 'pages': 0, 'bytes': 0}
    for addr, text in sorted(translations.items()):
        ins = decode_script(view, addr)
        if ins.op != 0x32 or ins.text is None:
            raise InsertError('%06X is not a message instruction' % addr)
        if ins.length < 4:
            # too short for a 4-byte jump: rewrite in place, padded with
            # trailing spaces so the next instruction stays where it was
            body = encode(text)
            if 0x00 in body or len(body) > len(ins.text):
                raise InsertError('%06X: message too short to relocate (%d bytes) and the '
                                  'English does not fit in place' % (addr, ins.length))
            body = body + bytes([0x01]) * (len(ins.text) - len(body))
            rom[addr - ROM_BASE:ins.next - ROM_BASE] = bytes([0x32]) + body + bytes([ins.term])
            stats['messages'] += 1
            stats['pages'] += 1
            continue
        try:
            frag, npages = build_fragment(text, ins.term, ins.next, line_width_for(addr))
        except (InsertError, ValueError) as e:
            raise InsertError('%06X: %s' % (addr, e))
        f = alloc.alloc(len(frag))
        rom[f - ROM_BASE:f - ROM_BASE + len(frag)] = frag
        jump = bytes([0xDA, f & 0xFF, (f >> 8) & 0xFF, f >> 16])
        rom[addr - ROM_BASE:addr - ROM_BASE + 4] = jump
        stats['messages'] += 1
        stats['pages'] += npages
        stats['bytes'] += len(frag)
    return stats
