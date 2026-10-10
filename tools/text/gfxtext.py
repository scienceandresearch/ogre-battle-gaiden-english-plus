"""English text that the game shows as pre-drawn graphics.

The text lives in translation/en/ (drawn into tiles by tools/gfx at build
time): labels.txt (menu labels), intro.txt (intro narration), cards.txt
(chapter title cards), title.txt (title logo and warning window) and tags.txt
(small status tags). This module reads those files item by item for the
localization database (tools/text/l10n.py) and writes reviewed suggestions
back into them.

Item ids:
  gfx:labels:NN          menu label NN (hex, 00-2C)
  gfx:intro:N            line N (1-15...) of the intro narration
  gfx:cards:SET:N:head   heading line of card N of SET (story or area)
  gfx:cards:SET:N:K      title line K (1 or 2) of that card
  gfx:title:KEY          kicker, logo, subtitle, window:1, window:2, yes, no
  gfx:tags:KEY           deployed, paralysis

The Japanese wording of pre-drawn art is not text in the ROM, so the database
takes it from an optional local file, build/l10n/gfx_source.tsv (id, Japanese,
meaning; never committed), made from the graphics workstreams' reports:

    python -m tools.text.gfxtext list
    python -m tools.text.gfxtext source REPORT.json [REPORT.json ...] [-o FILE]

REPORT.json: the round-1 graphics workflow result (targets' 'text_shown'
lists: original, meaning, proposed English) or the round-2 survey result
('new_targets'); see build/handoff/ in a working copy.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
EN = os.path.join(ROOT, 'translation', 'en')
SOURCE_TSV = os.path.join(ROOT, 'build', 'l10n', 'gfx_source.tsv')

FILES = ('labels', 'intro', 'cards', 'title', 'tags')


class GfxTextError(Exception):
    pass


class Item:
    """One replaceable line: `prefix` + `text` on line `line` (1-based) of `path`."""
    def __init__(self, iid, path, line, prefix, text, context, limits, notes=(), editable=True):
        self.id, self.path, self.line = iid, path, line
        self.prefix, self.text = prefix, text
        self.context, self.limits = context, limits
        self.notes = list(notes)
        self.editable = editable


def _read(path):
    with open(path, encoding='utf-8', newline='') as f:
        data = f.read()
    nl = '\r\n' if '\r\n' in data else '\n'
    return data.split(nl), nl


def _labels(path):
    lines, _ = _read(path)
    items, last = [], None
    for n, line in enumerate(lines, 1):
        if line.startswith('# (') and last is not None:     # note under an entry
            last.notes.append(line[2:].strip())
            continue
        m = re.match(r'@([0-9A-Fa-f]{2})(\s+)(.*)$', line)
        if not m:
            if not line.startswith('#'):
                last = None
            continue
        nn, text = m.group(1).upper(), m.group(3)
        last = None
        if text.strip() == 'keep':
            continue
        last = Item('gfx:labels:%s' % nn, path, n, line[:m.start(3)], text,
                    'menu label %s (64x8-px picture under an icon bar)' % nn,
                    'at most 64 px in the vwf8 font with its 1-px outline (python -m tools.gfx.labels fit)')
        items.append(last)
    return items


def _intro(path):
    lines, _ = _read(path)
    items, para, k, blank = [], 1, 0, False
    for n, line in enumerate(lines, 1):
        if line.startswith('#'):
            continue
        if not line.strip():
            blank = bool(items)
            continue
        if blank:
            para, k, blank = para + 1, 0, False
        k += 1
        items.append(Item('gfx:intro:%d' % (len(items) + 1), path, n, '', line,
                          'intro narration (crawl before the title), paragraph %d, line %d' % (para, k),
                          'at most 144 px in the title16 font with its outline (python -m tools.gfx.intro fit); '
                          'paragraphs of 6, 6 and 3 lines keep the original layout and timing'))
    return items


def _cards(path):
    lines, _ = _read(path)
    items, card, k = [], None, 0
    for n, line in enumerate(lines, 1):
        if line.startswith('#') or not line.strip():
            continue
        m = re.match(r'\[(story|area)\s+(\d+)\]\s*$', line)
        if m:
            card, k = (m.group(1), int(m.group(2))), 0
            continue
        if card is None or re.match(r'same\s+\d+\s*$', line):
            continue
        what = ('the first time chapter %d is played' % card[1] if card[0] == 'story'
                else 'when cleared chapter %d is played again' % card[1])
        lim = 'at most 158 px in the title16 font with its outline (python -m tools.gfx.cards fit)'
        if line.startswith('^'):
            items.append(Item('gfx:cards:%s:%d:head' % card, path, n, '^', line[1:],
                              'chapter title card (%s %d, shown %s): heading' % (card[0], card[1], what), lim))
        else:
            k += 1
            items.append(Item('gfx:cards:%s:%d:%d' % (card[0], card[1], k), path, n, '', line,
                              'chapter title card (%s %d, shown %s): title line %d' % (card[0], card[1], what, k),
                              lim + '; one heading and at most two title lines'))
    return items


_TITLE_INFO = {
    'kicker': ('title screen logo: small line above the main title',
               'drawn as art in assets/gfx/title/ (python -m tools.gfx.title draft); a change needs new art', False),
    'logo': ('title screen logo: main title, fire part | white part',
             'drawn as art in assets/gfx/title/ (python -m tools.gfx.title draft); a change needs new art', False),
    'subtitle': ('title screen logo: subtitle',
                 'drawn as art in assets/gfx/title/ (python -m tools.gfx.title draft); a change needs new art', False),
    'window': ('title screen warning window (NewGame or Load while suspend data exists): line %d',
               'at most 144 px in the vwf8 font (18 cells)', True),
    'yes': ('title screen warning window: the Yes answer', 'at most 40 px in the vwf8 font', True),
    'no': ('title screen warning window: the No answer', 'at most 56 px in the vwf8 font', True),
}

_TAGS_INFO = {
    'deployed': ('status tag on the organize status pane of a unit deployed on the stage map',
                 'at most 30 px of capitals inside the original box (assets/gfx/tags/caps6.txt)'),
    'paralysis': ('label over a combatant hit by a paralysing attack in battle',
                  'at most 16 px of capitals (16x8-px picture)'),
}


def _keyed(path, which):
    lines, _ = _read(path)
    items, seen = [], {}
    for n, line in enumerate(lines, 1):
        m = re.match(r'@([a-z]+)(\s+)(.*)$', line)
        if not m:
            continue
        key, text = m.group(1), m.group(3)
        if which == 'title':
            ctx, lim, editable = _TITLE_INFO.get(key, ('title screen: %s' % key, '', True))
            if key == 'window':
                seen[key] = seen.get(key, 0) + 1
                iid, ctx = 'gfx:title:window:%d' % seen[key], ctx % seen[key]
            else:
                iid = 'gfx:title:%s' % key
        else:
            ctx, lim = _TAGS_INFO.get(key, ('status tag %s' % key, ''))
            editable, iid = True, 'gfx:tags:%s' % key
            if text.strip() == 'keep':
                continue
        items.append(Item(iid, path, n, line[:m.start(3)], text, ctx, lim, editable=editable))
    return items


def read_items(folder=EN):
    """Every item of the graphics text files that exist, in file order."""
    out = []
    for name in FILES:
        path = os.path.join(folder, name + '.txt')
        if not os.path.exists(path):
            continue
        if name == 'labels':
            out += _labels(path)
        elif name == 'intro':
            out += _intro(path)
        elif name == 'cards':
            out += _cards(path)
        else:
            out += _keyed(path, name)
    return out


def read_source(path=SOURCE_TSV):
    """{id: (japanese, meaning)} from the optional local source file."""
    src = {}
    if not os.path.exists(path):
        return src
    with open(path, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 2 and parts[0].startswith('gfx:'):
                src[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else '')
    return src


def find(iid, text, folder=EN):
    """The item `iid`, checked for a one-line replacement `text`. Raises GfxTextError."""
    if '\n' in text:
        raise GfxTextError('%s is one line; drop the line break' % iid)
    item = next((i for i in read_items(folder) if i.id == iid), None)
    if item is None:
        raise GfxTextError('%s: no such item in translation/en' % iid)
    if not item.editable:
        raise GfxTextError('%s is drawn as art: change the art and the text by hand (%s)' % (iid, item.limits))
    return item


def replace(iid, text, folder=EN):
    """Write a reviewed suggestion for item `iid` into its file. Returns
    'file:line'. Raises GfxTextError."""
    item = find(iid, text, folder)
    lines, nl = _read(item.path)
    lines[item.line - 1] = item.prefix + text
    with open(item.path, 'w', encoding='utf-8', newline='') as f:
        f.write(nl.join(lines))
    return '%s:%d' % (os.path.relpath(item.path, ROOT).replace(os.sep, '/'), item.line)


# ---------------------------------------------------------------------------
# Local source file from the graphics reports
# ---------------------------------------------------------------------------

def _plain(s):
    """'text (description)' -> 'text'."""
    return re.sub(r'\s*\([^)]*\)\s*$', '', s).strip()


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower().replace('…', '').replace('...', ''))


def source_rows(reports, items):
    """[(id, japanese, meaning)] from report JSON objects."""
    rows = []
    by_text = {}
    for it in items:
        if it.id.startswith('gfx:cards:'):
            by_text.setdefault(_norm(it.text), []).append(it.id)
    for rep in reports:
        if isinstance(rep, list):           # round-2 wave-1 result: [{task, result, review}]
            for entry in rep:
                r = entry.get('result') if isinstance(entry, dict) else None
                for nt in (r or {}).get('new_targets', []) or []:
                    key = {'deployed-tag': 'deployed', 'paralysis-label': 'paralysis'}.get(nt.get('name'))
                    if key:
                        rows.append(('gfx:tags:%s' % key, '', nt.get('meaning', '')))
            continue
        res = rep.get('result', rep)
        targets = res.get('reports', []) if isinstance(res, dict) else []
        for t in targets:
            name = t.get('target', '').lower()
            shown = t.get('text_shown', [])
            if name.startswith('title'):
                kind = 'title'
            elif name.startswith('intro'):
                kind = 'intro'
            elif name.startswith('chapter'):
                kind = 'cards'
            elif 'label' in name:
                kind = 'labels'
            else:
                continue
            if kind == 'labels':
                for i, s in enumerate(shown):
                    m = re.search(r'0x([0-9A-Fa-f]{2})', s.get('space', ''))
                    nn = m.group(1).upper() if m else '%02X' % i
                    rows.append(('gfx:labels:%s' % nn, _plain(s['original']), s.get('meaning', '')))
            elif kind == 'intro':
                for i, s in enumerate(shown):
                    rows.append(('gfx:intro:%d' % (i + 1), _plain(s['original']), s.get('meaning', '')))
            elif kind == 'cards':
                for s in shown:
                    ja_parts = [_plain(p) for p in s['original'].split(' / ')]
                    en_parts = [_plain(p) for p in s.get('proposed_english', '').split(' / ')]
                    meaning = s.get('meaning', '')
                    if len(ja_parts) == 2 and len(en_parts) >= 2:
                        for iid in by_text.get(_norm(en_parts[0]), []):
                            if iid.endswith(':head'):
                                rows.append((iid, ja_parts[0], meaning))
                        # the title may span several English lines: every title line of
                        # the card whose first title line matches gets the Japanese title
                        for iid in by_text.get(_norm(en_parts[1]), []):
                            if iid.endswith(':1'):
                                card = iid.rsplit(':', 1)[0]
                                for other in sorted(set(x for v in by_text.values() for x in v)):
                                    if other.startswith(card + ':') and not other.endswith(':head'):
                                        rows.append((other, ja_parts[1], meaning))
                    else:
                        for iid in by_text.get(_norm(en_parts[0]), []):
                            rows.append((iid, ja_parts[0], meaning))
            elif kind == 'title':
                for s in shown:
                    orig = s['original']
                    if 'warning' in orig:
                        parts = [_plain(p) for p in re.split(r'\s*/\s*', _plain(orig))]
                        for iid, p in zip(('gfx:title:window:1', 'gfx:title:window:2', 'gfx:title:yes',
                                           'gfx:title:no'), parts):
                            rows.append((iid, p, s.get('meaning', '')))
                    elif 'subtitle' in orig:
                        rows.append(('gfx:title:subtitle', _plain(orig), s.get('meaning', '')))
                    elif 'fire' in orig:
                        rows.append(('gfx:title:kicker', _plain(orig), s.get('meaning', '')))
                        rows.append(('gfx:title:logo', _plain(orig), s.get('meaning', '')))
                    elif 'white' in orig:
                        rows.append(('gfx:title:logo:white', _plain(orig), s.get('meaning', '')))
    # merge the logo's two parts into one row
    merged, white = [], {r[0]: r for r in rows}.get('gfx:title:logo:white')
    for r in rows:
        if r[0] == 'gfx:title:logo:white':
            continue
        if r[0] == 'gfx:title:logo' and white:
            r = (r[0], r[1] + ' | ' + white[1], r[2] + ' | ' + white[2])
        merged.append(r)
    seen, out = set(), []
    for r in merged:
        if r[0] not in seen:
            seen.add(r[0])
            out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser(prog='python -m tools.text.gfxtext')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list', help='list the items of the graphics text files')
    s = sub.add_parser('source', help='write the local source file from graphics reports')
    s.add_argument('reports', nargs='+')
    s.add_argument('-o', '--out', default=SOURCE_TSV)
    args = ap.parse_args()
    items = read_items()
    if args.cmd == 'list':
        for it in items:
            print('%-24s %s' % (it.id, it.text))
        print('%d items' % len(items))
        return
    reports = [json.load(open(p, encoding='utf-8')) for p in args.reports]
    rows = source_rows(reports, items)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# id\tjapanese\tmeaning  (local only: holds text from the game, never commit)\n')
        for r in rows:
            f.write('\t'.join(x.replace('\t', ' ').replace('\n', ' ') for x in r) + '\n')
    known = {it.id for it in items}
    print('wrote %d rows to %s (%d match an item; %d items without a source)' % (
        len(rows), os.path.relpath(args.out, ROOT), sum(1 for r in rows if r[0] in known),
        len(known - {r[0] for r in rows})))


if __name__ == '__main__':
    main()
