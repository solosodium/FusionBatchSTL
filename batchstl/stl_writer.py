"""Minimal STL writer (binary and ASCII). Pure Python, no Fusion dependency.

A "mesh" is a tuple ``(coords, indices)`` where ``coords`` is a flat sequence
``[x0, y0, z0, x1, y1, z1, ...]`` and ``indices`` is a flat sequence of node
indices, three per triangle. Several meshes can be written into one file.
"""

import math
import re
import struct

_FACET = struct.Struct('<12fH')


def _triangles(meshes):
    for coords, indices in meshes:
        for i in range(0, len(indices) - 2, 3):
            a = indices[i] * 3
            b = indices[i + 1] * 3
            c = indices[i + 2] * 3
            ax, ay, az = coords[a], coords[a + 1], coords[a + 2]
            bx, by, bz = coords[b], coords[b + 1], coords[b + 2]
            cx, cy, cz = coords[c], coords[c + 1], coords[c + 2]
            ux, uy, uz = bx - ax, by - ay, bz - az
            vx, vy, vz = cx - ax, cy - ay, cz - az
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            if length > 0.0:
                nx, ny, nz = nx / length, ny / length, nz / length
            else:
                nx = ny = nz = 0.0
            yield nx, ny, nz, ax, ay, az, bx, by, bz, cx, cy, cz


def triangle_count(meshes):
    return sum(len(indices) // 3 for _, indices in meshes)


def write_stl(path, meshes, binary=True, solid_name='mesh'):
    """Write ``meshes`` to ``path``. Returns the number of triangles written."""
    meshes = list(meshes)
    count = triangle_count(meshes)
    if binary:
        # The header must not start with "solid" or some readers treat it as ASCII.
        header = 'FusionBatchSTL {}'.format(solid_name).encode('ascii', 'replace')[:80].ljust(80, b' ')
        with open(path, 'wb') as f:
            f.write(header)
            f.write(struct.pack('<I', count))
            buf = bytearray()
            pack = _FACET.pack
            for tri in _triangles(meshes):
                buf += pack(*tri, 0)
                if len(buf) >= 1 << 20:
                    f.write(buf)
                    buf.clear()
            f.write(buf)
    else:
        name = re.sub(r'\s+', '_', solid_name.strip()) or 'mesh'
        name = name.encode('ascii', 'replace').decode('ascii')
        with open(path, 'w', encoding='ascii', newline='\n') as f:
            f.write('solid {}\n'.format(name))
            for nx, ny, nz, ax, ay, az, bx, by, bz, cx, cy, cz in _triangles(meshes):
                f.write(
                    '  facet normal {:e} {:e} {:e}\n'
                    '    outer loop\n'
                    '      vertex {:e} {:e} {:e}\n'
                    '      vertex {:e} {:e} {:e}\n'
                    '      vertex {:e} {:e} {:e}\n'
                    '    endloop\n'
                    '  endfacet\n'.format(nx, ny, nz, ax, ay, az, bx, by, bz, cx, cy, cz)
                )
            f.write('endsolid {}\n'.format(name))
    return count
