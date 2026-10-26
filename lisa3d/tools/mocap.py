"""BVH (CMU, cgspeed) -> скелет MPFB (Mixamo-совместимый)."""
import json, struct, re
import numpy as np
from scipy.spatial.transform import Rotation as R


# ---------- BVH ----------
def parse_bvh(path):
    txt = open(path).read()
    head, motion = txt.split("MOTION")
    joints, stack = [], []
    tokens = re.findall(r"[^\s{}]+|[{}]", head)
    i = 0
    cur = None
    while i < len(tokens):
        t = tokens[i]
        if t in ("ROOT", "JOINT"):
            cur = {"name": tokens[i + 1], "parent": stack[-1] if stack else -1, "offset": None, "channels": [], "end": None}
            joints.append(cur); i += 2; continue
        if t == "End":
            # End Site: запоминаем смещение конца для родителя
            j = i
            while tokens[j] != "OFFSET": j += 1
            joints[stack[-1]]["end"] = np.array([float(x) for x in tokens[j + 1:j + 4]])
            depth = 0; k = i + 2
            while True:
                if tokens[k] == "{": depth += 1
                if tokens[k] == "}":
                    depth -= 1
                    if depth == 0: break
                k += 1
            i = k + 1; continue
        if t == "{":
            stack.append(len(joints) - 1); i += 1; continue
        if t == "}":
            stack.pop(); i += 1; continue
        if t == "OFFSET":
            joints[-1]["offset"] = np.array([float(x) for x in tokens[i + 1:i + 4]]); i += 4; continue
        if t == "CHANNELS":
            n = int(tokens[i + 1]); joints[-1]["channels"] = tokens[i + 2:i + 2 + n]; i += 2 + n; continue
        i += 1
    lines = motion.strip().splitlines()
    nfr = int(lines[0].split(":")[1]); ft = float(lines[1].split(":")[1])
    data = np.array([[float(x) for x in l.split()] for l in lines[2:2 + nfr]])
    return {"joints": joints, "frames": data, "dt": ft, "names": [j["name"] for j in joints]}


def bvh_fk(b, idx=None):
    """мировые повороты (Rotation[J] по кадрам) и позиции (N,J,3)"""
    F = b["frames"] if idx is None else b["frames"][idx]
    N = len(F); J = b["joints"]
    rots, pos = [None] * len(J), np.zeros((N, len(J), 3))
    col = 0
    for k, j in enumerate(J):
        ch = j["channels"]
        tr = np.zeros((N, 3)); ang = []; order = ""
        for c in ch:
            v = F[:, col]; col += 1
            if c.endswith("position"): tr[:, "XYZ".index(c[0])] = v
            else: ang.append(v); order += c[0]
        loc = R.from_euler(order, np.stack(ang, 1), degrees=True) if order else R.identity(N)
        p = j["parent"]
        if p < 0:
            rots[k] = loc; pos[:, k] = tr + j["offset"]
        else:
            rots[k] = rots[p] * loc
            pos[:, k] = pos[:, p] + rots[p].apply(np.broadcast_to(j["offset"], (N, 3)))
    b["_end"] = {j["name"]: pos[:, k] + rots[k].apply(np.broadcast_to(j["end"], (N, 3))) for k, j in enumerate(J) if j["end"] is not None}
    return rots, pos


# ---------- целевой скелет (glb) ----------
def load_glb_skeleton(path):
    b = open(path, "rb").read()
    L = struct.unpack("<I", b[12:16])[0]; j = json.loads(b[20:20 + L])
    nodes = j["nodes"]; parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []): parent[c] = i
    joints = j["skins"][0]["joints"]
    names = [nodes[i]["name"] for i in joints]
    sk = {"names": names, "parent": [], "t": [], "q": []}
    jset = {i: k for k, i in enumerate(joints)}
    for i in joints:
        n = nodes[i]
        sk["parent"].append(jset.get(parent.get(i), -1))
        sk["t"].append(np.array(n.get("translation", [0, 0, 0]), float))
        sk["q"].append(np.array(n.get("rotation", [0, 0, 0, 1]), float))
    return sk


def tgt_fk(sk, qloc):
    """qloc: список кватернионов (x,y,z,w) локальных поворотов -> мировые Rotation и позиции"""
    n = len(sk["names"]); W = [None] * n; P = np.zeros((n, 3))
    for k in range(n):
        p = sk["parent"][k]; loc = R.from_quat(qloc[k])
        if p < 0: W[k] = loc; P[k] = sk["t"][k]
        else: W[k] = W[p] * loc; P[k] = P[p] + W[p].apply(sk["t"][k])
    return W, P


# ---------- соответствие костей ----------
MAP = {  # цель <- источник
    "Hips": "Hips", "Spine": "LowerBack", "Spine1": "Spine", "Spine2": "Spine1", "Neck": "Neck", "Head": "Head",
    "LeftShoulder": "LeftShoulder", "LeftArm": "LeftArm", "LeftForeArm": "LeftForeArm", "LeftHand": "LeftHand",
    "RightShoulder": "RightShoulder", "RightArm": "RightArm", "RightForeArm": "RightForeArm", "RightHand": "RightHand",
    "LeftUpLeg": "LeftUpLeg", "LeftLeg": "LeftLeg", "LeftFoot": "LeftFoot", "LeftToeBase": "LeftToeBase",
    "RightUpLeg": "RightUpLeg", "RightLeg": "RightLeg", "RightFoot": "RightFoot", "RightToeBase": "RightToeBase",
}
BONES = list(MAP.keys())
# выравнивание позы покоя: (цель: точка направления), (источник: точка направления)
DIR = {
    "Spine": ("Spine1", "Spine"), "Spine1": ("Spine2", "Spine1"), "Spine2": ("Neck", "Neck1"), "Neck": ("Head", "Head"),
    "LeftShoulder": ("LeftArm", "LeftArm"), "LeftArm": ("LeftForeArm", "LeftForeArm"), "LeftForeArm": ("LeftHand", "LeftHand"),
    "RightShoulder": ("RightArm", "RightArm"), "RightArm": ("RightForeArm", "RightForeArm"), "RightForeArm": ("RightHand", "RightHand"),
    "LeftUpLeg": ("LeftLeg", "LeftLeg"), "LeftLeg": ("LeftFoot", "LeftFoot"), "LeftFoot": ("LeftToeBase", "LeftToeBase"),
    "RightUpLeg": ("RightLeg", "RightLeg"), "RightLeg": ("RightFoot", "RightFoot"), "RightFoot": ("RightToeBase", "RightToeBase"),
}


def frame_from(a, b):
    a = a / np.linalg.norm(a); b = b - a * np.dot(a, b); b /= np.linalg.norm(b)
    return np.stack([a, b, np.cross(a, b)], 1)


def min_rot(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = np.dot(a, b)
    if np.linalg.norm(v) < 1e-8:
        return R.identity() if c > 0 else R.from_rotvec(np.pi * np.array([0, 1, 0]))
    return R.from_rotvec(v / np.linalg.norm(v) * np.arctan2(np.linalg.norm(v), c))


class Retarget:
    def __init__(self, glb, ref_bvh):
        self.sk = load_glb_skeleton(glb)
        sk = self.sk; ix = {n: k for k, n in enumerate(sk["names"])}; self.ix = ix
        b = parse_bvh(ref_bvh); sr, sp = bvh_fk(b, [0])           # кадр 0 у cgspeed: Т-поза
        si = {n: k for k, n in enumerate(b["names"])}
        S = {n: sp[0, si[n]] for n in b["names"]}
        self.src_names = b["names"]
        q = [x.copy() for x in sk["q"]]
        # таз: вверх (к спине) и вбок (между бёдрами)
        W, P = tgt_fk(sk, q)
        Ft = frame_from(P[ix["Spine1"]] - P[ix["Hips"]], P[ix["LeftUpLeg"]] - P[ix["RightUpLeg"]])
        Fs = frame_from(S["Spine"] - S["Hips"], S["LeftUpLeg"] - S["RightUpLeg"])
        A = R.from_matrix(Fs @ Ft.T)
        q[ix["Hips"]] = (A * W[ix["Hips"]]).as_quat()
        order = ["Spine", "Spine1", "Spine2", "Neck", "LeftShoulder", "LeftArm", "LeftForeArm", "RightShoulder", "RightArm", "RightForeArm",
                 "LeftUpLeg", "LeftLeg", "LeftFoot", "RightUpLeg", "RightLeg", "RightFoot"]
        for bn in order:
            W, P = tgt_fk(sk, q)
            tc, sc = DIR[bn]
            A = min_rot(P[ix[tc]] - P[ix[bn]], S[sc] - S[MAP[bn]])
            p = sk["parent"][ix[bn]]
            q[ix[bn]] = (W[p].inv() * A * W[ix[bn]]).as_quat()
        # кисти: направление к среднему пальцу и сторона большого пальца
        for side in ("Left", "Right"):
            W, P = tgt_fk(sk, q)
            h = ix[side + "Hand"]
            Ft = frame_from(P[ix[side + "HandMiddle1"]] - P[h], P[ix[side + "HandThumb1"]] - P[h])
            th = "LThumb" if side == "Left" else "RThumb"
            Fs = frame_from(S[side + "HandIndex1"] - S[side + "Hand"], b["_end"][th][0] - S[side + "Hand"])
            A = R.from_matrix(Fs @ Ft.T)
            p = sk["parent"][h]
            q[h] = (W[p].inv() * A * W[h]).as_quat()
        self.qref = q
        W, P = tgt_fk(sk, q)
        self.Wref = {n: W[ix[n]] for n in BONES}
        self.Pref = P
        self.Wsrc0 = {MAP[n]: sr[si[MAP[n]]][0] for n in BONES}
        self.scale = P[ix["Hips"]][1] / S["Hips"][1]
        self.Wbind, self.Pbind = tgt_fk(sk, sk["q"])

    def run(self, bvh, step=4):
        """-> позиция таза (N,3) и локальные кватернионы (N,len(BONES),4) цели"""
        sk, ix = self.sk, self.ix
        idx = np.arange(1, len(bvh["frames"]), step)          # кадр 0 (Т-поза) пропускаем
        sr, sp = bvh_fk(bvh, idx)
        si = {n: k for k, n in enumerate(bvh["names"])}
        N = len(idx); Wt = {}
        for n in BONES:
            s = MAP[n]
            Wt[n] = sr[si[s]] * self.Wsrc0[s].inv() * self.Wref[n]
        Q = np.zeros((N, len(BONES), 4))
        for k, n in enumerate(BONES):
            p = sk["parent"][ix[n]]
            pn = sk["names"][p] if p >= 0 else None
            if pn is None: loc = Wt[n]
            elif pn in Wt: loc = Wt[pn].inv() * Wt[n]
            else: raise ValueError("родитель не перенесён: " + pn)
            Q[:, k] = loc.as_quat()
        hips = sp[:, si["Hips"]] * self.scale
        return hips, Q, bvh["dt"] * step
