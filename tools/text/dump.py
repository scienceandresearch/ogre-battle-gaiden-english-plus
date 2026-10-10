"""Write the Japanese script (from the user's ROM) for translators.

Usage: python -m tools.text.dump rom/baserom.ngc build/script_ja.txt

Output is local only (it contains the original text and is git-ignored).
Each entry is '@ADDR term=XX' followed by the decoded Japanese text; blank
lines separate entries and '# ---' lines mark scene boundaries (a script
terminator between two messages). term=FE waits for a button, term=FC is a
yes/no question.

Only verified message instructions are written. Text that only the
byte-pattern scan finds (raw menu/UI strings and fragments) goes to
build/strings_unverified.txt for review; it is not dialogue.
"""
import bisect
import os
import sys

from ..recomp.rom import Rom
from .extract import build_walker, uncovered_candidates, STAGE_TABLE, NUM_STAGES
from .charmap import decode_bytes

DIALOGUE_TERMS = (0xFE, 0xFC)


def stage_ranges(rom):
    """[(script start, stage number)] sorted by address."""
    return sorted((rom.read24(STAGE_TABLE + 18 * k + 14), k) for k in range(NUM_STAGES))


def context(starts, a):
    if a >> 16 == 0x29:
        return 'opening/prologue'
    i = bisect.bisect_right([s for s, _ in starts], a) - 1
    if i < 0:
        return 'common'
    s, k = starts[i]
    nxt = starts[i + 1][0] if i + 1 < len(starts) else 0x273400
    return 'stage %d' % k if a < nxt else 'common'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rom = Rom(sys.argv[1])
    out = sys.argv[2]
    w = build_walker(rom, log=lambda *a: None)
    starts = stage_ranges(rom)
    msgs = [(a, i) for a, i in w.strings() if i.term in DIALOGUE_TERMS]
    other = [(a, i) for a, i in w.strings() if i.term not in DIALOGUE_TERMS]
    ends = sorted(a for a, i in w.script.items() if i.flow == 'end')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# Japanese script extracted from your ROM (local only; never commit).\n')
        f.write('# %d messages. term=FE: wait for button, term=FC: yes/no question.\n\n' % len(msgs))
        prev, prev_ctx = None, None
        for a, i in msgs:
            ctx = context(starts, a)
            if ctx != prev_ctx:
                f.write('# ===== %s =====\n\n' % ctx)
            elif prev is not None:
                k = bisect.bisect_left(ends, prev)
                if k < len(ends) and ends[k] < a:
                    f.write('# ---\n\n')
            f.write('@%06X term=%02X\n%s\n\n' % (a, i.term, decode_bytes(i.text)))
            prev, prev_ctx = a, ctx
    miss = uncovered_candidates(w, rom)
    rep = os.path.join(os.path.dirname(out) or '.', 'strings_unverified.txt')
    with open(rep, 'w', encoding='utf-8') as f:
        f.write('# Text-like byte runs not covered by verified script code (raw UI text,\n')
        f.write('# fragments). For review only; not part of the dialogue script.\n')
        for a, t, term in miss:
            f.write('%06X [%02X] %s\n' % (a, term, decode_bytes(t).replace('\n', '⏎')))
        for a, i in other:
            f.write('%06X [%02X] (verified, unusual terminator) %s\n' % (
                a, i.term, decode_bytes(i.text).replace('\n', '⏎')))
    print('wrote %d messages to %s' % (len(msgs), out))
    print('wrote %d unverified/unusual items to %s' % (len(miss) + len(other), rep))


if __name__ == '__main__':
    main()
