"""Tests of the release packager (tools/release/package.py) on scratch copies.

    python -m tools.release.test_package --work NEW_DIR [--build build] [--rom rom/baserom.ngc]

Copies zenobia.exe and ogre_en.{ngc,bps,sha1} from the build folder into
NEW_DIR (keeping their times) and runs the packager on the copies; the build
folder is never changed. Checks:
  1. a normal run makes the zip (exit 0); a second run makes a byte-identical
     zip; --release names it without the -dev suffix;
  1b. the zip holds the guide, Chapter saves/About.txt and every chapter
     save of BUILD/catalog (copied with the build files; without it, a
     made-up empty save of file 1 stands in), and the guide lists each save
     with its note from catalog.json;
  2. each refusal on its own (exit 1, only that check fails, nothing
     written): ogre_en.sha1 not matching ogre_en.ngc; a patch that writes
     into the game's save blocks (layout); a patch whose literal holds 16
     bytes of the original ROM (audit); zenobia.exe older than its sources;
     ROM data inside a packaged file (64 ROM bytes appended to zenobia.exe);
     a missing input; no chapter saves (and --no-catalog then packages
     without them, its guide saying so); no catalog.json to describe the
     saves; a chapter save holding another flash block, or 16
     bytes of the original ROM; --release over a different zip of the
     same version;
  3. the classification of matches with the ROM (padding, runs, counting,
     cartridge header; real ROM data found as one piece, also when every
     8-byte window of it looks trivial);
  4. the icon converter: the sizes and formats made from
     assets/icon/zenobia.txt, deterministic output, malformed sources
     refused with a message and no .ico;
  5. the files of this workstream (tools/release, VERSION, the icon source,
     zenobia.rc, resource.h, docs/workstreams/release.md,
     docs/guide-sources.md) are plain ASCII;
  6. zenobia.exe looks for the guide and the saves folder under the names
     the package gives them (GUIDE_FILE and CATALOG_DIR in gui.c).
About 20 s. Exit 1 if any check fails.
"""
import argparse
import contextlib
import hashlib
import html
import io
import json
import os
import re
import shutil
import struct
import sys
import time
import zipfile

from ..patch import bps
from . import mkicon, package

BUILD_FILES = ('zenobia.exe', 'ogre_en.ngc', 'ogre_en.bps', 'ogre_en.sha1')


class T:
    passed = failed = 0

    @classmethod
    def check(cls, name, cond, detail=''):
        print('%s %s%s' % ('ok  ' if cond else 'FAIL', name, ('\n      ' + detail.replace('\n', '\n      '))
                                                         if detail and not cond else ''))
        if cond:
            cls.passed += 1
        else:
            cls.failed += 1
        return cond


def run(args):
    """package.main(args) with its output captured: (exit code, text)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = package.main(args)
    return code, buf.getvalue()


def failed_checks(text):
    for line in text.splitlines():
        if line.startswith('refused:'):
            return sorted(set(w.strip() for w in line.split(':', 2)[2].split(',')))
    return []


def copy_build(src, dst, catalog=True):
    """The build files, and the chapter saves (BUILD/catalog) unless catalog is False.
    Without BUILD/catalog (it needs the maintainer's test states) a made-up
    save stands in: file 1's block, empty, described in catalog.json."""
    os.makedirs(dst)
    for name in BUILD_FILES:
        shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
    if catalog and os.path.isdir(os.path.join(src, 'catalog')):
        shutil.copytree(os.path.join(src, 'catalog'), os.path.join(dst, 'catalog'))
    elif catalog:
        folder = os.path.join(dst, 'catalog')
        os.makedirs(folder)
        with open(os.path.join(folder, '01 Test save.sav'), 'wb') as f:
            f.write(b'NGPFLSH1' + struct.pack('<BBHI', 0, 0x1C, 0, 0x10000) + bytes(0x10000))
        info = [{'file': '01 Test save.sav', 'note': "A made-up save for the packager's tests.", 'state': '',
                 'hero_level': 1, 'characters': 3, 'funds': 30000, 'chaos_frame': 50,
                 'stages_cleared': [], 'stages_open': [0]}]
        with open(os.path.join(folder, package.CATALOG_INFO), 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=1)
    return dst


def first_save(folder):
    return os.path.join(folder, 'catalog', sorted(f for f in os.listdir(os.path.join(folder, 'catalog'))
                                                  if f.endswith('.sav'))[0])


def put_english(folder, rom, target, patch):
    with open(os.path.join(folder, 'ogre_en.ngc'), 'wb') as f:
        f.write(target)
    with open(os.path.join(folder, 'ogre_en.bps'), 'wb') as f:
        f.write(patch)
    with open(os.path.join(folder, 'ogre_en.sha1'), 'w', newline='\n') as f:
        f.write(hashlib.sha1(target).hexdigest() + '\n')


def zips(folder):
    return sorted(n for n in os.listdir(folder)) if os.path.isdir(folder) else []


def rich_rom_piece(rom, size, start=0x100):
    """Offset of `size` ROM bytes in which no 8-byte window is trivial data."""
    for off in range(start, len(rom) - size, 0x40):
        piece = rom[off:off + size]
        if all(package.trivial(piece[i:i + 8]) is None for i in range(size - 7)):
            return off
    raise RuntimeError('no suitable piece of the ROM')


def sparse_rom_piece(rom, size):
    """Offset of `size` ROM bytes that are not trivial as a whole although
    every 8-byte window in them is (low-information graphics or tables)."""
    for off in range(0x100, 0x16746D - size):
        piece = rom[off:off + size]
        wins = [piece[i:i + 8] for i in range(size - 7)]
        if (package.trivial(piece) is None and all(package.trivial(w) for w in wins)
                and all(len(set(w)) > 1 for w in wins)):
            return off
    raise RuntimeError('no suitable piece of the ROM')


def refusal(name, work, build, rom_path, expect, extra=()):
    out = os.path.join(work, 'out-' + re.sub(r'[^a-z0-9]+', '-', name.lower())[:24].strip('-'))
    code, text = run(['--build', build, '--rom', rom_path, '--out', out] + list(extra))
    got = failed_checks(text)
    T.check('refused: %s (exit %d, failed checks %s)' % (name, code, ', '.join(got) or '-'),
            code == 1 and got == [expect], text)
    T.check('  nothing written', not [z for z in zips(out) if z.endswith(('.zip', '.tmp'))], ', '.join(zips(out)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.release.test_package')
    ap.add_argument('--work', required=True, help='a new or empty folder')
    ap.add_argument('--build', default='build')
    ap.add_argument('--rom', default=os.path.join('rom', 'baserom.ngc'))
    a = ap.parse_args(argv)
    work, build_src, rom_path = (os.path.abspath(p) for p in (a.work, a.build, a.rom))
    if os.path.isdir(work) and os.listdir(work):
        sys.exit('--work must be a new or empty folder: %s' % work)
    os.makedirs(work, exist_ok=True)
    rom = package.read(rom_path)
    t0 = time.time()

    print('== 1. normal runs')
    good = copy_build(build_src, os.path.join(work, 'build-good'))
    code, text = run(['--build', good, '--rom', rom_path, '--out', os.path.join(work, 'out-a')])
    made = zips(os.path.join(work, 'out-a'))
    T.check('packages (exit %d): %s' % (code, ', '.join(made)), code == 0 and len(made) == 1, text)
    english_sha1 = hashlib.sha1(package.read(os.path.join(good, 'ogre_en.ngc'))).hexdigest()
    version = package.read_version()
    T.check('  dev name has -dev+<8 digits of the English SHA-1>',
            made == ['ogre-battle-gaiden-english-plus-%s-dev+%s-win64.zip' % (version, english_sha1[:8])])
    if made:
        names = zipfile.ZipFile(os.path.join(work, 'out-a', made[0])).namelist()
        top = names[0]
        saves = [n for n in names if n.startswith(top + 'Chapter saves/') and n.endswith('.sav')]
        catalog_saves = [f for f in os.listdir(os.path.join(good, 'catalog')) if f.endswith('.sav')]
        T.check("  the zip holds Player's Guide.html, Chapter saves/About.txt and the %d chapter saves"
                % len(catalog_saves), top + "Player's Guide.html" in names and
                top + 'Chapter saves/About.txt' in names and len(saves) == len(catalog_saves) > 0, '\n'.join(names))
        guide = zipfile.ZipFile(os.path.join(work, 'out-a', made[0])).read(top + "Player's Guide.html").decode('utf-8')
        T.check('  the guide lists every chapter save, with its note from catalog.json',
                package.GUIDE_SAVES_MARK not in guide and all(
                    html.escape(f) in guide and html.escape(e['note']) in guide
                    for f, e in package.catalog_info(os.path.join(good, 'catalog')).items()))
    code, text2 = run(['--build', good, '--rom', rom_path, '--out', os.path.join(work, 'out-b')])
    same = (code == 0 and made and zips(os.path.join(work, 'out-b')) == made
            and package.read(os.path.join(work, 'out-a', made[0])) == package.read(os.path.join(work, 'out-b', made[0])))
    T.check('second run: byte-identical zip', same, text2)
    code, text3 = run(['--build', good, '--rom', rom_path, '--out', os.path.join(work, 'out-b')])
    T.check('third run into the same folder reports it unchanged', code == 0 and ', unchanged;' in text3, text3)
    rel_out = os.path.join(work, 'out-release')
    code, text = run(['--build', good, '--rom', rom_path, '--out', rel_out, '--release'])
    T.check('--release: %s' % ', '.join(zips(rel_out)),
            code == 0 and zips(rel_out) == ['ogre-battle-gaiden-english-plus-%s-win64.zip' % version], text)

    print('== 2. refusals')
    b = copy_build(build_src, os.path.join(work, 'build-sha1'))
    with open(os.path.join(b, 'ogre_en.sha1'), 'r+') as f:
        s = f.read()
        f.seek(0)
        f.write(('0' if s[0] != '0' else '1') + s[1:])
    refusal('sha1 file does not match ogre_en.ngc', work, b, rom_path, 'sha1')

    b = copy_build(build_src, os.path.join(work, 'build-layout'))
    target = bytearray(rom)
    note = b'English test text written into the save block of file 1'
    target[0x1C0000:0x1C0000 + len(note)] = note
    patch, _ = bps.create(rom, bytes(target))
    put_english(b, rom, bytes(target), patch)
    refusal('layout: patch data in the save blocks', work, b, rom_path, 'layout')

    b = copy_build(build_src, os.path.join(work, 'build-audit'))
    src = rich_rom_piece(rom, 16)
    at = 0x17FF00                                       # CPU 0x37FF00: end of the data region
    target = bytearray(rom)
    target[at:at + 16] = rom[src:src + 16]
    actions = [(bps.SOURCE_READ, 0, at), (bps.TARGET_READ, at, 16), (bps.SOURCE_READ, at + 16, len(rom) - at - 16)]
    patch = bps.serialize(actions, rom, bytes(target))
    T.check('  (the crafted patch applies and its literal holds ROM bytes)',
            bps.apply(rom, patch) == bytes(target) and not bps.audit(rom, patch).ok)
    put_english(b, rom, bytes(target), patch)
    refusal('audit: ROM bytes in a literal of the patch', work, b, rom_path, 'audit')

    b = copy_build(build_src, os.path.join(work, 'build-old-exe'))
    old = time.mktime((2020, 1, 1, 0, 0, 0, 0, 0, -1))
    os.utime(os.path.join(b, 'zenobia.exe'), (old, old))
    refusal('exe: zenobia.exe older than its sources', work, b, rom_path, 'exe')

    b = copy_build(build_src, os.path.join(work, 'build-romdata'))
    src = rich_rom_piece(rom, 64)
    with open(os.path.join(b, 'zenobia.exe'), 'ab') as f:
        f.write(rom[src:src + 64])
    refusal('rom-data: 64 ROM bytes inside zenobia.exe', work, b, rom_path, 'rom-data')

    b = copy_build(build_src, os.path.join(work, 'build-missing'))
    os.remove(os.path.join(b, 'ogre_en.bps'))
    refusal('inputs: ogre_en.bps missing', work, b, rom_path, 'inputs')

    b = copy_build(build_src, os.path.join(work, 'build-nosaves'), catalog=False)
    refusal('saves: no chapter saves', work, b, rom_path, 'saves')
    out = os.path.join(work, 'out-nocatalog')
    code, text = run(['--build', b, '--rom', rom_path, '--out', out, '--no-catalog'])
    T.check('--no-catalog packages without the chapter saves (exit %d)' % code, code == 0 and len(zips(out)) == 1, text)
    if code == 0 and len(zips(out)) == 1:
        z = zipfile.ZipFile(os.path.join(out, zips(out)[0]))
        guide = z.read(z.namelist()[0] + "Player's Guide.html").decode('utf-8')
        T.check('  its guide says the package has no chapter saves', 'This package has no chapter saves.' in guide
                and package.GUIDE_SAVES_MARK not in guide)

    b = copy_build(build_src, os.path.join(work, 'build-noinfo'))
    os.remove(os.path.join(b, 'catalog', package.CATALOG_INFO))
    refusal('saves: catalog.json missing', work, b, rom_path, 'saves')

    b = copy_build(build_src, os.path.join(work, 'build-saveblock'))
    path = first_save(b)
    data = bytearray(package.read(path))
    data[9] = 0x1D                                      # file 2's block instead of file 1's
    open(path, 'wb').write(bytes(data))
    refusal('saves: a chapter save holding another block', work, b, rom_path, 'saves')

    b = copy_build(build_src, os.path.join(work, 'build-saverom'))
    path = first_save(b)
    data = bytearray(package.read(path))
    src = rich_rom_piece(rom, 16)
    data[16 + 0x2000:16 + 0x2010] = rom[src:src + 16]   # inside block 0x1C's data, past the game's 4 KB
    open(path, 'wb').write(bytes(data))
    refusal('saves: 16 ROM bytes inside a chapter save', work, b, rom_path, 'saves')

    b = copy_build(build_src, os.path.join(work, 'build-rerelease'))
    with open(os.path.join(b, 'zenobia.exe'), 'ab') as f:
        f.write(b'\0' * 16)                             # different exe, no ROM data
    code, text = run(['--build', b, '--rom', rom_path, '--out', rel_out, '--release'])
    T.check('refused: --release over a different zip of the same version (exit %d, failed %s)'
            % (code, ', '.join(failed_checks(text))), code == 1 and failed_checks(text) == ['zip'], text)
    T.check('  the existing release zip is kept, no temporary file left',
            zips(rel_out) == ['ogre-battle-gaiden-english-plus-%s-win64.zip' % version])

    print('== 3. classification of matches')
    cases = [(b'\x40\x01\x00\x00\x00\x05\x00\x00', 'padding'),
             (b'\x00\x10\x00\x10\x00\x10\x00\x20' + b'\0' * 7, 'padding'),
             (b'\0' * 7 + b'\xff' * 23 + b'\0' * 5, 'runs'),
             (bytes(range(0x80, 0xB0)), 'counting'),
             (b'VWXYZ' + b'\0' * 18, 'counting'),
             (b''.join(struct.pack('>I', i) for i in range(8)), 'counting'),
             (b''.join(struct.pack('<H', 0x100 + 3 * i) for i in range(8)), 'counting')]
    got = [package.trivial(s) for s, _ in cases]
    T.check('padding, runs, counting (8/16/32-bit) recognised: %s' % got, got == [k for _, k in cases])
    rich = [b'COPYRIGHT BY SNK', b'Zenobia English!', bytes([0x3C, 0x66, 0x7E, 0x81, 0x99, 0x24, 0x18, 0x42])]
    T.check('text and varied bytes are not trivial', all(package.trivial(s) is None for s in rich))
    off, allowed = package.scan_rom_data(rom, [('header', rom[0:0x30])])
    T.check('the cartridge header is allowed (%s)' % dict(allowed), not off and allowed['header'] > 0)
    src = rich_rom_piece(rom, 24)
    off, _ = package.scan_rom_data(rom, [('x', b'padding ' + rom[src:src + 24] + b' padding')])
    T.check('24 ROM bytes inside a file are found as one piece: %s' % off,
            len(off) == 1 and off[0][:3] == ('x', 8, 24))
    src = sparse_rom_piece(rom, 32)
    off, _ = package.scan_rom_data(rom, [('y', b'\xa5\x5a' * 4 + rom[src:src + 32] + b'\x5a\xa5' * 4)])
    T.check('32 low-information ROM bytes (every window trivial, the block not) are found: %s' % off,
            len(off) >= 1 and sum(n for _, _, n, _ in off) >= 24)

    print('== 4. icon (tools/release/mkicon.py)')
    src = os.path.join(package.REPO, 'assets', 'icon', 'zenobia.txt')
    ico1, ico2 = os.path.join(work, 'a.ico'), os.path.join(work, 'b.ico')
    images, data = mkicon.convert(src, ico1, os.path.join(work, 'preview.png'))
    mkicon.convert(src, ico2)
    count = struct.unpack_from('<H', data, 4)[0]
    entries = [struct.unpack_from('<BBBBHHII', data, 6 + 16 * i) for i in range(count)]
    kinds = ['%d%s' % (w or 256, 'png' if data[o:o + 4] == b'\x89PNG' else 'bmp') for w, _, _, _, _, _, _, o in entries]
    T.check('assets/icon/zenobia.txt -> %s (%d bytes)' % (', '.join(kinds), len(data)),
            kinds == ['16bmp', '32bmp', '48bmp', '64png', '96png', '256png'])
    T.check('  same icon twice (deterministic), preview written',
            package.read(ico1) == package.read(ico2) and os.path.getsize(os.path.join(work, 'preview.png')) > 0)
    bad_sources = [('@chars . = none\n@size 2 2\n@data\n..\n.\n', 'row of 1 characters'),
                   ('@chars . = none\n@size 2 2\n@data\n..\n.X\n', "character 'X' has no colour"),
                   ('@chars . = #12345\n', 'is not #RRGGBB'),
                   ('@chars . = none\n@size 2 2\n@data\n..\n..\n@scale 2 to 3\n', 'not a whole multiple'),
                   ('@chars . = none\n@size 2 3\n@data\n..\n..\n..\n', 'square')]
    for i, (text, expect) in enumerate(bad_sources):
        path = os.path.join(work, 'bad%d.txt' % i)
        with open(path, 'w') as f:
            f.write(text)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = mkicon.main([path, os.path.join(work, 'bad%d.ico' % i)])
        T.check('  malformed source %d refused (exit %d): %s' % (i + 1, code, buf.getvalue().strip()[-70:]),
                code == 1 and expect in buf.getvalue() and not os.path.exists(os.path.join(work, 'bad%d.ico' % i)))

    print('== 5. this workstream\'s repository files are ASCII (no Japanese, no stray characters)')
    owned = [os.path.join('tools', 'release', n) for n in sorted(os.listdir(os.path.join(package.REPO, 'tools', 'release')))
             if n.endswith(('.py', '.txt', '.html'))]
    owned += ['VERSION', os.path.join('assets', 'icon', 'zenobia.txt'), os.path.join('runtime', 'src', 'frontend', 'zenobia.rc'),
              os.path.join('runtime', 'src', 'frontend', 'resource.h'), os.path.join('docs', 'workstreams', 'release.md'),
              os.path.join('docs', 'guide-sources.md')]
    bad = []
    for name in owned:
        path = os.path.join(package.REPO, name)
        if os.path.isfile(path) and any(b > 127 for b in package.read(path)):
            bad.append(name)
    T.check('%d files checked%s' % (len(owned), ', non-ASCII: ' + ', '.join(bad) if bad else ''), not bad)

    print('== 6. the player and the package agree on the names of the guide and the saves folder')
    gui = package.read(os.path.join(package.REPO, 'runtime', 'src', 'frontend', 'gui.c')).decode('utf-8')
    names = dict(re.findall(r'#define\s+(GUIDE_FILE|CATALOG_DIR)\s+L"([^"]*)"', gui))
    T.check('gui.c opens %s' % names, names == {'GUIDE_FILE': package.GUIDE_NAME, 'CATALOG_DIR': package.CATALOG_NAME})

    print('passed %d, failed %d (%.1f s)' % (T.passed, T.failed, time.time() - t0))
    return 1 if T.failed else 0


if __name__ == '__main__':
    sys.exit(main())
