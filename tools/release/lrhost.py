"""Run a ROM in a libretro emulator core without a window, for checking the
English ROM in established emulators (Beetle NeoPop, RACE). It writes PNG
frames at the console's own resolution, save states and contact sheets; the
core keeps the cartridge save in the save folder. Bring your own core: this
project downloads nothing (release checklist step 8 in
docs/workstreams/release.md).

    python -m tools.release.lrhost CORE.dll ROM --frames N [--input "F:BTN:LEN;..."]
        [--shot F,F,...] [--shot-every N] [--out DIR] [--sheet FILE [--sheet-scale S]]
        [--save-dir DIR] [--system-dir DIR] [--opt KEY=VALUE ...]
        [--load-state FILE] [--save-state F:FILE ...] [--srm FILE] [--quiet-log]

Buttons as in the project's harness: U D L R A B O (Option). F:BTN:LEN presses
BTN for LEN frames starting at frame F (frame 0 is the first retro_run). The
core's input descriptors give the mapping of A, B and Option.
"""
import argparse
import ctypes
import os
import struct
import sys
import zlib
from ctypes import (CFUNCTYPE, POINTER, c_bool, c_char_p, c_double, c_float,
                    c_int, c_int16, c_size_t, c_uint, c_void_p)


class GameInfo(ctypes.Structure):
    _fields_ = [('path', c_char_p), ('data', c_void_p), ('size', c_size_t), ('meta', c_char_p)]


class SystemInfo(ctypes.Structure):
    _fields_ = [('library_name', c_char_p), ('library_version', c_char_p),
                ('valid_extensions', c_char_p), ('need_fullpath', c_bool), ('block_extract', c_bool)]


class Geometry(ctypes.Structure):
    _fields_ = [('base_width', c_uint), ('base_height', c_uint), ('max_width', c_uint),
                ('max_height', c_uint), ('aspect_ratio', c_float)]


class Timing(ctypes.Structure):
    _fields_ = [('fps', c_double), ('sample_rate', c_double)]


class AVInfo(ctypes.Structure):
    _fields_ = [('geometry', Geometry), ('timing', Timing)]


class Variable(ctypes.Structure):
    _fields_ = [('key', c_char_p), ('value', c_char_p)]


class InputDescriptor(ctypes.Structure):
    _fields_ = [('port', c_uint), ('device', c_uint), ('index', c_uint), ('id', c_uint),
                ('description', c_char_p)]


class Message(ctypes.Structure):
    _fields_ = [('msg', c_char_p), ('frames', c_uint)]


ENV_CB = CFUNCTYPE(c_bool, c_uint, c_void_p)
VIDEO_CB = CFUNCTYPE(None, c_void_p, c_uint, c_uint, c_size_t)
AUDIO_CB = CFUNCTYPE(None, c_int16, c_int16)
AUDIO_BATCH_CB = CFUNCTYPE(c_size_t, c_void_p, c_size_t)
POLL_CB = CFUNCTYPE(None)
STATE_CB = CFUNCTYPE(c_int16, c_uint, c_uint, c_uint, c_uint)
LOG_CB = CFUNCTYPE(None, c_int, c_char_p, c_void_p, c_void_p)  # variadic in C; only fmt is read


class LogCallback(ctypes.Structure):
    _fields_ = [('log', LOG_CB)]


EXP = 0x10000
JOYPAD = 1
JOY_IDS = {'UP': 4, 'DOWN': 5, 'LEFT': 6, 'RIGHT': 7}
MEMORY_SAVE_RAM = 0


def write_png(path, w, h, rgb):
    raw = b''.join(b'\x00' + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def to_rgb(fmt, data, w, h, pitch):
    out = bytearray(w * h * 3)
    i = 0
    for y in range(h):
        row = data[y * pitch:]
        if fmt == 1:  # XRGB8888, little-endian B G R X
            for x in range(w):
                out[i] = row[x * 4 + 2]
                out[i + 1] = row[x * 4 + 1]
                out[i + 2] = row[x * 4]
                i += 3
        else:
            px = struct.unpack_from('<%dH' % w, row)
            for p in px:
                if fmt == 2:  # RGB565
                    r, g, b = (p >> 11) & 31, (p >> 5) & 63, p & 31
                    out[i], out[i + 1], out[i + 2] = (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)
                else:  # 0RGB1555
                    r, g, b = (p >> 10) & 31, (p >> 5) & 31, p & 31
                    out[i], out[i + 1], out[i + 2] = (r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2)
                i += 3
    return bytes(out)


def write_sheet(path, shots, scale, cols=6, gap=4):
    if not shots:
        return
    w, h = shots[0][1], shots[0][2]
    cw, ch = w * scale + gap, h * scale + gap
    rows = (len(shots) + cols - 1) // cols
    W, H = cols * cw + gap, rows * ch + gap
    img = bytearray(b'\x40' * (W * H * 3))
    for n, (_, sw, sh, rgb) in enumerate(shots):
        ox, oy = gap + (n % cols) * cw, gap + (n // cols) * ch
        for y in range(sh * scale):
            src = (y // scale) * sw * 3
            line = bytearray()
            for x in range(sw):
                line += rgb[src + x * 3:src + x * 3 + 3] * scale
            o = ((oy + y) * W + ox) * 3
            img[o:o + len(line)] = line
    write_png(path, W, H, bytes(img))


def parse_input(spec):
    events = []
    for part in filter(None, (p.strip() for p in spec.split(';'))):
        f, btns, n = part.split(':')
        events.append((int(f), btns.upper(), int(n)))
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('core')
    ap.add_argument('rom')
    ap.add_argument('--frames', type=int, default=600)
    ap.add_argument('--input', default='')
    ap.add_argument('--shot', default='')
    ap.add_argument('--shot-every', type=int, default=0)
    ap.add_argument('--out', default='.')
    ap.add_argument('--sheet')
    ap.add_argument('--sheet-scale', type=int, default=1)
    ap.add_argument('--save-dir')
    ap.add_argument('--system-dir')
    ap.add_argument('--opt', action='append', default=[])
    ap.add_argument('--load-state')
    ap.add_argument('--save-state', action='append', default=[])
    ap.add_argument('--srm')
    ap.add_argument('--quiet-log', action='store_true')
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    save_dir = os.path.abspath(a.save_dir or a.out)
    sys_dir = os.path.abspath(a.system_dir or a.out)
    os.makedirs(save_dir, exist_ok=True)
    os.makedirs(sys_dir, exist_ok=True)
    keep = {'save': save_dir.encode(), 'sys': sys_dir.encode()}
    overrides = dict(o.split('=', 1) for o in a.opt)
    options = {}          # key -> bytes value (kept alive)
    option_desc = {}
    st = {'fmt': 0, 'frame': None, 'w': 0, 'h': 0, 'pitch': 0, 'pressed': set(), 'map': {}}

    def env(cmd, data):
        base = cmd & ~EXP
        if cmd == 3:  # GET_CAN_DUPE
            ctypes.cast(data, POINTER(c_bool))[0] = True
            return True
        if cmd in (6, 60):  # SET_MESSAGE(_EXT)
            m = ctypes.cast(data, POINTER(Message))[0]
            print('[core message]', (m.msg or b'').decode('utf-8', 'replace'))
            return True
        if cmd == 7:
            print('[core] shutdown requested')
            return True
        if cmd in (9, 30, 31):  # system / core assets / save directory
            ctypes.cast(data, POINTER(c_char_p))[0] = keep['save'] if cmd == 31 else keep['sys']
            return True
        if cmd == 10:  # SET_PIXEL_FORMAT
            st['fmt'] = ctypes.cast(data, POINTER(c_int))[0]
            return st['fmt'] in (0, 1, 2)
        if cmd == 11:  # SET_INPUT_DESCRIPTORS
            p = ctypes.cast(data, POINTER(InputDescriptor))
            i = 0
            while p[i].description is not None:
                d = p[i]
                if d.port == 0 and d.device == JOYPAD:
                    st['map'][d.description.decode('utf-8', 'replace').strip().upper()] = d.id
                i += 1
            return True
        if cmd == 15:  # GET_VARIABLE
            v = ctypes.cast(data, POINTER(Variable))[0]
            key = v.key.decode()
            if key in options:
                v.value = options[key]
                return True
            return False
        if cmd == 16:  # SET_VARIABLES
            p = ctypes.cast(data, POINTER(Variable))
            i = 0
            while p[i].key is not None:
                key = p[i].key.decode()
                desc = (p[i].value or b'').decode('utf-8', 'replace')
                values = desc.split(';', 1)[1].strip().split('|') if ';' in desc else ['']
                option_desc[key] = desc
                options[key] = overrides.get(key, values[0]).encode()
                i += 1
            for k, v in overrides.items():
                options.setdefault(k, v.encode())
            return True
        if cmd == 17:  # GET_VARIABLE_UPDATE
            ctypes.cast(data, POINTER(c_bool))[0] = False
            return True
        if cmd == 27:  # GET_LOG_INTERFACE
            ctypes.cast(data, POINTER(LogCallback))[0].log = log_cb
            return True
        if cmd == 39:  # GET_LANGUAGE
            ctypes.cast(data, POINTER(c_uint))[0] = 0
            return True
        if base == 47:  # GET_AUDIO_VIDEO_ENABLE
            ctypes.cast(data, POINTER(c_int))[0] = 3
            return True
        if base == 49:  # GET_FASTFORWARDING
            ctypes.cast(data, POINTER(c_bool))[0] = False
            return True
        if cmd == 61:  # GET_INPUT_MAX_USERS
            ctypes.cast(data, POINTER(c_uint))[0] = 1
            return True
        if cmd in (8, 44, 35, 34, 36 | EXP, 42 | EXP, 32, 37, 18, 55):
            return True
        return False

    def video(data, w, h, pitch):
        if data:
            st['frame'] = ctypes.string_at(data, pitch * h)
            st['w'], st['h'], st['pitch'] = w, h, pitch

    def audio(l, r):
        pass

    def audio_batch(data, frames):
        return frames

    def poll():
        pass

    def state(port, device, index, id_):
        if port != 0 or device != JOYPAD:
            return 0
        if id_ == 256:
            return sum(1 << i for i in st['pressed'])
        return 1 if id_ in st['pressed'] else 0

    def log(level, fmt, a1, a2):
        if not a.quiet_log and fmt:
            print('[core log %d] %s' % (level, fmt.decode('utf-8', 'replace').rstrip()))

    env_cb, video_cb, audio_cb = ENV_CB(env), VIDEO_CB(video), AUDIO_CB(audio)
    batch_cb, poll_cb, state_cb, log_cb = AUDIO_BATCH_CB(audio_batch), POLL_CB(poll), STATE_CB(state), LOG_CB(log)

    core = ctypes.CDLL(os.path.abspath(a.core))
    core.retro_api_version.restype = c_uint
    core.retro_serialize_size.restype = c_size_t
    core.retro_serialize.restype = c_bool
    core.retro_serialize.argtypes = [c_void_p, c_size_t]
    core.retro_unserialize.restype = c_bool
    core.retro_unserialize.argtypes = [c_void_p, c_size_t]
    core.retro_load_game.restype = c_bool
    core.retro_get_memory_data.restype = c_void_p
    core.retro_get_memory_data.argtypes = [c_uint]
    core.retro_get_memory_size.restype = c_size_t
    core.retro_get_memory_size.argtypes = [c_uint]

    core.retro_set_environment(env_cb)
    core.retro_set_video_refresh(video_cb)
    core.retro_set_audio_sample(audio_cb)
    core.retro_set_audio_sample_batch(batch_cb)
    core.retro_set_input_poll(poll_cb)
    core.retro_set_input_state(state_cb)
    core.retro_init()
    info = SystemInfo()
    core.retro_get_system_info(ctypes.byref(info))
    print('core: %s %s (api %d, need_fullpath=%s)' % (info.library_name.decode(), info.library_version.decode(),
                                                     core.retro_api_version(), info.need_fullpath))
    rom = open(a.rom, 'rb').read()
    rom_buf = ctypes.create_string_buffer(rom, len(rom))
    gi = GameInfo(os.path.abspath(a.rom).encode(), ctypes.cast(rom_buf, c_void_p), len(rom), None)
    if not core.retro_load_game(ctypes.byref(gi)):
        sys.exit('retro_load_game failed')
    av = AVInfo()
    core.retro_get_system_av_info(ctypes.byref(av))
    print('video %dx%d @ %.3f fps; options: %s' % (av.geometry.base_width, av.geometry.base_height,
                                                av.timing.fps, {k: v.decode() for k, v in options.items()}))
    btn = {'U': JOY_IDS['UP'], 'D': JOY_IDS['DOWN'], 'L': JOY_IDS['LEFT'], 'R': JOY_IDS['RIGHT'],
           'A': st['map'].get('A', 0), 'B': st['map'].get('B', 8),
           'O': st['map'].get('OPTION', 3)}
    print('input map (RetroPad ids):', btn, 'descriptors:', st['map'])

    if a.srm and os.path.isfile(a.srm):
        size = core.retro_get_memory_size(MEMORY_SAVE_RAM)
        ptr = core.retro_get_memory_data(MEMORY_SAVE_RAM)
        data = open(a.srm, 'rb').read()
        if ptr and size == len(data):
            ctypes.memmove(ptr, data, size)
            print('loaded save RAM %s (%d bytes)' % (a.srm, size))
        else:
            print('save RAM not loaded: core size %d, file %d' % (size, len(data)))
    if a.load_state:
        data = open(a.load_state, 'rb').read()
        buf = ctypes.create_string_buffer(data, len(data))
        print('load state:', core.retro_unserialize(buf, len(data)))

    events = parse_input(a.input)
    shots = set(int(x) for x in a.shot.split(',') if x.strip())
    save_states = {}
    for s in a.save_state:
        f, path = s.split(':', 1)
        save_states[int(f)] = path
    taken = []
    for frame in range(a.frames):
        pressed = set()
        for f, b, n in events:
            if f <= frame < f + n:
                for ch in b:
                    pressed.add(btn[ch])
        st['pressed'] = pressed
        core.retro_run()
        if frame in save_states:
            size = core.retro_serialize_size()
            buf = ctypes.create_string_buffer(size)
            ok = core.retro_serialize(buf, size)
            open(save_states[frame], 'wb').write(buf.raw)
            print('frame %d: save state %s (%d bytes, ok=%s)' % (frame, save_states[frame], size, ok))
        if frame in shots or (a.shot_every and frame % a.shot_every == 0):
            if st['frame'] is not None:
                rgb = to_rgb(st['fmt'], st['frame'], st['w'], st['h'], st['pitch'])
                write_png(os.path.join(a.out, 'f%06d.png' % frame), st['w'], st['h'], rgb)
                taken.append((frame, st['w'], st['h'], rgb))
    if a.sheet:
        write_sheet(a.sheet, taken, a.sheet_scale)
        print('sheet %s: %d frames: %s' % (a.sheet, len(taken), ' '.join(str(t[0]) for t in taken)))
    size = core.retro_get_memory_size(MEMORY_SAVE_RAM)
    ptr = core.retro_get_memory_data(MEMORY_SAVE_RAM)
    print('save RAM exposed by the core: %d bytes' % size)
    if a.srm and ptr and size:
        open(a.srm, 'wb').write(ctypes.string_at(ptr, size))
        print('wrote save RAM to', a.srm)
    core.retro_unload_game()
    core.retro_deinit()
    print('done: %d frames; files in save dir: %s' % (a.frames, sorted(os.listdir(save_dir))))


if __name__ == '__main__':
    main()
