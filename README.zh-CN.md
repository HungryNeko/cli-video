# cli-video

用 `curl` 在终端里播放视频的字符动画。仅 Python 3 标准库,单文件服务。

[English](README.md) | 简体中文

- Demo:`curl https://badapple.fujisaki.top`(浏览器打开则直接网页播放)
- 博客:https://fujisaki.top/pages/tech/badapple_cli/post

## 部署

```bash
git clone https://github.com/HungryNeko/cli-video && cd cli-video
python3 server.py 8080
```

Docker:

```bash
docker build -t cli-video . && docker run -d -p 8080:8080 cli-video
```

播放:

```bash
curl http://服务器:8080
```

放在 nginx 等反向代理后面时,必须关闭缓冲,否则画面会攒着一起出来:

```nginx
proxy_buffering off;
```

## 换成自己的视频

本机需要 `ffmpeg` 和 `numpy`(服务器不需要):

```bash
pip install numpy
python3 convert.py 你的视频.mp4 [宽=72] [高=27] [fps=30]
```

生成新的 `frames.gz`,重启服务(或重新构建镜像)即可,宽高和帧率会自动读取。

- 终端字符约为 1:2,`宽 ≈ 高 × 2 × 视频宽 ÷ 视频高`。
- 终端的行数要大于「高」,否则会滚屏闪烁。
- 加 `--tri` 用 `◢◣◤◥` 三角形表现斜边;部分终端字体里它们不撑满整格,所以默认关闭,仓库里自带的 `frames.gz` 就是用 `--tri` 生成的。

## Windows cmd

先执行 `chcp 65001`,字体用 Consolas / Cascadia。
