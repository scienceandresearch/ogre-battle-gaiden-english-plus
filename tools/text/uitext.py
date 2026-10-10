"""Menu / window (UI) text insertion.

translation/en/ui.txt holds entries like

    @202E67 vwf
    This character
    can't be deleted.

The header is '@ADDR' (ROM address of the original string) followed by
optional words:
    fixed      (default) remapped, drawn with the fixed-cell 8x8 font
    vwf        remapped, drawn with the variable-width font (window
               renderer 0x200BAC only)
    uiprint    fixed cells drawn by the tile-mapped printer 0x200B72, which
               maps codes to a preloaded font (no per-string tile budget)
    sysmsg     vwf in the 18 x 3 message window (system messages shown by
               0x202FA1): width=18 lines=3, tile budget max(original, 36)
               (a Yes/No prompt's tiles start 36 tiles after the text's)
    inplace    written over the original bytes (must fit)
    width=N    maximum cells per line   (default: the original's widest line)
    lines=N    maximum number of lines  (default: the original's line count)
    tiles=N    tile budget              (default: the original's character count)
    len=N      in-place only: exact byte span to overwrite (for fragments that
               the game copies with a fixed length and no terminator)
    fixedwidth in-place only: pad with spaces up to the original text length
               and keep the 00 00 terminator in its place (fixed-width name
               tables that code copies by length)
    fill=N     vwf only: pad each line with the blank glyph {DC} to just
               under N cells, so a fixed field is fully redrawn (no stale
               cells from a longer previous label); 'center' centres it
    cells=N    the string is also drawn by a fixed-cell printer somewhere
               (e.g. the organize screen prints system messages with the
               tile-mapped printer, 18 cells a line): every line must have
               at most N characters
An address may have one in-place entry and one remapped entry: the remapped
text is drawn when the renderer gets the original pointer, the in-place text
wherever the game copies the bytes.

Each following line of the entry is one display line; a blank line ends the
entry. Leading/trailing spaces are kept (use them for alignment). {XX} inserts
the raw byte XX (e.g. {DC}, the blank glyph that takes a tile, which the
name-entry grid uses as a selectable space).

'@=SYMBOL [noterm] [solid] [orig=ADDR[:LEN]]' defines a new string for code
patches instead: it is placed in free ROM and patch/main.asm can use SYMBOL
(address) and SYMBOL_LEN (bytes, including the 00 00 terminator unless
'noterm'). 'orig' names the original text the string replaces (LEN bytes at
ADDR, or the terminated string there) for the localization database.
A named string may contain one {FF}: the place where code inserts a name or
a number (patch/src/msgcompose.asm copies the head up to it); it then also
defines SYMBOL_HEAD (bytes up to and including {FF}), SYMBOL_TAIL (bytes
after it) and SYMBOL_TAILPTR (address of the tail).

'solid' (any fixed-cell entry): spaces are encoded as {DC} so they draw a
blank tile. The fixed-cell renderer leaves the map cell of an ordinary space
untouched, which shows stale glyphs in windows that are not cleared first.

Remapped strings are placed in free ROM and listed in a table that the hooks
in patch/src/uitext.asm search at run time (see there for the format), so
they work however the game computes the pointer.
"""
import os
import struct

from ..recomp.rom import ROM_BASE
from .encoding_en import encode, EncodeError
from .layout import text_width

FLAG_VWF = 0x01
SPLIT = 0xFF        # {FF} in a named string: where code inserts a name or number


class UiError(Exception):
    pass


class UiEntry:
    def __init__(self, addr, mode, opts, lines, src_line):
        self.addr = addr
        self.mode = mode
        self.opts = opts
        self.lines = lines
        self.src_line = src_line


def read_ui(path):
    entries = []
    cur = None
    with open(path, encoding='utf-8') as f:
        raw = f.read().split('\n')
    for n, line in enumerate(raw + [''], 1):
        line = line.rstrip('\r')
        if cur is None:
            if line.startswith('#') or not line.strip():
                continue
            if not line.startswith('@'):
                raise UiError('line %d: expected @ADDR' % n)
            words = line[1:].split()
            if words[0].startswith('='):
                addr, mode, opts = words[0][1:], 'symbol', {}
                for w in words[1:]:
                    if w in ('noterm', 'solid'):
                        opts[w] = 1
                    elif w.startswith('orig='):   # original text(s) it replaces: ADDR[:LEN][,ADDR[:LEN]...]
                        origs = []
                        for part in w[5:].split(','):
                            a, _, ln = part.partition(':')
                            origs.append((int(a, 16), int(ln, 0) if ln else None))
                        opts['orig'] = origs[0]
                        opts['origs'] = origs
                    elif w.startswith('#'):
                        break
                    else:
                        raise UiError('line %d: unknown option %r' % (n, w))
                cur = UiEntry(addr, mode, opts, [], n)
                continue
            addr = int(words[0], 16)
            mode, opts = 'fixed', {}
            for w in words[1:]:
                if w in ('fixed', 'vwf', 'inplace'):
                    mode = w
                elif w == 'uiprint':
                    mode = 'fixed'
                    opts['uiprint'] = 1
                elif w == 'sysmsg':
                    mode = 'vwf'
                    opts.setdefault('width', 18)
                    opts.setdefault('lines', 3)
                    opts['sysmsg'] = 1
                elif w in ('solid', 'fixedwidth', 'center'):
                    opts[w] = 1
                elif '=' in w:
                    k, v = w.split('=', 1)
                    if k not in ('width', 'lines', 'tiles', 'len', 'fill', 'cells'):
                        raise UiError('line %d: unknown option %r' % (n, w))
                    opts[k] = int(v, 0)
                elif w.startswith('#'):
                    break
                else:
                    raise UiError('line %d: unknown option %r' % (n, w))
            cur = UiEntry(addr, mode, opts, [], n)
            continue
        if line == '':
            if cur.mode == 'vwf' and 'fill' in cur.opts:
                cur.lines = [vwf_fill(l, cur.opts['fill'], cur.opts.get('center')) for l in cur.lines]
            entries.append(cur)
            cur = None
            continue
        if cur.opts.get('solid'):
            line = line.replace(' ', '{DC}')
        cur.lines.append(line)
    return entries


def vwf_fill(line, cells, center=False):
    """Pad a variable-width line with the blank glyph 0xDC (3 px, a real glyph,
    so its tiles are drawn) to just under `cells` cells, so every cell of a
    fixed-size field is redrawn; 'center' splits the padding."""
    from .layout import widths
    w = widths()
    px = sum(w[b] for b in encode_ui(line))
    step = w[0xDC]
    if px > 8 * cells:
        return line
    n = (8 * cells - px) // step
    left = n // 2 if center else 0
    return '{DC}' * left + line + '{DC}' * (n - left)


def original_string(base, addr):
    """Bytes of the window-format string at addr, including the 00 00."""
    o = addr - ROM_BASE
    i = o
    while not (base[i] == 0 and base[i + 1] == 0):
        if base[i] >= 0xDF:
            raise UiError('%06X: byte %02X inside the original string' % (addr, base[i]))
        i += 1
    return bytes(base[o:i + 2])


def shape(bs):
    """(lines, widest line in cells, non-space characters) of a window string."""
    body = bs[:-2] if bs.endswith(b'\x00\x00') else bs
    lines = body.split(b'\x00')
    return len(lines), max(len(l) for l in lines), sum(1 for b in body if b not in (0, 1))


def measure(entry):
    """(cells per line list, tiles) of the English text in the entry's mode."""
    from .layout import widths
    cells, tiles = [], 0
    for line in entry.lines:
        if entry.mode == 'vwf':
            bs = encode_ui(line)
            lead = len(bs) - len(bs.lstrip(b'\x01'))
            px = 8 * lead + sum(widths()[b] for b in bs[lead:])   # leading spaces are whole cells
            c = (px + 7) // 8 if bs.strip(b'\x01') else 0       # blank lines use no tiles
            cells.append(c)
            tiles += c
        else:
            bs = encode_ui(line)
            cells.append(len(bs))
            tiles += sum(1 for b in bs if b != 0x01)
    return cells, tiles


def encode_ui(line):
    """encode() plus {XX} raw-byte escapes."""
    out = bytearray()
    i = 0
    while i < len(line):
        j = line.find('{', i)
        if j < 0:
            out += encode(line[i:])
            break
        out += encode(line[i:j])
        k = line.index('}', j)
        out.append(int(line[j + 1:k], 16))
        i = k + 1
    return bytes(out)


def encode_lines(lines):
    out = bytearray()
    for i, line in enumerate(lines):
        if i:
            out.append(0x00)
        out += encode_ui(line)
    return bytes(out)


def check(entry, base):
    if entry.mode == 'inplace' and 'len' in entry.opts:
        o = entry.addr - ROM_BASE              # raw span: no terminator to parse
        return bytes(base[o:o + entry.opts['len']])
    orig = original_string(base, entry.addr)
    n_lines, width, nchars = shape(orig)
    if entry.mode == 'inplace':
        return orig
    max_w = entry.opts.get('width', width)
    max_l = entry.opts.get('lines', n_lines)
    max_t = entry.opts.get('tiles', max(nchars, 36) if entry.opts.get('sysmsg') else nchars)
    cells, tiles = measure(entry)
    where = '%06X (ui.txt line %d)' % (entry.addr, entry.src_line)
    if len(entry.lines) > max_l:
        raise UiError('%s: %d lines, at most %d fit' % (where, len(entry.lines), max_l))
    for line, c in zip(entry.lines, cells):
        if c > max_w:
            raise UiError('%s: line %r needs %d cells, at most %d fit' % (where, line, c, max_w))
    if tiles > max_t and not entry.opts.get('uiprint'):
        raise UiError('%s: needs %d tiles, the original uses %d' % (where, tiles, max_t))
    if 'cells' in entry.opts:                   # also printed in fixed cells elsewhere
        for line in entry.lines:
            n = len(encode_ui(line))
            if n > entry.opts['cells']:
                raise UiError('%s: line %r has %d characters, the fixed-cell printer fits %d'
                              % (where, line, n, entry.opts['cells']))
    if entry.mode == 'vwf' and (0xDD in encode_lines(entry.lines) or 0xDE in encode_lines(entry.lines)):
        raise UiError('%s: [NAME]/[NUM] are not expanded in window text' % where)
    return orig


def build_ui(base, rom, path, text_start, text_end, table_out):
    """Apply in-place entries to rom, place remapped strings at text_start and
    write the remap table to table_out. Returns statistics."""
    entries = read_ui(path) if os.path.exists(path) else []
    seen = set()
    remap = []
    symbols = []
    ptr = text_start
    stats = {'remap': 0, 'inplace': 0, 'bytes': 0, 'symbols': 0}
    for e in entries:
        if e.mode == 'symbol':
            try:
                data = encode_lines(e.lines)
            except (EncodeError, ValueError) as ex:
                raise UiError('%s (ui.txt line %d): %s' % (e.addr, e.src_line, ex))
            if not e.opts.get('noterm'):
                data += b'\x00\x00'
            o = ptr - ROM_BASE
            if any(b != 0xFF for b in base[o:o + len(data)]):
                raise UiError('UI text area %06X is not free' % ptr)
            rom[o:o + len(data)] = data
            symbols.append((e.addr, ptr, len(data)))
            ptr += len(data)
            stats['symbols'] += 1
            stats['bytes'] += len(data)
            continue
        key = (e.addr, e.mode == 'inplace')    # one in-place + one remapped entry allowed
        if key in seen:
            raise UiError('%06X listed twice in ui.txt' % e.addr)
        seen.add(key)
        try:
            orig = check(e, base)
            body = encode_lines(e.lines)
        except (EncodeError, ValueError) as ex:
            raise UiError('%06X (ui.txt line %d): %s' % (e.addr, e.src_line, ex))
        if e.mode == 'inplace':
            span = e.opts.get('len')
            if e.opts.get('solid') and span is None and not e.opts.get('fixedwidth'):
                # fill the original shape: every line padded to the original
                # line's width with the blank glyph, so no cell keeps old text
                olines = orig[:-2].split(b'\x00')
                nlines = body.split(b'\x00')
                if len(nlines) > len(olines):
                    raise UiError('%06X (ui.txt line %d): %d lines, the original has %d' % (
                        e.addr, e.src_line, len(nlines), len(olines)))
                nlines += [b''] * (len(olines) - len(nlines))
                for k, (o_, n_) in enumerate(zip(olines, nlines)):
                    if len(n_) > len(o_):
                        raise UiError('%06X (ui.txt line %d): line %d has %d cells, the original %d' % (
                            e.addr, e.src_line, k + 1, len(n_), len(o_)))
                body = b'\x00'.join(n_ + b'\xdc' * (len(o_) - len(n_)) for o_, n_ in zip(olines, nlines))
            if e.opts.get('fixedwidth'):
                text_len = len(orig) - 2
                if len(body) > text_len:
                    raise UiError('%06X (ui.txt line %d): %d bytes, the fixed width is %d' % (
                        e.addr, e.src_line, len(body), text_len))
                data = body + b'\x01' * (text_len - len(body)) + b'\x00\x00'
                span = len(orig)
            elif span is None:
                data = body + b'\x00\x00'
                span = len(orig)
            else:
                data = body
            if len(data) > span:
                raise UiError('%06X (ui.txt line %d): %d bytes, only %d available in place' % (
                    e.addr, e.src_line, len(data), span))
            data += b'\x01' * (span - len(data))
            o = e.addr - ROM_BASE
            rom[o:o + span] = data
            stats['inplace'] += 1
            continue
        data = body + b'\x00\x00'
        if ptr + len(data) > text_end:
            raise UiError('out of space for UI text')
        o = ptr - ROM_BASE
        if any(b != 0xFF for b in base[o:o + len(data)]):
            raise UiError('UI text area %06X is not free' % ptr)
        rom[o:o + len(data)] = data
        remap.append((e.addr, FLAG_VWF if e.mode == 'vwf' else 0, ptr))
        ptr += len(data)
        stats['remap'] += 1
        stats['bytes'] += len(data)
    remap.sort()
    table = bytearray(struct.pack('<HH', len(remap), 0))
    for orig, flags, new in remap:
        table += struct.pack('<I', orig | (flags << 24)) + struct.pack('<I', new)
    os.makedirs(os.path.dirname(table_out), exist_ok=True)
    with open(table_out, 'wb') as f:
        f.write(table)
    with open(os.path.join(os.path.dirname(table_out), 'symbols.asm'), 'w') as f:
        f.write('; generated from translation/en/ui.txt\n')
        for name, addr, n in symbols:
            f.write('%s = 0x%06X\n%s_LEN = %d\n' % (name, addr, name, n))
            o = addr - ROM_BASE
            data = bytes(rom[o:o + n])
            if SPLIT in data:           # "head{FF}tail": a value is inserted at the {FF}
                k = data.index(SPLIT)
                f.write('%s_HEAD = %d\n%s_TAIL = %d\n%s_TAILPTR = 0x%06X\n' % (
                    name, k + 1, name, n - k - 1, name, addr + k + 1))
    stats['end'] = ptr
    return stats
