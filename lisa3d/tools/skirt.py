#!/usr/bin/env python3
"""Юбка облегающего мини-платья: кольца по сечениям бёдер от талии до низа юбки.

Сечение на каждой высоте — выпуклая оболочка обеих ног (юбка идёт через ноги, а не облегает каждую),
отступ от брюк модели, верх заходит под край рубашки. Привязку к костям (таз и бёдра) и отталкивание
от бёдер в движении делает движок.
    node uvmap.mjs ../avatar.glb suit data/suitw-uv.f32 data/suitw-orig.png 1024 world
    python3 skirt.py data ../../avatar2/skirt.bin

Формат skirt.bin: 'SKRT', u16 версия, u16 колец, u16 точек в кольце, u16 0, f32[3] начало, f32 шаг;
i16[кольца*точки*3] точки (м = начало + i * шаг), кольцо 0 — верх, точка 0 — спереди по центру, обход к левому боку.
"""
import pathlib, struct, sys
import numpy as np
from scipy.spatial import ConvexHull
from scipy.ndimage import gaussian_filter1d

data, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
TOP, HEM, M = .995, .66, 72
SHIRT_HEM = .967

S = np.fromfile(data / "suitw-uv.f32", dtype=np.float32).reshape(1024, 1024, 7)
rows, cols = np.mgrid[0:1024, 0:1024] / 1024
cov = S[..., 6] == 1
pants = S[cov & (rows >= .43) & ~((rows >= .55) & (cols >= .74))][:, :3]
shirt = S[cov & (rows < .43)][:, :3]


def radial(P, y, cz):
    """сечение на высоте y: радиус выпуклой оболочки по направлениям (0 = вперёд, к левому боку)"""
    sl = P[np.abs(P[:, 1] - y) < .006][:, [0, 2]] - [0, cz]
    hull = sl[ConvexHull(sl).vertices]
    th = np.arctan2(hull[:, 0], hull[:, 1])
    o = np.argsort(th); hull, th = hull[o], th[o]
    ang = np.linspace(-np.pi, np.pi, M, endpoint=False) + np.pi    # 0 спереди
    ang = (ang + np.pi) % (2 * np.pi) - np.pi
    r = np.zeros(M)
    for k, a in enumerate(ang):                                     # луч из центра до стороны оболочки
        d = np.array([np.sin(a), np.cos(a)])
        best = 0
        for i in range(len(hull)):
            p, q = hull[i], hull[(i + 1) % len(hull)]
            e = q - p; den = d[0] * e[1] - d[1] * e[0]
            if abs(den) < 1e-12: continue
            t = (p[0] * e[1] - p[1] * e[0]) / den
            u = (p[0] * d[1] - p[1] * d[0]) / den
            if t > 0 and -1e-9 <= u <= 1 + 1e-9: best = max(best, t)
        r[k] = best
    return ang, r


ys = np.linspace(TOP, HEM, int(round((TOP - HEM) / .012)) + 1)
cz = np.median(pants[np.abs(pants[:, 1] - .85) < .01][:, 2])
rings = []
for y in ys:
    ang, r = radial(pants, y, cz)
    r = r + np.interp(y, [HEM, .85, TOP], [.013, .011, .008])           # отступ от брюк: свободнее к низу
    if y > SHIRT_HEM - .01:                                             # верх под рубашкой, но не глубже брюк
        _, rs = radial(shirt, max(y, SHIRT_HEM + .004), cz)
        _, rp = radial(pants, y, cz)
        r = np.maximum(np.minimum(r, rs - .004), rp + .004)
    rings.append(r)
R = np.array(rings)
R = gaussian_filter1d(R, 1.0, axis=0, mode="nearest")                   # плавно по высоте
R = gaussian_filter1d(R, 1.2, axis=1, mode="wrap")                      # и по кругу
ang = (np.linspace(0, 2 * np.pi, M, endpoint=False) + np.pi) % (2 * np.pi) - np.pi
P = np.stack([np.sin(ang)[None] * R, np.repeat(ys[:, None], M, 1), cz + np.cos(ang)[None] * R], -1)

org = np.array([0., .8, 0.]); q = 1 / 8000
with open(out, "wb") as f:
    f.write(b"SKRT" + struct.pack("<4H", 1, len(ys), M, 0) + struct.pack("<4f", *org, q))
    f.write(np.clip(np.round((P - org) / q), -32767, 32767).astype("<i2").tobytes())
print("колец", len(ys), "точек", M, "радиус у низа %.3f..%.3f" % (R[-1].min(), R[-1].max()), "->", out)
