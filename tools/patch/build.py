"""Build the English ROM from the user's original ROM.

Usage: python -m tools.patch.build rom/baserom.ngc [-o build/ogre_en.ngc] [--no-gfx]

Steps: verify the base ROM, compile the font, build the UI text and the
location names, then graphics phase 1 (tools/gfx/build.py: run the graphics
targets, write build/gfx/gfx.asm, which main.asm includes), assemble
patch/main.asm, apply every assembled chunk (new code/data must land in a
patch region, a graphics target's chunks in its sub-region; chunks inside
the original program are hooks and are listed in the report), then apply
text insertions, then graphics phase 2 (the targets' in-place writes, last;
refused where another writer changed a byte). Then the layout check: nothing
may change in the game's save blocks (0x3B0000-0x3EFFFF) or outside the
regions listed in tools/patch/layout.py. Last, the distribution patch:
build/ogre_en.bps (BPS, audited to carry no ROM data, see tools/patch/bps.py)
and build/ogre_en.sha1 (SHA-1 of the English ROM), named after the output ROM.

--no-gfx leaves the replacement graphics out (no target runs; gfx.asm then
holds only the region constants), for comparisons.
"""
import argparse
import hashlib
import os

from ..recomp.rom import EXPECTED_SHA1, ROM_BASE
from ..asm.tlcs900asm import Assembler, AsmError
from ..text import fontc
from . import layout
from .layout import FREE_START, LayoutError

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
UI_TEXT_START, UI_TEXT_END = layout.region('ui')    # remapped menu/window strings, then locations
TEXT_START, TEXT_END = layout.region('dialogue')    # relocated English dialogue
TABLES_START, TABLES_END = layout.region('tables')  # rebuilt name/description tables


def spread_table():
    """256 words: 1bpp byte (bit 7 = leftmost) -> 2bpp mask with 11 per set pixel."""
    out = bytearray()
    for b in range(256):
        m = 0
        for p in range(8):
            if b & (0x80 >> p):
                m |= 3 << (14 - 2 * p)
        out += bytes((m & 0xFF, m >> 8))
    return bytes(out)


def build_font():
    out = os.path.join(ROOT, 'build', 'font')
    fontc.build(os.path.join(ROOT, 'assets', 'font', 'vwf8.txt'), out)
    with open(os.path.join(out, 'spread.bin'), 'wb') as f:
        f.write(spread_table())


def check_no_japanese():
    """The repository must stay free of ROM text: refuse Japanese characters
    (CJK punctuation, kana, kanji, full-width forms) anywhere in the
    translation files and the assets' text sources (comments included)."""
    import re
    jp = re.compile('[\u3000-\u30ff\u4e00-\u9fff\uff01-\uff9f]')
    for folder in (os.path.join(ROOT, 'translation', 'en'), os.path.join(ROOT, 'assets')):
        for dirpath, _, files in os.walk(folder):
            for name in files:
                if not name.endswith('.txt'):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding='utf-8') as f:
                    for n, line in enumerate(f, 1):
                        if jp.search(line):
                            raise SystemExit('%s:%d: Japanese text in a source file (keep ROM text '
                                             'out of the repository)' % (os.path.relpath(path, ROOT), n))


def apply_chunks(base, rom, chunks):
    hooks = []
    used = []
    for org, data in chunks:
        if not data:
            continue
        end = org + len(data)
        if org < ROM_BASE or end > ROM_BASE + len(rom):
            raise SystemExit('chunk %06X-%06X outside the ROM' % (org, end))
        for (a, b) in used:
            if org < b and a < end:
                raise SystemExit('chunk %06X-%06X overlaps %06X-%06X' % (org, end, a, b))
        used.append((org, end))
        off = org - ROM_BASE
        if org >= FREE_START:
            try:
                layout.check_chunk(org, end)
            except LayoutError as e:
                raise SystemExit(str(e))
            if any(x != 0xFF for x in base[off:off + len(data)]):
                raise SystemExit('chunk %06X-%06X is not in free space' % (org, end))
        else:
            hooks.append((org, base[off:off + len(data)], data))
        rom[off:off + len(data)] = data
    return hooks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('-o', '--out', default=os.path.join(ROOT, 'build', 'ogre_en.ngc'))
    ap.add_argument('--inplace', default=None, help='test file of in-place text replacements')
    ap.add_argument('--no-gfx', action='store_true',
                    help='leave the replacement graphics out (tools/gfx targets), e.g. for comparisons')
    args = ap.parse_args()

    base = open(args.rom, 'rb').read()
    sha1 = hashlib.sha1(base).hexdigest()
    if sha1 != EXPECTED_SHA1:
        raise SystemExit('unexpected ROM (sha1 %s); expected %s' % (sha1, EXPECTED_SHA1))
    rom = bytearray(base)

    check_no_japanese()
    build_font()

    # UI strings first: the remap table they produce is included by main.asm
    from ..text.uitext import build_ui, UiError
    ui_txt = os.path.join(ROOT, 'translation', 'en', 'ui.txt')
    try:
        ui_stats = build_ui(base, rom, ui_txt, UI_TEXT_START, UI_TEXT_END,
                            os.path.join(ROOT, 'build', 'ui', 'remap.bin'))
    except UiError as e:
        raise SystemExit('UI text: %s' % e)

    # Location names go after the UI strings; their symbols are included too
    from ..text.locations import build_locations, LocationError
    try:
        loc_stats = build_locations(base, rom, os.path.join(ROOT, 'translation', 'en', 'locations.txt'),
                                    ui_stats['end'], UI_TEXT_END,
                                    os.path.join(ROOT, 'build', 'loc', 'symbols.asm'))
    except LocationError as e:
        raise SystemExit('locations: %s' % e)

    # Graphics phase 1 (tools/gfx/build.py): run the targets, queue their
    # in-place writes, write build/gfx/gfx.asm (included at the end of main.asm)
    from ..gfx import build as gfx_build
    try:
        gfx = gfx_build.prepare(ROOT, base, rom, targets=() if args.no_gfx else None)
    except gfx_build.GfxError as e:
        raise SystemExit('graphics: %s' % e)

    asm = Assembler()
    asm.load(os.path.join(ROOT, 'patch', 'main.asm'))
    try:
        chunks = asm.assemble()
    except AsmError as e:
        raise SystemExit(str(e))
    try:        # a target's chunks lie in its sub-region or are hooks; nothing else uses the region
        gfx_chunks = gfx.check_chunks(chunks, asm.lines)
    except gfx_build.GfxError as e:
        raise SystemExit('graphics: %s' % e)
    hooks = apply_chunks(base, rom, chunks)
    code_bytes = sum(len(d) for o, d in chunks if o >= FREE_START)
    print('assembled %d chunks, %d bytes of new code/data' % (len(chunks), code_bytes))
    for org, old, new in hooks:
        print('  hook %06X: %s -> %s' % (org, old.hex(' '), new.hex(' ')))
    print('UI text: %d remapped (%d bytes), %d in place' % (
        ui_stats['remap'], ui_stats['bytes'], ui_stats['inplace']))
    print('locations: %d names (%d bytes)' % (loc_stats['names'], loc_stats['bytes']))
    print('\n'.join(['graphics: left out (--no-gfx)'] if args.no_gfx else gfx.report() + gfx_chunks))

    script = os.path.join(ROOT, 'translation', 'en', 'script.txt')
    if os.path.exists(script):
        from ..text.insert import read_translations, insert_dialogue, Allocator, InsertError
        tr = read_translations(script)
        alloc = Allocator(TEXT_START, TEXT_END)
        try:
            st = insert_dialogue(base, rom, tr, alloc)
        except InsertError as e:
            raise SystemExit('text insertion failed: %s' % e)
        print('dialogue: %d messages, %d pages, %d bytes' % (st['messages'], st['pages'], st['bytes']))

    from ..text.tables import build_tables, TableError
    try:
        used, ntab, nent = build_tables(base, rom, os.path.join(ROOT, 'translation', 'en', 'tables'),
                                        TABLES_START, TABLES_END)
    except TableError as e:
        raise SystemExit('tables: %s' % e)
    print('tables: %d rebuilt, %d entries translated, %d bytes' % (ntab, nent, used))

    if args.inplace:
        from .inplace import apply_inplace
        n = apply_inplace(rom, args.inplace)
        print('in-place text replacements: %d' % n)

    # Graphics phase 2: the targets' in-place writes, after every other writer
    # (refused where another writer changed a byte)
    try:
        gfx_lines = gfx.apply_inplace()
    except gfx_build.GfxError as e:
        raise SystemExit('graphics: %s' % e)
    if gfx_lines:
        print('\n'.join(gfx_lines))

    # Nothing in the game's save blocks, nothing outside the patch regions
    try:
        usage = layout.check(base, rom)
    except LayoutError as e:
        raise SystemExit('layout check failed: %s' % e)
    print('layout:')
    print('\n'.join(layout.report(usage)))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'wb') as f:
        f.write(rom)
    with open(os.path.join(os.path.dirname(args.out), 'symbols.txt'), 'w') as f:
        for k, v in sorted(asm.symbols.items(), key=lambda kv: kv[1]):
            if v >= ROM_BASE:
                f.write('%06X %s\n' % (v, k))
    print('wrote', args.out)

    write_distribution_patch(base, bytes(rom), args.out)


def write_distribution_patch(base, rom, rom_path):
    """Write the BPS patch original -> English ROM and the English ROM's SHA-1
    next to the ROM (ogre_en.ngc -> ogre_en.bps, ogre_en.sha1). The patch is
    checked by applying it and audited: no literal may hold 8 or more bytes
    that occur in the original ROM. (The layout check before it guarantees
    that the patch leaves the game's save blocks alone.)"""
    from . import bps
    stem = os.path.splitext(rom_path)[0]
    bps_path, sha1_path = stem + '.bps', stem + '.sha1'
    for path in (bps_path, sha1_path):      # never leave a patch for an older ROM behind
        if os.path.exists(path):
            os.remove(path)
    try:
        patch, report = bps.create(base, rom)
    except bps.AuditError as e:
        for off, n, src in e.report.offenders[:10]:
            print('  literal at 0x%06X: %d bytes also at original 0x%06X' % (off + ROM_BASE, n, src + ROM_BASE))
        raise SystemExit('BPS patch audit failed (the patch would carry ROM data): %s' % e)
    except bps.BpsError as e:
        raise SystemExit('BPS patch: %s' % e)
    with open(bps_path, 'wb') as f:
        f.write(patch)
    sha1 = hashlib.sha1(rom).hexdigest()
    with open(sha1_path, 'w', newline='\n') as f:
        f.write(sha1 + '\n')
    print('patch: %s, %s bytes' % (bps_path, format(len(patch), ',')))
    print('patch audit: %s' % report.summary())
    print('patched ROM SHA-1: %s (%s)' % (sha1, sha1_path))


if __name__ == '__main__':
    main()
