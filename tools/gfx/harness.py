"""Run the headless harness and work with its outputs (screenshots, states).

    python -m tools.gfx.harness run [--exe EXE] ROM [harness options...]
    python -m tools.gfx.harness poke SRC.state DST.state ADDR=HEX [ADDR=HEX ...]
    python -m tools.gfx.harness diff A.png B.png [X0 Y0 X1 Y1 ...]
    python -m tools.gfx.harness sheet DIR [START STOP STEP] [--cols N] [--out FILE]

run    runs ngp_harness.exe: the executable is --exe, else the environment
       variable NGP_HARNESS, else build/ngp_harness.exe (for checks that
       must not be disturbed by rebuilds, use the stable snapshot:
       NGP_HARNESS=<scratchpad>/snap/ngp_harness.exe). The other options go
       to the harness unchanged (--frames N --out DIR --shot F,F --shot-every
       K --input "FRAME:BUTTONS:LEN;..." --load-state F --save-state F FILE
       --vram F,F --text-log FILE ...); the --out folder is created.
poke   copies a state file with bytes of the 64 KB low memory changed (RAM
       0x4000-0x6FFF at their own addresses): ADDR is hex, HEX the new bytes
       (5490=04 546E=20000000). A state is 'NGPSTAT1', the CPU state, then
       the low-memory image at byte 192; the tool checks the magic and the
       minimum size (66,399 bytes; states that carry flash blocks are
       longer) and stops if the format changed.
diff   counts the screen pixels (160x152) that differ between two harness
       screenshots, outside the given rectangles (screen coordinates, both
       ends inclusive: 0 56 159 103 masks rows 56-103). Prints the count and
       the box around the differences; exit status 1 when any pixel differs.
sheet  contact sheet of DIR/frame_NNNNN.png (all, or START <= N < STOP in
       steps of STEP), at 1x with the frame number under each picture;
       writes DIR/sheet.png unless --out is given.

From Python: run(rom, out, frames=..., shots=..., vram=..., inputs=..., load_state=...),
poke(src, dst, {addr: bytes}), state_ram(path), diff_png(a, b, rects),
contact_sheet(dir, frames, out, cols).
"""
import argparse
import os
import subprocess
import sys

from ..common import png

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
STATE_MAGIC = b'NGPSTAT1'
STATE_SIZE = 66399
STATE_RAM = 192                 # offset of the 64 KB low-memory image in a state file
SCREEN_W, SCREEN_H = 160, 152


class HarnessError(Exception):
    pass


def find_exe(exe=None):
    """--exe, else NGP_HARNESS, else build/ngp_harness.exe."""
    path = exe or os.environ.get('NGP_HARNESS') or os.path.join(ROOT, 'build', 'ngp_harness.exe')
    if not os.path.isfile(path):
        raise HarnessError('harness %s not found (give --exe or set NGP_HARNESS)' % path)
    return path


def _frames(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple, range)):
        return ','.join(str(int(v)) for v in value)
    return str(value)


def _inputs(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return ';'.join('%d:%s:%d' % tuple(v) if not isinstance(v, str) else v for v in value)
    return str(value)


class RunResult:
    def __init__(self, cmd, returncode, stdout, stderr, out):
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.out = out

    def path(self, kind, frame):
        """out/frame_NNNNN.png (kind 'frame') or out/mem_NNNNN.bin (kind 'mem')."""
        return os.path.join(self.out, '%s_%05d.%s' % (kind, frame, 'png' if kind == 'frame' else 'bin'))


def run(rom, out=None, frames=None, shots=None, shot_every=None, inputs=None, load_state=None, save_state=None,
        vram=None, text_log=None, extra=(), exe=None, timeout=3600, check=True):
    """Run the harness. shots/vram: frame numbers (list or 'F,F'); inputs: the
    --input string or [(frame, buttons, length)]; save_state: (frame, path).
    Returns a RunResult; raises HarnessError on a non-zero exit when check."""
    cmd = [find_exe(exe), rom]
    if frames is not None:
        cmd += ['--frames', str(frames)]
    if out is not None:
        os.makedirs(out, exist_ok=True)
        cmd += ['--out', out]
    for opt, value in (('--shot', _frames(shots)), ('--shot-every', shot_every), ('--input', _inputs(inputs)),
                       ('--load-state', load_state), ('--vram', _frames(vram)), ('--text-log', text_log)):
        if value is not None:
            cmd += [opt, str(value)]
    if save_state is not None:
        cmd += ['--save-state', str(save_state[0]), save_state[1]]
    cmd += list(extra)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    result = RunResult(cmd, p.returncode, p.stdout, p.stderr, out)
    if check and p.returncode != 0:
        raise HarnessError('harness failed (exit %d): %s\n%s' % (p.returncode, ' '.join(cmd), p.stderr.strip()))
    return result


# ---------------------------------------------------------------------------
# States

def _read_state(path):
    with open(path, 'rb') as f:
        st = f.read()
    if st[:8] != STATE_MAGIC:
        raise HarnessError('%s is not a harness state (no %s magic)' % (path, STATE_MAGIC.decode()))
    # A state is at least STATE_SIZE bytes; states that carry flash blocks
    # (after the game saved, or with --save) append them after the core state.
    if len(st) < STATE_SIZE:
        raise HarnessError('%s has %d bytes, fewer than %d: the state format changed, check the RAM '
                           'offset (%d) in tools/gfx/harness.py' % (path, len(st), STATE_SIZE, STATE_RAM))
    return bytearray(st)


def state_ram(path):
    """The 64 KB low-memory image of a state file (index = address)."""
    return bytes(_read_state(path)[STATE_RAM:STATE_RAM + 0x10000])


def poke(src, dst, changes):
    """Copy state src to dst with low-memory bytes changed: changes {addr: bytes}."""
    st = _read_state(src)
    for addr, data in sorted(changes.items()):
        data = bytes(data)
        if addr < 0 or addr + len(data) > 0x10000:
            raise HarnessError('poke %04X+%d is outside the 64 KB low memory' % (addr, len(data)))
        st[STATE_RAM + addr:STATE_RAM + addr + len(data)] = data
    with open(dst, 'wb') as f:
        f.write(st)


def parse_pokes(items):
    changes = {}
    for item in items:
        addr, sep, value = item.partition('=')
        if not sep:
            raise HarnessError('expected ADDR=HEX, got %r' % item)
        try:
            changes[int(addr, 16)] = bytes.fromhex(value)
        except ValueError:
            raise HarnessError('expected ADDR=HEX with hex digits, got %r' % item)
    return changes


# ---------------------------------------------------------------------------
# Screenshots

def read_screen(path):
    """(scale, rows of (r, g, b)) of a harness screenshot (160x152 at any integer scale)."""
    w, h, rows, pal = png.read(path)
    scale = w // SCREEN_W
    if scale < 1 or w != SCREEN_W * scale or h != SCREEN_H * scale:
        raise HarnessError('%s is %dx%d, not a 160x152 screenshot at an integer scale' % (path, w, h))
    if pal is not None and rows and not isinstance(rows[0][0], tuple):
        rows = [[pal[v] for v in r] for r in rows]
    return scale, [[p[:3] for p in r] for r in rows]


def diff_png(a, b, rects=()):
    """(count, box) of the screen pixels that differ between screenshots a and b
    outside rects [(x0, y0, x1, y1)] (inclusive, screen coordinates). A screen
    pixel differs when any of its scaled pixels does. box = (x0, y0, x1, y1) or None."""
    sa, ra = read_screen(a)
    sb, rb = read_screen(b)
    count, box = 0, None
    for y in range(SCREEN_H):
        for x in range(SCREEN_W):
            if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rects):
                continue
            same = all(ra[y * sa + j][x * sa + i] == rb[y * sb + (j * sb) // sa][x * sb + (i * sb) // sa]
                       for j in range(sa) for i in range(sa))
            if not same:
                count += 1
                box = (x, y, x, y) if box is None else (min(box[0], x), min(box[1], y), max(box[2], x),
                                                        max(box[3], y))
    return count, box


# 3x5 digits for the frame numbers of contact sheets
_DIGITS = ('111101101101111', '010110010010111', '111001111100111', '111001111001111', '101101111001001',
           '111100111001111', '111100111101111', '111001001001001', '111101111101111', '111101111001111')


def _draw_number(img, x0, y0, n, colour=(255, 255, 255)):
    for k, ch in enumerate(str(n)):
        bits = _DIGITS[int(ch)]
        for i, bit in enumerate(bits):
            if bit == '1':
                img[y0 + i // 3][x0 + 4 * k + i % 3] = colour


def contact_sheet(folder, frames=None, out=None, cols=8):
    """Contact sheet of folder/frame_NNNNN.png at 1x. frames: numbers (default:
    every frame file in the folder). Returns (path, frames used)."""
    if frames is None:
        frames = sorted(int(f[6:11]) for f in os.listdir(folder)
                        if f.startswith('frame_') and f.endswith('.png') and f[6:11].isdigit())
    frames = [f for f in frames if os.path.isfile(os.path.join(folder, 'frame_%05d.png' % f))]
    if not frames:
        raise HarnessError('no frame_NNNNN.png in %s' % folder)
    cols = max(1, min(cols, len(frames)))
    cw, ch = SCREEN_W + 2, SCREEN_H + 9
    nrows = (len(frames) + cols - 1) // cols
    img = [[(40, 40, 40)] * (cw * cols) for _ in range(ch * nrows)]
    for idx, f in enumerate(frames):
        scale, rows = read_screen(os.path.join(folder, 'frame_%05d.png' % f))
        ox, oy = (idx % cols) * cw + 1, (idx // cols) * ch + 1
        for y in range(SCREEN_H):
            src = rows[y * scale]
            dst = img[oy + y]
            for x in range(SCREEN_W):
                dst[ox + x] = src[x * scale]
        _draw_number(img, ox, oy + SCREEN_H + 2, f)
    out = out or os.path.join(folder, 'sheet.png')
    png.write_rgb(out, cw * cols, ch * nrows, img, 1)
    return out, frames


# ---------------------------------------------------------------------------

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == 'run':
            ap = argparse.ArgumentParser(prog='python -m tools.gfx.harness run')
            ap.add_argument('--exe')
            ap.add_argument('rom')
            args, extra = ap.parse_known_args(rest)
            if '--out' in extra:
                i = extra.index('--out')
                if i + 1 < len(extra):
                    os.makedirs(extra[i + 1], exist_ok=True)
            r = run(args.rom, extra=extra, exe=args.exe, check=False)
            sys.stdout.write(r.stdout)
            sys.stderr.write(r.stderr)
            return r.returncode
        if cmd == 'poke':
            if len(rest) < 3:
                raise HarnessError('usage: poke SRC.state DST.state ADDR=HEX [...]')
            changes = parse_pokes(rest[2:])
            poke(rest[0], rest[1], changes)
            print('wrote %s (%s)' % (rest[1], ', '.join('%04X=%s' % (a, d.hex().upper())
                                                         for a, d in sorted(changes.items()))))
            return 0
        if cmd == 'diff':
            if len(rest) < 2 or (len(rest) - 2) % 4:
                raise HarnessError('usage: diff A.png B.png [X0 Y0 X1 Y1 ...]')
            nums = [int(v) for v in rest[2:]]
            rects = [tuple(nums[i:i + 4]) for i in range(0, len(nums), 4)]
            count, box = diff_png(rest[0], rest[1], rects)
            print('%d differing pixels outside the masks%s' % (
                count, ' (within x %d-%d, y %d-%d)' % (box[0], box[2], box[1], box[3]) if box else ''))
            return 1 if count else 0
        if cmd == 'sheet':
            ap = argparse.ArgumentParser(prog='python -m tools.gfx.harness sheet')
            ap.add_argument('dir')
            ap.add_argument('range', nargs='*', type=int, metavar='START STOP STEP')
            ap.add_argument('--cols', type=int, default=8)
            ap.add_argument('--out')
            args = ap.parse_args(rest)
            frames = None
            if args.range:
                if len(args.range) != 3:
                    raise HarnessError('give START STOP STEP, or nothing for every frame')
                frames = list(range(*args.range))
            path, used = contact_sheet(args.dir, frames, args.out, args.cols)
            print('wrote %s: %d frames (%s)' % (path, len(used), ' '.join(str(f) for f in used)))
            return 0
    except HarnessError as e:
        print('error: %s' % e, file=sys.stderr)
        return 1
    print('unknown command %r (run, poke, diff, sheet)' % cmd, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
