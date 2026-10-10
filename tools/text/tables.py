"""Rebuild the game's packed text tables with English text.

Many lists (class names, character names, items, item descriptions, ...) are
stored as a table of self-relative 16-bit offsets followed by the packed
entries; code reads entry k with the helper at 0x201B77, which returns
XIY = entry start and BC = entry length (distance to the next entry). English
entries are longer, so each table is rebuilt in free ROM and every
instruction that loads the table base into a register is repointed.

translation/en/tables/*.txt:

    @table 20E49D prefix=0
    # comment
    1	Fighter
    2	Knight

'@table ADDR' starts a table (ADDR = the offsets' address); 'prefix=N' keeps
the first N bytes of every original entry (binary data in front of the text);
'prefix=item' keeps the item data: 4 bytes (type, price, flags) plus one stat
byte per bit set in the 4th byte. 'wrap' word-wraps each '|'-separated part
to 'width' cells. 'vwf' starts every translated entry with
the marker 0xDB so the window renderer draws it with the variable-width font
(only for entries that are shown on their own, e.g. descriptions). Each following line is 'INDEX<TAB>TEXT'; '|' in
TEXT starts a new line (00). Entries that are not listed keep their original
bytes. Every 24-bit occurrence of the table address in the ROM must be the
operand of a known load instruction (a load site); anything else stops the
build. Text after '#' on the '@table' line is a comment.

Copy tables: a field narrower than the table's English (an 8-cell name field
in a list, say) can read its own version of the table:

    @table 2166B8 maxlen=8 sites=2157F6,20D5CA   # Items list, status pane ITEM field
    1	CurePotn

An '@table' line with 'sites=A,B,...' (hex load sites) declares a copy table.
It starts from the English entries of the main table (the '@table' line with
the same ADDR and no sites=, in any file of the folder), replaces the entries
it lists itself, and checks its own options (maxlen, vwf, wrap, width,
lines, tiles) on every resulting text, the inherited ones included; prefix=
comes from the main table (a different value is refused). The copy is
written as a table of its own, after all the main tables, and only the
listed load sites are repointed to it; the main table keeps the others (it
is not written at all when copy tables take every one). A load site is
given as the address of the load instruction or of its 24-bit operand;
'python -m tools.text.tables ROM ADDR' lists a table's load sites and which
table each one reads. 'name=WORD' names the copy in the localization
database ids, tbl:ADDR:N:WORD (default: the file name without '.txt'); the
'#' comment on its '@table' line should name the fields, the database shows
it in the context column. Refused: a copy table without a main table, a site
that is not a load site of the table or that another copy table lists too,
two tables with the same ADDR and the same sites, two copy tables of one
table with the same name.
"""
import os
import re
import struct
import sys

from ..recomp.rom import ROM_BASE
from ..recomp.tlcs900 import decode, DecodeError, Imm, Mem
from .uitext import encode_ui


VWF_MARK = 0xDB      # first byte of a window string: draw it with the VWF
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TABLES_DIR = os.path.join(ROOT, 'translation', 'en', 'tables')
_NAME = re.compile(r'^[A-Za-z0-9_-]+$')


class TableError(Exception):
    pass


def read_table(base, T):
    """[(entry bytes)] of the original table at T (offsets + packed entries)."""
    def r16(a):
        o = a - ROM_BASE
        return base[o] | (base[o + 1] << 8)
    first = T + r16(T)
    n = (first - T) // 2              # offsets, including the end marker
    targets = [T + 2 * k + r16(T + 2 * k) for k in range(n)]
    if any(b < a for a, b in zip(targets, targets[1:])):
        raise TableError('table %06X: offsets are not monotonic' % T)
    return [bytes(base[a - ROM_BASE:b - ROM_BASE]) for a, b in zip(targets, targets[1:])]


def build_table(entries):
    """Self-relative offset table + packed entries (same layout as the game's)."""
    n = len(entries) + 1
    data = bytearray()
    starts = []
    pos = 2 * n
    for e in entries:
        starts.append(pos)
        pos += len(e)
    starts.append(pos)
    for k, s in enumerate(starts):
        off = s - 2 * k
        if not 0 <= off < 0x10000:
            raise TableError('table too large for 16-bit offsets')
        data += struct.pack('<H', off)
    for e in entries:
        data += e
    return bytes(data)


# ---------------------------------------------------------------------------
# Table files
# ---------------------------------------------------------------------------

def parse_sites(text, path, n):
    """The addresses of a 'sites=A,B,...' option (hex)."""
    sites = []
    for s in text.split(','):
        try:
            a = int(s, 16)
        except ValueError:
            raise TableError('%s:%d: sites=: %r is not a hex address' % (path, n, s))
        if a in sites:
            raise TableError('%s:%d: sites=: %06X is listed twice' % (path, n, a))
        sites.append(a)
    return sites


def parse_header(line, path, n):
    """The table that an '@table ADDR [options] [# comment]' line starts.
    Keys: addr, prefix, vwf, entries {index: (text, line)}, file, line, sites
    (None for a main table), name (None for a main table), comment, given
    (the option names on the line), and wrap/width/lines/tiles/maxlen when given."""
    words = line.split()
    try:
        addr = int(words[1], 16)
    except (IndexError, ValueError):
        raise TableError('%s:%d: expected @table ADDR (hex)' % (path, n))
    t = {'addr': addr, 'prefix': 0, 'vwf': False, 'entries': {}, 'file': path, 'line': n,
         'sites': None, 'name': None, 'comment': '', 'given': set()}
    for i, w in enumerate(words[2:], 2):
        if w.startswith('#'):
            t['comment'] = ' '.join(words[i:])[1:].strip()
            break
        key, eq, value = w.partition('=')
        if key in t['given']:
            raise TableError('%s:%d: option %s given twice' % (path, n, key))
        t['given'].add(key)
        try:
            if w == 'prefix=item':
                t['prefix'] = 'item'
            elif w.startswith('prefix='):
                t['prefix'] = int(value, 0)
            elif w == 'vwf':
                t['vwf'] = True
            elif w == 'wrap':
                t['wrap'] = True
            elif key in ('width', 'lines', 'tiles', 'maxlen') and eq:
                t[key] = int(value, 0)
            elif w.startswith('sites='):
                t['sites'] = parse_sites(value, path, n)
            elif w.startswith('name='):
                if not _NAME.match(value):
                    raise TableError('%s:%d: name=%s: use letters, digits, _ and -' % (path, n, value))
                t['name'] = value
            else:
                raise TableError('%s:%d: unknown option %r' % (path, n, w))
        except ValueError:
            raise TableError('%s:%d: bad value in %r' % (path, n, w))
    if t['sites'] is None and t['name'] is not None:
        raise TableError('%s:%d: name= is only for copy tables (with sites=)' % (path, n))
    if t['sites'] is not None and t['name'] is None:
        t['name'] = os.path.splitext(os.path.basename(path))[0]
    return t


def read_table_file(path):
    tables = []
    cur = None
    with open(path, encoding='utf-8') as f:
        for n, raw in enumerate(f, 1):
            line = raw.rstrip('\r\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            if line.startswith('@table'):
                cur = parse_header(line, path, n)
                tables.append(cur)
                continue
            if cur is None:
                raise TableError('%s:%d: entry before @table' % (path, n))
            if '\t' not in line:
                raise TableError('%s:%d: expected INDEX<TAB>TEXT' % (path, n))
            idx, text = line.split('\t', 1)
            k = int(idx)
            if k in cur['entries']:
                raise TableError('%s:%d: entry %d listed twice' % (path, n, k))
            cur['entries'][k] = (text, n)
    return tables


def read_tables(folder):
    """Every table of folder/*.txt: files in name order, tables in file order."""
    out = []
    for name in sorted(os.listdir(folder)):
        if name.endswith('.txt'):
            out += read_table_file(os.path.join(folder, name))
    return out


def describe(t):
    """'table ADDR' or 'copy table ADDR "NAME"' (for messages)."""
    if t['sites'] is None:
        return 'table %06X' % t['addr']
    return 'copy table %06X "%s"' % (t['addr'], t['name'])


def group_tables(tables):
    """Pair every copy table with its main table. Returns (mains, copies):
    {ADDR: main table} and the copy tables in order; each copy gets 'main'
    (its main table) and the main table's prefix. Refuses a second main table
    for an ADDR, a second table with the same ADDR and sites (as written), a
    copy table without a main table, two copies of one table with the same
    name, and a copy whose prefix= differs from the main table's."""
    mains, copies, seen, names = {}, [], {}, {}
    for t in tables:
        key = (t['addr'], None if t['sites'] is None else frozenset(t['sites']))
        if key in seen:
            o = seen[key]
            raise TableError('%s:%d: %s defined twice (also at %s:%d)'
                             % (t['file'], t['line'], describe(t) if t['sites'] is None
                                else 'table %06X sites=%s' % (t['addr'], ','.join('%06X' % s for s in t['sites'])),
                                o['file'], o['line']))
        seen[key] = t
        if t['sites'] is None:
            mains[t['addr']] = t
        else:
            copies.append(t)
    for c in copies:
        m = mains.get(c['addr'])
        if m is None:
            raise TableError('%s:%d: copy table %06X has no main table (an @table %06X line without sites=)'
                             % (c['file'], c['line'], c['addr'], c['addr']))
        nk = (c['addr'], c['name'])
        if nk in names:
            o = names[nk]
            raise TableError('%s:%d: two copy tables of %06X are named "%s" (also %s:%d); give one another name='
                             % (c['file'], c['line'], c['addr'], c['name'], o['file'], o['line']))
        names[nk] = c
        if 'prefix' in c['given'] and c['prefix'] != m['prefix']:
            raise TableError('%s:%d: prefix=%s differs from the main table\'s prefix=%s (%s:%d)'
                             % (c['file'], c['line'], c['prefix'], m['prefix'], m['file'], m['line']))
        c['prefix'] = m['prefix']
        c['main'] = m
    return mains, copies


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------

def wrapped(t, text, line):
    """'wrap' tables: word-wrap each '|'-separated part to the table width."""
    if not t.get('wrap'):
        return text
    from .layout import wrap_line
    out = []
    for part in text.split('|'):
        lead = len(part) - len(part.lstrip(' '))
        out += [' ' * lead + l for l in wrap_line(part, 8 * t.get('width', 18))] if part.strip() else ['']
    return '|'.join(out)


def check_entry(t, k, text, line, where=None):
    """Fit checks: 'maxlen=N' (characters per line, fixed cells) for name
    tables; 'width=N lines=N tiles=N' (cells/lines/tiles) for vwf tables.
    `where` names the entry in messages (default: FILE:LINE (entry K))."""
    if where is None:
        where = '%s:%d (entry %d)' % (t['file'], line, k)
    lines = text.split('|')
    if 'maxlen' in t:
        for l in lines:
            if len(l) > t['maxlen']:
                raise TableError('%s: %r is longer than %d characters' % (where, l, t['maxlen']))
    if t['vwf']:
        from .layout import text_width
        if len(lines) > t.get('lines', 99):
            raise TableError('%s: %d lines, at most %d' % (where, len(lines), t['lines']))
        tiles = 0
        for l in lines:
            cells = (text_width(l) + 7) // 8
            if cells > t.get('width', 99):
                raise TableError('%s: line %r needs %d cells, at most %d' % (where, l, cells, t['width']))
            tiles += cells
        if tiles > t.get('tiles', 999):
            raise TableError('%s: needs %d tiles, at most %d' % (where, tiles, t['tiles']))


def entry_prefix(t, e):
    """Number of bytes of the original entry e kept in front of the text."""
    if t['prefix'] == 'item':
        return 4 + bin(e[3]).count('1') if len(e) >= 4 else 0
    return t['prefix']


def own_texts(t):
    """{index: (text, file, line)} of the entries a table file lists for t."""
    return {k: (text, t['file'], line) for k, (text, line) in t['entries'].items()}


def merged_texts(t):
    """The texts of a table: a main table's own entries; for a copy table the
    main table's entries replaced by the copy's own."""
    texts = own_texts(t['main']) if t['sites'] is not None else {}
    texts.update(own_texts(t))
    return texts


def table_entries(t, orig, texts):
    """The entries of table t: the original entries `orig` with the texts
    {index: (text, file, line)} encoded with t's options (wrap, prefix, vwf)
    and checked against t's limits. A copy table's inherited texts (from the
    main table's file) are checked against the copy's limits as well."""
    entries = list(orig)
    for k, (text, path, line) in sorted(texts.items()):
        at = '%s:%d' % (path, line)
        via = '' if path == t['file'] else ', inherited by the %s at %s:%d' % (describe(t), t['file'], t['line'])
        where = '%s (entry %d%s)' % (at, k, via)
        try:
            text = wrapped(t, text, line)
        except ValueError as e:
            raise TableError('%s: %s' % (where, e))
        if not 0 <= k < len(orig):
            raise TableError('%s: table %06X has no entry %d' % (at, t['addr'], k))
        prefix = entry_prefix(t, orig[k])
        if len(orig[k]) < prefix:
            raise TableError('%s: entry %d is shorter than the prefix' % (at, k))
        try:
            body = b'\x00'.join(encode_ui(part) for part in text.split('|'))
        except Exception as e:
            raise TableError('%s: %s' % (at, e))
        try:
            check_entry(t, k, text, line, where=where)
        except TableError as e:
            if via:
                raise TableError('%s; give the copy table its own entry %d' % (e, k))
            raise
        if t['vwf']:
            body = bytes([VWF_MARK]) + body
        entries[k] = orig[k][:prefix] + body
    return entries


# ---------------------------------------------------------------------------
# Load sites
# ---------------------------------------------------------------------------

def load_refs(base, T):
    """[(operand address, instruction address)] of every load of the table
    address T: each 24-bit occurrence of T in the ROM must be the operand of
    a ld/lda instruction, or the build stops."""
    refs = []
    pat = bytes([T & 0xFF, (T >> 8) & 0xFF, T >> 16])
    view = _View(base)
    i = base.find(pat)
    while i >= 0:
        a = ROM_BASE + i
        insn = None
        for back in range(1, 4):
            try:
                ins = decode(view.read8, a - back)
            except DecodeError:
                continue
            if ins.next in (a + 3, a + 4) and ins.mnem in ('ld', 'lda') and any(
                    (isinstance(op, Imm) and (op.value & 0xFFFFFFFF) == T) or
                    (isinstance(op, Mem) and op.mode == 'abs' and op.disp == T) for op in ins.ops):
                insn = a - back
                break
        if insn is None:
            raise TableError('table %06X: reference at %06X is not a recognised load' % (T, a))
        refs.append((a, insn))
        i = base.find(pat, i + 1)
    return refs


def load_sites(base, T):
    """Addresses of the 24-bit operands equal to T inside load instructions."""
    return [a for a, _ in load_refs(base, T)]


def resolve_sites(c, refs):
    """The operand addresses of a copy table's sites=, each given as the
    instruction or the operand address of one of the load sites `refs`."""
    by_insn = {insn: op for op, insn in refs}
    ops = {op for op, _ in refs}
    out = []
    for s in c['sites']:
        op = s if s in ops else by_insn.get(s)
        if op is None:
            raise TableError('%s:%d: %06X is not a load site of table %06X; its load sites are %s'
                             % (c['file'], c['line'], s, c['addr'],
                                ', '.join('%06X' % insn for _, insn in refs) or 'none'))
        if op in out:
            raise TableError('%s:%d: sites= names the load at %06X twice'
                             % (c['file'], c['line'], [i for o, i in refs if o == op][0]))
        out.append(op)
    return out


def assign_sites(copies, refs_of):
    """Resolve the copy tables' sites (c['site_ops'] = operand addresses).
    Returns {operand address: copy table}. Refuses two copies of a table for
    the same load sites and a load site that two copies list."""
    claimed, by_sites = {}, {}
    for c in copies:
        c['site_ops'] = resolve_sites(c, refs_of(c['addr']))
        key = (c['addr'], frozenset(c['site_ops']))
        if key in by_sites:
            o = by_sites[key]
            raise TableError('%s:%d: table %06X defined twice: same load sites as the %s at %s:%d'
                             % (c['file'], c['line'], c['addr'], describe(o), o['file'], o['line']))
        by_sites[key] = c
        for op in c['site_ops']:
            if op in claimed:
                o = claimed[op]
                raise TableError('%s:%d: the load at %06X is also listed by the %s at %s:%d'
                                 % (c['file'], c['line'], [i for p, i in refs_of(c['addr']) if p == op][0],
                                    describe(o), o['file'], o['line']))
            claimed[op] = c
    return claimed


class _View:
    def __init__(self, data):
        self.data = data

    def read8(self, a):
        o = a - ROM_BASE
        return self.data[o] if 0 <= o < len(self.data) else 0xFF


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_tables(base, rom, folder, start, end, placed=None):
    """Rebuild every table described in folder/*.txt into [start, end): the
    main tables first (files in name order, tables in file order), then the
    copy tables in the same order. Returns (bytes used, number of tables
    written, number of entries replaced: every main table entry and every
    entry a copy table lists itself). If `placed` is a list, a record is
    appended for each table: {'addr', 'name' (None for a main table),
    'start' (None for a main table that nothing reads any more), 'size',
    'sites' (the operand addresses repointed to it), 'file', 'line'}."""
    if not os.path.isdir(folder):
        return 0, 0, 0
    tables = read_tables(folder)
    _, copies = group_tables(tables)
    refs = {}

    def refs_of(T):
        if T not in refs:
            refs[T] = load_refs(base, T)
        return refs[T]

    claimed = assign_sites(copies, refs_of)
    ptr = start
    ntab = nent = 0
    order = [t for t in tables if t['sites'] is None] + copies
    for t in order:
        T = t['addr']
        orig = read_table(base, T)
        entries = table_entries(t, orig, merged_texts(t))
        nent += len(t['entries'])
        if t['sites'] is None:
            sites = [op for op, _ in refs_of(T) if op not in claimed]
        else:
            sites = t['site_ops']
        record = {'addr': T, 'name': t['name'], 'start': None, 'size': 0, 'sites': sites,
                  'file': t['file'], 'line': t['line']}
        if placed is not None:
            placed.append(record)
        if not sites:               # copy tables take every load site: nothing reads it
            continue
        data = build_table(entries)
        if ptr + len(data) > end:
            raise TableError('out of space for tables')
        o = ptr - ROM_BASE
        if any(b != 0xFF for b in base[o:o + len(data)]):
            raise TableError('table area %06X is not free' % ptr)
        rom[o:o + len(data)] = data
        for s in sites:
            so = s - ROM_BASE
            rom[so:so + 3] = bytes([ptr & 0xFF, (ptr >> 8) & 0xFF, ptr >> 16])
        record['start'], record['size'] = ptr, len(data)
        ptr += len(data)
        ntab += 1
    return ptr - start, ntab, nent


# ---------------------------------------------------------------------------
# Command line: list load sites
# ---------------------------------------------------------------------------

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description='List the load sites of packed tables (the addresses for sites= of a copy table) '
                    'and which table of the translation reads each one.')
    def hex_addr(s):
        try:
            return int(s, 16)
        except ValueError:
            raise argparse.ArgumentTypeError('%r is not a hex address' % s)
    ap.add_argument('rom', help='the original ROM (rom/baserom.ngc)')
    ap.add_argument('addr', nargs='+', type=hex_addr, help='table address (hex), e.g. 2166B8')
    ap.add_argument('--folder', default=TABLES_DIR, help='table files (default translation/en/tables)')
    args = ap.parse_args(argv)
    with open(args.rom, 'rb') as f:
        base = f.read()
    try:
        mains, copies = group_tables(read_tables(args.folder) if os.path.isdir(args.folder) else [])
        for T in args.addr:
            refs = load_refs(base, T)
            readers = {}
            for c in copies:
                if c['addr'] == T:
                    for op in resolve_sites(c, refs):
                        readers[op] = '%s (%s:%d)' % (describe(c), os.path.basename(c['file']), c['line'])
            m = mains.get(T)
            rest = ('table %06X (%s:%d)' % (T, os.path.basename(m['file']), m['line']) if m
                    else 'the original table (no table file)')
            print('table %06X: %d load sites (instruction address, instruction, table read)' % (T, len(refs)))
            view = _View(base)
            for op, insn in refs:
                print('  %06X  %-26s %s' % (insn, decode(view.read8, insn).text(), readers.get(op, rest)))
    except TableError as e:
        raise SystemExit('tables: %s' % e)


if __name__ == '__main__':
    sys.exit(main())
