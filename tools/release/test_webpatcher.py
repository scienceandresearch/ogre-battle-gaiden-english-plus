"""Tests of the one-file web patcher ("Patch your game.html").

    python -m tools.release.test_webpatcher [rom/baserom.ngc]

Builds the page from build/ogre_en.bps and runs the page's own <script> in
Node (which has the browser APIs the page uses: atob, Blob, Response,
DecompressionStream). With the original ROM it checks the real cases: the
plain file, a stored and a deflate .zip, an over-dump, an English ROM, a
changed ROM, damaged and password-protected zips and other archives. Without
Node or the ROM those tests are skipped. Nothing is written outside a
temporary folder.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from . import webpatcher as W

REPO = W.REPO
BUILD = os.path.join(REPO, 'build')

NODE_DRIVER = r"""
const fs = require('fs');
const P = require(process.argv[2]);
const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const patch = P.base64ToBytes(P.PATCH_BASE64_FOR_TEST);
(async () => {
  const out = {};
  for (const c of cases) {
    try {
      const r = await P.translate(c.name, new Uint8Array(fs.readFileSync(c.path)), patch);
      out[c.id] = { kind: r.kind, sha1: r.english ? P.sha1Hex(r.english) : null };
    } catch (e) {
      out[c.id] = { error: e.message };
    }
  }
  out.selftest = { sha1_abc: P.sha1Hex(new TextEncoder().encode('abc')),
                   crc_abc: P.crc32(new TextEncoder().encode('abc')) };
  process.stdout.write(JSON.stringify(out));
})();
"""


def page_and_sha1():
    patch = open(os.path.join(BUILD, 'ogre_en.bps'), 'rb').read()
    english = open(os.path.join(BUILD, 'ogre_en.sha1')).read().split()[0]
    return W.build(patch, english, 'test'), english


def test_static():
    page, english = page_and_sha1()
    text = page.decode('utf-8')
    assert text.isascii(), 'the page is ASCII'
    assert "default-src 'none'" in text, 'the page forbids network access'
    assert not re.search(r'https?://', text), 'the page links nowhere'
    assert not re.findall(r'@[A-Z0-9_]+@', text), 'every field is filled'
    assert english in text and W.EXPECTED_SHA1.lower() in text
    assert len(page) < 400 * 1024, 'the page is small'


def node():
    return shutil.which('node')


def run_cases(rom):
    page, english = page_and_sha1()
    tmp = tempfile.mkdtemp(prefix='webpatcher-')
    try:
        script = W.script_of(page)
        script += '\nmodule.exports.PATCH_BASE64_FOR_TEST = PATCH_BASE64;\n'
        mod = os.path.join(tmp, 'patcher.cjs')
        with open(mod, 'w', encoding='utf-8') as f:
            f.write(script)
        drv = os.path.join(tmp, 'driver.cjs')
        with open(drv, 'w', encoding='utf-8') as f:
            f.write(NODE_DRIVER)
        english_rom = open(os.path.join(BUILD, 'ogre_en.ngc'), 'rb').read()
        changed = bytearray(rom)
        changed[0x1000] ^= 0xFF

        def put(name, data):
            path = os.path.join(tmp, name)
            with open(path, 'wb') as f:
                f.write(data)
            return path

        def zipped(method, name='Game (Japan).ngc', extra=None):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', method) as z:
                if extra:
                    z.writestr('readme.txt', extra)
                z.writestr(name, rom)
            return buf.getvalue()

        stored = zipped(zipfile.ZIP_STORED)
        deflated = zipped(zipfile.ZIP_DEFLATED, extra='hello')
        bad_crc = bytearray(stored)
        bad_crc[len(bad_crc) // 2] ^= 0x01                     # inside the stored data
        locked = bytearray(stored)
        locked[6] |= 1                                         # local header flags
        cd = bytes(locked).rfind(b'PK\x01\x02')
        locked[cd + 8] |= 1                                    # central directory flags
        cases = [
            ('plain', 'game.ngc', put('game.ngc', rom)),
            ('stored', 'game.zip', put('stored.zip', stored)),
            ('deflate', 'game.zip', put('deflate.zip', deflated)),
            ('overdump', 'big.ngc', put('big.ngc', rom + b'\xFF' * len(rom))),
            ('english', 'en.ngc', put('en.ngc', english_rom)),
            ('changed', 'changed.ngc', put('changed.ngc', bytes(changed))),
            ('badcrc', 'bad.zip', put('bad.zip', bytes(bad_crc))),
            ('locked', 'locked.zip', put('locked.zip', bytes(locked))),
            ('sevenzip', 'game.7z', put('game.7z', b'7z\xbc\xaf\x27\x1c' + bytes(32))),
        ]
        spec = os.path.join(tmp, 'cases.json')
        with open(spec, 'w') as f:
            json.dump([{'id': i, 'name': n, 'path': p} for i, n, p in cases], f)
        r = subprocess.run([node(), drv, mod, spec], capture_output=True, text=True, timeout=300)
        if r.returncode:
            raise AssertionError('node failed: %s' % r.stderr[-2000:])
        return json.loads(r.stdout), english
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_node(rom):
    got, english = run_cases(rom)
    assert got['selftest']['sha1_abc'] == 'a9993e364706816aba3e25717850c26c9cd0d89d', got['selftest']
    assert got['selftest']['crc_abc'] == 0x352441C2, got['selftest']
    for case in ('plain', 'stored', 'deflate', 'overdump'):
        assert got[case] == {'kind': 'translated', 'sha1': english}, (case, got[case])
    assert got['english'] == {'kind': 'english', 'sha1': None}, got['english']
    assert 'not the original Japanese game' in got['changed'].get('error', ''), got['changed']
    assert 'damaged' in got['badcrc'].get('error', ''), got['badcrc']
    assert 'password' in got['locked'].get('error', ''), got['locked']
    assert 'compressed archive' in got['sevenzip'].get('error', ''), got['sevenzip']


def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'rom', 'baserom.ngc')
    tests = [('test_static', test_static, False), ('test_node', test_node, True)]
    failed = skipped = 0
    for name, fn, needs_rom in tests:
        if needs_rom and (not os.path.isfile(rom_path) or not node()):
            print('skip %s (needs %s)' % (name, 'the ROM' if not os.path.isfile(rom_path) else 'node'))
            skipped += 1
            continue
        try:
            fn(open(rom_path, 'rb').read()) if needs_rom else fn()
            print('ok   %s' % name)
        except Exception as e:                       # report every failure, keep going
            failed += 1
            print('FAIL %s: %s' % (name, e))
    print('%d tests, %d failed, %d skipped' % (len(tests), failed, skipped))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
