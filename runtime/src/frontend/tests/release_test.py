"""End-to-end test of the release package: zenobia.exe + ogre_en.bps in an
otherwise empty folder, used the way a player would, with the ROM elsewhere.

    python runtime/src/frontend/tests/release_test.py --exe build/zenobia.exe
        --patch build/ogre_en.bps --rom rom/baserom.ngc --english build/ogre_en.ngc
        --harness build/ngp_harness.exe
        --save-state build/states/data-popup_save_prompt.state --work NEW_DIR

Checks:
 1. the executable imports only Windows system DLLs (no Visual C++ runtime);
 2. the original ROM, patched in memory, gives the same picture as the
    harness running the English ROM (frame 1499), and the same image SHA-1;
    the English ROM runs as is; --write-patched equals the English ROM;
 3. the C applier (--bps-apply) and tools/patch/bps.py give the English ROM;
 4. refusals and messages: changed byte, wrong size, another game, archive,
    missing / damaged / truncated patch, English ROM without the patch,
    patch next to the ROM instead of the player;
 5. cartridge save: the game saves (Data -> Save from the given state), the
    file holds block 28, the next start offers Load and loads the saved game;
    a truncated save file is reported and not loaded half;
 6. window mode for a few seconds (--exit-after): clean exit, sound device,
    and the same with XInput missing (ZENOBIA_XINPUT names a missing DLL).
WORK must be a new or empty folder. Opens a real window twice (about 12 s).
"""
import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import zipfile

SYSTEM_DLLS = {'kernel32.dll', 'user32.dll', 'gdi32.dll', 'winmm.dll', 'comdlg32.dll', 'shell32.dll',
               'ole32.dll', 'advapi32.dll'}
FRAME = 1500                       # frames run for the picture comparison


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


def pe_imports(path):
    """Names of the DLLs a PE file imports (normal and delay-load)."""
    data = open(path, 'rb').read()
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    nsec = struct.unpack_from('<H', data, pe + 6)[0]
    optsize = struct.unpack_from('<H', data, pe + 20)[0]
    opt = pe + 24
    ddir = opt + (112 if struct.unpack_from('<H', data, opt)[0] == 0x20B else 96)
    secs = []
    for i in range(nsec):
        vsize, va, rsize, raw = struct.unpack_from('<IIII', data, opt + optsize + i * 40 + 8)
        secs.append((va, max(vsize, rsize), raw))

    def off(rva):
        for va, size, raw in secs:
            if va <= rva < va + size:
                return rva - va + raw
        raise ValueError('bad RVA %x' % rva)

    def name_at(rva):
        o = off(rva)
        return data[o:data.index(b'\0', o)].decode('ascii', 'replace')

    out = []
    for entry, name_field, size in ((1, 12, 20), (13, 4, 32)):
        rva = struct.unpack_from('<I', data, ddir + entry * 8)[0]
        if not rva:
            continue
        o = off(rva)
        while struct.unpack_from('<I', data, o + name_field)[0]:
            out.append(name_at(struct.unpack_from('<I', data, o + name_field)[0]))
            o += size
    return out


def run(args, env=None, timeout=120):
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
                       timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def sha1(path):
    return hashlib.sha1(open(path, 'rb').read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    for a in ('exe', 'patch', 'rom', 'english', 'harness', 'save_state', 'work'):
        ap.add_argument('--' + a.replace('_', '-'), required=True)
    a = ap.parse_args()
    exe_src, patch_src, rom, english, harness, save_state, work = (
        os.path.abspath(p) for p in (a.exe, a.patch, a.rom, a.english, a.harness, a.save_state, a.work))
    if os.path.isdir(work) and os.listdir(work):
        sys.exit('WORK must be a new or empty folder: %s' % work)
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
    os.makedirs(work, exist_ok=True)
    W = lambda *p: os.path.join(work, *p)           # noqa: E731

    # the release folder: the two files a player downloads, nothing else
    app = W('Zenobia player')
    os.makedirs(app)
    shutil.copy(exe_src, app)
    shutil.copy(patch_src, os.path.join(app, 'ogre_en.bps'))
    exe = os.path.join(app, 'zenobia.exe')
    en_sha1 = sha1(english)

    print('== 1. executable')
    dlls = pe_imports(exe)
    other = [d for d in dlls if d.lower() not in SYSTEM_DLLS]
    T.check('imports only system DLLs (%s)' % ', '.join(dlls), not other, 'also needs: %s' % ', '.join(other))

    print('== 2. the original ROM patched in memory')
    os.makedirs(W('h'))
    run([harness, english, '--frames', str(FRAME), '--shot', str(FRAME - 1), '--out', W('h')])
    ref = W('h', 'frame_%05d.png' % (FRAME - 1))
    code, out = run([exe, '--selftest', rom, '--frames', str(FRAME), '--png', W('jp.png')])
    T.check('original ROM runs (exit %d)' % code, code == 0, out)
    T.check('  the patch next to the player is applied', 'patch applied' in out and app in out, out)
    T.check('  image SHA-1 = English ROM', 'image sha1 ' + en_sha1 in out, out)
    T.check('  frame %d = harness on the English ROM' % (FRAME - 1),
            os.path.isfile(ref) and os.path.isfile(W('jp.png')) and open(ref, 'rb').read() == open(W('jp.png'), 'rb').read())
    code, out = run([exe, '--selftest', english, '--frames', str(FRAME), '--png', W('en.png')])
    T.check('English ROM runs as is (exit %d)' % code, code == 0 and '(English ROM)' in out, out)
    T.check('  same picture', open(W('en.png'), 'rb').read() == open(W('jp.png'), 'rb').read())
    code, out = run([exe, rom, '--write-patched', W('written.ngc')])
    T.check('--write-patched (exit %d) = English ROM' % code,
            code == 0 and os.path.isfile(W('written.ngc')) and sha1(W('written.ngc')) == en_sha1, out)

    print('== 3. C and Python appliers on the real patch')
    code, out = run([exe, '--bps-apply', rom, patch_src, W('c.ngc')])
    T.check('--bps-apply (exit %d) = English ROM' % code, code == 0 and sha1(W('c.ngc')) == en_sha1, out)
    sys.path.insert(0, repo)
    from tools.patch import bps as pybps                         # noqa: E402
    py = pybps.apply(open(rom, 'rb').read(), open(patch_src, 'rb').read())
    T.check('tools/patch/bps.py gives the same bytes', py == open(W('c.ngc'), 'rb').read())

    print('== 4. wrong files and patches')
    base = open(rom, 'rb').read()
    os.makedirs(W('roms'))

    def put(name, data):
        with open(W('roms', name), 'wb') as f:
            f.write(data)
        return W('roms', name)

    changed = bytearray(base)
    changed[0x100000] ^= 0x42
    cases = [
        ('one byte changed', put('changed.ngc', bytes(changed)), 'differ from the known original dump'),
        ('wrong size', put('half.ngc', base[:0x100000]), 'wrong size'),
        ('another game', put('other.ngc', base[:0x24] + b'OTHER_GAME  ' + base[0x30:]), 'another Neo Geo Pocket game'),
        ('not a ROM', put('text.ngc', b'hello' * 100), 'does not look like a Neo Geo Pocket ROM'),
    ]
    for name, path, text in cases:
        code, out = run([exe, '--selftest', path, '--frames', '10'])
        T.check('%s: warned and run as is in headless mode (exit %d)' % (name, code),
                code == 0 and 'not a ROM the patch knows' in out and text in out, out)
        code, out = run([exe, path, '--write-patched', W('roms', 'x.ngc')])
        T.check('  --write-patched refuses (exit %d) with the reason' % code,
                code == 3 and not os.path.exists(W('roms', 'x.ngc')) and text in out
                and 'nothing written' in out, out)
    with zipfile.ZipFile(W('roms', 'game.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('game.ngc', base)
    code, out = run([exe, '--selftest', W('roms', 'game.zip'), '--frames', '10'])
    T.check('.zip archive refused (exit %d), told to extract it' % code,
            code == 3 and 'compressed archive' in out and 'Extract' in out, out)

    nopatch = W('player without patch')
    os.makedirs(nopatch)
    shutil.copy(exe_src, nopatch)
    exe2 = os.path.join(nopatch, 'zenobia.exe')
    code, out = run([exe2, '--selftest', rom, '--frames', '10'])
    T.check('missing patch: not run (exit %d)' % code, code == 3 and 'English patch was not found' in out, out)
    T.check('  names both places looked at', os.path.join(nopatch, 'ogre_en.bps') in out
            and os.path.join(os.path.dirname(rom), 'ogre_en.bps') in out, out)
    lone_en = put('english.ngc', open(english, 'rb').read())     # no ogre_en.bps in that folder
    code, out = run([exe2, '--selftest', lone_en, '--frames', '10'])
    T.check('English ROM without the patch: recognised as patched, run (exit %d)' % code,
            code == 0 and 'already been patched' in out, out)
    romdir = W('rom folder')
    os.makedirs(romdir)
    shutil.copy(rom, os.path.join(romdir, 'game.ngc'))
    shutil.copy(patch_src, os.path.join(romdir, 'ogre_en.bps'))
    code, out = run([exe2, '--selftest', os.path.join(romdir, 'game.ngc'), '--frames', '10'])
    T.check('patch next to the ROM is used (exit %d)' % code,
            code == 0 and 'patch applied: ' + os.path.join(romdir, 'ogre_en.bps') in out
            and 'image sha1 ' + en_sha1 in out, out)
    data = open(patch_src, 'rb').read()
    for name, bad in (('one byte changed', data[:60000] + bytes([data[60000] ^ 1]) + data[60001:]),
                      ('truncated', data[:100000])):
        with open(os.path.join(nopatch, 'ogre_en.bps'), 'wb') as f:
            f.write(bad)
        code, out = run([exe2, '--selftest', rom, '--frames', '10'])
        T.check('damaged patch (%s) refused (exit %d)' % (name, code),
                code == 3 and 'could not be used' in out and 'damaged' in out, out)

    print('== 5. cartridge save')
    sav = W('game.sav')
    code, out = run([exe, '--selftest', rom, '--load-state', save_state, '--input', '10:A:2', '--frames', '600',
                     '--png', W('saved.png'), '--save', sav])
    T.check('the game saves (exit %d, 4096 bytes programmed)' % code,
            code == 0 and '4096 bytes programmed' in out, out)
    blocks = []
    if os.path.isfile(sav):
        d = open(sav, 'rb').read()
        p = 8
        while p + 8 <= len(d):
            blocks.append(d[p + 1])
            p += 8 + struct.unpack_from('<I', d, p + 4)[0]
    T.check('save file written with block 28 (blocks %s)' % blocks, blocks == [28])
    title = '300:A:2;400:A:2;500:A:2'
    code, out = run([exe, '--selftest', rom, '--input', title, '--frames', '700', '--png', W('title_nosave.png')])
    shutil.copy(sav, W('game2.sav'))
    code, out = run([exe, '--selftest', rom, '--save', W('game2.sav'), '--input', title, '--frames', '700',
                     '--png', W('title_save.png')])
    T.check('next start loads the save file (exit %d)' % code, code == 0 and 'flash save loaded' in out, out)
    T.check('  title menu differs (Load offered)',
            open(W('title_save.png'), 'rb').read() != open(W('title_nosave.png'), 'rb').read())
    T.check('  reading the save does not rewrite it', open(W('game2.sav'), 'rb').read() == open(sav, 'rb').read())
    load = title + ';720:A:2;850:A:2'
    run([exe, '--selftest', rom, '--input', load, '--frames', '1000', '--png', W('load_nosave.png')])
    code, out = run([exe, '--selftest', rom, '--save', W('game2.sav'), '--input', load, '--frames', '1000',
                     '--png', W('load_save.png')])
    T.check('Load -> file 1 runs (exit %d) and leads elsewhere than NewGame' % code,
            code == 0 and open(W('load_save.png'), 'rb').read() != open(W('load_nosave.png'), 'rb').read(), out)
    d = open(sav, 'rb').read()
    with open(W('truncated.sav'), 'wb') as f:
        f.write(d[:-100])
    code, out = run([exe, '--selftest', rom, '--save', W('truncated.sav'), '--input', title, '--frames', '700',
                     '--png', W('title_truncated.png')])
    T.check('truncated save reported (exit %d)' % code, code == 0 and 'flash save is damaged' in out, out)
    T.check('  and not loaded half (title as without a save)',
            open(W('title_truncated.png'), 'rb').read() == open(W('title_nosave.png'), 'rb').read())

    print('== 6. window mode')
    for label, env_extra in (('normal', {}), ('XInput missing', {'ZENOBIA_XINPUT': 'xinput_missing_test.dll'})):
        env = dict(os.environ)
        env.pop('ZENOBIA_XINPUT', None)
        env.update(env_extra)
        png = W('window_%s.png' % label.split()[0].lower())
        code, out = run([exe, rom, '--exit-after', '5', '--png', png], env=env, timeout=60)
        frames = [l for l in out.splitlines() if 'frames in' in l]
        audio = [l for l in out.splitlines() if 'audio ' in l]
        xin = [l for l in out.splitlines() if 'XInput' in l]
        print('     ' + ' | '.join(frames + audio + xin))
        T.check('%s: window ran and quit cleanly (exit %d)' % (label, code),
                code == 0 and frames and os.path.isfile(png), out)
        T.check('  sound device open', bool(audio) and 'waveOut 48000 Hz' in audio[0], out)
        if env_extra:
            T.check('  keyboard only: XInput not available', bool(xin) and 'not available' in xin[0], out)
        else:
            T.check('  XInput loaded', bool(xin) and 'xinput' in xin[0].lower() and 'not available' not in xin[0], out)
    leftovers = sorted(os.listdir(app))
    T.check('release folder afterwards: %s' % ', '.join(leftovers),
            set(leftovers) <= {'zenobia.exe', 'ogre_en.bps', 'zenobia.ini', 'saves', 'states'})

    print('passed %d, failed %d' % (T.passed, T.failed))
    return 1 if T.failed else 0


if __name__ == '__main__':
    sys.exit(main())
