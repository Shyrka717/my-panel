#!/usr/bin/env python3
"""Чувственный (эротический) танец для второй девушки: процедурная хореография на её скелете.

Петля 15 с, три фразы по 5 с: покачивание бёдрами с переносом веса, круги бёдрами с руками над головой,
волна телом с руками, скользящими по шее, груди и бёдрам. Ноги и руки ставятся обратной кинематикой
(стопы не скользят), корпус гнётся по сегментам с запаздыванием. Два зеркальных варианта.
Все прежние танцы из набора убираются, остальные движения (речь, ожидание, действия) остаются.
    python3 make-dance.py ../motions.json ../motions.bin ../../avatar2/motions.json ../../avatar2/motions.bin
"""
import json, sys
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as R
from mocap import load_glb_skeleton, tgt_fk, BONES

src_meta, src_bin, out_meta, out_bin = sys.argv[1:5]
FPS, T = 30, 15.0
sk = load_glb_skeleton("data/mpfb.glb")
ix = {n: k for k, n in enumerate(sk["names"])}
LB = [R.from_quat(q) for q in sk["q"]]                       # локальные повороты позы привязки
WB, PB = tgt_fk(sk, sk["q"])                                  # мир в позе привязки
UP = np.array([0., 1., 0.])


def smooth(t):
    t = np.clip(t, 0, 1); return t * t * t * (t * (t * 6 - 15) + 10)


def window(t, a, b, fade=.6):
    """1 внутри [a, b] на круге длиной T, мягкие края"""
    def w(x):
        return smooth((x - (a - fade)) / (2 * fade)) * (1 - smooth((x - (b - fade)) / (2 * fade)))
    return max(w(t), w(t + T), w(t - T))


def min_rot(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); s = np.linalg.norm(v); c = np.dot(a, b)
    if s < 1e-9: return R.identity()
    return R.from_rotvec(v / s * np.arctan2(s, c))


class Pose:
    """локальные повороты + положение таза; мир пересчитывается по требованию"""
    def __init__(self):
        self.L = list(LB); self.t = [x.copy() for x in sk["t"]]

    def fk(self):
        self.W, self.P = tgt_fk(dict(sk, t=self.t), [r.as_quat() for r in self.L])

    def world_delta(self, name, D):
        """повернуть кость (и всё, что ниже) поворотом D в мировых осях"""
        k = ix[name]; p = sk["parent"][k]
        Wp = self.W[p] if p >= 0 else R.identity()
        self.L[k] = Wp.inv() * D * Wp * self.L[k]
        self.fk()

    def aim(self, name, child, target_dir):
        """направить кость на точку: поворот с наименьшим кручением"""
        k = ix[name]; p = sk["parent"][k]
        axis = self.W[k].apply(sk["t"][ix[child]])
        D = min_rot(axis, target_dir)
        self.L[k] = self.W[p].inv() * D * self.W[k]
        self.fk()

    def aim_hinge(self, name, child, d, n, h_local):
        """направить кость по d, повернув ось сгиба h_local в нормаль n: без прокручивания"""
        axis = sk["t"][ix[child]] / np.linalg.norm(sk["t"][ix[child]])
        d = d / np.linalg.norm(d); n = n - d * (n @ d); n /= np.linalg.norm(n)
        Wd, _ = R.align_vectors([d, n], [axis, h_local], weights=[100, 1])
        self.set_world(name, Wd)

    def set_world(self, name, Wd):
        k = ix[name]; p = sk["parent"][k]
        self.L[k] = self.W[p].inv() * Wd
        self.fk()


def two_bone(A, l1, l2, T_, pole):
    """точка сгиба (колено, локоть) для цели T_ с полюсом pole"""
    d = T_ - A; dist = np.clip(np.linalg.norm(d), 1e-4, l1 + l2 - 1e-4); n = d / np.linalg.norm(d)
    a = np.arccos(np.clip((l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist), -1, 1))
    pp = pole - n * np.dot(pole, n); pp /= np.linalg.norm(pp) + 1e-9
    return A + n * l1 * np.cos(a) + pp * l1 * np.sin(a), A + n * dist


# руки: ключевые позы запястья относительно таза, груди или головы (смещения в осях позы привязки) и направление локтя
SPOTS = {
    "hip":   ("Hips",   (.19, .08, .05),   (1, -.3, -.3)),
    "thigh": ("Hips",   (.17, -.15, .08),  (1, 0, -.5)),
    "rib":   ("Spine2", (.17, -.07, .02),  (1, -.3, -.6)),
    "hair":  ("Head",   (.10, .12, -.05),  (1, .3, .6)),
    "over":  ("Head",   (-.02, .33, .05),  (1, 0, .3)),
    "neck":  ("Head",   (.08, -.06, .10),  (1, -.6, .4)),
    "chest": ("Spine2", (.06, .09, .13),   (1, -1, 0)),
}
# время, поза: левая рука ведёт, правая отвечает
KEYS = {
    1: [(0, "hip"), (.8, "hip"), (2, "rib"), (3, "hair"), (4.2, "hair"), (5.4, "over"), (8.6, "over"), (9.6, "hair"),
        (10.6, "neck"), (11.4, "chest"), (12.4, "hip"), (13.2, "thigh"), (14.2, "hip"), (15, "hip")],
    -1: [(0, "hip"), (4.6, "hip"), (5.8, "over"), (8.6, "over"), (9.8, "hair"), (10.6, "hair"), (11.4, "neck"),
         (12.2, "chest"), (13.2, "hip"), (15, "hip")],
}
# граница тела: голова и шея модели + поверхность одежды на торсе и бёдрах (под одеждой тело модели удалено),
# без рук; каждая точка привязана к своему позвонку
SEG = (("Hips", 0, 1.05), ("Spine", 1.05, 1.18), ("Spine1", 1.18, 1.32), ("Spine2", 1.32, 1.50), ("Neck", 1.50, 1.56), ("Head", 1.56, 9))


def body_points():
    A = np.fromfile("data/head-uv.f32", dtype=np.float32).reshape(2048, 2048, 7)
    A = A[(A[..., 6] == 1) & (A[..., 1] > 1.38)]
    S = np.fromfile("data/suitw-uv.f32", dtype=np.float32).reshape(1024, 1024, 7)
    rows, cols = np.mgrid[0:1024, 0:1024] / 1024
    S = S[(S[..., 6] == 1) & ~((rows >= .55) & (cols >= .74)) & (S[..., 1] > .55)]   # костюм без рукавов
    A = np.vstack([A, S]).astype(np.float64)
    X, Nn = A[:, :3], A[:, 3:6] / (np.linalg.norm(A[:, 3:6], axis=1, keepdims=True) + 1e-9)
    arm = np.zeros(len(X), bool)
    for side in ("Left", "Right"):                            # руки модели в позе привязки исключаем
        for a, b in ((side + "Arm", side + "ForeArm"), (side + "ForeArm", side + "Hand"), (side + "Hand", side + "HandMiddle1")):
            pa, pb = PB[ix[a]], PB[ix[b]]; v = pb - pa
            u = np.clip((X - pa) @ v / (v @ v), 0, 1)
            arm |= np.linalg.norm(X - (pa + u[:, None] * v), axis=1) < .065
    X, Nn = X[~arm], Nn[~arm]
    # внутренние поверхности (рот, глазницы) не граница: нормаль смотрит к оси тела
    c = np.where((X[:, 1] > 1.56)[:, None], [0, 1.665, .05], np.c_[np.zeros(len(X)), X[:, 1], np.zeros(len(X))])
    out = np.einsum("ij,ij->i", X - c, Nn) > 0
    X, Nn = X[out], Nn[out]
    _, keep = np.unique(np.floor(X / .01).astype(int), axis=0, return_index=True)
    X, Nn = X[keep], Nn[keep]
    seg = np.zeros(len(X), int)
    for k, (_, lo, hi) in enumerate(SEG): seg[(X[:, 1] >= lo) & (X[:, 1] < hi)] = k
    return X, Nn, seg


BX, BN, BSEG = body_points()


class Body:
    """поверхность тела в текущей позе: точки движутся вместе со своими позвонками"""
    def __init__(self, pose):
        self.X = np.empty_like(BX); self.N = np.empty_like(BN)
        for k, (bone, _, _) in enumerate(SEG):
            m = BSEG == k; b = ix[bone]; D = pose.W[b] * WB[b].inv()
            self.X[m] = pose.P[b] + D.apply(BX[m] - PB[b]); self.N[m] = D.apply(BN[m])
        self.tree = cKDTree(self.X)

    def push(self, x, margin):
        """точка не ближе margin к коже: выталкиваем по нормали"""
        for _ in range(3):
            d, i = self.tree.query(x, k=8)
            h = np.einsum("kj,kj->k", x - self.X[i], self.N[i])
            j = np.argmin(d); hj = h[j]
            if hj >= margin or d[j] > margin + .05: break
            x = x + self.N[i[j]] * (margin - hj)
        return x


# шарнир локтя в позе привязки: ось сгиба в системах плеча и предплечья
def hinge(side):
    a, b, c = (PB[ix[side + n]] for n in ("Arm", "ForeArm", "Hand"))
    n = np.cross(b - a, c - b); n /= np.linalg.norm(n)
    return WB[ix[side + "Arm"]].inv().apply(n), WB[ix[side + "ForeArm"]].inv().apply(n)


HINGE = {s: hinge(s) for s in ("Left", "Right")}
FEET = {1: np.array([.10, PB[ix["LeftFoot"]][1], .03]), -1: np.array([-.10, PB[ix["RightFoot"]][1], .05])}


def spot_world(pose, name, side):
    bone, off, pole = SPOTS[name]
    off = np.array(off) * [side, 1, 1]; pole = np.array(pole, float) * [side, 1, 1]
    k = ix[bone]; D = pose.W[k] * WB[k].inv()
    return pose.P[k] + D.apply(off), D.apply(pole)


def frame(t, mirror):
    w = 2 * np.pi / 2.5
    wa, wb, wc = window(t, 0, 5), window(t, 5, 10), window(t, 10, 15)
    # бёдра: покачивание (A, слабее в C) и круги (B)
    sway = (.07 * wa + .03 * wc) * np.sin(w * t)
    hx = sway + wb * .06 * np.cos(w * t)
    hz = wb * .05 * np.sin(w * t) - wc * .04 * np.sin(w * t - 2.1)
    hy = -.035 - .02 * np.cos(2 * w * t) * (wa + wb) - wc * .04 * (.5 + .5 * np.sin(w * t - 2.5))
    wave = wc * 1.3 * np.sin(w * t)
    roll = 3.4 * hx; yaw = .35 * np.sin(2 * np.pi * t / T) + 1.4 * hx
    pitch = -2.2 * hz - wc * .24 * np.sin(w * t - 2.1)
    hx *= mirror; roll *= mirror; yaw *= mirror

    p = Pose()
    p.t[ix["Hips"]] = sk["t"][ix["Hips"]] + [hx, hy, hz]
    p.fk()
    p.world_delta("Hips", R.from_euler("zyx", [roll, yaw, pitch]))
    # корпус: встречный наклон (грудь ровнее таза) и волна сверху вниз с запаздыванием
    for name, lag, amp in (("Spine", 1.4, .13), ("Spine1", .7, .15), ("Spine2", 0, .16)):
        p.world_delta(name, R.from_euler("zyx", [-.33 * roll, -.3 * yaw, amp * wave if lag == 0 else amp * wc * np.sin(w * t - lag)]))
    head_roll = mirror * (.1 * np.sin(w * t / 2) + .08 * wa)
    p.world_delta("Neck", R.from_euler("zyx", [0, 0, -.5 * .16 * wave]))
    p.world_delta("Head", R.from_euler("zyx", [head_roll, mirror * .15 * np.sin(2 * np.pi * t / 7.5), .08 * wa - .05 * wb]))

    # ноги: стопы стоят, у свободной ноги пятка приподнята
    for side, leg in ((1, "Left"), (-1, "Right")):
        free = smooth(np.clip(-side * hx / .05, 0, 1)) * (wa + wc)
        h = .05 * free
        foot = FEET[side] if mirror == 1 else FEET[-side] * [-1, 1, 1]
        target = foot + [0, h, .3 * h]
        A = p.P[ix[leg + "UpLeg"]]
        knee, end = two_bone(A, np.linalg.norm(sk["t"][ix[leg + "Leg"]]), np.linalg.norm(sk["t"][ix[leg + "Foot"]]),
                             target, np.array([.15 * side, 0, 1.]))
        p.aim(leg + "UpLeg", leg + "Leg", knee - A)
        p.aim(leg + "Leg", leg + "Foot", end - knee)
        th = np.arcsin(np.clip(h / .12, 0, .9))
        p.set_world(leg + "Foot", R.from_euler("x", th) * WB[ix[leg + "Foot"]])
        p.set_world(leg + "ToeBase", WB[ix[leg + "ToeBase"]])

    # руки: запястье по ключевым позам, путь огибает тело (по кругу вокруг оси корпуса), кисть и локоть
    # не заходят под кожу; локоть — шарнир без прокручивания; ключица приподнимается, когда рука выше плеча
    body = Body(p)
    ax_o = p.P[ix["Spine1"]]; ax_u = (p.W[ix["Spine1"]] * WB[ix["Spine1"]].inv()).apply(UP)
    def cyl(x):
        v = x - ax_o; hgt = v @ ax_u; r = v - ax_u * hgt
        return np.arctan2(r[0], r[2]), hgt, np.linalg.norm(r)
    def uncyl(th, hgt, rad):
        return ax_o + ax_u * hgt + np.array([np.sin(th), 0, np.cos(th)]) * rad
    for side, arm in ((1, "Left"), (-1, "Right")):
        keys = KEYS[side * mirror]
        for i in range(len(keys) - 1):
            if keys[i][0] <= t <= keys[i + 1][0]: break
        (t0, s0), (t1, s1) = keys[i], keys[i + 1]
        u = smooth((t - t0) / max(t1 - t0, 1e-6))
        a0, p0 = spot_world(p, s0, side); a1, p1 = spot_world(p, s1, side)
        (th0, h0, r0), (th1, h1, r1) = cyl(a0), cyl(a1)
        dth = (th1 - th0 + np.pi) % (2 * np.pi) - np.pi
        if min(r0, r1) > .12 and abs(dth) < 1.6:
            # вокруг корпуса — по дуге, чтобы кисть шла по телу, а не сквозь него
            target = uncyl(th0 + dth * u, h0 + (h1 - h0) * u, r0 + (r1 - r0) * u + .05 * np.sin(np.pi * u) * (s0 != s1))
        else:
            # у головы и над ней дуга вокруг оси даёт круговой мах: идём прямо, чуть наружу, тело само отодвинет
            out = a0 + a1 - 2 * ax_o; out -= ax_u * (out @ ax_u); out /= np.linalg.norm(out) + 1e-9
            target = a0 * (1 - u) + a1 * u + (out * .04 + ax_u * .0) * np.sin(np.pi * u) * (s0 != s1)
        if s0 == s1 == "over": target += np.array([.02 * np.sin(w * t), .01 * np.sin(2 * w * t), 0])
        pole = p0 * (1 - u) + p1 * u
        lift = np.clip((target[1] - p.P[ix[arm + "Arm"]][1]) / .25, 0, 1)
        p.world_delta(arm + "Shoulder", R.from_euler("z", side * .22 * smooth(lift)))
        target = body.push(target, .045)
        S = p.P[ix[arm + "Arm"]]
        l1, l2 = np.linalg.norm(sk["t"][ix[arm + "ForeArm"]]), np.linalg.norm(sk["t"][ix[arm + "Hand"]])
        for _ in range(3):
            elbow, end = two_bone(S, l1, l2, target, pole)
            e2 = body.push(elbow, .05)                          # локоть снаружи тела
            if np.linalg.norm(e2 - elbow) > 1e-4:
                elbow = S + (e2 - S) / np.linalg.norm(e2 - S) * l1
                end = elbow + (target - elbow) / np.linalg.norm(target - elbow) * l2
            n = np.cross(elbow - S, end - elbow)
            if np.linalg.norm(n) < 1e-4: n = np.cross(pole, elbow - S)   # рука прямая: сгиб в сторону полюса
            hu, hf = HINGE[arm]
            p.aim_hinge(arm + "Arm", arm + "ForeArm", elbow - S, n, hu)
            p.aim_hinge(arm + "ForeArm", arm + "Hand", end - elbow, n, hf)
            # ладонь ложится вдоль тела: пальцы не смотрят внутрь
            hp_, kn = p.P[ix[arm + "Hand"]], p.P[ix[arm + "HandMiddle1"]]
            dh = kn - hp_; dq, iq = body.tree.query(kn + dh * .5)
            if dq < .08 and dh @ body.N[iq] < 0:
                p.aim(arm + "Hand", arm + "HandMiddle1", dh - body.N[iq] * (dh @ body.N[iq]) * 1.15)
            # костяшки и кончики пальцев на коже, а не в ней: если внутри, кисть отходит наружу
            kn = p.P[ix[arm + "HandMiddle1"]]; tip = kn + (kn - p.P[ix[arm + "Hand"]]) * .6
            fixes = [body.push(kn, .02) - kn, body.push(tip, .015) - tip]
            fix = max(fixes, key=np.linalg.norm)
            if np.linalg.norm(fix) < 1e-3: break
            target = target + fix
    return p


def clip(mirror):
    n = int(T * FPS); hips = np.zeros((n, 3)); Q = np.zeros((n, len(BONES), 4)); low = []; depth = []
    for f in range(n):
        p = frame(f / FPS, mirror)
        hips[f] = p.t[ix["Hips"]]
        Q[f] = [p.L[ix[b]].as_quat() for b in BONES]
        low.append(min(p.P[ix[j]][1] for j in ("LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase")))
        # проверка: насколько предплечья и кисти подходят к коже (меньше 0 — внутри тела)
        b = Body(p)
        for arm in ("Left", "Right"):
            e, h, m = (p.P[ix[arm + j]] for j in ("ForeArm", "Hand", "HandMiddle1"))
            for x in [e + (h - e) * a for a in (.3, .6, 1)] + [m, m + (m - h) * .6]:
                d, i = b.tree.query(x)
                if d < .06: depth.append((x - b.X[i]) @ b.N[i])
    hips[:, 1] -= np.percentile(low, 1) - .045               # пол как у остальных записей
    for k in range(Q.shape[1]):
        for f in range(1, n):
            if np.dot(Q[f, k], Q[f - 1, k]) < 0: Q[f, k] = -Q[f, k]
    depth = np.array(depth)
    print("руки у кожи: мин %.3f м, точек глубже 1 см: %d из %d" % (depth.min(), (depth < -.01).sum(), len(depth)))
    return hips, Q


meta = json.load(open(src_meta)); data = open(src_bin, "rb").read()
st = meta["stride"]
assert meta["bones"] == BONES
keep = [c for c in meta["clips"] if c["group"] != "dance"]
chunks, header, off = [], [], 0
for c in keep:
    buf = data[c["offset"]:c["offset"] + c["frames"] * st * 2]
    header.append(dict(c, offset=off)); chunks.append(buf); off += len(buf)
for name, mirror in (("erotic1", 1), ("erotic2", -1)):
    hips, Q = clip(mirror)
    n = len(Q)
    hp = np.clip(np.round(hips / meta["posScale"]), -32767, 32767).astype("<i2")
    qq = np.clip(np.round(Q / meta["quatScale"]), -32767, 32767).astype("<i2")
    buf = np.concatenate([hp, qq.reshape(n, -1)], axis=1).astype("<i2").tobytes()
    header.append({"name": name, "group": "dance", "title": "Эротический танец", "frames": n, "offset": off})
    chunks.append(buf); off += len(buf)
    print(name, n / FPS, "с")
open(out_meta, "w").write(json.dumps(dict(meta, clips=header), ensure_ascii=False, separators=(",", ":")))
open(out_bin, "wb").write(b"".join(chunks))
print("клипов", len(header), "->", out_bin, round(off / 1e6, 2), "МБ")
