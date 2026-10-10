"""Read what the release needs from a Windows executable (PE32/PE32+):
resources (version information, icon groups) and imported DLLs.

    python -m tools.release.pe FILE.exe      print version, icon sizes, imports

Standard library only; raises PEError for anything that is not a well-formed
PE file.
"""
import struct
import sys

RT_ICON = 3
RT_GROUP_ICON = 14
RT_VERSION = 16
RT_MANIFEST = 24

VS_FIXEDFILEINFO_SIGNATURE = 0xFEEF04BD


class PEError(Exception):
    pass


class PE:
    def __init__(self, data):
        self.data = data = bytes(data)
        if data[:2] != b'MZ' or len(data) < 0x40:
            raise PEError('not an executable (no MZ header)')
        pe = struct.unpack_from('<I', data, 0x3C)[0]
        if data[pe:pe + 4] != b'PE\0\0':
            raise PEError('not a PE executable')
        self.machine, nsec = struct.unpack_from('<HH', data, pe + 4)
        self.timestamp = struct.unpack_from('<I', data, pe + 8)[0]
        optsize = struct.unpack_from('<H', data, pe + 20)[0]
        opt = pe + 24
        magic = struct.unpack_from('<H', data, opt)[0]
        if magic not in (0x10B, 0x20B):
            raise PEError('unknown optional header (magic %04X)' % magic)
        self.pe32_plus = magic == 0x20B
        ddir = opt + (112 if self.pe32_plus else 96)
        ndirs = struct.unpack_from('<I', data, ddir - 4)[0]
        self.dirs = [struct.unpack_from('<II', data, ddir + 8 * i) for i in range(min(ndirs, 16))]
        self.sections = []
        for i in range(nsec):
            o = opt + optsize + 40 * i
            name = data[o:o + 8].rstrip(b'\0').decode('ascii', 'replace')
            vsize, va, rsize, raw = struct.unpack_from('<IIII', data, o + 8)
            self.sections.append((name, va, max(vsize, rsize), raw, rsize))

    def offset(self, rva):
        for _, va, size, raw, rsize in self.sections:
            if va <= rva < va + size:
                if rva - va >= rsize:
                    raise PEError('RVA %X is not stored in the file' % rva)
                return rva - va + raw
        raise PEError('RVA %X is outside every section' % rva)

    # ---- resources

    def resources(self):
        """{(type, name, language): (file offset, size)}; type and name are
        integers for numbered entries and strings for named ones."""
        if len(self.dirs) <= 2 or not self.dirs[2][0]:
            return {}
        base = self.offset(self.dirs[2][0])
        data = self.data
        out = {}

        def entries(off):
            named, ids = struct.unpack_from('<HH', data, off + 12)
            for i in range(named + ids):
                name, target = struct.unpack_from('<II', data, off + 16 + 8 * i)
                if name & 0x80000000:
                    p = base + (name & 0x7FFFFFFF)
                    n = struct.unpack_from('<H', data, p)[0]
                    name = data[p + 2:p + 2 + 2 * n].decode('utf-16-le')
                yield name, target

        for rtype, t1 in entries(base):
            if not t1 & 0x80000000:
                raise PEError('malformed resource directory')
            for rname, t2 in entries(base + (t1 & 0x7FFFFFFF)):
                if not t2 & 0x80000000:
                    raise PEError('malformed resource directory')
                for lang, t3 in entries(base + (t2 & 0x7FFFFFFF)):
                    if t3 & 0x80000000:
                        raise PEError('malformed resource directory')
                    rva, size = struct.unpack_from('<II', data, base + t3)
                    out[(rtype, rname, lang)] = (self.offset(rva), size)
        return out

    def resource(self, rtype, rname=None):
        """Bytes of the first resource of that type (and name)."""
        for (t, n, _), (off, size) in sorted(self.resources().items(), key=lambda kv: str(kv[0])):
            if t == rtype and (rname is None or n == rname):
                return self.data[off:off + size]
        return None

    def version_info(self):
        """{'file_version': (a, b, c, d), 'product_version': (...),
        'strings': {key: value}} from the RT_VERSION resource, or None."""
        blob = self.resource(RT_VERSION)
        if blob is None:
            return None
        root = _parse_version_block(blob, 0)
        value = root['value']
        if len(value) < 52 or struct.unpack_from('<I', value, 0)[0] != VS_FIXEDFILEINFO_SIGNATURE:
            raise PEError('version resource without VS_FIXEDFILEINFO')
        fms, fls, pms, pls = struct.unpack_from('<IIII', value, 8)
        strings = {}
        for child in root['children']:
            if child['key'] == 'StringFileInfo':
                for table in child['children']:
                    for s in table['children']:
                        strings[s['key']] = s['value'].decode('utf-16-le').rstrip('\0')
        return {'file_version': (fms >> 16, fms & 0xFFFF, fls >> 16, fls & 0xFFFF),
                'product_version': (pms >> 16, pms & 0xFFFF, pls >> 16, pls & 0xFFFF),
                'strings': strings}

    def icon_groups(self):
        """{group name: [(width, height, bits per pixel, icon id)]} for every
        RT_GROUP_ICON; 0 width/height in the directory means 256."""
        out = {}
        for (t, n, _), (off, size) in self.resources().items():
            if t != RT_GROUP_ICON:
                continue
            reserved, kind, count = struct.unpack_from('<HHH', self.data, off)
            items = []
            for i in range(count):
                w, h, _, _, _, bpp, _, icon_id = struct.unpack_from('<BBBBHHIH', self.data, off + 6 + 14 * i)
                items.append((w or 256, h or 256, bpp, icon_id))
            out[n] = items
        return out

    # ---- imports

    def imports(self):
        """Names of the DLLs the file imports (normal and delay-load)."""
        out = []
        for entry, name_field, size in ((1, 12, 20), (13, 4, 32)):
            if len(self.dirs) <= entry or not self.dirs[entry][0]:
                continue
            o = self.offset(self.dirs[entry][0])
            while struct.unpack_from('<I', self.data, o + name_field)[0]:
                p = self.offset(struct.unpack_from('<I', self.data, o + name_field)[0])
                out.append(self.data[p:self.data.index(b'\0', p)].decode('ascii', 'replace'))
                o += size
        return out


def _parse_version_block(data, off):
    """One node of a VS_VERSIONINFO tree: {'key', 'value', 'children'}."""
    length, value_len, vtype = struct.unpack_from('<HHH', data, off)
    if length < 6 or off + length > len(data):
        raise PEError('malformed version resource')
    end = off + length
    p = off + 6
    q = p
    while data[q:q + 2] != b'\0\0':
        q += 2
        if q >= end:
            raise PEError('malformed version resource key')
    key = data[p:q].decode('utf-16-le')
    p = (q + 2 + 3) & ~3
    nbytes = value_len * 2 if vtype == 1 else value_len
    value = data[p:p + nbytes]
    p = (p + nbytes + 3) & ~3
    children = []
    while p + 6 <= end:
        child = _parse_version_block(data, p)
        children.append(child)
        p = (p + child['length'] + 3) & ~3
    return {'key': key, 'value': value, 'children': children, 'length': length}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 1
    with open(args[0], 'rb') as f:
        pe = PE(f.read())
    vi = pe.version_info()
    if vi:
        print('file version:    %d.%d.%d.%d' % vi['file_version'])
        print('product version: %d.%d.%d.%d' % vi['product_version'])
        for k, v in sorted(vi['strings'].items()):
            print('  %-17s %s' % (k, v))
    else:
        print('no version resource')
    groups = pe.icon_groups()
    for name, items in sorted(groups.items(), key=lambda kv: str(kv[0])):
        print('icon group %s: %s' % (name, ', '.join('%dx%d' % (w, h) for w, h, _, _ in items)))
    if not groups:
        print('no icon')
    print('imports: %s' % ', '.join(pe.imports()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
