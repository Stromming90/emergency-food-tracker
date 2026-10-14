#!/usr/bin/env python3
"""Generate launcher icons (pure stdlib PNG writer)."""
import struct, zlib, os

W = H = 512

def hex2rgb(h):
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

BG = hex2rgb("10151C")      # app dark background
ACCENT = hex2rgb("3b82f6")  # app accent blue
WHITE = hex2rgb("f2f5f7")
GREY = hex2rgb("9aa7b0")

px = [[list(BG) for _ in range(W)] for _ in range(H)]

def rrect(x0, y0, x1, y1, r, color):
    for y in range(y0, y1):
        for x in range(x0, x1):
            dx = min(x - x0, x1 - 1 - x)
            dy = min(y - y0, y1 - 1 - y)
            if dx < r and dy < r and (r - dx) ** 2 + (r - dy) ** 2 > r * r:
                continue
            px[y][x] = list(color)

def ellipse(cx, cy, rx, ry, color):
    for y in range(max(0, cy - ry), min(H, cy + ry)):
        for x in range(max(0, cx - rx), min(W, cx + rx)):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                px[y][x] = list(color)

rrect(0, 0, W, H, 96, BG)
ellipse(256, 256, 200, 200, ACCENT)
rrect(176, 190, 336, 350, 26, WHITE)
rrect(176, 176, 336, 214, 20, GREY)
rrect(200, 240, 312, 254, 6, ACCENT)
rrect(200, 276, 312, 290, 6, ACCENT)

def write_png(path, size):
    step = W // size
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    raw = b""
    for y in range(size):
        line = b"\x00"
        for x in range(size):
            r = g = b = n = 0
            for sy in range(y * step, (y + 1) * step):
                for sx in range(x * step, (x + 1) * step):
                    p = px[sy][sx]; r += p[0]; g += p[1]; b += p[2]; n += 1
            line += bytes((r // n, g // n, b // n, 255))
        raw += line
    data = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

base = "/home/user/eft/app/src/res"
for name, size in (("mipmap-mdpi", 48), ("mipmap-hdpi", 72),
                   ("mipmap-xhdpi", 96), ("mipmap-xxhdpi", 144),
                   ("mipmap-xxxhdpi", 192)):
    write_png(f"{base}/{name}/ic_launcher.png", size)
print("icons done")
