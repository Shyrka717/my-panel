#!/usr/bin/env python3
"""Собирает самодостаточные HTML (скрипты, данные лица и портрет внутри) в lisa/dist/.
Такой файл работает из приложения напрямую (WebView, Electron), без сервера.
    python3 lisa/tools/build-single.py
"""
import base64, pathlib

root = pathlib.Path(__file__).resolve().parent.parent
img = "data:image/webp;base64," + base64.b64encode((root / "portrait.webp").read_bytes()).decode()
scripts = {name: (root / name).read_text() for name in ("face-data.js", "lisa-face.js")}
out = root / "dist"
out.mkdir(exist_ok=True)

for src, dst in (("embed.html", "lisa-hologram.html"), ("index.html", "lisa-demo.html")):
    html = (root / src).read_text()
    for name, code in scripts.items():
        tag = f'<script src="{name}"></script>'
        assert tag in html, (src, tag)
        html = html.replace(tag, "<script>\n" + code + "</script>")
    assert 'src="portrait.webp"' in html and "image:'portrait.webp'" in html, src
    html = html.replace('src="portrait.webp"', f'src="{img}"', 1)
    html = html.replace("image:'portrait.webp'", "image:document.getElementById('fallback').src")
    (out / dst).write_text(html)
    print(dst, len(html) // 1024, "КБ")
