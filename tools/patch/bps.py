"""BPS patches (the "beat" format by byuu/Near): encoder, decoder, literal audit.

Dependency-free (zlib.crc32 only). Patch layout:

    "BPS1"
    number source-size
    number target-size
    number metadata-size, then metadata-size bytes of metadata
    actions, up to the 12-byte footer; each starts with
        number ((length - 1) << 2) | kind
        kind 0  SourceRead  copy `length` bytes of the source at the output
                            offset (the same offset in both files)
        kind 1  TargetRead  `length` literal bytes follow in the patch
        kind 2  SourceCopy  number (|delta| << 1) | (delta < 0): move the source
                            cursor by delta, copy `length` bytes from it, and
                            advance the cursor by `length`
        kind 3  TargetCopy  the same with a cursor into the target written so
                            far; it must point before the output offset, and
                            the copy runs byte by byte, so it may overlap the
                            bytes it writes (a run-length repeat)
    uint32 CRC32 of the source
    uint32 CRC32 of the target
    uint32 CRC32 of the patch (every byte before this field); little endian

Numbers: 7 bits per byte, least significant group first; the last byte has
bit 7 set, and every continuation byte adds one, so each value has exactly
one encoding (0 -> 80, 127 -> FF, 128 -> 00 80).

The patch must not carry ROM data. The encoder references everything it can
find in the source (SourceRead at the same offset, SourceCopy from anywhere)
and repeats inside the target (TargetCopy); only bytes the source does not
have become literals. `audit` then checks every literal (TargetRead) run: no
run may contain AUDIT_LIMIT (8) or more consecutive bytes that occur anywhere
in the source. `create` encodes, checks that the patch reproduces the target,
and fails when the audit does.

Command line:
    python -m tools.patch.bps create SOURCE TARGET OUT.bps [--metadata TEXT]
    python -m tools.patch.bps apply SOURCE PATCH.bps OUT
    python -m tools.patch.bps audit SOURCE PATCH.bps
    python -m tools.patch.bps info PATCH.bps
"""
import argparse
import re
import struct
import sys
import time
import zlib

MAGIC = b'BPS1'
SOURCE_READ, TARGET_READ, SOURCE_COPY, TARGET_COPY = range(4)
ACTION_NAMES = ('SourceRead', 'TargetRead', 'SourceCopy', 'TargetCopy')
FOOTER_SIZE = 12
MIN_PATCH_SIZE = len(MAGIC) + 3 + FOOTER_SIZE   # magic, three one-byte numbers, footer
MAX_NUMBER = (1 << 64) - 1
MAX_SIZE = 1 << 28           # largest source/target size a patch may declare (256 MiB)

AUDIT_LIMIT = 8              # literals must not hold this many consecutive source bytes

# Encoder tuning. WINDOW must not exceed AUDIT_LIMIT: the WINDOW bytes starting
# at every position that could become a literal are looked up in the source,
# so no literal can hold WINDOW bytes that occur in the source.
WINDOW = AUDIT_LIMIT
TARGET_WINDOW = 6            # shortest repeat inside the target used for TargetCopy
FAST_READ = 32               # unchanged runs this long become SourceRead at once
SOURCE_CANDIDATES = 16       # source positions kept per window
TARGET_CANDIDATES = 8        # most recent target positions kept per window


class BpsError(Exception):
    """A problem with a patch or with the file it is applied to."""


class PatchFormatError(BpsError):
    """The patch is damaged, truncated or not a BPS patch."""


class SourceMismatch(BpsError):
    """The file given as the source is not the patch's source."""

    def __init__(self, message, already_patched=False):
        BpsError.__init__(self, message)
        self.already_patched = already_patched


class TargetMismatch(BpsError):
    """The patched result does not match the target checksum."""


class AuditError(BpsError):
    """A literal of the patch carries bytes that occur in the source."""

    def __init__(self, report):
        BpsError.__init__(self, report.summary())
        self.report = report


# ---------------------------------------------------------------------------
# Numbers

def encode_number(value, out):
    """Append `value` (0 or more) to the bytearray `out` in BPS encoding."""
    if value < 0:
        raise ValueError('BPS numbers are unsigned (%d)' % value)
    while True:
        x = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(0x80 | x)
            return
        out.append(x)
        value -= 1


def number_bytes(value):
    """The encoding of `value` as bytes."""
    out = bytearray()
    encode_number(value, out)
    return bytes(out)


def number_size(value):
    """How many bytes `encode_number` writes for `value`."""
    n = 1
    while value >= 0x80:
        value = (value >> 7) - 1
        n += 1
    return n


def decode_number(buf, pos, end):
    """Read a number from buf[pos:end]. Returns (value, position after it)."""
    value = 0
    shift = 1
    start = pos
    while True:
        if pos >= end:
            raise PatchFormatError('truncated number at patch offset %d' % start)
        x = buf[pos]
        pos += 1
        value += (x & 0x7F) * shift
        if x & 0x80:
            break
        shift <<= 7
        value += shift
        if value > MAX_NUMBER:
            break
    if value > MAX_NUMBER:
        raise PatchFormatError('number too large at patch offset %d' % start)
    return value, pos


def offset_number(delta):
    """The number that encodes a relative cursor move of `delta`."""
    return ((-delta) << 1) | 1 if delta < 0 else delta << 1


# ---------------------------------------------------------------------------
# Decoder

class Patch:
    """A parsed patch whose structure has been fully validated.

    `actions` holds (kind, target offset, length, arg): arg is the source
    offset for SourceRead/SourceCopy, the offset of the literal bytes inside
    the patch for TargetRead, and the target offset copied from for TargetCopy.
    """

    def __init__(self, data, source_size, target_size, metadata, actions,
                 source_crc, target_crc, patch_crc):
        self.data = data
        self.source_size = source_size
        self.target_size = target_size
        self.metadata = metadata
        self.actions = actions
        self.source_crc = source_crc
        self.target_crc = target_crc
        self.patch_crc = patch_crc

    def literals(self):
        """(target offset, bytes) of every TargetRead."""
        d = self.data
        return [(o, d[a:a + n]) for k, o, n, a in self.actions if k == TARGET_READ]

    def stats(self):
        """([number of actions], [bytes written]) per action kind."""
        counts, sizes = [0] * 4, [0] * 4
        for k, o, n, a in self.actions:
            counts[k] += 1
            sizes[k] += n
        return counts, sizes

    def describe(self):
        counts, sizes = self.stats()
        lines = ['BPS patch: %s bytes, CRC32 %08X' % (format(len(self.data), ','), self.patch_crc),
                 'source: %s bytes, CRC32 %08X' % (format(self.source_size, ','), self.source_crc),
                 'target: %s bytes, CRC32 %08X' % (format(self.target_size, ','), self.target_crc),
                 'metadata: %d bytes' % len(self.metadata)]
        for k in range(4):
            lines.append('  %-10s %7s actions %11s bytes' % (
                ACTION_NAMES[k], format(counts[k], ','), format(sizes[k], ',')))
        return '\n'.join(lines)


def parse(patch, max_size=MAX_SIZE):
    """Parse and validate a patch: signature, patch checksum, numbers, and
    the bounds of every action (sizes from the header). Returns a Patch."""
    data = bytes(patch)
    if len(data) < MIN_PATCH_SIZE:
        raise PatchFormatError('too short to be a BPS patch (%d bytes)' % len(data))
    if data[:4] != MAGIC:
        raise PatchFormatError('not a BPS patch (no "BPS1" signature)')
    source_crc, target_crc, patch_crc = struct.unpack_from('<III', data, len(data) - FOOTER_SIZE)
    if zlib.crc32(data[:-4]) != patch_crc:
        raise PatchFormatError('patch checksum mismatch: the file is damaged or incomplete')
    end = len(data) - FOOTER_SIZE
    source_size, pos = decode_number(data, 4, end)
    target_size, pos = decode_number(data, pos, end)
    meta_size, pos = decode_number(data, pos, end)
    if source_size > max_size or target_size > max_size:
        raise PatchFormatError('the patch declares a %d-byte source and a %d-byte target '
                               '(limit %d)' % (source_size, target_size, max_size))
    if meta_size > end - pos:
        raise PatchFormatError('metadata runs past the end of the patch')
    metadata = data[pos:pos + meta_size]
    pos += meta_size

    actions = []
    out = src = tgt = 0
    while pos < end:
        at = pos
        n, pos = decode_number(data, pos, end)
        kind, length = n & 3, (n >> 2) + 1
        if length > target_size - out:
            raise PatchFormatError('%s at patch offset %d writes past the end of the target'
                                   % (ACTION_NAMES[kind], at))
        if kind == SOURCE_READ:
            if out + length > source_size:
                raise PatchFormatError('SourceRead at patch offset %d reads past the end of the source' % at)
            actions.append((kind, out, length, out))
        elif kind == TARGET_READ:
            if length > end - pos:
                raise PatchFormatError('TargetRead at patch offset %d runs past the end of the patch' % at)
            actions.append((kind, out, length, pos))
            pos += length
        else:
            v, pos = decode_number(data, pos, end)
            delta = -(v >> 1) if v & 1 else v >> 1
            if kind == SOURCE_COPY:
                src += delta
                if src < 0 or src + length > source_size:
                    raise PatchFormatError('SourceCopy at patch offset %d reads outside the source' % at)
                actions.append((kind, out, length, src))
                src += length
            else:
                tgt += delta
                if tgt < 0 or tgt >= out:
                    raise PatchFormatError('TargetCopy at patch offset %d reads target data not written yet' % at)
                actions.append((kind, out, length, tgt))
                tgt += length
        out += length
    if out != target_size:
        raise PatchFormatError('the patch writes %d bytes of a %d-byte target' % (out, target_size))
    return Patch(data, source_size, target_size, metadata, actions, source_crc, target_crc, patch_crc)


def apply(source, patch, check_source=True):
    """Apply `patch` (bytes or a Patch) to `source`; returns the target bytes.

    Raises PatchFormatError for a damaged patch, SourceMismatch when `source`
    is not the patch's source (with .already_patched set when it is the
    target instead) and TargetMismatch when the result's CRC32 is wrong."""
    p = patch if isinstance(patch, Patch) else parse(patch)
    crc = None
    if len(source) != p.source_size or check_source:
        crc = zlib.crc32(source)
    if len(source) != p.source_size or (check_source and crc != p.source_crc):
        already = len(source) == p.target_size and crc == p.target_crc
        if already:
            raise SourceMismatch('the file is already patched (it matches the patch target)', True)
        raise SourceMismatch('the file does not match the patch source: %d bytes with CRC32 %08X, '
                             'expected %d bytes with CRC32 %08X'
                             % (len(source), crc, p.source_size, p.source_crc))
    out = bytearray(p.target_size)
    data = p.data
    for kind, o, n, a in p.actions:
        if kind == SOURCE_READ or kind == SOURCE_COPY:
            out[o:o + n] = source[a:a + n]
        elif kind == TARGET_READ:
            out[o:o + n] = data[a:a + n]
        else:
            dist = o - a
            if dist >= n:
                out[o:o + n] = out[a:a + n]
            else:                       # overlapping copy: the last `dist` bytes repeat
                pattern = bytes(out[a:o])
                out[o:o + n] = (pattern * (n // dist + 1))[:n]
    crc = zlib.crc32(out)
    if crc != p.target_crc:
        raise TargetMismatch('the result has CRC32 %08X, the patch expects %08X' % (crc, p.target_crc))
    return bytes(out)


# ---------------------------------------------------------------------------
# Encoder

_CHANGED = re.compile(rb'[^\x00]+')


def _changed_spans(source, target):
    """[start, end) spans of target offsets whose byte differs from the source
    byte at the same offset; offsets past the end of the source are changed."""
    n = min(len(source), len(target))
    spans = []
    if n:
        x = int.from_bytes(source[:n], 'little') ^ int.from_bytes(target[:n], 'little')
        spans = [m.span() for m in _CHANGED.finditer(x.to_bytes(n, 'little'))]
    if len(target) > n:
        if spans and spans[-1][1] == n:
            spans[-1] = (spans[-1][0], len(target))
        else:
            spans.append((n, len(target)))
    return spans


def _common(a, ai, b, bi, limit):
    """Length of the common prefix of a[ai:ai+limit] and b[bi:bi+limit]."""
    n = 0
    step = 16
    while n < limit:
        m = min(step, limit - n)
        if a[ai + n:ai + n + m] == b[bi + n:bi + n + m]:
            n += m
            step <<= 1
            continue
        lo, hi = 0, m                   # equal for lo bytes, different within hi
        while hi - lo > 1:
            mid = (lo + hi) >> 1
            if a[ai + n:ai + n + mid] == b[bi + n:bi + n + mid]:
                lo = mid
            else:
                hi = mid
        return n + lo
    return n


class _SourceIndex:
    """Where WINDOW-byte pieces of the target occur in the source.

    Only the pieces in `wanted` (the ones the encoder may look up) are indexed,
    up to SOURCE_CANDIDATES positions each; inside a run of one byte value
    only the run's start is kept, and the longest run of that value is offered
    first. A piece outside `wanted` is searched for directly, so lookups are
    always exact."""

    def __init__(self, source, wanted):
        self.source = source
        self.wanted = wanted
        self.runs = {}
        cands = {}
        if wanted:
            w_len = WINDOW
            for i in range(len(source) - w_len + 1):
                w = source[i:i + w_len]
                if w in wanted:
                    lst = cands.get(w)
                    if lst is None:
                        cands[w] = [i]
                    elif len(lst) < SOURCE_CANDIDATES and source[i - 1:i - 1 + w_len] != w:
                        lst.append(i)
        self.cands = cands

    def longest_run(self, v):
        r = self.runs.get(v)
        if r is None:
            r = (-1, 0)
            pat = re.compile(re.escape(bytes((v,))) + b'{%d,}' % WINDOW)
            for m in pat.finditer(self.source):
                if m.end() - m.start() > r[1]:
                    r = (m.start(), m.end() - m.start())
            self.runs[v] = r
        return r

    def lookup(self, w):
        lst = self.cands.get(w)
        if lst is None:
            if w in self.wanted:
                return ()
            i = self.source.find(w)
            return (i,) if i >= 0 else ()
        if w.count(w[:1]) == len(w):
            start = self.longest_run(w[0])[0]
            if start >= 0 and start not in lst:
                return [start] + lst
        return lst


def _remember(tindex, target, p):
    key = target[p:p + TARGET_WINDOW]
    lst = tindex.get(key)
    if lst is None:
        tindex[key] = [p]
    else:
        lst.append(p)
        if len(lst) > TARGET_CANDIDATES:
            del lst[0]


def encode_actions(source, target):
    """Greedy encoding. Returns [(kind, arg, length)], arg being the target
    offset (SourceRead, TargetRead), the source offset (SourceCopy) or the
    target offset copied from (TargetCopy)."""
    ls, lt = len(source), len(target)
    w_len, tw_len = WINDOW, TARGET_WINDOW
    spans = _changed_spans(source, target)

    # The encoder only looks pieces up at changed bytes and in the FAST_READ
    # bytes before a change (anywhere else SourceRead is taken at once).
    wanted = set()
    done = 0
    for a, b in spans:
        lo, hi = max(a - FAST_READ, done), min(b, lt - w_len + 1)
        if lo < hi:
            wanted.update(target[p:p + w_len] for p in range(lo, hi))
        done = max(done, b)
    index = _SourceIndex(source, wanted)

    starts = [a for a, _ in spans]
    ends = [b for _, b in spans]
    nspans = len(spans)
    si = 0
    actions = []
    tindex = {}
    lit = -1                            # start of the pending literal run
    src_cur = tgt_cur = 0
    pos = 0
    while pos < lt:
        while si < nspans and ends[si] <= pos:
            si += 1
        if si < nspans and starts[si] <= pos:
            sr = 0
        else:
            sr = (starts[si] if si < nspans else lt) - pos
            if sr >= FAST_READ or pos + sr == lt:
                if lit >= 0:
                    actions.append((TARGET_READ, lit, pos - lit))
                    lit = -1
                actions.append((SOURCE_READ, pos, sr))
                pos += sr
                continue

        # Changed region: pick the action that saves the most patch bytes.
        # A piece of WINDOW bytes found in the source forces a non-literal.
        penalty = 1 if lit >= 0 else 0     # a copy splits the literal run
        best = None
        gain = 0
        forced = sr >= w_len
        if sr:
            best = (SOURCE_READ, pos, sr)
            gain = sr - number_size((sr - 1) << 2) - penalty
        if pos + w_len <= lt:
            cands = index.lookup(target[pos:pos + w_len])
            if cands:
                forced = True
                room = lt - pos
                for c in cands:
                    n = w_len + _common(source, c + w_len, target, pos + w_len, min(ls - c, room) - w_len)
                    g = (n - number_size(((n - 1) << 2) | SOURCE_COPY)
                         - number_size(offset_number(c - src_cur)) - penalty)
                    if best is None or g > gain:
                        best, gain = (SOURCE_COPY, c, n), g
        if pos + tw_len <= lt:
            tl = tindex.get(target[pos:pos + tw_len])
            if tl:
                room = lt - pos - tw_len
                for q in reversed(tl):
                    n = tw_len + _common(target, q + tw_len, target, pos + tw_len, room)
                    g = (n - number_size(((n - 1) << 2) | TARGET_COPY)
                         - number_size(offset_number(q - tgt_cur)) - penalty)
                    if best is None or g > gain:
                        best, gain = (TARGET_COPY, q, n), g

        if best is not None and (gain > 0 or forced):
            if lit >= 0:
                actions.append((TARGET_READ, lit, pos - lit))
                lit = -1
            kind, arg, n = best
            actions.append(best)
            if kind == SOURCE_COPY:
                src_cur = arg + n
            elif kind == TARGET_COPY:
                tgt_cur = arg + n
                for p in range(pos, min(pos + n, lt - tw_len + 1)):
                    _remember(tindex, target, p)
            pos += n
        else:
            if lit < 0:
                lit = pos
            if pos + tw_len <= lt:
                _remember(tindex, target, pos)
            pos += 1
    if lit >= 0:
        actions.append((TARGET_READ, lit, lt - lit))
    return actions


def serialize(actions, source, target, metadata=b''):
    """Write a patch from encoder actions [(kind, arg, length)]."""
    out = bytearray(MAGIC)
    encode_number(len(source), out)
    encode_number(len(target), out)
    encode_number(len(metadata), out)
    out += metadata
    src_cur = tgt_cur = 0
    for kind, arg, n in actions:
        encode_number(((n - 1) << 2) | kind, out)
        if kind == TARGET_READ:
            out += target[arg:arg + n]
        elif kind == SOURCE_COPY:
            encode_number(offset_number(arg - src_cur), out)
            src_cur = arg + n
        elif kind == TARGET_COPY:
            encode_number(offset_number(arg - tgt_cur), out)
            tgt_cur = arg + n
    out += struct.pack('<II', zlib.crc32(source), zlib.crc32(target))
    out += struct.pack('<I', zlib.crc32(out))
    return bytes(out)


def encode(source, target, metadata=b''):
    """Make a patch that turns `source` into `target` (no audit; see create)."""
    source, target = bytes(source), bytes(target)
    if isinstance(metadata, str):
        metadata = metadata.encode('utf-8')
    return serialize(encode_actions(source, target), source, target, bytes(metadata))


def create(source, target, metadata=b'', limit=AUDIT_LIMIT):
    """Encode, check that the patch reproduces `target`, and audit it.

    Returns (patch bytes, AuditReport). Raises AuditError when a literal holds
    `limit` or more consecutive bytes that occur in the source."""
    source, target = bytes(source), bytes(target)
    patch = encode(source, target, metadata)
    parsed = parse(patch)
    if apply(source, parsed) != target:
        raise BpsError('internal error: the new patch does not reproduce the target')
    report = audit(source, parsed, limit)
    if not report.ok:
        raise AuditError(report)
    return patch, report


# ---------------------------------------------------------------------------
# Audit

class AuditReport:
    """Result of `audit`.

    literal_bytes / literal_runs: size and number of the TargetRead runs.
    longest: the longest run of consecutive literal bytes that also occurs
    somewhere in the source; example: (target offset, length, source offset)
    of one such run. offenders: every literal piece of `limit` or more bytes
    found in the source, as (target offset, length, source offset)."""

    def __init__(self, limit, literal_bytes, literal_runs, longest, example, offenders):
        self.limit = limit
        self.literal_bytes = literal_bytes
        self.literal_runs = literal_runs
        self.longest = longest
        self.example = example
        self.offenders = offenders
        self.ok = not offenders

    def summary(self):
        lits = '%s literal bytes in %s runs' % (format(self.literal_bytes, ','), format(self.literal_runs, ','))
        if self.ok:
            return ('OK: %s; longest literal run found in the source: %d bytes (limit %d)'
                    % (lits, self.longest, self.limit))
        o, n, s = max(self.offenders, key=lambda t: t[1])
        return ('FAILED: %s; %d literal runs of %d or more bytes occur in the source, the longest '
                '%d bytes at target offset 0x%X (source offset 0x%X)'
                % (lits, len(self.offenders), self.limit, n, o, s))


def _source_hits(source, pieces, k, find_all):
    """{piece: first source offset} for the k-byte pieces of `source` that are
    in `pieces`; stops at the first one unless find_all."""
    hits = {}
    if pieces:
        for i in range(len(source) - k + 1):
            g = source[i:i + k]
            if g in pieces and g not in hits:
                hits[g] = i
                if not find_all:
                    break
    return hits


def _longest_in_source(source, data, j, n):
    """Largest m >= n such that data[j:j+m] occurs in source (data[j:j+n] does)."""
    top = len(data) - j
    step = 1
    while n < top:
        m = min(n + step, top)
        if source.find(data[j:j + m]) < 0:
            lo, hi = n, m
            while hi - lo > 1:
                mid = (lo + hi) >> 1
                if source.find(data[j:j + mid]) >= 0:
                    lo = mid
                else:
                    hi = mid
            return lo
        n = m
        step <<= 1
    return n


def audit(source, patch, limit=AUDIT_LIMIT):
    """Check that no literal (TargetRead) run of `patch` contains `limit` or
    more consecutive bytes that occur anywhere in `source`."""
    source = bytes(source)
    p = patch if isinstance(patch, Patch) else parse(patch)
    lits = p.literals()
    total = sum(len(d) for _, d in lits)

    pieces = {}
    for off, d in lits:
        for j in range(len(d) - limit + 1):
            pieces.setdefault(d[j:j + limit], off + j)
    hits = _source_hits(source, pieces, limit, True)
    offenders = []
    if hits:
        for off, d in lits:
            j = 0
            while j + limit <= len(d):
                if d[j:j + limit] in hits:
                    n = _longest_in_source(source, d, j, limit)
                    offenders.append((off + j, n, source.find(d[j:j + n])))
                    j += n
                else:
                    j += 1
        example = max(offenders, key=lambda t: t[1])
        return AuditReport(limit, total, len(lits), example[1], example, offenders)

    for k in range(limit - 1, 0, -1):
        pieces = {}
        for off, d in lits:
            for j in range(len(d) - k + 1):
                pieces.setdefault(d[j:j + k], off + j)
        hits = _source_hits(source, pieces, k, False)
        if hits:
            g, s = next(iter(hits.items()))
            return AuditReport(limit, total, len(lits), k, (pieces[g], k, s), [])
    return AuditReport(limit, total, len(lits), 0, None, [])


# ---------------------------------------------------------------------------
# Command line

def _read(path):
    with open(path, 'rb') as f:
        return f.read()


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.patch.bps', description='BPS patch tool.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('create', help='make a patch from SOURCE to TARGET (audited)')
    c.add_argument('source')
    c.add_argument('target')
    c.add_argument('out')
    c.add_argument('--metadata', default='', help='metadata text stored in the patch (UTF-8)')
    a = sub.add_parser('apply', help='apply PATCH to SOURCE and write OUT')
    a.add_argument('source')
    a.add_argument('patch')
    a.add_argument('out')
    u = sub.add_parser('audit', help='check that no literal of PATCH carries SOURCE data')
    u.add_argument('source')
    u.add_argument('patch')
    i = sub.add_parser('info', help='describe PATCH')
    i.add_argument('patch')
    args = ap.parse_args(argv)

    try:
        if args.cmd == 'create':
            t0 = time.time()
            patch, report = create(_read(args.source), _read(args.target), args.metadata)
            with open(args.out, 'wb') as f:
                f.write(patch)
            print(parse(patch).describe())
            print('audit:', report.summary())
            print('wrote %s (%.1f s)' % (args.out, time.time() - t0))
        elif args.cmd == 'apply':
            out = apply(_read(args.source), _read(args.patch))
            with open(args.out, 'wb') as f:
                f.write(out)
            print('wrote %s (%s bytes, CRC32 %08X)' % (args.out, format(len(out), ','), zlib.crc32(out)))
        elif args.cmd == 'audit':
            report = audit(_read(args.source), _read(args.patch))
            print('audit:', report.summary())
            for o, n, s in report.offenders[:20]:
                print('  target 0x%X: %d bytes also at source 0x%X' % (o, n, s))
            return 0 if report.ok else 1
        else:
            print(parse(_read(args.patch)).describe())
    except (BpsError, OSError) as e:
        print('error: %s' % e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
