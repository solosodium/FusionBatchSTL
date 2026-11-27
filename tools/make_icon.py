"""Toolbar icon for Batch STL Export: a faceted (meshed) cube with an export badge.

Pure Python, no dependencies. Usage: python tools/make_icon.py resources [preview.png]
"""
import math
import os
import struct
import sys
import zlib


def png(path, w, h, pixels):
    raw = b''.join(b'\x00' + bytes(pixels[y * w * 4:(y + 1) * w * 4]) for y in range(h))

    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)

    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    data += chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(data)


def inside(poly, x, y):
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def line(p, q, w):
    """A line segment of width w as a polygon."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy)
    ox, oy = -dy / n * w / 2, dx / n * w / 2
    return [(p[0] + ox, p[1] + oy), (q[0] + ox, q[1] + oy), (q[0] - ox, q[1] - oy), (p[0] - ox, p[1] - oy)]


def circle(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def render(shapes, size, ss=6):
    """shapes: [(polygon in 0..1 coords, (r, g, b, a))], later on top."""
    px = [0] * (size * size * 4)
    for y in range(size):
        for x in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(ss):
                for sx in range(ss):
                    u = (x + (sx + 0.5) / ss) / size
                    v = (y + (sy + 0.5) / ss) / size
                    col = None
                    for poly, rgba in shapes:
                        if inside(poly, u, v):
                            col = rgba
                    if col and col[3]:
                        a = col[3] / 255.0
                        acc[0] += col[0] * a; acc[1] += col[1] * a; acc[2] += col[2] * a; acc[3] += a
            i = (y * size + x) * 4
            if acc[3]:
                n = acc[3]
                px[i:i + 4] = [int(acc[0] / n), int(acc[1] / n), int(acc[2] / n), int(255 * n / (ss * ss))]
    return px


TOP = (126, 186, 250, 255)
LEFT = (48, 124, 222, 255)
RIGHT = (26, 78, 168, 255)
EDGE = (235, 245, 255, 255)
FACET_TOP = (176, 216, 255, 255)
FACET_SIDE = (104, 162, 238, 255)
ORANGE = (247, 142, 30, 255)
WHITE = (255, 255, 255, 255)
CUT = (0, 0, 0, 0)  # transparent gap around the badge


def icon(size):
    # Isometric cube, slightly left of centre to leave room for the badge.
    T, UL, UR, C = (0.43, 0.06), (0.07, 0.26), (0.79, 0.26), (0.43, 0.46)
    LL, LR, B = (0.07, 0.70), (0.79, 0.70), (0.43, 0.90)
    shapes = [
        ([T, UR, C, UL], TOP),
        ([UL, C, B, LL], LEFT),
        ([C, UR, LR, B], RIGHT),
    ]
    small = size <= 16
    if not small:
        fw = 1.0 / size  # one-pixel facet lines
        shapes += [
            (line(T, C, fw), FACET_TOP),
            (line(UL, B, fw), FACET_SIDE),
            (line(C, LR, fw), FACET_SIDE),
        ]
    ew = (1.0 if small else 1.3) / size
    shapes += [(line(UL, C, ew), EDGE), (line(C, UR, ew), EDGE), (line(C, B, ew), EDGE)]

    # Export badge: orange disc with a white arrow pointing out to the right.
    cx, cy, r = 0.76, 0.76, 0.22
    shapes += [(circle(cx, cy, r + 0.06), CUT), (circle(cx, cy, r), ORANGE)]
    sw = 0.09  # arrow shaft width
    shapes += [
        ([(cx - 0.12, cy - sw / 2), (cx + 0.01, cy - sw / 2), (cx + 0.01, cy + sw / 2), (cx - 0.12, cy + sw / 2)], WHITE),
        ([(cx - 0.01, cy - 0.115), (cx + 0.13, cy), (cx - 0.01, cy + 0.115)], WHITE),
    ]
    return render(shapes, size)


def preview(path, images):
    """Images enlarged 8x on light and dark backgrounds, side by side."""
    scale, pad = 8, 16
    bgs = [(240, 240, 240), (60, 63, 68)]
    w = sum(s * scale + pad for s, _ in images) + pad
    row = max(s for s, _ in images) * scale + pad
    h = row * len(bgs) + pad
    out = [0] * (w * h * 4)
    for b, bg in enumerate(bgs):
        for y in range(b * row, (b + 1) * row + pad):
            for x in range(w):
                if y < h:
                    out[(y * w + x) * 4:(y * w + x) * 4 + 4] = [bg[0], bg[1], bg[2], 255]
        ox = pad
        for s, px in images:
            for y in range(s * scale):
                for x in range(s * scale):
                    i = ((y // scale) * s + x // scale) * 4
                    a = px[i + 3] / 255.0
                    o = ((pad + b * row + y) * w + ox + x) * 4
                    out[o:o + 3] = [int(px[i + k] * a + bg[k] * (1 - a)) for k in range(3)]
            ox += s * scale + pad
    png(path, w, h, out)


if __name__ == '__main__':
    out_dir = os.path.join(sys.argv[1], 'batch_export')
    os.makedirs(out_dir, exist_ok=True)
    cache = {s: icon(s) for s in (16, 32, 64)}
    for fname, size in (('16x16.png', 16), ('32x32.png', 32), ('16x16@2x.png', 32), ('32x32@2x.png', 64)):
        png(os.path.join(out_dir, fname), size, size, cache[size])
    if len(sys.argv) > 2:
        preview(sys.argv[2], [(16, cache[16]), (32, cache[32]), (64, cache[64])])
    print('ok')
