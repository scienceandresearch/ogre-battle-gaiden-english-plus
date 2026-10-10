"""Static inventory of the graphics the game loads (survey for pre-drawn Japanese).

    python -m tools.gfx.inventory ROM OUTDIR [--no-png]

ROM is the original image (rom/baserom.ngc). OUTDIR must be a local folder such as
build/gfx/inventory: the PNG files are decoded ROM graphics and are never committed.
The notes that go with this tool are docs/workstreams/gfx-survey.md.

1. Scripts. Every script that tools.text.extract.build_walker finds, plus the scripts
   that native code starts without the patterns the walker follows (in native code the
   walker never visits):
     * task slots: `ld.l R, (script << 8) | n` then `ld.l (slot), R`, where slot is a
       task's script slot (0x4086 + 0x38 * task + 0, 4 or 8);
     * `ld.l XDE, script` then a jump or call to the VM loop 0x20023D;
     * `calr 0x20023C` (inline bytecode; the walker seeds only the 24-bit call).
2. Graphics ops of every walked script: gfx2a / gfx2c (tiles, VM copy routine
   0x200B37), gfxfe (map block, 0x2009F1), gfx26 / gfx28 (palettes, 0x200B33) and
   anim (sprite list). gfx2c copies relative to the task's sprite tile; its dest is the
   operand. gfx28 adds the task palette (0-15) * 8 to its dest. An anim op's dest is
   the tile base of the nearest `tile` op of the same script run, if any.
3. Native loaders: every call or jump to 0x200B37 / 0x200194 (tiles), 0x200B33
   (palettes) and 0x2009F1 / 0x2009F4 (maps). XIY (source), IX (dest) and BC (size) come
   from a backward search over the local control-flow graph; each immediate source
   value found on some path gives one op.
4. Table-driven loaders (`_tables`): native code that computes the source from a
   table (menu icons and labels, map unit icons, result banners, intro lines, chapter
   card sheets, tarot cards, ending text, battle backgrounds, popup icons). Each table
   was found by reading its loader; the entries are enumerated as ops 'table:<name>'.
5. Filters (counts are printed before and after):
     tiles     dest 0xA000-0xBFFF (the copy must end by 0xC000), source in ROM below the
               free space (0x200000-0x36746C), 1 to 0x1000 words;
     maps      dest 0x9000-0x9FFF, ROM source, header 1-32 x 1-32;
     palettes  dest 0x8200-0x83FF, ROM source, at most 0x100 words;
     anim      ROM source, 1-64 sprites.
   A native or table load whose dest is set at run time (a task's tile field) is kept
   when its source and size pass ('dest set at run time'). A source in RAM (below
   0x10000) is a dynamic load: counted, never rendered.
6. Output in OUTDIR: inventory.txt (every op with its verdict), blocks.txt (distinct
   tile blocks with users and class), tiles/T_<src>.png (grey sheet of each block, 16
   tiles per row), maps/M_<src>_<site>.png (each map block drawn with the tiles and
   palettes of its script run, else of the loads stored nearest to it in ROM: a guess;
   magenta = tile not loaded), sprites/S_<list>_<tile>.png (sprite lists that have a
   tile base), contact/sheet_NN.png (all blocks, labelled with address, size, class).
7. Classes: CLASSES below is the survey's verdict per block (address and English
   description only). A block that is not in the table is printed as 'unclassified',
   so a later change of the walk shows up.
"""
import os
import sys
from collections import defaultdict

from ..common import png
from ..common.tiles import decode_tile_2bpp
from ..recomp.rom import Rom, ROM_BASE
from ..recomp.tlcs900 import decode, DecodeError, Imm, Mem, Reg
from ..text.extract import build_walker

ROM_LO, ROM_HI = 0x200000, 0x36746D      # program and data; 0x36746D on is free (0xFF)
TILE_LO, TILE_HI = 0xA000, 0xC000         # character RAM (512 tiles)
MAP_LO, MAP_HI = 0x9000, 0xA000           # scroll plane maps (plane 1 0x9000, plane 2 0x9800)
PAL_LO, PAL_HI = 0x8200, 0x8400           # palettes (sprites 0x8200, plane 1 0x8280, plane 2 0x8300)
MAX_WORDS = 0x1000
VM_INLINE, VM_LOOP = 0x20023C, 0x20023D
TASK0, TASK_SIZE, TASKS = 0x4086, 0x38, 16

# native copy routines: address -> (kind, description)
ROUTINES = {
    0x200B37: ('tiles', 'copy BC words XIY -> IX (direct, or queued while the display is on)'),
    0x200194: ('tiles', 'queue a VBlank copy of BC words XIY -> IX'),
    0x200B33: ('palette', 'copy C+1 colour words XIY -> IX'),
    0x2009F1: ('map', 'map block [w][h] + entries XIY -> map IX'),
    0x2009F4: ('map', 'map entries XIY -> map IX, size preset in BC'),
}

# The four round-1 targets (docs/workstreams/gfx-*.md): ROM ranges they own.
KNOWN_TARGETS = {
    'labels': [(0x218112, 0x219792)],                          # 45 menu labels
    'intro': [(0x290F55, 0x29311D), (0x293DDD, 0x29496D)],     # palette, 15 lines, narration map
    'cards': [(0x29EE8E, 0x29EF0A), (0x29F34A, 0x2A1E4A), (0x2A2144, 0x2A2F0C)],
    'title': [(0x28CECF, 0x28CFA1), (0x28D277, 0x28FB81)],     # menu label maps; package to the plane-2 map end
}

# ---------------------------------------------------------------------------
# Survey verdicts: (lo, hi, class, description). A block whose start lies in
# [lo, hi) gets the class. Classes: 'none' (no text), 'english', 'japanese',
# 'unclear', 'known' (one of the round-1 targets). Filled in from the review of
# the rendered sheets; see docs/workstreams/gfx-survey.md.
# ---------------------------------------------------------------------------
CLASSES = [
    # bank 0x20: map, HUD and banner art
    (0x200C99, 0x200C9A, 'none', 'digits 0-9 for the tile-mapped printer'),
    (0x201C03, 0x201ECB, 'none', 'small map effect sprites'),
    (0x201ECB, 0x201FEB, 'english', 'stat-up sprites STR AGI INT CHA ALI LUK H.P. L.V. UP!'),
    (0x202006, 0x202D86, 'none', 'map unit icons (54 x 4 tiles, table 0x201FC6)'),
    (0x202D86, 0x202E86, 'none', 'map icons'),
    (0x206C9B, 0x206D0B, 'english', 'unit window field labels F: B: MOVE ITEM'),
    (0x20A588, 0x20ADD8, 'english', 'map HUD sheet: PAUSE, NEXT Lv, stat names, COST, GOTH, EXP, ITEM, '
                                    'TAROT, UNIT, CITY, OK!, BAD, UP'),
    (0x20AFF5, 0x20B135, 'none', 'window frame pieces and digits'),
    (0x20B5CB, 0x20BCDB, 'english', 'stage clear screen: Congratulation!, YOU COMPLETED THIS MAP., '
                                    'BONUS MONEY, Goth., digits'),
    (0x20BE14, 0x20C1E4, 'english', 'game over art "Game" / "Over" (sprite lists 0x20BCDB, 0x20BD77)'),
    (0x20C25E, 0x20C3CE, 'english', 'banner FIND OUT!'),
    (0x20C418, 0x20C5E8, 'english', 'banner FIGHT IT OUT!'),
    (0x20C62A, 0x20C7CA, 'english', 'banner LIBERATION'),
    (0x20C7CA, 0x20C93A, 'english', 'banner LUCKY!!'),
    (0x20C93A, 0x20CAAA, 'english', 'banner THANK YOU'),
    (0x20CAAA, 0x20CC1A, 'english', 'banner Boo!Boo!'),
    (0x20CC1A, 0x20CC5A, 'english', 'label BOSS!'),
    (0x20CC5A, 0x20CC9A, 'english', 'label READY'),
    # bank 0x21: organize, menus, tarot cards
    (0x214450, 0x214451, 'japanese', 'organize sheet: English field labels and frames, plus the '
                                     '"deployed" tag (tiles 0x5B-0x5F = ROM 0x214A00, 80 bytes)'),
    (0x2148A0, 0x214960, 'none', 'item icons (inside the organize sheet; another loader)'),
    (0x2172D2, 0x2172D3, 'none', 'menu icons (57 x 4 tiles; pictograms, one reads NEXT)'),
    (0x217F52, 0x217F92, 'english', 'label NEXT'),
    (0x218112, 0x219792, 'known', 'round-1 target: menu labels (gfx-labels.md)'),
    (0x21C0F9, 0x226000, 'english', 'tarot card art: roman numeral and English caption (table 0x219918)'),
    # banks 0x27-0x28: event art and portraits
    (0x273870, 0x273EE0, 'none', 'stage map terrain tiles'),
    (0x274F5D, 0x2797CC, 'none', 'event background landscapes'),
    (0x2797CC, 0x28C700, 'none', 'character portraits'),
    (0x28D307, 0x28F307, 'known', 'round-1 target: title package (gfx-title-logo.md)'),
    (0x28FBB1, 0x2900B1, 'english', 'publisher logo screen (word mark, web address)'),
    (0x2904CB, 0x290DCB, 'japanese', 'unused text screen: 9 lines of 16 characters of prose; its loader '
                                     'script 0x28CB82 has no reference'),
    (0x290F5D, 0x29311D, 'known', 'round-1 target: intro narration lines (gfx-intro-narration.md)'),
    (0x29312D, 0x293DDD, 'none', 'intro cloud tiles (two copies)'),
    # bank 0x29: opening reading, data screen, scenario map
    (0x297651, 0x299471, 'none', 'tarot reading scene art and sparkles'),
    (0x29A849, 0x29B049, 'english', 'data load screen: stained glass, frames, Lv- (DATA LOAD and NOTHING '
                                    'are font text)'),
    (0x29C9A4, 0x29D1A4, 'english', 'scenario map frame and the banner The Zenobian Age'),
    (0x29D402, 0x29E3FA, 'none', 'scenario map art'),
    (0x29E3FA, 0x29E5FA, 'none', 'scenario map symbols'),
    (0x29E7CE, 0x29EA4E, 'none', 'scenario popup icons'),
    (0x29EF0A, 0x29F34A, 'known', 'round-1 target: chapter card emblem (no text; gfx-chapter-cards.md)'),
    (0x29F34A, 0x2A1E4A, 'known', 'round-1 target: chapter card sheets (gfx-chapter-cards.md)'),
    # bank 0x2A: ending
    (0x2A4E54, 0x2AFC54, 'japanese', 'ending epilogue text, 5 endings, 87 lines of 32 tiles (table '
                                     '0x2A3058); the display routine has no reference: unused'),
    (0x2AFF4E, 0x2B054E, 'english', 'ending results screen: CHAOS FRAME, PT., CONQUEST, DAYS, digits'),
    (0x2B0850, 0x2B0890, 'english', 'SNK word mark (staff roll)'),
    # banks 0x2C-0x35: battle
    (0x2C9AFD, 0x2C9BBD, 'english', 'battle numbers: MISS and digits'),
    (0x2C9D1D, 0x2C9E1D, 'none', 'battle icons'),
    (0x2CC784, 0x2CC7E4, 'english', 'battle labels WAKE, LEVEL UP!'),
    (0x2CCC3D, 0x2CD60D, 'none', 'battle effect sprites'),
    (0x2CF390, 0x2DCB30, 'none', 'battle backgrounds (tables 0x2CDDCC, 0x2CDE6C)'),
    (0x2DEF17, 0x2DEFA7, 'none', 'link battle art'),
    (0x2E3BDE, 0x2E3BEE, 'none', 'cursor'),
    (0x2E62AA, 0x2E6B2A, 'none', 'link menu icons'),
    (0x2E6C4A, 0x2E6CBA, 'none', 'digits 1-7'),
    (0x2E6CBA, 0x2E6DBA, 'none', 'window frame pieces'),
    (0x2E6DBA, 0x2E6DBB, 'japanese', 'link copy of the organize sheet, with the "deployed" tag copy '
                                     '(tiles 0x5B-0x5F = ROM 0x2E736A)'),
    (0x2F99A2, 0x2F9A92, 'english', 'battle effect with sleep marks zzz'),
    (0x2F9E6F, 0x2F9EAF, 'english', 'battle label M-SHILD (sic)'),
    (0x2FB123, 0x2FB163, 'english', 'battle label AGI UP!'),
    (0x2FB269, 0x2FB2A9, 'english', 'battle label R-AGAIN'),
    (0x2FB39D, 0x2FB3DD, 'english', 'battle label DEF DOWN'),
    (0x2FB4BC, 0x2FB4FC, 'english', 'battle label DEF UP!'),
    (0x2FE5ED, 0x2FE60D, 'japanese', 'battle hit-reaction label meaning "paralysed!" (2 tiles)'),
    (0x3206A9, 0x3206C9, 'none', 'battle hit-reaction marks !?'),
    (0x2E8000, 0x35C000, 'none', 'battle animation frames and spell effects'),
    (0x35C000, 0x35E700, 'none', 'small unit sprites (4-6 tiles each)'),
]


# ---------------------------------------------------------------------------
# Walk
# ---------------------------------------------------------------------------

def _task_slot(addr):
    off = addr - TASK0
    return 0 <= off < TASK_SIZE * TASKS and off % TASK_SIZE in (0, 4, 8)


def _decode(rom, a):
    try:
        return decode(rom.read8, a)
    except DecodeError:
        return None


def extra_seeds(rom):
    """Script entry points that native code sets up in ways the walker does not
    follow outside the native code it visits. Returns [(entry, why)]."""
    seeds = []
    data = rom.data
    for off in range(len(data) - 6):
        op = data[off]
        a = ROM_BASE + off
        if 0x40 <= op <= 0x47:                          # ld.l R, imm32
            ins = _decode(rom, a)
            if ins is None or ins.mnem != 'ld' or not isinstance(ins.ops[1], Imm):
                continue
            v = ins.ops[1].value
            reg = ins.ops[0]
            b = ins.next
            for _ in range(6):
                j = _decode(rom, b)
                if j is None:
                    break
                # task slot: value = script << 8 | frames to wait
                if (ROM_LO <= v >> 8 < ROM_HI and 1 <= (v & 0xFF) <= 0x10 and j.mnem == 'ld'
                        and len(j.ops) == 2 and isinstance(j.ops[0], Mem) and j.ops[0].mode == 'abs'
                        and _task_slot(j.ops[0].disp) and j.ops[1] == reg):
                    seeds.append((v >> 8, 'taskslot@%06X' % a))
                    break
                # ld.l XDE, script ; ... ; jp/call (cc,) 0x20023D
                if (reg == Reg(32, 0xE8) and ROM_LO <= v < ROM_HI and
                        j.kind in ('jump', 'call', 'branch') and j.target == VM_LOOP):
                    seeds.append((v, 'xde@%06X' % a))
                    break
                if j.kind in ('jump', 'ret', 'reti', 'ijump', 'call') and j.cond in (None, 8):
                    break
                if isinstance(j.ops, tuple) and j.ops and j.ops[0] == reg:
                    break                               # register overwritten
                b = j.next
        elif op == 0x1E and off + 3 <= len(data):        # calr 0x20023C: inline bytecode
            d = data[off + 1] | data[off + 2] << 8
            if (a + 3 + (d - 0x10000 if d & 0x8000 else d)) & 0xFFFFFF == VM_INLINE:
                seeds.append((a + 3, 'calr-inline@%06X' % a))
    return seeds


def walk(rom):
    """The text walker plus the extra seeds. Returns (walker, stats)."""
    w = build_walker(rom, log=lambda *a: None)
    stats = {'walker_entries': len(w.script_entries), 'walker_insns': len(w.script),
             'walker_set': set(w.script)}
    seeds = extra_seeds(rom)
    new = sorted({e for e, _ in seeds if e not in w.script and e not in w.script_entries})
    for e, why in seeds:
        w.add_script(e, why)
    w.run()
    stats.update(seeds=len(seeds), new_entries=len(new), entries=len(w.script_entries),
                 insns=len(w.script))
    return w, stats


# ---------------------------------------------------------------------------
# Ops
# ---------------------------------------------------------------------------

class Op:
    __slots__ = ('kind', 'site', 'src', 'dest', 'count', 'w', 'h', 'via', 'ok', 'why', 'run')

    def __init__(self, kind, site, src=None, dest=None, count=None, via=None):
        self.kind = kind          # 'tiles', 'map', 'palette', 'anim'
        self.site = site          # script op address, or native call site
        self.src = src
        self.dest = dest
        self.count = count        # words (tiles), entries (map), colours (palette), sprites (anim)
        self.w = self.h = None
        self.via = via            # script mnemonic, or 'native:<routine>'
        self.ok = False
        self.why = ''
        self.run = None           # start of the straight script run that holds the op

    def describe(self):
        def h(v, n=6):
            return ('%0*X' % (n, v)) if isinstance(v, int) else (v or '?')
        s = '%-6s %06X %-14s src=%s dest=%s' % (self.kind, self.site, self.via, h(self.src), h(self.dest, 4))
        if self.kind == 'map' and self.w is not None:
            s += ' %dx%d' % (self.w, self.h)
        elif self.count is not None:
            s += ' n=%s' % (('%X' % self.count) if isinstance(self.count, int) else self.count)
        return s


def script_runs(w):
    """Map each script instruction to the start of its straight run (consecutive
    instructions, broken after any instruction that ends the flow)."""
    run_of = {}
    start = prev = None
    for a in sorted(w.script):
        ins = w.script[a]
        if prev is None or prev.next != a or prev.flow == 'end':
            start = a
        run_of[a] = start
        prev = ins
    return run_of


def script_ops(rom, w):
    """Graphics ops of the walked scripts. An anim op's dest is the sprite tile base
    set by a `tile` op of the same run (the nearest one), when there is one."""
    run_of = script_runs(w)
    ops = []
    tiles_of_run = defaultdict(list)
    for a in sorted(w.script):
        ins = w.script[a]
        m = ins.mnem
        if m in ('gfx2a', 'gfx2c'):
            o = Op('tiles', a, ins.args[0], ins.args[1], ins.args[2], m)
        elif m == 'gfxfe':
            o = Op('map', a, ins.args[0], ins.args[1], None, m)
        elif m in ('gfx26', 'gfx28'):
            o = Op('palette', a, ins.args[0], ins.args[2], ins.args[1] + 1, m)
        elif m == 'anim':
            o = Op('anim', a, ins.args[0], None, None, m)
        else:
            if m == 'tile':
                tiles_of_run[run_of[a]].append((a, ins.args[0] & 0x1FF))
            continue
        o.run = run_of[a]
        ops.append(o)
    for o in ops:
        if o.kind == 'anim' and tiles_of_run.get(o.run):
            o.dest = min(tiles_of_run[o.run], key=lambda t: abs(t[0] - o.site))[1]
    return ops


# registers as (32-bit code base); 8/16-bit codes of the same register share code & 0xFC
_XIX, _XIY, _XBC = 0xF0, 0xF4, 0xE4
_NO_WRITE = {'cp', 'bit', 'push', 'andcf', 'orcf', 'xorcf', 'ldcf', 'stcf', 'jp', 'jr', 'jrl',
             'call', 'calr', 'ret', 'reti', 'nop', 'halt'}


def _writes(ins, base):
    if not ins.ops:
        return ins.mnem in ('ldir', 'lddr', 'ldi', 'ldd', 'cpir', 'cpdr')
    if ins.mnem in ('ldir', 'lddr', 'ldi', 'ldd'):
        return True
    op0 = ins.ops[0]
    if isinstance(op0, Reg) and ins.mnem not in _NO_WRITE:
        if (op0.code & 0xFC) == base:
            return True
    if ins.mnem == 'ex':
        return any(isinstance(o, Reg) and (o.code & 0xFC) == base for o in ins.ops)
    return False


def _imm_of(ins, base):
    """Value given to the register by `ins` if it is an immediate load, else None."""
    if ins.mnem == 'ld' and len(ins.ops) == 2 and isinstance(ins.ops[1], Imm):
        return ins.ops[1].value
    if ins.mnem == 'lda' and len(ins.ops) == 2 and isinstance(ins.ops[1], Mem) and ins.ops[1].mode == 'abs':
        return ins.ops[1].disp
    return None


def _window(rom, site, native, back=0x100):
    """Instructions of the code before `site` (addr -> insn): the walker's own decoding
    when it covers the site, else a linear decoding from the earliest start in
    [site - back, site) that lands exactly on the site."""
    if site in native:
        return {a: i for a, i in native.items() if site - back <= a < site}
    for s in range(site - back, site):
        a, out = s, {}
        while a < site:
            ins = _decode(rom, a)
            if ins is None:
                out = None
                break
            out[a] = ins
            a = ins.next
        if out and a == site:
            return out
    return {}


def _writers(win, site, base, width, depth=40):
    """Where a register gets its value at `site`, from a backward search over the
    local control-flow graph (fall-through and jumps inside the window). Returns a
    list of (value, writer address): value is an int (an immediate load),
    'computed' (memory, arithmetic, or a call that clobbers it) or '?' (no write
    found on some path; writer None)."""
    preds = defaultdict(list)
    for a, ins in win.items():
        if not (ins.kind in ('jump', 'ret', 'reti', 'ijump') and ins.cond in (None, 8)):
            preds[ins.next].append(ins)
        if (ins.kind in ('jump', 'branch') and ins.target is not None
                and (ins.target in win or ins.target == site)):
            preds[ins.target].append(ins)
    found, seen = [], set()
    stack = [(site, 0)]
    while stack:
        a, d = stack.pop()
        if a in seen:
            continue
        seen.add(a)
        ps = preds.get(a)
        if not ps or d >= depth:
            found.append(('?', None))
            continue
        for ins in ps:
            if ins.kind == 'call' and ins.next == a:
                found.append(('computed', ins.addr))       # registers clobbered by the call
            elif _writes(ins, base):
                v = _imm_of(ins, base)
                found.append(('computed' if v is None else v & ((1 << width) - 1), ins.addr))
            else:
                stack.append((ins.addr, d + 1))
    return list(dict.fromkeys(found))


def _values(writers):
    """Sorted distinct values of _writers(): ints first, then 'computed' / '?'."""
    vals = {v for v, _ in writers}
    return sorted(v for v in vals if isinstance(v, int)) + sorted(v for v in vals if not isinstance(v, int))


def _trace(win, site, base, width):
    """Values a register can hold at `site` (see _writers)."""
    return _values(_writers(win, site, base, width))


def _along(win, start, site, base, width):
    """Value of a register at `site` on the path that runs through instruction
    `start`: the first write after `start` on the straight path to the site (jumps
    followed), else its value before `start`."""
    a, steps = win[start].next, 0
    while a != site and steps < 64:
        ins = win.get(a)
        if ins is None:
            break
        if ins.kind == 'call':
            return 'computed'
        if _writes(ins, base):
            v = _imm_of(ins, base)
            return 'computed' if v is None else v & ((1 << width) - 1)
        a = ins.target if ins.kind == 'jump' and ins.cond in (None, 8) else ins.next
        steps += 1
    return _single(_trace(win, start, base, width))


def native_call_sites(rom):
    """[(site, routine)] of calls and jumps to the copy routines (byte scan + decode)."""
    sites = []
    data = rom.data
    for off in range(len(data) - 5):
        b = data[off]
        a = ROM_BASE + off
        if b in (0x1B, 0x1D, 0xF2):
            t = data[off + 1] | data[off + 2] << 8 | data[off + 3] << 16
            if t not in ROUTINES:
                continue
        elif b in (0x1E,) or 0x60 <= b <= 0x7F:
            if not (0x1F8000 <= a < 0x208C00):
                continue
        else:
            continue
        ins = _decode(rom, a)
        if ins is not None and ins.kind in ('call', 'jump', 'branch') and ins.target in ROUTINES:
            sites.append((a, ins.target))
    return sites


def _single(values):
    """One int when the search found exactly one value, else a short description."""
    ints = [v for v in values if isinstance(v, int)]
    if len(ints) == 1 and len(values) == 1:
        return ints[0]
    if ints:
        tail = ' or computed' if len(ints) < len(values) else ''
        return 'one of ' + ','.join('%X' % v for v in ints) + tail
    return values[0] if values else '?'


def native_ops(rom, w):
    """One op per call site and per immediate source value found for it; dest and
    size are taken on the path of that source's load."""
    ops = []
    for site, routine in native_call_sites(rom):
        kind = ROUTINES[routine][0]
        win = _window(rom, site, w.native)
        xiy = _writers(win, site, _XIY, 24)
        paths = [(v, wa) for v, wa in xiy if isinstance(v, int)]
        if paths:
            found = [(v, _along(win, wa, site, _XIX, 16), _along(win, wa, site, _XBC, 16)) for v, wa in paths]
        else:
            found = [(_single(_values(xiy)), _single(_trace(win, site, _XIX, 16)),
                      _single(_trace(win, site, _XBC, 16)))]
        for src, dest, bc in dict.fromkeys(found):
            if kind == 'palette' and isinstance(bc, int):
                bc = (bc & 0xFF) + 1
            ops.append(Op('map' if kind == 'map' else kind, site, src, dest, bc, 'native:%06X' % routine))
    return ops


# ---------------------------------------------------------------------------
# Table-driven loaders: the source is computed at run time from a table, so the
# native scan above reports 'computed'. Each table was found by reading the
# loader; this enumerates its entries. (site of the copy, name, enumerator)
# ---------------------------------------------------------------------------

RUN = 'run time'


def _tables(rom):
    """Yield (kind, site, src, dest, count, name) for every table-driven load."""
    # Menu icons: icon bar builder 0x2171B4, copy at 0x217206; 57 icons of 4 tiles.
    yield 'tiles', 0x217206, 0x2172D2, RUN, 57 * 0x20, 'menu-icons'
    # Menu labels (round-1 target): label task 0x217271; 45 labels of 8 tiles.
    yield 'tiles', 0x21729B, 0x218112, RUN, 45 * 0x40, 'menu-labels'
    # Map unit icons: 0x20703E / 0x209D4F / 0x20D7AF copy 0x201FC6 + 64 * id, where id
    # is byte 0 of the class record at 0x20DAF4 + 16 * class (ids 1-54; id 0 is unused).
    yield 'tiles', 0x20D7AF, 0x201FC6 + 64, RUN, 54 * 0x20, 'map-unit-icons'
    # Result banners: 0x2086AB picks one of three sources (23 tiles to 0xAA50).
    for src in (0x20C7CA, 0x20C93A, 0x20CAAA):
        yield 'tiles', 0x2086AB, src, 0xAA50, 0xB8, 'result-banners'
    # Intro narration lines (round-1 target): table 0x28D1EA, 7-byte records
    # [u16 trigger][u16 dest][u24 src], 0x120 words each, end mark 0xFFFF.
    a = 0x28D1EA
    while rom.read16(a) != 0xFFFF and a < 0x28D260:
        yield 'tiles', 0x28D128, rom.read24(a + 4), rom.read16(a + 2), 0x120, 'intro-lines'
        a += 7
    # Chapter card sheets (round-1 target): 0x29ECFE copies 0xB40 words of one set.
    for src in (0x29F34A, 0x2A09CA):
        yield 'tiles', 0x29ECFE, src, 0xA440, 0xB40, 'card-sheets'
    # Tarot cards: 0x219820 reads 16-byte records at 0x219918 + 16 * card (cards
    # 1-22): +0 tiles (0x1F0 words), +3 palette (offset +6, count +7), +8 tiles
    # (0x1B8 words), +0xB palette (offset +0xE, count +0xF).
    for card in range(1, 23):
        r = 0x219918 + 16 * card
        yield 'tiles', 0x21983D, rom.read24(r), RUN, 0x1F0, 'tarot-cards'
        yield 'tiles', 0x21986D, rom.read24(r + 8), RUN, 0x1B8, 'tarot-cards'
    # Ending text: 0x2A30CB picks [u8 lines][u24 first line] at 0x2A3058 + 4 * ending
    # (RAM 0x45CC, endings 0-4); 0x2A34A0 copies 0x100 words per line. Listed in
    # chunks of at most 16 lines (0x1000 words).
    for e in range(5):
        n, src = rom.read8(0x2A3058 + 4 * e), rom.read24(0x2A3059 + 4 * e)
        for k in range(0, n, 16):
            yield 'tiles', 0x2A34A0, src + 0x200 * k, RUN, 0x100 * min(16, n - k), 'ending-text-%d' % (e + 1)
    # Battle backgrounds: 0x2C5FFE indexes the pointer tables 0x2CDDCC (normal) and
    # 0x2CDE6C (link), 40 entries each (20 terrains, day then night). A record holds
    # two layers of [u32 map][u16 dest][u32 palette][u16 dest][u8 count-1]
    # [u32 tiles][u16 dest][u16 words].
    seen = set()
    for table in (0x2CDDCC, 0x2CDE6C):
        for i in range(40):
            rec = rom.read24(table + 4 * i)
            if rec in seen:
                continue
            seen.add(rec)
            for part in range(2):
                p = rec + 21 * part
                name = 'battle-backgrounds'
                yield 'map', 0x2C602C, rom.read24(p), rom.read16(p + 4), None, name
                yield 'palette', 0x2C603B, rom.read24(p + 6), rom.read16(p + 10), rom.read8(p + 12) + 1, name
                yield 'tiles', 0x2C604A, rom.read24(p + 13), rom.read16(p + 17), rom.read16(p + 19), name
    # Scenario map popup icons: 0x29C1F9 copies 0x140 words from list (0x6800),
    # which the scripts set to 0x29C121 or 0x29C083 (+3 tiles, +6 dest).
    for lst in (0x29C083, 0x29C121):
        yield 'tiles', 0x29C1F9, rom.read24(lst + 3), rom.read16(lst + 6), 0x140, 'popup-icons'


def table_ops(rom):
    ops = []
    for kind, site, src, dest, count, name in _tables(rom):
        ops.append(Op(kind, site, src, dest, count, 'table:' + name))
    return ops


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

RUNTIME_DEST = 'dest set at run time'


def _rom_src(v):
    return isinstance(v, int) and ROM_LO <= v < ROM_HI


def check(rom, o):
    """Set o.ok / o.why according to the filters of the module docstring."""
    if isinstance(o.src, int) and o.src < 0x10000:
        o.why = 'dynamic (RAM source)'
        return
    if not _rom_src(o.src):
        o.why = 'source not in ROM below 0x36746D' if isinstance(o.src, int) else 'source not an immediate'
        return
    # A native loader whose dest comes from memory (a task's tile field, a table) is
    # kept when source and size are known: 'dest set at run time'.
    runtime_dest = o.via.startswith(('native', 'table')) and not isinstance(o.dest, int)
    if o.kind == 'tiles':
        if not isinstance(o.count, int) or not (0 < o.count <= MAX_WORDS):
            o.why = 'size not 1-0x1000 words'
        elif runtime_dest:
            o.ok, o.why = True, RUNTIME_DEST
        elif not (TILE_LO <= o.dest < TILE_HI):
            o.why = 'dest not in 0xA000-0xBFFF'
        elif o.dest + 2 * o.count > TILE_HI:
            o.why = 'copy runs past 0xBFFF'
        else:
            o.ok = True
    elif o.kind == 'map':
        if o.via == 'native:2009F4':
            o.why = 'map rows (size preset): listed only'
            return
        o.w, o.h = rom.read8(o.src), rom.read8(o.src + 1)
        o.count = o.w * o.h
        if not (1 <= o.w <= 32 and 1 <= o.h <= 32):
            o.why = 'header not 1-32 x 1-32'
        elif runtime_dest:
            o.ok, o.why = True, RUNTIME_DEST
        elif not (MAP_LO <= o.dest < MAP_HI):
            o.why = 'dest not in 0x9000-0x9FFF'
        else:
            o.ok = True
    elif o.kind == 'palette':
        if not isinstance(o.count, int) or not (0 < o.count <= 0x100):
            o.why = 'size not 1-0x100 words'
        elif runtime_dest:
            o.ok, o.why = True, RUNTIME_DEST
        elif not (PAL_LO <= o.dest < PAL_HI):
            o.why = 'dest not in 0x8200-0x83FF'
        else:
            o.ok = True
    elif o.kind == 'anim':
        n = rom.read8(o.src)
        o.count = n
        if not 1 <= n <= 64:
            o.why = 'not a sprite list (count %d)' % n
        elif not _rom_src(o.src + 5 * n):
            o.why = 'list runs out of ROM'
        else:
            o.ok = True


# ---------------------------------------------------------------------------
# Blocks and classes
# ---------------------------------------------------------------------------

def known_target(lo, hi):
    for name, ranges in KNOWN_TARGETS.items():
        for a, b in ranges:
            if lo < b and a < hi:
                return name
    return None


def classify(src):
    for lo, hi, cls, desc in CLASSES:
        if lo <= src < hi:
            return cls, desc
    return 'unclassified', ''


def tile_blocks(ops):
    """Distinct tile blocks: src -> {'words': max, 'users': [op]}."""
    blocks = {}
    for o in ops:
        if o.kind == 'tiles' and o.ok:
            b = blocks.setdefault(o.src, {'words': 0, 'users': []})
            b['words'] = max(b['words'], o.count)
            b['users'].append(o)
    return blocks


# ---------------------------------------------------------------------------
# Rendering (local only)
# ---------------------------------------------------------------------------

GREY = [(255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)]
GAP = (255, 0, 255)

# 3x5 hex digits for labelling contact sheets (drawn for this tool)
_DIGITS = {
    '0': '###,#.#,#.#,#.#,###', '1': '.#.,##.,.#.,.#.,###', '2': '###,..#,###,#..,###',
    '3': '###,..#,.##,..#,###', '4': '#.#,#.#,###,..#,..#', '5': '###,#..,###,..#,###',
    '6': '###,#..,###,#.#,###', '7': '###,..#,..#,.#.,.#.', '8': '###,#.#,###,#.#,###',
    '9': '###,#.#,###,..#,###', 'A': '.#.,#.#,###,#.#,#.#', 'B': '##.,#.#,##.,#.#,##.',
    'C': '###,#..,#..,#..,###', 'D': '##.,#.#,#.#,#.#,##.', 'E': '###,#..,###,#..,###',
    'F': '###,#..,###,#..,#..', ' ': '...,...,...,...,...', '-': '...,...,###,...,...',
    'x': '...,#.#,.#.,#.#,...', 'J': '..#,..#,..#,#.#,.#.', 'N': '#.#,###,###,###,#.#',
    'K': '#.#,##.,#..,##.,#.#', 'U': '#.#,#.#,#.#,#.#,###', '?': '###,..#,.##,...,.#.',
    'L': '#..,#..,#..,#..,###',
}


def _text(img, x, y, s, colour=(0, 0, 160)):
    for ch in s:
        rows = _DIGITS.get(ch, _DIGITS['?']).split(',')
        for dy, r in enumerate(rows):
            for dx, c in enumerate(r):
                if c == '#' and 0 <= y + dy < len(img) and 0 <= x + dx < len(img[0]):
                    img[y + dy][x + dx] = colour
        x += 4


def _canvas(w, h, colour=GAP):
    return [[colour] * w for _ in range(h)]


def _blit_tile(img, data, off, x0, y0, pal=GREY, hflip=False, vflip=False):
    t = decode_tile_2bpp(data, off)
    for y in range(8):
        sy = 7 - y if vflip else y
        for x in range(8):
            sx = 7 - x if hflip else x
            img[y0 + y][x0 + x] = pal[t[sy][sx]]


def render_sheet(rom, src, words, path, cols=16, scale=2):
    n = max(1, (2 * words) // 16)
    data = rom.bytes(src, n * 16)
    rows = (n + cols - 1) // cols
    img = _canvas(cols * 8, rows * 8)
    for t in range(n):
        _blit_tile(img, data, 16 * t, (t % cols) * 8, (t // cols) * 8)
    png.write_rgb(path, cols * 8, rows * 8, img, scale)


def contact_sheets(rom, blocks, outdir, cols=32, max_h=720):
    """All blocks in address order, each under a label with its address and class."""
    os.makedirs(outdir, exist_ok=True)
    width = cols * 8
    pages, page, h = [], [], 0
    for src in sorted(blocks):
        n = max(1, (2 * blocks[src]['words']) // 16)
        bh = 8 + ((n + cols - 1) // cols) * 8 + 2
        if page and h + bh > max_h:
            pages.append(page)
            page, h = [], 0
        page.append((src, n, bh))
        h += bh
    if page:
        pages.append(page)
    names = []
    for k, page in enumerate(pages):
        height = sum(bh for _, _, bh in page)
        img = _canvas(width, height, (255, 255, 224))
        y = 0
        for src, n, bh in page:
            cls = classify(src)[0]
            tag = {'japanese': 'JA', 'english': 'EN', 'none': '-', 'unclear': '?',
                   'known': 'KN'}.get(cls, 'U')
            _text(img, 1, y + 1, '%06X %X %s' % (src, n, tag))
            data = rom.bytes(src, n * 16)
            for t in range(n):
                _blit_tile(img, data, 16 * t, (t % cols) * 8, y + 8 + (t // cols) * 8)
            y += bh
        name = os.path.join(outdir, 'sheet_%02d.png' % k)
        png.write_rgb(name, width, height, img, 2)
        names.append((name, page[0][0], page[-1][0]))
    return names


def _colour(word):
    r, g, b = word & 15, (word >> 4) & 15, (word >> 8) & 15
    return (r * 17, g * 17, b * 17)


def scene_for(mop, ops, by_run, near=0x8000):
    """Tile and palette ops to draw map op `mop` with: the ops of its own script run
    first, then (for tiles not loaded there) ops whose source lies within `near`
    bytes of the map's source, nearest first. A guess for native maps: the game
    usually stores a screen's tiles, maps and palettes together."""
    own = [o for o in by_run.get(mop.run, []) if o.ok] if mop.run is not None else []
    others = [o for o in ops if o.ok and o.kind in ('tiles', 'palette') and isinstance(o.dest, int)
              and abs(o.src - mop.src) < near and o not in own]
    others.sort(key=lambda o: abs(o.src - mop.src))
    return own + others


def _vram_of(rom, scene):
    vram = {}
    for o in scene:
        if o.kind == 'tiles' and isinstance(o.dest, int):
            data = rom.bytes(o.src, 2 * o.count)
            first = (o.dest - TILE_LO) // 16
            for t in range(len(data) // 16):
                vram.setdefault(first + t, (data, 16 * t))
    return vram


def render_sprites(rom, aop, scene, path, scale=2):
    """Draw sprite list `aop` (records [u16 tile/attr][dx][dy][palette]) with tile
    base aop.dest, using the tiles of `scene` (grey; magenta = tile not loaded)."""
    vram = _vram_of(rom, scene)
    n = rom.read8(aop.src)
    recs = []
    for i in range(n):
        r = rom.bytes(aop.src + 1 + 5 * i, 5)
        word = (aop.dest + (r[0] | r[1] << 8)) & 0xFFFF
        dx = r[2] - 256 if r[2] & 0x80 else r[2]
        dy = r[3] - 256 if r[3] & 0x80 else r[3]
        recs.append((word, dx, dy))
    x0 = min(dx for _, dx, _ in recs)
    y0 = min(dy for _, _, dy in recs)
    w = max(dx for _, dx, _ in recs) - x0 + 8
    h = max(dy for _, _, dy in recs) - y0 + 8
    img = _canvas(w, h, (255, 255, 224))
    for word, dx, dy in reversed(recs):          # lower-numbered sprites in front
        t = ((word >> 8) & 1) << 8 | (word & 0xFF)
        x, y = dx - x0, dy - y0
        if t in vram:
            data, off = vram[t]
            pal = [(255, 255, 224)] + GREY[1:]
            tile = decode_tile_2bpp(data, off)
            for yy in range(8):
                sy = 7 - yy if word & 0x4000 else yy
                for xx in range(8):
                    sx = 7 - xx if word & 0x8000 else xx
                    v = tile[sy][sx]
                    if v:
                        img[y + yy][x + xx] = pal[v]
        else:
            for yy in range(8):
                for xx in range(8):
                    if (xx + yy) % 4 == 0:
                        img[y + yy][x + xx] = (255, 0, 255)
    png.write_rgb(path, w, h, img, scale)


def render_map(rom, mop, scene, path, scale=2):
    """Draw map op `mop` with the tiles and palettes of `scene` (earlier ops win)."""
    vram = _vram_of(rom, scene)                  # tile number -> (data, offset)
    pals = {}                                    # palette word address -> colour word
    for o in scene:
        if o.kind == 'palette' and isinstance(o.dest, int) and o.via != 'gfx28':
            for i in range(o.count):
                pals.setdefault(o.dest + 2 * i, rom.read16(o.src + 2 * i))
    w, h = mop.w, mop.h
    base = 0x8280 if not isinstance(mop.dest, int) or mop.dest < 0x9800 else 0x8300
    img = _canvas(w * 8, h * 8)
    for r in range(h):
        for c in range(w):
            e = rom.read16(mop.src + 2 + 2 * (r * w + c))
            t, p = e & 0x1FF, (e >> 9) & 15
            x0, y0 = c * 8, r * 8
            if t in vram:
                words = [pals.get(base + 8 * p + 2 * i) for i in range(4)]
                pal = GREY if None in words[1:] else [(255, 255, 255)] + [_colour(v) for v in words[1:]]
                if t == 0 and None in words[1:]:
                    pal = GREY
                data, off = vram[t]
                _blit_tile(img, data, off, x0, y0, pal, bool(e & 0x8000), bool(e & 0x4000))
            else:
                for y in range(8):
                    for x in range(8):
                        img[y0 + y][x0 + x] = (255, 0, 255) if (x + y) % 4 == 0 else (255, 200, 255)
    png.write_rgb(path, w * 8, h * 8, img, scale)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def inventory(rom):
    w, stats = walk(rom)
    ops = script_ops(rom, w) + native_ops(rom, w) + table_ops(rom)
    tables = {o.site: o.via for o in ops if o.via.startswith('table')}
    for o in ops:
        check(rom, o)
        if o.via.startswith('native') and not o.ok and o.site in tables:
            o.why += ' (enumerated as %s)' % tables[o.site]
    return w, stats, ops


def counts(ops):
    """[(kind, op, before, after, of which dest set at run time, RAM sources)]"""
    out = []
    for kind in ('tiles', 'map', 'palette', 'anim'):
        for via in sorted({o.via for o in ops if o.kind == kind},
                          key=lambda v: (v.startswith('native') + 2 * v.startswith('table'), v)):
            sel = [o for o in ops if o.kind == kind and o.via == via]
            out.append((kind, via, len(sel), sum(o.ok for o in sel),
                        sum(1 for o in sel if o.ok and o.why == RUNTIME_DEST),
                        sum(1 for o in sel if o.why == 'dynamic (RAM source)')))
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(__doc__)
        return 2
    rom = Rom(argv[0])
    outdir = argv[1]
    want_png = '--no-png' not in argv
    os.makedirs(outdir, exist_ok=True)
    w, stats, ops = inventory(rom)
    print('scripts: walker %d entries / %d insns; extra seeds %d (%d new entries); '
          'total %d entries / %d insns' % (stats['walker_entries'], stats['walker_insns'], stats['seeds'],
                                           stats['new_entries'], stats['entries'], stats['insns']))
    print('%-8s %-26s %7s %7s %13s %11s' % ('kind', 'op', 'before', 'after', '(dest at run)', 'RAM source'))
    for kind, via, n, ok, rt, dyn in counts(ops):
        print('%-8s %-26s %7d %7d %13d %11d' % (kind, via, n, ok, rt, dyn))
    script_tiles = [o for o in ops if o.via in ('gfx2a', 'gfx2c')]
    base = [o for o in script_tiles if o.site in stats['walker_set']]
    print('script tile ops (gfx2a + gfx2c): %d before, %d after; distinct sources %d before, %d after' % (
        len(script_tiles), sum(o.ok for o in script_tiles), len({o.src for o in script_tiles}),
        len({o.src for o in script_tiles if o.ok})))
    print('  text walker alone: %d gfx2a, %d distinct gfx2a/gfx2c sources (before filtering)' % (
        sum(o.via == 'gfx2a' for o in base), len({o.src for o in base})))
    blocks = tile_blocks(ops)
    nbytes = sum(2 * b['words'] for b in blocks.values())
    print('distinct tile blocks (script, native and table loads, filtered): %d, %d bytes (%d tiles)' % (
        len(blocks), nbytes, nbytes // 16))
    with open(os.path.join(outdir, 'inventory.txt'), 'w') as f:
        f.write('# graphics ops: kind site op src dest size verdict\n')
        for o in sorted(ops, key=lambda o: (o.kind, o.site)):
            f.write('%s  %s\n' % (o.describe(), 'ok' if o.ok else 'filtered: ' + o.why))
    cls_count = defaultdict(int)
    known = defaultdict(list)
    japanese = []
    with open(os.path.join(outdir, 'blocks.txt'), 'w') as f:
        f.write('# src      bytes tiles  users (site>dest; * native, + table)  class  description\n')
        for src in sorted(blocks):
            b = blocks[src]
            size = 2 * b['words']
            kt = known_target(src, src + size)
            cls, desc = classify(src)
            if kt and cls == 'unclassified':
                cls, desc = 'known', 'round-1 target: %s' % kt
            if kt:
                known[kt].append(src)
            if cls == 'japanese':
                japanese.append(src)
            cls_count[cls] += 1
            users = ' '.join('%06X%s>%s' % (o.site, {'n': '*', 't': '+'}.get(o.via[0], ''),
                                            '%04X' % o.dest if isinstance(o.dest, int) else 'run')
                             for o in b['users'][:6])
            f.write('%06X %6d %5d  %-40s %-12s %s\n' % (src, size, size // 16, users, cls, desc))
    print('classes:', dict(sorted(cls_count.items())))
    print('round-1 targets (excluded): %s' % '; '.join(
        '%s %s' % (k, ' '.join('%06X' % s for s in v)) for k, v in sorted(known.items())))
    print('Japanese blocks outside them: %s' % ' '.join('%06X' % s for s in japanese))
    if want_png:
        tdir = os.path.join(outdir, 'tiles')
        mdir = os.path.join(outdir, 'maps')
        os.makedirs(tdir, exist_ok=True)
        os.makedirs(mdir, exist_ok=True)
        for src, b in blocks.items():
            render_sheet(rom, src, b['words'], os.path.join(tdir, 'T_%06X.png' % src))
        by_run = defaultdict(list)
        for o in ops:
            if o.run is not None:
                by_run[o.run].append(o)
        nmaps, done = 0, set()
        for o in ops:
            if o.kind == 'map' and o.ok and (o.src, o.run if o.run is not None else o.site) not in done:
                done.add((o.src, o.run if o.run is not None else o.site))
                render_map(rom, o, scene_for(o, ops, by_run),
                           os.path.join(mdir, 'M_%06X_%06X.png' % (o.src, o.site)))
                nmaps += 1
        sdir = os.path.join(outdir, 'sprites')
        os.makedirs(sdir, exist_ok=True)
        nspr, done = 0, set()
        for o in ops:
            if o.kind == 'anim' and o.ok and isinstance(o.dest, int) and (o.src, o.dest) not in done:
                done.add((o.src, o.dest))
                render_sprites(rom, o, scene_for(o, ops, by_run),
                               os.path.join(sdir, 'S_%06X_%03X.png' % (o.src, o.dest)))
                nspr += 1
        sheets = contact_sheets(rom, blocks, os.path.join(outdir, 'contact'))
        print('wrote %d tile sheets, %d map renders, %d sprite lists, %d contact sheets in %s' % (
            len(blocks), nmaps, nspr, len(sheets), outdir))
    return 0


if __name__ == '__main__':
    sys.exit(main())
