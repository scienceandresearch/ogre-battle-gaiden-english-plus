"""Cartridge ROM image access (CS0 mapped at 0x200000)."""
import hashlib

ROM_BASE = 0x200000

# The one supported dump: "Densetsu no Ogre Battle Gaiden - Zenobia no Ouji (Japan)".
EXPECTED_SHA1 = '5ac794c0f125bfb97efe9cd06c2aca3afdf549ea'


class Rom:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = f.read()
        self.sha1 = hashlib.sha1(self.data).hexdigest()
        self.size = len(self.data)

    def contains(self, addr):
        return ROM_BASE <= addr < ROM_BASE + self.size

    def read8(self, addr):
        off = addr - ROM_BASE
        if 0 <= off < self.size:
            return self.data[off]
        return 0xFF

    def read16(self, addr):
        return self.read8(addr) | (self.read8(addr + 1) << 8)

    def read24(self, addr):
        return self.read16(addr) | (self.read8(addr + 2) << 16)

    def read32(self, addr):
        return self.read16(addr) | (self.read16(addr + 2) << 16)

    def bytes(self, addr, n):
        off = addr - ROM_BASE
        return self.data[off:off + n]
