# -*- coding: utf-8 -*-
"""
Minimal raw FBX reader - what Unreal will actually see.

Blender's FBX *importer* normalises units on the way in, so a round-trip check
through it can never detect a file that declares itself in centimetres while
storing metres: Blender always agrees with itself.  Unreal reads the header and
the raw coordinate arrays literally.  This module parses the container directly
so verify.py can assert UE-visible sizes.

Two quirks this reader has to know about, both confirmed against the UE-authored
reference FBX and Blender's own 7.4 writer:

* ``EndOffset`` is an **absolute file offset**, despite the FBX docs describing
  it as record-relative.  A node with small children makes the two readings
  obviously different, and only the absolute one lands on the next sibling.
* Sibling names repeat constantly (``Objects`` holds hundreds of
  ``NodeAttribute`` children), so children are kept as a list, never a dict.

    python fbx_probe.py <file.fbx> [...]      # quick report
"""
import os
import struct
import sys
import zlib

MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"

_SCALAR = {'Y': ('<h', 2), 'C': ('<b', 1), 'I': ('i', 4), 'L': ('<q', 8),
           'F': ('f', 4), 'D': ('d', 8)}
_ARRAY = {'f': ('f', 4), 'd': ('d', 8), 'l': ('q', 8), 'i': ('i', 4),
          'b': ('?', 1), 'c': ('c', 1)}
_DECODE = ('Properties70', 'Vertices', 'P', 'Model')   # props worth decoding


class _Bad(Exception):
    pass


class Reader(object):
    def __init__(self, data, version):
        self.d = data
        self.p = 0
        self.version = version

    def u32(self):
        v = struct.unpack_from('<I', self.d, self.p)[0]
        self.p += 4
        return v

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def take(self, n):
        if self.p + n > len(self.d):
            raise _Bad("read past end of file")
        v = self.d[self.p:self.p + n]
        self.p += n
        return v


class Node(object):
    __slots__ = ('name', 'props', 'kids', 'end')

    def __init__(self, name, props, kids, end):
        self.name = name
        self.props = props
        self.kids = kids            # list of Node, siblings may share a name
        self.end = end              # absolute file offset just past this record

    def find(self, name):
        for k in self.kids:
            if k.name == name:
                return k
        return None

    def prefix(self, pre):
        return [k for k in self.kids if k.name.startswith(pre)]


def _props(r, nprops, proplen, name):
    """Decode a property list; skip it (using proplen) for nodes we don't need."""
    if name not in _DECODE:
        r.p += proplen
        return []
    stop = r.p + proplen
    vals = []
    for _ in range(nprops):
        t = chr(r.u8())
        if t in _SCALAR:
            fmt, size = _SCALAR[t]
            vals.append(struct.unpack_from(fmt, r.d, r.p)[0])
            r.p += size
        elif t in _ARRAY:
            n = r.u32()
            enc = r.u32()
            clen = r.u32()
            if r.version >= 7500:
                r.u32()                 # uncompressed length (7.5+ only)
            blob = r.take(clen)
            if enc == 1:
                blob = zlib.decompress(blob)
            code, width = _ARRAY[t]
            if n * width > len(blob):
                raise _Bad("array of %d %s does not fit in %d bytes"
                           % (n, t, len(blob)))
            if t in ('b', 'c'):
                vals.append(list(blob[:n]))
            else:
                vals.append(list(struct.unpack('<%d%s' % (n, code),
                                               blob[:n * width])))
        elif t in ('S', 'R'):
            n = r.u32()
            blob = r.take(n)
            vals.append(blob.decode('utf-8', 'replace') if t == 'S' else blob)
        elif t == 'P':
            vals.append('P')           # property-group marker, no payload
        else:
            raise _Bad("unhandled property type %r" % t)
    r.p = stop
    return vals


def _node_at(d, pos, version):
    """Parse one node record at `pos`; raises _Bad if `pos` is not a record."""
    r = Reader(d, version)
    r.p = pos
    raw_end = r.u32()
    nprops = r.u32()
    proplen = r.u32()
    namelen = r.u8()
    if namelen == 0 or namelen > 64:
        raise _Bad("implausible name length %d" % namelen)
    name = r.take(namelen).decode('utf-8', 'replace')
    end = raw_end if raw_end > pos else pos + raw_end
    if end > len(d) or end <= pos:
        raise _Bad("bad EndOffset for %r" % name)
    props = _props(r, nprops, proplen, name)
    r.p = pos + 13 + namelen + proplen
    kids = []
    while r.p < end:
        if d[r.p] == 0:
            # The 13-byte NULL record that terminates a childless node is a
            # *separator* - siblings continue after it.  Treating it as
            # end-of-list stops every parent at its first child.
            r.p += 13 if d[r.p:r.p + 13] == b"\x00" * 13 else 1
            continue
        start = r.p
        try:
            kid, kid_end = _node_at(d, r.p, version)
        except (_Bad, struct.error, IndexError, zlib.error):
            break
        kids.append(kid)
        # _node_at works on its own cursor; the parent must adopt the child's
        # end offset or the loop never advances past the first child
        r.p = max(kid_end, start + 1)
    r.p = max(end, r.p)
    return Node(name, props, kids, r.p), r.p


def find(data, version, name):
    """Every node record called `name`, located by scanning its length-prefixed
    tag and parsing forward.  Siblings may share a name, so this is a list."""
    pat = bytes([len(name)]) + name.encode()
    out = []
    i = 0
    while True:
        j = data.find(pat, i)
        if j < 0:
            return out
        i = j + 1
        pos = j - 12                  # 12 header bytes precede the name
        if pos < 0:
            continue
        try:
            n, _end = _node_at(data, pos, version)
        except (_Bad, struct.error, IndexError, zlib.error):
            continue
        if n.name == name:
            out.append(n)


def read(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    if not data.startswith(MAGIC):
        raise ValueError("%s is not a binary FBX" % os.path.basename(path))
    return data, struct.unpack_from('<I', data, len(MAGIC))[0]


def top_level(path, name):
    data, version = read(path)
    return find(data, version, name)


def p70_entries(node):
    """Decode a Properties70 node into [(name, subtype, value), ...].

    FBX 7.x stores each property as a *child node named "P"* carrying five
    sequential properties (type, name, type, value, flags) - not as a packed
    nine-element record.  Vector properties appear as three consecutive
    entries with subtypes X / Y / Z; only the first carries the name.
    """
    out = []
    p70 = node.find('Properties70')
    if p70 is None:
        return out
    for rec in p70.kids:
        p = rec.props
        if len(p) >= 5 and isinstance(p[0], str) and isinstance(p[1], str):
            out.append((p[0], p[2], p[4]))
    return out


def p70_scalar(entries, name):
    for n, _sub, v in entries:
        if n == name:
            return v
    return None


def p70_vector(entries, name):
    """Collect the X/Y/Z run that follows an entry called `name`."""
    out = []
    grabbing = False
    for n, sub, v in entries:
        if n == name:
            grabbing = True
            out.append((sub, v))
        elif grabbing and n == '':
            out.append((sub, v))
        elif grabbing:
            break
    return out


def global_settings(path):
    """UnitScaleFactor + axis triplet, straight from the file header."""
    for gs in top_level(path, 'GlobalSettings'):
        e = p70_entries(gs)
        if e:
            return {n: v for n, _sub, v in e}
    return {}


def objects(path):
    data, version = read(path)
    for n in find(data, version, 'Objects'):
        return n
    return Node('Objects', [], [], 0)


def vertices(path):
    """Raw (min, max, count, meshes) over every Geometry Vertices array.

    These are the numbers FBX stores before any importer normalisation - i.e.
    exactly what Unreal scales by UnitScaleFactor.
    """
    lo = [float('inf')] * 3
    hi = [float('-inf')] * 3
    count = 0
    meshes = 0
    for g in objects(path).prefix('Geometry'):
        v = g.find('Vertices')
        if v is None or not v.props or not isinstance(v.props[0], list):
            continue
        a = v.props[0]
        meshes += 1
        count += len(a) // 3
        for i in range(len(a) // 3):
            for k in range(3):
                c = a[i * 3 + k]
                if c < lo[k]:
                    lo[k] = c
                if c > hi[k]:
                    hi[k] = c
    return lo, hi, count, meshes


def model_transforms(path):
    """(name, class, Lcl Translation, Lcl Scaling) for every Model node."""
    out = []
    for m in objects(path).prefix('Model'):
        e = p70_entries(m)
        nm = m.props[2] if len(m.props) > 2 else '?'
        cls = m.props[1] if len(m.props) > 1 else ''
        out.append((nm, cls, p70_vector(e, 'Lcl Translation'),
                    p70_vector(e, 'Lcl Scaling')))
    return out


def bone_heads(path):
    """Raw Lcl Translation of every Model whose class is a bone (LimbNode)."""
    out = []
    for nm, cls, tr, _scl in model_transforms(path):
        if 'LimbNode' in (cls or '') and tr:
            out.append((nm, [v for _s, v in tr]))
    return out


def report(path):
    gs = global_settings(path)
    lo, hi, count, meshes = vertices(path)
    size = [hi[i] - lo[i] for i in range(3)]
    print("%-28s UnitScaleFactor=%s  meshes=%d verts=%d"
          % (os.path.basename(path), gs.get('UnitScaleFactor'), meshes, count))
    print("   raw bbox  x[%.4f,%.4f] y[%.4f,%.4f] z[%.4f,%.4f]"
          % (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
    print("   raw size  %.4f x %.4f x %.4f   z span %.4f"
          % (size[0], size[1], size[2], hi[2] - lo[2]))
    bones = bone_heads(path)
    if bones:
        zmax = max(abs(b[1][2]) for b in bones)
        print("   %d bone nodes, max |Lcl Translation.z| = %.4f" % (len(bones), zmax))
    return {'file': os.path.basename(path),
            'unit_scale_factor': gs.get('UnitScaleFactor'),
            'lo': lo, 'hi': hi, 'size': size, 'verts': count, 'meshes': meshes,
            'bone_z_max': max((abs(b[1][2]) for b in bones), default=None)}


if __name__ == '__main__':
    for p in sys.argv[1:]:
        report(p)
        print()