#!/usr/bin/env python3
"""Terminal video over curl. Needs only the Python 3 standard library and frames.gz next to this file.
Run: python3 server.py [port=8080]
curl gets the terminal animation; browsers get a web player."""
import gzip, socket, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

head, data = gzip.open("frames.gz").read().decode().split("\n", 1)  # header: width height fps
W, H, FPS = map(int, head.split())
raw = gzip.compress(data.encode())  # sent as-is to browsers, which decompress it themselves
size = (W + 1) * H  # one frame = H rows of W characters + newline (sliced by character, not byte)
# Each frame = cursor home + H rows (no trailing newline, so it occupies exactly H rows and never scrolls).
# \x1b[?2026h/l = synchronized update, removes flicker (ignored by terminals that don't support it);
# \x1b[J = erase everything below the frame.
frames = [b"\x1b[?2026h\x1b[H" + data[i:i + size - 1].encode() + b"\x1b[J\x1b[?2026l" for i in range(0, len(data), size)]

# Web player: the browser fetches /frames and draws the characters as blocks/triangles on a canvas (no font needed).
PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
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
const Q=" ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█",S={"░":.25,"▒":.5,"▓":.75};  // index into Q is a bitmask: 1 UL, 2 UR, 4 LL, 8 LR
const T={"◢":[1,0,1,1,0,1],"◣":[0,0,0,1,1,1],"◤":[0,0,1,0,0,1],"◥":[0,0,1,0,1,1]};  // triangle vertices in unit cell
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


class Handler(BaseHTTPRequestHandler):  # HTTP/1.0: no length, the stream ends when the connection closes
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
        if "curl" not in self.headers.get("User-Agent", "").lower():  # browser -> web player
            return self.send_bytes(PAGE, "text/html; charset=utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")  # don't buffer behind nginx
        self.end_headers()
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # send small packets immediately
        try:
            self.wfile.write(b"\x1b[2J")
            t0 = time.monotonic()
            i = 0
            while i < len(frames):
                lag = time.monotonic() - t0 - i / FPS
                if lag < 0:
                    time.sleep(-lag)
                elif lag > 1 / FPS:  # slow client/network: skip frames to keep up
                    i += int(lag * FPS)
                    continue
                self.wfile.write(frames[i])
                i += 1
            self.wfile.write(b"\x1b[0m\n")
        except (BrokenPipeError, ConnectionResetError):
            pass

    log_message = lambda *a: None


ThreadingHTTPServer(("0.0.0.0", int(sys.argv[1]) if len(sys.argv) > 1 else 8080), Handler).serve_forever()
