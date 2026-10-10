"""Location names (towns, castles, forts, temples) of every stage.

The stage table (STAGE_TABLE, NUM_STAGES records of 18 bytes) gives for each
stage the address of its event table (+0, 24 bits); the byte at +3 is the
offset from there to the stage's location table and the word at +4 its size
(1 + 16 * count). While a stage is loaded the game keeps the location table
address in RAM at 0x608E.

    location table:  [count] then count 16-byte records
    record:          +0 town type (0 = none, 1-8 = index into the town-type
                        names at 0x273334)
                     +1 name, 8 cells padded with 0x01
                     +9 flag, +10 u16 population, +12/+13 ratings, +14 x, +15 y

The game shows a name in two places, both handled by patch/src/locname.asm:
the town window (8-cell name field) and the liberated / discovered / lost
messages ("<town type><name> was liberated." etc.). English names are longer
than 8 cells, so the patch takes them from a table built here and draws them
with the variable-width font; the 8-cell field in each record still gets the
English name (cut to 8 characters) for any other reader.

translation/en/locations.txt:

    @types              town-type phrases that open the messages
    1	The fortress city of
    @stage 0            one line per record: INDEX<TAB>English name
    0	Estoa

Lines starting with '#' are comments.
"""
import os
import struct

from ..recomp.rom import ROM_BASE

STAGE_TABLE = 0x2261D9
NUM_STAGES = 20
NUM_TYPES = 9
NAME_CELLS = 8
NAME_WIDTH = 64          # pixels: the town window's 8-cell name row
MSG_WIDTH = 144          # pixels: system message window (18 cells)
MSG_TILES = 36           # tiles a system message may use (the original "lost"
                         # message with a long type and name used more)


class LocationError(Exception):
    pass


def _r8(base, a):
    return base[a - ROM_BASE]


def _r16(base, a):
    o = a - ROM_BASE
    return base[o] | (base[o + 1] << 8)


def _r24(base, a):
    o = a - ROM_BASE
    return base[o] | (base[o + 1] << 8) | (base[o + 2] << 16)


def location_records(base):
    """[(stage, index, record address)] for every location of every stage."""
    out = []
    for stage in range(NUM_STAGES):
        rec = STAGE_TABLE + 18 * stage
        table = _r24(base, rec) + _r8(base, rec + 3)
        size = _r16(base, rec + 4)
        count = _r8(base, table)
        if size != 1 + 16 * count:
            raise LocationError('stage %d: location table %06X has %d records but size %d'
                                % (stage, table, count, size))
        for i in range(count):
            out.append((stage, i, table + 1 + 16 * i))
    return out


def record_name(base, addr):
    """The original 8-cell name bytes (without the 0x01 padding)."""
    o = addr + 1 - ROM_BASE
    return bytes(base[o:o + NAME_CELLS]).rstrip(b'\x01')


def record_type(base, addr):
    return _r8(base, addr)


def read_locations(path):
    """{'types': {k: (text, line)}, 'names': {(stage, index): (text, line)}}"""
    types, names = {}, {}
    section = None
    with open(path, encoding='utf-8') as f:
        for n, raw in enumerate(f, 1):
            line = raw.rstrip('\r\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            if line.startswith('@'):
                words = line[1:].split()
                if words == ['types']:
                    section = 'types'
                elif len(words) == 2 and words[0] == 'stage':
                    section = int(words[1])
                else:
                    raise LocationError('%s:%d: unknown section %r' % (path, n, line))
                continue
            if section is None or '\t' not in line:
                raise LocationError('%s:%d: expected INDEX<TAB>TEXT inside a section' % (path, n))
            idx, text = line.split('\t', 1)
            key = int(idx) if section == 'types' else (section, int(idx))
            target = types if section == 'types' else names
            if key in target:
                raise LocationError('%s:%d: %r listed twice' % (path, n, key))
            target[key] = (text, n)
    return {'types': types, 'names': names}


def check_locations(base, data, path='locations.txt'):
    """Every record named, every name fits the town window, every message fits."""
    from .layout import text_width
    recs = location_records(base)
    known = {(s, i) for s, i, _ in recs}
    for key, (text, n) in data['names'].items():
        if key not in known:
            raise LocationError('%s:%d: stage %d has no location %d' % (path, n, key[0], key[1]))
    missing = [k for k in sorted(known) if k not in data['names']]
    if missing:
        raise LocationError('%s: no English name for %s' % (
            path, ', '.join('stage %d #%d' % k for k in missing[:8])))
    for k in data['types']:
        if not 0 <= k < NUM_TYPES:
            raise LocationError('%s:%d: town type %d out of range' % (path, data['types'][k][1], k))
    suffix_tiles = 13       # longest message ending ("has fallen to the enemy.")
    for (s, i), (text, n) in data['names'].items():
        w = text_width(text)
        if w > NAME_WIDTH:
            raise LocationError('%s:%d: %r is %d px wide, the town window has %d'
                                % (path, n, text, w, NAME_WIDTH))
    for s, i, addr in recs:
        t = record_type(base, addr)
        name = data['names'][(s, i)][0]
        phrase = data['types'].get(t, ('', 0))[0] if t else ''
        tiles = (text_width(name) + 7) // 8 + suffix_tiles
        if phrase:
            pw = text_width(phrase)
            if pw > MSG_WIDTH:
                raise LocationError('%s: type phrase %r is %d px, at most %d' % (path, phrase, pw, MSG_WIDTH))
            tiles += (pw + 7) // 8
        if tiles > MSG_TILES:
            raise LocationError('%s:%d: messages about %r would need %d tiles, at most %d'
                                % (path, data['names'][(s, i)][1], name, tiles, MSG_TILES))
    return recs


def build_locations(base, rom, path, start, end, sym_out):
    """Write the English names into the records (8 cells) and the full names,
    type phrases and lookup table at start; write the assembler symbols."""
    from .uitext import encode_ui
    data = read_locations(path)
    recs = check_locations(base, data, path)
    blob = bytearray()

    def put(bs):
        a = start + len(blob)
        blob.extend(bs)
        return a

    types = []
    for k in range(NUM_TYPES):
        text = data['types'].get(k, ('', 0))[0]
        types.append(put(encode_ui(text) + b'\x00\x00'))
    entries = []
    for s, i, addr in recs:
        text, n = data['names'][(s, i)]
        enc = encode_ui(text)
        if 0 in enc or 1 in enc[:1]:
            raise LocationError('%s:%d: %r: names cannot contain new lines or start with a space'
                                % (path, n, text))
        entries.append((addr, put(enc + b'\x00\x00')))
        field = enc[:NAME_CELLS]
        o = addr + 1 - ROM_BASE
        rom[o:o + NAME_CELLS] = field + b'\x01' * (NAME_CELLS - len(field))
    if len(blob) % 4:
        put(b'\x00' * (4 - len(blob) % 4))
    types_addr = put(b''.join(struct.pack('<I', a) for a in types))
    table_addr = put(b''.join(struct.pack('<II', a, p) for a, p in sorted(entries)) + b'\x00' * 8)
    if start + len(blob) > end:
        raise LocationError('out of space for location names')
    o = start - ROM_BASE
    if any(b != 0xFF for b in base[o:o + len(blob)]):
        raise LocationError('location data area %06X is not free' % start)
    rom[o:o + len(blob)] = blob
    os.makedirs(os.path.dirname(sym_out), exist_ok=True)
    with open(sym_out, 'w') as f:
        f.write('; generated from translation/en/locations.txt\n')
        f.write('loc_types = 0x%06X\nloc_table = 0x%06X\n' % (types_addr, table_addr))
    return {'names': len(entries), 'bytes': len(blob), 'end': start + len(blob)}
