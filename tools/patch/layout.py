"""ROM layout of the English patch, and the check that a built ROM keeps to it.

The original ROM is 0xFF-filled from 0x36746D to the end (0x3FFFFF). The game
saves into cartridge flash blocks 0x1B-0x1E, 0x3B0000-0x3EFFFF (suspend data,
then save files 1, 2 and 3; slot table at 0x29A66E). It appends records to a
block and erases the whole block when it is full, so nothing of the patch may
ever live there: on hardware, on flash carts and in any emulator that emulates
the flash chip, saving would overwrite it.

    python -m tools.patch.layout ROM [BASE]    report a built ROM's usage

Regions:
"""
import sys

from ..recomp.rom import ROM_BASE

FREE_START = 0x36746D       # first byte of the original's 0xFF fill
SAVE_START = 0x3B0000       # the game's save blocks: never written
SAVE_END = 0x3F0000

# name, start, end (exclusive), content. patch/main.asm places code at 0x370000 (FREE_CODE)
# and data at 0x378000 (FREE_DATA); tools/patch/build.py allocates the rest.
REGIONS = (
    ('ui', 0x368000, 0x370000, 'remapped UI strings, location names'),
    ('code', 0x370000, 0x378000, 'patch code (patch/main.asm)'),
    ('data', 0x378000, 0x380000, 'fonts, UI remap table'),
    ('dialogue', 0x380000, 0x3A0000, 'English dialogue pages'),
    ('gfx', 0x3A0000, 0x3B0000, 'replacement graphics (tools/gfx)'),
    ('tables', 0x3F0000, 0x400000, 'rebuilt name/description tables'),
)

__doc__ += ''.join('    %06X-%06X  %-9s %s\n' % (s, e - 1, n, c) for n, s, e, c in REGIONS)


class LayoutError(Exception):
    pass


def region(name):
    """(start, end) of a region by name."""
    for n, s, e, _ in REGIONS:
        if n == name:
            return s, e
    raise KeyError(name)


def check_chunk(org, end):
    """Refuse a new-data chunk [org, end) that touches the save blocks or lies
    outside every region (code below FREE_START is a hook, not checked here)."""
    if org < SAVE_END and SAVE_START < end:
        raise LayoutError('chunk %06X-%06X is inside the game\'s save blocks (%06X-%06X)'
                          % (org, end, SAVE_START, SAVE_END))
    if not any(s <= org and end <= e for _, s, e, _ in REGIONS):
        raise LayoutError('chunk %06X-%06X is not inside one patch region' % (org, end))


def _first_diff(a, b, lo, hi):
    """First offset in [lo, hi) where a and b differ, or None."""
    if a[lo:hi] == b[lo:hi]:
        return None
    step = 4096
    for x in range(lo, hi, step):
        y = min(hi, x + step)
        if a[x:y] != b[x:y]:
            for i in range(x, y):
                if a[i] != b[i]:
                    return i
    return None


def check(base, rom):
    """Check the finished ROM against the original: every changed byte at or
    above FREE_START must lie in a region, none in the save blocks. Returns
    [(name, start, end, used, changed)] where used is the extent from the
    region start to the last byte that differs from the original."""
    if len(base) != len(rom):
        raise LayoutError('ROM size changed (%d -> %d bytes)' % (len(base), len(rom)))
    top = ROM_BASE + len(rom)
    # gaps between the regions, the save blocks included
    covered = sorted((s, e) for _, s, e, _ in REGIONS)
    gaps, pos = [], FREE_START
    for s, e in covered:
        if pos < s:
            gaps.append((pos, s))
        pos = max(pos, e)
    if pos < top:
        gaps.append((pos, top))
    for lo, hi in gaps:
        d = _first_diff(base, rom, lo - ROM_BASE, hi - ROM_BASE)
        if d is not None:
            where = ('the game\'s save blocks' if SAVE_START <= d + ROM_BASE < SAVE_END
                     else 'no patch region')
            raise LayoutError('byte %06X changed, in %s (%06X-%06X)' % (d + ROM_BASE, where, lo, hi))
    usage = []
    for name, s, e, _ in REGIONS:
        lo, hi = s - ROM_BASE, min(e, top) - ROM_BASE
        last, changed = None, 0
        for i in range(lo, hi):
            if base[i] != rom[i]:
                changed += 1
                last = i
        used = 0 if last is None else last + 1 - lo
        usage.append((name, s, e, used, changed))
    return usage


def report(usage):
    """Lines describing each region's use."""
    out = []
    for name, s, e, used, changed in usage:
        out.append('  %-9s %06X-%06X  %6.1f of %3d KB used (%d bytes changed)'
                   % (name, s, e - 1, used / 1024, (e - s) // 1024, changed))
    out.append('  save blocks %06X-%06X untouched' % (SAVE_START, SAVE_END - 1))
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    rom = open(sys.argv[1], 'rb').read()
    base = open(sys.argv[2] if len(sys.argv) > 2 else 'rom/baserom.ngc', 'rb').read()
    try:
        usage = check(base, rom)
    except LayoutError as e:
        raise SystemExit('layout: %s' % e)
    print('\n'.join(report(usage)))


if __name__ == '__main__':
    main()
