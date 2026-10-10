"""Linear disassembler for quick inspection: python -m tools.recomp.disasm ROM ADDR [COUNT]"""
import sys
from .tlcs900 import decode, DecodeError
from .rom import Rom


def main():
    rom = Rom(sys.argv[1])
    addr = int(sys.argv[2], 16)
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    for _ in range(count):
        try:
            insn = decode(rom.read8, addr)
        except DecodeError as e:
            print('%06X: %02X  ?? (%s)' % (addr, rom.read8(addr), e))
            addr += 1
            continue
        print(repr(insn))
        addr = insn.next


if __name__ == '__main__':
    main()
