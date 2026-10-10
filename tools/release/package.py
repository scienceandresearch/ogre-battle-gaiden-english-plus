"""Build the release zip: the Windows player, the English patch and the docs.

    python -m tools.release.package [--out dist] [--build build]
                                    [--rom rom/baserom.ngc] [--release]

Writes OUT/ogre-battle-gaiden-en-<version>-win64.zip from what the build
folder holds now; it never builds anything (run build.bat and
python -m tools.patch.build rom/baserom.ngc first). <version> is the VERSION
file (MAJOR.MINOR.PATCH); without --release, "-dev+" and the first 8 hex
digits of the English ROM's SHA-1 are appended, e.g. 0.1.0-dev+e63bffd1.

The zip holds one folder, ogre-battle-gaiden-en-<version>, with
  README.txt                tools/release/README.txt, version/date/checksums filled in
  zenobia.exe               the player (build folder)
  ogre_en.bps, ogre_en.sha1 the patch and the English ROM's SHA-1 (build folder)
  LICENSE.txt, THIRD_PARTY_NOTICES.txt   from the repository root
  Patch your game.html      the one-file web patcher (tools/release/webpatcher.py):
                            choose your game in a browser, save the English ROM
  patch-tools/              apply.py (tools/release/patch_tools_apply.py) and the
                            applier modules it imports, unchanged
Text files get CRLF line ends; everything else is copied byte for byte.

It refuses (exit 1, nothing written) when
  * the ROM is not the expected original, or ogre_en.sha1 does not match
    ogre_en.ngc;
  * the layout check (python -m tools.patch.layout) or the BPS audit
    (python -m tools.patch.bps audit) fails, or ogre_en.bps does not turn
    the original into ogre_en.ngc;
  * zenobia.exe is older than its sources (asked from the build system with
    a Ninja dry run when the build folder has build.ninja, else by file
    times), its version resource is not VERSION, or it needs the Visual C++
    runtime DLLs;
  * a packaged file contains ROM data: 8 or more bytes of the original ROM
    in any file except ogre_en.bps (which the audit covers). Matches are
    allowed, and counted, only when they are data that any binary holds
    (padding: all but at most 4 bytes the same; runs: at most 3 stretches
    of a repeated byte; counting: a constant step in 8/16/32-bit units with
    at most 2 breaks) or occur in the ROM only inside the cartridge header
    (0x00-0x3F: the licence string and the game's title, which the player
    compares to recognise the ROM). A longer match is judged as a whole, so
    a block of real ROM data is never let through window by window;
  * a file looks like game data (.ngc/.ngp/.npc/.sav/.state, a 2 MB file,
    zenobia.ini, .pdb), a text file holds Japanese, README.txt has an
    unfilled @FIELD@ or does not name a packaged file;
  * with --release, a different zip of the same version exists already.
The zip is written to a temporary file, read back, extracted and its
patch-tools applier run on the ROM (the result must have ogre_en.sha1's
SHA-1) before it replaces the file in OUT.

Deterministic: the same inputs give a byte-identical zip (fixed order and
attributes; every entry is dated with the newest input file's time in UTC,
or SOURCE_DATE_EPOCH when set) with the same Python build: the compressed
bytes depend on its zlib (Python 3.14's zlib-ng packs differently from the
classic zlib of 3.12), so the output names the zlib it used.
"""
import argparse
import ast
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib
from collections import Counter

from ..patch import bps
from ..recomp.rom import EXPECTED_SHA1
from . import pe as pefile
from . import webpatcher

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
NAME = 'ogre-battle-gaiden-en'
PLATFORM = 'win64'
ROM_SIZE = 2 * 1024 * 1024
WINDOW = 8                      # same limit as the BPS audit (tools/patch/bps.py AUDIT_LIMIT)
HEADER_END = 0x40               # cartridge header: licence string, entry point, ID, title
README_TEMPLATE = 'tools/release/README.txt'
LAUNCHER = 'tools/release/patch_tools_apply.py'
APPLIER = 'tools/patch/apply.py'
TEXT_DOCS = (('LICENSE', 'LICENSE.txt'), ('THIRD_PARTY_NOTICES.md', 'THIRD_PARTY_NOTICES.txt'))
FORBIDDEN_EXT = ('.ngc', '.ngp', '.npc', '.sav', '.state', '.ini', '.pdb', '.zip', '.7z', '.rar', '.gz')
TEXT_EXT = ('.txt', '.py', '.sha1', '.md', '.html')
VC_RUNTIME = re.compile(r'^(vcruntime|msvcp|msvcr|ucrtbase|api-ms-win-crt-)', re.I)
# Files that make up zenobia.exe besides the C sources listed in CMakeLists.txt
# (CMakeLists.txt itself is covered by the Ninja dry run only).
EXE_EXTRA_SOURCES = ('VERSION', 'assets/icon/zenobia.txt', 'tools/release/mkicon.py')
EXE_FALLBACK_GLOBS = (('runtime/src/frontend', ('.c', '.h', '.rc', '.manifest')),
                      ('runtime/src/core', ('.c', '.h')), ('runtime/src/cpu', ('.c', '.h')),
                      ('third_party/z80', ('.c', '.h')))
# Japanese script: CJK punctuation, kana, CJK ideographs, compatibility
# ideographs, full-width forms (built from code points: keep this file ASCII)
JAPANESE = re.compile('[%s]' % ''.join('%s-%s' % (chr(a), chr(b)) for a, b in (
    (0x3000, 0x30FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0xFF00, 0xFFEF))))


class Report:
    """Collects the result of every check; problems make the run refuse."""

    def __init__(self):
        self.problems = []

    def ok(self, check, text):
        print('  ok    %-9s %s' % (check, text))

    def fail(self, check, text):
        print('  FAIL  %-9s %s' % (check, text))
        self.problems.append((check, text))

    def note(self, text):
        print('                  %s' % text)


def rel(path):
    try:
        r = os.path.relpath(path, REPO)
    except ValueError:
        return path
    return path if r.startswith('..') else r


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def crlf(data):
    return data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')


# ---------------------------------------------------------------------------
# version

def read_version(repo=REPO):
    """MAJOR.MINOR.PATCH from the VERSION file."""
    path = os.path.join(repo, 'VERSION')
    words = read(path).decode('ascii', 'replace').split()
    text = words[0] if words else ''
    if not re.fullmatch(r'\d+\.\d+\.\d+', text):
        raise ValueError('%s must hold MAJOR.MINOR.PATCH, not %r' % (rel(path), text))
    return text


def package_version(version, english_sha1, release):
    return version if release else '%s-dev+%s' % (version, english_sha1[:8])


# ---------------------------------------------------------------------------
# build checks

def run_module(args):
    """Run python -m ARGS in the repository; returns (exit code, output)."""
    r = subprocess.run([sys.executable, '-m'] + args, cwd=REPO, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout + r.stderr).strip()


def ninja_program(build):
    """The Ninja executable recorded in BUILD/CMakeCache.txt, or None."""
    cache = os.path.join(build, 'CMakeCache.txt')
    if not os.path.isfile(os.path.join(build, 'build.ninja')) or not os.path.isfile(cache):
        return None
    with open(cache, encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith('CMAKE_MAKE_PROGRAM:'):
                path = line.split('=', 1)[1].strip()
                if 'ninja' in os.path.basename(path).lower() and os.path.isfile(path):
                    return path
    return None


def ninja_dry_run(build, target='zenobia'):
    """(up_to_date, [what the build would do]) from a Ninja dry run, or None
    when there is no usable Ninja build in BUILD."""
    ninja = ninja_program(build)
    if not ninja:
        return None
    try:
        r = subprocess.run([ninja, '-C', build, '-n', target], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    if 'no work to do' in r.stdout:
        return True, []
    steps = [re.sub(r'^\[\d+/\d+\]\s*', '', line) for line in r.stdout.splitlines() if line.startswith('[')]
    return False, steps or [r.stdout.strip()]


def _cmake_list(text, pattern):
    m = re.search(pattern, text, re.S)
    if not m:
        return []
    return [w for w in m.group(1).split() if '${' not in w and not w.startswith('#')]


def exe_sources(repo=REPO):
    """Every file zenobia.exe is built from: the C/RC sources CMakeLists.txt
    lists for it (and the core), the headers they include, VERSION and the
    icon source. Falls back to the source folders if the lists are not found."""
    cm = read(os.path.join(repo, 'CMakeLists.txt')).decode('utf-8', 'replace')
    cm = re.sub(r'#[^\n]*', '', cm)
    files = (_cmake_list(cm, r'set\(\s*NGP_CORE_SOURCES\s+([^)]*)\)')
             + _cmake_list(cm, r'add_executable\(\s*zenobia\s+WIN32\s+([^)]*)\)'))
    for m in re.finditer(r'target_sources\(\s*zenobia\s+PRIVATE\s+([^)]*)\)', cm, re.S):
        files += [w for w in m.group(1).split() if '${' not in w]
    found = set()
    if files:
        todo = [os.path.normpath(os.path.join(repo, f)) for f in files]
    else:
        todo = []
        for folder, exts in EXE_FALLBACK_GLOBS:
            d = os.path.join(repo, folder)
            todo += [os.path.join(d, n) for n in sorted(os.listdir(d)) if n.endswith(exts)]
    roots = [os.path.join(repo, 'runtime', 'src')]
    while todo:
        f = todo.pop()
        if f in found or not os.path.isfile(f):
            continue
        found.add(f)
        if f.endswith(('.c', '.h', '.rc')):
            text = read(f).decode('utf-8', 'replace')
            for inc in re.findall(r'^\s*#\s*include\s*"([^"]+)"', text, re.M):
                for base in [os.path.dirname(f)] + roots:
                    p = os.path.normpath(os.path.join(base, inc))
                    if os.path.isfile(p):
                        todo.append(p)
                        break
    for extra in EXE_EXTRA_SOURCES:
        p = os.path.join(repo, extra)
        if os.path.isfile(p):
            found.add(os.path.normpath(p))
    return sorted(found)


def check_exe_current(rep, build, exe_path):
    dry = ninja_dry_run(build)
    if dry is not None:
        current, steps = dry
        if current:
            rep.ok('exe', 'zenobia.exe is up to date (Ninja dry run in %s: no work to do)' % rel(build))
        else:
            rep.fail('exe', 'zenobia.exe is older than its sources: the build would run %d step(s), '
                     'e.g. "%s". Run build.bat first.' % (len(steps), steps[0][:100]))
        return
    exe_time = os.path.getmtime(exe_path)
    sources = exe_sources()
    newer = [s for s in sources if os.path.getmtime(s) > exe_time]
    if newer:
        rep.fail('exe', 'zenobia.exe is older than %d of its sources (%s). Run build.bat first.'
                 % (len(newer), ', '.join(rel(p) for p in newer[:5]) + (', ...' if len(newer) > 5 else '')))
    else:
        rep.ok('exe', 'zenobia.exe is newer than its %d source files (file times; no Ninja build in %s)'
               % (len(sources), rel(build)))


def check_exe_resources(rep, exe, version):
    try:
        p = pefile.PE(exe)
        vi = p.version_info()
        groups = p.icon_groups()
        dlls = p.imports()
    except (pefile.PEError, struct.error, ValueError, IndexError) as e:
        rep.fail('exe', 'zenobia.exe cannot be read as a Windows program: %s' % e)
        return
    want = tuple(int(x) for x in version.split('.'))
    if vi is None:
        rep.fail('exe', 'zenobia.exe has no version resource (build it with the current CMakeLists.txt)')
    elif vi['file_version'][:3] != want or vi['product_version'][:3] != want:
        rep.fail('exe', 'zenobia.exe has version %d.%d.%d.%d, VERSION says %s: run build.bat'
                 % (vi['file_version'] + (version,)))
    else:
        rep.ok('exe', 'version resource %d.%d.%d.%d = VERSION, "%s"' % (
            vi['file_version'] + (vi['strings'].get('FileDescription', ''),)))
    if groups:
        sizes = sorted({w for items in groups.values() for w, _, _, _ in items})
        rep.ok('exe', 'icon: %s px' % '/'.join(str(s) for s in sizes))
    else:
        rep.note('note: zenobia.exe has no icon (built without Python?); packaging anyway')
    vc = [d for d in dlls if VC_RUNTIME.match(d)]
    if vc:
        rep.fail('exe', 'zenobia.exe needs the Visual C++ runtime (%s): link it statically (/MT)' % ', '.join(vc))


# ---------------------------------------------------------------------------
# package contents

def import_closure(repo, start):
    """Repository-relative paths of START and every module of the `tools`
    package it imports (directly or indirectly), with the packages'
    __init__.py files."""
    out = set()
    todo = [start]
    while todo:
        path = todo.pop()
        if path in out:
            continue
        out.add(path)
        package = path[:-3].split('/')[:-1]             # the module's package (an __init__'s own)
        for i in range(1, len(package) + 1):            # every enclosing package
            init = '/'.join(package[:i]) + '/__init__.py'
            if os.path.isfile(os.path.join(repo, init)) and init not in out:
                todo.append(init)
        tree = ast.parse(read(os.path.join(repo, path)).decode('utf-8'), path)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    base = package[:len(package) - (node.level - 1)] if node.level > 1 else package
                    mod = base + (node.module.split('.') if node.module else [])
                else:
                    mod = node.module.split('.') if node.module else []
                names = [mod] + [mod + [a.name] for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name.split('.') for a in node.names]
            for mod in names:
                if not mod or mod[0] != 'tools':
                    continue
                for cand in ('/'.join(mod) + '.py', '/'.join(mod) + '/__init__.py'):
                    if os.path.isfile(os.path.join(repo, cand)):
                        todo.append(cand)
                        break
    return sorted(out)


def readme_fields(version, date, rom, english):
    return {
        'VERSION': version,
        'DATE': date,
        'ORIGINAL_SIZE': format(len(rom), ','),
        'ORIGINAL_CRC32': '%08X' % zlib.crc32(rom),
        'ORIGINAL_MD5': hashlib.md5(rom).hexdigest(),
        'ORIGINAL_SHA1': sha1(rom),
        'ENGLISH_SHA1': sha1(english),
        'ENGLISH_CRC32': '%08X' % zlib.crc32(english),
    }


def fill_template(text, fields):
    for k, v in fields.items():
        text = text.replace('@%s@' % k, v)
    return text


def stage(top, build_files, readme, repo=REPO, page=None):
    """[(zip name, bytes or None for a folder, source description)] in zip order."""
    exe, patch, sha1_text = build_files
    entries = [(top + '/', None, ''),
               (top + '/README.txt', crlf(readme), README_TEMPLATE),
               (top + '/zenobia.exe', exe, 'build'),
               (top + '/ogre_en.bps', patch, 'build'),
               (top + '/ogre_en.sha1', sha1_text, 'build')]
    if page is not None:
        entries.append((top + '/' + webpatcher.PAGE_NAME, page, webpatcher.TEMPLATE))
    for src, name in TEXT_DOCS:
        entries.append((top + '/' + name, crlf(read(os.path.join(repo, src))), src))
    tools = top + '/patch-tools/'
    entries.append((tools, None, ''))
    entries.append((tools + 'apply.py', read(os.path.join(repo, LAUNCHER)), LAUNCHER))
    folders = set()
    for path in import_closure(repo, APPLIER):
        parts = path.split('/')
        for i in range(1, len(parts)):
            d = tools + '/'.join(parts[:i]) + '/'
            if d not in folders:
                folders.add(d)
                entries.append((d, None, ''))
        entries.append((tools + path, read(os.path.join(repo, path)), path))
    return entries


def check_contents(rep, entries, top):
    files = [(n, d) for n, d, _ in entries if d is not None]
    bad = []
    for name, data in files:
        base = name.rsplit('/', 1)[-1].lower()
        if base.endswith(FORBIDDEN_EXT) or base == 'zenobia.ini' or len(data) == ROM_SIZE:
            bad.append(name)
    if bad:
        rep.fail('contents', 'files that look like game data or local settings: %s' % ', '.join(bad))
    japanese = []
    for name, data in files:
        if name.lower().endswith(TEXT_EXT):
            try:
                text = data.decode('utf-8')
            except UnicodeDecodeError:
                rep.fail('contents', '%s is not UTF-8 text' % name)
                continue
            if JAPANESE.search(text):
                japanese.append(name)
    if japanese:
        rep.fail('contents', 'Japanese text in %s' % ', '.join(japanese))
    readme = dict(files)[top + '/README.txt'].decode('utf-8', 'replace')
    left = sorted(set(re.findall(r'@[A-Z0-9_]+@', readme)))
    if left:
        rep.fail('contents', 'README.txt has unfilled fields: %s' % ', '.join(left))
    items = sorted({n[len(top) + 1:].split('/')[0] for n, _, _ in entries if len(n) > len(top) + 1})
    missing = [i for i in items if i not in readme]
    if missing:
        rep.fail('contents', 'README.txt does not mention %s' % ', '.join(missing))
    if not bad and not japanese and not left and not missing:
        rep.ok('contents', '%d files, %d folders; README fields filled, every item described, no Japanese'
               % (len(files), len(entries) - len(files)))


# ---------------------------------------------------------------------------
# ROM data scan
#
# Every WINDOW-byte window of a packaged file that also occurs in the ROM is
# a hit. Overlapping hits form a region. A region is allowed when, as a
# whole, it is trivial data that occurs in any binary (see `trivial`) or
# occurs in the ROM only inside the cartridge header; otherwise it is cut
# into the longest pieces that occur in the ROM as they are, and each piece
# must be trivial or header-only. Anything else is ROM data. (Windows of one
# repeated byte are not hits at all: fill bytes.)

PADDING_OTHERS = 4             # padding: at most this many bytes differ from the commonest value
MAX_RUNS = 3                   # runs: at most this many stretches of one repeated byte
COUNTING_BREAKS = 2            # counting: at most this many breaks of the constant step


def windows(data):
    """Every WINDOW-byte window of data, as native-endian 64-bit integers."""
    out = set()
    mv = memoryview(data)
    for k in range(WINDOW):
        m = (len(data) - k) // WINDOW
        if m > 0:
            out.update(mv[k:k + m * WINDOW].cast('Q'))
    return out


def window_bytes(value):
    return struct.pack('=Q', value)


def trivial(s):
    """'padding', 'runs' or 'counting' when s is data that any binary holds,
    else None:
      padding   all but at most 4 bytes have one value (zero fill with small
                numbers in it);
      runs      at most 3 stretches of one repeated byte each;
      counting  the bytes, or the 16- or 32-bit units, step by a constant
                amount, with at most 2 breaks (checked over 4 units or more)."""
    n = len(s)
    if n - max(s.count(bytes((v,))) for v in set(s)) <= PADDING_OTHERS:
        return 'padding'
    if 1 + sum(1 for i in range(1, n) if s[i] != s[i - 1]) <= MAX_RUNS:
        return 'runs'
    for d in (1, 2, 4):
        if n >= 4 * d and sum(1 for i in range(2 * d, n)
                              if (s[i] - 2 * s[i - d] + s[i - 2 * d]) & 0xFF) <= COUNTING_BREAKS:
            return 'counting'
    return None


def header_only(rom, s):
    """True if s occurs in the ROM, and only inside the cartridge header."""
    p = rom.find(s)
    if p < 0:
        return False
    while p >= 0:
        if p + len(s) > HEADER_END:
            return False
        p = rom.find(s, p + 1)
    return True


def rom_hits(rom, wanted):
    """The values of `wanted` (window integers) that occur in the ROM."""
    hits = set()
    mv = memoryview(rom)
    for k in range(WINDOW):
        m = (len(rom) - k) // WINDOW
        if m > 0:
            hits.update(wanted.intersection(mv[k:k + m * WINDOW].cast('Q')))
    return hits


def hit_positions(data, hits):
    out = []
    mv = memoryview(data)
    for k in range(WINDOW):
        m = (len(data) - k) // WINDOW
        if m > 0:
            out.extend(k + i * WINDOW for i, v in enumerate(mv[k:k + m * WINDOW].cast('Q')) if v in hits)
    out.sort()
    return out


def longest_match(rom, data, pos, limit):
    """(n, ROM offset): the longest data[pos:pos+n], WINDOW <= n <= limit,
    that occurs in the ROM (data[pos:pos+WINDOW] must occur)."""
    n, q = WINDOW, rom.find(data[pos:pos + WINDOW])
    step = WINDOW
    while n < limit:
        m = min(n + step, limit)
        r = rom.find(data[pos:pos + m])
        if r < 0:
            lo, hi = n, m
            while hi - lo > 1:
                mid = (lo + hi) // 2
                r2 = rom.find(data[pos:pos + mid])
                if r2 >= 0:
                    lo, q = mid, r2
                else:
                    hi = mid
            return lo, q
        n, q = m, r
        step *= 2
    return n, q


def scan_rom_data(rom, files):
    """Look for ROM data in files [(name, bytes)]. Returns (offending,
    allowed): offending = [(name, file offset, length, ROM offset)];
    allowed = Counter of the allowed regions and pieces by kind."""
    per_file = [(name, data, windows(data)) for name, data in files]
    wanted = set()
    for _, _, w in per_file:
        wanted |= w
    hits = {v for v in rom_hits(rom, wanted) if len(set(window_bytes(v))) > 1}
    offending, allowed = [], Counter()
    for name, data, w in per_file:
        if not w & hits:
            continue
        positions = hit_positions(data, hits)
        regions = []
        for x in positions:
            if regions and x < regions[-1][1]:
                regions[-1][1] = max(regions[-1][1], x + WINDOW)
            else:
                regions.append([x, x + WINDOW])
        k = 0
        for a, b in regions:
            inside = []
            while k < len(positions) and positions[k] < b:
                if positions[k] >= a:
                    inside.append(positions[k])
                k += 1
            kind = trivial(data[a:b]) or ('header' if header_only(rom, data[a:b]) else None)
            if kind:
                allowed[kind] += 1
                continue
            end = -1
            for x in inside:
                if x + WINDOW <= end:
                    continue
                n, q = longest_match(rom, data, x, b - x)
                piece = data[x:x + n]
                kind = trivial(piece) or ('header' if header_only(rom, piece) else None)
                if kind:
                    allowed[kind] += 1
                else:
                    offending.append((name, x, n, q))
                end = x + n
    return offending, allowed


def check_rom_data(rep, rom, entries):
    files = [(n.split('/', 1)[1], d) for n, d, _ in entries if d is not None and not n.endswith('/ogre_en.bps')]
    offending, allowed = scan_rom_data(rom, files)
    if offending:
        for name, off, n, roff in offending[:20]:
            rep.note('%s: %d bytes at offset 0x%X are ROM data (ROM offset 0x%X)' % (name, n, off, roff))
        rep.fail('rom-data', '%d piece(s) of the original ROM in %s' % (
            len(offending), ', '.join(sorted({o[0] for o in offending}))))
    else:
        rep.ok('rom-data', 'no ROM data in %d files (ogre_en.bps: see audit); matches allowed: %s' % (
            len(files), ', '.join('%d %s' % (allowed[k], k) for k in ('padding', 'runs', 'counting', 'header')
                                  if allowed[k]) or 'none'))


# ---------------------------------------------------------------------------
# zip

def zip_time(paths):
    """(DOS date_time tuple, YYYY-MM-DD): SOURCE_DATE_EPOCH, else the newest
    modification time among `paths`, in UTC."""
    env = os.environ.get('SOURCE_DATE_EPOCH')
    t = int(env) if env and env.isdigit() else int(max(os.path.getmtime(p) for p in paths))
    tm = time.gmtime(max(t, 315532800))                  # zip dates start in 1980
    return (tm.tm_year, tm.tm_mon, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec & ~1), \
        '%04d-%02d-%02d' % (tm.tm_year, tm.tm_mon, tm.tm_mday)


def write_zip(path, entries, date_time):
    with zipfile.ZipFile(path, 'w') as z:
        for name, data, _ in entries:
            zi = zipfile.ZipInfo(name, date_time)
            zi.create_system = 0                          # MS-DOS attributes, the same on every OS
            if data is None:
                zi.external_attr = 0x10                   # directory
                z.writestr(zi, b'', compress_type=zipfile.ZIP_STORED)
            else:
                zi.external_attr = 0x20                   # archive bit, as Windows sets it
                packed = zlib.compressobj(9, zlib.DEFLATED, -15)
                smaller = len(packed.compress(data) + packed.flush()) < len(data)
                z.writestr(zi, data, compress_type=zipfile.ZIP_DEFLATED if smaller else zipfile.ZIP_STORED,
                           compresslevel=9 if smaller else None)


def verify_zip(rep, path, entries, rom, english_sha1, top):
    """Read the zip back, extract it and run its applier."""
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if names != [n for n, _, _ in entries]:
            rep.fail('zip', 'the zip does not hold the staged files in order')
            return None
        for (name, data, _), info in zip(entries, infos):
            if data is not None and z.read(info) != data:
                rep.fail('zip', '%s differs from its source after zipping' % name)
                return None
    tmp = tempfile.mkdtemp(prefix='ogre-release-check-')
    try:
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        original = os.path.join(tmp, 'original.ngc')
        with open(original, 'wb') as f:
            f.write(rom)
        out = os.path.join(tmp, 'english.ngc')
        folder = os.path.join(tmp, top)
        launcher = os.path.join(folder, 'patch-tools', 'apply.py')
        before = sorted(os.path.relpath(os.path.join(d, f), folder) for d, _, fs in os.walk(folder) for f in fs)
        r = subprocess.run([sys.executable, '-I', launcher, original, '-o', out], cwd=tmp,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        got = sha1(read(out)) if os.path.isfile(out) else None
        if r.returncode != 0 or got != english_sha1:
            rep.fail('zip', 'patch-tools/apply.py from the zip failed (exit %d): %s'
                     % (r.returncode, (r.stdout + r.stderr).strip()[-300:]))
            return None
        after = sorted(os.path.relpath(os.path.join(d, f), folder) for d, _, fs in os.walk(folder) for f in fs)
        if after != before:
            rep.fail('zip', 'patch-tools/apply.py left files in the release folder: %s'
                     % ', '.join(sorted(set(after) - set(before)))[:300])
            return None
        rep.ok('zip', 'read back and extracted; patch-tools/apply.py makes the English ROM (SHA-1 %s) '
               'and leaves the folder as it was' % got[:8])
        return infos
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.release.package',
                                 description='Build and check the release zip (see the module help).')
    ap.add_argument('--out', default='dist', help='output folder (default: dist)')
    ap.add_argument('--build', default='build', help='build folder with zenobia.exe and ogre_en.* (default: build)')
    ap.add_argument('--rom', default=os.path.join('rom', 'baserom.ngc'),
                    help='the original ROM (default: rom/baserom.ngc)')
    ap.add_argument('--release', action='store_true',
                    help='a release: the version without the -dev+<ROM SHA-1> suffix')
    args = ap.parse_args(argv)
    build, out_dir, rom_path = (os.path.abspath(p) for p in (args.build, args.out, args.rom))
    paths = {k: os.path.join(build, k) for k in ('zenobia.exe', 'ogre_en.bps', 'ogre_en.sha1', 'ogre_en.ngc')}
    rep = Report()
    print('Release package: build %s, ROM %s' % (rel(build), rel(rom_path)))

    try:
        version = read_version()
        rep.ok('version', 'VERSION %s' % version)
    except (OSError, ValueError) as e:
        rep.fail('version', str(e))
        version = None
    missing = [p for p in list(paths.values()) + [rom_path] if not os.path.isfile(p)]
    if missing:
        rep.fail('inputs', 'missing: %s' % ', '.join(rel(p) for p in missing))
        print('refused: %d problem(s): %s' % (len(rep.problems), ', '.join(c for c, _ in rep.problems)))
        return 1
    rom, english, patch, sha1_text, exe = (read(p) for p in (
        rom_path, paths['ogre_en.ngc'], paths['ogre_en.bps'], paths['ogre_en.sha1'], paths['zenobia.exe']))

    rom_ok = sha1(rom) == EXPECTED_SHA1
    if rom_ok:
        rep.ok('rom', 'original ROM, SHA-1 %s' % EXPECTED_SHA1)
    else:
        rep.fail('rom', '%s is not the original ROM (SHA-1 %s, expected %s)' % (rel(rom_path), sha1(rom), EXPECTED_SHA1))

    english_sha1 = sha1(english)
    words = sha1_text.decode('ascii', 'replace').split()
    if words and words[0].lower() == english_sha1:
        rep.ok('sha1', 'ogre_en.sha1 = SHA-1 of ogre_en.ngc (%s)' % english_sha1)
    else:
        rep.fail('sha1', 'ogre_en.sha1 says %s, but ogre_en.ngc has SHA-1 %s'
                 % (words[0] if words else '(empty)', english_sha1))

    code, text = run_module(['tools.patch.layout', paths['ogre_en.ngc'], rom_path])
    if code == 0:
        rep.ok('layout', 'python -m tools.patch.layout: OK')
        for line in text.splitlines():
            rep.note(line.strip())
    else:
        last = text.splitlines()[-1] if text else 'exit %d' % code
        rep.fail('layout', 'python -m tools.patch.layout refuses ogre_en.ngc: %s' % re.sub(r'^layout:\s*', '', last))

    code, text = run_module(['tools.patch.bps', 'audit', rom_path, paths['ogre_en.bps']])
    if code == 0:
        rep.ok('audit', text.splitlines()[-1] if text else 'OK')
    else:
        rep.fail('audit', 'python -m tools.patch.bps audit: %s' % ' | '.join(text.splitlines()[:3]))

    if rom_ok:
        try:
            made = bps.apply(rom, patch)
            if made == english:
                rep.ok('patch', 'ogre_en.bps turns the original into ogre_en.ngc (%s bytes)' % format(len(patch), ','))
            else:
                rep.fail('patch', 'ogre_en.bps does not make ogre_en.ngc (SHA-1 %s): they are from different builds'
                         % sha1(made))
        except bps.BpsError as e:
            rep.fail('patch', 'ogre_en.bps cannot be applied to the original: %s' % e)

    check_exe_current(rep, build, paths['zenobia.exe'])
    if version:
        check_exe_resources(rep, exe, version)

    if not version:
        print('refused: %d problem(s): %s' % (len(rep.problems), ', '.join(c for c, _ in rep.problems)))
        return 1
    full_version = package_version(version, english_sha1, args.release)
    top = '%s-%s' % (NAME, full_version)
    zip_name = '%s-%s.zip' % (top, PLATFORM)
    inputs = [paths['zenobia.exe'], paths['ogre_en.bps'], paths['ogre_en.sha1'], os.path.join(REPO, 'VERSION'),
              os.path.join(REPO, README_TEMPLATE), os.path.join(REPO, LAUNCHER),
              os.path.join(REPO, webpatcher.TEMPLATE)]
    inputs += [os.path.join(REPO, s) for s, _ in TEXT_DOCS]
    inputs += [os.path.join(REPO, p) for p in import_closure(REPO, APPLIER)]
    date_time, date = zip_time(inputs)
    template = read(os.path.join(REPO, README_TEMPLATE)).decode('utf-8')
    readme = fill_template(template, readme_fields(full_version, date, rom, english)).encode('utf-8')
    page = webpatcher.build(patch, english_sha1, full_version)
    entries = stage(top, (exe, patch, sha1_text), readme, page=page)
    check_contents(rep, entries, top)
    check_rom_data(rep, rom, entries)

    final = os.path.join(out_dir, zip_name)
    if rep.problems:
        print('refused: %d problem(s): %s' % (len(rep.problems), ', '.join(c for c, _ in rep.problems)))
        return 1

    os.makedirs(out_dir, exist_ok=True)
    tmp_zip = final + '.tmp'
    try:
        write_zip(tmp_zip, entries, date_time)
        infos = verify_zip(rep, tmp_zip, entries, rom, english_sha1, top)
        new = read(tmp_zip)
        old = read(final) if os.path.isfile(final) else None
        if infos and args.release and old is not None and old != new:
            rep.fail('zip', '%s exists with other contents: a release version is made once; raise VERSION '
                     'or delete the old zip' % rel(final))
        if rep.problems:
            print('refused: %d problem(s): %s' % (len(rep.problems), ', '.join(c for c, _ in rep.problems)))
            return 1
        os.replace(tmp_zip, final)
    finally:
        if os.path.exists(tmp_zip):
            os.remove(tmp_zip)

    print()
    print('%10s %10s  %s' % ('size', 'zipped', 'name'))
    for info in infos:
        print('%10s %10s  %s' % (format(info.file_size, ','), format(info.compress_size, ','), info.filename))
    print('%10s %10s  %d entries, dated %s UTC' % (
        format(sum(i.file_size for i in infos), ','), format(sum(i.compress_size for i in infos), ','),
        len(infos), '%04d-%02d-%02d %02d:%02d:%02d' % date_time))
    state = 'unchanged' if old == new else ('replaced' if old is not None else 'new')
    print('wrote %s (%s bytes, %s; deflate: zlib %s, Python %s)' % (
        rel(final), format(len(new), ','), state, zlib.ZLIB_RUNTIME_VERSION, sys.version.split()[0]))
    print('  SHA-256 %s' % hashlib.sha256(new).hexdigest())
    print('  SHA-1   %s' % sha1(new))
    print('release notes: version %s, %s; English ROM SHA-1 %s' % (full_version, date, english_sha1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
