"""In-place ROM writes with owners and range checks: RomPatch.

    patch = RomPatch(base, rom)         # base: the original ROM; rom: the bytearray being built
    patch.allow(lo, hi, owner)          # owner may write in [lo, hi) (CPU addresses, hi exclusive)
    patch.write(addr, data, owner)      # queued, not written yet
    lines = patch.commit()              # checks, then writes every queued write
    patch.log                           # the report lines of commit()

Refused (PatchError):
* allow: a range outside the ROM, empty, inside the game's save blocks
  (0x3B0000-0x3EFFFF), or overlapping a range of another owner;
* write: bytes outside the owner's ranges (adjacent ranges of one owner
  count as one), or overlapping any other queued write (of any owner);
* commit: a queued range where rom no longer equals base, i.e. bytes that
  another writer changed (a hook, in-place text...). Nothing is written then.

The graphics build queues the targets' writes in phase 1 (before
patch/main.asm is assembled) and commits them in phase 2, after every other
writer, so a clash with any other part of the patch is a build error, never
silent corruption.
"""
import bisect

from ..recomp.rom import ROM_BASE
from ..patch.layout import SAVE_START, SAVE_END
from .target import GfxError


class PatchError(GfxError):
    """A refused in-place write."""


def merge_ranges(ranges):
    """Sorted list of (lo, hi) with overlapping or adjacent ranges merged."""
    out = []
    for lo, hi in sorted(ranges):
        if out and lo <= out[-1][1]:
            if hi > out[-1][1]:
                out[-1] = (out[-1][0], hi)
        else:
            out.append((lo, hi))
    return out


def format_ranges(ranges, limit=6):
    """'218112-219791, 21A000-21A00F' (inclusive ends), shortened after limit ranges."""
    parts = ['%06X-%06X' % (lo, hi - 1) for lo, hi in ranges[:limit]]
    if len(ranges) > limit:
        parts.append('... (%d ranges)' % len(ranges))
    return ', '.join(parts)


class RomPatch:
    def __init__(self, base, rom):
        if not isinstance(rom, bytearray):
            raise TypeError('RomPatch needs the ROM being built as a bytearray')
        if len(base) != len(rom):
            raise PatchError('ROM size %d differs from the original (%d)' % (len(rom), len(base)))
        self.base = base
        self.rom = rom
        self.top = ROM_BASE + len(base)
        self.ranges = {}            # owner -> merged [(lo, hi)]
        self.owners = []            # owners in the order they first appeared
        self.writes = []            # (addr, end, data, owner), sorted by addr
        self._starts = []           # addr of each queued write, for bisect
        self.committed = False
        self.log = []

    def register(self, owner):
        """Make owner known (listed in the report even with no write)."""
        if owner not in self.ranges:
            self.ranges[owner] = []
            self.owners.append(owner)

    def allow(self, lo, hi, owner):
        """Let owner write in [lo, hi)."""
        self._check_open()
        if not (isinstance(lo, int) and isinstance(hi, int)) or hi <= lo:
            raise PatchError('%s: bad range %r-%r' % (owner, lo, hi))
        if lo < ROM_BASE or hi > self.top:
            raise PatchError('%s: range %06X-%06X is outside the ROM' % (owner, lo, hi - 1))
        if lo < SAVE_END and SAVE_START < hi:
            raise PatchError('%s: range %06X-%06X touches the game\'s save blocks (%06X-%06X)'
                             % (owner, lo, hi - 1, SAVE_START, SAVE_END - 1))
        for other, ranges in self.ranges.items():
            if other == owner:
                continue
            for a, b in ranges:
                if lo < b and a < hi:
                    raise PatchError('%s: range %06X-%06X overlaps %06X-%06X of %s'
                                     % (owner, lo, hi - 1, a, b - 1, other))
        self.register(owner)
        self.ranges[owner] = merge_ranges(self.ranges[owner] + [(lo, hi)])

    def write(self, addr, data, owner):
        """Queue data for addr. Empty data is ignored."""
        self._check_open()
        if not isinstance(addr, int):
            raise PatchError('%s: bad address %r' % (owner, addr))
        data = bytes(data)
        if not data:
            return
        end = addr + len(data)
        if not any(lo <= addr and end <= hi for lo, hi in self.ranges.get(owner, ())):
            raise PatchError('%s: write %06X-%06X (%d bytes) is outside its ranges (%s)'
                             % (owner, addr, end - 1, len(data),
                                format_ranges(self.ranges.get(owner, [])) or 'none declared'))
        i = bisect.bisect_left(self._starts, addr)
        for j in (i - 1, i):
            if 0 <= j < len(self.writes):
                a, b, _, other = self.writes[j]
                if addr < b and a < end:
                    raise PatchError('%s: write %06X-%06X overlaps the write %06X-%06X of %s'
                                     % (owner, addr, end - 1, a, b - 1, other))
        self.writes.insert(i, (addr, end, data, owner))
        self._starts.insert(i, addr)

    def _check_open(self):
        if self.committed:
            raise PatchError('the in-place writes were committed already')

    def changed_by_others(self):
        """[(owner, addr, end, first differing address)] for queued writes whose
        bytes in rom no longer equal the original."""
        bad = []
        for addr, end, data, owner in self.writes:
            lo, hi = addr - ROM_BASE, end - ROM_BASE
            if self.rom[lo:hi] != self.base[lo:hi]:
                first = next(i for i in range(lo, hi) if self.rom[i] != self.base[i])
                bad.append((owner, addr, end, first + ROM_BASE))
        return bad

    def commit(self):
        """Check that no other writer changed a queued range, then write
        everything. Returns (and keeps in .log) the report lines."""
        self._check_open()
        bad = self.changed_by_others()
        if bad:
            lines = ['%s: %06X-%06X, first at %06X (original %02X, now %02X)'
                     % (owner, addr, end - 1, first, self.base[first - ROM_BASE], self.rom[first - ROM_BASE])
                     for owner, addr, end, first in bad[:8]]
            raise PatchError('in-place graphics overlap bytes that another part of the patch changed:\n  '
                             + '\n  '.join(lines) + ('\n  ... (%d ranges)' % len(bad) if len(bad) > 8 else ''))
        for addr, end, data, owner in self.writes:
            self.rom[addr - ROM_BASE:end - ROM_BASE] = data
        self.committed = True
        self.log = self.report()
        return self.log

    def stats(self):
        """{owner: (writes, bytes, changed bytes, merged written ranges)}."""
        out = {}
        for owner in self.owners:
            ws = [(a, b, d) for a, b, d, o in self.writes if o == owner]
            changed = sum(1 for a, b, d in ws for i, v in enumerate(d) if self.base[a - ROM_BASE + i] != v)
            out[owner] = (len(ws), sum(b - a for a, b, _ in ws), changed, merge_ranges((a, b) for a, b, _ in ws))
        return out

    def report(self):
        lines = []
        for owner, (n, total, changed, ranges) in self.stats().items():
            if not n:
                lines.append('  %s: no in-place writes' % owner)
                continue
            lines.append('  %s: %s bytes in %d write%s (%s bytes differ from the original): %s'
                         % (owner, format(total, ','), n, '' if n == 1 else 's', format(changed, ','),
                            format_ranges(ranges)))
        return lines
