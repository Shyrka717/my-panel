#!/usr/bin/env python3
"""Наряд для второй девушки: чёрное атласное мини-платье с глубоким V-вырезом на широких бретелях,
чёрные чулки с ромбическим узором и плотной резинкой, лаковые туфли.

У модели под одеждой нет тела (торс и ноги удалены), поэтому платье рисуется на сетке рубашки,
чулки на сетке брюк, а открытые места (вырез, плечи, руки выше локтя, полоска бедра над чулком)
закрашиваются кожей её тона. Юбка строится отдельно (skirt.py), каблуки ставит движок.
Координаты в метрах сцены (карты uvmap.mjs с world).
    node uvmap.mjs ../avatar.glb suit data/suitw-uv.f32 data/suitw-orig.png 1024 world
    node uvmap.mjs ../avatar.glb '^base' data/bodyw-uv.f32 data/bodyw-orig.png 1024 world
    node front-render.mjs ../avatar.glb data/front.png data/front-z.f32
    python3 make-dress.py data ../../avatar2 ../../avatar2/portrait.webp data/face_landmarker.task
-> dress.webp (цвет одежды), dress-pbr.webp (R лак, G шероховатость), skin.webp, skin-pbr.webp
"""
import pathlib, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

data, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
photo, landmarker = sys.argv[3], sys.argv[4]
HEM, BAND_TOP, BAND_LOW = .66, .625, .595          # низ юбки, верх и низ резинки чулка (м)


def srgb(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)


def smooth(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def load(name):
    A = np.fromfile(data / f"{name}-uv.f32", dtype=np.float32)
    n = int(round((A.size / 7) ** .5)); A = A.reshape(n, n, 7)
    fill = ndi.distance_transform_edt(~(A[..., 6] == 1), return_distances=False, return_indices=True)
    return A[fill[0], fill[1]], A[..., 6] == 1, fill


def save(img, name):
    a = (np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)
    Image.fromarray(a).save(out / name, quality=92, method=6)


def pbr(coat, rough):
    """R — доля лака (clearcoat), G — шероховатость, B не используется"""
    return np.dstack([coat, rough, np.zeros_like(coat)])


# ---------- кожа тела: лицо с фото, кожа головы под волосами ----------
from face_project import project
from hair import scalp
B, bcov, bfill = load("bodyw")
skin = np.asarray(Image.open(data / "bodyw-orig.png").convert("RGB"), dtype=np.float32) / 255
raw = np.fromfile(data / "bodyw-uv.f32", dtype=np.float32).reshape(B.shape)
skin = project(skin, raw, data / "front.png", data / "front-z.f32", photo, landmarker)
sw = ndi.gaussian_filter(np.nan_to_num(scalp(B[..., :3])).astype(np.float32), 2)[..., None]
roots = srgb("#3b2619") * (1 + .25 * ndi.gaussian_filter(np.random.default_rng(3).normal(0, 1, sw.shape[:2]), 1)[..., None])
skin = skin * (1 - sw) + roots * sw
bx, by, bz = B[..., 0], B[..., 1], B[..., 2]

# тон её кожи для нарисованных открытых мест: верх груди и плечо
chest = bcov & (by > 1.40) & (by < 1.44) & (bz > .05) & (np.abs(bx) < .06)
arm = bcov & (by > 1.12) & (by < 1.26) & (np.abs(bx) > .24) & (np.abs(bx) < .34)
TONE_CHEST, TONE_ARM = np.median(skin[chest], 0), np.median(skin[arm], 0)
# кожа плеча — по краю настоящей руки модели (там, где под рукавом начинается рука): без стыка по цвету
S_, E_ = np.array([.181, 1.398, .02]), np.array([.352, 1.208, .019])
bt = (np.stack([np.abs(bx), by, bz], -1) - S_) @ (E_ - S_) / ((E_ - S_) @ (E_ - S_))
TONE_SHOULDER = np.median(skin[bcov & (bt > .28) & (bt < .38) & (np.abs(bx) > .15)], 0)

# ---------- узор чулок по оси ноги ----------
JOINTS = {1: [(.105, .928, .015), (.151, .513, .048), (.191, .071, .019)]}
JOINTS[-1] = [(-a, b, c) for a, b, c in JOINTS[1]]


def stocking(X, sheer_base):
    """полупрозрачный чёрный + ромбы; X — точки (..., 3); sheer_base — цвет кожи под чулком"""
    x, y, z = X[..., 0], X[..., 1], X[..., 2]
    side = np.where(x >= 0, 1, -1)
    S = np.zeros(x.shape); C = np.zeros(x.shape)
    for s in (1, -1):
        m = side == s
        P = X[m]; best = np.full(len(P), 9.); sv = np.zeros(len(P)); cv = np.zeros(len(P)); acc = 0.
        for a, b in zip(JOINTS[s][:-1], JOINTS[s][1:]):
            a, b = np.array(a), np.array(b); v = b - a; L = np.linalg.norm(v); d = v / L
            t = np.clip((P - a) @ d, 0, L); r = P - (a + t[:, None] * d); dist = np.linalg.norm(r, axis=1)
            fwd = np.array([0, 0, 1.]) - d * d[2]; fwd /= np.linalg.norm(fwd); lat = np.cross(d, fwd)
            ang = np.arctan2(r @ lat, r @ fwd)
            k = dist < best; best[k] = dist[k]; sv[k] = acc + t[k]; cv[k] = ang[k] * .06
            acc += L
        S[m] = sv; C[m] = cv
    P_ = .032
    u, v = (C + S) / P_, (C - S) / P_
    line = np.maximum(smooth(1 - np.abs(u - np.round(u)) / .07), smooth(1 - np.abs(v - np.round(v)) / .07))
    dots = smooth(1 - np.hypot(u - np.round(u), v - np.round(v)) / .12)
    col = sheer_base * .18 + srgb("#0a0a0d") * .82
    return col * (1 - .75 * np.maximum(line, dots)[..., None]), S


def lace(X):
    x, y = X[..., 0], X[..., 1]
    a = np.arctan2(x - np.sign(x) * .14, X[..., 2] - .03) * 30
    holes = smooth(1 - np.hypot((a - np.round(a)), ((y - BAND_LOW) / .0075 - np.round((y - BAND_LOW) / .0075))) / .3)
    return holes


# ---------- обувь и чулки на стопах (тело есть только до щиколотки) ----------
feet = bcov & (by < .2)
ank_z = .019
shoe = feet & ((by < .035) | (bz > .11) | ((bz < ank_z - .012) & (by < .085)))
shoe_soft = ndi.gaussian_filter(shoe.astype(np.float32), .8)
st_col, _ = stocking(B[..., :3], TONE_ARM)
foot_mask = ndi.gaussian_filter(feet.astype(np.float32), .8)[..., None]
skin = skin * (1 - foot_mask) + st_col * foot_mask
patent = srgb("#08080a") * (1 + .15 * smooth((by - .02) / .05))[..., None]
skin = skin * (1 - shoe_soft[..., None]) + patent * shoe_soft[..., None]
skin_coat = shoe_soft
skin_rough = np.full(skin.shape[:2], .55, np.float32)
skin_rough = skin_rough * (1 - foot_mask[..., 0]) + .5 * foot_mask[..., 0]
skin_rough = skin_rough * (1 - shoe_soft) + .12 * shoe_soft
save(skin[bfill[0], bfill[1]], "skin.webp")
save(pbr(skin_coat, skin_rough)[bfill[0], bfill[1]], "skin-pbr.webp")

# ---------- платье на сетке рубашки, чулки на сетке брюк ----------
A, cov, fill = load("suitw")
N = A.shape[0]
x, y, z = A[..., 0], A[..., 1], A[..., 2]
ax = np.abs(x)
rows, cols = np.mgrid[0:N, 0:N] / N
shirt = rows < .43
sleeve = (rows >= .55) & (cols >= .74)
pants = ~shirt & ~sleeve
orig = np.asarray(Image.open(data / "suit-orig.png").convert("RGB").resize((N, N), Image.LANCZOS), dtype=np.float32) / 255
lum = orig @ np.array([.299, .587, .114], np.float32)
logo = shirt & (z > 0) & (((x + .002) / .15) ** 2 + ((y - 1.315) / .1) ** 2 < 1)
orange = (orig[..., 0] - orig[..., 2] > .25) & (orig[..., 0] > orig[..., 1]) & ~logo
hp = lum - ndi.gaussian_filter(lum, 3)
hp[ndi.binary_dilation(orange | logo, iterations=6)] = 0
hp = np.clip(hp, -.12, .12)

# вырез: от основания шеи (|x| 0.075) до линии под грудью (y 1.215), края слегка выпуклые
V_BOTTOM, NECK_Y, V_TOP_X = 1.215, 1.445, .075
vh = V_TOP_X * np.clip((y - V_BOTTOM) / (NECK_Y - V_BOTTOM), 0, 1) ** .8
vee = shirt & (z > .03) & (y > V_BOTTOM - .004)
vee_d = (vh - ax)                                          # >0 внутри выреза
vee_m = vee * smooth((vee_d + .002) / .004)
# плечи открыты снаружи бретели (бретель |x| 0.075..0.118), глубокая пройма: ткань не тянется за поднятой рукой
yarm = np.interp(ax, [.118, .14, .155, .17, .2, .3], [1.47, 1.38, 1.30, 1.25, 1.24, 1.24])
shoulder_m = shirt * smooth((ax - .118) / .006) * smooth((y - yarm) / .006)
# на спине вырез между бретелями
back_m = shirt * (z < -.01) * smooth((.075 - ax) / .006) * smooth((y - (1.40 + 1.5 * x * x)) / .006)
skin_m = np.clip(np.maximum.reduce([vee_m, shoulder_m, back_m, sleeve.astype(np.float32)]), 0, 1)

tone = TONE_CHEST * (1 - smooth((ax - .12) / .1))[..., None] + TONE_SHOULDER * smooth((ax - .12) / .1)[..., None]
# ложбинка: тень по центру выреза ниже уровня груди, край ткани отбрасывает лёгкую тень
cleft = vee * np.exp(-(x / .011) ** 2) * smooth((1.33 - y) / .07)
edge_sh = vee * smooth(1 - np.clip(vee_d, 0, 1) / .008) * (vee_d > 0)
skin_col = tone * (1 - .22 * cleft - .12 * edge_sh)[..., None]

dress = srgb("#141418") * (1 + 1.6 * hp)[..., None]
# шов под грудью и вытачки от него вниз
seam = shirt & (z > .02) & (ax < .15) & (np.abs(y - (V_BOTTOM - .002)) < .0018)
dart = shirt & (z > .05) & (np.abs(ax - .085) < .0015) & (y < V_BOTTOM) & (y > 1.0)
dress = dress * (1 - .5 * (seam | dart))[..., None] + .05 * ndi.binary_dilation(seam | dart)[..., None] * (~(seam | dart))[..., None]

col = dress.copy()
col = col * (1 - skin_m[..., None]) + skin_col * skin_m[..., None]
coat = .55 * (1 - skin_m); rough = .32 * (1 - skin_m) + .55 * skin_m

# брюки: под юбкой — ткань платья, полоска кожи, резинка, ниже чулок
st, _ = stocking(A[..., :3], TONE_ARM)
lc = lace(A[..., :3])
leg_skin = pants * smooth((y - BAND_TOP) / .003) * smooth((HEM + .006 - y) / .003)
band = pants * smooth((y - BAND_LOW) / .002) * smooth((BAND_TOP - y) / .002)
under = pants * smooth((y - HEM - .004) / .003)
legs = pants * smooth((BAND_LOW - y) / .002)
pc = srgb("#0c0c0f") * (1 - .5 * lc)[..., None] + TONE_ARM * .25 * lc[..., None]
col = np.where(pants[..., None], 0, col)
col += st * legs[..., None] + pc * band[..., None] + TONE_ARM * leg_skin[..., None] + srgb("#141418") * under[..., None]
coat = np.where(pants, .25 * band + .55 * under, coat)
rough = np.where(pants, .5 * legs + .45 * band + .55 * leg_skin + .32 * under, rough)

save(col[fill[0], fill[1]], "dress.webp")
save(pbr(coat, rough)[fill[0], fill[1]], "dress-pbr.webp")
# проверка: вырез не открывает грудь (вершины груди ±0.088 на высоте 1.274)
apex = shirt & (z > .1) & (np.hypot(ax - .088, y - 1.274) < .04)
print("вырез у вершин груди:", float(vee_m[apex].max()), "(должно быть 0)")
print("->", out / "dress.webp", out / "dress-pbr.webp", out / "skin.webp", out / "skin-pbr.webp")
