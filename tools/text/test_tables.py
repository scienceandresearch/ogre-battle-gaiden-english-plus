"""Tests for the packed-table builder (tools/text/tables.py), copy tables in
particular, and their rows in the localization database (tools/text/l10n.py).

Usage: python -m tools.text.test_tables [ROM] [-k TEXT]
       (or: python -m pytest tools/text/test_tables.py)

ROM  the original ROM (default rom/baserom.ngc). Without it the tests that
     need the real ROM are skipped; the others use a small synthetic ROM made
     here (our own bytes: load instructions assembled by tools/asm, made-up
     table entries), never ROM data.

Covers: parsing of '@table' lines (sites=, name=, the '#' comment, errors);
pairing copy tables with their main tables (refused: no main table, a table
defined twice, keyed on ADDR and sites, two copies with one name, another
prefix=); the build without copy tables (tables back to back in file order,
every load site at its table); a copy table (main table's English, its own
entries on top, its own options: maxlen on inherited and own texts, vwf,
prefix=item inherited; written after all main tables; only its load sites
repointed); load sites given as instruction or operand address, refused when
unknown, listed twice or listed by two copies; copy tables taking every load
site (the main table is then not written); the localization rows of copy
tables and the review import into the right file and section, with the
files' line endings kept. With the ROM: the real tables' load sites, copy
tables of the item and class tables built against the real ROM (sites,
entries, item data, the ROM layout check) and the real translation folder
(every fixed-cell name field reads texts of at most 8 characters; the shop
list, the messages and the item data keep the main tables' full names).

Everything is written to temporary folders; build/ and translation/ are not
touched.
"""
import contextlib
import csv
import hashlib
import io
import os
import sys
import tempfile
import time
import traceback

from ..asm.tlcs900asm import assemble_text
from ..patch import layout
from ..recomp.rom import EXPECTED_SHA1, ROM_BASE
from . import l10n
from . import tables as tb
from .uitext import encode_ui

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEFAULT_ROM = os.path.join(ROOT, 'rom', 'baserom.ngc')

# ---------------------------------------------------------------------------
# Synthetic ROM: 64 KB at 0x200000; code at 0x200100, two tables, 0xFF from FREE

T1 = 0x2013A5                   # three load sites: A, B (ld.l XIY, imm) and C (lda XIY, (abs))
T2 = 0x2015C3                   # item-like table (prefix=item), one load site D
A, B, C, D = 0x200100, 0x200110, 0x200120, 0x200130     # load instructions
FREE, END = 0x208000, 0x210000
CODE = '''
        .org 0x200100
        ld.l    XIY, 0x2013A5
        .org 0x200110
        ld.l    XIY, 0x2013A5
        .org 0x200120
        lda     XIY, (0x2013A5)
        .org 0x200130
        ld.l    XIY, 0x2015C3
'''
T1_ORIG = [b'', bytes((0x60, 0x61, 0x62)), bytes((0x63, 0x64)), bytes((0x65, 0x66, 0x67, 0x68))]
T2_ORIG = [bytes((0, 0, 0, 0)),
           bytes((1, 0x10, 0x00, 0x03, 0x05, 0x06, 0x70, 0x71)),     # 4 bytes + 2 stat bytes, then text
           bytes((2, 0x20, 0x00, 0x00, 0x72))]                       # 4 bytes, then text
_SYN = []


def synthetic_rom():
    if not _SYN:
        rom = bytearray(b'\x00' * (FREE - ROM_BASE) + b'\xFF' * (END - FREE))
        chunks, _ = assemble_text(CODE)
        for org, data in chunks:
            rom[org - ROM_BASE:org - ROM_BASE + len(data)] = data
        for T, entries in ((T1, T1_ORIG), (T2, T2_ORIG)):
            data = tb.build_table(entries)
            rom[T - ROM_BASE:T - ROM_BASE + len(data)] = data
        _SYN.append(bytes(rom))
    return _SYN[0]


class SynRom:
    """What l10n.table_rows needs of a tools.recomp.rom.Rom."""
    def __init__(self, data):
        self.data = data


# ---------------------------------------------------------------------------
# Helpers

class Skip(Exception):
    pass


_ROM = {'path': DEFAULT_ROM, 'data': None}


def need_rom():
    """The original ROM, or skip the test."""
    if _ROM['data'] is None:
        if not os.path.exists(_ROM['path']):
            why = 'no ROM at %s' % _ROM['path']
            if 'pytest' in sys.modules:
                import pytest
                pytest.skip(why)
            raise Skip(why)
        with open(_ROM['path'], 'rb') as f:
            data = f.read()
        if hashlib.sha1(data).hexdigest() != EXPECTED_SHA1:
            raise AssertionError('%s is not the original ROM' % _ROM['path'])
        _ROM['data'] = data
    return _ROM['data']


def expect(fn, *args, contains=(), **kw):
    """fn(*args) must raise TableError (or SystemExit) with every text of `contains` in its message."""
    try:
        fn(*args, **kw)
    except (tb.TableError, SystemExit) as e:
        for c in ([contains] if isinstance(contains, str) else contains):
            if c not in str(e):
                raise AssertionError('%r is not in the error: %s' % (c, e))
        return str(e)
    raise AssertionError('no error raised')


def write(folder, name, text, newline='\n'):
    path = os.path.join(folder, name)
    with open(path, 'w', encoding='utf-8', newline=newline) as f:
        f.write(text)
    return path


def build(folder, base=None, start=FREE, end=END):
    """build_tables on a copy of base -> (rom, (used, ntab, nent), placed)."""
    base = synthetic_rom() if base is None else base
    rom = bytearray(base)
    placed = []
    stats = tb.build_tables(base, rom, folder, start, end, placed=placed)
    return rom, stats, placed


def ptr(rom, insn):
    """The 24-bit operand of the 5-byte load at insn."""
    o = insn + 1 - ROM_BASE
    return rom[o] | rom[o + 1] << 8 | rom[o + 2] << 16


def table_at(rom, addr):
    return tb.read_table(rom, addr)


def enc(text):
    return b'\x00'.join(encode_ui(p) for p in text.split('|'))


def by_name(placed, name):
    return [p for p in placed if p['name'] == name][0]


def tmpdir():
    return tempfile.TemporaryDirectory(prefix='test_tables_')


# ---------------------------------------------------------------------------
# Parsing and pairing (no ROM)

def test_parse_header():
    t = tb.parse_header('@table 2166B8 prefix=item maxlen=15', 'x/items.txt', 4)
    assert (t['addr'], t['prefix'], t['maxlen'], t['sites'], t['name'], t['comment']) == \
        (0x2166B8, 'item', 15, None, None, '')
    assert t['given'] == {'prefix', 'maxlen'} and (t['file'], t['line']) == ('x/items.txt', 4)
    t = tb.parse_header('@table 2166B8 maxlen=8 sites=2157F6,20D5CA   # Items list,  ITEM field',
                        os.path.join('x', 'items_short.txt'), 2)
    assert t['sites'] == [0x2157F6, 0x20D5CA] and t['name'] == 'items_short' and t['maxlen'] == 8
    assert t['comment'] == 'Items list, ITEM field' and t['given'] == {'maxlen', 'sites'}
    assert t['prefix'] == 0 and 'prefix' not in t['given']
    t = tb.parse_header('@table 20E49D sites=0x21303C name=short-1 vwf wrap width=9 #x', 'c.txt', 1)
    assert (t['sites'], t['name'], t['vwf'], t['wrap'], t['width'], t['comment']) == \
        ([0x21303C], 'short-1', True, True, 9, 'x')
    for line, msg in (('@table', 'expected @table ADDR'), ('@table XYZ', 'expected @table ADDR'),
                      ('@table 1 sites=', 'is not a hex address'), ('@table 1 sites=12G', 'is not a hex address'),
                      ('@table 1 sites=1,01', 'listed twice'), ('@table 1 name=x', 'only for copy tables'),
                      ('@table 1 sites=1 name=a.b', 'use letters'), ('@table 1 maxlen=8 maxlen=9', 'given twice'),
                      ('@table 1 bogus', 'unknown option'), ('@table 1 maxlen=x', 'bad value'),
                      ('@table 1 maxlen', 'unknown option')):
        expect(tb.parse_header, line, 'f.txt', 7, contains=('f.txt:7', msg))


def test_read_table_file():
    with tmpdir() as d:
        p = write(d, 'names.txt', '# names\n@table 2013A5 maxlen=12\n1\tAlpha\n2\tBravo\n\n'
                  '# short forms\n@table 2013A5 maxlen=4 sites=200110 name=short   # list field\n2\tBrv\n')
        main, copy = tb.read_table_file(p)
        assert main['entries'] == {1: ('Alpha', 3), 2: ('Bravo', 4)} and main['sites'] is None
        assert copy['entries'] == {2: ('Brv', 8)} and copy['sites'] == [0x200110]
        assert (copy['name'], copy['comment'], copy['line']) == ('short', 'list field', 7)
        write(d, 'twice.txt', '@table 2013A5 sites=200110\n2\tA\n2\tB\n')
        expect(tb.read_table_file, os.path.join(d, 'twice.txt'), contains='entry 2 listed twice')


def test_group_tables():
    def tabs(*lines):
        return [tb.parse_header(l, os.path.join('d', f), n) for n, (f, l) in enumerate(lines, 1)]
    mains, copies = tb.group_tables(tabs(('a.txt', '@table 2013A5 sites=200110 maxlen=4'),
                                         ('b.txt', '@table 2013A5 prefix=item'),
                                         ('b.txt', '@table 2015C3')))
    assert sorted(mains) == [T1, T2] and len(copies) == 1
    c = copies[0]
    assert c['main'] is mains[T1] and c['prefix'] == 'item' and c['name'] == 'a'
    expect(tb.group_tables, tabs(('a.txt', '@table 2013A5 sites=200110')),
           contains=('copy table 2013A5 has no main table', 'a.txt:1'))
    expect(tb.group_tables, tabs(('a.txt', '@table 2013A5'), ('b.txt', '@table 2013A5')),
           contains=('table 2013A5 defined twice', 'a.txt:1'))
    expect(tb.group_tables, tabs(('a.txt', '@table 2013A5'), ('a.txt', '@table 2013A5 sites=200110,200100'),
                                 ('b.txt', '@table 2013A5 sites=200100,200110 name=other')),
           contains=('defined twice', 'b.txt:3'))
    expect(tb.group_tables, tabs(('a.txt', '@table 2013A5'), ('s.txt', '@table 2013A5 sites=200110'),
                                 ('s.txt', '@table 2013A5 sites=200120')),
           contains=('named "s"', 'name='))
    expect(tb.group_tables, tabs(('a.txt', '@table 2013A5 prefix=item'), ('s.txt', '@table 2013A5 prefix=0 sites=1')),
           contains=('prefix=0 differs', 'prefix=item'))
    # copy tables of different tables may share a name
    tb.group_tables(tabs(('a.txt', '@table 2013A5'), ('a.txt', '@table 2015C3'),
                         ('s.txt', '@table 2013A5 sites=200110'), ('s.txt', '@table 2015C3 sites=200130')))


# ---------------------------------------------------------------------------
# Building (synthetic ROM)

def test_no_copies_layout():
    """Without copy tables: tables back to back from `start`, files in name
    order, every load site at its table (the layout of the builder before
    copy tables existed)."""
    with tmpdir() as d:
        write(d, 'a.txt', '@table 2015C3 prefix=item\n1\tSword\n')
        write(d, 'b.txt', '@table 2013A5 maxlen=10\n1\tAlpha\n2\tBravo|Two\n')
        rom, stats, placed = build(d)
        t2 = tb.build_table([T2_ORIG[0], T2_ORIG[1][:6] + enc('Sword'), T2_ORIG[2]])
        t1 = tb.build_table([T1_ORIG[0], enc('Alpha'), enc('Bravo|Two'), T1_ORIG[3]])
        o = FREE - ROM_BASE
        assert bytes(rom[o:o + len(t2) + len(t1)]) == t2 + t1
        assert all(b == 0xFF for b in rom[o + len(t2) + len(t1):])
        assert stats == (len(t2) + len(t1), 2, 3)
        assert [ptr(rom, s) for s in (A, B, C, D)] == [FREE + len(t2)] * 3 + [FREE]
        assert [(p['addr'], p['name'], p['start']) for p in placed] == [(T2, None, FREE), (T1, None, FREE + len(t2))]
        base = synthetic_rom()
        changed = [i for i in range(len(base)) if base[i] != rom[i] and i < FREE - ROM_BASE]
        assert len(changed) <= 12 and all(any(s + 1 <= ROM_BASE + i < s + 4 for s in (A, B, C, D))
                                          for i in changed)


def test_copy_merge_and_repoint():
    """A copy table: the main table's English with its own entries on top,
    written after every main table even when its file sorts first; only its
    load sites point at it."""
    with tmpdir() as d:
        write(d, 'a_short.txt', '@table 2013A5 maxlen=5 sites=200110   # list field\n2\tBee\n')
        write(d, 'b_main.txt', '@table 2013A5 maxlen=12\n1\tAlpha\n2\tBravo Long\n')
        rom, stats, placed = build(d)
        main = by_name(placed, None)
        copy = by_name(placed, 'a_short')
        assert main['start'] == FREE and copy['start'] == FREE + main['size']
        assert main['sites'] == [A + 1, C + 1] and copy['sites'] == [B + 1]
        assert (ptr(rom, A), ptr(rom, B), ptr(rom, C)) == (FREE, copy['start'], FREE)
        assert table_at(rom, main['start']) == [b'', enc('Alpha'), enc('Bravo Long'), T1_ORIG[3]]
        assert table_at(rom, copy['start']) == [b'', enc('Alpha'), enc('Bee'), T1_ORIG[3]]
        assert stats == (main['size'] + copy['size'], 2, 3)
        assert ptr(rom, D) == T2                         # a table without a file stays where it is
        # the same copy in the main table's own file
        os.remove(os.path.join(d, 'a_short.txt'))
        write(d, 'b_main.txt', '@table 2013A5\n1\tAlpha\n2\tBravo Long\n'
              '@table 2013A5 sites=200110 name=short\n2\tBee\n')
        rom2, _, placed2 = build(d)
        assert table_at(rom2, by_name(placed2, 'short')['start']) == [b'', enc('Alpha'), enc('Bee'), T1_ORIG[3]]
        assert ptr(rom2, B) == by_name(placed2, 'short')['start'] and ptr(rom2, A) == FREE


def test_copy_limits():
    """maxlen (per line) and the vwf limits of the copy apply to inherited and own texts."""
    with tmpdir() as d:
        write(d, 'main.txt', '@table 2013A5 maxlen=12\n1\tAlpha\n2\tBravo Long\n')
        write(d, 'short.txt', '@table 2013A5 maxlen=4 sites=200110\n2\tBee\n')
        e = expect(build, d, contains=('main.txt:2 (entry 1, inherited by the copy table 2013A5 "short" at',
                                       'short.txt:1', "'Alpha' is longer than 4 characters",
                                       'give the copy table its own entry 1'))
        assert 'main.txt' in e
        write(d, 'short.txt', '@table 2013A5 maxlen=4 sites=200110\n1\tAlph\n2\tBravo\n')
        expect(build, d, contains=('short.txt:3 (entry 2)', "'Bravo' is longer than 4"))
        write(d, 'short.txt', '@table 2013A5 maxlen=4 sites=200110\n1\tAl|ph\n2\tBr|avocado\n')
        expect(build, d, contains=('short.txt:3', "'avocado' is longer than 4"))
        write(d, 'short.txt', '@table 2013A5 maxlen=4 sites=200110\n1\tAl|ph\n2\tBr|av\n')
        rom, _, placed = build(d)
        assert table_at(rom, by_name(placed, 'short')['start'])[1:3] == [enc('Al|ph'), enc('Br|av')]
        # vwf limits: width in cells (8 px each), checked on the inherited text too
        write(d, 'short.txt', '@table 2013A5 vwf width=2 lines=1 sites=200110\n2\tBee\n')
        expect(build, d, contains=('main.txt:2 (entry 1, inherited', 'at most 2'))
        write(d, 'short.txt', '@table 2013A5 sites=200110\n5\tEcho\n')
        expect(build, d, contains=('short.txt:2', 'table 2013A5 has no entry 5'))


def test_copy_options():
    """prefix=item comes from the main table; vwf and the other display
    options are the copy's own."""
    with tmpdir() as d:
        write(d, 'items.txt', '@table 2015C3 prefix=item\n1\tSword\n2\tShield\n')
        write(d, 'items_short.txt', '@table 2015C3 vwf sites=200130\n1\tSwd\n')
        rom, _, placed = build(d)
        copy = by_name(placed, 'items_short')
        assert ptr(rom, D) == copy['start']
        assert table_at(rom, copy['start']) == [T2_ORIG[0], T2_ORIG[1][:6] + b'\xDB' + enc('Swd'),
                                                T2_ORIG[2][:4] + b'\xDB' + enc('Shield')]
        main = by_name(placed, None)
        assert main['start'] is None and main['sites'] == []    # its only load site reads the copy
        write(d, 'items.txt', '@table 2015C3 prefix=item vwf\n1\tSword\n2\tShield\n')
        write(d, 'items_short.txt', '@table 2015C3 prefix=item sites=200130\n1\tSwd\n')
        rom, _, placed = build(d)
        assert table_at(rom, by_name(placed, 'items_short')['start']) == [
            T2_ORIG[0], T2_ORIG[1][:6] + enc('Swd'), T2_ORIG[2][:4] + enc('Shield')]


def test_copy_sites():
    """Sites as instruction or operand addresses; refused: unknown sites, one
    load named twice, a load listed by two copies, two copies for the same loads."""
    with tmpdir() as d:
        write(d, 'main.txt', '@table 2013A5\n1\tAlpha\n2\tBravo\n')
        write(d, 'short.txt', '@table 2013A5 sites=200121,200100\n1\tAl\n')     # operand of C, instruction A
        rom, _, placed = build(d)
        copy = by_name(placed, 'short')
        assert copy['sites'] == [C + 1, A + 1] and by_name(placed, None)['sites'] == [B + 1]
        assert (ptr(rom, A), ptr(rom, B), ptr(rom, C)) == (copy['start'], FREE, copy['start'])
        write(d, 'short.txt', '@table 2013A5 sites=200100,200105\n')
        expect(build, d, contains=('short.txt:1', '200105 is not a load site of table 2013A5',
                                   '200100, 200110, 200120'))
        write(d, 'short.txt', '@table 2013A5 sites=200130\n')       # a load of the other table
        expect(build, d, contains='200130 is not a load site of table 2013A5')
        write(d, 'short.txt', '@table 2013A5 sites=200110,200111\n')
        expect(build, d, contains='names the load at 200110 twice')
        write(d, 'short.txt', '@table 2013A5 sites=200100,200110\n@table 2013A5 sites=200111 name=b\n')
        expect(build, d, contains=('short.txt:2', 'the load at 200110 is also listed by the copy table 2013A5 "short"'))
        write(d, 'short.txt', '@table 2013A5 sites=200100,200110\n@table 2013A5 sites=200111,200101 name=b\n')
        expect(build, d, contains=('short.txt:2', 'defined twice', 'same load sites'))
        write(d, 'short.txt', '@table 2013A5 sites=200100,200110\n@table 2013A5 sites=200110,200100 name=b\n')
        expect(build, d, contains=('short.txt:2', 'defined twice'))
        write(d, 'short.txt', '@table 2015C3 sites=200130\n')
        expect(build, d, contains='copy table 2015C3 has no main table')


def test_copies_take_every_site():
    """Two copy tables share the load sites: the main table is only the
    source of their English and is not written."""
    with tmpdir() as d:
        write(d, 'main.txt', '@table 2013A5\n1\tAlpha\n2\tBravo\n')
        write(d, 'short.txt', '@table 2013A5 sites=200100,200110 name=x\n1\tAl\n'
              '@table 2013A5 sites=200120 name=y\n2\tBr\n')
        rom, stats, placed = build(d)
        assert [(p['name'], p['start']) for p in placed] == [(None, None), ('x', FREE), ('y', FREE + placed[1]['size'])]
        assert (ptr(rom, A), ptr(rom, B), ptr(rom, C)) == (FREE, FREE, placed[2]['start'])
        assert table_at(rom, FREE) == [b'', enc('Al'), enc('Bravo'), T1_ORIG[3]]
        assert table_at(rom, placed[2]['start']) == [b'', enc('Alpha'), enc('Br'), T1_ORIG[3]]
        assert stats == (placed[1]['size'] + placed[2]['size'], 2, 4)


def test_no_folder():
    assert tb.build_tables(synthetic_rom(), bytearray(synthetic_rom()), os.path.join(ROOT, 'no such folder'),
                           FREE, END) == (0, 0, 0)


# ---------------------------------------------------------------------------
# Localization database (synthetic ROM)

class L10nFolder:
    """l10n pointed at a temporary tables folder (and ROOT, for its relative paths)."""
    def __init__(self, folder):
        self.folder = folder

    def __enter__(self):
        self.saved = (l10n.TABLES_DIR, l10n.ROOT, l10n.NOTES_TXT)
        l10n.TABLES_DIR, l10n.ROOT = self.folder, self.folder
        l10n.NOTES_TXT = os.path.join(self.folder, 'review_notes.txt')
        return self

    def __exit__(self, *exc):
        l10n.TABLES_DIR, l10n.ROOT, l10n.NOTES_TXT = self.saved


def rows_by_id(rows):
    out = {r['id']: r for r in rows}
    assert len(out) == len(rows), 'duplicate ids'
    return out


def import_csv(folder, rows, suggestions, apply=True):
    """Write `rows` as an exported CSV with suggestions {id: text}, import it; returns the printed output."""
    path = os.path.join(folder, 'review.csv')
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(l10n.COLUMNS)
        for r in rows:
            r = dict(r, suggested_english=suggestions.get(r['id'], ''), reviewer='', reviewer_comment='')
            w.writerow([r[c] for c in l10n.COLUMNS])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        l10n.do_import(path, apply, 'test')
    os.remove(path)
    return out.getvalue()


def test_l10n_rows():
    with tmpdir() as d, L10nFolder(d):
        write(d, 'items.txt', '# Item names.\n@table 2013A5 maxlen=12\n1\tAlpha\n2\tBravo|Two\n')
        write(d, 'items_short.txt', '# Short names for the list field.\n'
              '@table 2013A5 maxlen=5 sites=200110   # list field\n# own note\n2\tBee\n')
        rows = rows_by_id(l10n.table_rows(SynRom(synthetic_rom())))
        assert sorted(rows) == ['tbl:2013A5:1', 'tbl:2013A5:1:items_short', 'tbl:2013A5:2',
                                'tbl:2013A5:2:items_short', 'tbl:2013A5:3', 'tbl:2013A5:3:items_short']
        own, inh, untr = (rows['tbl:2013A5:%d:items_short' % k] for k in (2, 1, 3))
        assert own['english'] == 'Bee' and own['source'] == 'items_short.txt:4' and own['status'] == 'translated'
        assert own['category'] == 'table:items_short' and own['address'] == '2013A5'
        assert own['context'] == 'list field: table 2013A5 entry 2, copy "items_short" read by the code at 200110'
        assert own['limits'].startswith('at most 5 characters per line')
        assert 'own note' in own['notes'] and 'main table tbl:2013A5:2: Bravo / Two' in own['notes']
        assert inh['english'] == 'Alpha' and inh['source'] == 'items_short.txt' and inh['status'] == 'translated'
        assert 'Short names for the list field.' in inh['notes'] and 'main table tbl:2013A5:1: Alpha' in inh['notes']
        assert 'own entry' in inh['notes']
        assert untr['english'] == '' and untr['status'] == 'untranslated' and '(not translated)' in untr['notes']
        main = rows['tbl:2013A5:2']
        assert main['english'] == 'Bravo\nTwo' and main['source'] == 'items.txt:4'
        assert main['context'] == 'table 2013A5 entry 2 (the copy "items_short" replaces it for the code at 200110)'
        # without the copy file, the main rows are those of a folder without copy tables
        os.remove(os.path.join(d, 'items_short.txt'))
        plain = rows_by_id(l10n.table_rows(SynRom(synthetic_rom())))
        assert sorted(plain) == ['tbl:2013A5:1', 'tbl:2013A5:2', 'tbl:2013A5:3']
        assert plain['tbl:2013A5:2']['context'] == 'table 2013A5 entry 2'
        write(d, 'items_short.txt', '@table 2015C3 sites=200130\n')
        expect(l10n.table_rows, SynRom(synthetic_rom()), contains='copy table 2015C3 has no main table')


def test_l10n_import():
    """Suggestions go to the main table or to the right copy table (own entry
    replaced, inherited entry added, also to a copy without entries); line
    endings kept; an unchanged CSV changes nothing."""
    with tmpdir() as d, L10nFolder(d):
        main = write(d, 'items.txt', '# Item names.\n@table 2013A5 maxlen=12\n1\tAlpha\n2\tBravo\n', newline='\r\n')
        short = write(d, 'items_short.txt', '@table 2013A5 maxlen=5 sites=200110\n2\tBee\n')
        more = write(d, 'z_more.txt', '# A copy with no entries yet.\n@table 2013A5 sites=200120 name=other\n')
        before = {p: open(p, 'rb').read() for p in (main, short, more)}
        rows = l10n.table_rows(SynRom(synthetic_rom()))
        out = import_csv(d, rows, {})
        assert 'dry run' not in out and all(open(p, 'rb').read() == b for p, b in before.items())
        out = import_csv(d, rows, {'tbl:2013A5:1': 'Alfa', 'tbl:2013A5:2:items_short': 'Bvo',
                                   'tbl:2013A5:1:items_short': 'Alf', 'tbl:2013A5:3:other': 'Cha',
                                   'tbl:2013A5:2:other': 'Brv'}, apply=False)
        assert 'dry run: 5 change(s)' in out and all(open(p, 'rb').read() == b for p, b in before.items())
        stale = dict(rows[0], id='tbl:2013A5:2:nope', english='')         # a copy table that is gone
        out = import_csv(d, rows + [stale], {'tbl:2013A5:1': 'Alfa', 'tbl:2013A5:2:items_short': 'Bvo',
                                             'tbl:2013A5:1:items_short': 'Alf', 'tbl:2013A5:3:other': 'Cha',
                                             'tbl:2013A5:2:other': 'Brv', 'tbl:2013A5:2:nope': 'X'})
        assert 'applied 5 change(s)' in out
        assert 'NOT APPLIED tbl:2013A5:2:nope: copy table 2013A5 "nope" has no file' in out
        assert open(main, 'rb').read() == b'# Item names.\r\n@table 2013A5 maxlen=12\r\n1\tAlfa\r\n2\tBravo\r\n'
        assert open(short, 'rb').read() == b'@table 2013A5 maxlen=5 sites=200110\n2\tBvo\n1\tAlf\n'
        assert open(more, 'rb').read() == (b'# A copy with no entries yet.\n@table 2013A5 sites=200120 name=other\n'
                                           b'2\tBrv\n3\tCha\n')            # applied in the CSV's row order
        rows = rows_by_id(l10n.table_rows(SynRom(synthetic_rom())))
        assert [rows[i]['english'] for i in ('tbl:2013A5:1', 'tbl:2013A5:1:items_short', 'tbl:2013A5:2:items_short',
                                             'tbl:2013A5:1:other', 'tbl:2013A5:2:other', 'tbl:2013A5:3:other')] == \
            ['Alfa', 'Alf', 'Bvo', 'Alfa', 'Brv', 'Cha']
        assert rows['tbl:2013A5:1:other']['source'] == 'z_more.txt'
        rom, _, placed = build(d)                           # and the files still build
        assert table_at(rom, by_name(placed, 'other')['start'])[1:] == [enc('Alfa'), enc('Brv'), enc('Cha')]


# ---------------------------------------------------------------------------
# With the original ROM (our own English test entries, the real tables and load sites)

ITEMS, CLASSES = 0x2166B8, 0x20E49D
ITEM_SHORT_SITES = (0x2157F6, 0x20D5CA)                     # Items list, status pane ITEM field
CLASS_SHORT_SITES = (0x20D451, 0x21303C, 0x2C803A, 0x2C8103)


def test_rom_load_sites():
    base = need_rom()
    items = tb.load_refs(base, ITEMS)
    assert len(items) == 11 and all(op == insn + 1 for op, insn in items)
    assert set(ITEM_SHORT_SITES) <= {insn for _, insn in items}
    classes = tb.load_refs(base, CLASSES)
    assert len(classes) == 10 and set(CLASS_SHORT_SITES) <= {insn for _, insn in classes}
    assert tb.load_sites(base, ITEMS) == [op for op, _ in items]
    out = io.StringIO()
    with contextlib.redirect_stdout(out), tmpdir() as d:
        write(d, 'items.txt', '@table 2166B8 prefix=item\n1\tTest Potion\n')
        write(d, 'items_short.txt', '@table 2166B8 sites=2157F6\n')
        tb.main([_ROM['path'], '2166B8', '--folder', d])
    text = out.getvalue()
    assert 'table 2166B8: 11 load sites' in text
    assert [l for l in text.splitlines() if l.strip().startswith('2157F6')][0].endswith('(items_short.txt:1)')
    assert [l for l in text.splitlines() if l.strip().startswith('20745F')][0].endswith('(items.txt:1)')


def test_rom_copy_items():
    base = need_rom()
    with tmpdir() as d:
        write(d, 'items.txt', '@table 2166B8 prefix=item maxlen=15\n1\tTest Potion One\n2\tTest Stone\n3\tTest Bell\n')
        write(d, 'items_short.txt', '@table 2166B8 maxlen=10 sites=%s   # test\n1\tTestPot1\n' %
              ','.join('%06X' % s for s in ITEM_SHORT_SITES))
        lo, hi = layout.region('tables')
        rom, stats, placed = build(d, base, lo, hi)
        main, copy = by_name(placed, None), by_name(placed, 'items_short')
        assert main['start'] == lo and copy['start'] == lo + main['size'] and stats[1:] == (2, 4)
        for op, insn in tb.load_refs(base, ITEMS):
            assert ptr(rom, insn) == (copy['start'] if insn in ITEM_SHORT_SITES else main['start']), '%06X' % insn
        orig = tb.read_table(base, ITEMS)
        got_main, got_copy = table_at(rom, main['start']), table_at(rom, copy['start'])
        assert len(got_main) == len(got_copy) == len(orig)
        pre = [tb.entry_prefix({'prefix': 'item'}, e) for e in orig]
        assert got_copy[1] == orig[1][:pre[1]] + enc('TestPot1')          # item data kept, own text
        assert got_copy[2] == got_main[2] == orig[2][:pre[2]] + enc('Test Stone')
        assert got_main[1] == orig[1][:pre[1]] + enc('Test Potion One')
        assert got_copy[4:] == got_main[4:] == orig[4:]                   # not translated: original bytes
        layout.check(base, rom)
        write(d, 'items_short.txt', '@table 2166B8 maxlen=8 sites=2157F6,20D5CA\n1\tTestPot1\n')
        expect(build, d, base, lo, hi, contains=('items.txt:3 (entry 2, inherited', "'Test Stone' is longer than 8"))


def test_rom_copy_classes():
    base = need_rom()
    with tmpdir() as d:
        write(d, 'classes.txt', '@table 20E49D\n1\tTest Fighter\n10\tTest Samurai Master\n')
        write(d, 'classes_short.txt', '@table 20E49D maxlen=8 sites=%s\n1\tFighter\n10\tSamuraiM\n' %
              ','.join('%06X' % s for s in CLASS_SHORT_SITES))
        lo, hi = layout.region('tables')
        rom, stats, placed = build(d, base, lo, hi)
        main, copy = by_name(placed, None), by_name(placed, 'classes_short')
        full = sorted(insn for _, insn in tb.load_refs(base, CLASSES) if insn not in CLASS_SHORT_SITES)
        assert full == [0x2057BC, 0x2061AA, 0x20624E, 0x21312F, 0x2E3785, 0x2E4B84]
        assert all(ptr(rom, s) == main['start'] for s in full)
        assert all(ptr(rom, s) == copy['start'] for s in CLASS_SHORT_SITES)
        assert table_at(rom, copy['start'])[10] == enc('SamuraiM')
        assert table_at(rom, main['start'])[10] == enc('Test Samurai Master')
        layout.check(base, rom)


def test_rom_translation_folder():
    """The real translation/en/tables builds; each table's load sites point at it."""
    base = need_rom()
    lo, hi = layout.region('tables')
    rom, (used, ntab, _), placed = build(tb.TABLES_DIR, base, lo, hi)
    written = [p for p in placed if p['start'] is not None]
    assert ntab == len(written) and used == sum(p['size'] for p in written)
    assert sorted(op for p in placed for op in p['sites']) == sorted(
        op for T in {p['addr'] for p in placed} for op, _ in tb.load_refs(base, T))
    for p in written:
        assert all(ptr(rom, op - 1) == p['start'] for op in p['sites'])
        assert len(table_at(rom, p['start'])) == len(tb.read_table(base, p['addr']))
    layout.check(base, rom)


# Load sites whose names end up in fixed cells (8 at the narrowest: every original name has at most 8
# characters) and load sites that must keep the full English names (VWF lists and messages, item data).
NAMES = 0x20FCEA
FIXED_FIELD_SITES = {
    ITEMS: (0x2157F6, 0x20D5CA, 0x2E55A0),   # Items list, status pane ITEM, link/versus item getter
    CLASSES: (0x20D451, 0x21303C, 0x2C803A, 0x2C8103, 0x2E3785),
    NAMES: (0x20CCAB, 0x2E3774),             # name getter 0x20CC9A (every name field), link overview
}
FULL_NAME_SITES = {
    ITEMS: (0x20745F, 0x20939D, 0x20D077, 0x21596A, 0x215A31, 0x215B8B, 0x215D96, 0x215E96),
    CLASSES: (0x20624E, 0x21312F, 0x2E4B84,   # class change confirmations, link "was received"
              0x2061AA, 0x2057BC),            # unit window class list, recruit list (VWF lists)
}


def test_rom_fixed_fields():
    """The real translation folder: each fixed-cell name field reads texts of at most 8 characters;
    the shop list, the messages and the item data read the main tables, which keep the full names."""
    base = need_rom()
    lo, hi = layout.region('tables')
    rom, _, placed = build(tb.TABLES_DIR, base, lo, hi)
    mains = {p['addr']: p['start'] for p in placed if p['name'] is None}

    def texts(T, addr):
        pre = {'prefix': 'item' if T == ITEMS else 0}
        return [e[tb.entry_prefix(pre, e):] for e in table_at(rom, addr)]

    for T, sites in sorted(FIXED_FIELD_SITES.items()):
        for s in sites:
            long = [(k, t) for k, t in enumerate(texts(T, ptr(rom, s))) if len(t) > 8]
            assert not long, '%06X (table %06X) reads %d texts longer than 8 characters, e.g. entry %d' % (
                s, T, len(long), long[0][0])
    for T, sites in sorted(FULL_NAME_SITES.items()):
        assert any(len(t) > 8 for t in texts(T, mains[T])), '%06X: no full names left' % T
        for s in sites:
            assert ptr(rom, s) == mains[T], '%06X should read the main table %06X' % (s, T)


def test_rom_l10n_roundtrip():
    from ..recomp.rom import Rom
    need_rom()
    rom = Rom(_ROM['path'])
    with tmpdir() as d, L10nFolder(d):
        write(d, 'items.txt', '@table 2166B8 prefix=item maxlen=15\n1\tTest Potion One\n2\tTest Stone\n',
              newline='\r\n')
        write(d, 'items_short.txt', '@table 2166B8 maxlen=10 sites=2157F6,20D5CA   # Items list, ITEM field\n'
              '1\tTestPot1\n')
        rows = l10n.table_rows(rom)
        ids = rows_by_id(rows)
        n = len(tb.read_table(rom.data, ITEMS))
        copy_rows = [r for r in rows if r['id'].endswith(':items_short')]
        main_rows = [r for r in rows if r['category'] == 'table:items']
        assert len(copy_rows) == len(main_rows) and n - 1 <= len(copy_rows) <= n
        assert ids['tbl:2166B8:1:items_short']['context'].startswith('Items list, ITEM field: table 2166B8 entry 1')
        assert ids['tbl:2166B8:2:items_short']['english'] == 'Test Stone'
        assert ids['tbl:2166B8:3:items_short']['status'] == 'untranslated'
        import_csv(d, rows, {'tbl:2166B8:2:items_short': 'TestSt2', 'tbl:2166B8:1:items_short': 'TestP1'})
        ids = rows_by_id(l10n.table_rows(rom))
        assert ids['tbl:2166B8:2:items_short']['english'] == 'TestSt2'
        assert ids['tbl:2166B8:2:items_short']['source'] == 'items_short.txt:3'
        assert (ids['tbl:2166B8:1:items_short']['english'], ids['tbl:2166B8:2']['english']) == ('TestP1', 'Test Stone')
        assert open(os.path.join(d, 'items.txt'), 'rb').read().count(b'\r\n') == 3


TESTS = [test_parse_header, test_read_table_file, test_group_tables, test_no_copies_layout,
         test_copy_merge_and_repoint, test_copy_limits, test_copy_options, test_copy_sites,
         test_copies_take_every_site, test_no_folder, test_l10n_rows, test_l10n_import,
         test_rom_load_sites, test_rom_copy_items, test_rom_copy_classes, test_rom_translation_folder,
         test_rom_fixed_fields, test_rom_l10n_roundtrip]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    only = None
    if '-k' in argv:
        i = argv.index('-k')
        only = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if argv:
        _ROM['path'] = argv[0]
        if not os.path.exists(argv[0]):
            print('error: no ROM at %s' % argv[0])
            return 1
    failed = skipped = run = 0
    for test in TESTS:
        if only and only not in test.__name__:
            continue
        run += 1
        t0 = time.time()
        try:
            test()
        except Skip as e:
            skipped += 1
            print('skip %s (%s)' % (test.__name__, e))
        except Exception:
            failed += 1
            print('FAIL %s' % test.__name__)
            traceback.print_exc()
        else:
            print('ok   %s (%.2f s)' % (test.__name__, time.time() - t0))
    print('%d tests, %d failed, %d skipped' % (run, failed, skipped))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
