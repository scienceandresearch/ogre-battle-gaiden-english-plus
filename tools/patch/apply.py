"""Apply the English translation patch to your own copy of the game.

Usage: python -m tools.patch.apply ORIGINAL [PATCH.bps] [-o OUT.ngc]

ORIGINAL  the Japanese ROM "Densetsu no Ogre Battle Gaiden - Zenobia no Ouji
          (Japan)": 2,097,152 bytes, SHA-1 5ac794c0f125bfb97efe9cd06c2aca3afdf549ea.
          The file name and extension (.ngc, .ngp) do not matter; a .zip that
          contains the ROM works too.
PATCH     the BPS patch. Default: build/ogre_en.bps of this repository, else
          ogre_en.bps in the repository root, next to ORIGINAL or in the
          current folder.
-o OUT    where to write the English ROM. Default: ogre_en.ngc next to
          ORIGINAL (a .zip's folder for a zipped ROM).

Checks: the original's SHA-1 before patching, the patch's own checksums,
then the result's CRC32 (stored in the patch) and SHA-1 (from the file next
to the patch with the same name and the extension .sha1, when there is one).
"""
import argparse
import hashlib
import os
import sys
import zipfile
import zlib

from . import bps
from ..recomp.rom import EXPECTED_SHA1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ROM_NAME = 'Densetsu no Ogre Battle Gaiden - Zenobia no Ouji (Japan)'
ROM_SIZE = 2 * 1024 * 1024
PATCH_NAME = 'ogre_en.bps'
OUT_NAME = 'ogre_en.ngc'
# File offsets of space that is blank (0xFF) in the original and filled by the
# patch: used only to tell a user that a ROM looks patched already.
PATCH_AREA = (0x170000, 0x170100)
MAX_MEMBER = 64 << 20                   # ignore bigger files inside a .zip


class ApplyError(Exception):
    pass


def default_patch(original):
    """The first existing ogre_en.bps among the usual places."""
    places = [os.path.join(ROOT, 'build', PATCH_NAME), os.path.join(ROOT, PATCH_NAME),
              os.path.join(os.path.dirname(os.path.abspath(original)), PATCH_NAME),
              os.path.join(os.getcwd(), PATCH_NAME)]
    for p in places:
        if os.path.isfile(p):
            return p
    raise ApplyError('no patch given and no %s found (looked in: %s)' % (PATCH_NAME, ', '.join(places)))


def default_out(original):
    return os.path.join(os.path.dirname(os.path.abspath(original)), OUT_NAME)


def read_sha1_file(patch_path):
    """The SHA-1 in PATCH.sha1 (first word, hex), or None if there is none."""
    path = os.path.splitext(patch_path)[0] + '.sha1'
    if not os.path.isfile(path):
        return None, path
    with open(path, encoding='ascii', errors='replace') as f:
        words = f.read().split()
    sha1 = words[0].lower() if words else ''
    if len(sha1) != 40 or any(ch not in '0123456789abcdef' for ch in sha1):
        raise ApplyError('%s does not contain a SHA-1 (40 hex digits)' % path)
    return sha1, path


def read_rom(path):
    """(ROM bytes, display name) from a file, or from the right member of a .zip."""
    try:
        if zipfile.is_zipfile(path):
            return _rom_from_zip(path)
        with open(path, 'rb') as f:
            return f.read(), path
    except OSError as e:
        raise ApplyError('cannot read %s: %s' % (path, e.strerror or e))
    except zipfile.BadZipFile as e:
        raise ApplyError('cannot read the .zip archive %s: %s' % (path, e))
    except (RuntimeError, NotImplementedError) as e:     # encrypted, unsupported compression
        raise ApplyError('cannot extract the ROM from %s (%s); extract it with another tool first'
                         % (path, e))


def _rom_from_zip(path):
    with zipfile.ZipFile(path) as z:
        members = [i for i in z.infolist() if not i.is_dir() and i.file_size <= MAX_MEMBER]
        fallback = None
        for info in members:
            data = z.read(info)
            name = '%s (inside %s)' % (info.filename, path)
            if hashlib.sha1(data).hexdigest() == EXPECTED_SHA1:
                return data, name
            ext = os.path.splitext(info.filename)[1].lower()
            if fallback is None and (ext in ('.ngc', '.ngp', '.npc') or info.file_size == ROM_SIZE):
                fallback = (data, name)
        if fallback is not None:
            return fallback             # not the right ROM; the caller explains why
    raise ApplyError('%s is a .zip archive without a Neo Geo Pocket ROM in it' % path)


def explain_wrong_rom(rom, name, sha1, patch, out_sha1):
    crc = zlib.crc32(rom)
    if sha1 == out_sha1 or (len(rom) == patch.target_size and crc == patch.target_crc):
        return ('%s is already patched: it is the English ROM that this patch makes. '
                'Apply the patch to the original Japanese ROM instead.' % name)
    lines = ['%s is not the ROM this patch is for.' % name,
             '  this file: %s bytes, SHA-1 %s' % (format(len(rom), ','), sha1),
             '  needed:    %s bytes, SHA-1 %s' % (format(ROM_SIZE, ','), EXPECTED_SHA1),
             '             (%s)' % ROM_NAME]
    if len(rom) != ROM_SIZE:
        lines.append('The size is wrong: check that this is the right game and a complete, unmodified dump.')
    elif rom[PATCH_AREA[0]:PATCH_AREA[1]] != b'\xff' * (PATCH_AREA[1] - PATCH_AREA[0]):
        lines.append('It looks like a ROM that has been patched already (perhaps with another version '
                     'of this patch). Start again from the original ROM.')
    else:
        lines.append('It may be another dump, another revision or a modified ROM; only the dump above '
                     'is supported.')
    return '\n'.join(lines)


def apply_patch(original, patch_path, out_path, log=print):
    """Check, patch and write. Returns the SHA-1 of the written ROM."""
    try:
        with open(patch_path, 'rb') as f:
            patch_data = f.read()
    except OSError as e:
        raise ApplyError('cannot read the patch %s: %s' % (patch_path, e.strerror or e))
    try:
        patch = bps.parse(patch_data)
    except bps.PatchFormatError as e:
        raise ApplyError('the patch %s cannot be used (%s). Download it again.' % (patch_path, e))
    out_sha1, sha1_path = read_sha1_file(patch_path)

    rom, name = read_rom(original)
    sha1 = hashlib.sha1(rom).hexdigest()
    if sha1 != EXPECTED_SHA1:
        raise ApplyError(explain_wrong_rom(rom, name, sha1, patch, out_sha1))
    if len(rom) != patch.source_size or zlib.crc32(rom) != patch.source_crc:
        raise ApplyError('the patch %s was not made for this ROM (it expects %s bytes with CRC32 %08X); '
                         'get the patch of this project again' % (patch_path, format(patch.source_size, ','),
                                                                   patch.source_crc))
    try:
        out = bps.apply(rom, patch)
    except bps.BpsError as e:
        raise ApplyError('patching failed: %s. The patch file is probably damaged; download it again.' % e)
    result_sha1 = hashlib.sha1(out).hexdigest()
    if out_sha1 is not None and result_sha1 != out_sha1:
        raise ApplyError('the patched ROM has SHA-1 %s, but %s says %s: the patch and that file do not '
                         'belong together' % (result_sha1, sha1_path, out_sha1))

    if os.path.exists(out_path) and os.path.isfile(original) and os.path.samefile(out_path, original):
        raise ApplyError('refusing to overwrite the original ROM %s; choose another output with -o' % original)
    try:
        with open(out_path, 'wb') as f:
            f.write(out)
    except OSError as e:
        raise ApplyError('cannot write %s: %s' % (out_path, e.strerror or e))
    log('original: %s (SHA-1 OK)' % name)
    log('patch:    %s' % patch_path)
    log('wrote:    %s (%s bytes, CRC32 %08X, SHA-1 %s%s)' % (
        out_path, format(len(out), ','), zlib.crc32(out), result_sha1,
        ', matches %s' % os.path.basename(sha1_path) if out_sha1 else ''))
    return result_sha1


def _is_bps(path):
    try:
        with open(path, 'rb') as f:
            return f.read(4) == bps.MAGIC
    except OSError:
        return False


def main(argv=None, prog='python -m tools.patch.apply'):
    ap = argparse.ArgumentParser(prog=prog,
                                 description='Apply the English patch to the original ROM.')
    ap.add_argument('original', help='the original Japanese ROM (.ngc/.ngp, or a .zip containing it)')
    ap.add_argument('patch', nargs='?', help='the BPS patch (default: %s, see the module help)' % PATCH_NAME)
    ap.add_argument('-o', '--out', help='output ROM (default: %s next to the original)' % OUT_NAME)
    args = ap.parse_args(argv)
    original, patch_path = args.original, args.patch
    if patch_path and _is_bps(original) and not _is_bps(patch_path):
        original, patch_path = patch_path, original     # Flips order: patch first
        print('note: the first file is the patch; using %s as the ROM' % original)
    try:
        if not os.path.isfile(original):
            raise ApplyError('%s does not exist' % original)
        if not patch_path and _is_bps(original):
            raise ApplyError('%s is the patch; give the original ROM first: %s '
                             'ORIGINAL [PATCH.bps] [-o OUT.ngc]' % (original, prog))
        patch_path = patch_path or default_patch(original)
        apply_patch(original, patch_path, args.out or default_out(original))
    except ApplyError as e:
        print('error: %s' % e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
