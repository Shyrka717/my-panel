#!/usr/bin/env python3
"""Новый костюм для модели: серый атлас, молния, швы, голубые светящиеся линии, обувь в тон, зелёные глаза.
Рисует в координатах тела по картам из uvmap.mjs, поэтому линии ложатся ровно, где задумано.
    node uvmap.mjs ../avatar.glb suit data/suit-uv.f32 data/suit-orig.png
    node uvmap.mjs ../avatar.glb '^base' data/body-uv.f32 data/body-orig.png
    node uvmap.mjs ../avatar.glb high-poly data/eye-uv.f32 data/eye-orig.png
    python3 make-suit.py data ../../avatar2          # -> suit.webp, suit-glow.webp, skin.webp, eyes.webp
Лицо с фото на коже (нужны mediapipe и модель face_landmarker.task):
    node uvmap.mjs ../avatar.glb '^base' data/bodyw-uv.f32 data/bodyw-orig.png 1024 world
    node front-render.mjs ../avatar.glb data/front.png data/front-z.f32
    python3 make-suit.py data ../../avatar2 ../../avatar2/portrait.webp data/face_landmarker.task
Единицы костюма: 1 единица ~ 0.71 м; верх ворота спереди y~0.92, грудь y~0.7, низ куртки y~0.25.
Единицы тела: подошва y~-0.92, макушка y=1.
"""
import pathlib, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

data, out = (pathlib.Path(a) for a in sys.argv[1:3])
photo, landmarker = (sys.argv[3:5] + [None, None])[:2]

def load(name):
    """карта развёртки (с заполнением пустот ближайшей точкой) и исходная текстура"""
    A = np.fromfile(data / f"{name}-uv.f32", dtype=np.float32)
    n = int(round((A.size / 7) ** .5))
    A = A.reshape(n, n, 7)
    fill = ndi.distance_transform_edt(~(A[..., 6] == 1), return_distances=False, return_indices=True)
    tex = np.asarray(Image.open(data / f"{name}-orig.png").convert("RGB").resize((n, n), Image.LANCZOS), dtype=np.float32) / 255
    return A[fill[0], fill[1]], A[..., 6] == 1, fill, tex

def save(img, name):
    Image.fromarray((np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)).save(out / name, quality=90, method=6)

A, cov, fill, orig = load("suit")           # вне развёртки берём ближайшую точку: без тёмных краёв на швах
N = A.shape[0]
x, y, z = A[..., 0], A[..., 1], A[..., 2]

rows, cols = np.mgrid[0:N, 0:N] / N
shirt = rows < .43                            # куртка: верхняя часть развёртки
sleeve = (rows >= .55) & (cols >= .74)        # рукава: справа внизу
pants = ~shirt & ~sleeve

# фактура ткани из исходной текстуры: только мелкие складки и строчки, без пятен варёной джинсы и логотипа
lum = orig @ np.array([.299, .587, .114], np.float32)
logo = shirt & (z > 0) & ((x / .21) ** 2 + ((y - .74) / .14) ** 2 < 1)    # логотип исходника на груди
orange = (orig[..., 0] - orig[..., 2] > .25) & (orig[..., 0] > orig[..., 1]) & ~logo   # канты по низу куртки и рукавов
hp = lum - ndi.gaussian_filter(lum, 3)
hp[ndi.binary_dilation(orange | logo, iterations=6)] = 0
hp = np.clip(hp, -.12, .12)

def srgb(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)

col = np.empty((N, N, 3), np.float32)
col[:] = srgb("#9aa0a9")
col[pants] = srgb("#8a9099")
col *= (1 + np.where(pants, .6, 1.1) * hp)[..., None]
glow = np.zeros((N, N), np.float32)

def seg_dist(px, py, a, b):
    ax, ay = a; bx, by = b
    vx, vy = bx - ax, by - ay
    t = np.clip(((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy), 0, 1)
    return np.hypot(px - ax - t * vx, py - ay - t * vy)

def poly_dist(px, py, pts):
    return np.min([seg_dist(px, py, pts[i], pts[i + 1]) for i in range(len(pts) - 1)], axis=0)

def line(mask, d, w, soft):
    """коэффициент 0..1 линии шириной w с мягким краем soft"""
    return np.where(mask, np.clip((w / 2 + soft - d) / soft, 0, 1), 0)

front = (shirt & (z > .02))
back = (shirt & (z < -.02))

# швы реглана от ворота к подмышке: тёмная бороздка и светлый край
for s in (-1, 1):
    for m in (front, back):
        d = poly_dist(x, y, [(s * .075, .935), (s * .16, .83), (s * .235, .72)])
        groove = line(m, d, .004, .002)
        lip = line(m, np.abs(d - .005), .002, .002)
        col *= (1 - .45 * groove)[..., None]
        col += (.06 * lip)[..., None]

# молния по центру спереди
zip_m = front & (y < .925)
zd = np.abs(x)
tape = line(zip_m, zd, .016, .002)
teeth = line(zip_m, zd, .006, .0015) * (np.sin(y / .0045 * np.pi) > 0)
col = col * (1 - .35 * tape)[..., None] + (.1 * teeth)[..., None]
pull = zip_m & (np.abs(x) < .009) & (y > .865) & (y < .905)
col[pull] = srgb("#d9dde3")

# светящиеся линии на груди: «схема» по обе стороны молнии
for s in (-1, 1):
    paths = [
        [(.018, .805), (.055, .805), (.075, .828), (.135, .828)],
        [(.055, .805), (.074, .782), (.118, .782)],
        [(.075, .828), (.09, .848)],
        [(.152, .80), (.19, .842)],
    ]
    ends = [(.135, .828), (.118, .782), (.09, .848), (.152, .80), (.19, .842)]
    px = x * s
    d = np.min([poly_dist(px, y, p) for p in paths], axis=0)
    de = np.min([np.abs(np.hypot(px - a, y - b) - .006) for a, b in ends], axis=0)
    glow = np.maximum(glow, line(front, np.minimum(d, de), .0035, .0018))

# оранжевые канты исходника -> тонкие голубые линии (низ куртки и рукавов)
core = ndi.distance_transform_edt(orange) > 2.5
glow = np.maximum(glow, ndi.gaussian_filter(core.astype(np.float32), .8) * 1.4)
glow = np.clip(glow, 0, 1)

# нашивка на левом рукаве: прямоугольник с подсветкой
sl = sleeve & (x > .3) & (z > -.02)
if sl.any():
    cx, cy = .345, .74
    d = np.maximum(np.abs(x - cx) - .028, np.abs(y - cy) - .04)
    patch = sl & (d < 0)
    col[patch] *= .82
    glow = np.maximum(glow, line(sl, np.abs(d + .006), .003, .0015))

glow_rgb = glow[..., None] * srgb("#45dcff")
col = col * (1 - glow[..., None]) + glow[..., None] * srgb("#d8f6ff")

# вне развёртки — ближайший цвет (запас на мип-уровни)
save(col[fill[0], fill[1]], "suit.webp")
save(glow_rgb[fill[0], fill[1]], "suit-glow.webp")

# обувь: стопы на текстуре тела перекрашены в графит с подошвой, выше щиколотки всё скрыто брюками
B, bcov, _, skin = load("body")
if photo:
    from face_project import project
    from hair import scalp
    Aw = np.fromfile(data / "bodyw-uv.f32", dtype=np.float32).reshape(skin.shape[0], skin.shape[1], 7)
    skin = project(skin, Aw, data / "front.png", data / "front-z.f32", photo, landmarker)
    # кожа под волосами в цвет корней: без просветов между прядями
    sw = ndi.gaussian_filter(np.nan_to_num(scalp(Aw[..., :3])).astype(np.float32), 2)[..., None]
    roots = srgb("#3b2619") * (1 + .25 * ndi.gaussian_filter(np.random.default_rng(3).normal(0, 1, sw.shape[:2]), 1)[..., None])
    skin = skin * (1 - sw) + roots * sw
by = B[..., 1]
blum = skin @ np.array([.299, .587, .114], np.float32)
bhp = np.clip(blum - ndi.gaussian_filter(blum, 2.5), -.1, .1)
shoe = np.clip((-.79 - by) / .006, 0, 1)                    # плавная граница чуть выше манжеты брюк
sc = np.empty_like(skin); sc[:] = srgb("#4d545d")
sc[by < -.9] = srgb("#1c2026")                               # подошва
sc[(by >= -.9) & (by < -.893)] = srgb("#6d7580")             # светлый кант над подошвой
sc *= (1 + .8 * bhp)[..., None]
skin = skin * (1 - shoe[..., None]) + sc * shoe[..., None]
save(skin, "skin.webp")

# глаза: радужка из карих в серо-зелёные, белки без изменений
eye4 = np.asarray(Image.open(data / "eye-orig.png").convert("RGBA"), dtype=np.float32) / 255
eye = eye4[..., :3]                                           # альфа (прозрачная роговица) сохраняется
red = (eye[..., 0] - eye[..., 1] > .12) & (eye[..., 0] > .2)
lab, n = ndi.label(ndi.binary_opening(red, iterations=2))
iris = np.zeros(red.shape, bool)
yy, xx = np.mgrid[0:eye.shape[0], 0:eye.shape[1]]
for k in np.argsort(ndi.sum(red, lab, range(1, n + 1)))[-2:] + 1:   # две самые большие области: радужки
    cy, cx = ndi.center_of_mass(lab == k)
    r = ((lab == k).sum() / np.pi) ** .5
    iris |= (yy - cy) ** 2 + (xx - cx) ** 2 < (r * 1.08) ** 2
ilum = eye @ np.array([.299, .587, .114], np.float32)
tone = ilum / max(1e-3, float(np.median(ilum[iris & red])))
green = np.clip(srgb("#6f9a8c")[None, None] * tone[..., None] ** .8, 0, 1)
eye = np.where(iris[..., None], green, eye)
Image.fromarray((np.clip(np.dstack([eye, eye4[..., 3]]), 0, 1) * 255 + .5).astype(np.uint8), "RGBA").save(out / "eyes.webp", quality=90, method=6)
print("->", out / "suit.webp", out / "suit-glow.webp", out / "skin.webp", out / "eyes.webp")
