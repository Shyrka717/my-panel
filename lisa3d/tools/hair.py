#!/usr/bin/env python3
"""Волосы: каштановое каре до плеч, боковой пробор, крупные волны (как на фото).

Пряди растут от корней по линии роста волос, «расчёсываются» по голове от пробора, обходят лицо
и ложатся на плечи; столкновения считаются по поверхности тела и костюма в позе покоя.
    node uvmap.mjs ../avatar.glb '^base' data/head-uv.f32 data/head-orig.png 2048 world
    node uvmap.mjs ../avatar.glb suit data/suitw-uv.f32 data/suitw-orig.png 1024 world
    python3 hair.py data ../../avatar2/hair.bin

Формат hair.bin (little-endian): 'HAIR', u16 версия, u16 прядей, u16 точек в пряди, u16 0,
f32[3] начало координат, f32 шаг; i16[пряди*точки*3] точки (м = начало + i * шаг);
u8[пряди*точки*2] веса костей Head и Neck (остаток — Spine2); u8[пряди*2] ширина (0.1 мм) и тон.
Координаты — сцена модели в позе покоя (как у glTF), поэтому прядь привязывается к её скелету как есть.
"""
import pathlib, struct, sys
import numpy as np

HEAD_C = np.array([0., 1.665, .05])      # центр черепа, м
PART_X = -.022                           # пробор справа (у неё), как на фото
NPTS = 18


def hairline(az):
    """минимальная высота корней (угол над центром головы, град) по азимуту (0 = лоб, 180 = затылок)"""
    return np.interp(np.abs(az), [0, 30, 60, 90, 120, 160, 180], [33, 33, 16, 2, -15, -38, -38])


def head_angles(X):
    dz = X[..., 2] - HEAD_C[2]
    az = np.degrees(np.arctan2(X[..., 0], dz))
    el = np.degrees(np.arctan2(X[..., 1] - HEAD_C[1], np.hypot(X[..., 0], dz)))
    return az, el


def scalp(X):
    """0..1: точка кожи головы под волосами (без ушей и лица)"""
    az, el = head_angles(X)
    ear = (np.abs(X[..., 0]) > .083) & (X[..., 1] < 1.70)
    return np.clip((el - hairline(az)) / 3, 0, 1) * (X[..., 1] > 1.55) * ~ear


def smooth(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def main():
    from scipy.spatial import cKDTree
    data, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    rng = np.random.default_rng(7)

    def surface(name, n):
        A = np.fromfile(data / f"{name}-uv.f32", dtype=np.float32).reshape(n, n, 7)
        A = A[(A[..., 6] == 1) & (A[..., 1] > 1.25)].astype(np.float64)
        return A[:, :3], A[:, 3:6] / (np.linalg.norm(A[:, 3:6], axis=1, keepdims=True) + 1e-9)

    bp, bn = surface("head", 2048)
    sp, sn = surface("suitw", 1024)
    P, Nn = np.vstack([bp, sp]), np.vstack([bn, sn])
    _, keep = np.unique(np.floor(P / .003).astype(int), axis=0, return_index=True)   # сетка 3 мм: быстрее и достаточно
    P, Nn = P[keep], Nn[keep]
    tree = cKDTree(P)

    def push_out(X, margin):
        """точки ближе margin к телу выталкиваются по нормали поверхности"""
        _, i = tree.query(X)
        h = np.einsum("ij,ij->i", X - P[i], Nn[i])
        m = h < margin
        X[m] += Nn[i[m]] * (margin[m] - h[m])[:, None]
        return X

    def hug(X, margin, w):
        """на голове прядь лежит слоем: дальше margin притягивается к коже (вес w)"""
        _, i = tree.query(X)
        h = np.einsum("ij,ij->i", X - P[i], Nn[i])
        m = (w > 0) & (h > margin + .003) & (h < .06) & (P[i, 1] > 1.56)
        X[m] -= Nn[i[m]] * ((h[m] - margin[m] - .003) * w[m])[:, None]
        return X

    def off_face(X):
        """лицо открыто: пряди ниже линии волос уходят к краям лица"""
        y = X[:, 1]
        xl = np.interp(y, [1.50, 1.54, 1.60, 1.70, 1.73], [.055, .062, .068, .068, .05])
        m = (y > 1.50) & (y < 1.73) & (X[:, 2] > HEAD_C[2] + .02) & (np.abs(X[:, 0]) < xl)
        X[m, 0] = np.where(X[m, 0] < PART_X, -1, 1) * xl[m]
        return X

    # корни: равномерно по коже головы (сетка 8.5 мм), случайная точка в каждой ячейке
    cand = bp[:, 1] > 1.55
    sc = scalp(bp[cand]) > .99
    R, RN = bp[cand][sc], bn[cand][sc]
    perm = rng.permutation(len(R)); R, RN = R[perm], RN[perm]
    _, first = np.unique(np.floor(R / .0085).astype(int), axis=0, return_index=True)
    R, RN = R[first], RN[first]
    n = len(R)

    # направление расчёсывания: от пробора вбок и вниз, на затылке вниз
    ex, ey, ez = np.eye(3)
    side = np.where(R[:, 0] < PART_X, -1., 1.)
    front = smooth((R[:, 2] - (HEAD_C[2] - .045)) / .03)
    edge = smooth((R[:, 2] - .10) / .03)                         # у самой линии лба — сильнее вбок
    g = (front[:, None] * (side[:, None] * ex * (1 + .3 * edge[:, None]) - ey * (.55 - .2 * edge[:, None]) - ez * .2)
         + (1 - front[:, None]) * (-ey - ez * .35 + ex * .25 * np.sign(R[:, 0])[:, None]))
    g -= RN * np.einsum("ij,ij->i", g, RN)[:, None]
    g /= np.linalg.norm(g, axis=1, keepdims=True)

    lift = rng.uniform(.004, .018, n)                            # слой: объём причёски
    y_end = 1.458 + rng.uniform(-.015, .022, n) + .01 * (1 - front)
    step = .008
    X = R + RN * lift[:, None]
    d = g.copy()
    paths = [X.copy()]
    alive = np.ones(n, bool)
    for k in range(80):
        y = X[:, 1]
        down = np.tile(-ey, (n, 1))
        radial = X - HEAD_C; radial[:, 1] = 0
        radial /= np.linalg.norm(radial, axis=1, keepdims=True) + 1e-9
        on_head = smooth((y - 1.59) / .04)[:, None]
        t = on_head * (d * .75 + g * .25 + down * .15) + (1 - on_head) * (d * .6 + down * .45 + radial * .1)
        t /= np.linalg.norm(t, axis=1, keepdims=True)
        Xn = X + t * step
        margin = lift + .02 * smooth((1.66 - Xn[:, 1]) / .1)
        Xn = off_face(push_out(hug(Xn, margin, on_head[:, 0]), margin))
        dn = Xn - X
        d = dn / (np.linalg.norm(dn, axis=1, keepdims=True) + 1e-9)
        X = np.where(alive[:, None], Xn, X)
        alive &= X[:, 1] > y_end
        paths.append(X.copy())
        if not alive.any(): break
    paths = np.stack(paths, 1)                                    # (n, шаги, 3)

    # равномерная передискретизация по длине
    seg = np.linalg.norm(np.diff(paths, axis=1), axis=2)
    S = np.concatenate([np.zeros((n, 1)), np.cumsum(seg, 1)], 1)
    L = S[:, -1]
    St = np.linspace(0, 1, NPTS)[None] * L[:, None]
    pts = np.stack([np.stack([np.interp(St[i], S[i], paths[i, :, c]) for c in range(3)], 1) for i in range(n)])

    # волны прядями: соседние корни (ячейка 2.5 см) волнятся вместе
    cell = np.unique(np.floor(R / .025).astype(int), axis=0, return_inverse=True)[1].ravel()
    nc = cell.max() + 1
    ph = rng.uniform(0, 2 * np.pi, nc)[cell] + rng.uniform(-.4, .4, n)
    amp = rng.uniform(.018, .028, nc)[cell]
    lam = rng.uniform(.075, .105, nc)[cell]
    T = np.gradient(pts, axis=1); T /= np.linalg.norm(T, axis=2, keepdims=True) + 1e-9
    Rd = pts - HEAD_C; Rd[..., 1] *= .3
    Rd /= np.linalg.norm(Rd, axis=2, keepdims=True) + 1e-9
    B = np.cross(T, Rd); B /= np.linalg.norm(B, axis=2, keepdims=True) + 1e-9
    s0 = np.array([St[i][np.argmax(pts[i, :, 1] < 1.67)] if (pts[i, :, 1] < 1.67).any() else L[i] for i in range(n)])
    ww = smooth((St - s0[:, None] + .02) / .07) * (1 + .6 * smooth((St / L[:, None] - .7) / .3))
    w = 2 * np.pi * St / lam[:, None] + ph[:, None]
    pts = pts + (amp[:, None] * ww)[..., None] * (.8 * np.sin(w)[..., None] * B + .9 * np.cos(w)[..., None] * Rd)
    flat = pts.reshape(-1, 3)
    marg = np.repeat(lift, NPTS) + .008
    pts = off_face(push_out(flat, marg)).reshape(n, NPTS, 3)
    pts[:, 0] = R + RN * lift[:, None] * .5                       # корень у кожи

    # веса костей: у головы — голова, кончики делят шея и грудь (лежат на плечах)
    y = pts[..., 1]
    wh = np.interp(y, [1.45, 1.52, 1.60], [.45, .65, 1.])
    ws = np.interp(y, [1.45, 1.50], [.25, 0.])
    wn = 1 - wh - ws
    lv = (lift - .004) / .014                                     # 0 внутренний слой .. 1 внешний
    width = np.clip(rng.uniform(14, 22, n) * (1.15 - lv * .3), 10, 25)                   # мм; внутренние шире
    tone = np.clip(.7 + lv * .4 + rng.normal(0, .07, n), .55, 1.15)                       # внешние светлее

    org = np.array([0., 1.6, 0.]); q = 1 / 8000
    with open(out, "wb") as f:
        f.write(b"HAIR" + struct.pack("<4H", 1, n, NPTS, 0) + struct.pack("<4f", *org, q))
        f.write(np.clip(np.round((pts - org) / q), -32767, 32767).astype("<i2").tobytes())
        f.write(np.stack([np.round(wh * 255), np.round(wn * 255)], -1).astype(np.uint8).tobytes())
        f.write(np.stack([np.round(width * 10), np.round(tone / 1.2 * 255)], -1).clip(0, 255).astype(np.uint8).tobytes())
    print("прядей", n, "точек", NPTS, "длина", round(L.mean(), 3), "м ->", out, out.stat().st_size // 1024, "КБ")


if __name__ == "__main__":
    main()
