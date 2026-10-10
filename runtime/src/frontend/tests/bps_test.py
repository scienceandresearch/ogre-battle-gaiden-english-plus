"""Tests for the C BPS applier in zenobia.exe (--bps-apply SRC PATCH OUT).

A tiny independent BPS encoder builds patches from explicit action lists
(all four actions, overlapping TargetCopy, negative offsets, empty files,
multi-byte numbers), plus malformed patches that must be rejected with the
right error (exit code 10 + error code from bps.h). With REPO_ROOT, patches
made by the project's encoder (tools/patch/bps.py) are applied too.
All data is random; no ROM is needed.

    python runtime/src/frontend/tests/bps_test.py build/zenobia.exe WORKDIR [REPO_ROOT]
"""
import os
import random
import struct
import subprocess
import sys
import zlib

# exit codes: 10 + BPS error code (see runtime/src/frontend/bps.h)
OK = 0
TOO_SMALL, MAGIC, PATCH_CRC, NUMBER, HEADER = 12, 13, 14, 15, 16
SOURCE_SIZE, SOURCE_CRC, TRUNCATED, BOUNDS, TARGET_SIZE, TARGET_CRC = 17, 18, 19, 20, 21, 22


def enc_num(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def ref_apply(source, actions, target_size):
    """Reference semantics, used to compute the expected target."""
    t = bytearray()
    src_rel = tgt_rel = 0
    for a in actions:
        kind, length = a[0], a[1]
        if kind == 0:
            t += source[len(t):len(t) + length]
        elif kind == 1:
            t += a[2]
        elif kind == 2:
            src_rel += a[2]
            t += source[src_rel:src_rel + length]
            src_rel += length
        else:
            tgt_rel += a[2]
            for _ in range(length):
                t.append(t[tgt_rel])
                tgt_rel += 1
    assert len(t) == target_size, (len(t), target_size)
    return bytes(t)


def build(source, actions, target_size, metadata=b"", target_crc=None, raw_actions=None,
          source_size=None, fix_patch_crc=True):
    p = bytearray(b"BPS1")
    p += enc_num(len(source) if source_size is None else source_size)
    p += enc_num(target_size)
    p += enc_num(len(metadata)) + metadata
    if raw_actions is not None:
        p += raw_actions
    else:
        for a in actions:
            kind, length = a[0], a[1]
            p += enc_num(((length - 1) << 2) | kind)
            if kind == 1:
                p += a[2]
            elif kind in (2, 3):
                rel = a[2]
                p += enc_num((abs(rel) << 1) | (1 if rel < 0 else 0))
    if target_crc is None:
        target_crc = zlib.crc32(ref_apply(source, actions, target_size))
    p += struct.pack("<I", zlib.crc32(source)) + struct.pack("<I", target_crc)
    p += struct.pack("<I", zlib.crc32(bytes(p)) if fix_patch_crc else 0)
    return bytes(p)


class Runner:
    def __init__(self, exe, work):
        self.exe, self.work = exe, work
        self.passed = self.failed = 0

    def run(self, name, source, patch, expect_code, expect_target=None):
        sp = os.path.join(self.work, name + ".src")
        pp = os.path.join(self.work, name + ".bps")
        op = os.path.join(self.work, name + ".out")
        with open(sp, "wb") as f:
            f.write(source)
        with open(pp, "wb") as f:
            f.write(patch)
        if os.path.exists(op):
            os.remove(op)
        r = subprocess.run([self.exe, "--bps-apply", sp, pp, op], capture_output=True, text=True)
        ok = r.returncode == expect_code
        if ok and expect_code == 0:
            with open(op, "rb") as f:
                got = f.read()
            ok = got == expect_target
        if ok and expect_code != 0:
            ok = not os.path.exists(op)   # nothing written on failure
        status = "ok  " if ok else "FAIL"
        msg = (r.stdout + r.stderr).strip().splitlines()
        print("%s %-28s exit=%-3d %s" % (status, name, r.returncode, msg[-1] if msg else ""))
        if ok:
            self.passed += 1
        else:
            self.failed += 1


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    # absolute paths: CreateProcess does not resolve "build/zenobia.exe"
    exe, work = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    repo = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else None
    os.makedirs(work, exist_ok=True)
    rnd = random.Random(1234)
    T = Runner(exe, work)

    src = bytes(rnd.randrange(256) for _ in range(4096))
    lit = bytes(rnd.randrange(256) for _ in range(50))
    # out_off after each action noted on the right
    all4 = [
        (0, 100),                      # SourceRead            -> 100
        (1, 50, lit),                  # TargetRead            -> 150
        (2, 200, +1000),               # SourceCopy fwd        -> 350 (src_rel 1200)
        (2, 30, -500),                 # SourceCopy back       -> 380 (src_rel 730)
        (3, 64, 0),                    # TargetCopy from 0     -> 444 (tgt_rel 64)
        (3, 100, 443 - 64),            # TargetCopy overlap RLE-> 544 (tgt_rel 543)
        (3, 20, 10 - 543),             # TargetCopy back       -> 564
        (0, 16),                       # SourceRead at 564     -> 580
        (1, 1, b"\x5a"),               # TargetRead, length 1  -> 581
        (2, 1, 4095 - 730),            # SourceCopy last byte  -> 582
    ]
    tsize = 582
    p_all4 = build(src, all4, tsize, metadata=b"<test metadata/>")
    T.run("all_four_actions", src, p_all4, OK, ref_apply(src, all4, tsize))

    # long copies and large relative offsets (multi-byte numbers)
    big = bytes(rnd.randrange(256) for _ in range(300000))
    big_actions = [(2, 70000, 200000), (3, 50000, 0), (0, 1000), (1, 3, b"abc"), (2, 5000, -260000),
                   (3, 60000, 100)]
    big_size = 70000 + 50000 + 1000 + 3 + 5000 + 60000
    # SourceRead at 120000 reads source[120000:121000] (exists)
    T.run("large_offsets", big, build(big, big_actions, big_size), OK, ref_apply(big, big_actions, big_size))

    # target larger than source via a run-length TargetCopy
    small = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"
    grow = [(0, 10), (3, 5000, 9)]
    T.run("grow_rle", small, build(small, grow, 5010), OK, ref_apply(small, grow, 5010))

    T.run("empty_target", src, build(src, [], 0), OK, b"")
    T.run("empty_source", b"", build(b"", [(1, 4, b"wxyz"), (3, 8, 0)], 12), OK,
          ref_apply(b"", [(1, 4, b"wxyz"), (3, 8, 0)], 12))

    # ---- malformed patches ----
    T.run("too_small", src, b"BPS1\x80\x80", TOO_SMALL)
    T.run("bad_magic", src, b"BPS2" + p_all4[4:], MAGIC)
    damaged = bytearray(p_all4)
    damaged[40] ^= 0xFF
    T.run("patch_crc", src, bytes(damaged), PATCH_CRC)
    other = bytearray(src)
    other[123] ^= 1
    T.run("source_crc", bytes(other), p_all4, SOURCE_CRC)
    T.run("source_size", src[:-1], p_all4, SOURCE_SIZE)
    T.run("target_crc", src, build(src, all4, tsize, target_crc=12345), TARGET_CRC)
    # SourceRead past the end of the source (target is bigger than the source)
    T.run("sourceread_oob", small, build(small, [(0, 10)], 20, target_crc=0,
          raw_actions=enc_num(((20 - 1) << 2) | 0)), BOUNDS)
    T.run("sourcecopy_before_start", src, build(src, [], 4, target_crc=0,
          raw_actions=enc_num((3 << 2) | 2) + enc_num((1 << 1) | 1)), BOUNDS)
    T.run("sourcecopy_past_end", src, build(src, [], 8, target_crc=0,
          raw_actions=enc_num((7 << 2) | 2) + enc_num(4090 << 1)), BOUNDS)
    T.run("targetcopy_unwritten", src, build(src, [], 8, target_crc=0,
          raw_actions=enc_num((3 << 2) | 0) + enc_num((3 << 2) | 3) + enc_num(4 << 1)), BOUNDS)
    T.run("targetcopy_before_start", src, build(src, [], 8, target_crc=0,
          raw_actions=enc_num((3 << 2) | 0) + enc_num((3 << 2) | 3) + enc_num((1 << 1) | 1)), BOUNDS)
    T.run("write_past_target", src, build(src, [], 4, target_crc=0,
          raw_actions=enc_num((7 << 2) | 0)), BOUNDS)
    T.run("target_short", src, build(src, [], 8, target_crc=0,
          raw_actions=enc_num((3 << 2) | 0)), TARGET_SIZE)
    T.run("targetread_truncated", src, build(src, [], 8, target_crc=0,
          raw_actions=enc_num((7 << 2) | 1) + b"abc"), TRUNCATED)
    T.run("overlong_number", src, build(src, [], 8, target_crc=0,
          raw_actions=b"\x00" * 9), NUMBER)
    # a header number cut off by the footer
    cut = b"BPS1" + b"\x00\x00\x00" + struct.pack("<I", zlib.crc32(src)) + struct.pack("<I", 0)
    T.run("header_truncated", src, cut + struct.pack("<I", zlib.crc32(cut)), TRUNCATED)
    meta = b"BPS1" + enc_num(len(src)) + enc_num(0) + enc_num(1000) + b"xx"
    meta += struct.pack("<I", zlib.crc32(src)) + struct.pack("<I", 0)
    T.run("metadata_too_long", src, meta + struct.pack("<I", zlib.crc32(meta)), TRUNCATED)

    # ---- interoperability with the project's encoder (tools/patch/bps.py) ----
    if repo:
        sys.path.insert(0, repo)
        try:
            from tools.patch import bps as project_bps
        except Exception as e:   # noqa: BLE001
            print("skip interop:", e)
            project_bps = None
        if project_bps is not None:
            for i in range(4):
                a = bytearray(rnd.randrange(256) for _ in range(20000 + i * 5000))
                b = bytearray(a)
                for _ in range(40):
                    pos = rnd.randrange(len(b) - 64)
                    b[pos:pos + rnd.randrange(1, 64)] = bytes(rnd.randrange(256) for _ in range(rnd.randrange(1, 64)))
                b += bytes(b[:3000]) + bytes(300)
                patch = project_bps.encode(bytes(a), bytes(b))
                T.run("project_encoder_%d" % i, bytes(a), patch, OK, bytes(b))

    print("passed %d, failed %d" % (T.passed, T.failed))
    sys.exit(1 if T.failed else 0)


if __name__ == "__main__":
    main()
