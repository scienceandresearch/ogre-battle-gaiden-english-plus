"""Chapter saves for the release package: cartridge saves made from test states.

    python -m tools.release.catalog [--recipe tools/release/catalog.txt] [--states build/states]
        [--rom rom/baserom.ngc] [--english build/ogre_en.ngc] [--harness build/ngp_harness.exe]
        [--out build/catalog] [--work NEW_DIR]

For each entry of the recipe (format in catalog.txt) the harness loads the
state, runs the entry's input, names the hero Tristan and saves through the
game's own menu (scenario map popup: Data > Save > OK), keeping the cartridge
save in the player's .sav format. Each save is then checked:
  * it holds exactly file 1 (flash block 0x1C) and nothing else;
  * loaded from the title screen in a fresh run (Load, file 1), the game has
    the state's army, funds, cleared chapters and the hero's name;
  * it holds no run of 16 or more bytes with at least 4 different values that
    also occurs in the original game, so no text, graphics or code. Shorter
    matches are expected: a save holds the game's own numbers, and a story
    character who has not grown yet has the starting stats from the game's
    tables (8 bytes); runs of zeros with one other value match by chance.
Writes OUT/<file name>.sav and OUT/catalog.json (name, note, hero level,
characters, funds, chapters cleared). Nothing is written to OUT unless every
entry passes. The states are machine-local (docs/testing.md), so only the
maintainer can make the saves; the package takes them from OUT.
"""
import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
STATE_RAM = 0xC0
HERO_NAME = 0x46A1                        # 8 bytes, the game's character codes
TRISTAN = bytes.fromhex('1F372E38392633DC')
FUNDS, COUNT, CHARS, CLEARED, OPENED = 0x468E, 0x4692, 0x46AA, 0x546E, 0x546A   # masks: 32-bit, bit n = stage n
FILE1_BLOCK = 0x1C
SAVE_INPUT = '20:R:2;50:R:2;90:A:2;150:A:2;220:A:2'    # popup on Organize -> Data -> Save -> OK
SAVE_FRAMES = 900
LOAD_INPUT = '700:A:2;800:A:2;880:A:2;1000:A:2'      # intro, title, Load, file 1
LOAD_FRAMES = 1700
AUDIT_LIMIT = 16                          # bytes in a run that may not come from the game
AUDIT_DISTINCT = 4                        # ... counting runs with at least this many values


class CatalogError(Exception):
    pass


def read_recipe(path):
    entries = []
    for n, line in enumerate(open(path, encoding='utf-8'), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) != 4 or not parts[0].endswith('.sav'):
            raise CatalogError('%s:%d: want FILE NAME | STATE | INPUT | NOTE' % (path, n))
        entries.append({'file': parts[0], 'state': parts[1], 'input': parts[2], 'note': parts[3], 'line': n})
    return entries


def harness(exe, args):
    r = subprocess.run([exe] + args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, r.stdout + r.stderr


def save_records(data):
    if data[:8] != b'NGPFLSH1':
        raise CatalogError('not a save file')
    recs, p = [], 8
    while p < len(data):
        chip, block, _, length = struct.unpack_from('<BBHI', data, p)
        recs.append((chip, block, data[p + 8:p + 8 + length]))
        p += 8 + length
    return recs


def audit(rom, blocks):
    """Runs of AUDIT_LIMIT bytes with AUDIT_DISTINCT or more values that occur in rom."""
    wanted = {}
    for b in blocks:
        for i in range(len(b) - AUDIT_LIMIT + 1):
            w = b[i:i + AUDIT_LIMIT]
            if len(set(w)) >= AUDIT_DISTINCT:
                wanted.setdefault(w, i)
    found = []
    for i in range(len(rom) - AUDIT_LIMIT + 1):
        w = rom[i:i + AUDIT_LIMIT]
        if w in wanted:
            found.append((wanted.pop(w), i))
            if len(found) > 20:
                break
    return found


def make_one(e, o, rom, tmp):
    state = e['state'] if os.path.isfile(e['state']) else os.path.join(o.states, e['state'] + '.state')
    if not os.path.isfile(state):
        raise CatalogError('state not found: %s' % state)
    src = state
    if e['input']:
        inputs, _, frames = e['input'].partition('@')
        frames = int(frames or 300)
        src = os.path.join(tmp, 'pre.state')
        code, out = harness(o.harness, [o.english, '--load-state', state, '--frames', str(frames), '--input', inputs,
                                        '--save-state', str(frames - 1), src, '--out', tmp])
        if code or not os.path.isfile(src):
            raise CatalogError('input run failed:\n' + out[-800:])
    sav = os.path.join(tmp, 'new.sav')
    if os.path.exists(sav):
        os.remove(sav)
    code, out = harness(o.harness, [o.english, '--load-state', src, '--poke', '%04X=%s' % (HERO_NAME, TRISTAN.hex()),
                                    '--frames', str(SAVE_FRAMES), '--input', SAVE_INPUT, '--save', sav, '--dump-ram',
                                    os.path.join(tmp, 'before.bin'), '--out', tmp])
    if code or 'flash save written' not in out or not os.path.isfile(sav):
        raise CatalogError('the game did not save:\n' + out[-800:])
    data = open(sav, 'rb').read()
    recs = save_records(data)
    if [(c, b) for c, b, _ in recs] != [(0, FILE1_BLOCK)]:
        raise CatalogError('the save holds blocks %s, not file 1 only' % [(c, hex(b)) for c, b, _ in recs])
    before = open(os.path.join(tmp, 'before.bin'), 'rb').read()

    # load it in a fresh run, from the title screen
    check = os.path.join(tmp, 'check.sav')
    shutil.copy(sav, check)
    code, out = harness(o.harness, [o.english, '--save', check, '--frames', str(LOAD_FRAMES), '--input', LOAD_INPUT,
                                    '--dump-ram', os.path.join(tmp, 'loaded.bin'), '--out', tmp])
    after = open(os.path.join(tmp, 'loaded.bin'), 'rb').read() if os.path.isfile(os.path.join(tmp, 'loaded.bin')) else b''
    if code or len(after) != 0x10000:
        raise CatalogError('the load run failed:\n' + out[-800:])
    for what, a, n in (('hero name', HERO_NAME, 8), ('character count', COUNT, 1), ('funds', FUNDS, 4),
                       ('cleared chapters', CLEARED, 4), ('characters', CHARS, 18 * before[COUNT])):
        if after[a:a + n] != before[a:a + n]:
            raise CatalogError('after loading, the %s differ (%s != %s)' % (what, after[a:a + n].hex()[:40],
                                                                            before[a:a + n].hex()[:40]))
    if after[HERO_NAME:HERO_NAME + 8] != TRISTAN:
        raise CatalogError('the hero is not named Tristan after loading')
    found = audit(rom, [r[2] for r in recs])
    if found:
        raise CatalogError('the save holds runs of the original game: %s' % ', '.join(
            'save +%04X = ROM %06X' % (s, r) for s, r in found[:5]))
    cleared = int.from_bytes(before[CLEARED:CLEARED + 4], 'little')
    return data, {
        'file': e['file'], 'note': e['note'], 'state': e['state'],
        'hero_level': before[CHARS + 1], 'characters': before[COUNT],
        'funds': int.from_bytes(before[FUNDS:FUNDS + 4], 'little'),
        'chaos_frame': before[0x4694],
        'stages_cleared': [s for s in range(20) if cleared >> s & 1],
        'stages_open': [s for s in range(20) if int.from_bytes(before[OPENED:OPENED + 4], 'little') >> s & 1],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--recipe', default=os.path.join(ROOT, 'tools', 'release', 'catalog.txt'))
    ap.add_argument('--states', default=os.path.join(ROOT, 'build', 'states'))
    ap.add_argument('--rom', default=os.path.join(ROOT, 'rom', 'baserom.ngc'))
    ap.add_argument('--english', default=os.path.join(ROOT, 'build', 'ogre_en.ngc'))
    ap.add_argument('--harness', default=os.path.join(ROOT, 'build', 'ngp_harness.exe'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'build', 'catalog'))
    ap.add_argument('--work', default=None)
    o = ap.parse_args()
    for a in ('recipe', 'states', 'rom', 'english', 'harness', 'out'):
        setattr(o, a, os.path.abspath(getattr(o, a)))
    rom = open(o.rom, 'rb').read()
    entries = read_recipe(o.recipe)
    work = o.work or tempfile.mkdtemp(prefix='catalog-')
    os.makedirs(work, exist_ok=True)
    made, failed = [], 0
    for e in entries:
        tmp = os.path.join(work, os.path.splitext(e['file'])[0].replace(' ', '_'))
        os.makedirs(tmp, exist_ok=True)
        try:
            data, info = make_one(e, o, rom, tmp)
            made.append((data, info))
            print('ok    %-34s hero Lv %2d, %2d characters, %10s goth, chapters cleared %s' % (
                e['file'], info['hero_level'], info['characters'], format(info['funds'], ','),
                [s + 1 for s in info['stages_cleared']]))
        except CatalogError as err:
            failed += 1
            print('FAIL  %s (recipe line %d): %s' % (e['file'], e['line'], err))
    if failed:
        sys.exit('%d of %d saves failed; nothing written to %s' % (failed, len(entries), o.out))
    os.makedirs(o.out, exist_ok=True)
    for f in os.listdir(o.out):
        if f.endswith('.sav') or f == 'catalog.json':
            os.remove(os.path.join(o.out, f))
    for data, info in made:
        open(os.path.join(o.out, info['file']), 'wb').write(data)
    json.dump([info for _, info in made], open(os.path.join(o.out, 'catalog.json'), 'w', encoding='utf-8'), indent=1)
    print('wrote %d saves and catalog.json to %s' % (len(made), o.out))


if __name__ == '__main__':
    main()
