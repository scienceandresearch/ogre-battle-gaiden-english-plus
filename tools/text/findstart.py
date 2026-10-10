"""Debug helper: find plausible script starts leading to a given address and
references to them. Usage: python -m tools.text.findstart ROM ADDR"""
import sys
from ..recomp.rom import Rom
from .script import decode_script
from .charmap import decode_bytes


def chains_to(rom, target, back=256):
    res = []
    for start in range(target - back, target):
        a, seq, ok = start, [], True
        while a < target:
            ins = decode_script(rom, a)
            if ins.flow == 'bad' or (ins.flow in ('end', 'native') and ins.next < target):
                ok = False
                break
            seq.append(ins)
            a = ins.next
        if ok and a == target and seq:
            res.append((start, seq))
    return res


def refs(rom, addr):
    pat = bytes([addr & 0xFF, (addr >> 8) & 0xFF, addr >> 16])
    out, i = [], rom.data.find(pat)
    while i >= 0:
        out.append(0x200000 + i)
        i = rom.data.find(pat, i + 1)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rom = Rom(sys.argv[1])
    target = int(sys.argv[2], 16)
    for start, seq in chains_to(rom, target):
        r = refs(rom, start)
        if not r and len(seq) < 3:
            continue
        print('start %06X  insns=%d  refs=%s' % (start, len(seq), ' '.join('%06X' % x for x in r[:8])))
    print('direct refs to target:', ' '.join('%06X' % x for x in refs(rom, target)[:10]))


if __name__ == '__main__':
    main()
