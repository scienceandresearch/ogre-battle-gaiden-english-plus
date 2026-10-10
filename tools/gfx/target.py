"""Interface between the graphics build (tools/gfx/build.py) and its targets.

A target replaces one pre-drawn Japanese graphic, or a family of them (the
menu labels, the intro narration, the chapter cards, the title). It is a
module tools/gfx/<name>.py with

    from .target import Result

    def build(ctx):                 # ctx: Context, below
        ...                         # read translation/en/<name>.txt, render, encode
        return Result(writes=[(0x218112, data)],        # in place, CPU addresses
                      allow=[(0x218112, 0x219792)],     # where this target may write in place
                      asm=None,                         # or the path of its asm entry
                      previews=[png_path], stats={'labels': 45})

plus an entry in tools/gfx/build.py (TARGETS: name -> sub-region). Rules:

* build(ctx) is deterministic and never changes the ROM itself: in-place
  data goes into Result.writes, which graphics phase 2 commits through
  tools/gfx/romio.RomPatch after every other writer of the patch build.
* New code and data go into assembly: Result.asm names the target's asm
  entry (generated into ctx.work, or hand-written as patch/src/<name>.asm).
  It is included from build/gfx/gfx.asm, so it must start with an .org,
  place its new data inside its sub-region (.org GFX_CARDS etc.; the
  constants are defined before the include) and may use ROM addresses and
  its own labels only (the standalone path assembles it without main.asm).
  Chunks below 0x36746D are hooks into the original program.
* Generated files and previews go to ctx.work (build/gfx/<name>/), never
  into the repository.

Errors: raise TargetError (or let the library's FitError, PaletteError,
BudgetError, MissingGlyphError... propagate); the build names the target.
"""
import os

from ..recomp.rom import ROM_BASE


class GfxError(Exception):
    """Any error of the graphics build that is reported as a message (no traceback)."""


class TargetError(GfxError):
    """A target that cannot be built (bad text, does not fit, bad Result...)."""


class Context:
    """What a target's build(ctx) gets.

    root       repository root
    name       the target's name
    base       the original ROM (bytes; CPU address = ROM_BASE + offset)
    rom        the ROM being built, as it is when the targets run (bytes, a
               read-only snapshot: UI text and locations are in, the rest not)
    work       the target's work folder, build/gfx/<name>/ (created)
    subregion  name of the target's graphics sub-region ('GFX_CARDS'...) or None
    region     (lo, hi) of that sub-region, hi exclusive, or None
    log        log(text): one progress line, prefixed with the target's name
    """

    def __init__(self, root, name, base, rom, work, subregion=None, region=None, log=None):
        self.root = root
        self.name = name
        self.base = base
        self.rom = rom
        self.work = work
        self.subregion = subregion
        self.region = region
        self._log = log or print
        os.makedirs(work, exist_ok=True)

    def log(self, text):
        self._log('  %s: %s' % (self.name, text))

    def path(self, *parts):
        """A path inside the repository."""
        return os.path.join(self.root, *parts)

    def translation(self, filename):
        """translation/en/<filename> (the English text sources)."""
        return os.path.join(self.root, 'translation', 'en', filename)

    def font(self, name):
        """The font assets/font/<name>.txt (tools.gfx.font.load_font, cached)."""
        from .font import load_font
        return load_font(os.path.join(self.root, 'assets', 'font', name + '.txt'))

    def read(self, addr, n):
        """n bytes of the original ROM at CPU address addr."""
        off = addr - ROM_BASE
        if off < 0 or n < 0 or off + n > len(self.base):
            raise TargetError('%s: read %06X+%d is outside the ROM' % (self.name, addr, n))
        return bytes(self.base[off:off + n])

    def write_file(self, filename, data):
        """Write data (str as UTF-8 with '\\n' newlines, or bytes) to ctx.work/filename,
        only if the content changed (atomic replace). Returns the path."""
        path = os.path.join(self.work, filename)
        write_if_changed(path, data)
        return path


class Result:
    """What build(ctx) returns.

    writes    [(addr, bytes)]: in-place writes at CPU addresses (graphics phase 2)
    allow     [(lo, hi)]: ranges (hi exclusive) this target may write in place;
              every write must lie inside one of them. Ranges in the free area
              (0x36746D and up) must lie inside the target's sub-region.
    asm       path of the target's asm entry, or None (relative paths are
              relative to the repository root)
    previews  [paths] of the preview images written for review
    stats     {name: value}, printed in the build report
    """

    def __init__(self, writes=(), allow=(), asm=None, previews=(), stats=None):
        self.writes = list(writes)
        self.allow = list(allow)
        self.asm = asm
        self.previews = list(previews)
        self.stats = dict(stats or {})

    def __repr__(self):
        return '<Result %d writes, %d ranges, asm=%r>' % (len(self.writes), len(self.allow), self.asm)


def write_if_changed(path, data):
    """Write a generated file atomically, leaving it untouched if it already
    holds the same bytes (so parallel builds that generate the same file never
    see a half-written one). Returns True if the file was written."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    data = bytes(data)
    try:
        with open(path, 'rb') as f:
            if f.read() == data:
                return False
    except OSError:
        pass
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = '%s.%d.tmp' % (path, os.getpid())
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)
    return True
