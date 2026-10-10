"""Localization database: every Japanese string of the game next to its English
translation, for translators and linguist review.

    python -m tools.text.l10n export rom/baserom.ngc [--out build/l10n]
        -> build/l10n/l10n.sqlite   table `strings`, one row per string
           build/l10n/strings.csv   the same rows (UTF-8; Excel, LibreOffice,
                                    Google Sheets)
    python -m tools.text.l10n import REVIEW.csv [--apply] [--reviewer NAME]
        applies reviewed suggestions to translation/en/ (dry run without --apply)

The English side lives in translation/en/ and stays the source of truth; the
database is regenerated from it (and from your ROM) on every export and is
never edited directly. The export contains the Japanese text from your ROM, so
it stays in build/ (git-ignored): do not commit it, and share it only with
people who own the game.

Columns
  id            stable key: dlg:ADDR (dialogue message), ui:ADDR (window/menu
                string drawn from ROM), ui:ADDR:inplace (same string written over
                the original bytes), sym:NAME (text for a code patch), tbl:ADDR:N
                (entry N of a packed table), tbl:ADDR:N:NAME (entry N of the copy
                table NAME: the table's version for some fields, see
                tools/text/tables.py), loc:STAGE:N (location name),
                loctype:N (town-type phrase), raw:ADDR (unverified text-like bytes),
                gfx:FILE:KEY (text drawn as a picture: menu labels, intro,
                chapter cards, title, tags; see tools/text/gfxtext.py),
                ram:ADDR (text composed in RAM and drawn by the code at ADDR,
                found in the runtime text logs)
  category      dialogue, ui, symbol, table:<file>, location, location-type,
                graphic:<file>, composed, unverified
  context       where it appears (stage, speaker, renderer, table, ...)
  address       ROM address of the original text
  japanese      original text (new lines as line breaks; [NAME] and [NUM] are
                inserted by the game, ' ' is the game's space)
  english       current translation ('' = not translated yet)
  displayed     dialogue: the English as wrapped on screen (pages split by '---')
  limits        what the English must fit (see translation/en/ files)
  status        translated, untranslated or unverified
  source        file:line of the English text
  notes         translator comments (# lines above the entry) and review notes
  suggested_english, reviewer, reviewer_comment
                empty columns for the reviewer

Review workflow: export, give strings.csv to the reviewer, who fills the last
three columns (a suggestion in suggested_english, a remark in reviewer_comment,
or both) and returns the file. `import` shows every change it would make;
with --apply it writes the suggestions into translation/en/ and appends the
comments to translation/en/review_notes.txt (id, date, reviewer, comment), which
later exports show in `notes`. Rebuild afterwards: the build checks that
every string still fits. Review comments should be in English and must not
quote the Japanese text (the repository has to stay free of ROM text).
"""
import argparse
import csv
import datetime
import os
import re
import sqlite3
import sys

from ..recomp.rom import Rom, ROM_BASE
from .charmap import decode_bytes

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
EN = os.path.join(ROOT, 'translation', 'en')
SCRIPT_TXT = os.path.join(EN, 'script.txt')
UI_TXT = os.path.join(EN, 'ui.txt')
TABLES_DIR = os.path.join(EN, 'tables')
LOCATIONS_TXT = os.path.join(EN, 'locations.txt')
NOTES_TXT = os.path.join(EN, 'review_notes.txt')
NOT_TEXT_TXT = os.path.join(EN, 'not_text.txt')

COLUMNS = ['id', 'category', 'context', 'address', 'japanese', 'english', 'displayed', 'limits',
           'status', 'source', 'notes', 'suggested_english', 'reviewer', 'reviewer_comment']


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, '/')


def ja(bs):
    """Decode original text bytes (without terminator) for display."""
    while bs.endswith(b'\x00'):
        bs = bs[:-1]
    return decode_bytes(bs)


# ---------------------------------------------------------------------------
# English sources (with positions, so suggestions can be written back)
# ---------------------------------------------------------------------------

_DIVIDER = re.compile(r'^#\s*[-=]{3}')


def _blocks(lines):
    """A comment block (list of lines) as one paragraph."""
    return [' '.join(lines)] if lines else []


class Entry:
    """One '@HEADER' entry of script.txt / ui.txt."""
    def __init__(self, path, header, body, line, span, notes, section):
        self.path, self.header, self.body = path, header, body
        self.line, self.span = line, span          # header line number, body line indexes [a, b)
        self.notes, self.section = notes, section


def read_entries(path, comments_in_body):
    """Entries of a '@HEADER / lines / blank line' file. Comment blocks above an
    entry become its notes (and stay attached to the following entries until
    the next comment block); '# ---' lines name the section."""
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')
    out = []
    notes, section, fresh = [], '', False
    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\r')
        if line.startswith('@'):
            j = i + 1
            while j < len(lines) and lines[j].rstrip('\r') != '':
                j += 1
            body = [l.rstrip('\r') for l in lines[i + 1:j]]
            if not comments_in_body:
                body = [l for l in body if not l.startswith('#')]
            out.append(Entry(path, line[1:].split(), body, i + 1, (i + 1, j), _blocks(notes), section))
            fresh = False
            i = j
            continue
        if line.startswith('#'):
            if _DIVIDER.match(line):
                section = line.lstrip('#').strip().strip('-= ').strip()
                notes, fresh = [], False
            else:
                if not fresh:
                    notes, fresh = [], True
                notes.append(line.lstrip('#').strip())
        elif line.strip() == '':
            fresh = False
        i += 1
    return out


def read_line_file(path):
    """'@section' + 'INDEX<TAB>TEXT' files (tables/*.txt, locations.txt):
    ([(section header words, index, text, line number, notes)],
     {line number of an '@' line: the notes that cover its section})."""
    out, sections = [], {}
    section, section_notes, notes, fresh = None, [], [], False
    with open(path, encoding='utf-8') as f:
        for n, raw in enumerate(f, 1):
            line = raw.rstrip('\r\n')
            if line.startswith('#'):
                if not _DIVIDER.match(line):
                    if not fresh:
                        notes, fresh = [], True
                    notes.append(line.lstrip('#').strip())
                continue
            fresh = False
            if not line.strip():
                continue
            if line.startswith('@'):
                section = line[1:].split()
                section_notes, notes = notes, []    # a comment block above '@' covers the section
                sections[n] = _blocks(section_notes)
                continue
            if '\t' in line:
                idx, text = line.split('\t', 1)
                out.append((section, int(idx), text, n, _blocks(section_notes) + _blocks(notes)))
    return out, sections


def read_line_entries(path):
    """'@section' + 'INDEX<TAB>TEXT' files (tables/*.txt, locations.txt):
    [(section header words, index, text, line number, notes)]."""
    return read_line_file(path)[0]


def read_not_text():
    """ids the scans find that need no translation (translation/en/not_text.txt)."""
    ids = set()
    if os.path.exists(NOT_TEXT_TXT):
        with open(NOT_TEXT_TXT, encoding='utf-8') as f:
            for raw in f:
                if raw.strip() and not raw.startswith('#'):
                    ids.add(raw.split('\t')[0].strip())
    return ids


def read_review_notes():
    notes = {}
    if os.path.exists(NOTES_TXT):
        with open(NOTES_TXT, encoding='utf-8') as f:
            for raw in f:
                if raw.startswith('#') or not raw.strip():
                    continue
                parts = raw.rstrip('\r\n').split('\t')
                if len(parts) >= 4:
                    notes.setdefault(parts[0], []).append('%s (%s, %s)' % (parts[3], parts[2], parts[1]))
    return notes


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def speaker(text):
    m = re.match(r'^([^\n\u300e]{1,12})\u300e', text)
    return m.group(1) if m else ''


def dialogue_rows(rom, w):
    from .dump import stage_ranges, context
    from .layout import paginate, line_width_for
    entries = {int(e.header[0], 16): e for e in read_entries(SCRIPT_TXT, False)}
    starts = stage_ranges(rom)
    rows = []
    for a, i in w.strings():
        text = ja(i.text)
        e = entries.get(a)
        en = '\n'.join(e.body) if e else ''
        width = line_width_for(a)
        shown = ''
        if en:
            try:
                shown = '\n---\n'.join('\n'.join(p) for p in paginate(en, width))
            except ValueError as ex:
                shown = 'LAYOUT ERROR: %s' % ex
        ctx = context(starts, a)
        sp = speaker(text)
        rows.append({
            'id': 'dlg:%06X' % a, 'category': 'dialogue',
            'context': ctx + (', speaker ' + sp if sp else '') + (', yes/no question' if i.term == 0xFC else ''),
            'address': '%06X' % a, 'japanese': text, 'english': en, 'displayed': shown,
            'limits': 'variable-width font, %d px per line, 3 lines per page; one page '
                      'like the original where possible' % width,
            'status': 'translated' if en else 'untranslated',
            'source': '%s:%d' % (rel(SCRIPT_TXT), e.line) if e else '',
            'notes': ' | '.join(x for x in ([e.section] if e and e.section else []) + (e.notes if e else []) if x),
        })
    return rows


def ui_limits(mode, opts, orig_bs):
    from .uitext import shape
    if mode == 'inplace':
        if 'len' in opts:
            return 'written over the original bytes: exactly %d bytes (padded with spaces)' % opts['len']
        n = len(orig_bs) - 2
        return 'written over the original bytes: at most %d characters%s' % (
            n, ', padded to that width' if opts.get('fixedwidth') else '')
    lines, width, chars = shape(orig_bs)
    w = opts.get('width', width)
    l = opts.get('lines', lines)
    if mode == 'vwf':
        t = opts.get('tiles', max(chars, 36) if opts.get('sysmsg') else chars)
        extra = ''
        if 'cells' in opts:
            extra = ' (also printed in fixed cells: at most %d characters per line)' % opts['cells']
        return 'variable-width font: at most %d px per line, %d lines, %d tiles%s' % (8 * w, l, t, extra)
    if opts.get('uiprint'):
        return 'fixed 8x8 font: at most %d characters per line, %d lines' % (w, l)
    t = opts.get('tiles', chars)
    return 'fixed 8x8 font: at most %d characters per line, %d lines, %d letters' % (w, l, t)


def ui_rows(rom, w, scorer):
    from .uitext import original_string, read_ui, UiError
    from .uiscan import code_refs, script_refs, window_string
    base = rom.data
    parsed = {}
    for e in read_ui(UI_TXT):
        parsed[(e.addr, e.mode == 'inplace')] = e
    raw = {}
    for e in read_entries(UI_TXT, True):
        name = e.header[0]
        raw[(name, 'inplace' in e.header)] = e
    rows, covered = [], []
    for (key, inplace), e in sorted(raw.items(), key=lambda kv: (kv[0][0].startswith('='), kv[0][0])):
        if key.startswith('='):
            pe = parsed.get((key[1:], False)) or parsed.get((key[1:], True))
            origs = pe.opts.get('origs', []) if pe else []
            jtext, addr = '', ''
            for k, (a, n) in enumerate(origs):
                bs = bytes(base[a - ROM_BASE:a - ROM_BASE + n]) if n else window_string(rom, a) or b''
                if k == 0:
                    jtext, addr = ja(bs), '%06X' % a
                covered.append((a, a + max(1, len(bs))))
            rows.append({
                'id': 'sym:' + key[1:], 'category': 'symbol', 'context': 'text for a code patch'
                + (' (replaces the original at %s)' % ', '.join('%06X' % a for a, _ in origs) if origs else ''),
                'address': addr, 'japanese': jtext, 'english': '\n'.join(e.body), 'displayed': '',
                'limits': 'see the comment in ui.txt; {XX} is a raw byte ({00} new line)',
                'status': 'translated', 'source': '%s:%d' % (rel(UI_TXT), e.line),
                'notes': ' | '.join([e.section] + e.notes if e.section else e.notes)})
            continue
        a = int(key, 16)
        pe = parsed.get((a, inplace))
        mode = pe.mode if pe else ('inplace' if inplace else 'fixed')
        opts = pe.opts if pe else {}
        try:
            if mode == 'inplace' and 'len' in opts:
                orig = bytes(base[a - ROM_BASE:a - ROM_BASE + opts['len']])
            else:
                orig = original_string(base, a)
        except UiError:
            orig = b''
        covered.append((a, a + max(1, len(orig))))
        how = {'inplace': 'written in place', 'vwf': 'window, variable-width font',
               'fixed': 'window, fixed font'}[mode]
        if opts.get('sysmsg'):
            how = 'system message window, variable-width font'
        elif opts.get('uiprint'):
            how = 'tile-mapped printer, fixed font'
        rows.append({
            'id': 'ui:%06X%s' % (a, ':inplace' if inplace else ''), 'category': 'ui', 'context': how,
            'address': '%06X' % a, 'japanese': ja(orig[:-2] if orig.endswith(b'\x00\x00') else orig),
            'english': '\n'.join(e.body), 'displayed': '', 'limits': ui_limits(mode, opts, orig or b'\x00\x00'),
            'status': 'translated', 'source': '%s:%d' % (rel(UI_TXT), e.line),
            'notes': ' | '.join(x for x in [e.section] + e.notes if x)})
    refs = code_refs(rom, w, scorer)
    for v, l in script_refs(rom, w, scorer).items():
        refs.setdefault(v, []).extend(l)
    for v in sorted(refs):
        if any(lo <= v < hi for lo, hi in covered):
            continue
        bs = window_string(rom, v)
        uses = sorted({u for _, _, u in refs[v] if u})
        rows.append({
            'id': 'ui:%06X' % v, 'category': 'ui',
            'context': 'referenced by code at %s%s' % (
                ', '.join('%06X' % s for s, _, _ in refs[v][:4]), ' (%s)' % ', '.join(uses) if uses else ''),
            'address': '%06X' % v, 'japanese': ja(bs[:-2]), 'english': '', 'displayed': '',
            'limits': ui_limits('fixed', {}, bs), 'status': 'untranslated',
            'source': '', 'notes': ''})
    return rows


def table_limits(t):
    if t.get('maxlen'):
        return 'at most %d characters per line' % t['maxlen']
    if t['vwf']:
        return 'variable-width font: %d px per line, %d lines, %d tiles%s' % (
            8 * t.get('width', 18), t.get('lines', 3), t.get('tiles', 54),
            '; wrapped automatically' if t.get('wrap') else '')
    return 'no fixed limit (check the screens that show it)'


def read_table_files():
    """[(file name, path, tables)] of translation/en/tables/*.txt, with every
    copy table paired with its main table (tables.group_tables)."""
    from .tables import read_table_file, group_tables, TableError
    if not os.path.isdir(TABLES_DIR):
        return []
    try:
        files = [(name, os.path.join(TABLES_DIR, name), read_table_file(os.path.join(TABLES_DIR, name)))
                 for name in sorted(os.listdir(TABLES_DIR)) if name.endswith('.txt')]
        group_tables([t for _, _, tabs in files for t in tabs])
    except TableError as e:
        raise SystemExit('tables: %s' % e)
    return files


def table_rows(rom):
    """One row per entry of every table, main tables (tbl:ADDR:N) and copy
    tables (tbl:ADDR:N:NAME, with the text the copy really has: its own entry
    or the main table's)."""
    from .tables import read_table, entry_prefix
    rows = []
    base = rom.data
    files = read_table_files()
    copies = {}
    for _, _, tabs in files:
        for t in tabs:
            if t['sites'] is not None:
                copies.setdefault(t['addr'], []).append(t)
    for name, path, tabs in files:
        line_entries, sections = read_line_file(path)
        notes_by_line = {(n): nts for _, _, _, n, nts in line_entries}
        for t in tabs:
            T = t['addr']
            orig = read_table(base, T)
            lim = table_limits(t)
            if t['sites'] is not None:
                rows += copy_table_rows(t, orig, name, path, lim, notes_by_line, sections)
                continue
            also = '; '.join('the copy "%s" replaces it for the code at %s' % (
                c['name'], ', '.join('%06X' % s for s in c['sites'])) for c in copies.get(T, []))
            for k, e in enumerate(orig):
                prefix = entry_prefix(t, e)
                text, line = t['entries'].get(k, ('', None))
                if not ja(e[prefix:]) and not line:
                    continue                    # empty slot (e.g. entry 0)
                rows.append({
                    'id': 'tbl:%06X:%d' % (T, k), 'category': 'table:' + name[:-4],
                    'context': 'table %06X entry %d' % (T, k) + (' (%s)' % also if also else ''),
                    'address': '%06X' % T,
                    'japanese': ja(e[prefix:]), 'english': text.replace('|', '\n'), 'displayed': '',
                    'limits': lim + "; '|' in the file = new line",
                    'status': 'translated' if line else 'untranslated',
                    'source': '%s:%d' % (rel(path), line) if line else rel(path),
                    'notes': ' | '.join(notes_by_line.get(line, [])) if line else ''})
    return rows


def copy_table_rows(t, orig, name, path, lim, notes_by_line, sections):
    """Rows of a copy table: every entry with the text the copy holds (its
    own entry, or the main table's English, which the notes always show)."""
    from .tables import entry_prefix
    T, m = t['addr'], t['main']
    where = 'copy "%s" read by the code at %s' % (t['name'], ', '.join('%06X' % s for s in t['sites']))
    rows = []
    for k, e in enumerate(orig):
        prefix = entry_prefix(t, e)
        own, inh = t['entries'].get(k), m['entries'].get(k)
        text, line = own or inh or ('', None)
        if not ja(e[prefix:]) and not line:
            continue                            # empty slot (e.g. entry 0)
        main = 'main table tbl:%06X:%d: %s' % (T, k, inh[0].replace('|', ' / ') if inh else '(not translated)')
        if own:
            notes = notes_by_line.get(own[1], []) + [main]
        else:
            notes = sections.get(t['line'], []) + [main + (' (used here too: a suggestion for this row '
                                                           'gives the copy its own entry)' if inh else '')]
        ctx = 'table %06X entry %d, %s' % (T, k, where)
        rows.append({
            'id': 'tbl:%06X:%d:%s' % (T, k, t['name']), 'category': 'table:' + name[:-4],
            'context': '%s: %s' % (t['comment'], ctx) if t['comment'] else ctx, 'address': '%06X' % T,
            'japanese': ja(e[prefix:]), 'english': text.replace('|', '\n'), 'displayed': '',
            'limits': lim + "; '|' in the file = new line",
            'status': 'translated' if line else 'untranslated',
            'source': '%s:%d' % (rel(path), own[1]) if own else rel(path),
            'notes': ' | '.join(notes)})
    return rows


def location_rows(rom):
    from .locations import location_records, record_name, record_type, read_locations, NUM_TYPES
    from .tables import read_table
    base = rom.data
    data = read_locations(LOCATIONS_TXT)
    notes = {(tuple(s) if s else None, i): nts for s, i, _, _, nts in read_line_entries(LOCATIONS_TXT)}
    type_names = read_table(base, 0x273334)
    rows = []
    for k in range(1, NUM_TYPES):
        text, line = data['types'].get(k, ('', None))
        rows.append({
            'id': 'loctype:%d' % k, 'category': 'location-type',
            'context': 'starts the liberated / discovered / lost messages, followed by a '
                       'new line and the location name', 'address': '273334',
            'japanese': ja(type_names[k]), 'english': text, 'displayed': '',
            'limits': 'variable-width font, at most 144 px',
            'status': 'translated' if line else 'untranslated',
            'source': '%s:%d' % (rel(LOCATIONS_TXT), line) if line else rel(LOCATIONS_TXT),
            'notes': ' | '.join(notes.get((('types',), k), []))})
    for s, i, addr in location_records(base):
        text, line = data['names'].get((s, i), ('', None))
        t = record_type(base, addr)
        kind = 'town type %d (%s / "%s")' % (t, ja(type_names[t]), data['types'].get(t, ('', 0))[0]) \
            if t else 'castle, fort or other place without a town type'
        rows.append({
            'id': 'loc:%d:%d' % (s, i), 'category': 'location',
            'context': 'stage %d, %s' % (s, kind),
            'address': '%06X' % addr, 'japanese': ja(record_name(base, addr)), 'english': text,
            'displayed': '', 'limits': 'variable-width font, at most 64 px (town window)',
            'status': 'translated' if line else 'untranslated',
            'source': '%s:%d' % (rel(LOCATIONS_TXT), line) if line else rel(LOCATIONS_TXT),
            'notes': ' | '.join(notes.get((('stage', str(s)), i), []))})
    return rows


SCAN_LO, SCAN_HI = 0x200000, 0x36746D      # program and data; free space follows
def graphic_rows():
    """Text the game shows as pictures (menu labels, intro narration, chapter
    cards, title logo and warning window, status tags): the English from
    translation/en/{labels,intro,cards,title,tags}.txt. The pictures hold no
    text bytes, so the Japanese wording and its meaning come from the optional
    local file build/l10n/gfx_source.tsv (python -m tools.text.gfxtext source)."""
    from .gfxtext import read_items, read_source
    src = read_source()
    rows = []
    for it in read_items():
        jp, meaning = src.get(it.id, ('', ''))
        notes = it.notes + (['meaning: ' + meaning] if meaning else [])
        rows.append({
            'id': it.id, 'category': 'graphic:' + it.id.split(':')[1], 'context': it.context,
            'address': '', 'japanese': jp, 'english': it.text, 'displayed': '', 'limits': it.limits,
            'status': 'translated' if it.text.strip() else 'untranslated',
            'source': '%s:%d' % (rel(it.path), it.line), 'notes': ' | '.join(notes)})
    return rows


TEXTLOG_DIR = os.path.join(ROOT, 'build', 'textlogs')


def runtime_rows(rom, spans):
    """Strings the renderers actually drew in recorded runs of the English build
    (harness --text-log files in build/textlogs/) that nothing covers: ROM
    strings whose address no translation file names, and RAM strings (composed
    by code) that still contain Japanese. ROM sources are read from the
    original ROM, where codes 0x26-0xC5 are all kana; RAM strings hold English
    bytes, where only 0x56-0xC5 are unused by the English encoding."""
    from .textlog import parse
    from .uiscan import window_string
    rows, seen = [], set()
    if not os.path.isdir(TEXTLOG_DIR):
        return rows
    for name in sorted(os.listdir(TEXTLOG_DIR)):
        for frame, kind, src, caller, ix, iz, data in parse(os.path.join(TEXTLOG_DIR, name)):
            if src >= SCAN_HI:                  # our own English strings in free ROM
                continue
            if src >= ROM_BASE:
                if src in seen or any(lo <= src < hi for lo, hi in spans):
                    continue
                bs = window_string(rom, src)
                if not bs or not any(0x26 <= b <= 0xC5 for b in bs):
                    continue
                seen.add(src)
                rows.append({
                    'id': 'ui:%06X' % src, 'category': 'ui',
                    'context': 'drawn at run time (%s renderer, code at %06X; log %s)' % (kind, caller, name),
                    'address': '%06X' % src, 'japanese': ja(bs[:-2]), 'english': '', 'displayed': '',
                    'limits': ui_limits('fixed', {}, bs), 'status': 'untranslated', 'source': '', 'notes': ''})
            else:
                key = ('ram', caller)
                if key in seen or not any(0x56 <= b <= 0xC5 for b in data):
                    continue
                seen.add(key)
                rows.append({
                    'id': 'ram:%06X' % caller, 'category': 'composed',
                    'context': 'composed in RAM %06X and drawn by code at %06X (%s renderer; log %s)'
                               % (src, caller, kind, name),
                    'address': '', 'japanese': ja(data.split(b'\x00\x00')[0]), 'english': '',
                    'displayed': '', 'limits': '', 'status': 'untranslated', 'source': '', 'notes': ''})
    return rows


def known_spans(rom, w):
    """Byte ranges of every string the other categories cover."""
    from .uitext import original_string, read_ui, UiError
    from .tables import read_table_file
    from .locations import location_records
    base = rom.data
    spans = [(a, a + i.length) for a, i in w.strings()]
    for e in read_ui(UI_TXT):
        if e.mode == 'symbol':
            for a, n in e.opts.get('origs', []):
                spans.append((a, a + (n or 1)))
            continue
        try:
            n = e.opts['len'] if 'len' in e.opts else len(original_string(base, e.addr))
        except UiError:
            n = 1
        spans.append((e.addr, e.addr + n))
    tables = [0x273334]
    if os.path.isdir(TABLES_DIR):
        for name in os.listdir(TABLES_DIR):
            if name.endswith('.txt'):
                tables += [t['addr'] for t in read_table_file(os.path.join(TABLES_DIR, name))
                           if t['sites'] is None]       # a copy table covers no other bytes
    for T in tables:                            # offsets + packed entries
        n = rom.read16(T) // 2                  # offsets, including the end marker
        spans.append((T, T + 2 * (n - 1) + rom.read16(T + 2 * (n - 1))))
    for s, i, addr in location_records(base):
        spans.append((addr, addr + 16))
    return spans


def raw_rows(rom, w, scorer, spans, threshold=1.4, min_chars=3):
    """Text-like '00 00'-terminated byte runs that nothing above covers: possible
    UI strings whose use is not known yet (or unused text)."""
    from .charmap import DECODE
    d = rom.data
    covered = bytearray(len(d))
    for a, b in spans:
        covered[max(0, a - ROM_BASE):max(0, b - ROM_BASE)] = b'\x01' * max(0, b - a)
    for a in w.cover:
        if ROM_BASE <= a < ROM_BASE + len(d):
            covered[a - ROM_BASE] = 1
    rows = []
    i, end = SCAN_LO - ROM_BASE, SCAN_HI - ROM_BASE
    while i < end:
        j = i
        while j < end and d[j] < 0xDF and not (d[j] == 0 and d[j + 1] == 0):
            j += 1
        if j < end and d[j] == 0 and d[j + 1] == 0:
            k = i
            while k < j and d[k] in (0, 1):           # leading new lines / spaces
                k += 1
            body = bytes(d[k:j])
            chars = bytes(b for b in body if b not in (0, 1))
            kana = sum(1 for b in chars if 0x26 <= b <= 0xC5)
            if (len(chars) >= min_chars and kana >= 2 and not any(covered[k:j + 2])
                    and all(b in DECODE or b in (0xDD, 0xDE) for b in chars)
                    and scorer.logprob(chars) > threshold):
                rows.append({
                    'id': 'raw:%06X' % (ROM_BASE + k), 'category': 'unverified',
                    'context': 'text-like bytes not tied to known code yet (could also be unused)',
                    'address': '%06X' % (ROM_BASE + k), 'japanese': ja(body), 'english': '',
                    'displayed': '', 'limits': '', 'status': 'unverified', 'source': '', 'notes': ''})
            i = j + 2
        else:
            i = j + 1
    return rows


def collect(rom):
    from .extract import build_walker
    from .textscore import TextScorer
    w = build_walker(rom, log=lambda *a: None)
    scorer = TextScorer([i.text for _, i in w.strings()])
    from .uiscan import window_string
    rows = dialogue_rows(rom, w) + ui_rows(rom, w, scorer) + table_rows(rom) + location_rows(rom)
    rows += graphic_rows()
    spans = known_spans(rom, w)
    for r in rows:
        if r['category'] == 'ui' and r['status'] == 'untranslated':
            a = int(r['address'], 16)
            spans.append((a, a + len(window_string(rom, a) or b'..')))
    rt = runtime_rows(rom, spans)
    for r in rt:
        if r['address']:
            a = int(r['address'], 16)
            spans.append((a, a + len(window_string(rom, a) or b'..')))
    rows += rt + raw_rows(rom, w, scorer, spans)
    skip = read_not_text()
    rows = [r for r in rows if r['id'] not in skip]
    review = read_review_notes()
    for r in rows:
        if r['id'] in review:
            r['notes'] = ' | '.join(x for x in [r['notes']] + ['review: ' + n for n in review[r['id']]] if x)
        for c in ('suggested_english', 'reviewer', 'reviewer_comment'):
            r.setdefault(c, '')
    return rows


def export(rom_path, out):
    rom = Rom(rom_path)
    rows = collect(rom)
    os.makedirs(out, exist_ok=True)
    db = os.path.join(out, 'l10n.sqlite')
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE strings (%s, PRIMARY KEY (id))' % ', '.join('%s TEXT' % c for c in COLUMNS))
    con.executemany('INSERT INTO strings VALUES (%s)' % ', '.join('?' * len(COLUMNS)),
                    [[r[c] for c in COLUMNS] for r in rows])
    con.execute('CREATE TABLE info (key TEXT PRIMARY KEY, value TEXT)')
    con.executemany('INSERT INTO info VALUES (?, ?)', [
        ('exported', datetime.datetime.now().isoformat(timespec='seconds')),
        ('rom_sha1', rom.sha1), ('note', 'Contains text from the original ROM: do not commit or redistribute.')])
    con.commit()
    con.close()
    csv_path = os.path.join(out, 'strings.csv')
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(COLUMNS)
        for r in rows:
            wr.writerow([r[c] for c in COLUMNS])
    counts = {}
    for r in rows:
        k = (r['category'].split(':')[0], r['status'])
        counts[k] = counts.get(k, 0) + 1
    print('wrote %d strings to %s and %s' % (len(rows), rel(db), rel(csv_path)))
    for (cat, st), n in sorted(counts.items()):
        print('  %-14s %-12s %5d' % (cat, st, n))


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def replace_body(path, span, new_lines, cache):
    lines = cache.setdefault(path, open(path, encoding='utf-8').read().split('\n'))
    a, b = span
    cache[path] = lines[:a] + new_lines + lines[b:]
    return len(new_lines) - (b - a)


def apply_suggestion(r, text, cache, shifts):
    """Write one suggestion into its translation file. Returns a description or raises ValueError."""
    rid = r['id']
    kind = rid.split(':')[0]

    def shifted(path, line):
        return line + sum(d for (p, at), d in shifts.items() if p == path and at < line)

    if kind in ('dlg', 'ui', 'sym'):
        path = SCRIPT_TXT if kind == 'dlg' else UI_TXT
        entries = read_entries(path, kind != 'dlg')
        if kind == 'dlg':
            key = rid.split(':')[1]
            match = [e for e in entries if e.header[0].upper() == key]
        elif kind == 'sym':
            match = [e for e in entries if e.header[0] == '=' + rid[4:]]
        else:
            _, addr, *rest = rid.split(':')
            inplace = bool(rest)
            match = [e for e in entries if not e.header[0].startswith('=')
                     and int(e.header[0], 16) == int(addr, 16) and ('inplace' in e.header) == inplace]
        if not match:
            raise ValueError('not in %s yet: add it by hand (choose how it is drawn)' % rel(path))
        e = match[0]
        new_lines = text.split('\n')
        if any(l.strip() == '' for l in new_lines):
            raise ValueError('blank lines would end the entry; use {00} or remove them')
        a, b = e.span
        d = replace_body(path, (shifted(path, a), shifted(path, b)), new_lines, cache)
        shifts[(path, a)] = shifts.get((path, a), 0) + d
        return '%s:%d' % (rel(path), e.line)
    if kind in ('tbl', 'loc', 'loctype'):
        if kind == 'tbl':
            from .tables import read_table_file, parse_header, TableError
            parts = rid.split(':')              # tbl:ADDR:N (main table), tbl:ADDR:N:NAME (copy table)
            if len(parts) not in (3, 4):
                raise ValueError('unknown table id')
            addr, idx, copy = int(parts[1], 16), parts[2], (parts[3] if len(parts) == 4 else None)
            path = None
            try:
                for name in sorted(os.listdir(TABLES_DIR)):
                    p = os.path.join(TABLES_DIR, name)
                    if name.endswith('.txt') and any(t['addr'] == addr and t['name'] == copy
                                                     for t in read_table_file(p)):
                        path = p
                        break
            except TableError as e:
                raise ValueError(str(e))
            if path is None:
                raise ValueError('%s has no file in %s' % (
                    'copy table %06X "%s"' % (addr, copy) if copy else 'table %06X' % addr, rel(TABLES_DIR)))
            key = ('table', addr, copy)
            want = lambda sec, i: sec == key and i == int(idx)
            section_test = lambda sec: sec == key
        else:
            path = LOCATIONS_TXT
            if kind == 'loc':
                _, s, idx = rid.split(':')
                want = lambda sec, i: sec == ['stage', s] and i == int(idx)
                section_test = lambda sec: sec == ['stage', s]
            else:
                idx = rid.split(':')[1]
                want = lambda sec, i: sec == ['types'] and i == int(idx)
                section_test = lambda sec: sec == ['types']
        value = text.replace('\n', '|') if kind == 'tbl' else text
        if kind != 'tbl' and '\n' in text:
            raise ValueError('location names are one line')
        lines = cache.setdefault(path, open(path, encoding='utf-8').read().split('\n'))
        section, header, last_in_section = None, None, None
        for n, line in enumerate(lines):
            if line.startswith('@'):
                section = line[1:].split()
                if section and section[0] == 'table':
                    try:
                        h = parse_header(line, path, n + 1)
                    except TableError as e:
                        raise ValueError(str(e))
                    section = ('table', h['addr'], h['name'])
                if section_test(section):
                    header = n
                continue
            if section_test(section) and '\t' in line and not line.startswith('#'):
                last_in_section = n
                if want(section, int(line.split('\t', 1)[0])):
                    lines[n] = '%s\t%s' % (line.split('\t', 1)[0], value)
                    return '%s:%d' % (rel(path), n + 1)
        if header is None:
            raise ValueError('section not found in %s' % rel(path))
        at = (header if last_in_section is None else last_in_section) + 1   # a section may have no entries yet
        lines.insert(at, '%s\t%s' % (idx, value))
        return '%s:%d (new line)' % (rel(path), at + 1)
    if kind == 'gfx':                       # one line of a graphics text file
        from .gfxtext import find, GfxTextError
        try:
            item = find(rid, text)
        except GfxTextError as e:
            raise ValueError(str(e))
        lines = cache.setdefault(item.path, open(item.path, encoding='utf-8').read().split('\n'))
        lines[item.line - 1] = item.prefix + text
        return '%s:%d (rebuild to redraw the picture)' % (rel(item.path), item.line)
    raise ValueError('suggestions for %s strings are applied by hand' % kind)


def do_import(csv_path, apply, reviewer_default):
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows or 'id' not in rows[0]:
        raise SystemExit('%s: expected a CSV exported by this tool (id column missing)' % csv_path)
    cache, shifts = {}, {}
    changes, notes, errors = 0, [], []
    for r in rows:
        sug = (r.get('suggested_english') or '').replace('\r\n', '\n').strip('\n')
        comment = (r.get('reviewer_comment') or '').replace('\r\n', ' ').replace('\n', ' ').replace('\t', ' ').strip()
        who = (r.get('reviewer') or reviewer_default or 'reviewer').strip()
        if comment:
            notes.append((r['id'], who, comment))
        if not sug or sug == (r.get('english') or '').replace('\r\n', '\n').strip('\n'):
            continue
        try:
            where = apply_suggestion(r, sug, cache, shifts)
            changes += 1
            print('%-22s %s' % (r['id'], where))
            print('    was: %s' % (r.get('english') or '(untranslated)').replace('\n', ' / '))
            print('    now: %s' % sug.replace('\n', ' / '))
        except ValueError as e:
            errors.append('%s: %s' % (r['id'], e))
    for e in errors:
        print('NOT APPLIED ' + e)
    if notes:
        print('%d review comment(s)%s' % (len(notes), '' if apply else ' (would be added to %s)' % rel(NOTES_TXT)))
    if not apply:
        print('dry run: %d change(s); run again with --apply to write them' % changes)
        return
    for path, lines in cache.items():
        with open(path, 'rb') as f:
            nl = '\r\n' if b'\r\n' in f.read() else '\n'     # keep the file's line endings
        with open(path, 'w', encoding='utf-8', newline=nl) as f:
            f.write('\n'.join(lines))
    if notes:
        new = not os.path.exists(NOTES_TXT)
        with open(NOTES_TXT, 'a', encoding='utf-8', newline='\n') as f:
            if new:
                f.write('# Review notes: id<TAB>date<TAB>reviewer<TAB>comment (added by tools/text/l10n.py import).\n'
                        '# English only; do not quote the Japanese text here.\n')
            today = datetime.date.today().isoformat()
            for rid, who, comment in notes:
                f.write('%s\t%s\t%s\t%s\n' % (rid, today, who, comment))
    print('applied %d change(s); rebuild to check that everything still fits' % changes)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    ex = sub.add_parser('export')
    ex.add_argument('rom')
    ex.add_argument('--out', default=os.path.join(ROOT, 'build', 'l10n'))
    im = sub.add_parser('import')
    im.add_argument('csv')
    im.add_argument('--apply', action='store_true')
    im.add_argument('--reviewer', default='')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    if args.cmd == 'export':
        export(args.rom, args.out)
    else:
        do_import(args.csv, args.apply, args.reviewer)


if __name__ == '__main__':
    main()
