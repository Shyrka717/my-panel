#!/usr/bin/env python3
"""Разметка лица на портрете -> lisa/face-data.js

Нужно один раз при смене портрета:
    pip install mediapipe numpy pillow
    curl -o face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
    python3 make-face-data.py ../../assets/lisa.webp face_landmarker.task ../face-data.js
"""
import sys, json, collections
import numpy as np
from PIL import Image
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import FaceLandmarksConnections as C

img_path, model_path, out_path = sys.argv[1:4]
im = Image.open(img_path).convert("RGB")
W, H = im.size

# детектор лучше работает на крупном лице: берём область вокруг центра и увеличиваем
S = 3
cx0, cy0, cx1, cy1 = int(W * .28), int(H * .06), int(W * .92), int(H * .47)
crop = im.crop((cx0, cy0, cx1, cy1)).resize(((cx1 - cx0) * S, (cy1 - cy0) * S), Image.LANCZOS)
opts = vision.FaceLandmarkerOptions(
    base_options=mpt.BaseOptions(model_asset_path=model_path),
    running_mode=vision.RunningMode.IMAGE, num_faces=1,
    min_face_detection_confidence=.2, min_face_presence_confidence=.2)
res = vision.FaceLandmarker.create_from_options(opts).detect(
    mp.Image(image_format=mp.ImageFormat.SRGB, data=np.array(crop)))
if not res.face_landmarks:
    sys.exit("лицо не найдено")
cw, ch = crop.size
P = np.array([[cx0 + p.x * cw / S, cy0 + p.y * ch / S, p.z * cw / S] for p in res.face_landmarks[0]])

def edges(name):
    return [(c.start, c.end) for c in getattr(C, name)]

def loops(es):
    adj = collections.defaultdict(list)
    for u, v in es:
        adj[u].append(v); adj[v].append(u)
    seen, out = set(), []
    for s in adj:
        if s in seen: continue
        comp, st = [s], [s]; seen.add(s)
        while st:
            x = st.pop()
            for y in adj[x]:
                if y not in seen: seen.add(y); comp.append(y); st.append(y)
        order, prev, cur = [comp[0]], None, comp[0]
        while True:
            nxt = [y for y in adj[cur] if y != prev]
            if not nxt or nxt[0] == order[0] or len(order) > len(comp): break
            order.append(nxt[0]); prev, cur = cur, nxt[0]
        out.append(order)
    return out

def area(l):
    p = P[l, :2]; x, y = p[:, 0], p[:, 1]
    return abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2

# треугольники: 3-клики рёбер тесселяции, затем убираем наложенные (лишние) клики
E = {(min(a, b), max(a, b)) for a, b in edges("FACE_LANDMARKS_TESSELATION")}
adj = collections.defaultdict(set)
for u, v in E: adj[u].add(v); adj[v].add(u)
tris = sorted({tuple(sorted((u, v, w))) for u, v in E for w in adj[u] & adj[v]})

def inside(pt, t):
    p = P[list(t), :2]
    s = lambda a, b, c: (a[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (a[1] - c[1])
    d = [s(pt, p[0], p[1]), s(pt, p[1], p[2]), s(pt, p[2], p[0])]
    return not ((min(d) < 0) and (max(d) > 0))

use = collections.defaultdict(list)
for k, t in enumerate(tris):
    for i in range(3): use[tuple(sorted((t[i], t[(i + 1) % 3])))].append(k)
drop = set()
for e, v in use.items():
    if len(v) > 2:
        for k in v:
            if all(inside(P[list(tris[j]), :2].mean(0), tris[k]) for j in v if j != k): drop.add(k)
tris = [t for k, t in enumerate(tris) if k not in drop]

lips = sorted(loops(edges("FACE_LANDMARKS_LIPS")), key=area)
lip_in, lip_out = lips[0], lips[1]
oval = loops(edges("FACE_LANDMARKS_FACE_OVAL"))[0]

def split(loop):
    """контур -> (угол1, угол2, верхняя дуга, нижняя дуга), точки упорядочены слева направо"""
    xs = P[loop, 0]
    a, b = loop[int(np.argmin(xs))], loop[int(np.argmax(xs))]
    pa, pb = P[a, :2], P[b, :2]
    up, lo = [], []
    for i in loop:
        if i in (a, b): continue
        t = (P[i, 0] - pa[0]) / (pb[0] - pa[0])
        (up if P[i, 1] < pa[1] + t * (pb[1] - pa[1]) else lo).append(i)
    key = lambda i: P[i, 0]
    return a, b, sorted(up, key=key), sorted(lo, key=key)

def eye(loop):
    a, b, up, lo = split(loop)
    c = P[loop, :2].mean(0)
    iris = None
    for base in (468, 473):
        if np.linalg.norm(P[base, :2] - c) < 12: iris = list(range(base, base + 5))
    return {"loop": loop, "a": a, "b": b, "up": up, "lo": lo, "iris": iris}

eyes = sorted([loops(edges("FACE_LANDMARKS_LEFT_EYE"))[0], loops(edges("FACE_LANDMARKS_RIGHT_EYE"))[0]],
              key=lambda l: P[l, 0].mean())
brows = sorted([sorted({i for e in edges(n) for i in e}, key=lambda i: P[i, 0])
                for n in ("FACE_LANDMARKS_LEFT_EYEBROW", "FACE_LANDMARKS_RIGHT_EYEBROW")],
               key=lambda l: P[l, 0].mean())
oa, ob, oup, olo = split(lip_out)

def lip_arcs(loop, up_ref, lo_ref):
    """внутренний контур закрытого рта плоский: верх/низ определяем по близости к дугам внешнего контура"""
    a = loop[int(np.argmin(P[loop, 0]))]; b = loop[int(np.argmax(P[loop, 0]))]
    ia_, ib_ = loop.index(a), loop.index(b)
    n = len(loop)
    arc1 = [loop[(ia_ + k) % n] for k in range(1, (ib_ - ia_) % n)]
    arc2 = [loop[(ib_ + k) % n] for k in range(1, (ia_ - ib_) % n)]
    d = lambda arc, ref: np.mean([np.min(np.linalg.norm(P[ref, :2] - P[i, :2], axis=1)) for i in arc])
    up, lo = (arc1, arc2) if d(arc1, up_ref) + d(arc2, lo_ref) < d(arc2, up_ref) + d(arc1, lo_ref) else (arc2, arc1)
    key = lambda i: P[i, 0]
    return a, b, sorted(up, key=key), sorted(lo, key=key)

ia, ib, iup, ilo = lip_arcs(lip_in, oup, olo)

data = {
    "w": W, "h": H,
    "pts": [round(float(v), 1) for v in P.reshape(-1)],
    "tris": [int(i) for t in tris for i in t],
    "oval": oval,
    "eyeA": eye(eyes[0]), "eyeB": eye(eyes[1]),
    "browA": brows[0], "browB": brows[1],
    "lipIn": {"loop": lip_in, "a": ia, "b": ib, "up": iup, "lo": ilo},
    "lipOut": {"loop": lip_out, "a": oa, "b": ob, "up": oup, "lo": olo},
    "chin": 152, "nose": 1,
}
with open(out_path, "w") as f:
    f.write("window.LISA_FACE=" + json.dumps(data, separators=(",", ":")) + ";\n")
print("точек:", len(P), "треугольников:", len(tris), "->", out_path)
