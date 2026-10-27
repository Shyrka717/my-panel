#!/usr/bin/env python3
"""Туфли-лодочки с острым мысом: оболочка по форме стопы модели (позa покоя), шпильку ставит движок.

Стопа режется поперёк на срезы; каждый срез — выпуклая оболочка сечения с отступом 3 мм и плоской подошвой.
Туфля закрывает носок целиком, бока до вырезa лодочки и пятку задником; перед пальцами — острый мыс.
    node uvmap.mjs ../avatar.glb '^base' data/head-uv.f32 data/head-orig.png 2048 world
    python3 shoes.py data ../../avatar2/shoes.bin

Формат shoes.bin: 'SHOE', u16 версия, u16 срезов, u16 точек в срезе, u16 0, f32[3] начало, f32 шаг,
f32 z подушечки стопы (граница стопа/пальцы), затем для левой и правой туфли: f32[3] точка шпильки
(низ пятки) и i16[срезы*точки*3] точки.
"""
import pathlib, struct, sys
import numpy as np
from scipy.spatial import ConvexHull

data, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
M, PAD = 25, .003
A = np.fromfile(data / "head-uv.f32", dtype=np.float32).reshape(2048, 2048, 7)
F = A[(A[..., 6] == 1) & (A[..., 1] < .2)][:, :3].astype(np.float64)
ANKLE_Z, BALL_Z = .019, .125                       # щиколотка и подушечка (кость пальцев z 0.137)


def collar(z, z0, z1):
    """высота края туфли над подошвой: задник выше, у подъёма вырез лодочки, носок закрыт"""
    return np.interp(z, [z0, z0 + .03, ANKLE_Z + .01, BALL_Z - .035, BALL_Z - .01], [.055, .05, .03, .03, .1])


def shoe(side):
    P = F[np.sign(F[:, 0]) == side]
    sole = P[:, 1].min() - PAD
    z0, z1 = P[:, 2].min() - PAD, P[:, 2].max()
    zs = np.arange(z0, z1, .008)
    rings = []
    for z in zs:
        sl = P[np.abs(P[:, 2] - z) < .006][:, :2]
        if len(sl) < 8: continue
        cx = sl[:, 0].mean()
        h = sl[ConvexHull(sl).vertices] - [cx, 0]
        # оболочка с отступом: из центра среза по лучам
        cy = (h[:, 1].min() + h[:, 1].max()) / 2
        ang = np.arctan2(h[:, 0], -(h[:, 1] - cy))         # 0 — вниз (подошва), ±π — верх
        o = np.argsort(ang); h, ang = h[o], ang[o]
        top = sole + collar(z, z0, z1)
        full = z > BALL_Z - .012
        tmax = np.pi if full else None
        pts = []
        for t in np.linspace(-1, 1, M):
            a = t * (tmax if tmax else np.pi)
            d = np.array([np.sin(a), -np.cos(a)])
            best = 0
            for i in range(len(h)):
                p, q = h[i] - [0, cy], h[(i + 1) % len(h)] - [0, cy]
                e = q - p; den = d[0] * e[1] - d[1] * e[0]
                if abs(den) < 1e-12: continue
                tt = (p[0] * e[1] - p[1] * e[0]) / den; u = (p[0] * d[1] - p[1] * d[0]) / den
                if tt > 0 and -1e-9 <= u <= 1 + 1e-9: best = max(best, tt)
            q = d * (best + PAD) + [cx, cy]
            pts.append([q[0], max(q[1], sole), z])
        pts = np.array(pts)
        if not full:                                        # вырез лодочки: точки выше края опускаем на край
            pts[:, 1] = np.minimum(pts[:, 1], top)
        rings.append(pts)
    R = np.array(rings)
    # острый мыс: срезы сужаются и опускаются к острию на 3.5 см впереди пальцев
    last = R[-1]; c = last.mean(0)
    for k in range(1, 6):
        f = 1 - k / 6
        ring = last.copy()
        ring[:, 0] = c[0] + (ring[:, 0] - c[0]) * f ** .8
        ring[:, 1] = sole + (ring[:, 1] - sole) * f ** .6
        ring[:, 2] = last[:, 2].max() + .035 * k / 6
        R = np.concatenate([R, ring[None]])
    heel = np.array([R[0][:, 0].mean(), sole, z0 + .018])
    return R, heel


L, hl = shoe(1)
Rr, hr = shoe(-1)
n = min(len(L), len(Rr)); L, Rr = L[-n:], Rr[-n:]
org = np.array([0., 0., .05]); q = 1 / 8000
with open(out, "wb") as f:
    f.write(b"SHOE" + struct.pack("<4H", 1, n, M, 0) + struct.pack("<4f", *org, q) + struct.pack("<f", BALL_Z))
    for R, heel in ((L, hl), (Rr, hr)):
        f.write(struct.pack("<3f", *heel))
        f.write(np.clip(np.round((R - org) / q), -32767, 32767).astype("<i2").tobytes())
print("срезов", n, "точек", M, "пятка", hl.round(3), "->", out)
