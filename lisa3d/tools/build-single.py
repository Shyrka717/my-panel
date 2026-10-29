#!/usr/bin/env python3
"""Самодостаточные HTML (движок, модель, движения и текстуры внутри): работают без сервера и интернета.
    python3 lisa3d/tools/build-single.py      # -> lisa3d/dist/ и avatar2/dist/
"""
import base64, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
repo = root.parent
b64 = lambda p: base64.b64encode(p.read_bytes()).decode()
DECODE = "function d(s){var b=atob(s),u=new Uint8Array(b.length);for(var i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u}"
motions = lambda d: ("window.__LISA3D_MOTIONS_BUF=d('%s').buffer;window.__LISA3D_META=%s;"
                     % (b64(d / "motions.bin"), (d / "motions.json").read_text()))
base = "window.__LISA3D_AVATAR_BUF=d('%s').buffer;" % b64(root / "avatar.glb")
engine = "<script>\n" + (root / "lisa3d.js").read_text() + "\n</script>"


def build(folder, pages, extra=""):
    # движения: свои у папки (например, другой набор танцев), иначе общие из lisa3d
    boot = "<script>(function(){" + DECODE + base + motions(folder if (folder / "motions.bin").exists() else root) + extra + "})();</script>\n"
    out = folder / "dist"; out.mkdir(exist_ok=True)
    for src, dst in pages:
        html = (folder / src).read_text()
        tag = next(t for t in ('<script src="lisa3d.js"></script>', '<script src="../lisa3d/lisa3d.js"></script>') if t in html)
        html = html.replace(tag, boot + engine)
        (out / dst).write_text(html)
        print(dst, round(len(html) / 1e6, 1), "МБ")


build(root, (("index.html", "lisa3d-hologram.html"), ("demo.html", "lisa3d-demo.html")))

# вторая девушка: реалистичный вид, платье, кожа с лицом с фото, глаза, волосы, юбка и туфли
a2 = repo / "avatar2"
uri = lambda name: "'data:image/webp;base64,%s'" % b64(a2 / name)
buf = lambda name: "d('%s').buffer" % b64(a2 / name)
build(a2, (("3d.html", "avatar2-3d.html"), ("3d-demo.html", "avatar2-3d-demo.html")),
      "window.__SUIT_MAP=%s;window.__SUIT_PBR=%s;window.__SKIN_MAP=%s;window.__SKIN_PBR=%s;window.__EYE_MAP=%s;"
      "window.__HAIR_BUF=%s;window.__SKIRT_BUF=%s;window.__SHOES_BUF=%s;"
      % (uri("dress.webp"), uri("dress-pbr.webp"), uri("skin.webp"), uri("skin-pbr.webp"), uri("eyes.webp"),
         buf("hair.bin"), buf("skirt.bin"), buf("shoes.bin")))
