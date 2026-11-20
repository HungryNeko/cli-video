#!/usr/bin/env python3
"""视频 -> 字符帧 (frames.gz)。只在本地跑一次,服务器不需要 ffmpeg,本机需要 numpy。
每个字符格切成 4x8 个采样点,逐格挑最贴合的字符(象限块/半块/阴影,可选三角形),有效分辨率约为字符格的 2 倍以上。
用法: python3 convert.py 视频.mp4 [宽=72] [高=27] [fps=30] [--tri]
  --tri  额外启用 ◢◣◤◥ 三角形。注意:多数终端字体里它们不是"撑满整格"的,可能出现缝隙/错位,默认关闭。"""
import gzip, subprocess, sys
import numpy as np

args = [a for a in sys.argv[1:] if a != "--tri"]
TRI = "--tri" in sys.argv
src = args[0]
W = int(args[1]) if len(args) > 1 else 72
H = int(args[2]) if len(args) > 2 else 27
FPS = int(args[3]) if len(args) > 3 else 30
SW, SH = 4, 8  # 每格 4x8 个采样点(字符格宽高比约 1:2,所以采样点是方的)

# ---- 字符模板: 在 4x8 的采样网格上各字符"点亮"的比例 ----
yy, xx = np.mgrid[0:SH, 0:SW]
u, v = (xx + .5) / SW, (yy + .5) / SH
glyphs, tpl = [], []

def add(ch, mask):
    glyphs.append(ch)
    tpl.append(np.asarray(mask, dtype=np.float32).ravel())

QUAD = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"  # 下标 = 位掩码: 1 左上, 2 右上, 4 左下, 8 右下
for m, ch in enumerate(QUAD):
    ul, ur, ll, lr = (u < .5) & (v < .5), (u >= .5) & (v < .5), (u < .5) & (v >= .5), (u >= .5) & (v >= .5)
    add(ch, ((m & 1) > 0) * ul + ((m & 2) > 0) * ur + ((m & 4) > 0) * ll + ((m & 8) > 0) * lr)
for ch, val in (("░", .25), ("▒", .5), ("▓", .75)):
    add(ch, np.full((SH, SW), val))
if TRI:
    add("◢", u + v > 1); add("◣", v > u); add("◤", u + v < 1); add("◥", u > v)

T = np.stack(tpl)                      # (G, 32)
bias = (T * T).sum(1)                  # |t|^2
glyphs = np.array(glyphs)

# ---- 读取视频、逐批匹配 ----
p = subprocess.Popen(
    ["ffmpeg", "-v", "error", "-i", src, "-an", "-vf", f"fps={FPS},scale={W * SW}:{H * SH}:flags=area",
     "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
fsize = W * SW * H * SH
BATCH = 120
n = 0
with gzip.open("frames.gz", "wb", 9) as out:
    out.write(f"{W} {H} {FPS}\n".encode())  # 头部: 宽 高 帧率,server.py 自动读取
    while True:
        buf = p.stdout.read(fsize * BATCH)
        k = len(buf) // fsize
        if k == 0:
            break
        a = np.frombuffer(buf[:k * fsize], np.uint8).reshape(k, H, SH, W, SW).astype(np.float32) / 255
        cells = a.transpose(0, 1, 3, 2, 4).reshape(-1, SH * SW)       # (k*H*W, 32)
        best = (bias - 2 * cells @ T.T).argmin(1)                     # 平方误差最小的字符
        ch = glyphs[best].reshape(k, H, W)
        ch = np.concatenate([ch, np.full((k, H, 1), "\n")], axis=2)
        out.write("".join(ch.ravel()).encode())
        n += k
print(f"{n} frames, {W}x{H}, {FPS}fps, 字符集 {len(glyphs)} 种{' (含三角形)' if TRI else ''}")
