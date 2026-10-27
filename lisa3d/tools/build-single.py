#!/usr/bin/env python3
"""Самодостаточные HTML (движок, модель, движения и текстуры внутри): работают без сервера и интернета.
    python3 lisa3d/tools/build-single.py      # -> lisa3d/dist/ и avatar2/dist/
"""
import base64, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
repo = root.parent
b64 = lambda p: base64.b64encode(p.read_bytes()).decode()
DECODE = "function d(s){var b=atob(s),u=new Uint8Array(b.length);for(var i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u}"
base = ("window.__LISA3D_AVATAR_BUF=d('%s').buffer;window.__LISA3D_MOTIONS_BUF=d('%s').buffer;window.__LISA3D_META=%s;"
        % (b64(root / "avatar.glb"), b64(root / "motions.bin"), (root / "motions.json").read_text()))
engine = "<script>\n" + (root / "lisa3d.js").read_text() + "\n</script>"


def build(folder, pages, extra=""):
    boot = "<script>(function(){" + DECODE + base + extra + "})();</script>\n"
    out = folder / "dist"; out.mkdir(exist_ok=True)
    for src, dst in pages:
        html = (folder / src).read_text()
        tag = next(t for t in ('<script src="lisa3d.js"></script>', '<script src="../lisa3d/lisa3d.js"></script>') if t in html)
        html = html.replace(tag, boot + engine)
        (out / dst).write_text(html)
        print(dst, round(len(html) / 1e6, 1), "МБ")


build(root, (("index.html", "lisa3d-hologram.html"), ("demo.html", "lisa3d-demo.html")))

# вторая девушка: реалистичный вид, свой костюм, кожа с лицом с фото, глаза и волосы
a2 = repo / "avatar2"
uri = lambda name: "'data:image/webp;base64,%s'" % b64(a2 / name)
build(a2, (("3d.html", "avatar2-3d.html"), ("3d-demo.html", "avatar2-3d-demo.html")),
      "window.__SUIT_MAP=%s;window.__SUIT_GLOW=%s;window.__SKIN_MAP=%s;window.__EYE_MAP=%s;window.__HAIR_BUF=d('%s').buffer;"
      % (uri("suit.webp"), uri("suit-glow.webp"), uri("skin.webp"), uri("eyes.webp"), b64(a2 / "hair.bin")))
