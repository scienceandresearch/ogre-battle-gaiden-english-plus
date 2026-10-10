"""Graphics build: the target registry and the graphics phases of the patch build.

Targets (TARGETS below): one module tools/gfx/<name>.py each, with
build(ctx) -> Result (tools/gfx/target.py), and the sub-region that its new
data may use (None: in place only).

The graphics region (region 'gfx' of tools/patch/layout.py, 0x3A0000-0x3AFFFF)
is cut into fixed sub-regions, so that parallel tasks stay independent and the
standalone test ROMs (tools/gfx/apply.py) use the addresses of the full build:

    GFX_CARDS  3A0000-3A5FFF  24 KB  card routines, tables, records, tiles
    GFX_INTRO  3A6000-3A9FFF  16 KB  relocated intro: line table, map, extra lines
    GFX_TITLE  3AA000-3ADFFF  16 KB  fallback title package
    GFX_SPARE  3AE000-3AFFFF   8 KB  targets found by the survey

How tools/patch/build.py uses this module:

1. gfx = prepare(ROOT, base, rom), after the UI text and the locations, before
   patch/main.asm is assembled (graphics phase 1). It runs each target's
   build(ctx), queues the in-place writes in a RomPatch (each must lie in
   the ranges its target declared) and writes build/gfx/gfx.asm, which
   main.asm includes: GFX_START/GFX_END and the sub-region constants (NAME
   and NAME_END), then an include of each target's asm entry. A registered
   target whose module file does not exist yet is skipped with a note;
   errors inside an existing module are not hidden.
2. gfx.check_chunks(chunks, asm.lines) after assembling, before the chunks
   are applied: the assembly holds gfx.asm as phase 1 wrote it, once, and
   every target's asm entry (a missing include, or a gfx.asm rewritten by
   another build in the meantime, would otherwise drop a target's chunks
   silently); every chunk that a target's asm produces lies in the
   target's sub-region or is a hook (below 0x36746D) on bytes that no earlier
   writer changed; no other chunk uses the graphics region; a target's asm
   starts with an .org; no symbol of a target is defined twice. (Overlaps
   with other chunks: apply_chunks.)
3. gfx.apply_inplace() after the dialogue, the tables and --inplace (graphics
   phase 2): checks that no later writer overwrote a target's chunk, then
   commits the in-place writes, and refuses any range where another writer
   changed a byte.

--no-gfx is prepare(..., targets=()): no target runs and gfx.asm holds only
the constants. A module may set FULL_BUILD = False to stay out of the default
selection (the full build, and tools.gfx.apply without --target) while
`python -m tools.gfx.apply IN OUT --target NAME` still runs it.

    python -m tools.gfx.build        list the registry, sub-regions and modules present
"""
import importlib
import os
import re
import sys

from ..patch import layout
from ..patch.layout import FREE_START
from ..recomp.rom import ROM_BASE
from .romio import RomPatch, format_ranges, merge_ranges
from .target import Context, GfxError, Result, TargetError, write_if_changed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = __package__ or 'tools.gfx'           # also right when run with python -m

GFX_START, GFX_END = layout.region('gfx')

# Sub-regions of the graphics region: name -> (start, end exclusive). They
# tile the region in this order; gfx.asm defines NAME and NAME_END for each.
SUBREGIONS = {
    'GFX_CARDS': (0x3A0000, 0x3A6000),
    'GFX_INTRO': (0x3A6000, 0x3AA000),
    'GFX_TITLE': (0x3AA000, 0x3AE000),
    'GFX_SPARE': (0x3AE000, 0x3B0000),
}
SUBREGION_USE = {
    'GFX_CARDS': 'card routines, tables, records, tiles',
    'GFX_INTRO': 'relocated intro: line table, map, extra lines',
    'GFX_TITLE': 'fallback title package',
    'GFX_SPARE': 'targets found by the survey',
}

# The registry, in build order: target name -> sub-region of its new data
# (None: in place only). Adding a target: one line here, a module
# tools/gfx/<name>.py with build(ctx), and its test tools/gfx/test_<name>.py.
TARGETS = {
    'labels': None,             # 45 menu labels, in place at 0x218112
    'intro': 'GFX_INTRO',       # narration lines in place; table/map/extra lines if relocated
    'cards': 'GFX_CARDS',       # chapter title cards: routines, records, tiles, 2 hooks
    'title': 'GFX_TITLE',       # title logo and warning window in place; fallback package
    'tags': None,               # "deployed" tag (0x214A00, 0x2E736A) and paralysis label (0x2FE5ED), in place
}

# Module names in tools/gfx that are not targets.
RESERVED = frozenset(('build', 'target', 'romio', 'apply', 'vram', 'harness', 'font', 'textart', 'image',
                      'tiles', 'inventory', 'codec'))


class ChunkError(GfxError):
    """An assembled chunk that breaks the graphics layout rules."""


def _check_tables():
    pos = GFX_START
    for name, (lo, hi) in SUBREGIONS.items():
        if lo != pos or hi <= lo:
            raise AssertionError('sub-region %s %06X-%06X does not follow %06X' % (name, lo, hi, pos))
        pos = hi
    if pos != GFX_END:
        raise AssertionError('the sub-regions end at %06X, the graphics region at %06X' % (pos, GFX_END))
    for name, sub in TARGETS.items():
        if sub is not None and sub not in SUBREGIONS:
            raise AssertionError('target %s: unknown sub-region %s' % (name, sub))
        if name in RESERVED or name.startswith('test_') or not name.isidentifier():
            raise AssertionError('bad target name %r' % name)


_check_tables()


def rel(path, root=ROOT):
    """A path for messages: relative to the repository when it is inside it."""
    try:
        r = os.path.relpath(path, root)
    except ValueError:
        return path
    return path if r.startswith('..') else r.replace(os.sep, '/')


def _key(path):
    return os.path.normcase(os.path.abspath(path))


# ---------------------------------------------------------------------------
# Registry

class Target:
    """A target: name, sub-region name (or None), build(ctx) -> Result.

    The registry makes one per module tools/gfx/<name>.py; tests may make
    their own (Target('dummy', build_function, 'GFX_SPARE'))."""

    def __init__(self, name, build, subregion=None, module=None):
        if subregion is not None and subregion not in SUBREGIONS:
            raise GfxError('target %s: unknown sub-region %s' % (name, subregion))
        self.name = name
        self.build = build
        self.subregion = subregion
        self.module = module

    @property
    def region(self):
        return SUBREGIONS[self.subregion] if self.subregion else None

    def __repr__(self):
        return '<Target %s%s>' % (self.name, ' in %s' % self.subregion if self.subregion else '')


def module_path(name, folder=None):
    """The module file of a target, or None if it does not exist yet."""
    folder = folder or HERE
    for path in (os.path.join(folder, name + '.py'), os.path.join(folder, name, '__init__.py')):
        if os.path.isfile(path):
            return path
    return None


def load_target(name, subregion=None, folder=None, package=None):
    """Target for module <package>.<name> (default tools.gfx.<name>, file in
    tools/gfx), or None if the file does not exist. Errors inside an existing
    module propagate."""
    path = module_path(name, folder)
    if path is None:
        return None
    module = importlib.import_module('%s.%s' % (package or PACKAGE, name))
    build = getattr(module, 'build', None)
    if not callable(build):
        raise TargetError('%s has no build(ctx) function' % rel(path))
    return Target(name, build, subregion, module)


NO_MODULE = 'no module yet'
LEFT_OUT = 'left out (FULL_BUILD = False)'


def select_targets(targets=None):
    """(targets, notes). targets: None = every registered target whose module
    exists, except modules with FULL_BUILD = False; otherwise a list of
    registered names and/or Target objects (() = none). notes: [(name, reason)]
    for the registered targets that were skipped."""
    selected, notes = [], []
    if targets is None:
        for name, sub in TARGETS.items():
            t = load_target(name, sub)
            if t is None:
                notes.append((name, NO_MODULE))
            elif getattr(t.module, 'FULL_BUILD', True) is False:
                notes.append((name, LEFT_OUT))
            else:
                selected.append(t)
    else:
        for item in targets:
            if isinstance(item, Target):
                selected.append(item)
                continue
            if item not in TARGETS:
                raise GfxError('unknown target %r (registered: %s)' % (item, ', '.join(TARGETS)))
            t = load_target(item, TARGETS[item])
            if t is None:
                notes.append((item, NO_MODULE))
            else:
                selected.append(t)
    names = [t.name for t in selected]
    for name in names:
        if names.count(name) > 1:
            raise GfxError('target %s selected twice' % name)
    return selected, notes


# ---------------------------------------------------------------------------
# Phase 1

def _is_library_error(e):
    """Errors that the graphics library and the targets raise on purpose (text
    does not fit, missing glyph, palette or budget...): ValueErrors defined in
    this package. They are reported as messages; anything else is a bug and
    keeps its traceback."""
    return isinstance(e, ValueError) and type(e).__module__.startswith(PACKAGE + '.')


def _check_result(t, result, root):
    if not isinstance(result, Result):
        raise TargetError('%s: build(ctx) returned %s, not a tools.gfx.target.Result'
                          % (t.name, type(result).__name__))
    writes = []
    for item in result.writes:
        try:
            addr, data = item
        except (TypeError, ValueError):
            raise TargetError('%s: a write is not (address, bytes): %r' % (t.name, item))
        if not isinstance(addr, int) or not isinstance(data, (bytes, bytearray, memoryview)):
            raise TargetError('%s: a write is not (address, bytes): %r' % (t.name, (addr, type(data).__name__)))
        writes.append((addr, bytes(data)))
    allow = []
    for item in result.allow:
        try:
            lo, hi = item
        except (TypeError, ValueError):
            raise TargetError('%s: a range is not (lo, hi): %r' % (t.name, item))
        if not isinstance(lo, int) or not isinstance(hi, int) or hi <= lo:
            raise TargetError('%s: bad range %r' % (t.name, item))
        region = t.region
        if hi > FREE_START and not (region and region[0] <= lo and hi <= region[1]):
            raise TargetError('%s: in-place range %06X-%06X is in the free area but not inside the target\'s '
                              'sub-region (%s)' % (t.name, lo, hi - 1, '%s %06X-%06X' % (
                                  t.subregion, region[0], region[1] - 1) if region else 'none'))
        allow.append((lo, hi))
    asm = result.asm
    if asm is not None:
        if not isinstance(asm, str):
            raise TargetError('%s: Result.asm must be a path or None' % t.name)
        if not os.path.isabs(asm):
            asm = os.path.join(root, asm)
        asm = os.path.abspath(asm)
        if not os.path.isfile(asm):
            raise TargetError('%s: asm entry %s does not exist' % (t.name, asm))
    if not isinstance(result.stats, dict):
        raise TargetError('%s: Result.stats must be a dict' % t.name)
    return Result(writes, allow, asm, [str(p) for p in result.previews], result.stats)


def include_path(path, folder):
    """Path of path relative to folder for an .include (forward slashes);
    absolute when there is no relative path (another drive)."""
    try:
        r = os.path.relpath(path, folder)
    except ValueError:
        r = os.path.abspath(path)
    return r.replace(os.sep, '/')


def gfx_asm_text(entries, folder):
    """The generated include: constants, then each target's asm entry.
    entries: [(name, asm path)]; folder: where the file goes (include paths
    are relative to it). The line after each include marks the end of the
    target's lines for check_chunks."""
    out = ['; Generated by tools/gfx/build.py (graphics phase 1); rewritten by every build. Do not edit.',
           '; Graphics region (tools/patch/layout.py) and its sub-regions (tools/gfx/build.py)',
           'GFX_START = 0x%06X' % GFX_START,
           'GFX_END = 0x%06X' % GFX_END]
    for name, (lo, hi) in SUBREGIONS.items():
        out.append('%s = 0x%06X' % (name, lo))
        out.append('%s_END = 0x%06X' % (name, hi))
    if not entries:
        out.append('; no targets')
    for name, path in entries:
        out += ['; target %s' % name,
                '        .include "%s"' % include_path(path, folder),
                '; end of target %s' % name]
    return '\n'.join(out) + '\n'


class TargetRun:
    """A target that ran in phase 1: target, ctx, result."""

    def __init__(self, target, ctx, result):
        self.target = target
        self.ctx = ctx
        self.result = result

    @property
    def name(self):
        return self.target.name


def prepare(root, base, rom, targets=None, gfx_dir=None, asm_path=None, log=print, notes=()):
    """Graphics phase 1. rom is the bytearray being built (phase 2 writes into
    it). targets: see select_targets (None = the registry; () = none, for
    --no-gfx). gfx_dir: root of the targets' work folders (default
    <root>/build/gfx); asm_path: the generated include (default
    <gfx_dir>/gfx.asm). Returns a GfxBuild."""
    gfx_dir = gfx_dir or os.path.join(root, 'build', 'gfx')
    asm_path = os.path.abspath(asm_path or os.path.join(gfx_dir, 'gfx.asm'))
    selected, more = select_targets(targets)
    notes = list(notes) + more
    snapshot = bytes(rom)
    patch = RomPatch(base, rom)
    runs = []
    for t in selected:
        ctx = Context(root, t.name, base, snapshot, os.path.join(gfx_dir, t.name), t.subregion, t.region, log)
        try:
            result = t.build(ctx)
        except GfxError as e:
            raise TargetError('target %s: %s' % (t.name, e)) from e
        except Exception as e:
            if _is_library_error(e):
                raise TargetError('target %s: %s: %s' % (t.name, type(e).__name__, e)) from e
            raise
        result = _check_result(t, result, root)
        patch.register(t.name)
        for lo, hi in result.allow:
            patch.allow(lo, hi, t.name)
        for addr, data in result.writes:
            patch.write(addr, data, t.name)
        runs.append(TargetRun(t, ctx, result))
    entries = [(r.name, r.result.asm) for r in runs if r.result.asm]
    text = gfx_asm_text(entries, os.path.dirname(asm_path))
    write_if_changed(asm_path, text)
    return GfxBuild(root, base, rom, patch, runs, notes, asm_path, text)


# ---------------------------------------------------------------------------
# Chunk attribution (which file's .org started each chunk)

# The label and assignment forms of tools/asm/tlcs900asm.py (Assembler._pass),
# and its include form (Assembler.load).
_LABEL = re.compile(r'^\s*([A-Za-z_.][A-Za-z0-9_.]*)\s*:(.*)$')
_ASSIGN = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.+)$')
_INCLUDE = re.compile(r'^\s*\.include\s+"([^"]+)"')


def generated_lines(text):
    """[(line number, text)] of a generated include as Assembler.load keeps
    them: the comment cut off, right-stripped, .include lines left out (the
    included file's lines take their place)."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.split(';', 1)[0].rstrip()
        if not _INCLUDE.match(s):
            out.append((n, s))
    return out


def scan_lines(lines, gfx_asm, entries):
    """Walk an Assembler's line list (asm.lines: (file, line number, text
    without comment), includes already expanded) the way its passes do.

    Lines from a target's asm entry, and from the files it includes, belong to
    that target until the next line of gfx_asm (the generated include has a
    line after every include). Returns (owners, defs): the owner (target name
    or None) of each .org, in order, which is also the owner of each chunk that
    Assembler.assemble() returns; and {symbol: [(owner, file, line)]}."""
    gkey = _key(gfx_asm)
    ekeys = {_key(path): name for name, path in entries}
    keys = {}
    owner = None
    owners = []
    started = set()
    defs = {}
    for fname, lineno, s in lines:
        k = keys.get(fname)
        if k is None:
            k = keys[fname] = _key(fname)
        if k == gkey:
            owner = None
        elif k in ekeys:
            owner = ekeys[k]
        if not s.strip():
            continue
        m = _LABEL.match(s)
        if m:
            defs.setdefault(m.group(1), []).append((owner, fname, lineno))
            if owner is not None and owner not in started:
                raise ChunkError('%s:%d: target %s: label %s before the first .org'
                                 % (rel(fname), lineno, owner, m.group(1)))
            s = m.group(2)
            if not s.strip():
                continue
        m = _ASSIGN.match(s)
        if m:
            defs.setdefault(m.group(1), []).append((owner, fname, lineno))
            continue
        op = s.split(None, 1)[0].lower()
        if op == '.org':
            owners.append(owner)
            if owner is not None:
                started.add(owner)
        elif owner is not None and owner not in started:
            raise ChunkError('%s:%d: target %s: code or data before the first .org (it would be appended to '
                             'the section before the include)' % (rel(fname), lineno, owner))
    return owners, defs


class GfxBuild:
    """The state between the graphics phases (see the module docstring)."""

    def __init__(self, root, base, rom, patch, runs, notes, asm_path, asm_text=None):
        self.root = root
        self.base = base
        self.rom = rom
        self.patch = patch
        self.runs = runs
        self.notes = notes
        self.asm_path = asm_path
        self.asm_text = asm_text    # the generated include as phase 1 wrote it (None: not checked)
        self.chunks = {}            # target -> {'hooks': [(org, end)], 'data': [(org, end)]}
        self.target_chunks = []     # (target, org, bytes) of every target chunk, checked again in phase 2
        self.applied = False

    @property
    def names(self):
        return [r.name for r in self.runs]

    def skipped(self):
        """'no module yet: intro, cards; ...' for the skipped targets, or ''."""
        reasons = {}
        for name, reason in self.notes:
            reasons.setdefault(reason, []).append(name)
        return '; '.join('%s: %s' % (reason, ', '.join(names)) for reason, names in reasons.items())

    def report(self):
        """Phase 1 report lines."""
        skipped = self.skipped()
        if not self.runs:
            return ['graphics: no targets%s' % (' (%s)' % skipped if skipped else '')]
        lines = ['graphics: %d target%s (%s)%s' % (len(self.runs), '' if len(self.runs) == 1 else 's',
                                                    ', '.join(self.names), '; %s' % skipped if skipped else '')]
        for r in self.runs:
            res = r.result
            parts = ['%d in-place write%s (%s bytes)' % (len(res.writes), '' if len(res.writes) == 1 else 's',
                                                        format(sum(len(d) for _, d in res.writes), ','))]
            if res.asm:
                parts.append('asm %s' % rel(res.asm, self.root))
            if res.previews:
                parts.append('%d preview%s in %s' % (len(res.previews), '' if len(res.previews) == 1 else 's',
                                                      rel(r.ctx.work, self.root)))
            parts += ['%s %s' % (k, v) for k, v in res.stats.items()]
            lines.append('  %s: %s' % (r.name, ', '.join(parts)))
        return lines

    def check_chunks(self, chunks, lines):
        """Check the chunks that Assembler.assemble() returned for an assembly
        that includes self.asm_path; lines is that Assembler's .lines. Returns
        report lines; raises ChunkError."""
        entries = [(r.name, r.result.asm) for r in self.runs if r.result.asm]
        self.check_assembled(lines, entries)
        owners, defs = scan_lines(lines, self.asm_path, entries)
        if len(owners) != len(chunks):
            raise ChunkError('internal: %d .org lines but %d chunks (has the assembler changed?)'
                             % (len(owners), len(chunks)))
        for sym, where in defs.items():
            if len(where) > 1 and any(o is not None for o, _, _ in where):
                raise ChunkError('symbol %s is defined more than once: %s' % (
                    sym, ', '.join('%s:%d' % (rel(f, self.root), n) for _, f, n in where)))
        runs = {r.name: r for r in self.runs}
        stats = {name: {'hooks': [], 'data': []} for name, _ in entries}
        self.target_chunks = []
        for (org, data), owner in zip(chunks, owners):
            if not data:
                continue
            end = org + len(data)
            if owner is None:
                if org < GFX_END and GFX_START < end:
                    raise ChunkError('chunk %06X-%06X is in the graphics region (%06X-%06X), which only the '
                                     'tools/gfx targets may use' % (org, end - 1, GFX_START, GFX_END - 1))
                continue
            self.target_chunks.append((owner, org, bytes(data)))
            t = runs[owner].target
            if end <= FREE_START:
                off = org - ROM_BASE
                if self.rom[off:off + len(data)] != self.base[off:off + len(data)]:
                    raise ChunkError('target %s: hook %06X-%06X is on bytes that were changed already (UI text or '
                                     'locations of this build, or the input ROM)' % (owner, org, end - 1))
                stats[owner]['hooks'].append((org, end))
                continue
            if org < FREE_START:
                raise ChunkError('target %s: chunk %06X-%06X straddles the start of the free area (%06X)'
                                 % (owner, org, end - 1, FREE_START))
            if t.region is None:
                raise ChunkError('target %s: chunk %06X-%06X is new data, but the target has no sub-region '
                                 '(in place only; see TARGETS in tools/gfx/build.py)' % (owner, org, end - 1))
            lo, hi = t.region
            if not (lo <= org and end <= hi):
                raise ChunkError('target %s: chunk %06X-%06X is outside its sub-region %s (%06X-%06X)'
                                 % (owner, org, end - 1, t.subregion, lo, hi - 1))
            stats[owner]['data'].append((org, end))
        self.chunks = stats
        out = []
        for name, st in stats.items():
            t = runs[name].target
            parts = []
            hooks, data = st['hooks'], st['data']
            parts.append('%d hook%s (%d bytes)' % (len(hooks), '' if len(hooks) == 1 else 's',
                                                    sum(b - a for a, b in hooks)))
            if data:
                used = sum(b - a for a, b in data)
                parts.append('new data %s in %s (%s of %s bytes)' % (
                    format_ranges(merge_ranges(data)), t.subregion, format(used, ','),
                    format(t.region[1] - t.region[0], ',')))
            out.append('  %s: %s' % (name, ', '.join(parts)))
        return out

    def check_assembled(self, lines, entries):
        """The assembly (lines: Assembler.lines) holds the include that phase 1
        wrote, once, and every target's asm entry. Otherwise a target's chunks
        would be missing without an error: main.asm without the include, or
        build/gfx/gfx.asm rewritten in between by another build (every full
        build writes it; e.g. a --no-gfx comparison running at the same time).
        entries: [(name, asm path)]."""
        if self.asm_text is None:
            return
        keys = {}
        for f, _, _ in lines:
            if f not in keys:
                keys[f] = _key(f)
        gkey = _key(self.asm_path)
        got = [(n, s) for f, n, s in lines if keys[f] == gkey]
        name = rel(self.asm_path, self.root)
        if not got:
            raise ChunkError('the assembly does not include %s (patch/main.asm must include it once, near the '
                             'end)' % name)
        if got != generated_lines(self.asm_text):
            raise ChunkError('%s is not the file that graphics phase 1 wrote: it is included twice, or another '
                             'build rewrote it in the meantime (one running at the same time, e.g. with --no-gfx); '
                             'build again' % name)
        files = set(keys.values())
        for target, path in entries:
            if _key(path) in files:
                continue
            try:
                empty = os.path.getsize(path) == 0
            except OSError:
                empty = False
            if not empty:
                raise ChunkError('target %s: its asm entry %s was not assembled (%s was rewritten by another '
                                 'build in the meantime?); build again' % (target, rel(path, self.root), name))

    def apply_inplace(self):
        """Graphics phase 2: check that no later writer overwrote a target's
        chunk (hooks are applied before the dialogue and the tables), then
        commit the queued in-place writes. Returns report lines (none when no
        target ran)."""
        if self.applied:
            raise GfxError('graphics phase 2 ran already')
        for owner, org, data in self.target_chunks:
            off = org - ROM_BASE
            if bytes(self.rom[off:off + len(data)]) != data:
                first = next(i for i in range(len(data)) if self.rom[off + i] != data[i])
                raise GfxError('target %s: its chunk %06X-%06X was overwritten by a later writer (first at %06X)'
                               % (owner, org, org + len(data) - 1, org + first))
        lines = self.patch.commit()
        self.applied = True
        if not self.runs:
            return []
        return ['graphics: in-place writes'] + lines + self.subregion_usage()

    def subregion_usage(self):
        """Report lines for the sub-regions that differ from the original (the
        layout report measures the whole graphics region from its start)."""
        out = []
        for name, (lo, hi) in SUBREGIONS.items():
            a, b = lo - ROM_BASE, hi - ROM_BASE
            if self.rom[a:b] == self.base[a:b]:
                continue
            changed = [i for i in range(a, b) if self.rom[i] != self.base[i]]
            out.append('  %s %06X-%06X: %s of %s bytes used (%s changed)' % (
                name, lo, hi - 1, format(changed[-1] + 1 - a, ','), format(hi - lo, ','), format(len(changed), ',')))
        return ['graphics: sub-regions'] + out if out else []


# ---------------------------------------------------------------------------

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print(__doc__)
        return 0 if argv[0] in ('-h', '--help') else 2
    print('graphics region %06X-%06X (%d KB)' % (GFX_START, GFX_END - 1, (GFX_END - GFX_START) // 1024))
    for name, (lo, hi) in SUBREGIONS.items():
        print('  %-9s %06X-%06X %3d KB  %s' % (name, lo, hi - 1, (hi - lo) // 1024, SUBREGION_USE[name]))
    print('targets:')
    for name, sub in TARGETS.items():
        path = module_path(name)
        if path is None:
            state = 'no module yet'
        else:
            state = rel(path)
            t = load_target(name, sub)
            if getattr(t.module, 'FULL_BUILD', True) is False:
                state += ' (FULL_BUILD = False)'
        print('  %-7s %-9s %s' % (name, sub or 'in place', state))
    return 0


if __name__ == '__main__':
    sys.exit(main())
