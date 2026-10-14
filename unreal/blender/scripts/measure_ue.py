"""Measure every exported FBX the way Unreal 5.8 will:
read the file's GlobalSettings UnitScaleFactor and the
raw vertex coordinates directly (no Blender importer
round-trip), then report the size UE sees in cm.

UE's FBX importer scales raw vertex data by
UnitScaleFactor / 100 (with import scale 1.0), so the
size UE reports is raw_dims * UnitScaleFactor / 100.

Also re-imports via Blender for triangle counts (the
raw scan does not decode index buffers) and prints a
combined markdown table for README.md.
"""

import glob
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common  # noqa: E402


def scan_fbx_raw(path):
    """Read UnitScaleFactor and vertex array from the
    FBX binary without importing it.

    Returns (unit_scale_factor, ue_dims_cm) where
    ue_dims_cm is the bounding-box size UE 5.8 reports
    in UE axes (X forward, Y right, Z up).

    Axis note: with axis_forward="X", axis_up="Z" the
    exporter bakes the Blender->FBX axis conversion
    into the vertex data (FBX_X = authored Y,
    FBX_Y = authored X, FBX_Z = authored Z) and writes
    GlobalSettings FrontAxis/CoordAxis/UpAxis so
    importers convert back. The extents are therefore
    the same set of numbers, but stored in a swapped
    order: UE X = FBX Y, UE Y = FBX X, UE Z = FBX Z.
    We read the FrontAxis/CoordAxis/UpAxis metadata
    and reorder accordingly.
    """
    data = open(path, "rb").read()

    def prop_int(name):
        """Read an int GlobalSettings property.

        Layout: <name> S<len>int S<len>Integer S<len> I
        <int32>. The type code 'I' follows the three
        nested string properties, so scan for it only
        after the last nested string ('' -> S\\x00\\x00
        \\x00\\x00).
        """
        i = data.find(name)
        if i < 0:
            return None
        # The three nested strings end with an empty
        # string property: S\x00\x00\x00\x00 immediately
        # before the 'I' type code.
        j = data.find(b"S\x00\x00\x00\x00I", i + len(name))
        if 0 <= j < i + len(name) + 80:
            return struct.unpack(
                "<i", data[j + 6:j + 10])[0]
        return None

    usf = None
    i = data.find(b"UnitScaleFactor")
    if i >= 0:
        j = data.find(b"D", i + 15)
        if 0 <= j < i + 100:
            usf = struct.unpack("<d", data[j + 1:j + 9])[0]

    # Geometry 'Vertices' property: name, array type
    # code 'd', then array_len(int32), encoding(int32),
    # compressed_len(int32), then the (possibly
    # zlib-compressed) double array.
    verts = []
    j = data.find(b"Vertices")
    if j >= 0:
        p = j + 9
        arr_len = struct.unpack("<I", data[p:p + 4])[0]
        enc = struct.unpack("<I", data[p + 4:p + 8])[0]
        comp = struct.unpack("<I", data[p + 8:p + 12])[0]
        raw = data[p + 12:p + 12 + comp]
        if enc == 1:
            raw = zlib.decompress(raw)
        verts = list(struct.unpack("<%dd" % arr_len, raw))

    if not verts:
        raise RuntimeError("no Vertices array in " + path)
    if usf is None:
        raise RuntimeError("no UnitScaleFactor in " + path)

    xs, ys, zs = verts[0::3], verts[1::3], verts[2::3]
    fbx_dims = (max(xs) - min(xs), max(ys) - min(ys),
                max(zs) - min(zs))

    # Reorder FBX-native extents into UE axes.
    # The exporter (axis_forward="X", axis_up="Z",
    # bake_space_transform=True) bakes the Blender->FBX
    # conversion into the vertex data: authored X lands
    # on FBX Y, authored Y on FBX X, authored Z on
    # FBX Z. The GlobalSettings FrontAxis/CoordAxis/
    # UpAxis metadata then tells importers (Blender and
    # UE alike) to swap them back, so the round-trip
    # restores the authored orientation. Verified by
    # re-importing: the grasshopper's emissive eyes
    # land at UE +X. The raw-scan permutation is
    # therefore UE_X = FBX_Y, UE_Y = FBX_X, UE_Z = FBX_Z.
    front = prop_int(b"FrontAxis")
    coord = prop_int(b"CoordAxis")
    up = prop_int(b"UpAxis")
    # Sanity-check the metadata matches the expected
    # bake (FrontAxis=X, CoordAxis=Y, UpAxis=Z); if it
    # does, apply the inverse swap.
    if (front, coord, up) == (0, 1, 2):
        ue_dims = (fbx_dims[1], fbx_dims[0], fbx_dims[2])
    else:
        # Unexpected axis metadata: fall back to the
        # direct mapping and warn.
        print("WARNING: unexpected axis metadata "
              "FrontAxis=%s CoordAxis=%s UpAxis=%s"
              % (front, coord, up))
        ue_dims = fbx_dims
    ue_dims = tuple(d * usf / 100.0 for d in ue_dims)
    return usf, ue_dims


def main():
    rows = []
    for path in sorted(glob.glob(
            os.path.join(common.EXPORT_DIR, "*.fbx"))):
        name = os.path.splitext(os.path.basename(path))[0]
        usf, ue_dims = scan_fbx_raw(path)
        # Triangle count via Blender re-import (raw scan
        # would need the index arrays too).
        tris, _ = common.measure_fbx(path)
        rows.append((name, tris, usf, ue_dims))
        print("%s | %d | USF=%.1f | %.1f x %.1f x %.1f cm"
              % (name, tris, usf, ue_dims[0], ue_dims[1],
                 ue_dims[2]))
    return rows


if __name__ == "__main__":
    main()
