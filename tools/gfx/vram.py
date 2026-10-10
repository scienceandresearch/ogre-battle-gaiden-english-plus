"""Look at harness --vram dumps and compare them with ROM data.

A dump (`ngp_harness ... --vram F,F,... --out DIR` -> DIR/mem_NNNNN.bin) is
the 64 KB low memory, file offset = address: RAM 0x4000-0x6FFF, K2GE
registers and VRAM 0x8000-0xBFFF (palettes 0x8200, sprites 0x8800, plane maps
0x9000 / 0x9800, tiles 0xA000).

    python -m tools.gfx.vram render MEM.bin PREFIX [--maps] [--sprites] [--scale N]
    python -m tools.gfx.vram bytes MEM.bin ROM VADDR ROMADDR LEN
    python -m tools.gfx.vram map MEM.bin ROM PLANEADDR ROMADDR W H [--stride N]
    python -m tools.gfx.vram find MEM.bin|DIR [...] ROM VADDR[,VADDR...] LEN ROMADDR COUNT [--stride S] [--hex]
    python -m tools.gfx.vram queue MEM.bin|DIR [...] [--rom ROM] [--dest VADDR] [--index BASE STRIDE]

Addresses and byte lengths are hex (0x optional); W, H, COUNT and N are
decimal. ROM addresses are CPU addresses (0x200000 is the first ROM byte). A
DIR stands for its mem_*.bin files.

render  prints the registers and the palettes in use (--maps: both plane maps
        as tile/palette/flips; --sprites: the visible sprites), and writes
        PREFIX_p1.png and PREFIX_p2.png (each plane alone: the visible
        160x152 window at its scroll position), PREFIX_spr.png (the sprites),
        PREFIX_screen.png (the composite, as the core draws it: background
        colour, sprites and planes by priority, the window colour outside
        the window) and PREFIX_tiles.png (the 512 tiles in grey, 32 per
        row). Transparent pixels are magenta; --scale (default 2) enlarges
        the images. The composite uses the registers at dump time, so effects
        that change them during a frame (raster scrolling) are not shown.
bytes   compares LEN bytes of VRAM at VADDR with the ROM at ROMADDR:
        'N of LEN bytes differ', then the first differing tile.
map     compares a W x H block of plane map entries (32 per row in VRAM,
        starting with the entry at PLANEADDR, e.g. 0x9000 + 2 * (32 * row +
        col)) with W x H little-endian words in the ROM at ROMADDR, in rows
        of --stride words (default W): 'N of W*H map entries differ'.
find    for each dump and each VADDR: which of COUNT ROM blocks (LEN bytes at
        ROMADDR + i * stride; default stride LEN) VRAM holds there. Prints
        the index (decimal, or hex with --hex), indices joined by '/' when
        several blocks are identical, '-' when VRAM is all zero there, '?'
        when no block matches.
queue   the VBlank copy queue: count at 0x400D, 8-byte entries [u16 words]
        [u16 dest][u32 src] from 0x400E. --dest keeps the entries for one
        destination; --index numbers the sources as records of STRIDE bytes
        from BASE (#NN, hex); --rom checks that VRAM at the destination holds
        the source's bytes ('ok' / 'differs').

Exit status: bytes and map return 1 when something differs.
"""
import argparse
import os
import sys

from ..common import png
from ..common.tiles import GRAY4, decode_tile_2bpp, tiles_to_rows
from ..recomp.rom import ROM_BASE

SIZE = 0x10000
MAGENTA = (255, 0, 255)
PLANE1, PLANE2 = 0x9000, 0x9800
PAL_SPR, PAL_P1, PAL_P2 = 0x00, 0x40, 0x80        # colour index bases (colour word at 0x8200 + 2 * index)
SCREEN_W, SCREEN_H = 160, 152
Z_SPR1, Z_BACK, Z_SPR2, Z_FRONT, Z_SPR3 = 1, 2, 3, 4, 5      # depths of runtime/src/core/k2ge.c
QUEUE_COUNT, QUEUE = 0x400D, 0x400E


class Sprite:
    __slots__ = ('n', 'tile', 'attr', 'x', 'y', 'prio', 'hflip', 'vflip', 'pal', 'raw')

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class Vram:
    """A --vram dump."""

    def __init__(self, data, name=''):
        if len(data) != SIZE:
            raise ValueError('%s: a --vram dump has %d bytes, not %d' % (name or 'dump', SIZE, len(data)))
        self.m = bytes(data)
        self.name = name
        self._tiles = {}

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as f:
            return cls(f.read(), os.path.basename(path))

    def u8(self, a):
        return self.m[a]

    def u16(self, a):
        return self.m[a] | (self.m[a + 1] << 8)

    def colour(self, index):
        """12-bit colour word 0x0BGR of colour index (sprites 0x00, plane 1 0x40,
        plane 2 0x80, background 0xF0, window 0xF8)."""
        return self.u16(0x8200 + 2 * index) & 0xFFF

    def rgb(self, index):
        c = self.colour(index)
        return ((c & 15) * 17, ((c >> 4) & 15) * 17, ((c >> 8) & 15) * 17)

    def tile(self, n):
        n &= 0x1FF
        t = self._tiles.get(n)
        if t is None:
            t = self._tiles[n] = decode_tile_2bpp(self.m, 0xA000 + 16 * n)
        return t

    def entry(self, plane, col, row):
        return self.u16(plane + 2 * ((row & 31) * 32 + (col & 31)))

    def registers(self):
        m = self.m
        return {'ctrl': m[0x8000], 'win': (m[0x8002], m[0x8003], m[0x8004], m[0x8005]), 'oowc': m[0x8012],
                'spr_ofs': (m[0x8020], m[0x8021]), 'prio': m[0x8030], 'scroll1': (m[0x8032], m[0x8033]),
                'scroll2': (m[0x8034], m[0x8035]), 'bg': m[0x8118]}

    def sprites(self):
        """All 64 sprites with their screen position (chaining and the sprite
        offset applied, as in the core)."""
        po_h, po_v = self.m[0x8020], self.m[0x8021]
        px = py = 0
        out = []
        for n in range(64):
            s = self.m[0x8800 + 4 * n:0x8800 + 4 * n + 4]
            attr, ox, oy = s[1], s[2], s[3]
            if attr & 4:
                ox = (ox + px) & 0xFF
            if attr & 2:
                oy = (oy + py) & 0xFF
            px, py = ox, oy
            out.append(Sprite(n=n, tile=s[0] | ((attr & 1) << 8), attr=attr, x=(ox + po_h) & 0xFF,
                              y=(oy + po_v) & 0xFF, prio=(attr >> 3) & 3, hflip=bool(attr & 0x80),
                              vflip=bool(attr & 0x40), pal=self.m[0x8C00 + n] & 15, raw=bytes(s)))
        return out

    # -- images: rows of (r, g, b) or None (transparent)

    def _plane_pixel(self, plane, xx, yy):
        e = self.u16(plane + (yy >> 3) * 64 + (xx >> 3) * 2)
        col, row = xx & 7, yy & 7
        if e & 0x8000:
            col ^= 7
        if e & 0x4000:
            row ^= 7
        return e, self.tile(e & 0x1FF)[row][col]

    def plane_image(self, which, full=False):
        """Plane 1 or 2 alone: the visible window (or the whole 256x256 plane)."""
        plane, pal = (PLANE1, PAL_P1) if which == 1 else (PLANE2, PAL_P2)
        sx, sy = (0, 0) if full else ((self.m[0x8032], self.m[0x8033]) if which == 1 else
                                      (self.m[0x8034], self.m[0x8035]))
        w, h = (256, 256) if full else (SCREEN_W, SCREEN_H)
        rows = []
        for y in range(h):
            yy = (y + sy) & 0xFF
            row = []
            for x in range(w):
                e, v = self._plane_pixel(plane, (x + sx) & 0xFF, yy)
                row.append(self.rgb(pal + ((e >> 9) & 15) * 4 + v) if v else None)
            rows.append(row)
        return rows

    def _sprite_line(self, line, zb, y, sprites, depth_test=True):
        for s in sprites:
            if not s.prio:
                continue
            row = (y - s.y) & 0xFF
            if row >= 8:
                continue
            if s.vflip:
                row ^= 7
            t = self.tile(s.tile)
            depth = (Z_SPR1, Z_SPR2, Z_SPR3)[s.prio - 1]
            for c in range(8):
                x = (s.x + c) & 0xFF
                if x >= SCREEN_W:
                    continue
                v = t[row][7 - c if s.hflip else c]
                if not v or (depth_test and zb[x] >= depth):
                    continue
                zb[x] = depth
                line[x] = self.rgb(PAL_SPR + s.pal * 4 + v)

    def sprite_image(self):
        sprites = self.sprites()
        rows = []
        for y in range(SCREEN_H):
            line, zb = [None] * SCREEN_W, [0] * SCREEN_W
            self._sprite_line(line, zb, y, sprites)
            rows.append(line)
        return rows

    def screen(self):
        """The composite picture, following k2ge_render_line."""
        m = self.m
        bg = (0, 0, 0) if m[0x8118] & 0x40 else self.rgb(0xF0 + (m[0x8118] & 7))
        wc = self.rgb(0xF8 + (m[0x8012] & 7))
        wx, wy, ww, wh = m[0x8002], m[0x8003], m[0x8004], m[0x8005]
        if m[0x8030] & 0x80:
            order = ((PLANE1, PAL_P1, 0x8032, Z_BACK), (PLANE2, PAL_P2, 0x8034, Z_FRONT))
        else:
            order = ((PLANE2, PAL_P2, 0x8034, Z_BACK), (PLANE1, PAL_P1, 0x8032, Z_FRONT))
        sprites = self.sprites()
        rows = []
        for y in range(SCREEN_H):
            line, zb = [bg] * SCREEN_W, [0] * SCREEN_W
            self._sprite_line(line, zb, y, sprites)
            for plane, pal, sreg, depth in order:
                sx, sy = m[sreg], m[sreg + 1]
                yy = (y + sy) & 0xFF
                for x in range(SCREEN_W):
                    e, v = self._plane_pixel(plane, (x + sx) & 0xFF, yy)
                    if not v or zb[x] >= depth:
                        continue
                    zb[x] = depth
                    line[x] = self.rgb(pal + ((e >> 9) & 15) * 4 + v)
            in_y = wy <= y < wy + wh
            for x in range(SCREEN_W):
                if not in_y or x < wx or x >= wx + ww:
                    line[x] = wc
            rows.append(line)
        return rows

    def tile_sheet(self):
        """(w, h, rows): the 512 tiles in grey, 32 per row."""
        return tiles_to_rows([self.tile(n) for n in range(512)], 32, GRAY4)

    def queue(self):
        """The VBlank copy queue: [(words, dest, src)]."""
        out = []
        for i in range(self.m[QUEUE_COUNT]):
            a = QUEUE + 8 * i
            if a + 8 > SIZE:
                break
            out.append((self.u16(a), self.u16(a + 2), int.from_bytes(self.m[a + 4:a + 8], 'little')))
        return out


# ---------------------------------------------------------------------------
# Comparisons

def rom_bytes(rom, addr, n, what='ROM'):
    off = addr - ROM_BASE
    if off < 0 or off + n > len(rom):
        raise ValueError('%s %06X+%X is outside the ROM' % (what, addr, n))
    return rom[off:off + n]


def compare_bytes(mem, rom, vaddr, romaddr, n):
    """Offsets (from vaddr) where VRAM and the ROM differ."""
    a = mem.m[vaddr:vaddr + n]
    if len(a) != n:
        raise ValueError('VRAM %04X+%X is outside the dump' % (vaddr, n))
    b = rom_bytes(rom, romaddr, n)
    return [i for i in range(n) if a[i] != b[i]]


def compare_map(mem, rom, planeaddr, romaddr, w, h, stride=None):
    """[(row, col, vram entry, rom entry)] for the differing entries."""
    stride = w if stride is None else stride
    out = []
    for r in range(h):
        for c in range(w):
            va = planeaddr + 2 * (32 * r + c)
            ra = romaddr + 2 * (stride * r + c)
            e_rom = int.from_bytes(rom_bytes(rom, ra, 2), 'little')
            e_mem = mem.u16(va)
            if e_rom != e_mem:
                out.append((r, c, e_mem, e_rom))
    return out


def find_blocks(mem, rom, vaddr, n, romaddr, count, stride=None):
    """Indices i of the ROM blocks (n bytes at romaddr + i * stride) that VRAM
    holds at vaddr; None when VRAM is all zero there and no block is zero."""
    stride = n if stride is None else stride
    blob = mem.m[vaddr:vaddr + n]
    hits = [i for i in range(count) if rom_bytes(rom, romaddr + i * stride, n) == blob]
    if not hits and not any(blob):
        return None
    return hits


def dumps(paths):
    """Expand directories to their mem_*.bin files (sorted)."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.startswith('mem_') and f.endswith('.bin')]
        else:
            out.append(p)
    if not out:
        raise SystemExit('no dumps (mem_*.bin) in %s' % ' '.join(paths))
    return out


# ---------------------------------------------------------------------------
# Printing

def _pal_lines(mem):
    out = []
    for title, base in (('sprites', PAL_SPR), ('plane 1', PAL_P1), ('plane 2', PAL_P2)):
        used = []
        for p in range(16):
            cs = [mem.colour(base + 4 * p + i) for i in range(4)]
            if any(cs):
                used.append('%X:%s' % (p, ' '.join('%03X' % c for c in cs)))
        out.append('pal %-8s %s' % (title, ' | '.join(used) or '-'))
    out.append('pal bg (83E0) %s   window (83F0) %s' % (' '.join('%03X' % mem.colour(0xF0 + i) for i in range(8)),
                                                       ' '.join('%03X' % mem.colour(0xF8 + i) for i in range(8))))
    return out


def describe(mem):
    r = mem.registers()
    lines = ['regs: 8000=%02X window=%d,%d %dx%d 8012=%02X sprite offset=%d,%d 8030=%02X (plane %d in front) '
             'scroll1=%d,%d scroll2=%d,%d 8118=%02X' % (
                 r['ctrl'], *r['win'], r['oowc'], *r['spr_ofs'], r['prio'], 2 if r['prio'] & 0x80 else 1,
                 *r['scroll1'], *r['scroll2'], r['bg'])]
    return lines + _pal_lines(mem)


def map_lines(mem):
    out = []
    for title, base in (('plane 1 (9000)', PLANE1), ('plane 2 (9800)', PLANE2)):
        out.append('%s: tile, palette, h/v flips' % title)
        for row in range(32):
            ents = []
            for col in range(32):
                e = mem.entry(base, col, row)
                flips = ('h' if e & 0x8000 else '') + ('v' if e & 0x4000 else '')
                ents.append('%03X%X%-2s' % (e & 0x1FF, (e >> 9) & 15, flips))
            out.append('%2d %s' % (row, ' '.join(ents)))
    return out


def sprite_lines(mem):
    out = ['sprites (visible; position after chaining and the sprite offset):']
    for s in mem.sprites():
        if s.prio:
            out.append('  #%02d tile %03X x=%3d y=%3d prio %d pal %X %s%s%s%s raw %s' % (
                s.n, s.tile, s.x, s.y, s.prio, s.pal, 'H' if s.hflip else '-', 'V' if s.vflip else '-',
                'h' if s.attr & 4 else '-', 'v' if s.attr & 2 else '-', s.raw.hex()))
    return out


def save_rgb(path, rows, scale=2):
    h, w = len(rows), len(rows[0])
    png.write_rgb(path, w, h, [[p if p is not None else MAGENTA for p in r] for r in rows], scale)


def render(mem, prefix, maps=False, sprites=False, scale=2):
    """Print the description and write the five images. Returns their paths."""
    for line in describe(mem) + (map_lines(mem) if maps else []) + (sprite_lines(mem) if sprites else []):
        print(line)
    folder = os.path.dirname(os.path.abspath(prefix))
    os.makedirs(folder, exist_ok=True)
    paths = []
    for suffix, rows in (('p1', mem.plane_image(1)), ('p2', mem.plane_image(2)), ('spr', mem.sprite_image()),
                         ('screen', mem.screen())):
        path = '%s_%s.png' % (prefix, suffix)
        save_rgb(path, rows, scale)
        paths.append(path)
    w, h, rows = mem.tile_sheet()
    path = prefix + '_tiles.png'
    png.write_rgb(path, w, h, rows, scale)
    paths.append(path)
    print('wrote %s_{p1,p2,spr,screen,tiles}.png' % prefix)
    return paths


def _h(text):
    return int(text, 16)


def _hlist(text):
    return [int(v, 16) for v in text.split(',') if v]


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.gfx.vram', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('render', help='describe a dump and write images')
    p.add_argument('mem')
    p.add_argument('prefix')
    p.add_argument('--maps', action='store_true')
    p.add_argument('--sprites', action='store_true')
    p.add_argument('--scale', type=int, default=2)
    p = sub.add_parser('bytes', help='compare VRAM bytes with the ROM')
    for a in ('mem', 'rom'):
        p.add_argument(a)
    for a in ('vaddr', 'romaddr', 'len'):
        p.add_argument(a, type=_h)
    p = sub.add_parser('map', help='compare plane map entries with ROM words')
    for a in ('mem', 'rom'):
        p.add_argument(a)
    p.add_argument('planeaddr', type=_h)
    p.add_argument('romaddr', type=_h)
    p.add_argument('w', type=int)
    p.add_argument('h', type=int)
    p.add_argument('--stride', type=int)
    p = sub.add_parser('find', help='which ROM block VRAM holds')
    p.add_argument('mem', nargs='+')
    p.add_argument('rom')
    p.add_argument('vaddrs', type=_hlist)
    p.add_argument('len', type=_h)
    p.add_argument('romaddr', type=_h)
    p.add_argument('count', type=int)
    p.add_argument('--stride', type=_h)
    p.add_argument('--hex', action='store_true')
    p = sub.add_parser('queue', help='the VBlank copy queue')
    p.add_argument('mem', nargs='+')
    p.add_argument('--rom')
    p.add_argument('--dest', type=_h)
    p.add_argument('--index', nargs=2, type=_h, metavar=('BASE', 'STRIDE'))
    args = ap.parse_args(argv)

    if args.cmd == 'render':
        render(Vram.load(args.mem), args.prefix, args.maps, args.sprites, args.scale)
        return 0
    rom = open(args.rom, 'rb').read() if getattr(args, 'rom', None) else None
    if args.cmd == 'bytes':
        diff = compare_bytes(Vram.load(args.mem), rom, args.vaddr, args.romaddr, args.len)
        print('%d of %d bytes differ' % (len(diff), args.len))
        if diff:
            t = diff[0] // 16
            print('first differing tile %d (VRAM %04X, ROM %06X)' % (t, args.vaddr + 16 * t, args.romaddr + 16 * t))
        return 1 if diff else 0
    if args.cmd == 'map':
        diff = compare_map(Vram.load(args.mem), rom, args.planeaddr, args.romaddr, args.w, args.h, args.stride)
        print('%d of %d map entries differ' % (len(diff), args.w * args.h))
        if diff:
            r, c, e_mem, e_rom = diff[0]
            print('first at row %d col %d: VRAM %04X, ROM %04X' % (r, c, e_mem, e_rom))
        return 1 if diff else 0
    if args.cmd == 'find':
        fmt = '%02X' if args.hex else '%d'
        for path in dumps(args.mem):
            mem = Vram.load(path)
            got = []
            for va in args.vaddrs:
                hits = find_blocks(mem, rom, va, args.len, args.romaddr, args.count, args.stride)
                got.append('-' if hits is None else ('/'.join(fmt % i for i in hits) or '?'))
            print('%s: %s' % (os.path.basename(path), ' '.join('%2s' % g for g in got)))
        return 0
    if args.cmd == 'queue':
        for path in dumps(args.mem):
            mem = Vram.load(path)
            items = []
            for words, dest, src in mem.queue():
                if args.dest is not None and dest != args.dest:
                    continue
                s = '%06X->%04X x%d' % (src, dest, words)
                if args.index:
                    base, stride = args.index
                    if src >= base and (src - base) % stride == 0:
                        s += ' #%02X' % ((src - base) // stride)
                if rom is not None and words:
                    n = 2 * words
                    have = mem.m[dest:dest + n]
                    if src >= ROM_BASE:
                        want = rom[src - ROM_BASE:src - ROM_BASE + n]
                    else:
                        want = mem.m[src:src + n] if src + n <= SIZE else b''
                    s += ' ok' if have == want and len(want) == n else ' differs'
                items.append(s)
            print('%s: %s' % (os.path.basename(path), ', '.join(items) or
                              ('no entry for %04X' % args.dest if args.dest is not None else 'empty')))
        return 0
    return 2


if __name__ == '__main__':
    sys.exit(main())
