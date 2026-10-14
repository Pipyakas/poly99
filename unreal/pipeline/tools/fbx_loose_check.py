"""Check an FBX for vertices that no polygon references (loose geometry).

A hole in UE that does not exist in Blender is often geometry that was
generated but never linked into faces, so it never gets triangulated or
exported. Blender ray casts still hit such vertices only if the caller
ignores topology, which most coverage probes do.

Usage: python -I fbx_loose_check.py <file.fbx> [...]
"""

import struct
import sys
import zlib


def _array(data, name, code, fmt):
    """Return the decoded property array for a named FBX property."""
    j = data.find(name)
    if j < 0:
        return None
    p = j + len(name)
    if data[p:p + 1] != code:
        return None
    arr_len = struct.unpack("<I", data[p + 1:p + 5])[0]
    enc = struct.unpack("<I", data[p + 5:p + 9])[0]
    comp = struct.unpack("<I", data[p + 9:p + 13])[0]
    raw = data[p + 13:p + 13 + comp]
    if enc == 1:
        raw = zlib.decompress(raw)
    if len(raw) < arr_len * struct.calcsize(fmt):
        return None
    return list(struct.unpack("<%d%s" % (arr_len, fmt), raw[:arr_len * struct.calcsize(fmt)]))


def check(path):
    data = open(path, "rb").read()
    verts = _array(data, b"Vertices", b"d", "d")
    poly = _array(data, b"PolygonVertexIndex", b"i", "i")
    usf = None
    i = data.find(b"UnitScaleFactor")
    if i >= 0:
        j = data.find(b"D", i + 15)
        if 0 <= j < i + 100:
            usf = struct.unpack("<d", data[j + 1:j + 9])[0]
    if not verts or poly is None:
        return "%s: no Vertices/PolygonVertexIndex (ascii FBX?)" % path
    nv = len(verts) // 3
    used = bytearray(nv)
    npoly = 0
    for idx in poly:
        npoly += 1
        if idx < 0:
            idx = ~idx  # last index of a polygon is stored as ~i
        if 0 <= idx < nv:
            used[idx] = 1
    loose = [i for i in range(nv) if not used[i]]
    scale = (usf or 1.0) / 100.0
    msg = "%s: %d verts, %d polygons, %d LOOSE" % (path.split("\\")[-1].split("/")[-1], nv, npoly, len(loose))
    if loose:
        xs = [verts[3 * i] for i in loose]
        ys = [verts[3 * i + 1] for i in loose]
        zs = [verts[3 * i + 2] for i in loose]
        msg += " | loose bbox raw x[%.1f,%.1f] y[%.1f,%.1f] z[%.1f,%.1f] -> UE cm x[%.1f,%.1f] y[%.1f,%.1f] z[%.1f,%.1f]" % (
            min(xs), max(xs), min(ys), max(ys), min(zs), max(zs),
            min(ys) * scale, max(ys) * scale, min(xs) * scale, max(xs) * scale,
            min(zs) * scale, max(zs) * scale)
    return msg


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(check(p))
