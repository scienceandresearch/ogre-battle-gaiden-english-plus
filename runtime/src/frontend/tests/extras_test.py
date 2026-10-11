"""The player's extras: console date, continuing where you left off, importing
a saved game, and the cheats (through the harness, which runs the same code).

    python runtime/src/frontend/tests/extras_test.py --exe build/zenobia.exe --rom rom/baserom.ngc
        --english build/ogre_en.ngc --harness build/ngp_harness.exe --states build/states --work NEW_DIR

Checks:
 1. --date: MM-DD accepted, impossible dates refused (exit 1).
 2. --resume: quitting writes states\\resume.state for this ROM (with any
    --resume value: File > Continue where I left off needs it); the next start
    with --resume yes continues it (another picture than a fresh start), with
    --resume no it starts at power-on; without --resume a test run leaves no
    state behind.
 3. --import-save: a save file replaces the game's save and the previous one
    is kept in a "(before import ...)" copy; a file that is not a save, or
    holds blocks outside the game's save area, is refused (exit 7) and the
    save stays as it was.
 4. Cheats (--cheat in the harness): goth (+100,000, capped at 99,999,999),
    heal (HP to the maximum, the dead stay dead), level (experience 99; after
    a battle every member gained a level), rep+ / rep- (capped at 100 / 0).
The states come from STATES (machine-local, see docs/testing.md):
r2-story-early-s6_cleared_scenario_map and battle-gring_fight_banner.
WORK must be a new or empty folder.
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys

EXIT_USAGE, EXIT_SAVE_FAILED = 1, 7
FUNDS, REPUTATION, COUNT, CHARS, CSIZE = 0x468E, 0x4694, 0x4692, 0x46AA, 18
STATE_RAM = 0xC0


class T:
    passed = failed = 0

    @classmethod
    def check(cls, name, cond, detail=''):
        print('%s %s%s' % ('ok  ' if cond else 'FAIL', name, ('  [%s]' % detail.strip()[-1500:]) if detail and not cond else ''))
        if cond:
            cls.passed += 1
        else:
            cls.failed += 1
        return cond


def run(args, cwd=None, timeout=180):
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, cwd=cwd)
    return r.returncode, r.stdout + r.stderr


def save_file(blocks):
    """A save in the player's format: "NGPFLSH1", then {chip, block, 0, length, data} records."""
    out = bytearray(b'NGPFLSH1')
    for block, fill in blocks:
        out += struct.pack('<BBHI', 0, block, 0, 0x10000) + bytes([fill]) * 0x10000
    return bytes(out)


def ram_of_state(path):
    return open(path, 'rb').read()[STATE_RAM:STATE_RAM + 0x10000]


def u16(m, a):
    return m[a] | m[a + 1] << 8


def u32(m, a):
    return int.from_bytes(m[a:a + 4], 'little')


def main():
    ap = argparse.ArgumentParser()
    for a in ('--exe', '--rom', '--english', '--harness', '--states', '--work'):
        ap.add_argument(a, required=True)
    o = ap.parse_args()
    for a in ('exe', 'rom', 'english', 'harness', 'states'):   # Windows starts programs by full path only
        setattr(o, a, os.path.abspath(getattr(o, a)))
    work = os.path.abspath(o.work)
    os.makedirs(work, exist_ok=True)
    if os.listdir(work):
        sys.exit('WORK must be a new or empty folder: %s' % work)
    rom = os.path.abspath(o.rom)
    english_sha1 = __import__('hashlib').sha1(open(o.english, 'rb').read()).digest()

    # the player in its own folder, with the patch next to it
    pdir = os.path.join(work, 'player')
    os.makedirs(pdir)
    exe = os.path.join(pdir, 'zenobia.exe')
    shutil.copy(o.exe, exe)
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(o.english)), 'ogre_en.bps'), pdir)

    # 1. --date
    for date, want in (('12-25', 0), ('6-6', 0), ('13-01', EXIT_USAGE), ('02-30', EXIT_USAGE), ('12', EXIT_USAGE)):
        code, out = run([exe, rom, '--date', date, '--exit-after', '1'], cwd=pdir)
        T.check('--date %s -> exit %d' % (date, want), code == want, out)

    # 2. --resume
    rs = os.path.join(pdir, 'states', 'resume.state')
    code, out = run([exe, rom, '--exit-after', '2'], cwd=pdir)
    T.check('a test run without --resume leaves no resume state', code == 0 and not os.path.exists(rs), out)
    code, out = run([exe, rom, '--exit-after', '25', '--resume', 'yes'], cwd=pdir)
    data = open(rs, 'rb').read() if os.path.exists(rs) else b''
    T.check('quitting writes states\\resume.state', code == 0 and len(data) > 44, out)
    T.check('the resume state names the English ROM', data[-44:-36] == b'ZENOBST1' and data[-28:-8] == english_sha1)
    p_yes, p_no = os.path.join(work, 'resume_yes.png'), os.path.join(work, 'resume_no.png')
    code, out_yes = run([exe, rom, '--exit-after', '2', '--resume', 'yes', '--png', p_yes], cwd=pdir)
    T.check('--resume yes continues the last session', code == 0 and 'Continued where you left off' in out_yes, out_yes)
    code, out_no = run([exe, rom, '--exit-after', '2', '--resume', 'no', '--png', p_no], cwd=pdir)
    T.check('--resume no starts at power-on', code == 0 and 'Continued' not in out_no, out_no)
    T.check('continued and fresh starts show different pictures',
            os.path.exists(p_yes) and os.path.exists(p_no) and open(p_yes, 'rb').read() != open(p_no, 'rb').read())

    # 3. --import-save
    saves = os.path.join(pdir, 'saves')
    os.makedirs(saves, exist_ok=True)
    current = os.path.join(saves, os.path.splitext(os.path.basename(rom))[0] + '.sav')
    old, new = save_file([(0x1C, 0xFF)]), save_file([(0x1B, 0xFF), (0x1C, 0xFF)])
    open(current, 'wb').write(old)
    good = os.path.join(work, 'chapter.sav')
    open(good, 'wb').write(new)
    code, out = run([exe, rom, '--import-save', good, '--exit-after', '1', '--resume', 'no'], cwd=pdir)
    T.check('--import-save replaces the save', code == 0 and open(current, 'rb').read() == new, out)
    backups = [f for f in os.listdir(saves) if '(before import ' in f]
    T.check('the previous save is kept in a backup copy',
            len(backups) == 1 and open(os.path.join(saves, backups[0]), 'rb').read() == old, str(os.listdir(saves)))
    for name, content in (('not a save', b'not a save file'), ('a code block', save_file([(0x05, 0xFF)])),
                          ('a truncated record', new[:-100])):
        bad = os.path.join(work, 'bad.sav')
        open(bad, 'wb').write(content)
        code, out = run([exe, rom, '--import-save', bad, '--exit-after', '1', '--resume', 'no'], cwd=pdir)
        T.check('refused: %s (exit %d), save unchanged' % (name, EXIT_SAVE_FAILED),
                code == EXIT_SAVE_FAILED and open(current, 'rb').read() == new, out)

    # 4. cheats, through the harness
    base = os.path.join(o.states, 'r2-story-early-s6_cleared_scenario_map.state')
    before = ram_of_state(base)
    dump = os.path.join(work, 'ram.bin')
    code, out = run([o.harness, o.english, '--load-state', base, '--frames', '1', '--cheat', 'goth', '--cheat', 'heal',
                     '--cheat', 'level', '--cheat', 'rep+', '--dump-ram', dump, '--out', work])
    after = open(dump, 'rb').read() if os.path.exists(dump) else bytes(0x10000)
    T.check('goth: +100,000', u32(after, FUNDS) == u32(before, FUNDS) + 100000, out)
    T.check('rep+: +10', after[REPUTATION] == min(100, before[REPUTATION] + 10))
    n = before[COUNT]
    recs = [(CHARS + i * CSIZE) for i in range(n)]
    T.check('level: experience 99 for all %d characters' % n, all(after[r + 16] == 99 for r in recs))
    T.check('heal: HP at the maximum for the living', all(u16(after, r + 4) == (u16(after, r + 6) if u16(before, r + 4) else 0) for r in recs))
    # caps: funds near the limit, reputation near 0, a dead character
    code, out = run([o.harness, o.english, '--load-state', base, '--frames', '1',
                     '--poke', '468E=%s' % (99950000).to_bytes(4, 'little').hex(), '--poke', '4694=05',
                     '--poke', '%04X=0000' % (CHARS + 4 + 3 * CSIZE),
                     '--cheat', 'goth', '--cheat', 'rep-', '--cheat', 'heal', '--dump-ram', dump, '--out', work])
    after = open(dump, 'rb').read()
    T.check('goth stops at 99,999,999', u32(after, FUNDS) == 99999999, out)
    T.check('rep- stops at 0', after[REPUTATION] == 0)
    T.check('heal leaves a dead character dead', u16(after, CHARS + 4 + 3 * CSIZE) == 0)
    code, out = run([o.harness, o.english, '--frames', '1', '--cheat', 'goth', '--out', work])
    T.check('no game at power-on: the cheat is not applied', 'not applied' in out, out)
    # level: the game's own level-up after a battle
    battle = os.path.join(o.states, 'battle-gring_fight_banner.state')
    bb = ram_of_state(battle)
    inputs = ';'.join('%d:A:2' % f for f in range(30, 12000, 90))
    code, out = run([o.harness, o.english, '--load-state', battle, '--frames', '12000', '--input', inputs,
                     '--cheat', 'level', '--dump-ram', dump, '--out', work], timeout=600)
    after = open(dump, 'rb').read()
    members = [CHARS + i * CSIZE for i in range(bb[COUNT])]
    T.check('level: every member of the battle gained a level',
            all(after[r + 1] == bb[r + 1] + 1 for r in members) and all(u16(after, r + 6) > u16(bb, r + 6) for r in members),
            str([(bb[r + 1], after[r + 1]) for r in members]))

    print('passed %d, failed %d' % (T.passed, T.failed))
    sys.exit(1 if T.failed else 0)


if __name__ == '__main__':
    main()
