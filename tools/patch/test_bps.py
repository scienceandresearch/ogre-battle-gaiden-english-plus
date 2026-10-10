"""Tests for the BPS patch tools (tools/patch/bps.py and tools/patch/apply.py).

Usage: python -m tools.patch.test_bps [ROM] [--target EN_ROM] [--vectors DIR]

ROM        the original ROM (rom/baserom.ngc). Without it only the synthetic
           tests run.
--target   the English ROM for the real round trip (default build/ogre_en.ngc).
--vectors  also write the synthetic cases (sources, targets, patches and a
           MANIFEST.txt with the expected results) to DIR, for testing other
           BPS implementations such as the player's C applier.

Synthetic tests: number encoding; a hand-made patch with every action (copies
with negative moves, overlapping TargetCopy, metadata); encoder round trips
(empty files, longer/shorter targets, runs, large numbers, random edits);
damaged or malformed patches; wrong sources; the literal audit. Every result
is also checked with a byte-by-byte reference decoder written from the
specification. Real tests: encode(original, English ROM), audit, apply;
rejection of a damaged patch, a wrong ROM and an already patched ROM; the
shipped build/ogre_en.bps and build/ogre_en.sha1; the apply command.
"""
import argparse
import contextlib
import hashlib
import io
import os
import random
import struct
import sys
import tempfile
import time
import traceback
import zipfile
import zlib

from . import bps
from . import apply as apply_cmd
from ..recomp.rom import EXPECTED_SHA1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


# ---------------------------------------------------------------------------
# Helpers

def reference_apply(source, patch):
    """Decode straight from the specification, one byte at a time. Returns
    (target, list of the byte lengths of every number read)."""
    pos = 0
    sizes = []

    def number():
        nonlocal pos
        data, shift, start = 0, 1, pos
        while True:
            x = patch[pos]
            pos += 1
            data += (x & 0x7F) * shift
            if x & 0x80:
                break
            shift <<= 7
            data += shift
        sizes.append(pos - start)
        return data

    assert patch[:4] == b'BPS1'
    pos = 4
    source_size, target_size, meta_size = number(), number(), number()
    assert source_size == len(source)
    pos += meta_size
    end = len(patch) - 12
    out = bytearray()
    src = tgt = 0
    while pos < end:
        d = number()
        kind, length = d & 3, (d >> 2) + 1
        if kind == 0:
            for _ in range(length):
                out.append(source[len(out)])
        elif kind == 1:
            for _ in range(length):
                out.append(patch[pos])
                pos += 1
        else:
            v = number()
            delta = -(v >> 1) if v & 1 else v >> 1
            if kind == 2:
                src += delta
                for _ in range(length):
                    out.append(source[src])
                    src += 1
            else:
                tgt += delta
                assert 0 <= tgt < len(out)
                for _ in range(length):
                    out.append(out[tgt])
                    tgt += 1
    assert pos == end and len(out) == target_size
    crcs = struct.unpack('<III', patch[-12:])
    assert crcs == (zlib.crc32(source), zlib.crc32(out), zlib.crc32(patch[:-4]))
    return bytes(out), sizes


def assemble(source, target_size, actions, metadata=b'', target=b'', source_crc=None, target_crc=None):
    """A hand-made patch. actions: ('SR', n), ('TR', bytes), ('SC', n, delta),
    ('TC', n, delta), ('SCV'/'TCV', n, raw offset number), ('RAW', bytes).
    The checksums are right unless overridden; the patch checksum always is."""
    out = bytearray(bps.MAGIC)
    for v in (len(source), target_size, len(metadata)):
        bps.encode_number(v, out)
    out += metadata
    kinds = {'SR': bps.SOURCE_READ, 'SC': bps.SOURCE_COPY, 'TC': bps.TARGET_COPY,
             'SCV': bps.SOURCE_COPY, 'TCV': bps.TARGET_COPY}
    for a in actions:
        if a[0] == 'RAW':
            out += a[1]
        elif a[0] == 'TR':
            bps.encode_number(((len(a[1]) - 1) << 2) | bps.TARGET_READ, out)
            out += a[1]
        else:
            bps.encode_number(((a[1] - 1) << 2) | kinds[a[0]], out)
            if a[0] in ('SC', 'TC'):
                bps.encode_number(bps.offset_number(a[2]), out)
            elif a[0] in ('SCV', 'TCV'):
                bps.encode_number(a[2], out)
    out += struct.pack('<II', zlib.crc32(source) if source_crc is None else source_crc,
                       zlib.crc32(target) if target_crc is None else target_crc)
    out += struct.pack('<I', zlib.crc32(out))
    return bytes(out)


def seal(source, target, body):
    """Add the footer (right checksums) to a raw patch body."""
    out = body + struct.pack('<II', zlib.crc32(source), zlib.crc32(target))
    return out + struct.pack('<I', zlib.crc32(out))


def expect_error(cls, fn, *args):
    try:
        fn(*args)
    except cls as e:
        return e
    except Exception as e:                      # wrong exception type
        raise AssertionError('expected %s, got %s: %s' % (cls.__name__, type(e).__name__, e))
    raise AssertionError('expected %s, nothing was raised' % cls.__name__)


def check_round_trip(name, source, target, metadata=b''):
    """encode/create + bps.apply + reference decoder + audit. Returns (patch, report)."""
    patch, report = bps.create(source, target, metadata)
    assert bps.apply(source, patch) == target, name
    ref, _ = reference_apply(source, patch)
    assert ref == target, '%s: reference decoder disagrees' % name
    assert report.ok, '%s: %s' % (name, report.summary())
    assert bps.encode(source, target, metadata) == patch, '%s: encoding is not deterministic' % name
    return patch, report


# ---------------------------------------------------------------------------
# Synthetic cases (also exported by --vectors)

EXPLICIT_SOURCE = b'0123456789ABCDEFGHIJ'
EXPLICIT_ACTIONS = [('SR', 3), ('TR', b'xy'), ('SR', 2), ('SC', 4, 10), ('SC', 3, -12),
                    ('TC', 2, 3), ('TC', 5, 10), ('TC', 3, -13), ('SC', 1, 14), ('TR', b'ab'),
                    ('TC', 6, 15)]
EXPLICIT_TARGET = b'012xy56ABCD234xyyyyyyABCJabababab'


def encoder_cases():
    """(name, source, target) pairs for encoder round trips."""
    rnd = random.Random(20261009)
    cases = [('empty', b'', b'')]
    new = rnd.randbytes(300)
    cases.append(('from_empty', b'', new + new[:100] + b'\x42' * 40))
    cases.append(('to_empty', rnd.randbytes(300), b''))
    s = rnd.randbytes(1000)
    cases.append(('identical', s, s))

    s = rnd.randbytes(4096)
    t = bytearray(s)
    t[1000:1200] = s[3000:3200]                 # SourceCopy forward
    t[1200:1300] = new[:100]                    # TargetRead (not in the source)
    t[1300:1500] = s[500:700]                   # SourceCopy with a negative move
    t[1500:1600] = new[:100]                    # TargetCopy
    t[1600:1650] = b'\x77' * 50                 # literal byte + overlapping TargetCopy
    t += new[100:200] + s[10:90]                # longer target
    cases.append(('all_actions', s, bytes(t)))

    s = rnd.randbytes(2000)
    cases.append(('target_longer', s, s + new + s[100:400] + new))
    s = rnd.randbytes(3000)
    t = bytearray(s[:1500])
    t[200:260] = new[:60]
    t[900:1000] = s[2500:2600]
    cases.append(('target_shorter', s, bytes(t)))

    s = rnd.randbytes(500) + b'\x00' * 40 + rnd.randbytes(500) + b'\x55' * 20 + rnd.randbytes(100)
    t = rnd.randbytes(50) + b'\x00' * 100 + rnd.randbytes(50) + b'\x55' * 9 + b'\x66' * 30
    cases.append(('runs', s, t + s[300:600]))

    # Large numbers: 4-byte action headers (a SourceRead over 528,416 bytes),
    # a TargetRead longer than 16,512 bytes (3-byte header), and a SourceCopy
    # moving back more than 1,056,832 bytes (4-byte offset).
    s = rnd.randbytes(1100000)
    t = bytearray(s)
    t[700000:720000] = rnd.randbytes(20000)
    t[1080000:1080100] = s[1095000:1095100]
    t[1090000:1090100] = s[0:100]               # cursor moves back 1,095,100 bytes
    cases.append(('large_numbers', s, bytes(t)))
    return cases


def malformed_cases():
    """(name, source, patch, expected exception, what is wrong)."""
    src = EXPLICIT_SOURCE
    good = assemble(src, len(EXPLICIT_TARGET), EXPLICIT_ACTIONS, target=EXPLICIT_TARGET)
    flipped = bytearray(good)
    flipped[10] ^= 0x01
    PF = bps.PatchFormatError
    t3 = b'abc'
    return [
        ('bad_flipped_byte', src, bytes(flipped), PF, 'one byte changed (patch checksum)'),
        ('bad_truncated', src, good[:-5], PF, 'last bytes missing (patch checksum)'),
        ('bad_too_short', src, b'BPS1\x80\x80', PF, 'shorter than any patch'),
        ('bad_magic', src, b'BPS2' + good[4:-4] + struct.pack('<I', zlib.crc32(b'BPS2' + good[4:-4])),
         PF, 'wrong signature'),
        ('bad_source_read_past_end', src, assemble(src, 21, [('SR', 21)], target=src + b'x'), PF,
         'SourceRead past the end of the source'),
        ('bad_target_read_past_end', src, assemble(src, 10, [('RAW', b'\xa5abc')]), PF,
         'TargetRead longer than the rest of the patch'),
        ('bad_source_copy_before_start', src, assemble(src, 3, [('SC', 3, -1)], target=t3), PF,
         'SourceCopy before the start of the source'),
        ('bad_source_copy_past_end', src, assemble(src, 3, [('SC', 3, 18)], target=t3), PF,
         'SourceCopy past the end of the source'),
        ('bad_target_copy_first', src, assemble(src, 3, [('TC', 3, 0)], target=t3), PF,
         'TargetCopy before anything was written'),
        ('bad_target_copy_unwritten', src, assemble(src, 6, [('TR', t3), ('TC', 3, 3)], target=t3 * 2), PF,
         'TargetCopy from the output position'),
        ('bad_write_past_target', src, assemble(src, 2, [('TR', t3)], target=t3), PF,
         'writes more than the target size'),
        ('bad_short_output', src, assemble(src, 5, [('TR', t3)], target=t3), PF,
         'writes less than the target size'),
        ('bad_metadata_size', src, seal(src, b'', b'BPS1' + bps.number_bytes(len(src)) + b'\x80\xe4ab'), PF,
         'metadata size 100 with 2 bytes left'),
        ('bad_number_truncated', src, assemble(src, 3, [('TR', t3), ('RAW', b'\x00')], target=t3), PF,
         'unterminated number before the footer'),
        ('bad_number_too_large', src, assemble(src, 3, [('RAW', b'\x7f' * 11 + b'\x80')], target=t3), PF,
         'number above 64 bits'),
        ('bad_huge_target', src, assemble(src, 1 << 40, [], target=b''), PF,
         'declares a 1 TiB target'),
        ('bad_target_crc', src, assemble(src, 3, [('TR', t3)], target=t3, target_crc=0x12345678),
         bps.TargetMismatch, 'right structure, wrong target checksum'),
        ('bad_source_crc', src, assemble(src, 3, [('TR', t3)], target=t3, source_crc=0x12345678),
         bps.SourceMismatch, 'made for another source'),
    ]


# ---------------------------------------------------------------------------
# Synthetic tests

def test_numbers(ctx):
    known = {0: '80', 1: '81', 0x7F: 'ff', 0x80: '0080', 0x81: '0180', 0x407F: '7fff',
             0x4080: '000080', 0x20407F: '7f7fff', 0x204080: '00000080'}
    for v, h in known.items():
        assert bps.number_bytes(v).hex() == h, (v, bps.number_bytes(v).hex(), h)
    values = list(range(0, 300)) + [16383, 16384, 16511, 16512, 16513, 2113663, 2113664,
                                     (1 << 32) - 1, 1 << 32, 1 << 56, 1 << 63, (1 << 64) - 1]
    seen = set()
    for v in values:
        b = bps.number_bytes(v)
        assert bps.number_size(v) == len(b), v
        assert bps.decode_number(b + b'\xff', 0, len(b) + 1) == (v, len(b)), v
        assert b not in seen
        seen.add(b)
    assert len(bps.number_bytes((1 << 64) - 1)) == 10
    for d in (0, 1, -1, 5, -5, 1 << 40, -(1 << 40)):
        v = bps.offset_number(d)
        assert (-(v >> 1) if v & 1 else v >> 1) == d
    expect_error(bps.PatchFormatError, bps.decode_number, b'\x00\x00', 0, 2)          # no last byte
    expect_error(bps.PatchFormatError, bps.decode_number, b'\x7f' * 10 + b'\x80', 0, 11)  # > 64 bits


def test_handmade_all_actions(ctx):
    meta = b'<test name="all actions"/>'
    patch = assemble(EXPLICIT_SOURCE, len(EXPLICIT_TARGET), EXPLICIT_ACTIONS, metadata=meta,
                     target=EXPLICIT_TARGET)
    assert bps.apply(EXPLICIT_SOURCE, patch) == EXPLICIT_TARGET
    assert reference_apply(EXPLICIT_SOURCE, patch)[0] == EXPLICIT_TARGET
    p = bps.parse(patch)
    assert p.metadata == meta
    got = [(k, o, n) + ((a,) if k != bps.TARGET_READ else ()) for k, o, n, a in p.actions]
    assert got == [(0, 0, 3, 0), (1, 3, 2), (0, 5, 2, 5), (2, 7, 4, 10), (2, 11, 3, 2), (3, 14, 2, 3),
                   (3, 16, 5, 15), (3, 21, 3, 7), (2, 24, 1, 19), (1, 25, 2), (3, 27, 6, 25)], got
    # "negative zero" moves are valid; SourceRead does not move the SourceCopy cursor
    for op in ('SCV', 'TCV'):
        patch = assemble(b'abc', 6, [('SR', 3), (op, 3, 1)], target=b'abcabc')
        assert bps.apply(b'abc', patch) == b'abcabc', op
        assert reference_apply(b'abc', patch)[0] == b'abcabc', op


def test_encoder_round_trips(ctx):
    for name, s, t in encoder_cases():
        patch, report = check_round_trip(name, s, t)
        p = bps.parse(patch)
        counts, sizes = p.stats()
        if name == 'empty':
            assert len(patch) == bps.MIN_PATCH_SIZE and not p.actions
        if name == 'to_empty':
            assert not p.actions
        if name == 'identical':
            assert counts == [1, 0, 0, 0], counts
        if name == 'all_actions':
            assert all(counts), counts
            cur, negative = 0, False
            for k, o, n, a in p.actions:
                if k == bps.SOURCE_COPY:
                    negative |= a < cur
                    cur = a + n
            assert negative, 'no SourceCopy with a negative move'
            assert any(k == bps.TARGET_COPY and a + n > o for k, o, n, a in p.actions), 'no overlapping copy'
            assert sizes[bps.TARGET_READ] <= 201, sizes   # 100 + 100 new bytes + 1 for the run
        if name == 'large_numbers':
            sizes_read = reference_apply(s, patch)[1]
            assert max(sizes_read) >= 4, max(sizes_read)
            assert any(k == bps.TARGET_READ and n > 16512 for k, o, n, a in p.actions)
            cur, moves = 0, []
            for k, o, n, a in p.actions:
                if k == bps.SOURCE_COPY:
                    moves.append(a - cur)
                    cur = a + n
            assert any(bps.number_size(bps.offset_number(d)) == 4 for d in moves), moves
        ctx.log('  %-16s %9d -> %9d bytes: patch %7d, actions %s, literal %d, longest in source %d'
                % (name, len(s), len(t), len(patch), counts, report.literal_bytes, report.longest))


def test_encoder_random_edits(ctx):
    rnd = random.Random(99)
    for i in range(400):
        alphabet = rnd.choice((2, 3, 16, 256))
        src = bytes(rnd.randrange(alphabet) for _ in range(rnd.randrange(0, 400)))
        tgt = bytearray(src)
        for _ in range(rnd.randrange(0, 8)):
            op = rnd.randrange(5)
            p = rnd.randrange(len(tgt) + 1)
            if op == 0:
                tgt[p:p] = bytes(rnd.randrange(256) for _ in range(rnd.randrange(1, 40)))
            elif op == 1:
                del tgt[p:p + rnd.randrange(1, 40)]
            elif op == 2:
                tgt[p:p + 10] = bytes(rnd.randrange(alphabet) for _ in range(10))
            elif op == 3 and src:
                a = rnd.randrange(len(src))
                tgt[p:p] = src[a:a + rnd.randrange(1, 60)]
            elif tgt:
                a = rnd.randrange(len(tgt))
                tgt[p:p] = tgt[a:a + rnd.randrange(1, 30)] * rnd.randrange(1, 4)
        check_round_trip('random %d' % i, src, bytes(tgt), b'm' * rnd.randrange(0, 3))


def test_malformed_patches(ctx):
    for name, src, patch, cls, what in malformed_cases():
        try:
            expect_error(cls, bps.apply, src, patch)
        except AssertionError as e:
            raise AssertionError('%s (%s): %s' % (name, what, e))


def test_wrong_source(ctx):
    rnd = random.Random(5)
    s = rnd.randbytes(5000)
    t = s[:2000] + rnd.randbytes(300) + s[2300:]
    patch = bps.encode(s, t)
    e = expect_error(bps.SourceMismatch, bps.apply, s[:-1] + b'\x00', patch)
    assert not e.already_patched
    expect_error(bps.SourceMismatch, bps.apply, s[:-1], patch)
    expect_error(bps.SourceMismatch, bps.apply, s + b'\x00', patch)
    e = expect_error(bps.SourceMismatch, bps.apply, t, patch)
    assert e.already_patched, 'the patched file should be recognised'


def test_audit(ctx):
    src = bytes(range(64))
    pad = b'\xc8\xc9'
    for n in (8, 9, 20):
        tgt = pad + src[10:10 + n] + pad
        r = bps.audit(src, assemble(src, len(tgt), [('TR', tgt)], target=tgt))
        assert not r.ok and r.offenders == [(2, n, 10)] and r.longest == n, (n, r.offenders)
        assert 'FAILED' in r.summary() and 'FAILED' in str(bps.AuditError(r))
    tgt = pad + src[20:27] + pad + src[40:46]
    r = bps.audit(src, assemble(src, len(tgt), [('TR', tgt)], target=tgt))
    assert r.ok and r.longest == 7 and r.example == (2, 7, 20) and r.literal_bytes == len(tgt), r.summary()
    # literal pieces split over two TargetReads are audited separately
    tgt = src[0:5] + src[5:10]
    r = bps.audit(src, assemble(src, 10, [('TR', tgt[:5]), ('TR', tgt[5:])], target=tgt))
    assert r.ok and r.longest == 5 and r.literal_runs == 2
    r = bps.audit(src, assemble(src, 0, [], target=b''))
    assert r.ok and r.literal_bytes == 0 and r.longest == 0


# ---------------------------------------------------------------------------
# Real ROM tests

def test_real_round_trip(ctx):
    base, target = ctx.base, ctx.target
    assert hashlib.sha1(base).hexdigest() == EXPECTED_SHA1, 'the ROM is not the expected original'
    t0 = time.time()
    patch, report = bps.create(base, target)
    dt = time.time() - t0
    assert report.ok, report.summary()
    assert bps.apply(base, patch) == target
    ref, sizes = reference_apply(base, patch)
    assert ref == target, 'reference decoder disagrees'
    assert max(sizes) <= 8, 'numbers longer than 8 bytes (the C applier limit)'
    ctx.patch = patch
    counts, written = bps.parse(patch).stats()
    ctx.log('  patch %s bytes (encode + verify + audit %.1f s)' % (format(len(patch), ','), dt))
    ctx.log('  actions %s, bytes written %s' % (counts, written))
    ctx.log('  audit: %s' % report.summary())


def test_real_rejections(ctx):
    base, target, patch = ctx.base, ctx.target, ctx.patch
    bad = bytearray(patch)
    bad[len(bad) // 2] ^= 0x10
    expect_error(bps.PatchFormatError, bps.apply, base, bytes(bad))
    expect_error(bps.PatchFormatError, bps.apply, base, patch[:-1])
    wrong = bytearray(base)
    wrong[0x1000] ^= 0xFF
    e = expect_error(bps.SourceMismatch, bps.apply, bytes(wrong), patch)
    assert not e.already_patched
    e = expect_error(bps.SourceMismatch, bps.apply, target, patch)
    assert e.already_patched


def test_shipped_patch(ctx):
    path = os.path.join(ROOT, 'build', 'ogre_en.bps')
    if not os.path.isfile(path):
        ctx.log('  (no %s yet: run the build)' % os.path.relpath(path, ROOT))
        return
    shipped = open(path, 'rb').read()
    out = bps.apply(ctx.base, shipped)
    assert out == ctx.target, 'build/ogre_en.bps does not produce %s (stale patch?)' % ctx.target_path
    sha_path = os.path.splitext(path)[0] + '.sha1'
    want = open(sha_path).read().split()[0]
    assert want == hashlib.sha1(out).hexdigest(), 'build/ogre_en.sha1 does not match the patched ROM'
    report = bps.audit(ctx.base, shipped)
    assert report.ok, report.summary()
    ctx.log('  build/ogre_en.bps: %s bytes, SHA-1 of the result %s; audit %s'
            % (format(len(shipped), ','), want, report.summary()))


def _run_apply(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = apply_cmd.main(args)
    return code, out.getvalue() + err.getvalue()


def test_apply_command(ctx):
    base, target, patch = ctx.base, ctx.target, ctx.patch
    want = hashlib.sha1(target).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        def path(name):
            return os.path.join(tmp, name)
        for name, data in (('orig.ngc', base), ('ogre_en.bps', patch), ('ogre_en.sha1', (want + '\n').encode()),
                           ('english.ngc', target), ('other.ngc', base[:-1] + b'\x00'),
                           ('half.ngc', base[:len(base) // 2])):
            with open(path(name), 'wb') as f:
                f.write(data)
        with zipfile.ZipFile(path('rom.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('readme.txt', 'not a ROM')
            z.writestr('Some Name (Japan).ngc', base)

        code, msg = _run_apply([path('orig.ngc'), path('ogre_en.bps'), '-o', path('out.ngc')])
        assert code == 0, msg
        assert hashlib.sha1(open(path('out.ngc'), 'rb').read()).hexdigest() == want
        assert 'matches ogre_en.sha1' in msg, msg

        code, msg = _run_apply([path('orig.ngc'), path('ogre_en.bps')])        # default output
        assert code == 0 and open(path('ogre_en.ngc'), 'rb').read() == target, msg

        code, msg = _run_apply([path('rom.zip'), path('ogre_en.bps'), '-o', path('zip.ngc')])
        assert code == 0 and open(path('zip.ngc'), 'rb').read() == target, msg

        code, msg = _run_apply([path('ogre_en.bps'), path('orig.ngc'), '-o', path('swap.ngc')])
        assert code == 0 and 'note:' in msg and open(path('swap.ngc'), 'rb').read() == target, msg

        for rom, text in (('english.ngc', 'already patched'), ('other.ngc', 'not the ROM'),
                          ('half.ngc', 'size is wrong'), ('missing.ngc', 'does not exist')):
            code, msg = _run_apply([path(rom), path('ogre_en.bps'), '-o', path('x.ngc')])
            assert code == 1 and text in msg, (rom, msg)

        code, msg = _run_apply([path('ogre_en.bps')])                         # patch only
        assert code == 1 and 'is the patch' in msg, msg

        code, msg = _run_apply([path('orig.ngc'), path('ogre_en.bps'), '-o', path('orig.ngc')])
        assert code == 1 and 'refusing' in msg, msg
        assert open(path('orig.ngc'), 'rb').read() == base

        bad = bytearray(patch)
        bad[100] ^= 1
        with open(path('bad.bps'), 'wb') as f:
            f.write(bad)
        code, msg = _run_apply([path('orig.ngc'), path('bad.bps'), '-o', path('x.ngc')])
        assert code == 1 and 'cannot be used' in msg, msg

        with open(path('ogre_en.sha1'), 'w') as f:
            f.write('0' * 40 + '\n')
        code, msg = _run_apply([path('orig.ngc'), path('ogre_en.bps'), '-o', path('x.ngc')])
        assert code == 1 and 'do not belong together' in msg, msg


# ---------------------------------------------------------------------------
# Runner

SYNTHETIC = [test_numbers, test_handmade_all_actions, test_encoder_round_trips, test_encoder_random_edits,
             test_malformed_patches, test_wrong_source, test_audit]
REAL = [test_real_round_trip, test_real_rejections, test_shipped_patch, test_apply_command]


def write_vectors(folder):
    """Synthetic cases as files, with MANIFEST.txt: name, expected result,
    source file, patch file, target file (or '-')."""
    os.makedirs(folder, exist_ok=True)
    lines = ['# name  expected  source  patch  target', '# expected: ok, or error-patch / '
             'error-source / error-target (damaged patch, wrong source, wrong result)']

    def put(name, data):
        with open(os.path.join(folder, name), 'wb') as f:
            f.write(data)
        return name

    explicit = assemble(EXPLICIT_SOURCE, len(EXPLICIT_TARGET), EXPLICIT_ACTIONS,
                        metadata=b'<test name="all actions"/>', target=EXPLICIT_TARGET)
    lines.append('handmade_all_actions ok %s %s %s' % (
        put('handmade_all_actions.source', EXPLICIT_SOURCE), put('handmade_all_actions.bps', explicit),
        put('handmade_all_actions.target', EXPLICIT_TARGET)))
    for name, s, t in encoder_cases():
        lines.append('%s ok %s %s %s' % (name, put(name + '.source', s), put(name + '.bps', bps.encode(s, t)),
                                         put(name + '.target', t)))
    kinds = {bps.PatchFormatError: 'error-patch', bps.SourceMismatch: 'error-source',
             bps.TargetMismatch: 'error-target'}
    for name, s, patch, cls, what in malformed_cases():
        lines.append('%s %s %s %s -   # %s' % (name, kinds[cls], put(name + '.source', s),
                                               put(name + '.bps', patch), what))
    with open(os.path.join(folder, 'MANIFEST.txt'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    return len(lines) - 2


class Context:
    def __init__(self):
        self.base = self.target = self.patch = None
        self.target_path = None

    def log(self, text):
        print(text)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.patch.test_bps')
    ap.add_argument('rom', nargs='?', help='the original ROM (rom/baserom.ngc)')
    ap.add_argument('--target', default=os.path.join(ROOT, 'build', 'ogre_en.ngc'),
                    help='English ROM for the real round trip (default build/ogre_en.ngc)')
    ap.add_argument('--vectors', help='write the synthetic cases to this folder')
    args = ap.parse_args(argv)

    ctx = Context()
    tests = list(SYNTHETIC)
    if args.rom:
        ctx.base = open(args.rom, 'rb').read()
        if os.path.isfile(args.target):
            ctx.target = open(args.target, 'rb').read()
            ctx.target_path = args.target
            tests += REAL
        else:
            print('note: %s not found; real-ROM tests skipped (run the build first)' % args.target)
    else:
        print('note: no ROM given; real-ROM tests skipped')

    failed = 0
    for test in tests:
        t0 = time.time()
        try:
            test(ctx)
        except Exception:
            failed += 1
            print('FAIL %s' % test.__name__)
            traceback.print_exc()
            if test is test_real_round_trip:
                print('(skipping the other real-ROM tests)')
                break
        else:
            print('ok   %s (%.1f s)' % (test.__name__, time.time() - t0))
    if args.vectors:
        print('wrote %d test vectors to %s' % (write_vectors(args.vectors), args.vectors))
    print('%d tests, %d failed' % (len(tests), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
