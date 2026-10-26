#!/usr/bin/env python3
"""Самодостаточные HTML (движок, модель и движения внутри) -> lisa3d/dist/.
    python3 lisa3d/tools/build-single.py
"""
import base64, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
b64 = lambda p: base64.b64encode((root / p).read_bytes()).decode()
boot = ("<script>(function(){function d(s){var b=atob(s),u=new Uint8Array(b.length);for(var i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u}"
        "window.__LISA3D_AVATAR_BUF=d('%s').buffer;"
        "window.__LISA3D_MOTIONS_BUF=d('%s').buffer;window.__LISA3D_META=%s;})();</script>\n"
        % (b64("avatar.glb"), b64("motions.bin"), (root / "motions.json").read_text()))
engine = "<script>\n" + (root / "lisa3d.js").read_text() + "\n</script>"
out = root / "dist"; out.mkdir(exist_ok=True)
for src, dst in (("index.html", "lisa3d-hologram.html"), ("demo.html", "lisa3d-demo.html")):
    html = (root / src).read_text()
    tag = '<script src="lisa3d.js"></script>'
    assert tag in html, src
    html = html.replace(tag, boot + engine)
    (out / dst).write_text(html)
    print(dst, round(len(html) / 1e6, 1), "МБ")
