"""Measure every exported FBX: re-import into a
scratch scene, print triangle count and bounding
box in centimeters. Output is a markdown table
appended to README.md.
"""

import glob
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__))))

import common  # noqa: E402


def main():
    rows = []
    for path in sorted(
            glob.glob(os.path.join(
                common.EXPORT_DIR, "*.fbx"))):
        name = os.path.splitext(
            os.path.basename(path))[0]
        tris, dims = common.measure_fbx(path)
        rows.append((name, tris, dims))
        print("%s | %d | %.1f x %.1f x %.1f"
              % (name, tris, dims[0], dims[1],
                 dims[2]))
    return rows


if __name__ == "__main__":
    main()
