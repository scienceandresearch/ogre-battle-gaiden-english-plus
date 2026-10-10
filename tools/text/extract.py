"""Find all script bytecode and inline text in the ROM.

Usage: python -m tools.text.extract rom/baserom.ngc [--dump OUT.txt]
"""
import sys

from ..recomp.rom import Rom, ROM_BASE
from ..recomp.analyze import Analysis
from .script import Walker, OPS, decode_script
from .charmap import decode_bytes
from .textscore import TextScorer


def native_reenters_known(rom, w, a, limit=64):
    """Linear decode of a short native segment. Returns True if it re-enters
    the VM (call 0x20023C) at verified script code, False if it re-enters at
    unknown code or ends otherwise, None if it does not decode cleanly."""
    from ..recomp.tlcs900 import decode, DecodeError
    for _ in range(limit):
        try:
            ins = decode(rom.read8, a)
        except DecodeError:
            return None
        if ins.kind == 'call' and ins.target == 0x20023C:
            return ins.next in w.script
        if ins.kind in ('jump', 'ret', 'reti', 'ijump') and ins.cond in (None, 8):
            return False
        a = ins.next
    return False


def coverage(w):
    """Map every byte of verified script code to the start of its instruction."""
    return w.cover


def overlaps(cover, a, length):
    return any(b in cover for b in range(a, a + length))


def validate_candidate(rom, w, scorer, v, max_insns=400, lenient=False, cover=None):
    """Decode bytecode speculatively from v; accept when it merges into
    verified script code, or ends properly while producing natural text.
    `lenient` is for entry points named by structured tables (event lists):
    their text only has to be printable and not data-like, so stylised lines
    (e.g. a villain speaking all in katakana) are not rejected."""
    known = w.script
    if cover is None:
        cover = coverage(w)
    a, n, strings, merged, last, seen = v, 0, [], False, None, set()
    while n < max_insns:
        if a in known:
            merged = True
            break
        if a in seen or not rom.contains(a):
            break
        seen.add(a)
        ins = decode_script(rom, a)
        if ins.flow == 'bad':
            return False
        # real script never overlaps itself: a path that runs into the middle
        # of verified code (or starts inside it) is data or a misaligned entry
        if overlaps(cover, a, ins.length):
            return False
        if ins.op == 0x32:
            strings.append(ins.text)
        n += 1
        last = ins
        if ins.flow == 'native':
            merged = native_reenters_known(rom, w, ins.next)
            if merged is None:
                return False
            break
        if ins.op == 0xDA:          # unconditional jump: keep following
            a = ins.targets[0][1]
            continue
        if ins.flow == 'end':
            break
        a = ins.next
    if n == 0:
        return False
    if lenient:
        text_ok = scorer.strings_look_like_text(strings, combined=-0.5, floor=-2.0)
    else:
        text_ok = scorer.strings_look_like_text(strings)
    if strings and not text_ok:
        return False
    if lenient:
        # a listed handler may hold no text itself and only arm another
        # script (`st32 <script>, 0x61F0`); clean decoding is enough
        return merged or (n >= 2 and last is not None and last.flow == 'end')
    return merged or (bool(strings) and n >= 3 and last is not None and last.flow == 'end')


def fallthrough_search(w, rom):
    """Script chunks are laid out back to back: try the byte after every
    terminating instruction (stop/jump/ret/switch) as a new chunk."""
    scorer = TextScorer([i.text for _, i in w.strings()])
    cover = coverage(w)
    accepted = []
    for a, ins in list(w.script.items()):
        if ins.flow != 'end':
            continue
        v = ins.next
        # skip 0xF6/0xFF padding runs between chunks
        while rom.contains(v) and rom.read8(v) in (0xF6, 0xFF) and v - ins.next < 64:
            v += 1
        if v in w.script or v in w.script_entries or not rom.contains(v):
            continue
        if validate_candidate(rom, w, scorer, v, cover=cover):
            accepted.append(v)
    for v in accepted:
        w.add_script(v, 'fallthrough')
    return accepted


def pointer_search(w, rom, lo=0x220000, hi=0x380000):
    """Accept 24-bit values found anywhere in the ROM as script entry points
    when bytecode decoded from them is clean, does not overlap verified code,
    and either merges into verified script code or yields only
    natural-looking Japanese text."""
    scorer = TextScorer([i.text for _, i in w.strings()])
    cover = coverage(w)
    known = w.script
    data = rom.data
    cands = set()
    for off in range(len(data) - 2):
        v = data[off] | (data[off + 1] << 8) | (data[off + 2] << 16)
        if lo <= v < hi and v not in known and v not in w.script_entries and v not in cover:
            cands.add(v)
    accepted = [v for v in sorted(cands) if validate_candidate(rom, w, scorer, v, cover=cover)]
    for v in accepted:
        w.add_script(v, 'ptrsearch')
    return accepted


def seed_walker(rom):
    w = Walker(rom)
    data = rom.data
    # 1. every `call 0x20023C` (24-bit absolute form) is followed by inline bytecode
    pat = bytes([0x1D, 0x3C, 0x02, 0x20])
    i = data.find(pat)
    while i >= 0:
        w.add_script(ROM_BASE + i + 4, 'scan-inline@%06X' % (ROM_BASE + i))
        i = data.find(pat, i + 1)
    # 2. stage records (20 x 18 bytes at 0x2261D9): +0 event table, +10 map,
    #    +14 stage script. Event tables list handlers as 16-bit offsets from
    #    the stage script; they are added later by stage_event_search().
    for k in range(NUM_STAGES):
        rec = STAGE_TABLE + 18 * k
        w.add_script(rom.read24(rec + 14), 'stage%02d' % k)
    return w


STAGE_TABLE = 0x2261D9
NUM_STAGES = 20
_END_OPS = {0xE0, 0xE2, 0x84, 0x80, 0xDA}


def stage_event_lists(rom):
    """Yield (stage script, handler offset, location id) for the event lists in
    the stage event tables. A list is a run of 4-byte entries
    [u16 offset][u8 location id][u8 town id or 0] whose location ids count up
    by one (ids are global across stages: stage 1 has 05-0C, stage 2 0D-15,
    ...); offset 0 means "no event". The run is followed by one entry with a
    different id and a zero last byte: the stage's main event handler.
    Handler offsets are relative to the stage script and stay inside it.
    Each stage table holds exactly one such list (the first match); location
    ids continue across stages (stage 0: 01-04, ..., stage 19: E2-EA)."""
    recs = [(rom.read24(STAGE_TABLE + 18 * k), rom.read24(STAGE_TABLE + 18 * k + 14))
            for k in range(NUM_STAGES)]
    tables = sorted(t for t, _ in recs)
    scripts = sorted(s for _, s in recs)
    for table, script in recs:
        end = min([t for t in tables if t > table] + [table + 0x400])
        limit = min([s for s in scripts if s > script] + [script + 0x4000]) - script

        def entry(q):
            return rom.read16(q), rom.read8(q + 2), rom.read8(q + 3)

        def ok(e):
            off, lid, town = e
            return off < limit and town < 0x80

        p = table
        while p + 12 <= end:
            e = [entry(p + 4 * i) for i in range(3)]
            if not (all(ok(x) for x in e) and any(x[0] for x in e) and
                    e[1][1] == e[0][1] + 1 and e[2][1] == e[1][1] + 1):
                p += 1
                continue
            q, prev = p, e[0][1] - 1
            while q + 4 <= end:
                x = entry(q)
                if x[1] != prev + 1 or not ok(x):
                    break
                if x[0]:
                    yield script, x[0], x[1]
                prev = x[1]
                q += 4
            if q + 4 <= end:
                off, lid, town = entry(q)
                if town == 0 and 0 < off < limit:
                    yield script, off, lid
            break       # one location list per stage; later matches are other data


def stage_event_search(w, rom):
    """Add event handlers named by the stage event tables: entries of the
    structured event lists, plus any 16-bit value in a table that points at an
    event-handler prologue directly after a terminating instruction."""
    scorer = TextScorer([i.text for _, i in w.strings()])
    listed = [script + off for script, off, lid in stage_event_lists(rom)]
    cands = list(listed)
    tables = sorted(rom.read24(STAGE_TABLE + 18 * k) for k in range(NUM_STAGES))
    for k in range(NUM_STAGES):
        rec = STAGE_TABLE + 18 * k
        table, script = rom.read24(rec), rom.read24(rec + 14)
        end = min([t for t in tables if t > table] + [table + 0x400])
        for p in range(table, end - 1):
            v = rom.read16(p)
            t = script + v
            if not (0x10 <= v < 0x8000) or rom.read8(t) not in (0xDE, 0x38, 0x3A, 0x36, 0x86, 0x32):
                continue
            after_end = any(t - n in w.script and w.script[t - n].next == t and
                            w.script[t - n].flow == 'end' for n in range(1, 6))
            if after_end or rom.read8(t - 1) in _END_OPS:
                cands.append(t)
    cover = coverage(w)
    accepted = []
    for t in dict.fromkeys(cands):
        if t in w.script or t in w.script_entries:
            continue
        if validate_candidate(rom, w, scorer, t, lenient=t in listed, cover=cover):
            accepted.append(t)
    for t in accepted:
        w.add_script(t, 'stage-event')
    return accepted


def build_walker(rom, log=print):
    """Walk from trusted entry points, then expand with progressively less
    certain searches: structural (stage event lists), layout (fall-through
    after terminators), and only when those have converged, the broad
    pointer search. Each accepted batch is walked before the next search so
    that more trusted code claims its bytes first."""
    w = seed_walker(rom)
    w.run()
    for it in range(40):
        acc3 = stage_event_search(w, rom)
        w.run()
        acc2 = fallthrough_search(w, rom)
        w.run()
        acc = []
        if not acc3 and not acc2:
            acc = pointer_search(w, rom)
            w.run()
        log('expansion pass %d: %d stage-event, %d fall-through, %d pointer entries' % (
            it, len(acc3), len(acc2), len(acc)))
        if not acc and not acc2 and not acc3:
            break
    return w


def uncovered_candidates(w, rom, threshold=1.0):
    """`0x32 <text> FE/FC` sequences that look like dialogue but are not
    covered by verified code (neither a verified string nor inside any other
    verified script or native instruction). What remains is mostly raw
    menu/UI text, which has no 0x32 prefix of its own (0x32 is also a kana
    character code)."""
    covered = set(w.cover)
    for a, ins in w.native.items():
        covered.update(range(a, ins.next))
    scorer = TextScorer([i.text for _, i in w.strings()])
    d = rom.data
    miss = []
    for off in range(len(d)):
        if d[off] != 0x32:
            continue
        a = ROM_BASE + off
        if a in covered:
            continue
        j = off + 1
        while j < len(d) and d[j] < 0xDF and j - off < 300:
            j += 1
        if j >= len(d) or d[j] not in (0xFE, 0xFC):
            continue
        t = d[off + 1:j]
        if len(t) >= 3 and scorer.looks_like_text(t, threshold):
            miss.append((a, t, d[j]))
    return miss


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rom = Rom(sys.argv[1])
    w = build_walker(rom, log=lambda *a: None)
    strs = w.strings()
    nbytes = sum(len(i.text) for _, i in strs)
    print('script insns: %d  native insns: %d  script entries: %d' % (len(w.script), len(w.native), len(w.script_entries)))
    print('text strings: %d  text bytes: %d' % (len(strs), nbytes))
    print('bad: %d' % len(w.bad))
    terms = {}
    for _, i in strs:
        terms[i.term] = terms.get(i.term, 0) + 1
    print('terminators:', {('%02X' % k): v for k, v in sorted(terms.items())})
    if '--dump' in sys.argv:
        out = sys.argv[sys.argv.index('--dump') + 1]
        with open(out, 'w', encoding='utf-8') as f:
            for a, i in strs:
                f.write('%06X [%02X] %s\n' % (a, i.term, decode_bytes(i.text).replace('\n', '⏎')))
        print('wrote', out)
    miss = uncovered_candidates(w, rom)
    print('uncovered candidates: %d (%d bytes)' % (len(miss), sum(len(t) for _, t, _ in miss)))
    with open('build/strings_missed.txt', 'w', encoding='utf-8') as f:
        for a, t, term in miss:
            f.write('%06X [%02X] %s\n' % (a, term, decode_bytes(t).replace('\n', '⏎')))
    if '--bad' in sys.argv:
        for a in sorted(w.bad):
            print('BAD %06X %s' % (a, w.bad[a]))


if __name__ == '__main__':
    main()
