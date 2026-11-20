#!/usr/bin/env python3
"""Video -> character frames (frames.gz). Run once locally; needs ffmpeg and numpy (the server needs neither).
Each character cell is split into 8x16 samples and the best-fitting glyph is chosen per cell
(quadrant/half blocks, eighth blocks, optional triangles; shades only on near-uniform cells),
so the effective resolution is well above the cell grid.
Usage: python3 convert.py video.mp4 [width=72] [height=27] [fps=30] [--tri]
  --tri  also use the triangles ◢◣◤◥. Most terminal fonts don't draw them cell-filling,
         which can leave gaps or misalign the picture, so they are off by default."""
import gzip, subprocess, sys
import numpy as np

args = [a for a in sys.argv[1:] if a != "--tri"]
TRI = "--tri" in sys.argv
src = args[0]
W = int(args[1]) if len(args) > 1 else 72
H = int(args[2]) if len(args) > 2 else 27
FPS = int(args[3]) if len(args) > 3 else 30
SW, SH = 8, 16  # 8x16 samples per cell (a cell is ~1:2, so the samples are square)
FLAT = 0.08     # shades (░▒▓) are only allowed on cells that are nearly uniform (std below this)

# ---- glyph templates: how much of the 4x8 sample grid each glyph lights up ----
yy, xx = np.mgrid[0:SH, 0:SW]
u, v = (xx + .5) / SW, (yy + .5) / SH
glyphs, tpl = [], []

def add(ch, mask):
    glyphs.append(ch)
    tpl.append(np.asarray(mask, dtype=np.float32).ravel())

QUAD = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"  # index = bitmask: 1 upper-left, 2 upper-right, 4 lower-left, 8 lower-right
for m, ch in enumerate(QUAD):
    ul, ur, ll, lr = (u < .5) & (v < .5), (u >= .5) & (v < .5), (u < .5) & (v >= .5), (u >= .5) & (v >= .5)
    add(ch, ((m & 1) > 0) * ul + ((m & 2) > 0) * ur + ((m & 4) > 0) * ll + ((m & 8) > 0) * lr)
SHADE = list(range(len(glyphs), len(glyphs) + 3))
for ch, val in (("░", .25), ("▒", .5), ("▓", .75)):
    add(ch, np.full((SH, SW), val))
for k, ch in zip((1, 2, 3, 5, 6, 7), "▁▂▃▅▆▇"):  # lower k/8 of the cell
    add(ch, v >= 1 - k / 8)
for k, ch in zip((1, 2, 3, 5, 6, 7), "▏▎▍▋▊▉"):  # left k/8 of the cell
    add(ch, u < k / 8)
add("▔", v < 1 / 8); add("▕", u >= 7 / 8)         # upper / right 1/8
if TRI:
    add("◢", u + v > 1); add("◣", v > u); add("◤", u + v < 1); add("◥", u > v)

T = np.stack(tpl)                      # (G, 32)
bias = (T * T).sum(1)                  # |t|^2
glyphs = np.array(glyphs)

# ---- read the video and match in batches ----
p = subprocess.Popen(
    ["ffmpeg", "-v", "error", "-i", src, "-an", "-vf", f"fps={FPS},scale={W * SW}:{H * SH}:flags=area",
     "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
fsize = W * SW * H * SH
BATCH = 120
n = 0
with gzip.open("frames.gz", "wb", 9) as out:
    out.write(f"{W} {H} {FPS}\n".encode())  # header: width height fps (read by server.py)
    while True:
        buf = p.stdout.read(fsize * BATCH)
        k = len(buf) // fsize
        if k == 0:
            break
        a = np.frombuffer(buf[:k * fsize], np.uint8).reshape(k, H, SH, W, SW).astype(np.float32) / 255
        cells = a.transpose(0, 1, 3, 2, 4).reshape(-1, SH * SW)       # (k*H*W, 32)
        sc = bias - 2 * cells @ T.T                                   # squared error (minus a per-cell constant)
        sc[np.ix_(cells.std(1) >= FLAT, SHADE)] = np.inf              # shades only on near-uniform cells
        best = sc.argmin(1)                                           # glyph with the smallest squared error
        ch = glyphs[best].reshape(k, H, W)
        ch = np.concatenate([ch, np.full((k, H, 1), "\n")], axis=2)
        out.write("".join(ch.ravel()).encode())
        n += k
print(f"{n} frames, {W}x{H}, {FPS}fps, {len(glyphs)} glyphs{' (with triangles)' if TRI else ''}")
