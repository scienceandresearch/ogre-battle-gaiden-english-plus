"""Regression test of the core's cartridge saving, through ngp_harness.

    python runtime/src/core/tests/save_test.py --harness build/ngp_harness.exe
        --rom build/ogre_en.ngc --states build/states --work NEW_DIR
        [--reference OLD_HARNESS.exe]

ROM: the English ROM with the save-safe layout (nothing in 0x3B0000-0x3EFFFF).
States (from build/states, see docs/workstreams/explore-data.md):
data-popup_save_prompt ("OK:A NO:B" bar of Data -> Save), data-cmdbar_suspend
(stage 0 command bar on Suspend), stage0_selected (chapter card); with
--reference also organize-items, map-unitwin, battle-inbattle_cmdbar,
progress-stage2_gameplay, data-popup_monitor.

Checks:
 1. BIOS flash chip size codes (0x6C58/0x6C59) for 0.5 to 4 MB images (blank
    synthetic images) and for this game; a state made with the old code 1 is
    corrected when loaded;
 2. in-game save: "Save complete." (4096 bytes programmed, the file holds
    block 28); --no-flash-commands: nothing programmed, "Could not save.";
 3. the next power-on with that file offers Load, and reading it does not
    rewrite it; a truncated file is reported and not applied half;
 4. 19 saves to file 1: exactly one block erase, of block 28; the emulated
    image differs from the ROM only inside block 28; "Save complete." again;
 5. a save file's blocks stay in it across --load-state (suspend -> 27 + 28);
 6. --poke: the chapter byte changes the chapter card; bad specs refused;
 7. state files keep their format: "NGPSTAT1", 66,399 bytes, RAM at byte 192;
 8. with --reference: power-on and five states give byte-identical
    screenshots and text logs with both harnesses (runs that do not save).
WORK must be a new or empty folder. No ROM data is stored in this script.
"""
import argparse
import os
import struct
import subprocess
import sys

SAVE_PROMPT, SUSPEND, CHAPTER = 'data-popup_save_prompt', 'data-cmdbar_suspend', 'stage0_selected'
DETERMINISM = ['organize-items', 'map-unitwin', 'battle-inbattle_cmdbar', 'progress-stage2_gameplay',
               'data-popup_monitor']
TITLE = '300:A:2;400:A:2;500:A:2'                       # power-on to the title menu
SAVES19 = ';'.join(['10:A:2'] + ['%d:A:2;%d:A:2;%d:A:2' % (c, c + 100, c + 200) for c in range(400, 7201, 400)])
STATE_SIZE, RAM_OFFSET = 66399, 192


class T:
    passed = failed = 0

    @classmethod
    def check(cls, name, cond, detail=''):
        print('%s %s%s' % ('ok  ' if cond else 'FAIL', name, ('  [%s]' % detail) if detail and not cond else ''))
        if cond:
            cls.passed += 1
        else:
            cls.failed += 1
        return cond


def run(exe, *args):
    r = subprocess.run([exe] + [str(a) for a in args], capture_output=True, text=True, errors='replace')
    return r.returncode, r.stdout + r.stderr


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def write(path, data):
    with open(path, 'wb') as f:
        f.write(data)


def blocks_of(path):
    """[(chip, block, data)] of a save file ("NGPFLSH1" records)."""
    d = read(path)
    if d[:8] != b'NGPFLSH1':
        return None
    out, p = [], 8
    while p + 8 <= len(d):
        n = struct.unpack_from('<I', d, p + 4)[0]
        out.append((d[p], d[p + 1], d[p + 8:p + 8 + n]))
        p += 8 + n
    return out


def ids(blocks):
    return [(c, k) for c, k, _ in blocks] if blocks is not None else None


def main():
    ap = argparse.ArgumentParser()
    for a in ('harness', 'rom', 'states', 'work'):
        ap.add_argument('--' + a, required=True)
    ap.add_argument('--reference')
    a = ap.parse_args()
    H, rom, work = os.path.abspath(a.harness), os.path.abspath(a.rom), os.path.abspath(a.work)
    if os.path.isdir(work) and os.listdir(work):
        sys.exit('WORK must be a new or empty folder: %s' % work)
    os.makedirs(work, exist_ok=True)
    rom_data = read(rom)

    def st(name):
        return os.path.join(os.path.abspath(a.states), name + '.state')

    def D(name):
        """A new folder in WORK."""
        path = os.path.join(work, name)
        os.makedirs(path, exist_ok=True)
        return path

    def W(*p):
        return os.path.join(work, *p)

    def sizes():
        for size, want in ((0x80000, (1, 0)), (0x100000, (2, 0)), (0x180000, (3, 0)), (0x200000, (3, 0)),
                           (0x300000, (3, 2)), (0x400000, (3, 3))):
            img = bytearray(b'\xff' * size)
            img[0x1C:0x1F] = b'\x40\x00\x20'            # entry point; no code runs with --frames 0
            path, ram = os.path.join(D('sizes'), '%x.ngc' % size), W('sizes', '%x.bin' % size)
            write(path, img)
            run(H, path, '--frames', 0, '--out', D('sizes'), '--dump-ram', ram)
            ram = read(ram)
            T.check('%4d KB image: codes %d, %d' % (size // 1024, ram[0x6C58], ram[0x6C59]),
                    (ram[0x6C58], ram[0x6C59]) == want, 'want %d, %d' % want)
        run(H, rom, '--frames', 0, '--out', D('sizes'), '--dump-ram', W('sizes', 'game.bin'))
        ram = read(W('sizes', 'game.bin'))
        T.check('this game at power-on: %d, %d (one 16 Mbit chip)' % (ram[0x6C58], ram[0x6C59]),
                len(rom_data) != 0x200000 or (ram[0x6C58], ram[0x6C59]) == (3, 0))
        old = read(st(SAVE_PROMPT))[RAM_OFFSET + 0x6C58]
        run(H, rom, '--load-state', st(SAVE_PROMPT), '--frames', 0, '--out', D('sizes'),
            '--dump-ram', W('sizes', 'loaded.bin'))
        now = read(W('sizes', 'loaded.bin'))[0x6C58]
        T.check('state holding code %d: %d after loading' % (old, now), now == 3)

    def save():
        code, out = run(H, rom, '--load-state', st(SAVE_PROMPT), '--input', '10:A:2', '--frames', 600,
                        '--save', W('s.sav'), '--out', D('save'))
        T.check('Data -> Save programs 4096 bytes (exit %d)' % code,
                code == 0 and '4096 bytes programmed, 0 blocks erased' in out, out)
        b = blocks_of(W('s.sav')) if os.path.isfile(W('s.sav')) else None
        T.check('save file holds block 28 only', ids(b) == [(0, 28)] and len(b[0][2]) == 0x10000, ids(b))
        code, out = run(H, rom, '--load-state', st(SAVE_PROMPT), '--input', '10:A:2', '--frames', 600,
                        '--save', W('n.sav'), '--no-flash-commands', '--out', D('nosave'))
        T.check('--no-flash-commands: nothing programmed, no file (exit %d)' % code,
                code == 0 and 'bytes programmed' not in out and not os.path.exists(W('n.sav')), out)
        T.check('  and the screen differs ("Could not save." instead of "Save complete.")',
                read(W('nosave', 'final.png')) != read(W('save', 'final.png')))

    def load():
        write(W('s2.sav'), read(W('s.sav')))
        run(H, rom, '--input', TITLE, '--frames', 700, '--out', D('title_none'))
        code, out = run(H, rom, '--save', W('s2.sav'), '--input', TITLE, '--frames', 700, '--out', D('title_save'))
        T.check('title menu with the save differs (Load offered) (exit %d)' % code,
                code == 0 and read(W('title_save', 'final.png')) != read(W('title_none', 'final.png')), out)
        T.check('  reading the file does not rewrite it', read(W('s2.sav')) == read(W('s.sav')))
        write(W('t.sav'), read(W('s.sav'))[:-100])
        code, out = run(H, rom, '--save', W('t.sav'), '--input', TITLE, '--frames', 700, '--out', D('title_trunc'))
        T.check('truncated save reported', 'damaged' in out, out)
        T.check('  and not applied half (title as without a save)',
                read(W('title_trunc', 'final.png')) == read(W('title_none', 'final.png')))

    def saves19():
        code, out = run(H, rom, '--load-state', st(SAVE_PROMPT), '--input', SAVES19, '--frames', 7700,
                        '--save', W('s19.sav'), '--dump-flash', W('image.bin'), '--out', D('saves19'))
        T.check('19 saves, one block erase: block 28 (exit %d)' % code,
                code == 0 and '77824 bytes programmed, 1 blocks erased (chip 0 block 28 at 3C0000: 1)' in out, out)
        T.check('  save file holds block 28 only', ids(blocks_of(W('s19.sav'))) == [(0, 28)])
        img = read(W('image.bin'))
        diff = [i for i in range(len(img)) if img[i] != rom_data[i]] if len(img) == len(rom_data) else None
        T.check('  emulated image differs from the ROM only inside block 28 (%s bytes)'
                % (len(diff) if diff is not None else 'size differs'),
                diff is not None and all(0x1C0000 <= i < 0x1D0000 for i in diff))
        T.check('  0x2F0000-0x2FFFFF (block 15, game data) untouched', img[0xF0000:0x100000] == rom_data[0xF0000:0x100000])
        T.check('  last screen = "Save complete." (as after the first save)',
                read(W('saves19', 'final.png')) == read(W('save', 'final.png')))

    def kept():
        write(W('su.sav'), read(W('s.sav')))
        code, out = run(H, rom, '--save', W('su.sav'), '--load-state', st(SUSPEND), '--input', '10:A:2;60:A:2;200:A:2',
                        '--frames', 600, '--out', D('suspend'))
        b = blocks_of(W('su.sav'))
        T.check('suspend writes block 27, file 1 (block 28) stays: blocks %s' % ids(b),
                ids(b) == [(0, 27), (0, 28)] and b[1][2] == blocks_of(W('s.sav'))[0][2], out)

    def poke():
        for tag, extra in (('card', []), ('card5', ['--poke', '5490=05']), ('card_late', ['--poke', '5490=05@300'])):
            run(H, rom, '--load-state', st(CHAPTER), '--frames', 201, '--shot', 200, '--out', D(tag), *extra)
        card = read(W('card', 'frame_00200.png'))
        T.check('--poke 5490=05: another chapter card', read(W('card5', 'frame_00200.png')) != card)
        T.check('--poke 5490=05@300: not applied before frame 300', read(W('card_late', 'frame_00200.png')) == card)
        run(H, rom, '--load-state', st(CHAPTER), '--frames', 0, '--poke', '6000=0102030405,6100=A@0',
            '--poke', '6200=ff', '--out', D('pokes'), '--dump-ram', W('pokes', 'ram.bin'))
        ram = read(W('pokes', 'ram.bin'))
        T.check('several pokes land after --load-state (also with --frames 0)',
                ram[0x6000:0x6005] == b'\x01\x02\x03\x04\x05' and ram[0x6100] == 0x0A and ram[0x6200] == 0xFF)
        bad = [s for s in ('5490', '10000=01', 'FFFF=0102', '5490=123', '5490=zz', '5490=05@x', '=05', '5490=')
               if run(H, rom, '--frames', 1, '--poke', s, '--out', D('pokes'))[0] != 1]
        T.check('bad --poke specs refused (exit 1)', not bad, 'accepted: %s' % bad)

    def fmt():
        run(H, rom, '--frames', 100, '--save-state', 99, W('fmt.state'), '--dump-ram', W('fmt_ram.bin'), '--out', D('fmt'))
        s = read(W('fmt.state'))
        T.check('NGPSTAT1, %d bytes, RAM at byte %d' % (len(s), RAM_OFFSET),
                s[:8] == b'NGPSTAT1' and len(s) == STATE_SIZE
                and s[RAM_OFFSET:RAM_OFFSET + 0x10000] == read(W('fmt_ram.bin')))

    def determinism():
        cases = [('power_on', None, ['--frames', 1500, '--shot-every', 100])]
        cases += [(n, n, ['--frames', 200, '--shot-every', 20]) for n in DETERMINISM]
        for name, state, args in cases:
            files = {}
            for tag, exe in (('new', H), ('ref', os.path.abspath(a.reference))):
                d = D(os.path.join('det', tag, name))
                extra = ['--load-state', st(state)] if state else []
                run(exe, rom, '--out', d, '--text-log', os.path.join(d, 'text.txt'), *(args + extra))
                files[tag] = {f: read(os.path.join(d, f)) for f in os.listdir(d) if f.endswith('.png') or f == 'text.txt'}
            T.check('%s: %d screenshots + text log identical' % (name, len(files['new']) - 1),
                    bool(files['new']) and files['new'] == files['ref'])

    sections = [('1. flash chip size codes', sizes), ('2. in-game save', save), ('3. loading the save file', load),
                ('4. 19 saves to file 1', saves19), ('5. save file blocks kept across --load-state', kept),
                ('6. --poke', poke), ('7. state file format', fmt)]
    if a.reference:
        sections.append(('8. determinism against %s' % a.reference, determinism))
    for title, fn in sections:
        print('== ' + title)
        try:
            fn()
        except Exception as e:      # a missing output, a short file...: report it and go on
            T.check('section stopped: %s: %s' % (type(e).__name__, e), False)

    print('passed %d, failed %d' % (T.passed, T.failed))
    return 1 if T.failed else 0


if __name__ == '__main__':
    sys.exit(main())
