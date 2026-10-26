import sys, json, struct, numpy as np
sys.path.insert(0, ".")
from scipy.spatial.transform import Rotation as R
from mocap import Retarget, parse_bvh, tgt_fk, BONES

# имя, файл, [начало, конец] в секундах (None = авто), корень: free | inplace | hold, группа, флаги
CLIPS = [
    # танцы
    ("salsa1", "60_01", None, "dance", "dance", "Сальса"),
    ("salsa2", "61_01", None, "dance", "dance", "Сальса"),
    ("salsa3", "60_02", None, "dance", "dance", "Сальса"),
    ("salsa4", "61_02", None, "dance", "dance", "Сальса"),
    ("charleston1", "93_03", (0.3, 3.5), "dance", "dance", "Чарльстон"),
    ("charleston2", "93_04", None, "dance", "dance", "Чарльстон"),
    ("charleston3", "93_08", None, "dance", "dance", "Чарльстон"),
    ("lindy", "93_06", None, "dance", "dance", "Линди-хоп"),
    ("indian1", "94_01", None, "dance", "dance", "Индийский танец"),
    ("indian2", "94_02", None, "dance", "dance", "Индийский танец"),
    ("indian3", "94_05", None, "dance", "dance", "Индийский танец"),
    ("modern1", "05_02", None, "dance", "dance", "Современный танец"),
    ("modern2", "05_11", None, "dance", "dance", "Современный танец"),
    ("modern3", "49_09", None, "dance", "dance", "Современный танец"),
    ("russian1", "90_30", None, "dance", "dance", "Русский танец"),
    ("russian2", "90_31", None, "dance", "dance", "Русский танец"),
    ("moonwalk", "90_32", None, "dance", "dance", "Лунная походка"),
    ("twist", "141_12", None, "dance", "dance", "Твист"),
    ("macarena", "143_35", None, "dance", "dance", "Макарена"),
    ("chicken", "143_34", None, "dance", "dance", "Танец утят"),
    # речь и ожидание
    ("talk1", "80_14", (0.5, 7.5), "dance", "talk", ""),
    ("talk2", "80_14", (7.5, 14.3), "dance", "talk", ""),
    ("talk3", "80_06", None, "dance", "talk", ""),
    ("talk4", "79_16", None, "dance", "talk", ""),
    ("talk5", "80_48", None, "dance", "talk", ""),
    ("idle1", "140_06", None, "dance", "idle", ""),
    ("idle2", "140_07", None, "dance", "idle", ""),
    ("idle3", "141_20", None, "dance", "idle", ""),
    ("idle4", "137_23", None, "dance", "idle", ""),
    ("idle5", "137_37", None, "dance", "idle", ""),
    # передвижение
    ("walk1", "137_24", None, "inplace", "walk", ""),
    ("walk2", "91_29", None, "inplace", "walk", ""),
    ("run1", "35_17", None, "inplace", "run", ""),
    ("run2", "16_35", None, "inplace", "run", ""),
    ("run3", "35_18", None, "inplace", "run", ""),
    # действия
    ("jump1", "13_39", (0.6, 2.5), "free", "jump", ""),
    ("jump2", "16_01", (0.6, 2.2), "free", "jump", ""),
    ("jump3", "143_06", None, "free", "jump", ""),
    ("spin", "91_60", (0.8, 2.6), "free", "spin", ""),
    ("turn", "91_54", (3.2, 5.2), "free", "turn", ""),
    ("sit_down", "140_08", (2.75, 6.2), "free", "sit", "reverse"),
    ("sit_hold", "140_08", (2.75, 3.15), "free", "sitidle", ""),
    ("sit_up", "140_08", (2.75, 6.2), "free", "standup", ""),
    ("lie_hold", "140_08", (0.4, 1.8), "free", "lieidle", ""),
    ("lie_up", "140_08", (1.8, 6.2), "free", "getup", ""),
    ("lie_down", "140_08", (1.8, 6.2), "free", "liedown", "reverse"),
    ("wave1", "143_25", None, "free", "wave", ""),
    ("wave2", "141_16", None, "free", "wave", ""),
    ("bow", "141_26", (0.6, 3.1), "inplace", "bow", ""),
    ("shrug", "141_21", None, "free", "shrug", ""),
    ("stretch", "141_13", None, "dance", "stretch", ""),
    ("laugh", "13_14", (3.0, 11.0), "dance", "laugh", ""),
    ("happy", "79_69", None, "free", "happy", ""),
    ("peekaboo", "141_18", None, "dance", "peekaboo", ""),
    ("jacks", "13_29", (0.5, 8.0), "free", "jacks", ""),
    ("highfive", "141_22", None, "inplace", "highfive", ""),
]

FPS = 30
LIE_YAW = 80
LIE_SHIFT = -0.08   # таз чуть левее центра: тело целиком в кадре
LIE_O = [None]
FAMILY = {"75_20": (0.8, (0.8, 3.7)), "140_08": (6.0, (0.4, 6.2))}   # опорный кадр (с) и отрезок для пола
floor_cache = {}
rt = Retarget("data/mpfb.glb", "data/bvh/141_16.bvh")
sk, ix = rt.sk, rt.ix
BIND_HIPS = R.from_quat(sk["q"][ix["Hips"]])
cache = {}


def fk_positions(hips, Q):
    """позиции суставов цели по кадрам (для пола и центра)"""
    names = ["Hips", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase", "LeftLeg", "RightLeg", "Spine2"]
    out = np.zeros((len(hips), len(names), 3))
    t = [x.copy() for x in sk["t"]]
    for f in range(len(hips)):
        ql = [x.copy() for x in rt.qref]
        for k, n in enumerate(BONES): ql[ix[n]] = Q[f, k]
        t[ix["Hips"]] = hips[f]
        W, P = tgt_fk(dict(sk, t=t), ql)
        out[f] = [P[ix[n]] for n in names]
    # концы пальцев ног ниже сустава: берём запас 2 см
    return out


def autotrim(hips, Q):
    v = np.linalg.norm(np.diff(Q.reshape(len(Q), -1), axis=0), axis=1)
    v = np.convolve(v, np.ones(9) / 9, "same")
    thr = 0.25 * np.percentile(v, 90)
    on = np.where(v > thr)[0]
    if len(on) == 0: return 0, len(Q)
    a = max(0, on[0] - int(0.3 * FPS)); b = min(len(Q), on[-1] + int(0.3 * FPS))
    return a, b


def highpass(x, win):
    k = np.ones(win) / win
    pad = np.pad(x, (win // 2, win - 1 - win // 2), mode="edge")
    return x - np.convolve(pad, k, "valid")


header, chunks, off = [], [], 0
for name, src, span, root, group, title in CLIPS:
    rev = title == "reverse"
    if src not in cache:
        b = parse_bvh(f"data/bvh/{src}.bvh")
        cache[src] = rt.run(b, step=4)
    hips, Q, dt = cache[src]
    if span: a, bnd = int(span[0] / dt), int(span[1] / dt)
    else: a, bnd = autotrim(hips, Q)
    hips = hips[a:bnd].copy(); Q = Q[a:bnd].copy()
    if rev: hips = hips[::-1].copy(); Q = Q[::-1].copy()
    # разворот к зрителю и центр: по первому кадру, у связок (сесть/лечь) по общему опорному кадру
    fam = FAMILY.get(src)
    hu, Qu, _ = cache[src]
    if fam: rq, rx = Qu[int(fam[0] / dt), 0], hu[int(fam[0] / dt), [0, 2]].copy()
    else: rq, rx = Q[0, 0] if not rev else Q[-1, 0], hips[0, [0, 2]].copy()
    fwd = R.from_quat(rq).apply(BIND_HIPS.inv().apply([0, 0, 1]))
    yaw = np.arctan2(fwd[0], fwd[2])
    Ry = R.from_euler("y", -yaw)
    hips[:, 0] -= rx[0]; hips[:, 2] -= rx[1]
    hips = Ry.apply(hips)
    Q[:, 0] = (Ry * R.from_quat(Q[:, 0])).as_quat()
    # лёжа: плавно разворачиваем боком к зрителю (по высоте таза), чтобы не лежала ногами в камеру
    if group in ("lieidle", "getup", "liedown"):
        w = np.clip((0.85 - hips[:, 1]) / 0.5, 0, 1); w = w * w * (3 - 2 * w)
        Rw = R.from_euler("y", (np.deg2rad(LIE_YAW) * w)[:, None])
        hips = Rw.apply(hips)
        Q[:, 0] = (Rw * R.from_quat(Q[:, 0])).as_quat()
        # лёжа таз сдвигаем к центру платформы, чтобы тело целиком было в кадре
        lying = w > .95
        if lying.any():
            O = hips[lying][:, [0, 2]].mean(0) - np.array([LIE_SHIFT, 0])
            if group == "lieidle": LIE_O[0] = O
            O = LIE_O[0] if LIE_O[0] is not None else O
            hips[:, 0] -= O[0] * w; hips[:, 2] -= O[1] * w
    if root == "inplace":
        hips[:, 0] = highpass(hips[:, 0], int(0.9 * FPS)) * 0.15; hips[:, 2] = highpass(hips[:, 2], int(0.9 * FPS)) * 0.15
    elif root == "dance":
        win = int(4 * FPS)
        if len(hips) > win: hips[:, 0] = highpass(hips[:, 0], win); hips[:, 2] = highpass(hips[:, 2], win)
        hips[:, [0, 2]] -= hips[0, [0, 2]]
    # пол: нижняя точка тела (1-й перцентиль) -> 0; у связок считаем по всей связке
    if fam:
        key = src
        if key not in floor_cache:
            fa, fb = int(fam[1][0] / dt), int(fam[1][1] / dt)
            h2 = hu[fa:fb].copy(); h2[:, 0] -= rx[0]; h2[:, 2] -= rx[1]; h2 = Ry.apply(h2)
            Q2 = Qu[fa:fb].copy(); Q2[:, 0] = (Ry * R.from_quat(Q2[:, 0])).as_quat()
            P2 = fk_positions(h2[::3], Q2[::3]); floor_cache[key] = np.percentile(P2[:, :, 1].min(axis=1), 1)
        low = floor_cache[key]
    else:
        P = fk_positions(hips[::3], Q[::3])
        low = np.percentile(P[:, :, 1].min(axis=1), 1)
    floor_pad = 0.045 if group not in ("lieidle", "getup", "liedown") else 0.06
    hips[:, 1] -= low - floor_pad
    # непрерывность кватернионов
    for k in range(Q.shape[1]):
        for f in range(1, len(Q)):
            if np.dot(Q[f, k], Q[f - 1, k]) < 0: Q[f, k] = -Q[f, k]
    n = len(Q)
    hp = np.clip(np.round(hips * 2000), -32767, 32767).astype("<i2")
    qq = np.clip(np.round(Q * 32767), -32767, 32767).astype("<i2")
    buf = np.concatenate([hp.reshape(n, 3), qq.reshape(n, -1)], axis=1).astype("<i2").tobytes()
    header.append({"name": name, "group": group, "title": title if title != "reverse" else "", "frames": n, "offset": off})
    chunks.append(buf); off += len(buf)
    print(f"{name:12s} {src:7s} {n/FPS:5.1f}s  root={root:7s} travel={np.ptp(hips[:,0]):.2f}/{np.ptp(hips[:,2]):.2f}m")

meta = {"fps": FPS, "bones": BONES, "posScale": 1 / 2000, "quatScale": 1 / 32767, "stride": 3 + 4 * len(BONES), "clips": header}
open("../motions.json", "w").write(json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
open("../motions.bin", "wb").write(b"".join(chunks))
# поза покоя цели после выравнивания (для пальцев и неперенесённых костей)
print("total", round(off / 1e6, 2), "MB")
