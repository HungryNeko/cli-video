#!/usr/bin/env python3
"""curl 字符动画服务。依赖: 仅 Python3 标准库 + 同目录 frames.gz
运行: python3 server.py [端口=8080]
curl 访问 -> 终端动画;浏览器访问 -> 网页播放。"""
import gzip, socket, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

head, data = gzip.open("frames.gz").read().decode().split("\n", 1)  # 头部: 宽 高 帧率
W, H, FPS = map(int, head.split())
raw = gzip.compress(data.encode())  # 网页版直接把它发给浏览器,由浏览器解压
size = (W + 1) * H  # 每帧 H 行,每行 W 个字符 + 换行(按字符切,不是字节)
# 每帧 = 光标回左上角 + H 行字符(去掉末尾换行,恰好占 H 行,不会滚屏)
# \x1b[?2026h/l 同步刷新,消除闪烁(不支持的终端会忽略);\x1b[J 清掉帧下面的残留
frames = [b"\x1b[?2026h\x1b[H" + data[i:i + size - 1].encode() + b"\x1b[J\x1b[?2026l" for i in range(0, len(data), size)]

# 网页版: 浏览器拉 /frames,用 canvas 把字符画成方块/三角形,不依赖字体
PAGE = """<!doctype html><html lang="zh"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>cli-video</title>
<style>
html,body{margin:0;height:100%;background:#000;color:#888;font:13px/1.6 ui-monospace,Consolas,monospace}
body{display:flex;flex-direction:column;align-items:center;justify-content:center}
p{margin:10px 0 0}code{color:#ccc}
</style>
<canvas id="c"></canvas>
<p><code id="cmd"></code></p>
<script>
const W=__W__,H=__H__,FPS=__FPS__,CW=16,CH=32,HW=CW/2,HH=CH/2;
const Q=" ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█",S={"░":.25,"▒":.5,"▓":.75};  // Q 的下标是位掩码: 1 左上 2 右上 4 左下 8 右下
const T={"◢":[1,0,1,1,0,1],"◣":[0,0,0,1,1,1],"◤":[0,0,1,0,0,1],"◥":[0,0,1,0,1,1]};  // 三角形顶点(单位格内)
const c=document.getElementById("c"),g=c.getContext("2d");
c.width=W*CW;c.height=H*CH;
c.style.width="min(100vw,calc((100vh - 40px) * "+(W*CW)/(H*CH)+"))";c.style.aspectRatio=W*CW+"/"+H*CH;
document.getElementById("cmd").textContent="curl "+location.origin;
function draw(f){
  g.fillStyle="#000";g.fillRect(0,0,c.width,c.height);g.fillStyle="#fff";
  for(let y=0;y<H;y++)for(let x=0;x<W;x++){
    const ch=f[y*(W+1)+x];if(ch===" ")continue;
    const px=x*CW,py=y*CH,m=Q.indexOf(ch);
    if(m>0){
      if(m&1)g.fillRect(px,py,HW,HH);if(m&2)g.fillRect(px+HW,py,HW,HH);
      if(m&4)g.fillRect(px,py+HH,HW,HH);if(m&8)g.fillRect(px+HW,py+HH,HW,HH);
    }else if(S[ch]){g.globalAlpha=S[ch];g.fillRect(px,py,CW,CH);g.globalAlpha=1;}
    else if(T[ch]){const t=T[ch];g.beginPath();g.moveTo(px+t[0]*CW,py+t[1]*CH);
      g.lineTo(px+t[2]*CW,py+t[3]*CH);g.lineTo(px+t[4]*CW,py+t[5]*CH);g.fill();}
  }
}
fetch("/frames").then(r=>r.text()).then(t=>{
  const S=(W+1)*H,N=Math.floor(t.length/S),t0=performance.now();let last=-1;
  (function loop(now){
    const i=Math.floor((now-t0)*FPS/1000)%N;
    if(i!==last){draw(t.substr(i*S,S));last=i}
    requestAnimationFrame(loop);
  })(t0);
});
</script></html>""".replace("__W__", str(W)).replace("__H__", str(H)).replace("__FPS__", str(FPS)).encode()


class Handler(BaseHTTPRequestHandler):  # HTTP/1.0: 不发长度,连接关闭即结束,curl 直接流式输出
    def send_bytes(self, body, ctype, gz=False):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if gz:
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/frames":
            return self.send_bytes(raw, "text/plain; charset=utf-8", gz=True)
        if "curl" not in self.headers.get("User-Agent", "").lower():  # 浏览器 -> 网页版
            return self.send_bytes(PAGE, "text/html; charset=utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")  # nginx 反代时不缓冲
        self.end_headers()
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # 小包立即发出
        try:
            self.wfile.write(b"\x1b[2J")
            t0 = time.monotonic()
            i = 0
            while i < len(frames):
                lag = time.monotonic() - t0 - i / FPS
                if lag < 0:
                    time.sleep(-lag)
                elif lag > 1 / FPS:  # 客户端/网络慢了就跳帧,保持节奏
                    i += int(lag * FPS)
                    continue
                self.wfile.write(frames[i])
                i += 1
            self.wfile.write(b"\x1b[0m\n")
        except (BrokenPipeError, ConnectionResetError):
            pass

    log_message = lambda *a: None


ThreadingHTTPServer(("0.0.0.0", int(sys.argv[1]) if len(sys.argv) > 1 else 8080), Handler).serve_forever()
