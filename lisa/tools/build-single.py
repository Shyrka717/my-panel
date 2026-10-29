#!/usr/bin/env python3
"""Собирает самодостаточные HTML (скрипты, данные лица и портрет внутри) в <папка>/dist/.
Такой файл работает из приложения напрямую (WebView, Electron), без сервера.
    python3 lisa/tools/build-single.py            # папка lisa
    python3 lisa/tools/build-single.py avatar2    # другая папка с portrait.webp, face-data.js, embed.html, index.html
"""
import base64, pathlib, re, sys

repo = pathlib.Path(__file__).resolve().parent.parent.parent
root = repo / (sys.argv[1] if len(sys.argv) > 1 else "lisa")
img = "data:image/webp;base64," + base64.b64encode((root / "portrait.webp").read_bytes()).decode()
names = (("embed.html", "lisa-hologram.html"), ("index.html", "lisa-demo.html")) if root.name == "lisa" else \
        (("embed.html", f"{root.name}-face.html"), ("index.html", f"{root.name}-face-demo.html"))
out = root / "dist"
out.mkdir(exist_ok=True)

for src, dst in names:
    html = (root / src).read_text()
    for name in ("face-data.js", "lisa-face.js"):
        m = re.search(r'<script src="([^"]*%s)"></script>' % re.escape(name), html)
        assert m, (src, name)
        code = (root / m.group(1)).resolve().read_text()
        html = html.replace(m.group(0), "<script>\n" + code + "</script>")
    assert 'src="portrait.webp"' in html and "image:'portrait.webp'" in html, src
    html = html.replace('src="portrait.webp"', f'src="{img}"', 1)
    html = html.replace("image:'portrait.webp'", "image:document.getElementById('fallback').src")
    (out / dst).write_text(html)
    print(dst, len(html) // 1024, "КБ")
