# cli-video

Play a video as a character animation in the terminal with `curl`. Single-file server, Python 3 standard library only.

English | [简体中文](README.zh-CN.md)

- Demo: `curl https://badapple.fujisaki.top` (open it in a browser for a web player)
- Blog: https://fujisaki.top/pages/tech/badapple_cli/post

## Deploy

```bash
git clone https://github.com/HungryNeko/cli-video && cd cli-video
python3 server.py 8080
```

Or with Docker:

```bash
docker build -t cli-video . && docker run -d -p 8080:8080 cli-video
```

Play:

```bash
curl http://your-server:8080
```

Behind a reverse proxy such as nginx, turn buffering off, otherwise frames arrive in bursts:

```nginx
proxy_buffering off;
```

## Use your own video

You need `ffmpeg` and `numpy` on your own machine (not on the server):

```bash
pip install numpy
python3 convert.py your-video.mp4 [width=72] [height=27] [fps=30]
```

This writes a new `frames.gz`. Restart the server (or rebuild the image); width, height and fps are read from the file automatically.

- A terminal cell is about 1:2, so `width ≈ height × 2 × video width ÷ video height`.
- The terminal must have more rows than `height`, otherwise the picture scrolls and flickers.
- `--tri` also uses the triangles `◢◣◤◥`. Most terminal fonts don't draw them cell-filling, so they are off by default.

## Windows cmd

Run `chcp 65001` first and use a font such as Consolas or Cascadia.
